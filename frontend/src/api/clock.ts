import { api } from './client';

export interface ClockData {
  current_time: string;
  last_advance_reason: string | null;
}

export async function getClock(): Promise<ClockData> {
  return api<ClockData>('/clock');
}

export async function advanceClock(durationSeconds: number, reason: string): Promise<ClockData> {
  return api<ClockData>('/clock/advance', {
    method: 'POST',
    body: JSON.stringify({ duration_seconds: durationSeconds, reason }),
  });
}
