import { api } from './client';

export interface Mission {
  id: string;
  name: string;
  architecture_type: string;
  status: string;
  workflow_id: string | null;
  created_at: string;
  updated_at: string;
}

export async function listMissions(): Promise<Mission[]> {
  return api<Mission[]>('/missions');
}

export async function createMission(name: string, architectureType: string = 'estes'): Promise<Mission> {
  return api<Mission>('/missions', {
    method: 'POST',
    body: JSON.stringify({ name, architecture_type: architectureType }),
  });
}
