import { Component, createSignal, onMount } from 'solid-js';

const [theme, setThemeSignal] = createSignal<'light' | 'dark'>('light');

function applyTheme(t: 'light' | 'dark') {
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('artemis-theme', t);
  setThemeSignal(t);
}

export const ThemeToggle: Component = () => {
  onMount(() => {
    const stored = localStorage.getItem('artemis-theme') as 'light' | 'dark' | null;
    applyTheme(stored || 'light');
  });

  const toggle = () => {
    applyTheme(theme() === 'light' ? 'dark' : 'light');
  };

  return (
    <button class="theme-toggle" onClick={toggle} title="Toggle light/dark mode">
      {theme() === 'light' ? '\u263E' : '\u2600'}{' '}
      {theme() === 'light' ? 'Dark' : 'Light'}
    </button>
  );
};
