import { Component, For, createMemo } from 'solid-js';
import type { Task } from '../api/tasks';

interface Props {
  tasks: Task[];
  label?: string;
}

const STATUS_ORDER = ['COMPLETED', 'IN_PROGRESS', 'AVAILABLE', 'NOT_READY', 'FAILED', 'REWORK'] as const;

const STATUS_COLORS: Record<string, string> = {
  COMPLETED: 'var(--green)',
  IN_PROGRESS: 'var(--blue)',
  AVAILABLE: 'var(--amber)',
  NOT_READY: 'var(--text-ghost)',
  FAILED: 'var(--red)',
  REWORK: 'var(--purple)',
};

export const ProgressBars: Component<Props> = (props) => {
  const segments = createMemo(() => {
    const total = props.tasks.length;
    if (total === 0) return [];
    const counts: Record<string, number> = {};
    for (const t of props.tasks) {
      counts[t.status] = (counts[t.status] || 0) + 1;
    }
    return STATUS_ORDER
      .filter(s => counts[s])
      .map(s => ({
        status: s,
        count: counts[s],
        pct: (counts[s] / total) * 100,
        color: STATUS_COLORS[s] || 'var(--text-dim)',
      }));
  });

  return (
    <div class="progress-bar-container">
      <div class="progress-bar">
        <For each={segments()}>
          {(seg) => (
            <div
              class="progress-bar-segment"
              style={{ width: `${seg.pct}%`, background: seg.color }}
              title={`${seg.status}: ${seg.count}`}
            />
          )}
        </For>
      </div>
      <div class="progress-bar-legend">
        <For each={segments()}>
          {(seg) => (
            <span class="progress-bar-legend-item">
              <span class="progress-bar-legend-dot" style={{ background: seg.color }} />
              {seg.status.replace(/_/g, ' ')} ({seg.count})
            </span>
          )}
        </For>
      </div>
    </div>
  );
};
