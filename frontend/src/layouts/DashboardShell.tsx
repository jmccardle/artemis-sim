import { ParentComponent, onMount, onCleanup } from 'solid-js';
import { Sidebar } from './Sidebar';
import { ClockDisplay } from '../components/ClockDisplay';
import { ThemeToggle } from '../components/ThemeToggle';
import { ToastContainer } from '../components/ToastContainer';
import { useAuth } from '../auth/context';
import { connectSSE, disconnectSSE } from '../api/sse';

export const DashboardShell: ParentComponent = (props) => {
  const { role, username, logout } = useAuth();

  onMount(() => connectSSE());
  onCleanup(() => disconnectSSE());

  return (
    <div class="shell">
      <Sidebar />
      <div class="shell-main">
        <header class="topbar">
          <ClockDisplay />
          <div class="topbar-right">
            <ThemeToggle />
            <div class="topbar-user">
              <span class="topbar-role mono">{role()}</span>
              <span class="topbar-username">{username()}</span>
              <button class="btn-ghost" onClick={logout}>Logout</button>
            </div>
          </div>
        </header>
        <main class="content">
          {props.children}
        </main>
      </div>
      <ToastContainer />
    </div>
  );
};
