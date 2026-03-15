import { Component, createResource, createSignal, Show, createEffect } from 'solid-js';
import { listMissions } from '../api/missions';
import { getAllTasks, completeTask, failTask, advanceTask, type Task } from '../api/tasks';
import { KanbanBoard } from '../components/kanban/KanbanBoard';
import { TaskDetailModal } from '../components/TaskDetailModal';
import { addToast, lastTaskEvent } from '../api/sse';

export const ContractorEngineer: Component = () => {
  const [missions] = createResource(listMissions);
  const [tasks, { refetch }] = createResource(
    () => missions(),
    (m) => m ? getAllTasks(m, { assigned_role: 'contractor-engineer' }) : Promise.resolve([]),
  );
  const [selectedTask, setSelectedTask] = createSignal<Task | null>(null);

  createEffect(() => { if (lastTaskEvent()) refetch(); });

  const handleAction = async (taskId: string, action: 'complete' | 'fail' | 'advance') => {
    try {
      const fn = { complete: completeTask, fail: failTask, advance: advanceTask }[action];
      await fn(taskId);
      addToast(`Task ${action}d`, 'success');
      refetch();
    } catch (err: any) {
      addToast(err.message || 'Action failed', 'error');
    }
  };

  return (
    <div>
      <div class="page-header">
        <h1 class="page-title">Integration Tasks</h1>
      </div>

      <Show when={!tasks.loading} fallback={
        <div class="skeleton" style={{ height: '300px', width: '100%' }} />
      }>
        <Show when={(tasks() || []).length > 0} fallback={
          <div class="panel">
            <div class="empty-state">
              <div class="empty-state-text">No tasks assigned to Contractor Engineer</div>
            </div>
          </div>
        }>
          <KanbanBoard
            tasks={tasks()!}
            onAction={handleAction}
            onTaskClick={setSelectedTask}
          />
        </Show>
      </Show>

      <Show when={selectedTask()}>
        <TaskDetailModal
          task={selectedTask()!}
          onClose={() => setSelectedTask(null)}
          onTaskUpdated={() => refetch()}
        />
      </Show>
    </div>
  );
};
