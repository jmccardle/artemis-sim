import { Component, Show } from 'solid-js';
import type { Resource } from 'solid-js';
import type { SimulationStatus as StatusData } from '../api/admin';

interface Props {
  status: Resource<StatusData | undefined>;
}

export const SimulationStatus: Component<Props> = (props) => {
  return (
    <div class="stats-grid">
      <Show
        when={!props.status.loading}
        fallback={
          <>
            <div class="stat-card"><div class="skeleton" style={{ height: '40px', width: '60px' }} /><div class="skeleton" style={{ height: '12px', width: '80px', 'margin-top': '8px' }} /></div>
            <div class="stat-card"><div class="skeleton" style={{ height: '40px', width: '60px' }} /><div class="skeleton" style={{ height: '12px', width: '80px', 'margin-top': '8px' }} /></div>
            <div class="stat-card"><div class="skeleton" style={{ height: '40px', width: '60px' }} /><div class="skeleton" style={{ height: '12px', width: '80px', 'margin-top': '8px' }} /></div>
          </>
        }
      >
        <Show when={props.status()}>
          {(data) => (
            <>
              <div class="stat-card">
                <div class="stat-value">{data().mission_count}</div>
                <div class="stat-label">Missions</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{data().task_count}</div>
                <div class="stat-label">Tasks</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{data().contractor_count}</div>
                <div class="stat-label">Contractors</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{data().facility_count}</div>
                <div class="stat-label">Facilities</div>
              </div>
              <div class={`stat-card ${data().temporal_connected ? 'stat-card--connected' : 'stat-card--disconnected'}`}>
                <div class="stat-value">{data().temporal_connected ? 'GO' : 'NO-GO'}</div>
                <div class="stat-label">Temporal</div>
              </div>
            </>
          )}
        </Show>
      </Show>

      <Show when={props.status.error}>
        <div class="stat-card stat-card--disconnected">
          <div class="stat-value">ERR</div>
          <div class="stat-label">API Unreachable</div>
        </div>
      </Show>
    </div>
  );
};
