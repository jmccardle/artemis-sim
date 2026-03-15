import { Component, createSignal, For } from 'solid-js';
import { useAuth } from './context';
import { ThemeToggle } from '../components/ThemeToggle';

const ROLES = [
  { value: 'admin', label: 'Admin', desc: 'Full simulation control' },
  { value: 'nasa-program-manager', label: 'Program Manager', desc: 'Mission oversight & Gantt' },
  { value: 'nasa-tech-authority', label: 'Tech Authority', desc: 'Review queue & scorecards' },
  { value: 'nasa-contracts-officer', label: 'Contracts Officer', desc: 'Budget & invoices' },
  { value: 'contractor-pm', label: 'Contractor PM', desc: 'RFP inbox & tasks' },
  { value: 'contractor-engineer', label: 'Contractor Engineer', desc: 'Integration kanban' },
  { value: 'egs-ground-ops', label: 'Ground Ops', desc: 'Facility management' },
];

export const DevLogin: Component = () => {
  const { setRole } = useAuth();
  const [selected, setSelected] = createSignal<string | null>(null);

  const handleLogin = () => {
    const role = selected();
    if (role) setRole(role);
  };

  return (
    <div class="login-page">
      <div class="login-card">
        <div class="login-header">
          <ThemeToggle />
        </div>

        <div class="login-brand">
          <div class="login-logo-mark">A</div>
          <div class="login-app-name">ARTEMIS</div>
          <div class="login-subtitle">Development Mode &mdash; Select Role</div>
        </div>

        <div class="login-roles">
          <For each={ROLES}>
            {(role) => (
              <button
                class={`login-role ${selected() === role.value ? 'selected' : ''}`}
                onClick={() => setSelected(role.value)}
              >
                <span class="login-role-dot" />
                <div>
                  <div class="login-role-name">{role.label}</div>
                  <div class="login-role-desc">{role.desc}</div>
                </div>
              </button>
            )}
          </For>
        </div>

        <button
          class="btn-primary login-submit"
          disabled={!selected()}
          onClick={handleLogin}
        >
          Enter Simulation
        </button>
      </div>
    </div>
  );
};
