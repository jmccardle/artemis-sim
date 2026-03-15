import { Component, For, createMemo, Show } from 'solid-js';
import type { Task } from '../api/tasks';

interface Props {
  tasks: Task[];
}

const PHASE_ORDER = ['PROCUREMENT', 'DELIVERY', 'INTEGRATION', 'LAUNCH_READINESS'];
const PHASE_COLORS: Record<string, string> = {
  PROCUREMENT: 'var(--blue)',
  DELIVERY: 'var(--amber)',
  INTEGRATION: 'var(--green)',
  LAUNCH_READINESS: 'var(--red)',
};
const STATUS_OPACITY: Record<string, number> = {
  COMPLETED: 1,
  IN_PROGRESS: 0.75,
  AVAILABLE: 0.5,
  NOT_READY: 0.25,
  FAILED: 1,
  REWORK: 0.6,
};

export const GanttChart: Component<Props> = (props) => {
  const phases = createMemo(() => {
    const grouped: Record<string, Task[]> = {};
    for (const phase of PHASE_ORDER) grouped[phase] = [];
    for (const t of props.tasks) {
      if (grouped[t.phase]) grouped[t.phase].push(t);
    }
    return PHASE_ORDER.filter(p => grouped[p].length > 0).map(p => ({
      name: p,
      tasks: grouped[p],
    }));
  });

  // Compute timeline: use nominal durations laid out sequentially per phase
  const timeline = createMemo(() => {
    let globalEnd = 0;
    const phaseData = phases().map(phase => {
      let offset = 0;
      // Find where this phase starts (after previous phases)
      const phaseIdx = PHASE_ORDER.indexOf(phase.name);
      if (phaseIdx > 0) {
        for (let i = 0; i < phaseIdx; i++) {
          const prevPhase = phases().find(p => p.name === PHASE_ORDER[i]);
          if (prevPhase) {
            for (const t of prevPhase.tasks) offset += t.nominal_duration_seconds;
          }
        }
      }

      const bars = phase.tasks.map(t => {
        const start = offset;
        const duration = t.nominal_duration_seconds || 3600;
        offset += duration;
        return { task: t, start, duration, end: start + duration };
      });

      if (offset > globalEnd) globalEnd = offset;
      return { ...phase, bars };
    });
    return { phases: phaseData, totalDuration: globalEnd || 1 };
  });

  return (
    <Show when={props.tasks.length > 0} fallback={
      <div class="empty-state">
        <div class="empty-state-text">No tasks to display</div>
      </div>
    }>
      <div class="gantt">
        <For each={timeline().phases}>
          {(phase) => (
            <div class="gantt-phase">
              <div class="gantt-phase-label" style={{ color: PHASE_COLORS[phase.name] }}>
                {phase.name.replace(/_/g, ' ')}
              </div>
              <div class="gantt-rows">
                <For each={phase.bars}>
                  {(bar) => {
                    const left = (bar.start / timeline().totalDuration) * 100;
                    const width = Math.max((bar.duration / timeline().totalDuration) * 100, 1);
                    const opacity = STATUS_OPACITY[bar.task.status] ?? 0.5;
                    const isFailed = bar.task.status === 'FAILED';

                    return (
                      <div class="gantt-row">
                        <div class="gantt-task-label">{bar.task.name}</div>
                        <div class="gantt-bar-track">
                          <div
                            class={`gantt-bar ${isFailed ? 'gantt-bar--failed' : ''}`}
                            style={{
                              left: `${left}%`,
                              width: `${width}%`,
                              background: isFailed ? 'var(--red)' : PHASE_COLORS[phase.name],
                              opacity: String(opacity),
                            }}
                            title={`${bar.task.name} — ${bar.task.status} (${Math.round(bar.duration / 3600)}h)`}
                          />
                        </div>
                        <div class={`gantt-status gantt-status--${bar.task.status.toLowerCase()}`}>
                          {bar.task.status.replace(/_/g, ' ')}
                        </div>
                      </div>
                    );
                  }}
                </For>
              </div>
            </div>
          )}
        </For>
      </div>
    </Show>
  );
};
