import { Component, createSignal } from 'solid-js';
import { createMission } from '../api/missions';
import { addToast } from '../api/sse';

interface Props {
  onCreated?: () => void;
}

export const MissionCreateForm: Component<Props> = (props) => {
  const [name, setName] = createSignal('');
  const [arch, setArch] = createSignal('estes');
  const [submitting, setSubmitting] = createSignal(false);

  const handleSubmit = async (e: Event) => {
    e.preventDefault();
    const missionName = name().trim();
    if (!missionName) return;

    setSubmitting(true);
    try {
      const mission = await createMission(missionName, arch());
      addToast(`Mission "${mission.name}" created`, 'success');
      setName('');
      props.onCreated?.();
    } catch (err: any) {
      addToast(err.message || 'Failed to create mission', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form class="mission-form" onSubmit={handleSubmit}>
      <div class="form-group">
        <label>Mission Name</label>
        <input
          type="text"
          placeholder="e.g. Estes I"
          value={name()}
          onInput={(e) => setName(e.currentTarget.value)}
          required
        />
      </div>
      <div class="form-row">
        <div class="form-group form-group--grow">
          <label>Architecture</label>
          <select value={arch()} onChange={(e) => setArch(e.currentTarget.value)}>
            <option value="estes">Estes (5 components)</option>
          </select>
        </div>
        <button class="btn-primary" type="submit" disabled={submitting() || !name().trim()}>
          {submitting() ? 'Creating...' : 'Create Mission'}
        </button>
      </div>
    </form>
  );
};
