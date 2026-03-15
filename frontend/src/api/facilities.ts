import { api } from './client';

export interface Facility {
  id: string;
  name: string;
  location: string;
  capacity: number;
  current_occupancy: number;
  capabilities: string[];
  workflow_id: string | null;
  created_at: string;
  updated_at: string;
}

export async function listFacilities(): Promise<Facility[]> {
  return api<Facility[]>('/facilities');
}
