import { Component, createResource, createSignal, Show, For, createEffect } from 'solid-js';
import { listMissions } from '../api/missions';
import { getAllTasks, getArtifacts, completeTask, failTask, type Task, type Artifact } from '../api/tasks';
import { StatusBadge } from '../components/StatusBadge';
import { ArtifactViewer } from '../components/ArtifactViewer';
import { PriorityWorkQueue } from '../components/PriorityWorkQueue';
import { addToast, lastTaskEvent } from '../api/sse';

export const TechAuthority: Component = () => {
  const [missions] = createResource(listMissions);
  const [reviewTasks, { refetch }] = createResource(
    () => missions(),
    (m) => m ? getAllTasks(m, { assigned_role: 'nasa-tech-authority' }) : Promise.resolve([]),
  );
  const [expandedTask, setExpandedTask] = createSignal<string | null>(null);
  const [taskArtifacts, setTaskArtifacts] = createSignal<Record<string, Artifact[]>>({});
  const [acting, setActing] = createSignal<string | null>(null);

  createEffect(() => { if (lastTaskEvent()) refetch(); });

  const loadArtifacts = async (taskId: string) => {
    if (taskArtifacts()[taskId]) return;
    try {
      const arts = await getArtifacts(taskId);
      setTaskArtifacts(prev => ({ ...prev, [taskId]: arts }));
    } catch { /* ignore */ }
  };

  const toggleExpand = (taskId: string) => {
    if (expandedTask() === taskId) {
      setExpandedTask(null);
    } else {
      setExpandedTask(taskId);
      loadArtifacts(taskId);
    }
  };

  const handleAction = async (taskId: string, action: 'approve' | 'reject') => {
    setActing(taskId);
    try {
      if (action === 'approve') {
        await completeTask(taskId);
        addToast('Task approved', 'success');
      } else {
        await failTask(taskId);
        addToast('Task rejected', 'warning');
      }
      refetch();
    } catch (err: any) {
      addToast(err.message || 'Action failed', 'error');
    } finally {
      setActing(null);
    }
  };

  const pendingReview = () => (reviewTasks() || []).filter(
    t => t.status === 'AVAILABLE' || t.status === 'IN_PROGRESS',
  );
  const completedReview = () => (reviewTasks() || []).filter(
    t => t.status === 'COMPLETED' || t.status === 'FAILED',
  );

  return (
    <div>
      <div class="page-header">
        <h1 class="page-title">Technical Review Queue</h1>
      </div>

      <Show when={missions() && missions()!.length > 0}>
        <PriorityWorkQueue
          missions={missions()!}
          role="nasa-tech-authority"
        />
      </Show>

      <div class="panel" style={{ 'margin-bottom': 'var(--sp-4)' }}>
        <h2 class="panel-title">Pending Review ({pendingReview().length})</h2>
        <Show when={!reviewTasks.loading} fallback={
          <div class="skeleton" style={{ height: '100px', width: '100%' }} />
        }>
          <Show when={pendingReview().length > 0} fallback={
            <div class="empty-state"><div class="empty-state-text">No tasks awaiting review</div></div>
          }>
            <table class="data-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Phase</th>
                  <th>Status</th>
                  <th>Contractor</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <For each={pendingReview()}>
                  {(task) => (
                    <>
                      <tr onClick={() => toggleExpand(task.id)} style={{ cursor: 'pointer' }}>
                        <td>{task.name}</td>
                        <td class="col-mono">{task.phase}</td>
                        <td><StatusBadge status={task.status} /></td>
                        <td>{task.assigned_contractor || '—'}</td>
                        <td onClick={(e) => e.stopPropagation()}>
                          <div style={{ display: 'flex', gap: 'var(--sp-2)' }}>
                            <button
                              class="btn-sm btn-sm--green"
                              onClick={() => handleAction(task.id, 'approve')}
                              disabled={acting() === task.id}
                            >Approve</button>
                            <button
                              class="btn-sm btn-sm--red"
                              onClick={() => handleAction(task.id, 'reject')}
                              disabled={acting() === task.id}
                            >Reject</button>
                          </div>
                        </td>
                      </tr>
                      <Show when={expandedTask() === task.id}>
                        <tr>
                          <td colspan="5" style={{ padding: '0' }}>
                            <div class="review-expanded">
                              <Show when={taskArtifacts()[task.id]} fallback={
                                <div class="skeleton" style={{ height: '60px', width: '100%' }} />
                              }>
                                <For each={taskArtifacts()[task.id]} fallback={
                                  <div class="dim" style={{ padding: 'var(--sp-3)' }}>No artifacts</div>
                                }>
                                  {(artifact) => <ArtifactViewer artifact={artifact} />}
                                </For>
                              </Show>
                            </div>
                          </td>
                        </tr>
                      </Show>
                    </>
                  )}
                </For>
              </tbody>
            </table>
          </Show>
        </Show>
      </div>

      <Show when={completedReview().length > 0}>
        <div class="panel">
          <h2 class="panel-title">Reviewed ({completedReview().length})</h2>
          <table class="data-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Phase</th>
                <th>Result</th>
                <th>Contractor</th>
              </tr>
            </thead>
            <tbody>
              <For each={completedReview()}>
                {(task) => (
                  <tr onClick={() => toggleExpand(task.id)} style={{ cursor: 'pointer' }}>
                    <td>{task.name}</td>
                    <td class="col-mono">{task.phase}</td>
                    <td><StatusBadge status={task.status} /></td>
                    <td>{task.assigned_contractor || '—'}</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      </Show>
    </div>
  );
};
