import { Component, Show, For, createResource, createSignal } from 'solid-js';
import type { Task } from '../api/tasks';
import { getArtifacts, completeTask, failTask, advanceTask } from '../api/tasks';
import { StatusBadge } from './StatusBadge';
import { ArtifactViewer } from './ArtifactViewer';
import { addToast } from '../api/sse';

interface Props {
  task: Task;
  onClose: () => void;
  onTaskUpdated?: () => void;
}

export const TaskDetailModal: Component<Props> = (props) => {
  const [artifacts] = createResource(() => props.task.id, getArtifacts);
  const [acting, setActing] = createSignal(false);

  const handleAction = async (action: 'complete' | 'fail' | 'advance') => {
    setActing(true);
    try {
      const fn = { complete: completeTask, fail: failTask, advance: advanceTask }[action];
      await fn(props.task.id);
      addToast(`Task ${action}d: ${props.task.name}`, 'success');
      props.onTaskUpdated?.();
      props.onClose();
    } catch (err: any) {
      addToast(err.message || `Failed to ${action} task`, 'error');
    } finally {
      setActing(false);
    }
  };

  const t = props.task;
  const canAct = t.status === 'AVAILABLE' || t.status === 'IN_PROGRESS' || t.status === 'NOT_READY';

  return (
    <div class="modal-backdrop" onClick={props.onClose}>
      <div class="modal" onClick={(e) => e.stopPropagation()}>
        <div class="modal-header">
          <h2 class="modal-title">{t.name}</h2>
          <button class="btn-ghost modal-close" onClick={props.onClose}>&times;</button>
        </div>

        <div class="modal-body">
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">Status</span>
              <StatusBadge status={t.status} />
            </div>
            <div class="detail-item">
              <span class="detail-label">Phase</span>
              <span class="detail-value mono">{t.phase}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Type</span>
              <span class="detail-value mono">{t.task_type}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Assigned Role</span>
              <span class="detail-value">{t.assigned_role}</span>
            </div>
            <Show when={t.assigned_contractor}>
              <div class="detail-item">
                <span class="detail-label">Contractor</span>
                <span class="detail-value">{t.assigned_contractor}</span>
              </div>
            </Show>
            <Show when={t.facility}>
              <div class="detail-item">
                <span class="detail-label">Facility</span>
                <span class="detail-value">{t.facility}</span>
              </div>
            </Show>
            <div class="detail-item">
              <span class="detail-label">Duration</span>
              <span class="detail-value mono">{Math.round(t.nominal_duration_seconds / 3600)}h</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Failure Prob.</span>
              <span class="detail-value mono">{(t.failure_probability * 100).toFixed(0)}%</span>
            </div>
            <Show when={t.simulated_start}>
              <div class="detail-item">
                <span class="detail-label">Start</span>
                <span class="detail-value mono">{t.simulated_start?.replace('T', ' ').slice(0, 19)}</span>
              </div>
            </Show>
            <Show when={t.simulated_end}>
              <div class="detail-item">
                <span class="detail-label">End</span>
                <span class="detail-value mono">{t.simulated_end?.replace('T', ' ').slice(0, 19)}</span>
              </div>
            </Show>
          </div>

          <Show when={!artifacts.loading && (artifacts() || []).length > 0}>
            <div class="detail-section">
              <h3 class="detail-section-title">Artifacts</h3>
              <For each={artifacts()}>
                {(artifact) => <ArtifactViewer artifact={artifact} />}
              </For>
            </div>
          </Show>
        </div>

        <Show when={canAct}>
          <div class="modal-footer">
            <Show when={t.status === 'NOT_READY'}>
              <button class="btn-primary" onClick={() => handleAction('advance')} disabled={acting()}>
                Advance to Available
              </button>
            </Show>
            <Show when={t.status === 'AVAILABLE' || t.status === 'IN_PROGRESS'}>
              <button class="btn-primary" onClick={() => handleAction('complete')} disabled={acting()}>
                Complete
              </button>
              <button class="btn-danger" onClick={() => handleAction('fail')} disabled={acting()}>
                Fail
              </button>
            </Show>
          </div>
        </Show>
      </div>
    </div>
  );
};
