import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Settings from '../pages/Settings';
import * as api from '../lib/api';

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
  Toaster: () => null,
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('Settings → Models tab', () => {
  it('loads agent models and saves updates', async () => {
    vi.spyOn(api, 'getAgentModels').mockResolvedValue({
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
    });
    vi.spyOn(api, 'getAvailableModels').mockResolvedValue({ models: ['m1', 'm2'] });
    const putSpy = vi.spyOn(api, 'putAgentModels').mockResolvedValue({ success: true });

    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    );

    // Wait for models tab to render rows
    await waitFor(() => {
      expect(screen.getByTestId('agent-row-generation')).toBeInTheDocument();
    });

    // Change provider for generation
    fireEvent.change(screen.getByTestId('provider-select-generation'), {
      target: { value: 'openai' },
    });

    // Save
    fireEvent.click(screen.getByTestId('save-models'));

    await waitFor(() => expect(putSpy).toHaveBeenCalledTimes(1));
    const payload = putSpy.mock.calls[0][0];
    expect(payload.agents.generation?.provider).toBe('openai');
  });

  it('reset button clears agent override', async () => {
    vi.spyOn(api, 'getAgentModels').mockResolvedValue({
      default: { provider: 'gemini', model: 'gemini-2.5-flash', temperature: 0.7 },
      agents: {
        generation: { provider: 'openai', model: 'gpt-4o', temperature: 0.5 },
        reflection: null,
        ranking: null,
        evolution: null,
        proximity: null,
        meta_review: null,
        supervisor: null,
        safety: null,
      },
    });
    vi.spyOn(api, 'getAvailableModels').mockResolvedValue({ models: ['gpt-4o'] });
    const putSpy = vi.spyOn(api, 'putAgentModels').mockResolvedValue({ success: true });

    render(
      <MemoryRouter>
        <Settings />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('agent-row-generation')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('reset-generation'));
    fireEvent.click(screen.getByTestId('save-models'));

    await waitFor(() => expect(putSpy).toHaveBeenCalled());
    expect(putSpy.mock.calls[0][0].agents.generation).toBeNull();
  });
});
