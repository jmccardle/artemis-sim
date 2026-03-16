"""Scheduling service — prerequisite resolution, DAG analysis, critical path."""
from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from artemis.models.task import Task, TaskStatus


# ── Data types ─────────────────────────────────────────────────────


@dataclass
class AvailableWorkItem:
    task_id: str
    mission_id: str
    name: str
    phase: str
    task_type: str
    assigned_role: str
    assigned_contractor: str
    facility: str
    nominal_duration_seconds: int
    downstream_task_count: int
    downstream_duration_seconds: int
    on_critical_path: bool
    unblocks: list[str] = field(default_factory=list)


@dataclass
class BlockerInfo:
    task_id: str
    name: str
    status: str
    assigned_role: str
    nominal_duration_seconds: int


@dataclass
class BlockedTaskInfo:
    task_id: str
    name: str
    status: str
    other_prerequisites_met: bool


@dataclass
class BlockingAnalysisResult:
    task_id: str
    task_name: str
    task_status: str
    blocked_by: list[BlockerInfo] = field(default_factory=list)
    blocks_tasks: list[BlockedTaskInfo] = field(default_factory=list)
    estimated_unblock_seconds: int = 0
    total_downstream_impact_seconds: int = 0


@dataclass
class CriticalPathTask:
    task_id: str
    name: str
    phase: str
    status: str
    nominal_duration_seconds: int
    position_in_path: int
    cumulative_duration_seconds: int


@dataclass
class CriticalPathResult:
    total_duration_seconds: int
    tasks_on_path: list[CriticalPathTask] = field(default_factory=list)
    current_delay_seconds: int = 0


@dataclass
class WorkSuggestionsResult:
    available_same_mission: list[AvailableWorkItem] = field(default_factory=list)
    available_other_missions: list[AvailableWorkItem] = field(default_factory=list)


# ── DAG helpers ────────────────────────────────────────────────────


def _build_task_dag(
    tasks: list[Task],
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, Task]]:
    """Build predecessor and successor adjacency lists from task prerequisites.

    Returns (predecessors, successors, task_map) where keys are task ID strings.
    """
    task_map: dict[str, Task] = {str(t.id): t for t in tasks}
    predecessors: dict[str, list[str]] = {}
    successors: dict[str, list[str]] = {}

    for tid in task_map:
        predecessors[tid] = []
        successors[tid] = []

    for tid, task in task_map.items():
        prereqs = task.prerequisites if isinstance(task.prerequisites, list) else []
        for prereq_id in prereqs:
            if prereq_id in task_map:
                predecessors[tid].append(prereq_id)
                successors[prereq_id].append(tid)

    return predecessors, successors, task_map


def _compute_downstream_impact(
    task_id: str,
    task_map: dict[str, Task],
    successors: dict[str, list[str]],
) -> tuple[int, int]:
    """BFS through successor graph. Returns (count, total_nominal_seconds)."""
    visited: set[str] = set()
    queue = deque(successors.get(task_id, []))
    total_seconds = 0

    while queue:
        tid = queue.popleft()
        if tid in visited or tid not in task_map:
            continue
        visited.add(tid)
        total_seconds += task_map[tid].nominal_duration_seconds
        for succ in successors.get(tid, []):
            if succ not in visited:
                queue.append(succ)

    return len(visited), total_seconds


# ── Prerequisite resolution ────────────────────────────────────────


async def resolve_prerequisites_for_task(
    db: AsyncSession,
    completed_task_id: str,
    mission_id: str,
) -> list[Task]:
    """Transition NOT_READY → AVAILABLE for tasks whose prerequisites are now met.

    Called after a task is marked COMPLETED. Finds all NOT_READY tasks in the
    same mission that list completed_task_id as a prerequisite, then checks
    whether ALL their prerequisites are now COMPLETED.

    Returns the list of tasks that were transitioned to AVAILABLE.
    """
    mission_uuid = uuid.UUID(mission_id)

    # Get all tasks in this mission (small set: ~40 for Estes, ~150 for Artemis)
    result = await db.execute(
        select(Task).where(Task.mission_id == mission_uuid)
    )
    all_tasks = list(result.scalars().all())

    # Build lookup for status by task ID
    status_by_id: dict[str, str] = {str(t.id): t.status for t in all_tasks}

    # Find NOT_READY tasks that have completed_task_id in their prerequisites
    candidates: list[Task] = []
    for task in all_tasks:
        if task.status != TaskStatus.NOT_READY:
            continue
        prereqs = task.prerequisites if isinstance(task.prerequisites, list) else []
        if completed_task_id not in prereqs:
            continue
        candidates.append(task)

    # Check which candidates now have ALL prerequisites completed
    newly_available: list[Task] = []
    for task in candidates:
        prereqs = task.prerequisites if isinstance(task.prerequisites, list) else []
        all_met = all(
            status_by_id.get(pid) == TaskStatus.COMPLETED
            for pid in prereqs
        )
        if all_met:
            task.status = TaskStatus.AVAILABLE
            newly_available.append(task)

    return newly_available


