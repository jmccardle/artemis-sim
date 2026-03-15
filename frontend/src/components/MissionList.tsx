import { Component, For, Show } from 'solid-js';
import type { Resource } from 'solid-js';
import type { Mission } from '../api/missions';
import { StatusBadge } from './StatusBadge';

interface Props {
  missions: Resource<Mission[] | undefined>;
}

export const MissionList: Component<Props> = (props) => {
  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toISOString().replace('T', ' ').replace(/\.\d+Z$/, '');
    } catch {
      return iso;
    }
  };

  return (
    <Show
      when={!props.missions.loading}
      fallback={
        <div style={{ padding: 'var(--sp-4)' }}>
          <div class="skeleton" style={{ height: '16px', width: '100%', 'margin-bottom': '8px' }} />
          <div class="skeleton" style={{ height: '16px', width: '80%', 'margin-bottom': '8px' }} />
          <div class="skeleton" style={{ height: '16px', width: '90%' }} />
        </div>
      }
    >
      <Show
        when={(props.missions() || []).length > 0}
        fallback={
          <div class="empty-state">
            <div class="empty-state-icon">&#9671;</div>
            <div class="empty-state-text">No missions yet. Create one above.</div>
          </div>
        }
      >
        <table class="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Architecture</th>
              <th>Status</th>
              <th>Workflow</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            <For each={props.missions()}>
              {(mission) => (
                <tr>
                  <td>{mission.name}</td>
                  <td class="col-mono">{mission.architecture_type}</td>
                  <td><StatusBadge status={mission.status} /></td>
                  <td class="col-mono" style={{ 'font-size': '0.6875rem', color: 'var(--text-dim)' }}>
                    {mission.workflow_id
                      ? mission.workflow_id.length > 20
                        ? mission.workflow_id.slice(0, 20) + '...'
                        : mission.workflow_id
                      : '—'}
                  </td>
                  <td class="col-mono" style={{ 'font-size': '0.75rem' }}>
                    {formatDate(mission.created_at)}
                  </td>
                </tr>
              )}
            </For>
          </tbody>
        </table>
      </Show>
    </Show>
  );
};
