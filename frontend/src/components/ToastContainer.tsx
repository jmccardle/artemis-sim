import { Component, For } from 'solid-js';
import { toasts, removeToast } from '../api/sse';

export const ToastContainer: Component = () => {
  return (
    <div class="toast-container">
      <For each={toasts()}>
        {(toast) => (
          <div class={`toast toast--${toast.type}`}>
            <span class="toast-indicator" />
            <span>{toast.message}</span>
            <button class="toast-close" onClick={() => removeToast(toast.id)}>
              &#10005;
            </button>
          </div>
        )}
      </For>
    </div>
  );
};
