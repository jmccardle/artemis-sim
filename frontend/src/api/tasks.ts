import { api } from './client';

export interface Task {
  id: string;
  mission_id: string;
  phase: string;
  name: string;
  task_type: string;
  status: string;
  assigned_role: string;
  assigned_contractor: string | null;
  facility: string | null;
  prerequisites: string[];
  nominal_duration_seconds: number;
  failure_probability: number;
  simulated_start: string | null;
  simulated_end: string | null;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  rework_of: string | null;
  workflow_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Artifact {
  id: string;
  task_id: string;
  artifact_type: string;
  content: Record<string, unknown>;
  created_at: string;
}

export async function getMissionTasks(
  missionId: string,
  filters?: { phase?: string; status?: string; assigned_role?: string },
): Promise<Task[]> {
  const params = new URLSearchParams();
  if (filters?.phase) params.set('phase', filters.phase);
  if (filters?.status) params.set('status', filters.status);
  if (filters?.assigned_role) params.set('assigned_role', filters.assigned_role);
  const qs = params.toString();
  return api<Task[]>(`/missions/${missionId}/tasks${qs ? `?${qs}` : ''}`);
}

export async function getTask(taskId: string): Promise<Task> {
  return api<Task>(`/tasks/${taskId}`);
}

export async function completeTask(taskId: string): Promise<Task> {
  return api<Task>(`/tasks/${taskId}/complete`, { method: 'POST' });
}

export async function failTask(taskId: string): Promise<Task> {
  return api<Task>(`/tasks/${taskId}/fail`, { method: 'POST' });
}

export async function advanceTask(taskId: string): Promise<Task> {
  return api<Task>(`/tasks/${taskId}/advance`, { method: 'POST' });
}

export async function getArtifacts(taskId: string): Promise<Artifact[]> {
  return api<Artifact[]>(`/tasks/${taskId}/artifacts`);
}

/** Fetch tasks across all missions with optional filters. */
export async function getAllTasks(
  missions: { id: string }[],
  filters?: { phase?: string; status?: string; assigned_role?: string },
): Promise<Task[]> {
  const results = await Promise.all(
    missions.map(m => getMissionTasks(m.id, filters)),
  );
  return results.flat();
}
