import { Component, Switch, Match } from 'solid-js';
import { AuthProvider, useAuth } from './auth/context';
import { DevLogin } from './auth/DevLogin';
import { DashboardShell } from './layouts/DashboardShell';
import { AdminDashboard } from './pages/AdminDashboard';
import { ProgramManager } from './pages/ProgramManager';
import { TechAuthority } from './pages/TechAuthority';
import { ContractsOfficer } from './pages/ContractsOfficer';
import { ContractorPM } from './pages/ContractorPM';
import { ContractorEngineer } from './pages/ContractorEngineer';
import { GroundOps } from './pages/GroundOps';

const AppContent: Component = () => {
  const { isAuthenticated, role } = useAuth();

  return (
    <Switch>
      <Match when={!isAuthenticated()}>
        <DevLogin />
      </Match>
      <Match when={isAuthenticated()}>
        <DashboardShell>
          <Switch fallback={
            <div class="empty-state">
              <div class="empty-state-icon">&#9671;</div>
              <div class="empty-state-text">
                Unknown role: "{role()}"
              </div>
            </div>
          }>
            <Match when={role() === 'admin'}>
              <AdminDashboard />
            </Match>
            <Match when={role() === 'nasa-program-manager'}>
              <ProgramManager />
            </Match>
            <Match when={role() === 'nasa-tech-authority'}>
              <TechAuthority />
            </Match>
            <Match when={role() === 'nasa-contracts-officer'}>
              <ContractsOfficer />
            </Match>
            <Match when={role() === 'contractor-pm'}>
              <ContractorPM />
            </Match>
            <Match when={role() === 'contractor-engineer'}>
              <ContractorEngineer />
            </Match>
            <Match when={role() === 'egs-ground-ops'}>
              <GroundOps />
            </Match>
          </Switch>
        </DashboardShell>
      </Match>
    </Switch>
  );
};

export const App: Component = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};
