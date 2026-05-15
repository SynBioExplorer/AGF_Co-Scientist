import * as React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { MotionButton } from './MotionButton';
import { MotionInput } from './MotionInput';
import type { ProviderMeta } from '../lib/types';
import { validateApiKey } from '../lib/api';
import { springSoft } from '../lib/motion';
import { cn } from '../lib/cn';

export interface ProviderInputProps {
  provider: ProviderMeta;
  value: string;
  onChange: (next: string) => void;
  onValidated?: (valid: boolean, availableModels?: string[]) => void;
  initiallyMasked?: boolean;
}

type Status = 'idle' | 'testing' | 'ok' | 'error';

export function ProviderInput({
  provider,
  value,
  onChange,
  onValidated,
  initiallyMasked,
}: ProviderInputProps): React.ReactElement {
  const [status, setStatus] = React.useState<Status>('idle');
  const [error, setError] = React.useState<string | null>(null);
  const [revealed, setRevealed] = React.useState<boolean>(!initiallyMasked);

  async function handleTest(): Promise<void> {
    if (!value) {
      setStatus('error');
      setError('Please enter an API key');
      onValidated?.(false);
      return;
    }
    setStatus('testing');
    setError(null);
    const result = await validateApiKey(provider.id, value);
    if (result.valid) {
      setStatus('ok');
      onValidated?.(true, result.available_models);
    } else {
      setStatus('error');
      setError(result.error ?? 'Validation failed');
      onValidated?.(false);
    }
  }

  return (
    <motion.div
      layout
      transition={springSoft}
      className="rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-neutral-800 dark:bg-neutral-900"
      data-testid={`provider-row-${provider.id}`}
    >
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span
            className="inline-block h-3 w-3 rounded-full"
            style={{ background: provider.brandColor }}
            aria-hidden
          />
          <h3 className="text-base font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
            {provider.label}
          </h3>
        </div>
        <a
          href={provider.helpUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-medium text-sky-600 hover:text-sky-700 dark:text-sky-400 dark:hover:text-sky-300"
        >
          How to get a key →
        </a>
      </div>
      <div className="mt-3 flex items-stretch gap-2">
        <div className="flex-1">
          <MotionInput
            type={revealed ? 'text' : 'password'}
            placeholder={`Paste your ${provider.label} API key`}
            value={value}
            monoValue
            onChange={(e) => {
              onChange(e.target.value);
              setStatus('idle');
            }}
            aria-label={`${provider.label} API key`}
            data-testid={`provider-key-${provider.id}`}
            rightSlot={
              <button
                type="button"
                className="text-xs text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200"
                onClick={() => setRevealed((r) => !r)}
              >
                {revealed ? 'Hide' : 'Show'}
              </button>
            }
          />
        </div>
        <div className="flex shrink-0 items-center">
          <MotionButton
            type="button"
            onClick={handleTest}
            variant="secondary"
            size="md"
            isLoading={status === 'testing'}
            data-testid={`provider-test-${provider.id}`}
          >
            Test
          </MotionButton>
        </div>
      </div>

      <AnimatePresence>
        {status === 'ok' ? (
          <motion.div
            key="ok"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={springSoft}
            className={cn('mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-emerald-600 dark:text-emerald-400')}
          >
            <span aria-hidden>✓</span> Validated successfully
          </motion.div>
        ) : null}
        {status === 'error' && error ? (
          <motion.div
            key="err"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={springSoft}
            className="mt-2 text-xs text-red-500"
          >
            {error}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
}
