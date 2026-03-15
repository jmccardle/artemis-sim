import { Component, createResource, createSignal, Show, For, createEffect } from 'solid-js';
import { listMissions } from '../api/missions';
import { getMissionTasks, type Task } from '../api/tasks';
import { ProgressBars } from '../components/ProgressBars';
import { GanttChart } from '../components/GanttChart';
import { StatusBadge } from '../components/StatusBadge';
import { TaskDetailModal } from '../components/TaskDetailModal';
import { lastMissionEvent, lastTaskEvent } from '../api/sse';

export const ProgramManager: Component = () => {
  const [missions, { refetch: refetchMissions }] = createResource(listMissions);
  const [selectedMissionId, setSelectedMissionId] = createSignal<string | null>(null);
  const [tasks, { refetch: refetchTasks }] = createResource(
    selectedMissionId,
    (id) => id ? getMissionTasks(id) : Promise.resolve([]),
  );
  const [selectedTask, setSelectedTask] = createSignal<Task | null>(null);

  // Auto-select first mission
  createEffect(() => {
    const m = missions();
    if (m && m.length > 0 && !selectedMissionId()) {
      setSelectedMissionId(m[0].id);
    }
  });

  // Refetch on SSE events
  createEffect(() => { if (lastMissionEvent()) refetchMissions(); });
  createEffect(() => { if (lastTaskEvent()) refetchTasks(); });

  return (
    <div>
      <div class="page-header">
        <h1 class="page-title">Program Overview</h1>
        <Show when={missions()}>
          <div class="page-actions">
            <select
              value={selectedMissionId() || ''}
              onChange={(e) => setSelectedMissionId(e.currentTarget.value || null)}
              style={{ width: '220px' }}
            >
              <For each={missions()}>
                {(m) => <option value={m.id}>{m.name}</option>}
              </For>
            </select>
          </div>
        </Show>
      </div>

      {/* Mission cards overview */}
      <Show when={missions()}>
        <div class="mission-cards-grid">
          <For each={missions()}>
            {(m) => (
              <div
                class={`panel mission-overview-card ${selectedMissionId() === m.id ? 'mission-overview-card--selected' : ''}`}
                onClick={() => setSelectedMissionId(m.id)}
              >
                <div class="mission-overview-header">
                  <span class="mission-overview-name">{m.name}</span>
                  <StatusBadge status={m.status} />
                </div>
                <div class="mission-overview-arch mono">{m.architecture_type}</div>
              </div>
            )}
          </For>
        </div>
      </Show>

      {/* Task progress for selected mission */}
      <Show when={tasks() && (tasks() || []).length > 0}>
        <div class="panel" style={{ 'margin-bottom': 'var(--sp-4)' }}>
          <h2 class="panel-title">Task Progress</h2>
          <ProgressBars tasks={tasks()!} />
        </div>

        <div class="panel">
          <h2 class="panel-title">Timeline</h2>
          <GanttChart tasks={tasks()!} />
        </div>
      </Show>

      <Show when={tasks.loading}>
        <div class="panel">
          <div class="skeleton" style={{ height: '200px', width: '100%' }} />
        </div>
      </Show>

      <Show when={selectedTask()}>
        <TaskDetailModal
          task={selectedTask()!}
          onClose={() => setSelectedTask(null)}
          onTaskUpdated={() => refetchTasks()}
        />
      </Show>
    </div>
  );
};
