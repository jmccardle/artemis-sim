import { Component, For, Show, createMemo } from 'solid-js';
import type { Task } from '../../api/tasks';
import { KanbanCard } from './KanbanCard';

const COLUMNS = [
  { key: 'NOT_READY', label: 'Not Ready' },
  { key: 'AVAILABLE', label: 'Available' },
  { key: 'IN_PROGRESS', label: 'In Progress' },
  { key: 'COMPLETED', label: 'Completed' },
] as const;

interface Props {
  tasks: Task[];
  onAction?: (taskId: string, action: 'complete' | 'fail' | 'advance') => void;
  onTaskClick?: (task: Task) => void;
}

export const KanbanBoard: Component<Props> = (props) => {
  const grouped = createMemo(() => {
    const groups: Record<string, Task[]> = {};
    for (const col of COLUMNS) groups[col.key] = [];
    for (const task of props.tasks) {
      const key = task.status;
      if (groups[key]) {
        groups[key].push(task);
      } else if (key === 'FAILED' || key === 'REWORK') {
        // Show failed/rework tasks in a logical column
        groups['COMPLETED'].push(task);
      }
    }
    return groups;
  });

  return (
    <div class="kanban-board">
      <For each={COLUMNS}>
        {(col) => (
          <div class="kanban-column">
            <div class="kanban-column-header">
              <span class="kanban-column-title">{col.label}</span>
              <span class="kanban-column-count">{grouped()[col.key].length}</span>
            </div>
            <div class="kanban-column-body">
              <For each={grouped()[col.key]}>
                {(task) => (
                  <KanbanCard
                    task={task}
                    onAction={props.onAction}
                    onClick={() => props.onTaskClick?.(task)}
                  />
                )}
              </For>
              <Show when={grouped()[col.key].length === 0}>
                <div class="kanban-empty">No tasks</div>
              </Show>
            </div>
          </div>
        )}
      </For>
    </div>
  );
};
