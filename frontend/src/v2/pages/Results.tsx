import * as React from 'react';
import { Link, useParams } from 'react-router-dom';
import { motion } from 'motion/react';
import { toast } from 'sonner';

import { HypothesisCard } from '../components/HypothesisCard';
import { MotionButton } from '../components/MotionButton';
import { ThemeToggle } from '../components/ThemeToggle';
import { exportRunEmail, getRun } from '../lib/api';
import type { Hypothesis, RunDetail } from '../lib/types';
import { listContainer, listItem, springSoft } from '../lib/motion';

function topN(hypotheses: Hypothesis[] | undefined, n: number): Hypothesis[] {
  return [...(hypotheses ?? [])]
    .sort((a, b) => b.elo_rating - a.elo_rating)
    .slice(0, n);
}

export default function Results(): React.ReactElement {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = React.useState<RunDetail | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!id) return;
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const r = await getRun(id as string);
        if (!cancelled) setRun(r);
      } catch (e) {
        if (!cancelled && e instanceof Error) toast.error(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const top3 = topN(run?.hypotheses, 3);
  const remaining = topN(run?.hypotheses, 999).slice(3);

  async function openReport(): Promise<void> {
    const path = run?.html_report_path;
    if (!path) {
      toast.error('No report path available yet.');
      return;
    }
    const url = `file://${path}`;
    if (window.electronAPI?.openExternal) {
      await window.electronAPI.openExternal(url);
    } else {
      window.open(url, '_blank');
    }
  }

  async function showInFolder(): Promise<void> {
    const path = run?.html_report_path;
    if (!path) {
      toast.error('No file path available yet.');
      return;
    }
    if (window.electronAPI?.showInFolder) {
      await window.electronAPI.showInFolder(path);
    } else {
      toast.message('Folder reveal requires the desktop app.');
    }
  }

  async function sendEmail(): Promise<void> {
    if (!id) return;
    try {
      const res = await exportRunEmail(id);
      if (window.electronAPI?.openMailto) {
        await window.electronAPI.openMailto(res.mailto_url);
      } else {
        window.location.href = res.mailto_url;
      }
      toast.success('Opening your email client…');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to prepare email';
      toast.error(message);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-neutral-200 bg-white/70 backdrop-blur-md dark:border-neutral-800 dark:bg-neutral-950/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Link
              to={`/run/${id}`}
              className="text-sm font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-50"
            >
              ← Back to run
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-12">
        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={springSoft}
          className="mb-12"
        >
          <p className="mono mb-3 text-xs uppercase tracking-widest text-neutral-500">
            Final report
          </p>
          <h1 className="text-4xl font-bold tracking-tightest md:text-5xl">
            {loading ? 'Loading…' : run?.goal}
          </h1>
        </motion.section>

        <section className="mb-10">
          <h2 className="mb-4 text-lg font-semibold tracking-tight">Top hypotheses</h2>
          <motion.div
            variants={listContainer}
            initial="hidden"
            animate="show"
            className="grid grid-cols-1 gap-4 md:grid-cols-3"
          >
            {top3.map((h, i) => (
              <motion.div key={h.id} variants={listItem}>
                <HypothesisCard hypothesis={h} index={i} highlighted={i === 0} />
              </motion.div>
            ))}
          </motion.div>
        </section>

        {remaining.length > 0 ? (
          <section className="mb-10">
            <h2 className="mb-4 text-lg font-semibold tracking-tight">All hypotheses</h2>
            <motion.div variants={listContainer} initial="hidden" animate="show" className="space-y-3">
              {remaining.map((h, i) => (
                <motion.div key={h.id} variants={listItem}>
                  <HypothesisCard hypothesis={h} index={i + 3} />
                </motion.div>
              ))}
            </motion.div>
          </section>
        ) : null}

        <section className="mb-10 grid grid-cols-1 gap-4 md:grid-cols-3">
          {[
            ['Duration', run?.stats?.duration_seconds ? `${Math.round((run.stats.duration_seconds ?? 0) / 60)} min` : '—'],
            ['Hypotheses', String(run?.stats?.hypotheses_generated ?? run?.hypotheses?.length ?? 0)],
            ['Tournament matches', String(run?.stats?.matches_played ?? 0)],
            ['Cost (USD)', typeof run?.stats?.cost_usd === 'number' ? `$${run.stats.cost_usd.toFixed(2)}` : '—'],
            ['Cost (AUD)', typeof run?.stats?.cost_aud === 'number' ? `A$${run.stats.cost_aud.toFixed(2)}` : '—'],
            ['Finished', run?.finished_at ? new Date(run.finished_at).toLocaleString() : '—'],
          ].map(([label, value]) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={springSoft}
              className="card p-4"
            >
              <p className="mono text-[10px] uppercase tracking-widest text-neutral-500">{label}</p>
              <p className="mt-1 text-xl font-semibold">{value}</p>
            </motion.div>
          ))}
        </section>

        <section className="flex flex-wrap items-center gap-3">
          <MotionButton onClick={openReport} data-testid="open-report">
            Open HTML report
          </MotionButton>
          <MotionButton onClick={showInFolder} variant="secondary" data-testid="show-in-folder">
            Show in folder
          </MotionButton>
          <MotionButton onClick={sendEmail} variant="secondary" data-testid="send-email">
            Send via email
          </MotionButton>
        </section>
      </main>
    </div>
  );
}
