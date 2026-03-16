import { Component, Show, For, createResource } from 'solid-js';
import { getWorkSuggestions, formatDuration, type AvailableWorkItem } from '../api/scheduling';

interface Props {
  missionId: string;
  role: string;
  blockedTaskId?: string;
  onTaskClick?: (taskId: string) => void;
}

export const WorkSuggestionsPanel: Component<Props> = (props) => {
  const [suggestions] = createResource(
    () => ({ missionId: props.missionId, role: props.role, blockedTaskId: props.blockedTaskId }),
    ({ missionId, role, blockedTaskId }) => getWorkSuggestions(missionId, role, blockedTaskId),
  );

  const hasData = () => {
    const s = suggestions();
    return s && (s.available_same_mission.length > 0 || s.available_other_missions.length > 0);
  };

  return (
    <Show when={!suggestions.loading && suggestions()}>
      <div class="suggestions-panel">
        <h4 class="suggestions-title">While you wait</h4>

        <Show when={!hasData()}>
          <div class="suggestions-empty">
            No alternative work available. All tasks are waiting on prerequisites.
          </div>
        </Show>

        <Show when={suggestions()!.available_same_mission.length > 0}>
          <div class="suggestions-section">
            <div class="suggestions-section-label">Available in this mission</div>
            <div class="suggestions-list">
              <For each={suggestions()!.available_same_mission}>
                {(item) => <SuggestionCard item={item} onTaskClick={props.onTaskClick} />}
              </For>
            </div>
          </div>
        </Show>

        <Show when={suggestions()!.available_other_missions.length > 0}>
          <div class="suggestions-section">
            <div class="suggestions-section-label">Available in other missions</div>
            <div class="suggestions-list">
              <For each={suggestions()!.available_other_missions}>
                {(item) => <SuggestionCard item={item} onTaskClick={props.onTaskClick} />}
              </For>
            </div>
          </div>
        </Show>
      </div>
    </Show>
  );
};

const SuggestionCard: Component<{
  item: AvailableWorkItem;
  onTaskClick?: (taskId: string) => void;
}> = (props) => {
  const i = () => props.item;

  return (
    <div class="suggestion-card" onClick={() => props.onTaskClick?.(i().task_id)}>
      <div class="suggestion-card-header">
        <span class="suggestion-card-name">{i().name}</span>
        <span class="work-card-phase">{i().phase}</span>
      </div>
      <Show when={i().unblocks.length > 0}>
        <div class="work-card-unblocks">Unblocks: {i().unblocks.join(', ')}</div>
      </Show>
      <div class="suggestion-card-meta">
        <span class="mono dim">{formatDuration(i().nominal_duration_seconds)}</span>
        <Show when={i().on_critical_path}>
          <span class="work-card-badge work-card-badge--critical">Critical Path</span>
        </Show>
      </div>
    </div>
  );
};
