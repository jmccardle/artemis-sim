/**
 * Thin fetch wrapper for the Artemis REST API.
 *
 * In dev-bypass mode (ARTEMIS_AUTH_DISABLED=true), sends the
 * X-Simulation-Role header so the backend identifies the user.
 */

function getRole(): string | null {
  return localStorage.getItem('artemis-role');
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = 'ApiError';
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const role = getRole();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (role) {
    headers['X-Simulation-Role'] = role;
  }

  const res = await fetch(`/api/v1${path}`, { ...options, headers });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response wasn't JSON
    }
    throw new ApiError(res.status, detail);
  }

  return res.json();
}
