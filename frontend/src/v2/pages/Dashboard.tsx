import * as React from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { motion, AnimatePresence } from 'motion/react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { MotionButton } from '../components/MotionButton';
import { RunCard } from '../components/RunCard';
import { ThemeToggle } from '../components/ThemeToggle';
import { listContainer, listItem, springSoft } from '../lib/motion';
import { createRun, listRuns } from '../lib/api';
import type { RunSummary } from '../lib/types';

function NewRunDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onCreated: (run: RunSummary) => void;
}): React.ReactElement {
  const [description, setDescription] = React.useState('');
  const [constraints, setConstraints] = React.useState('');
  const [preferences, setPreferences] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);

  async function handleCreate(): Promise<void> {
    if (!description.trim()) {
      toast.error('Please describe a research goal.');
      return;
    }
    setSubmitting(true);
    try {
      const run = await createRun({
        goal: {
          description: description.trim(),
          constraints: constraints
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean),
          preferences: preferences
            .split('\n')
            .map((s) => s.trim())
            .filter(Boolean),
        },
      });
      onCreated(run);
      onOpenChange(false);
      setDescription('');
      setConstraints('');
      setPreferences('');
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Failed to create run';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open ? (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
              />
            </Dialog.Overlay>
            <Dialog.Content asChild>
              <motion.div
                initial={{ opacity: 0, scale: 0.97, y: 8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, y: 4 }}
                transition={springSoft}
                className="fixed left-1/2 top-1/2 z-50 w-[min(640px,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-neutral-200 bg-white p-6 shadow-2xl dark:border-neutral-800 dark:bg-neutral-900"
                data-testid="new-run-dialog"
              >
                <Dialog.Title className="text-xl font-semibold tracking-tight">
                  Start a new investigation
                </Dialog.Title>
                <Dialog.Description className="mt-1 text-sm text-neutral-500">
                  Describe what you want to explore. The system will plan iterations from there.
                </Dialog.Description>
                <div className="mt-4 space-y-3">
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium">Research goal</span>
                    <textarea
                      autoFocus
                      data-testid="goal-description"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={3}
                      placeholder="e.g. Design a bacterial scaffold to enhance soil microbiome resilience under drought."
                      className="w-full resize-none rounded-xl border border-neutral-200 bg-white p-3 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30 dark:border-neutral-700 dark:bg-neutral-900"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium">Constraints (one per line)</span>
                    <textarea
                      data-testid="goal-constraints"
                      value={constraints}
                      onChange={(e) => setConstraints(e.target.value)}
                      rows={3}
                      placeholder="e.g. Must use BSL-2 organisms only."
                      className="w-full resize-none rounded-xl border border-neutral-200 bg-white p-3 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30 dark:border-neutral-700 dark:bg-neutral-900"
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium">Preferences (one per line)</span>
                    <textarea
                      data-testid="goal-preferences"
                      value={preferences}
                      onChange={(e) => setPreferences(e.target.value)}
                      rows={3}
                      placeholder="e.g. Prefer mechanism-of-action level explanations."
                      className="w-full resize-none rounded-xl border border-neutral-200 bg-white p-3 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/30 dark:border-neutral-700 dark:bg-neutral-900"
                    />
                  </label>
                </div>
                <div className="mt-6 flex items-center justify-end gap-2">
                  <MotionButton variant="ghost" onClick={() => onOpenChange(false)}>
                    Cancel
                  </MotionButton>
                  <MotionButton
                    onClick={handleCreate}
                    isLoading={submitting}
                    data-testid="goal-submit"
                  >
                    Start investigation
                  </MotionButton>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        ) : null}
      </AnimatePresence>
    </Dialog.Root>
  );
}

export default function Dashboard(): React.ReactElement {
  const navigate = useNavigate();
  const [runs, setRuns] = React.useState<RunSummary[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [showNew, setShowNew] = React.useState(false);

  const fetchRuns = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await listRuns();
      setRuns(data);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void fetchRuns();
  }, [fetchRuns]);

  const activeRuns = runs.filter((r) => r.status === 'running' || r.status === 'pending');
  const recentRuns = runs.filter((r) => r.status === 'completed' || r.status === 'failed').slice(0, 10);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-neutral-200 bg-white/70 backdrop-blur-md dark:border-neutral-800 dark:bg-neutral-950/70">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2">
            <span
              className="inline-block h-6 w-6 rounded-md bg-gradient-to-br from-sky-400 to-violet-500"
              aria-hidden
            />
            <span className="font-bold tracking-tightest">AGF · Co-Scientist</span>
          </Link>
          <div className="flex items-center gap-3">
            <kbd className="mono hidden rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] text-neutral-500 md:inline-block dark:border-neutral-700 dark:bg-neutral-900">
              ⌘K
            </kbd>
            <Link
              to="/settings"
              className="text-sm font-medium text-neutral-700 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-neutral-50"
            >
              Settings
            </Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pt-12 pb-20">
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={springSoft}
          className="mb-12 flex flex-col items-start gap-6 md:mb-16"
        >
          <h1 className="text-5xl font-bold leading-tight tracking-tightest text-neutral-900 dark:text-neutral-50 md:text-6xl">
            Start a new <br />
            investigation
          </h1>
          <p className="max-w-xl text-base leading-relaxed text-neutral-600 dark:text-neutral-300">
            Give the co-scientist a research goal. Eight specialised agents will explore,
            debate, and converge on the most promising directions.
          </p>
          <div className="flex items-center gap-3">
            <MotionButton onClick={() => setShowNew(true)} size="lg" data-testid="start-investigation">
              Start investigation →
            </MotionButton>
            <MotionButton variant="ghost" onClick={() => navigate('/settings')}>
              Configure models
            </MotionButton>
          </div>
        </motion.section>

        {activeRuns.length > 0 ? (
          <section className="mb-12" data-testid="active-runs-section">
            <h2 className="mb-4 text-lg font-semibold tracking-tight">Active runs</h2>
            <motion.div
              variants={listContainer}
              initial="hidden"
              animate="show"
              className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
            >
              {activeRuns.map((r) => (
                <RunCard key={r.id} run={r} />
              ))}
            </motion.div>
          </section>
        ) : null}

        <section data-testid="recent-runs-section">
          <h2 className="mb-4 text-lg font-semibold tracking-tight">Recent runs</h2>
          {loading ? (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <motion.div
                  key={i}
                  variants={listItem}
                  initial="hidden"
                  animate="show"
                  className="card h-40 animate-pulse"
                />
              ))}
            </div>
          ) : recentRuns.length === 0 ? (
            <div className="card flex flex-col items-center justify-center gap-3 p-12 text-center">
              <p className="text-sm text-neutral-500">No runs yet — start your first investigation.</p>
              <MotionButton onClick={() => setShowNew(true)} variant="secondary">
                Start now
              </MotionButton>
            </div>
          ) : (
            <motion.div
              variants={listContainer}
              initial="hidden"
              animate="show"
              className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
            >
              {recentRuns.map((r) => (
                <RunCard key={r.id} run={r} />
              ))}
            </motion.div>
          )}
        </section>
      </main>

      <NewRunDialog
        open={showNew}
        onOpenChange={setShowNew}
        onCreated={(run) => {
          toast.success('Investigation started');
          navigate(`/run/${run.id}`);
        }}
      />
    </div>
  );
}
