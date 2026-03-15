import { Component, createResource, Show, For, createEffect } from 'solid-js';
import { listContractors } from '../api/contractors';
import { getBudget, type BudgetSummary } from '../api/invoices';
import { listMissions } from '../api/missions';
import { getAllTasks, type Task } from '../api/tasks';
import { StatusBadge } from '../components/StatusBadge';
import { lastTaskEvent } from '../api/sse';

export const ContractsOfficer: Component = () => {
  const [contractors] = createResource(listContractors);
  const [budget] = createResource(() => getBudget());
  const [missions] = createResource(listMissions);
  const [contractTasks, { refetch }] = createResource(
    () => missions(),
    (m) => m ? getAllTasks(m, { assigned_role: 'nasa-contracts-officer' }) : Promise.resolve([]),
  );

  createEffect(() => { if (lastTaskEvent()) refetch(); });

  const formatCurrency = (n: number) => `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  return (
    <div>
      <div class="page-header">
        <h1 class="page-title">Contracts & Budget</h1>
      </div>

      {/* Budget summary */}
      <Show when={budget()}>
        {(b) => (
          <div class="stats-grid" style={{ 'margin-bottom': 'var(--sp-6)' }}>
            <div class="stat-card">
              <div class="stat-value mono">{formatCurrency(b().total)}</div>
              <div class="stat-label">Total Budget</div>
            </div>
            <div class="stat-card">
              <div class="stat-value mono">{b().invoice_count}</div>
              <div class="stat-label">Invoices</div>
            </div>
            <For each={Object.entries(b().by_contractor)}>
              {([name, amount]) => (
                <div class="stat-card">
                  <div class="stat-value mono" style={{ 'font-size': '1.25rem' }}>{formatCurrency(amount)}</div>
                  <div class="stat-label">{name}</div>
                </div>
              )}
            </For>
          </div>
        )}
      </Show>

      {/* Contractors */}
      <Show when={contractors()}>
        <div class="panel" style={{ 'margin-bottom': 'var(--sp-4)' }}>
          <h2 class="panel-title">Contractors</h2>
          <table class="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Reliability</th>
                <th>Cost Factor</th>
                <th>Speed Factor</th>
                <th>Specialties</th>
              </tr>
            </thead>
            <tbody>
              <For each={contractors()}>
                {(c) => (
                  <tr>
                    <td style={{ 'font-weight': '600' }}>{c.name}</td>
                    <td class="col-mono">{(c.reliability * 100).toFixed(0)}%</td>
                    <td class="col-mono">{c.cost_factor.toFixed(2)}x</td>
                    <td class="col-mono">{c.speed_factor.toFixed(2)}x</td>
                    <td>
                      <div style={{ display: 'flex', gap: 'var(--sp-1)', 'flex-wrap': 'wrap' }}>
                        <For each={c.specialties}>
                          {(s) => <span class="facility-capability-badge">{s}</span>}
                        </For>
                      </div>
                    </td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
        </div>
      </Show>

      {/* Contract tasks */}
      <Show when={contractTasks()}>
        <div class="panel">
          <h2 class="panel-title">Contract Tasks ({(contractTasks() || []).length})</h2>
          <Show when={(contractTasks() || []).length > 0} fallback={
            <div class="empty-state"><div class="empty-state-text">No contract tasks</div></div>
          }>
            <table class="data-table">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Phase</th>
                  <th>Status</th>
                  <th>Contractor</th>
                </tr>
              </thead>
              <tbody>
                <For each={contractTasks()}>
                  {(task) => (
                    <tr>
                      <td>{task.name}</td>
                      <td class="col-mono">{task.phase}</td>
                      <td><StatusBadge status={task.status} /></td>
                      <td>{task.assigned_contractor || '—'}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </Show>
        </div>
      </Show>
    </div>
  );
};
