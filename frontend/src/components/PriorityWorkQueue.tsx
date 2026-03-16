import { Component, Show, For, createResource, createEffect } from 'solid-js';
import { getAvailableWork, formatDuration, type AvailableWorkItem } from '../api/scheduling';
import type { Mission } from '../api/missions';
import { lastTaskEvent } from '../api/sse';

interface Props {
  missions: Mission[];
  role?: string;
  contractor?: string;
  facility?: string;
  onTaskClick?: (taskId: string) => void;
  onComplete?: (taskId: string) => void;
}

export const PriorityWorkQueue: Component<Props> = (props) => {
  const filters = () => ({
    role: props.role,
    contractor: props.contractor,
    facility: props.facility,
  });

  const [items, { refetch }] = createResource(
    () => ({ missions: props.missions, filters: filters() }),
    async ({ missions, filters }) => {
      if (!missions.length) return [];
      const results = await Promise.all(
        missions.map(m => getAvailableWork(m.id, filters)),
      );
      return results.flat();
    },
  );

  createEffect(() => { if (lastTaskEvent()) refetch(); });

  return (
    <div class="priority-queue panel" style={{ 'margin-bottom': 'var(--sp-4)' }}>
      <h2 class="panel-title">Priority Work Queue</h2>
      <Show when={!items.loading} fallback={
        <div class="skeleton" style={{ height: '60px', width: '100%' }} />
      }>
        <Show when={(items() || []).length > 0} fallback={
          <div class="priority-queue-empty">
            No tasks available — all prerequisites pending.
          </div>
        }>
          <div class="priority-queue-list">
            <For each={items()}>
              {(item) => <WorkCard item={item} onTaskClick={props.onTaskClick} onComplete={props.onComplete} />}
            </For>
          </div>
        </Show>
      </Show>
    </div>
  );
};

const WorkCard: Component<{
  item: AvailableWorkItem;
  onTaskClick?: (taskId: string) => void;
  onComplete?: (taskId: string) => void;
}> = (props) => {
  const i = () => props.item;

  return (
    <div class="work-card" onClick={() => props.onTaskClick?.(i().task_id)}>
      <div class="work-card-header">
        <span class="work-card-name">{i().name}</span>
        <div class="work-card-badges">
          <span class="work-card-phase">{i().phase}</span>
          <Show when={i().on_critical_path}>
            <span class="work-card-badge work-card-badge--critical">Critical Path</span>
          </Show>
          <Show when={i().downstream_task_count > 0}>
            <span class="work-card-badge work-card-badge--unblocks">
              Unblocks {i().downstream_task_count}
            </span>
          </Show>
        </div>
      </div>
      <Show when={i().unblocks.length > 0}>
        <div class="work-card-unblocks">
          Unblocks: {i().unblocks.join(', ')}
        </div>
      </Show>
      <div class="work-card-footer">
        <span class="work-card-duration mono">{formatDuration(i().nominal_duration_seconds)}</span>
        <Show when={i().downstream_duration_seconds > 0}>
          <span class="work-card-impact dim">
            {formatDuration(i().downstream_duration_seconds)} downstream
          </span>
        </Show>
        <Show when={props.onComplete}>
          <button
            class="btn-sm btn-sm--green"
            onClick={(e) => { e.stopPropagation(); props.onComplete?.(i().task_id); }}
          >
            Complete
          </button>
        </Show>
      </div>
    </div>
  );
};
