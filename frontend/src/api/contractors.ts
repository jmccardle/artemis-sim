import { api } from './client';

export interface Contractor {
  id: string;
  name: string;
  slug: string;
  reliability: number;
  cost_factor: number;
  speed_factor: number;
  specialties: string[];
  branding: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export async function listContractors(): Promise<Contractor[]> {
  return api<Contractor[]>('/contractors');
}

export async function getContractor(slug: string): Promise<Contractor> {
  return api<Contractor>(`/contractors/${slug}`);
}