# ── Available work query ───────────────────────────────────────────


async def get_available_work(
    db: AsyncSession,
    mission_id: uuid.UUID | None = None,
    role: str | None = None,
    contractor: str | None = None,
    facility: str | None = None,
) -> list[AvailableWorkItem]:
    """Get AVAILABLE tasks sorted by downstream impact (highest first)."""
    stmt = select(Task).where(Task.status == TaskStatus.AVAILABLE)
    if mission_id:
        stmt = stmt.where(Task.mission_id == mission_id)
    if role:
        stmt = stmt.where(Task.assigned_role == role)
    if contractor:
        stmt = stmt.where(Task.assigned_contractor == contractor)
    if facility:
        stmt = stmt.where(Task.facility == facility)

    result = await db.execute(stmt)
    available_tasks = list(result.scalars().all())

    if not available_tasks:
        return []

    # Get all tasks for missions that have available work (for DAG analysis)
    mission_ids = {t.mission_id for t in available_tasks}
    all_result = await db.execute(
        select(Task).where(Task.mission_id.in_(mission_ids))
    )
    all_tasks = list(all_result.scalars().all())

    _, successors, task_map = _build_task_dag(all_tasks)

    # Compute critical path tasks for each mission
    critical_task_ids: set[str] = set()
    for mid in mission_ids:
        mission_tasks = [t for t in all_tasks if t.mission_id == mid]
        cp = _compute_critical_path_from_tasks(mission_tasks)
        critical_task_ids.update(t.task_id for t in cp.tasks_on_path)

    items: list[AvailableWorkItem] = []
    for task in available_tasks:
        tid = str(task.id)
        count, duration = _compute_downstream_impact(tid, task_map, successors)
        direct_successors = successors.get(tid, [])
        unblock_names = [
            task_map[s].name for s in direct_successors if s in task_map
        ]
        items.append(AvailableWorkItem(
            task_id=tid,
            mission_id=str(task.mission_id),
            name=task.name,
            phase=task.phase,
            task_type=task.task_type,
            assigned_role=task.assigned_role,
            assigned_contractor=task.assigned_contractor or "",
            facility=task.facility or "",
            nominal_duration_seconds=task.nominal_duration_seconds,
            downstream_task_count=count,
            downstream_duration_seconds=duration,
            on_critical_path=tid in critical_task_ids,
            unblocks=unblock_names,
        ))

    # Sort by downstream impact descending
    items.sort(key=lambda x: x.downstream_duration_seconds, reverse=True)
    return items


# ── Blocking analysis ──────────────────────────────────────────────


