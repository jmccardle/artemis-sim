import { Component, createResource } from 'solid-js';
import { getClock } from '../api/clock';
import { clockTime, sseConnected } from '../api/sse';

export const ClockDisplay: Component = () => {
  const [initialClock] = createResource(getClock);

  const displayTime = () => {
    const sse = clockTime();
    if (sse) return sse;
    const fetched = initialClock();
    return fetched?.current_time ?? null;
  };

  const formatted = () => {
    const raw = displayTime();
    if (!raw) return '--:--:-- UTC';
    try {
      const d = new Date(raw);
      return d.toISOString().replace('T', '  ').replace(/\.\d+Z$/, ' UTC');
    } catch {
      return raw;
    }
  };

  return (
    <div class="clock-display">
      <div class={`clock-dot ${sseConnected() ? 'clock-dot--connected' : 'clock-dot--disconnected'}`} />
      <div>
        <div class="clock-label">Simulated Time</div>
        <div class="clock-time">{formatted()}</div>
      </div>
    </div>
  );
};
