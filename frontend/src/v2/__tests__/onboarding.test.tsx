import * as React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import Onboarding from '../pages/Onboarding';
import * as api from '../lib/api';

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    message: vi.fn(),
  },
  Toaster: () => null,
}));

beforeEach(() => {
  vi.restoreAllMocks();
});

function renderWizard(): void {
  render(
    <MemoryRouter>
      <Onboarding />
    </MemoryRouter>,
  );
}

describe('Onboarding wizard', () => {
  it('renders step 1 and advances on click', async () => {
    renderWizard();
    expect(screen.getByText(/Welcome to AGF Co-Scientist/i)).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('wizard-next'));
    await waitFor(() => {
      expect(screen.getByText(/Connect a model provider/i)).toBeInTheDocument();
    });
  });

  it('disables continue on providers step until a key is entered', async () => {
    renderWizard();
    fireEvent.click(screen.getByTestId('wizard-next')); // step 2
    await waitFor(() =>
      expect(screen.getByText(/Connect a model provider/i)).toBeInTheDocument(),
    );

    const next = screen.getByTestId('wizard-next');
    expect(next).toBeDisabled();

    fireEvent.change(screen.getByTestId('provider-key-gemini'), {
      target: { value: 'sk-test' },
    });
    await waitFor(() => expect(next).not.toBeDisabled());
  });

  it('drives the full state machine to the finish call', async () => {
    const completeSpy = vi
      .spyOn(api, 'completeSetup')
      .mockResolvedValue({ success: true });

    renderWizard();

    // Step 1 → 2
    fireEvent.click(screen.getByTestId('wizard-next'));
    await waitFor(() =>
      expect(screen.getByText(/Connect a model provider/i)).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByTestId('provider-key-gemini'), {
      target: { value: 'sk-gemini' },
    });
    fireEvent.change(screen.getByTestId('provider-key-openai'), {
      target: { value: 'sk-openai' },
    });

    // Step 2 → 3
    fireEvent.click(screen.getByTestId('wizard-next'));
    await waitFor(() =>
      expect(screen.getByText(/Optional services/i)).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByTestId('tavily-key'), {
      target: { value: 'tvly-abc' },
    });

    // Step 3 → 4
    fireEvent.click(screen.getByTestId('wizard-next'));
    await waitFor(() =>
      expect(screen.getByText(/Where should we save reports/i)).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByTestId('export-folder-input'), {
      target: { value: '/home/user/research' },
    });

    // Step 4 → 5
    fireEvent.click(screen.getByTestId('wizard-next'));
    await waitFor(() =>
      expect(screen.getByText(/Email reports/i)).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId('wizard-finish'));

    await waitFor(() => expect(completeSpy).toHaveBeenCalledTimes(1));
    const payload = completeSpy.mock.calls[0][0];
    expect(payload.providers.gemini).toBe('sk-gemini');
    expect(payload.providers.openai).toBe('sk-openai');
    expect(payload.optional.tavily).toBe('tvly-abc');
    expect(payload.optional.semantic_scholar).toBe(true);
    expect(payload.export_folder).toBe('/home/user/research');
    expect(payload.email.enabled).toBe(false);
  });

  it('blocks finish when email is enabled but recipient is invalid', async () => {
    const completeSpy = vi
      .spyOn(api, 'completeSetup')
      .mockResolvedValue({ success: true });
    renderWizard();

    fireEvent.click(screen.getByTestId('wizard-next')); // 2
    await waitFor(() => screen.getByText(/Connect a model provider/i));
    fireEvent.change(screen.getByTestId('provider-key-gemini'), {
      target: { value: 'sk' },
    });
    fireEvent.click(screen.getByTestId('wizard-next')); // 3
    await waitFor(() => screen.getByText(/Optional services/i));
    fireEvent.click(screen.getByTestId('wizard-next')); // 4
    await waitFor(() => screen.getByText(/Where should we save reports/i));
    fireEvent.click(screen.getByTestId('wizard-next')); // 5
    await waitFor(() => screen.getByText(/Email reports/i));

    // Enable email but provide invalid recipient
    const toggle = screen.getByRole('switch', { name: /Email me each run/i });
    fireEvent.click(toggle);
    await waitFor(() => screen.getByTestId('email-recipient'));
    fireEvent.change(screen.getByTestId('email-recipient'), {
      target: { value: 'not-an-email' },
    });

    fireEvent.click(screen.getByTestId('wizard-finish'));
    await new Promise((r) => setTimeout(r, 50));
    expect(completeSpy).not.toHaveBeenCalled();
  });
});
