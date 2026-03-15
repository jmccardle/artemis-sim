import { Component, createResource, createEffect } from 'solid-js';
import { SimulationStatus } from '../components/SimulationStatus';
import { ClockAdvanceForm } from '../components/ClockAdvanceForm';
import { MissionCreateForm } from '../components/MissionCreateForm';
import { MissionList } from '../components/MissionList';
import { getStatus } from '../api/admin';
import { listMissions } from '../api/missions';
import { resetSimulation, seedScenario, testWorkflow } from '../api/admin';
import { addToast, lastMissionEvent } from '../api/sse';
import { createSignal } from 'solid-js';

export const AdminDashboard: Component = () => {
  const [status, { refetch: refetchStatus }] = createResource(getStatus);
  const [missions, { refetch: refetchMissions }] = createResource(listMissions);
  const [resetting, setResetting] = createSignal(false);
  const [seeding, setSeeding] = createSignal(false);
  const [testing, setTesting] = createSignal(false);

  // Auto-refetch when SSE pushes a mission event
  createEffect(() => {
    const evt = lastMissionEvent();
    if (evt) {
      refetchMissions();
      refetchStatus();
    }
  });

  const handleReset = async () => {
    if (!confirm('Reset entire simulation? This deletes all missions, tasks, and artifacts.')) return;
    setResetting(true);
    try {
      await resetSimulation();
      addToast('Simulation reset', 'success');
      await Promise.all([refetchStatus(), refetchMissions()]);
    } catch (err: any) {
      addToast(err.message || 'Reset failed', 'error');
    } finally {
      setResetting(false);
    }
  };

  const handleSeed = async (scenario: string) => {
    setSeeding(true);
    try {
      await seedScenario(scenario);
      addToast(`Scenario "${scenario}" seeded`, 'success');
      await Promise.all([refetchStatus(), refetchMissions()]);
    } catch (err: any) {
      addToast(err.message || 'Seed failed', 'error');
    } finally {
      setSeeding(false);
    }
  };

  const handleTestWorkflow = async () => {
    setTesting(true);
    try {
      const result = await testWorkflow();
      addToast(`Workflow test: ${result.result}`, 'success');
    } catch (err: any) {
      addToast(err.message || 'Workflow test failed', 'error');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div>
      <div class="page-header">
        <h1 class="page-title">Mission Control</h1>
        <div class="page-actions">
          <button class="btn-secondary" onClick={handleTestWorkflow} disabled={testing()}>
            {testing() ? 'Testing...' : 'Test Temporal'}
          </button>
          <button class="btn-secondary" onClick={() => handleSeed('estes-mid-delivery')} disabled={seeding()}>
            {seeding() ? 'Seeding...' : 'Seed: Mid-Delivery'}
          </button>
          <button class="btn-danger" onClick={handleReset} disabled={resetting()}>
            {resetting() ? 'Resetting...' : 'Reset Simulation'}
          </button>
        </div>
      </div>

      <SimulationStatus status={status} />

      <div class="admin-grid">
        <div class="panel">
          <h2 class="panel-title">Clock Control</h2>
          <ClockAdvanceForm onAdvanced={() => refetchStatus()} />
        </div>
        <div class="panel">
          <h2 class="panel-title">Create Mission</h2>
          <MissionCreateForm onCreated={() => { refetchMissions(); refetchStatus(); }} />
        </div>
      </div>

      <div class="panel">
        <h2 class="panel-title">Missions</h2>
        <MissionList missions={missions} />
      </div>
    </div>
  );
};
