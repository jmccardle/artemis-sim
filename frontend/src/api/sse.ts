/**
 * SSE connection manager.
 *
 * Connects to /views/events and pushes updates into SolidJS signals.
 * Each event type maps to a signal that components can subscribe to.
 */

import { createSignal } from 'solid-js';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

let nextToastId = 0;

// ── Signals (reactive state driven by SSE) ──────────────

export const [clockTime, setClockTime] = createSignal<string | null>(null);
export const [toasts, setToasts] = createSignal<Toast[]>([]);
export const [lastTaskEvent, setLastTaskEvent] = createSignal<Record<string, unknown> | null>(null);
export const [lastMissionEvent, setLastMissionEvent] = createSignal<Record<string, unknown> | null>(null);
export const [lastFacilityEvent, setLastFacilityEvent] = createSignal<Record<string, unknown> | null>(null);
export const [sseConnected, setSseConnected] = createSignal(false);

// ── Toast helpers ───────────────────────────────────────

export function addToast(message: string, type: ToastType = 'info') {
  const id = nextToastId++;
  setToasts(prev => [...prev, { id, message, type }]);
  setTimeout(() => removeToast(id), 5000);
}

export function removeToast(id: number) {
  setToasts(prev => prev.filter(t => t.id !== id));
}

// ── Connection lifecycle ────────────────────────────────

let source: EventSource | null = null;

export function connectSSE() {
  if (source) source.close();

  source = new EventSource('/views/events');

  source.onopen = () => setSseConnected(true);
  source.onerror = () => setSseConnected(false);

  source.addEventListener('clock-updated', (e: MessageEvent) => {
    const data = JSON.parse(e.data);
    setClockTime(data.current_time);
  });

  source.addEventListener('notification', (e: MessageEvent) => {
    const data = JSON.parse(e.data);
    addToast(data.message, data.type || 'info');
  });

  source.addEventListener('task-updated', (e: MessageEvent) => {
    setLastTaskEvent(JSON.parse(e.data));
  });

  source.addEventListener('mission-updated', (e: MessageEvent) => {
    setLastMissionEvent(JSON.parse(e.data));
  });

  source.addEventListener('facility-updated', (e: MessageEvent) => {
    setLastFacilityEvent(JSON.parse(e.data));
  });
}

export function disconnectSSE() {
  if (source) {
    source.close();
    source = null;
  }
  setSseConnected(false);
}
