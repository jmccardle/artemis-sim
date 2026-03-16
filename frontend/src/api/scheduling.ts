import { api } from './client';

// ── Interfaces ──────────────────────────────────────────

export interface AvailableWorkItem {
  task_id: string;
  mission_id: string;
  name: string;
  phase: string;
  task_type: string;
  assigned_role: string;
  assigned_contractor: string;
  facility: string;
  nominal_duration_seconds: number;
  downstream_task_count: number;
  downstream_duration_seconds: number;
  on_critical_path: boolean;
  unblocks: string[];
}

export interface BlockerInfo {
  task_id: string;
  name: string;
  status: string;
  assigned_role: string;
  nominal_duration_seconds: number;
}

export interface BlockedTaskInfo {
  task_id: string;
  name: string;
  status: string;
  other_prerequisites_met: boolean;
}

export interface BlockingAnalysis {
  task_id: string;
  task_name: string;
  task_status: string;
  blocked_by: BlockerInfo[];
  blocks_tasks: BlockedTaskInfo[];
  estimated_unblock_seconds: number;
  total_downstream_impact_seconds: number;
}

export interface CriticalPathTask {
  task_id: string;
  name: string;
  phase: string;
  status: string;
  nominal_duration_seconds: number;
  position_in_path: number;
  cumulative_duration_seconds: number;
}

export interface CriticalPathData {
  total_duration_seconds: number;
  tasks_on_path: CriticalPathTask[];
  current_delay_seconds: number;
}

export interface WorkSuggestions {
  available_same_mission: AvailableWorkItem[];
  available_other_missions: AvailableWorkItem[];
}

// ── API Functions ───────────────────────────────────────

export async function getAvailableWork(
  missionId: string,
  filters?: { role?: string; contractor?: string; facility?: string },
): Promise<AvailableWorkItem[]> {
  const params = new URLSearchParams();
  if (filters?.role) params.set('role', filters.role);
  if (filters?.contractor) params.set('contractor', filters.contractor);
  if (filters?.facility) params.set('facility', filters.facility);
  const qs = params.toString();
  return api<AvailableWorkItem[]>(`/missions/${missionId}/available-work${qs ? `?${qs}` : ''}`);
}

export async function getBlockingAnalysis(taskId: string): Promise<BlockingAnalysis> {
  return api<BlockingAnalysis>(`/tasks/${taskId}/blocking-analysis`);
}

export async function getWorkSuggestions(
  missionId: string,
  role: string,
  blockedTaskId?: string,
): Promise<WorkSuggestions> {
  const params = new URLSearchParams({ role });
  if (blockedTaskId) params.set('blocked_task_id', blockedTaskId);
  return api<WorkSuggestions>(`/missions/${missionId}/work-suggestions?${params}`);
}

export async function getCriticalPath(missionId: string): Promise<CriticalPathData> {
  return api<CriticalPathData>(`/missions/${missionId}/critical-path`);
}

// ── Helpers ─────────────────────────────────────────────

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}
