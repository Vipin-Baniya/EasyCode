/**
 * Typed API client for Project Core backend.
 */

const API_BASE = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000') + '/api/v1';

export interface Project {
  id: number;
  name: string;
  slug: string;
  description?: string;
  workspace_path: string;
  language?: string;
  framework?: string;
  created_at: string;
}

export interface Action {
  id: number;
  project_id: number;
  intent: string;
  status: 'pending' | 'planning' | 'executing' | 'verifying' | 'completed' | 'failed' | 'rolled_back' | 'cancelled';
  plan?: Record<string, unknown>;
  execution_result?: Record<string, unknown>;
  verification_result?: Record<string, unknown>;
  reflection?: string;
  error?: string;
  requires_approval: boolean;
  created_at: string;
}

export interface CreateProjectPayload {
  name: string;
  slug?: string;
  description?: string;
  language?: string;
  framework?: string;
}

export interface CreateActionPayload {
  intent: string;
  context?: Record<string, unknown>;
  permission_level?: 'none' | 'review' | 'auto';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  projects: {
    list: () => request<Project[]>('/projects'),
    get: (id: number) => request<Project>(`/projects/${id}`),
    create: (data: CreateProjectPayload) =>
      request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
    delete: (id: number) =>
      request<void>(`/projects/${id}`, { method: 'DELETE' }),
  },
  actions: {
    get: (id: number) => request<Action>(`/actions/${id}`),
    create: (projectId: number, data: CreateActionPayload) =>
      request<Action>(`/projects/${projectId}/actions`, {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    approve: (id: number) =>
      request<{ status: string }>(`/actions/${id}/approve`, { method: 'POST' }),
    reject: (id: number) =>
      request<{ status: string }>(`/actions/${id}/reject`, { method: 'POST' }),
  },
  stats: () => request<Record<string, unknown>>('/stats'),
};
