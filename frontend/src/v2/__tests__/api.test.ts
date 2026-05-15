import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  apiClient,
  completeSetup,
  createRun,
  exportRunEmail,
  getAgentModels,
  getAvailableModels,
  getRun,
  getSecrets,
  getSetupStatus,
  putAgentModels,
  putSecrets,
  validateApiKey,
} from '../lib/api';

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('api client', () => {
  it('getSetupStatus returns response data', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: { completed: true, missing_steps: [] },
    });
    const result = await getSetupStatus();
    expect(result.completed).toBe(true);
  });

  it('getSetupStatus falls back when backend missing', async () => {
    vi.spyOn(apiClient, 'get').mockRejectedValueOnce(new Error('boom'));
    const result = await getSetupStatus();
    expect(result.completed).toBe(false);
    expect(result.missing_steps).toContain('providers');
  });

  it('validateApiKey wraps error responses', async () => {
    vi.spyOn(apiClient, 'post').mockRejectedValueOnce(new Error('bad key'));
    const result = await validateApiKey('gemini', 'sk-xxx');
    expect(result.valid).toBe(false);
    expect(result.error).toBe('bad key');
  });

  it('validateApiKey returns successful response', async () => {
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
      data: { valid: true, available_models: ['gemini-2.5-flash'] },
    });
    const result = await validateApiKey('gemini', 'good-key');
    expect(result.valid).toBe(true);
    expect(result.available_models).toEqual(['gemini-2.5-flash']);
  });

  it('completeSetup posts to correct endpoint', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
      data: { success: true },
    });
    await completeSetup({
      providers: { gemini: 'sk' },
      optional: { semantic_scholar: true },
      export_folder: '/tmp',
      email: { enabled: false },
    });
    expect(spy).toHaveBeenCalledWith(
      '/api/setup/complete',
      expect.objectContaining({ providers: { gemini: 'sk' } }),
    );
  });

  it('getRun fetches a single run', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: { id: 'abc', goal: 'g', status: 'running', created_at: 'now' },
    });
    const run = await getRun('abc');
    expect(spy).toHaveBeenCalledWith('/api/runs/abc');
    expect(run.id).toBe('abc');
  });

  it('createRun posts payload', async () => {
    const spy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
      data: { id: 'r1', goal: 'x', status: 'pending', created_at: 'now' },
    });
    const created = await createRun({
      goal: { description: 'x', constraints: [], preferences: [] },
    });
    expect(spy).toHaveBeenCalledWith(
      '/api/runs',
      expect.objectContaining({ goal: expect.any(Object) }),
    );
    expect(created.id).toBe('r1');
  });

  it('exportRunEmail returns mailto', async () => {
    vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
      data: { mailto_url: 'mailto:test@example.com?subject=...', html_report_path: '/x.html' },
    });
    const res = await exportRunEmail('r1');
    expect(res.mailto_url.startsWith('mailto:')).toBe(true);
  });

  it('getSecrets returns shape', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        providers: { gemini: { set: true, masked: '••••1234' } },
        optional: {
          tavily: { set: false, masked: '' },
          semantic_scholar: { enabled: true },
          pubmed: { set: false, masked: '' },
        },
        email: { enabled: false, recipient: '' },
        export_folder: '/tmp',
      },
    });
    const s = await getSecrets();
    expect(s.providers.gemini.set).toBe(true);
  });

  it('putSecrets sends to correct endpoint', async () => {
    const spy = vi.spyOn(apiClient, 'put').mockResolvedValueOnce({
      data: { success: true },
    });
    await putSecrets({
      providers: {},
      optional: { semantic_scholar: true },
      export_folder: '/x',
      email: { enabled: false },
    });
    expect(spy).toHaveBeenCalledWith('/api/settings/secrets', expect.any(Object));
  });

  it('agent-models GET and PUT', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        default: { provider: 'gemini', model: 'gemini-2.5-flash', temperature: 0.7 },
        agents: {
          generation: null,
          reflection: null,
          ranking: null,
          evolution: null,
          proximity: null,
          meta_review: null,
          supervisor: null,
          safety: null,
        },
      },
    });
    const am = await getAgentModels();
    expect(getSpy).toHaveBeenCalledWith('/api/settings/agent-models');
    expect(am.default.provider).toBe('gemini');

    const putSpy = vi.spyOn(apiClient, 'put').mockResolvedValueOnce({
      data: { success: true },
    });
    await putAgentModels(am);
    expect(putSpy).toHaveBeenCalledWith('/api/settings/agent-models', am);
  });

  it('getAvailableModels passes provider param', async () => {
    const spy = vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: { models: ['m1', 'm2'] },
    });
    const r = await getAvailableModels('openai');
    expect(spy).toHaveBeenCalledWith('/api/settings/available-models', {
      params: { provider: 'openai' },
    });
    expect(r.models).toEqual(['m1', 'm2']);
  });
});
