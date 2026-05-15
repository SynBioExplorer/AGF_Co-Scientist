import * as React from 'react';
import { motion } from 'motion/react';
import { cn } from '../lib/cn';
import { springSoft } from '../lib/motion';

const PHASES = ['generation', 'reflection', 'ranking', 'evolution', 'meta_review'] as const;
type Phase = (typeof PHASES)[number];

const LABELS: Record<Phase, string> = {
  generation: 'Generation',
  reflection: 'Reflection',
  ranking: 'Ranking',
  evolution: 'Evolution',
  meta_review: 'Meta-review',
};

export interface ProgressStepperProps {
  current?: Phase | 'idle';
  iteration?: number;
  maxIterations?: number;
}

export function ProgressStepper({
  current,
  iteration,
  maxIterations,
}: ProgressStepperProps): React.ReactElement {
  const activeIdx = current && current !== 'idle' ? PHASES.indexOf(current) : -1;
  return (
    <div className="card p-5">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
          Current iteration
        </h2>
        <span className="mono text-xs text-neutral-500">
          {typeof iteration === 'number' && typeof maxIterations === 'number'
            ? `${iteration} / ${maxIterations}`
            : '—'}
        </span>
      </div>
      <ol className="flex items-center gap-2 overflow-x-auto" data-testid="progress-stepper">
        {PHASES.map((phase, idx) => {
          const isActive = idx === activeIdx;
          const isDone = idx < activeIdx;
          return (
            <React.Fragment key={phase}>
              <motion.li
                layout
                transition={springSoft}
                className={cn(
                  'flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs',
                  isActive &&
                    'border-sky-500 bg-sky-500/10 text-sky-900 dark:text-sky-200',
                  isDone &&
                    'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
                  !isActive && !isDone &&
                    'border-neutral-200 text-neutral-500 dark:border-neutral-700',
                )}
              >
                <span className="mono text-[10px]">{idx + 1}</span>
                <span>{LABELS[phase]}</span>
                {isActive ? (
                  <span
                    className="inline-block h-2 w-2 animate-pulse rounded-full bg-sky-500"
                    aria-hidden
                  />
                ) : null}
              </motion.li>
              {idx < PHASES.length - 1 ? (
                <span className="h-px w-3 bg-neutral-200 dark:bg-neutral-700" aria-hidden />
              ) : null}
            </React.Fragment>
          );
        })}
      </ol>
    </div>
  );
}
