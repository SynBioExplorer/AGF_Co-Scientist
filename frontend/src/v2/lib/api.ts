import axios, { AxiosError } from 'axios';
import type {
  AgentModelsResponse,
  CreateRunPayload,
  MailtoExport,
  ProviderId,
  RunDetail,
  RunSummary,
  SecretsResponse,
  SetupCompletePayload,
  SetupStatus,
  ValidateKeyResponse,
} from './types';

export function resolveBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const fromElectron = window.electronAPI?.getBackendUrl?.();
    if (fromElectron) return fromElectron;
  }
  // Vite injects import.meta.env at build time.
  const env = (import.meta as unknown as { env?: Record<string, string> }).env;
  return env?.VITE_API_URL || 'http://localhost:8000';
}

export const apiClient = axios.create({
  baseURL: resolveBaseUrl(),
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  config.baseURL = resolveBaseUrl();
  return config;
});

function extractError(err: unknown): string {
  if (err instanceof AxiosError) {
    const data = err.response?.data as { error?: string; detail?: string } | undefined;
    return data?.error || data?.detail || err.message;
  }
  if (err instanceof Error) return err.message;
  return 'Unknown error';
}

// ---------- Setup ----------
export async function getSetupStatus(): Promise<SetupStatus> {
  try {
    const { data } = await apiClient.get<SetupStatus>('/api/setup/status');
    return data;
  } catch {
    // If the backend doesn't yet support this endpoint, assume setup not done.
    return { completed: false, missing_steps: ['providers'] };
  }
}

export async function validateApiKey(
  provider: ProviderId,
  apiKey: string,
): Promise<ValidateKeyResponse> {
  try {
    const { data } = await apiClient.post<ValidateKeyResponse>(
      '/api/setup/validate-key',
      { provider, api_key: apiKey },
    );
    return data;
  } catch (err) {
    return { valid: false, error: extractError(err) };
  }
}

export async function completeSetup(
  payload: SetupCompletePayload,
): Promise<{ success: boolean }> {
  const { data } = await apiClient.post<{ success: boolean }>(
    '/api/setup/complete',
    payload,
  );
  return data;
}

// ---------- Settings: secrets ----------
export async function getSecrets(): Promise<SecretsResponse> {
  const { data } = await apiClient.get<SecretsResponse>('/api/settings/secrets');
  return data;
}

export async function putSecrets(
  payload: SetupCompletePayload,
): Promise<{ success: boolean }> {
  const { data } = await apiClient.put<{ success: boolean }>(
    '/api/settings/secrets',
    payload,
  );
  return data;
}

export async function deleteProviderSecret(
  provider: ProviderId,
): Promise<{ success: boolean }> {
  const { data } = await apiClient.delete<{ success: boolean }>(
    `/api/settings/secrets/${provider}`,
  );
  return data;
}

// ---------- Settings: agent models ----------
export async function getAgentModels(): Promise<AgentModelsResponse> {
  const { data } = await apiClient.get<AgentModelsResponse>('/api/settings/agent-models');
  return data;
}

export async function putAgentModels(
  payload: AgentModelsResponse,
): Promise<{ success: boolean }> {
  const { data } = await apiClient.put<{ success: boolean }>(
    '/api/settings/agent-models',
    payload,
  );
  return data;
}

export async function getAvailableModels(
  provider: ProviderId,
): Promise<{ models: string[] }> {
  try {
    const { data } = await apiClient.get<{ models: string[] }>(
      '/api/settings/available-models',
      { params: { provider } },
    );
    return data;
  } catch {
    return { models: [] };
  }
}

// ---------- Runs ----------
export async function listRuns(): Promise<RunSummary[]> {
  try {
    const { data } = await apiClient.get<RunSummary[] | { runs: RunSummary[] }>('/api/runs');
    return Array.isArray(data) ? data : data.runs ?? [];
  } catch {
    return [];
  }
}

export async function getRun(id: string): Promise<RunDetail> {
  const { data } = await apiClient.get<RunDetail>(`/api/runs/${id}`);
  return data;
}

export async function createRun(payload: CreateRunPayload): Promise<RunSummary> {
  const { data } = await apiClient.post<RunSummary>('/api/runs', payload);
  return data;
}

export async function exportRunEmail(runId: string): Promise<MailtoExport> {
  const { data } = await apiClient.post<MailtoExport>(
    `/api/runs/${runId}/export/email`,
  );
  return data;
}