async def get_blocking_analysis(
    db: AsyncSession,
    task_id: uuid.UUID,
) -> BlockingAnalysisResult:
    """Analyze what blocks a task and what it blocks."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise ValueError(f"Task {task_id} not found")

    # Get all tasks in same mission
    all_result = await db.execute(
        select(Task).where(Task.mission_id == task.mission_id)
    )
    all_tasks = list(all_result.scalars().all())
    predecessors, successors, task_map = _build_task_dag(all_tasks)

    tid = str(task.id)

    # What blocks this task
    blocked_by: list[BlockerInfo] = []
    prereqs = task.prerequisites if isinstance(task.prerequisites, list) else []
    max_remaining = 0
    for prereq_id in prereqs:
        if prereq_id in task_map:
            ptask = task_map[prereq_id]
            if ptask.status != TaskStatus.COMPLETED:
                blocked_by.append(BlockerInfo(
                    task_id=prereq_id,
                    name=ptask.name,
                    status=ptask.status,
                    assigned_role=ptask.assigned_role,
                    nominal_duration_seconds=ptask.nominal_duration_seconds,
                ))
                max_remaining = max(max_remaining, ptask.nominal_duration_seconds)

    # What this task blocks
    blocks_tasks: list[BlockedTaskInfo] = []
    for succ_id in successors.get(tid, []):
        if succ_id in task_map:
            stask = task_map[succ_id]
            # Check if this task is the ONLY incomplete prerequisite
            other_prereqs = [
                p for p in (stask.prerequisites if isinstance(stask.prerequisites, list) else [])
                if p != tid
            ]
            other_met = all(
                task_map.get(p, task).status == TaskStatus.COMPLETED
                for p in other_prereqs
                if p in task_map
            )
            blocks_tasks.append(BlockedTaskInfo(
                task_id=succ_id,
                name=stask.name,
                status=stask.status,
                other_prerequisites_met=other_met,
            ))

    # Downstream impact
    _, downstream_seconds = _compute_downstream_impact(tid, task_map, successors)

    return BlockingAnalysisResult(
        task_id=tid,
        task_name=task.name,
        task_status=task.status,
        blocked_by=blocked_by,
        blocks_tasks=blocks_tasks,
        estimated_unblock_seconds=max_remaining,
        total_downstream_impact_seconds=downstream_seconds,
    )


# ── Work suggestions ──────────────────────────────────────────────


async def get_work_suggestions(
    db: AsyncSession,
    mission_id: uuid.UUID,
    role: str,
    blocked_task_id: uuid.UUID | None = None,
) -> WorkSuggestionsResult:
    """Suggest alternative work when a task is blocked."""
    # Get blocked task's facility (to suggest work at different facilities)
    blocked_facility: str | None = None
    if blocked_task_id:
        result = await db.execute(select(Task).where(Task.id == blocked_task_id))
        blocked_task = result.scalar_one_or_none()
        if blocked_task:
            blocked_facility = blocked_task.facility

    # Same mission, same role
    same_mission = await get_available_work(db, mission_id=mission_id, role=role)

    # Filter out the blocked task itself
    if blocked_task_id:
        blocked_str = str(blocked_task_id)
        same_mission = [w for w in same_mission if w.task_id != blocked_str]

    # Other missions, same role
    all_work = await get_available_work(db, role=role)
    other_missions = [
        w for w in all_work if w.mission_id != str(mission_id)
    ]

    # If blocked at a specific facility, prioritize work at different facilities
    if blocked_facility:
        same_mission.sort(
            key=lambda w: (w.facility == blocked_facility, -w.downstream_duration_seconds)
        )

    return WorkSuggestionsResult(
        available_same_mission=same_mission,
        available_other_missions=other_missions,
    )


# ── Critical path ─────────────────────────────────────────────────


def _compute_critical_path_from_tasks(tasks: list[Task]) -> CriticalPathResult:
    """Compute critical path through a task DAG (longest path by nominal duration).

    Uses topological sort + forward propagation of cumulative durations.
    """
    if not tasks:
        return CriticalPathResult(total_duration_seconds=0)

    predecessors, successors, task_map = _build_task_dag(tasks)

    # Topological sort (Kahn's algorithm)
    in_degree: dict[str, int] = {tid: len(predecessors[tid]) for tid in task_map}
    topo_queue: deque[str] = deque(tid for tid, deg in in_degree.items() if deg == 0)
    topo_order: list[str] = []

    while topo_queue:
        tid = topo_queue.popleft()
        topo_order.append(tid)
        for succ in successors.get(tid, []):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                topo_queue.append(succ)

    # Forward propagation: compute cumulative duration to reach each task
    cumulative: dict[str, int] = {}
    prev_on_path: dict[str, str | None] = {}

    for tid in topo_order:
        task = task_map[tid]
        max_pred_cumulative = 0
        best_pred: str | None = None

        for pred_id in predecessors.get(tid, []):
            if cumulative.get(pred_id, 0) > max_pred_cumulative:
                max_pred_cumulative = cumulative[pred_id]
                best_pred = pred_id

        cumulative[tid] = max_pred_cumulative + task.nominal_duration_seconds
        prev_on_path[tid] = best_pred

    if not cumulative:
        return CriticalPathResult(total_duration_seconds=0)

    # Find the task with maximum cumulative duration (end of critical path)
    end_task_id = max(cumulative, key=lambda k: cumulative[k])
    total_duration = cumulative[end_task_id]

    # Trace back to build the path
    path_ids: list[str] = []
    current: str | None = end_task_id
    while current is not None:
        path_ids.append(current)
        current = prev_on_path.get(current)
    path_ids.reverse()

    # Compute current delay (actual elapsed vs nominal for completed tasks on path)
    current_delay = 0
    running_cumulative = 0
    path_tasks: list[CriticalPathTask] = []

    for position, tid in enumerate(path_ids):
        task = task_map[tid]
        running_cumulative += task.nominal_duration_seconds

        path_tasks.append(CriticalPathTask(
            task_id=tid,
            name=task.name,
            phase=task.phase,
            status=task.status,
            nominal_duration_seconds=task.nominal_duration_seconds,
            position_in_path=position,
            cumulative_duration_seconds=running_cumulative,
        ))

        # If completed and has simulated timing, compute actual vs nominal
        if (task.status == TaskStatus.COMPLETED
                and task.simulated_start and task.simulated_end):
            actual = (task.simulated_end - task.simulated_start).total_seconds()
            current_delay += int(actual) - task.nominal_duration_seconds

    return CriticalPathResult(
        total_duration_seconds=total_duration,
        tasks_on_path=path_tasks,
        current_delay_seconds=max(0, current_delay),
    )


async def compute_critical_path(
    db: AsyncSession,
    mission_id: uuid.UUID,
) -> CriticalPathResult:
    """Compute critical path for a mission."""
    result = await db.execute(
        select(Task).where(Task.mission_id == mission_id)
    )
    tasks = list(result.scalars().all())
    return _compute_critical_path_from_tasks(tasks)
