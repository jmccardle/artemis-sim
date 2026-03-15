import { Component } from 'solid-js';
import { useAuth } from '../auth/context';

export const Sidebar: Component = () => {
  const { role } = useAuth();

  return (
    <aside class="sidebar">
      <div class="sidebar-brand">
        <span class="sidebar-logo">&#9672;</span>
        <span class="sidebar-title">ARTEMIS</span>
      </div>

      <nav class="sidebar-nav">
        <div class="sidebar-section-label">Control</div>
        <a class={`sidebar-link ${role() === 'admin' ? 'active' : ''}`} href="#">
          <span class="sidebar-link-icon">&#9670;</span>
          Admin
        </a>

        <div class="sidebar-section-label">NASA</div>
        <a class={`sidebar-link ${role() === 'nasa-program-manager' ? 'active' : ''}`} href="#">
          <span class="sidebar-link-icon">&#9671;</span>
          Program Manager
        </a>
        <a class={`sidebar-link ${role() === 'nasa-tech-authority' ? 'active' : ''}`} href="#">
          <span class="sidebar-link-icon">&#9671;</span>
          Tech Authority
        </a>
        <a class={`sidebar-link ${role() === 'nasa-contracts-officer' ? 'active' : ''}`} href="#">
          <span class="sidebar-link-icon">&#9671;</span>
          Contracts
        </a>

        <div class="sidebar-section-label">Contractor</div>
        <a class={`sidebar-link ${role() === 'contractor-pm' ? 'active' : ''}`} href="#">
          <span class="sidebar-link-icon">&#9671;</span>
          Contractor PM
        </a>
        <a class={`sidebar-link ${role() === 'contractor-engineer' ? 'active' : ''}`} href="#">
          <span class="sidebar-link-icon">&#9671;</span>
          Engineer
        </a>

        <div class="sidebar-section-label">Ops</div>
        <a class={`sidebar-link ${role() === 'egs-ground-ops' ? 'active' : ''}`} href="#">
          <span class="sidebar-link-icon">&#9671;</span>
          Ground Ops
        </a>
      </nav>

      <div class="sidebar-footer">
        <span class="sidebar-version mono">v0.1.0</span>
      </div>
    </aside>
  );
};
