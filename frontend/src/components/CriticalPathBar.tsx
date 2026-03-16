import { Component, Show, For, createResource, createEffect } from 'solid-js';
import { getCriticalPath, formatDuration, type CriticalPathData } from '../api/scheduling';
import { lastTaskEvent } from '../api/sse';

interface Props {
  missionId: string;
}

const statusColor = (status: string): string => {
  switch (status) {
    case 'COMPLETED': return 'var(--green)';
    case 'IN_PROGRESS': return 'var(--blue)';
    case 'AVAILABLE': return 'var(--amber)';
    case 'FAILED': return 'var(--red)';
    default: return 'var(--border-strong)';
  }
};

export const CriticalPathBar: Component<Props> = (props) => {
  const [data, { refetch }] = createResource(
    () => props.missionId,
    (id) => getCriticalPath(id),
  );

  createEffect(() => { if (lastTaskEvent()) refetch(); });

  const completedSeconds = (d: CriticalPathData) =>
    d.tasks_on_path
      .filter(t => t.status === 'COMPLETED')
      .reduce((sum, t) => sum + t.nominal_duration_seconds, 0);

  const remainingSeconds = (d: CriticalPathData) =>
    d.total_duration_seconds - completedSeconds(d);

  return (
    <Show when={data() && data()!.tasks_on_path.length > 0}>
      <div class="critical-path panel" style={{ 'margin-bottom': 'var(--sp-4)' }}>
        <h2 class="panel-title">Critical Path</h2>

        {/* Summary line */}
        <div class="critical-path-summary mono">
          {formatDuration(data()!.total_duration_seconds)} total
          {' · '}{formatDuration(completedSeconds(data()!))} completed
          <Show when={data()!.current_delay_seconds > 0}>
            {' · '}<span class="critical-path-delay">{formatDuration(data()!.current_delay_seconds)} delayed</span>
          </Show>
          {' · '}{formatDuration(remainingSeconds(data()!))} remaining
        </div>

        {/* Delay banner */}
        <Show when={data()!.current_delay_seconds > 0}>
          <div class="critical-path-delay-banner">
            Mission delayed by {formatDuration(data()!.current_delay_seconds)}
          </div>
        </Show>

        {/* Segmented bar */}
        <div class="critical-path-bar">
          <For each={data()!.tasks_on_path}>
            {(task) => {
              const pct = () =>
                data()!.total_duration_seconds > 0
                  ? (task.nominal_duration_seconds / data()!.total_duration_seconds) * 100
                  : 0;
              return (
                <div
                  class={`critical-path-segment ${task.status === 'IN_PROGRESS' ? 'critical-path-segment--active' : ''}`}
                  style={{
                    width: `${pct()}%`,
                    background: statusColor(task.status),
                  }}
                  title={`${task.name} (${task.status}) — ${formatDuration(task.nominal_duration_seconds)}`}
                />
              );
            }}
          </For>
        </div>

        {/* Task labels */}
        <div class="critical-path-labels">
          <For each={data()!.tasks_on_path}>
            {(task) => {
              const pct = () =>
                data()!.total_duration_seconds > 0
                  ? (task.nominal_duration_seconds / data()!.total_duration_seconds) * 100
                  : 0;
              return (
                <div
                  class="critical-path-label"
                  style={{ width: `${pct()}%` }}
                  title={task.name}
                >
                  <span class="critical-path-label-text">{task.name}</span>
                </div>
              );
            }}
          </For>
        </div>
      </div>
    </Show>
  );
};
