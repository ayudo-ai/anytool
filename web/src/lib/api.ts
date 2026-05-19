/**
 * API client for anytool platform.
 * All requests go through the Vite proxy → /v1/* → localhost:8100
 */

const API_BASE = '/v1';

function getApiKey(): string {
  return localStorage.getItem('anytool_api_key') || '';
}

export function setApiKey(key: string) {
  localStorage.setItem('anytool_api_key', key);
}

export function clearApiKey() {
  localStorage.removeItem('anytool_api_key');
}

export function hasApiKey(): boolean {
  return !!getApiKey();
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const key = getApiKey();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(key ? { Authorization: `Bearer ${key}` } : {}),
      ...((options.headers as Record<string, string>) || {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || body.message || `HTTP ${res.status}`);
  }

  return res.json();
}

// ── Auth ────────────────────────────────────────────────────────────

export function getGoogleConfig() {
  return request<{ client_id: string }>('/auth/google/config');
}

export interface GoogleLoginResponse {
  api_key: string;
  account_id: string;
  workspace_id: string;
  name: string;
  email: string;
  picture: string;
  is_new: boolean;
}

export function googleLogin(idToken: string) {
  return request<GoogleLoginResponse>('/auth/google', {
    method: 'POST',
    body: JSON.stringify({ id_token: idToken }),
  });
}

export interface SignupResponse {
  api_key: string;
  account_id: string;
  workspace_id: string;
  workspace_name: string;
  plan: string;
  message: string;
}

export function signup(name: string, email: string) {
  return request<SignupResponse>('/accounts', {
    method: 'POST',
    body: JSON.stringify({ name, email }),
  });
}

export function getMe() {
  return request<{
    account: { id: string; name: string; email: string; plan: string };
    workspace: { id: string; name: string };
    usage: { calls_this_month: number; max_calls: number };
    limits: Record<string, number>;
  }>('/accounts/me');
}

// ── Dashboard ───────────────────────────────────────────────────────

export function getDashboardOverview() {
  return request<{
    plan: string;
    calls_this_month: number;
    max_calls: number;
    active_connections: number;
    max_connections: number;
    active_triggers: number;
    max_triggers: number;
    triggers_with_errors: number;
  }>('/dashboard/overview');
}

export function getDashboardUsage(days = 30) {
  return request<{
    days: { date: string; total: number; successful: number; failed: number; avg_duration_ms: number }[];
    total_days: number;
  }>(`/dashboard/usage?days=${days}`);
}

export function getDashboardLogs(params?: {
  limit?: number;
  offset?: number;
  action?: string;
  user_id?: string;
  successful?: boolean;
}) {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  if (params?.action) qs.set('action', params.action);
  if (params?.user_id) qs.set('user_id', params.user_id);
  if (params?.successful !== undefined) qs.set('successful', String(params.successful));
  return request<{
    logs: {
      id: string;
      action: string;
      provider: string;
      user_id: string;
      successful: boolean;
      status_code: number;
      duration_ms: number;
      error: string | null;
      created_at: string;
    }[];
    total: number;
  }>(`/dashboard/logs?${qs}`);
}

export function getDashboardConnections(userId?: string) {
  const qs = userId ? `?user_id=${userId}` : '';
  return request<{
    connections: {
      user_id: string;
      provider: string;
      status: string;
      connected_at: string;
    }[];
    total: number;
  }>(`/dashboard/connections${qs}`);
}

// ── Connections ─────────────────────────────────────────────────────

export function connectApp(provider: string, userId: string) {
  return request<{ auth_url: string }>('/connections', {
    method: 'POST',
    body: JSON.stringify({ provider, user_id: userId }),
  });
}

export function checkConnection(provider: string, userId: string) {
  return request<{ connected: boolean }>(`/connections/check?provider=${provider}&user_id=${userId}`);
}

// ── Actions ─────────────────────────────────────────────────────────

export function listActions(app?: string) {
  const qs = app ? `?app=${app}` : '';
  return request<{
    actions: {
      name: string;
      app: string;
      description: string;
      method: string;
      params: {
        name: string;
        type: string;
        required: boolean;
        description: string;
        location: string;
      }[];
    }[];
    total: number;
  }>(`/actions${qs}`);
}

// ── Execute ─────────────────────────────────────────────────────────

export function executeAction(action: string, userId: string, params: Record<string, unknown>) {
  return request<{
    successful: boolean;
    data: unknown;
    error: string | null;
    extracted_ids: Record<string, string>;
    status_code: number;
  }>('/execute', {
    method: 'POST',
    body: JSON.stringify({ action, user_id: userId, params }),
  });
}

// ── Triggers ────────────────────────────────────────────────────────

export function listTriggers(userId?: string) {
  const qs = userId ? `?user_id=${userId}` : '';
  return request<{
    triggers: {
      trigger_id: string;
      trigger_type: string;
      provider: string;
      user_id: string;
      webhook_url: string;
      filters: Record<string, unknown>;
      poll_interval_seconds: number;
      enabled: boolean;
      last_poll_at: string | null;
      created_at: string;
    }[];
    total: number;
  }>(`/triggers${qs}`);
}

export function deployTrigger(data: {
  trigger_type: string;
  user_id: string;
  webhook_url: string;
  filters?: Record<string, unknown>;
  poll_interval_seconds?: number;
}) {
  return request<{ trigger_id: string; status: string }>('/triggers', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function removeTrigger(triggerId: string) {
  return request<{ removed: boolean }>(`/triggers/${triggerId}`, { method: 'DELETE' });
}

export function listTriggerTypes() {
  return request<{
    trigger_types: { type: string; provider: string; description: string }[];
  }>('/triggers/types');
}

// ── API Keys ────────────────────────────────────────────────────────

export function listApiKeys() {
  return request<{
    keys: {
      key_id: string;
      key_masked: string;
      label: string;
      workspace_id: string;
      created_at: string;
    }[];
    total: number;
  }>('/keys');
}

export function createApiKey(label?: string) {
  return request<{ api_key: string; label: string }>('/keys', {
    method: 'POST',
    body: JSON.stringify({ label: label || '' }),
  });
}

export function revokeApiKey(keyId: string) {
  return request<{ revoked: boolean }>(`/keys/${keyId}`, { method: 'DELETE' });
}
