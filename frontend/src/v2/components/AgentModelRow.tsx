import * as React from 'react';
import * as Slider from '@radix-ui/react-slider';
import { motion } from 'motion/react';
import type { AgentModelConfig, AgentType, ProviderId } from '../lib/types';
import { PROVIDERS } from '../lib/types';
import { getAvailableModels } from '../lib/api';
import { cn } from '../lib/cn';
import { springSoft } from '../lib/motion';

const AGENT_LABELS: Record<AgentType, string> = {
  generation: 'Generation',
  reflection: 'Reflection',
  ranking: 'Ranking',
  evolution: 'Evolution',
  proximity: 'Proximity',
  meta_review: 'Meta-review',
  supervisor: 'Supervisor',
  safety: 'Safety',
};

export interface AgentModelRowProps {
  agent: AgentType;
  value: AgentModelConfig | null;
  defaultLabel: string;
  onChange: (next: AgentModelConfig | null) => void;
}

export function AgentModelRow({
  agent,
  value,
  defaultLabel,
  onChange,
}: AgentModelRowProps): React.ReactElement {
  const cfg: AgentModelConfig =
    value ?? { provider: 'default', model: '', temperature: 0.7 };
  const [models, setModels] = React.useState<string[]>([]);
  const [loadingModels, setLoadingModels] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      if (cfg.provider === 'default') {
        setModels([]);
        return;
      }
      setLoadingModels(true);
      try {
        const result = await getAvailableModels(cfg.provider as ProviderId);
        if (!cancelled) setModels(result.models);
      } finally {
        if (!cancelled) setLoadingModels(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [cfg.provider]);

  function update(patch: Partial<AgentModelConfig>): void {
    onChange({ ...cfg, ...patch });
  }

  return (
    <motion.div
      layout
      transition={springSoft}
      className="grid grid-cols-1 items-center gap-3 rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900 md:grid-cols-12"
      data-testid={`agent-row-${agent}`}
    >
      <div className="md:col-span-3">
        <h4 className="text-sm font-semibold text-neutral-900 dark:text-neutral-50">
          {AGENT_LABELS[agent]}
        </h4>
        <p className="mono text-[10px] uppercase tracking-widest text-neutral-500">
          {agent}
        </p>
      </div>

      <div className="md:col-span-3">
        <label className="sr-only" htmlFor={`provider-${agent}`}>
          Provider
        </label>
        <select
          id={`provider-${agent}`}
          aria-label={`Provider for ${AGENT_LABELS[agent]}`}
          data-testid={`provider-select-${agent}`}
          value={cfg.provider}
          onChange={(e) =>
            update({ provider: e.target.value as AgentModelConfig['provider'], model: '' })
          }
          className={cn(
            'w-full rounded-lg border border-neutral-200 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900',
          )}
        >
          <option value="default">Use default ({defaultLabel})</option>
          {PROVIDERS.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      <div className="md:col-span-3">
        <label className="sr-only" htmlFor={`model-${agent}`}>
          Model
        </label>
        <select
          id={`model-${agent}`}
          aria-label={`Model for ${AGENT_LABELS[agent]}`}
          data-testid={`model-select-${agent}`}
          disabled={cfg.provider === 'default'}
          value={cfg.model}
          onChange={(e) => update({ model: e.target.value })}
          className={cn(
            'w-full rounded-lg border border-neutral-200 bg-white px-2 py-1.5 text-sm disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-900',
          )}
        >
          <option value="">
            {loadingModels ? 'Loading…' : cfg.provider === 'default' ? '—' : 'Select a model'}
          </option>
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      <div className="md:col-span-2">
        <Slider.Root
          className="relative flex h-5 w-full touch-none select-none items-center"
          min={0}
          max={2}
          step={0.1}
          value={[cfg.temperature]}
          onValueChange={(v) => update({ temperature: v[0] ?? 0 })}
          aria-label={`Temperature for ${AGENT_LABELS[agent]}`}
        >
          <Slider.Track className="relative h-1.5 grow rounded-full bg-neutral-200 dark:bg-neutral-700">
            <Slider.Range className="absolute h-full rounded-full bg-sky-500" />
          </Slider.Track>
          <Slider.Thumb
            className="block h-4 w-4 rounded-full bg-white shadow ring-1 ring-neutral-300 transition-colors hover:bg-sky-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            aria-label="Temperature"
            data-testid={`temperature-thumb-${agent}`}
          />
        </Slider.Root>
        <p className="mono mt-1 text-[10px] text-neutral-500">
          temp {cfg.temperature.toFixed(1)}
        </p>
      </div>

      <div className="md:col-span-1 text-right">
        <button
          type="button"
          onClick={() => onChange(null)}
          className="text-xs text-sky-600 hover:text-sky-700 dark:text-sky-400"
          data-testid={`reset-${agent}`}
        >
          Reset
        </button>
      </div>
    </motion.div>
  );
}
