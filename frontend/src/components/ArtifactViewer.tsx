import { Component, Show, createSignal } from 'solid-js';
import type { Artifact } from '../api/tasks';

interface Props {
  artifact: Artifact;
}

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

    // Default: JSON display
    return (
      <pre class="artifact-json mono">{JSON.stringify(content, null, 2)}</pre>
    );
  };

  return (
    <div class="artifact">
      <button class="artifact-header" onClick={() => setExpanded(!expanded())}>
        <span class="artifact-type-badge">{a().artifact_type.replace(/_/g, ' ')}</span>
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
