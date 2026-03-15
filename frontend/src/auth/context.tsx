import { createContext, createSignal, useContext, ParentComponent } from 'solid-js';

interface AuthState {
  role: () => string | null;
  username: () => string;
  setRole: (role: string) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

const AuthContext = createContext<AuthState>();

export const AuthProvider: ParentComponent = (props) => {
  const stored = localStorage.getItem('artemis-role');
  const [role, setRoleSignal] = createSignal<string | null>(stored);
  const [username] = createSignal('dev');

  const setRole = (r: string) => {
    setRoleSignal(r);
    localStorage.setItem('artemis-role', r);
  };

  const logout = () => {
    setRoleSignal(null);
    localStorage.removeItem('artemis-role');
  };

  const isAuthenticated = () => role() !== null;

  return (
    <AuthContext.Provider value={{ role, username, setRole, logout, isAuthenticated }}>
      {props.children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
