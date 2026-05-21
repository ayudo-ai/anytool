/**
 * API client for anytool platform.
 * 
 * Auth: Two tokens:
 * - session_token (sess_xxx): for dashboard access, stored in localStorage
 * - api_key (at_xxx): for API access, shown in dashboard Keys page
 * 
 * Dashboard requests use session_token.
 * The API key is only for developers to use in their code.
 */

const isDevelopment = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

const getApiBase = () => {
  if (isDevelopment) {
    return '/v1'; // Vite proxy handles this
  }
  return 'https://api-anytool.ayudo.ai/v1';
};

const API_BASE = getApiBase();

// ── Session management ──────────────────────────────────────────────

function getSessionToken(): string {
  return localStorage.getItem('anytool_session') || '';
}

export function setSession(token: string) {
  localStorage.setItem('anytool_session', token);
}

export function clearSession() {
  localStorage.removeItem('anytool_session');
  localStorage.removeItem('anytool_user');
  localStorage.removeItem('anytool_api_key');
}

export function isLoggedIn(): boolean {
  return !!getSessionToken();
}

// Store API key separately (shown in Keys page, used in quickstart snippets)
export function getStoredApiKey(): string {
  return localStorage.getItem('anytool_api_key') || '';
}

export function setStoredApiKey(key: string) {
  localStorage.setItem('anytool_api_key', key);
}

// ── HTTP client ─────────────────────────────────────────────────────

export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getSessionToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...((options.headers as Record<string, string>) || {}),
    },
  });

  if (res.status === 401) {
    // Session expired — clear and redirect
    clearSession();
    window.location.href = '/';
    throw new Error('Session expired');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || body.message || `HTTP ${res.status}`);
  }

  return res.json();
}

// Unauthenticated request (for auth endpoints)
async function publicRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
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
  return publicRequest<{ client_id: string }>('/auth/google/config');
}

export interface AuthResponse {
  session_token: string;
  api_key: string;
  account_id: string;
  workspace_id: string;
  name: string;
  email: string;
  picture: string;
  is_new: boolean;
}

export function googleLogin(idToken: string) {
  return publicRequest<AuthResponse>('/auth/google', {
    method: 'POST',
    body: JSON.stringify({ id_token: idToken }),
  });
}

export function emailSignup(name: string, email: string, password: string) {
  return publicRequest<AuthResponse>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ name, email, password }),
  });
}

export function emailLogin(email: string, password: string) {
  return publicRequest<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export function getMe() {
  return request<{
    account_id: string;
    workspace_id: string;
    name: string;
    email: string;
    picture: string;
    plan: string;
  }>('/auth/me');
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

export function connectUser(provider: string, userId: string) {
  return request<{ auth_url: string; user_id: string; provider: string }>('/connections', {
    method: 'POST',
    body: JSON.stringify({ provider, user_id: userId }),
  });
}

export function disconnectUser(provider: string, userId: string) {
  return request<{ disconnected: boolean }>('/connections', {
    method: 'DELETE',
    body: JSON.stringify({ provider, user_id: userId }),
  });
}

export function connectApiKey(provider: string, userId: string, apiKey: string, domain: string) {
  return request<{ connected: boolean; provider: string; user_id: string }>('/connections/api-key', {
    method: 'POST',
    body: JSON.stringify({ provider, user_id: userId, api_key: apiKey, domain }),
  });
}

export function getDashboardWebhookLogs(params?: {
  limit?: number;
  offset?: number;
  trigger_id?: string;
  user_id?: string;
  successful?: boolean;
}) {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  if (params?.trigger_id) qs.set('trigger_id', params.trigger_id);
  if (params?.user_id) qs.set('user_id', params.user_id);
  if (params?.successful !== undefined) qs.set('successful', String(params.successful));
  return request<{
    logs: {
      id: string;
      trigger_id: string;
      user_id: string;
      webhook_url: string;
      event_type: string;
      event_data: Record<string, unknown>;
      status_code: number;
      successful: boolean;
      retry_count: number;
      error: string | null;
      duration_ms: number;
      created_at: string;
    }[];
    total: number;
  }>(`/dashboard/webhook-logs?${qs}`);
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

// ── Auth Configs ─────────────────────────────────────────────────────

export interface AuthConfig {
  id: string;
  name: string;
  provider: string;
  auth_scheme: string;
  management: string;
  client_id: string;
  scopes: string[];
  redirect_uri: string;
  domain: string;
  connections_count: number;
  enabled: boolean;
  created_at: string;
}

export function listAuthConfigs() {
  return request<{ auth_configs: AuthConfig[]; total: number }>('/auth-configs');
}

export function createAuthConfig(data: {
  name: string;
  provider: string;
  auth_scheme?: string;
  management?: string;
  client_id?: string;
  client_secret?: string;
  scopes?: string[];
  redirect_uri?: string;
  api_key?: string;
  domain?: string;
}) {
  return request<{ id: string; provider: string; status: string }>('/auth-configs', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateAuthConfig(id: string, data: Record<string, unknown>) {
  return request<{ updated: boolean }>(`/auth-configs/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteAuthConfig(id: string) {
  return request<{ deleted: boolean }>(`/auth-configs/${id}`, { method: 'DELETE' });
}

export function listProviders() {
  return request<{
    providers: {
      slug: string;
      name: string;
      auth_scheme: string;
      apps: string[];
      default_scopes: string[];
    }[];
  }>('/auth-configs/providers');
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

// ── Webhook Test ────────────────────────────────────────────────────

export function listTestWebhooks(params?: { limit?: number; offset?: number }) {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  return request<{
    webhooks: {
      id: string;
      trigger_id: string;
      trigger_type: string;
      connection_id: string;
      event_data: Record<string, unknown>;
      full_payload: Record<string, unknown>;
      signature: string;
      received_at: string;
    }[];
    total: number;
  }>(`/webhook-test?${qs}`);
}
