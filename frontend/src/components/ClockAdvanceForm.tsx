import { Component, createSignal } from 'solid-js';
import { advanceClock } from '../api/clock';
import { addToast } from '../api/sse';

interface Props {
  onAdvanced?: () => void;
}

export const ClockAdvanceForm: Component<Props> = (props) => {
  const [hours, setHours] = createSignal(1);
  const [reason, setReason] = createSignal('');
  const [submitting, setSubmitting] = createSignal(false);

  const handleSubmit = async (e: Event) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const seconds = Math.round(hours() * 3600);
      await advanceClock(seconds, reason() || 'Manual advance');
      addToast(`Clock advanced ${hours()}h`, 'success');
      setReason('');
      props.onAdvanced?.();
    } catch (err: any) {
      addToast(err.message || 'Failed to advance clock', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form class="clock-form" onSubmit={handleSubmit}>
      <div class="form-row">
        <div class="form-group" style={{ width: '100px' }}>
          <label>Hours</label>
          <input
            type="number"
            min="0.5"
            max="720"
            step="0.5"
            value={hours()}
            onInput={(e) => setHours(parseFloat(e.currentTarget.value) || 1)}
          />
        </div>
        <div class="form-group form-group--grow">
          <label>Reason</label>
          <input
            type="text"
            placeholder="Why advance the clock?"
            value={reason()}
            onInput={(e) => setReason(e.currentTarget.value)}
          />
        </div>
      </div>
      <button class="btn-primary" type="submit" disabled={submitting()}>
        {submitting() ? 'Advancing...' : 'Advance Clock'}
      </button>
    </form>
  );
};
