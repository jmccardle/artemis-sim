import { Component, For, Show } from 'solid-js';
import type { Facility } from '../api/facilities';

interface Props {
  facility: Facility;
}

export const FacilityCard: Component<Props> = (props) => {
  const f = () => props.facility;
  const occupancyPct = () => f().capacity > 0 ? (f().current_occupancy / f().capacity) * 100 : 0;
  const occupancyColor = () => {
    const pct = occupancyPct();
    if (pct >= 90) return 'var(--red)';
    if (pct >= 60) return 'var(--amber)';
    return 'var(--green)';
  };

  return (
    <div class="facility-card panel">
      <div class="facility-card-header">
        <h3 class="facility-card-name">{f().name}</h3>
        <span class="facility-card-location secondary">{f().location}</span>
      </div>

      <div class="facility-occupancy">
        <div class="facility-occupancy-header">
          <span class="detail-label">Occupancy</span>
          <span class="mono" style={{ 'font-size': '0.75rem', color: occupancyColor() }}>
            {f().current_occupancy} / {f().capacity}
          </span>
        </div>
        <div class="facility-occupancy-bar">
          <div
            class="facility-occupancy-fill"
            style={{ width: `${occupancyPct()}%`, background: occupancyColor() }}
          />
        </div>
      </div>

      <Show when={f().capabilities.length > 0}>
        <div class="facility-capabilities">
          <For each={f().capabilities}>
            {(cap) => <span class="facility-capability-badge">{cap}</span>}
          </For>
        </div>
      </Show>
    </div>
  );
};
