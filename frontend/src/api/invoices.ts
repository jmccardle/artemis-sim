import { api } from './client';

export interface Invoice {
  id: string;
  contractor_id: string;
  mission_id: string;
  task_id: string | null;
  invoice_number: string;
  amount: number;
  status: string;
  description: string;
  line_items: Record<string, unknown>[];
  submitted_at: string;
  reviewed_at: string | null;
  reviewer_username: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface BudgetSummary {
  total: number;
  by_mission: Record<string, number>;
  by_contractor: Record<string, number>;
  invoice_count: number;
}

export async function listInvoices(contractorSlug: string): Promise<Invoice[]> {
  return api<Invoice[]>(`/contractors/${contractorSlug}/invoices`);
}

export async function createInvoice(
  contractorSlug: string,
  data: { mission_id: string; amount: number; description: string; line_items?: Record<string, unknown>[] },
): Promise<Invoice> {
  return api<Invoice>(`/contractors/${contractorSlug}/invoices`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateInvoiceStatus(
  contractorSlug: string,
  invoiceId: string,
  status: string,
  notes: string = '',
): Promise<Invoice> {
  return api<Invoice>(`/contractors/${contractorSlug}/invoices/${invoiceId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, notes }),
  });
}

export async function getBudget(missionId?: string): Promise<BudgetSummary> {
  const qs = missionId ? `?mission_id=${missionId}` : '';
  return api<BudgetSummary>(`/budget${qs}`);
}
