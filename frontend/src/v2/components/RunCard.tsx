import * as React from 'react';
import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { cn } from '../lib/cn';
import { listItem, springSoft } from '../lib/motion';
import type { RunSummary } from '../lib/types';

const STATUS_LABEL: Record<RunSummary['status'], string> = {
  pending: 'Queued',
  running: 'Running',
  completed: 'Done',
  failed: 'Failed',
};

const STATUS_COLOR: Record<RunSummary['status'], string> = {
  pending: 'bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300',
  running: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
  completed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
  failed: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
};

export interface RunCardProps {
  run: RunSummary;
  destination?: string;
}

export function RunCard({ run, destination }: RunCardProps): React.ReactElement {
  const to = destination ?? `/run/${run.id}`;
  return (
    <motion.div
      layoutId={`run-${run.id}`}
      variants={listItem}
      whileHover={{ y: -2 }}
      transition={springSoft}
      className="card"
      data-testid={`run-card-${run.id}`}
    >
      <Link to={to} className="block p-5">
        <div className="flex items-center justify-between gap-3">
          <span
            className={cn(
              'mono rounded-full px-2 py-0.5 text-[10px] uppercase tracking-widest',
              STATUS_COLOR[run.status],
            )}
          >
            {STATUS_LABEL[run.status]}
          </span>
          <span className="mono text-[11px] text-neutral-500">
            {new Date(run.created_at).toLocaleDateString()}
          </span>
        </div>
        <h3 className="mt-3 line-clamp-2 text-base font-semibold tracking-tight text-neutral-900 dark:text-neutral-50">
          {run.goal}
        </h3>
        <div className="mt-4 flex items-center justify-between text-xs text-neutral-500">
          <span>{run.hypotheses_count ?? 0} hypotheses</span>
          {typeof run.cost_usd === 'number' ? (
            <span className="mono">${run.cost_usd.toFixed(2)}</span>
          ) : null}
        </div>
      </Link>
    </motion.div>
  );
}
