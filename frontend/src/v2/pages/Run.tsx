import * as React from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';

import { ProgressStepper } from '../components/ProgressStepper';
import { HypothesisCard } from '../components/HypothesisCard';
import { TournamentBracket } from '../components/TournamentBracket';
import { MotionButton } from '../components/MotionButton';
import { ThemeToggle } from '../components/ThemeToggle';
import { usePolling } from '../hooks/usePolling';
import { getRun } from '../lib/api';
import type { Hypothesis, LogEntry, RunDetail } from '../lib/types';
import { listContainer, listItem, springSoft } from '../lib/motion';

function sortedHypotheses(list: Hypothesis[] | undefined): Hypothesis[] {
  if (!list) return [];
  return [...list].sort((a, b) => b.elo_rating - a.elo_rating);
}

function LogStrip({ entries }: { entries?: LogEntry[] }): React.ReactElement {
  const items = (entries ?? []).slice(-12);
  return (
    <div className="mono flex h-32 flex-col gap-0.5 overflow-y-auto rounded-xl border border-neutral-200 bg-neutral-50 p-3 text-[11px] leading-relaxed text-neutral-700 dark:border-neutral-800 dark:bg-neutral-900 dark:text-neutral-300">
      <AnimatePresence initial={false}>
        {items.map((e, idx) => (
          <motion.div
            key={`${e.ts}-${idx}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={springSoft}
            className="flex gap-3"
          >
            <span className="text-neutral-400">{new Date(e.ts).toLocaleTimeString()}</span>
            <span
              className={
                e.level === 'error'
                  ? 'text-red-500'
                  : e.level === 'warn'
                    ? 'text-amber-500'
                    : ''
              }
            >
              {e.message}
            </span>
          </motion.div>
        ))}
        {items.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-neutral-400"
          >
            Waiting for events…
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export default function Run(): React.ReactElement {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const fetcher = React.useCallback(async (): Promise<RunDetail> => {
    if (!id) throw new Error('Missing run id');
    return getRun(id);
  }, [id]);

  const { data: run, error } = usePolling<RunDetail>(fetcher, {
    intervalMs: 2000,
    enabled: Boolean(id),
  });

  if (!id) {
    return <div className="p-10">Missing run id.</div>;
  }

  const hypotheses = sortedHypotheses(run?.hypotheses);
  const finished = run?.status === 'completed' || run?.status === 'failed';

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-neutral-200 bg-white/70 backdrop-blur-md dark:border-neutral-800 dark:bg-neutral-950/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="text-sm font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-50"
            >
              ← Dashboard
            </Link>
            <span className="mono text-xs text-neutral-400">/</span>
            <span className="mono text-xs text-neutral-500">run · {id.slice(0, 8)}</span>
          </div>
          <div className="flex items-center gap-2">
            {finished ? (
              <MotionButton size="sm" onClick={() => navigate(`/run/${id}/results`)}>
                View results →
              </MotionButton>
            ) : null}
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={springSoft}
          className="mb-8"
        >
          <h1 className="line-clamp-2 text-3xl font-bold tracking-tightest md:text-4xl">
            {run?.goal ?? 'Loading…'}
          </h1>
          <p className="mt-2 text-sm text-neutral-500">
            Status: <span className="mono">{run?.status ?? '—'}</span>
            {typeof run?.iteration === 'number' ? (
              <>
                {' · '}iteration{' '}
                <span className="mono">
                  {run.iteration} / {run.max_iterations ?? '?'}
                </span>
              </>
            ) : null}
          </p>
          {error ? (
            <p className="mt-2 text-xs text-red-500">{error.message}</p>
          ) : null}
        </motion.section>

        <div className="mb-8">
          <ProgressStepper
            current={run?.current_phase}
            iteration={run?.iteration}
            maxIterations={run?.max_iterations}
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <section className="lg:col-span-2">
            <h2 className="mb-3 text-lg font-semibold tracking-tight">Hypotheses</h2>
            <motion.div
              variants={listContainer}
              initial="hidden"
              animate="show"
              layout
              className="space-y-3"
            >
              <AnimatePresence>
                {hypotheses.map((h, i) => (
                  <motion.div key={h.id} layout variants={listItem} transition={springSoft}>
                    <HypothesisCard hypothesis={h} index={i} />
                  </motion.div>
                ))}
              </AnimatePresence>
              {hypotheses.length === 0 ? (
                <motion.div
                  variants={listItem}
                  className="card flex h-40 items-center justify-center text-sm text-neutral-500"
                >
                  Generating first hypotheses…
                </motion.div>
              ) : null}
            </motion.div>
          </section>

          <aside className="space-y-6">
            <section>
              <h2 className="mb-3 text-lg font-semibold tracking-tight">Tournament</h2>
              <TournamentBracket data={run?.tournament} />
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold tracking-tight">Live log</h2>
              <LogStrip entries={run?.logs} />
            </section>
          </aside>
        </div>
      </main>
    </div>
  );
}
