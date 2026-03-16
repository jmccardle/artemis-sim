import { Component, createResource, createSignal, Show, For, createEffect } from 'solid-js';
import { listFacilities } from '../api/facilities';
import { listMissions } from '../api/missions';
import { getAllTasks, completeTask, failTask, advanceTask, type Task } from '../api/tasks';
import { FacilityCard } from '../components/FacilityCard';
import { StatusBadge } from '../components/StatusBadge';
import { TaskDetailModal } from '../components/TaskDetailModal';
import { PriorityWorkQueue } from '../components/PriorityWorkQueue';
import { addToast, lastFacilityEvent, lastTaskEvent } from '../api/sse';

export const GroundOps: Component = () => {
  const [facilities, { refetch: refetchFacilities }] = createResource(listFacilities);
  const [missions] = createResource(listMissions);
  const [deliveryTasks, { refetch: refetchTasks }] = createResource(
    () => missions(),
    (m) => m ? getAllTasks(m, { phase: 'DELIVERY' }) : Promise.resolve([]),
  );
  const [selectedTask, setSelectedTask] = createSignal<Task | null>(null);

  createEffect(() => { if (lastFacilityEvent()) refetchFacilities(); });
  createEffect(() => { if (lastTaskEvent()) refetchTasks(); });

  const handleAction = async (taskId: string, action: 'complete' | 'fail' | 'advance') => {
    try {
      const fn = { complete: completeTask, fail: failTask, advance: advanceTask }[action];
      await fn(taskId);
      addToast(`Task ${action}d`, 'success');
      refetchTasks();
    } catch (err: any) {
      addToast(err.message || 'Action failed', 'error');
    }
  };

  const incomingShipments = () => (deliveryTasks() || []).filter(
    t => t.status === 'IN_PROGRESS' || t.status === 'AVAILABLE',
  );

  return (
    <div>
      <div class="page-header">
        <h1 class="page-title">Ground Operations</h1>
      </div>

      <Show when={missions() && missions()!.length > 0}>
        <PriorityWorkQueue
          missions={missions()!}
          role="egs-ground-ops"
          onTaskClick={(id) => {
            const t = deliveryTasks()?.find(task => task.id === id);
            if (t) setSelectedTask(t);
          }}
          onComplete={(id) => handleAction(id, 'complete')}
        />
      </Show>

      {/* Facilities */}
      <div class="panel" style={{ 'margin-bottom': 'var(--sp-4)' }}>
        <h2 class="panel-title">Facilities</h2>
        <Show when={!facilities.loading} fallback={
          <div class="skeleton" style={{ height: '120px', width: '100%' }} />
        }>
          <Show when={(facilities() || []).length > 0} fallback={
            <div class="empty-state"><div class="empty-state-text">No facilities</div></div>
          }>
            <div class="facility-grid">
              <For each={facilities()}>
                {(f) => <FacilityCard facility={f} />}
              </For>
            </div>
          </Show>
        </Show>
      </div>

      {/* Incoming shipments */}
      <div class="panel">
        <h2 class="panel-title">Incoming Shipments ({incomingShipments().length})</h2>
        <Show when={incomingShipments().length > 0} fallback={
          <div class="empty-state"><div class="empty-state-text">No incoming shipments</div></div>
        }>
          <table class="data-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Status</th>
                <th>Contractor</th>
                <th>Facility</th>
                <th>Duration</th>
              </tr>
            </thead>
            <tbody>
              <For each={incomingShipments()}>
                {(task) => (
                  <tr onClick={() => setSelectedTask(task)} style={{ cursor: 'pointer' }}>
                    <td>{task.name}</td>
                    <td><StatusBadge status={task.status} /></td>
                    <td>{task.assigned_contractor || '—'}</td>
                    <td>{task.facility || '—'}</td>
                    <td class="col-mono">{Math.round(task.nominal_duration_seconds / 3600)}h</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </Show>
      </div>
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
