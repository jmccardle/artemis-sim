import { api } from './client';

export interface SimulationStatus {
  simulated_time: string | null;
  mission_count: number;
  task_count: number;
  facility_count: number;
  contractor_count: number;
  temporal_connected: boolean;
}

export interface ResetResponse {
  status: string;
  timestamp: string;
}

export async function getStatus(): Promise<SimulationStatus> {
  return api<SimulationStatus>('/admin/status');
}

export async function resetSimulation(): Promise<ResetResponse> {
  return api<ResetResponse>('/admin/reset', {
    method: 'POST',
    body: JSON.stringify({ confirm: true, reason: 'Admin reset via new frontend' }),
  });
}

export async function seedScenario(name: string): Promise<ResetResponse> {
  return api<ResetResponse>(`/admin/seed/${name}`, { method: 'POST' });
}

export async function testWorkflow(): Promise<{ workflow_id: string; result: string }> {
  return api('/admin/test-workflow', { method: 'POST' });
}
