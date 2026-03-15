import { Component } from 'solid-js';

interface Props {
  status: string;
}

export const StatusBadge: Component<Props> = (props) => {
  const normalized = () => props.status.toLowerCase().replace(/ /g, '_');

  return (
    <span class={`status-badge status-badge--${normalized()}`}>
      <span class="status-dot" />
      {props.status.replace(/_/g, ' ')}
    </span>
  );
};
