import { Component, Show, For, createSignal } from 'solid-js';
import type { Artifact } from '../api/tasks';

interface Props {
  artifact: Artifact;
}

const typeBadgeClass = (type: string): string => {
  switch (type) {
    case 'PREFLIGHT_REPORT': return 'artifact-type-badge--blue';
    case 'NCR': return 'artifact-type-badge--red';
    case 'WAD': return 'artifact-type-badge--dark';
    case 'ESCALATION_NOTICE': return 'artifact-type-badge--amber';
    default: return '';
  }
};

export const ArtifactViewer: Component<Props> = (props) => {
  const [expanded, setExpanded] = createSignal(false);
  const a = () => props.artifact;

  const renderContent = () => {
    const content = a().content;
    const type = a().artifact_type;

    // Scorecard: criteria table
    if (type === 'SCORECARD' && content.criteria) {
      const criteria = content.criteria as Array<{ name: string; score: number; weight: number; notes?: string }>;
      return (
        <div class="artifact-scorecard">
          <table class="data-table">
            <thead>
              <tr>
                <th>Criterion</th>
                <th>Score</th>
                <th>Weight</th>
                <th>Weighted</th>
              </tr>
            </thead>
            <tbody>
              {criteria.map((c) => (
                <tr>
                  <td>{c.name}</td>
                  <td class="col-mono">{c.score}</td>
                  <td class="col-mono">{c.weight}</td>
                  <td class="col-mono">{(c.score * c.weight).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Show when={content.total_score != null}>
            <div class="artifact-total">
              Total Score: <strong class="mono">{String(content.total_score)}</strong>
            </div>
          </Show>
          <Show when={content.recommendation}>
            <div class="artifact-recommendation">
              Recommendation: <strong>{String(content.recommendation)}</strong>
            </div>
          </Show>
        </div>
      );
    }

    // Preflight Report: checklist with PASS/FAIL badges
    if (type === 'PREFLIGHT_REPORT') {
      const ready = content.ready as boolean;
      const checks = (content.checks || []) as Array<{ type: string; system: string; status: string; detail: string }>;
      const blocking = (content.blocking_reasons || []) as string[];
      const wadNumber = content.wad_number as string | undefined;

      return (
        <div class="artifact-preflight">
          <Show when={!ready && blocking.length > 0}>
            <div class="preflight-blocking-banner">
              <strong>Blocked:</strong> {blocking.join('; ')}
            </div>
          </Show>
          <table class="data-table">
            <thead>
              <tr>
                <th>System</th>
                <th>Check</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              <For each={checks}>
                {(c) => (
                  <tr class={c.status === 'FAIL' ? 'preflight-row--fail' : ''}>
                    <td class="col-mono">{c.system}</td>
                    <td>{c.type}</td>
                    <td>
                      <span class={`preflight-status preflight-status--${c.status.toLowerCase()}`}>
                        {c.status}
                      </span>
                    </td>
                    <td class="dim">{c.detail}</td>
                  </tr>
                )}
              </For>
            </tbody>
          </table>
          <Show when={wadNumber}>
            <div class="artifact-total mono">WAD: {wadNumber}</div>
          </Show>
        </div>
      );
    }

    // NCR: severity-colored alert box
    if (type === 'NCR') {
      const severity = (content.severity || 'major') as string;
      const status = (content.status || 'open') as string;
      return (
        <div class={`artifact-ncr artifact-ncr--${severity}`}>
          <div class="ncr-header">
            <strong class="mono">{String(content.ncr_number)}</strong>
            <span class={`preflight-status preflight-status--${status === 'open' ? 'fail' : 'pass'}`}>
              {status}
            </span>
          </div>
          <div class="ncr-description">{String(content.description)}</div>
        </div>
      );
    }

    // WAD: numbered step list
    if (type === 'WAD') {
      const steps = (content.steps || []) as Array<{ index: number; description: string; signed_off: boolean; signed_by?: string; signed_at?: string }>;
      const allSigned = steps.length > 0 && steps.every(s => s.signed_off);
      return (
        <div class="artifact-wad">
          <div class="wad-header">
            <strong class="mono">{String(content.wad_number)}</strong>
            <span class="dim">{String(content.procedure_name)}</span>
            <Show when={allSigned}>
              <span class="preflight-status preflight-status--pass">COMPLETE</span>
            </Show>
          </div>
          <ol class="wad-steps">
            <For each={steps}>
              {(step) => (
                <li class={`wad-step ${step.signed_off ? 'wad-step--signed' : ''}`}>
                  <span class="wad-step-icon">{step.signed_off ? '\u2713' : '\u25CB'}</span>
                  <span class="wad-step-desc">{step.description}</span>
                  <Show when={step.signed_off && step.signed_by}>
                    <span class="wad-step-signer dim mono">{step.signed_by}</span>
                  </Show>
                </li>
              )}
            </For>
          </ol>
        </div>
      );
    }

    // Escalation Notice: colored alert
    if (type === 'ESCALATION_NOTICE') {
      const level = (content.level || 'warning') as string;
      const expected = content.expected_seconds as number;
      const actual = content.actual_seconds as number;
      return (
        <div class={`artifact-escalation artifact-escalation--${level}`}>
          <div class="escalation-message">{String(content.message)}</div>
          <Show when={expected > 0 && actual > 0}>
            <div class="escalation-duration mono dim">
              Expected: {Math.round(expected / 3600)}h, Actual: {(actual / 3600).toFixed(1)}h
              {' — '}{(actual / expected).toFixed(2)}x overrun
            </div>
          </Show>
        </div>
      );
    }

    // Default: JSON display
    return (
      <pre class="artifact-json mono">{JSON.stringify(content, null, 2)}</pre>
    );
  };

  return (
    <div class="artifact">
      <button class="artifact-header" onClick={() => setExpanded(!expanded())}>
        <span class={`artifact-type-badge ${typeBadgeClass(a().artifact_type)}`}>
          {a().artifact_type.replace(/_/g, ' ')}
        </span>
        <span class="artifact-toggle">{expanded() ? '\u25B2' : '\u25BC'}</span>
      </button>
      <Show when={expanded()}>
        <div class="artifact-body">
          {renderContent()}
        </div>
      </Show>
    </div>
  );
};
