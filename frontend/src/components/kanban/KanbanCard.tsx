import { Component, Show } from 'solid-js';
import type { Task } from '../../api/tasks';
import { StatusBadge } from '../StatusBadge';

interface Props {
  task: Task;
  onAction?: (taskId: string, action: 'complete' | 'fail' | 'advance') => void;
  onClick?: () => void;
}

export const KanbanCard: Component<Props> = (props) => {
  const t = () => props.task;

  return (
    <div class="kanban-card" onClick={props.onClick}>
      <div class="kanban-card-header">
        <span class="kanban-card-name">{t().name}</span>
        <StatusBadge status={t().status} />
      </div>

      <div class="kanban-card-meta">
        <span class="kanban-card-phase">{t().phase}</span>
        <Show when={t().assigned_contractor}>
          <span class="kanban-card-contractor">{t().assigned_contractor}</span>
        </Show>
      </div>

      <Show when={props.onAction && (t().status === 'AVAILABLE' || t().status === 'IN_PROGRESS' || t().status === 'NOT_READY')}>
        <div class="kanban-card-actions" onClick={(e) => e.stopPropagation()}>
          <Show when={t().status === 'NOT_READY'}>
            <button class="btn-sm btn-sm--blue" onClick={() => props.onAction?.(t().id, 'advance')}>
              Advance
            </button>
          </Show>
          <Show when={t().status === 'AVAILABLE' || t().status === 'IN_PROGRESS'}>
            <button class="btn-sm btn-sm--green" onClick={() => props.onAction?.(t().id, 'complete')}>
              Complete
            </button>
            <button class="btn-sm btn-sm--red" onClick={() => props.onAction?.(t().id, 'fail')}>
              Fail
            </button>
          </Show>
        </div>
      </Show>
    </div>
  );
};
