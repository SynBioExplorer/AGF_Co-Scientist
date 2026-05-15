import * as React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { WizardCard } from '../components/WizardCard';
import { MotionButton } from '../components/MotionButton';
import { MotionInput } from '../components/MotionInput';
import { MotionToggle } from '../components/MotionToggle';
import { ProviderInput } from '../components/ProviderInput';
import { completeSetup } from '../lib/api';
import { PROVIDERS } from '../lib/types';
import type { ProviderId, SetupCompletePayload } from '../lib/types';
import { springSoft } from '../lib/motion';

const TOTAL_STEPS = 5;

const STEP_HUES: Array<[number, number]> = [
  [200, 270], // Welcome
  [220, 290], // Providers
  [180, 220], // Optional
  [270, 320], // Export
  [200, 160], // Email
];

interface ProviderState {
  key: string;
  validated: boolean;
}

const DEFAULT_EXPORT = '~/Documents/AGF Co-Scientist';

export default function Onboarding(): React.ReactElement {
  const navigate = useNavigate();
  const [step, setStep] = React.useState<number>(1);
  const [direction, setDirection] = React.useState<1 | -1>(1);
  const [providers, setProviders] = React.useState<Record<ProviderId, ProviderState>>({
    gemini: { key: '', validated: false },
    openai: { key: '', validated: false },
    deepseek: { key: '', validated: false },
    anthropic: { key: '', validated: false },
  });
  const [tavilyKey, setTavilyKey] = React.useState('');
  const [semanticScholarEnabled, setSemanticScholarEnabled] = React.useState(true);
  const [pubmedKey, setPubmedKey] = React.useState('');
  const [exportFolder, setExportFolder] = React.useState(DEFAULT_EXPORT);
  const [emailEnabled, setEmailEnabled] = React.useState(false);
  const [emailRecipient, setEmailRecipient] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);

  // Drive conic gradient hues from step.
  React.useEffect(() => {
    const [a, b] = STEP_HUES[step - 1] ?? STEP_HUES[0];
    document.documentElement.style.setProperty('--grad-hue-a', String(a));
    document.documentElement.style.setProperty('--grad-hue-b', String(b));
  }, [step]);

  const atLeastOneProvider = React.useMemo(
    () => Object.values(providers).some((p) => p.key.trim().length > 0),
    [providers],
  );

  function next(): void {
    setDirection(1);
    setStep((s) => Math.min(TOTAL_STEPS, s + 1));
  }
  function back(): void {
    setDirection(-1);
    setStep((s) => Math.max(1, s - 1));
  }

  async function handleFolderPick(): Promise<void> {
    if (window.electronAPI?.openFolder) {
      const chosen = await window.electronAPI.openFolder();
      if (chosen) setExportFolder(chosen);
    } else {
      toast.message('Folder picker requires the desktop app — enter the path manually.');
    }
  }

  async function handleFinish(): Promise<void> {
    if (emailEnabled && !emailRecipient.includes('@')) {
      toast.error('Please enter a valid email address.');
      return;
    }
    const providersPayload: Partial<Record<ProviderId, string>> = {};
    for (const id of Object.keys(providers) as ProviderId[]) {
      const v = providers[id].key.trim();
      if (v) providersPayload[id] = v;
    }
    const payload: SetupCompletePayload = {
      providers: providersPayload,
      optional: {
        tavily: tavilyKey.trim() || undefined,
        semantic_scholar: semanticScholarEnabled,
        pubmed: pubmedKey.trim() || undefined,
      },
      export_folder: exportFolder.trim() || DEFAULT_EXPORT,
      email: {
        enabled: emailEnabled,
        recipient: emailEnabled ? emailRecipient.trim() : undefined,
      },
    };
    setSubmitting(true);
    try {
      const res = await completeSetup(payload);
      if (res.success) {
        toast.success('Setup complete!');
        navigate('/');
      } else {
        toast.error('Setup failed — please retry.');
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Setup failed';
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  }

  const stepVariants = {
    enter: (dir: 1 | -1) => ({ x: dir * 40, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (dir: 1 | -1) => ({ x: dir * -40, opacity: 0 }),
  } as const;

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="onboarding-bg" aria-hidden />
      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="flex items-center justify-between px-6 py-6 md:px-10">
          <span className="mono text-xs uppercase tracking-widest text-neutral-500">
            AGF · Co-Scientist
          </span>
          <span className="mono text-xs text-neutral-500" data-testid="step-indicator">
            Step {step} of {TOTAL_STEPS}
          </span>
        </header>

        <main className="flex flex-1 items-center justify-center px-4 py-10">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={step}
              variants={stepVariants}
              custom={direction}
              initial="enter"
              animate="center"
              exit="exit"
              transition={springSoft}
              className="w-full"
            >
              {step === 1 ? (
                <WizardCard
                  title="Welcome to AGF Co-Scientist"
                  subtitle="A multi-agent research collaborator that generates, debates, and evolves hypotheses with you."
                  footer={
                    <>
                      <span />
                      <MotionButton onClick={next} size="lg" data-testid="wizard-next">
                        Get started →
                      </MotionButton>
                    </>
                  }
                >
                  <p className="text-base leading-relaxed text-neutral-700 dark:text-neutral-300">
                    Eight specialised agents collaborate to explore a research goal you provide.
                    They generate ideas, critique each other in tournaments, and converge on the
                    most promising directions.
                  </p>
                  <p className="text-base leading-relaxed text-neutral-700 dark:text-neutral-300">
                    Setup takes about a minute. Your API keys never leave your computer except to
                    talk directly to each provider.
                  </p>
                </WizardCard>
              ) : null}

              {step === 2 ? (
                <WizardCard
                  title="Connect a model provider"
                  subtitle="You need at least one. Add as many as you like — agents can be routed per provider later."
                  footer={
                    <>
                      <MotionButton onClick={back} variant="ghost">
                        ← Back
                      </MotionButton>
                      <MotionButton
                        onClick={next}
                        size="lg"
                        disabled={!atLeastOneProvider}
                        data-testid="wizard-next"
                      >
                        Continue →
                      </MotionButton>
                    </>
                  }
                >
                  <div className="space-y-3">
                    {PROVIDERS.map((p) => (
                      <ProviderInput
                        key={p.id}
                        provider={p}
                        value={providers[p.id].key}
                        onChange={(v) =>
                          setProviders((prev) => ({
                            ...prev,
                            [p.id]: { ...prev[p.id], key: v, validated: false },
                          }))
                        }
                        onValidated={(valid) =>
                          setProviders((prev) => ({
                            ...prev,
                            [p.id]: { ...prev[p.id], validated: valid },
                          }))
                        }
                      />
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-neutral-500 dark:text-neutral-400">
                    Your keys are stored only on this computer (in your OS keychain). They are
                    never sent anywhere except directly to the provider.
                  </p>
                </WizardCard>
              ) : null}

              {step === 3 ? (
                <WizardCard
                  title="Optional services"
                  subtitle="These power literature search and live web grounding. Skip anything you don't need."
                  footer={
                    <>
                      <MotionButton onClick={back} variant="ghost">
                        ← Back
                      </MotionButton>
                      <MotionButton onClick={next} size="lg" data-testid="wizard-next">
                        Continue →
                      </MotionButton>
                    </>
                  }
                >
                  <div className="space-y-3">
                    <div className="rounded-2xl border border-neutral-200 p-4 dark:border-neutral-800">
                      <div className="mb-2 flex items-center justify-between">
                        <h3 className="text-sm font-semibold tracking-tight">Tavily</h3>
                        <span className="mono text-[10px] uppercase tracking-widest text-neutral-500">
                          Optional
                        </span>
                      </div>
                      <p className="mb-3 text-xs text-neutral-500">
                        Used for live web search during research expansion.
                      </p>
                      <MotionInput
                        type="password"
                        monoValue
                        placeholder="tvly-…"
                        value={tavilyKey}
                        onChange={(e) => setTavilyKey(e.target.value)}
                        aria-label="Tavily API key"
                        data-testid="tavily-key"
                      />
                    </div>

                    <div className="rounded-2xl border border-neutral-200 p-4 dark:border-neutral-800">
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-semibold tracking-tight">Semantic Scholar</h3>
                        <span className="mono text-[10px] uppercase tracking-widest text-emerald-600 dark:text-emerald-400">
                          Free · Recommended
                        </span>
                      </div>
                      <MotionToggle
                        checked={semanticScholarEnabled}
                        onCheckedChange={setSemanticScholarEnabled}
                        label="Enable Semantic Scholar"
                        description="No API key required."
                      />
                    </div>

                    <div className="rounded-2xl border border-neutral-200 p-4 dark:border-neutral-800">
                      <div className="mb-2 flex items-center justify-between">
                        <h3 className="text-sm font-semibold tracking-tight">NCBI PubMed</h3>
                        <span className="mono text-[10px] uppercase tracking-widest text-neutral-500">
                          Optional
                        </span>
                      </div>
                      <p className="mb-3 text-xs text-neutral-500">
                        Provide an API key for higher rate limits.
                      </p>
                      <MotionInput
                        type="password"
                        monoValue
                        placeholder="NCBI API key"
                        value={pubmedKey}
                        onChange={(e) => setPubmedKey(e.target.value)}
                        aria-label="PubMed API key"
                        data-testid="pubmed-key"
                      />
                    </div>
                  </div>
                </WizardCard>
              ) : null}

              {step === 4 ? (
                <WizardCard
                  title="Where should we save reports?"
                  subtitle="Every run produces an interactive HTML report and a JSON dump."
                  footer={
                    <>
                      <MotionButton onClick={back} variant="ghost">
                        ← Back
                      </MotionButton>
                      <MotionButton
                        onClick={next}
                        size="lg"
                        disabled={!exportFolder.trim()}
                        data-testid="wizard-next"
                      >
                        Continue →
                      </MotionButton>
                    </>
                  }
                >
                  <div className="flex flex-col gap-3">
                    <MotionButton
                      onClick={handleFolderPick}
                      variant="secondary"
                      size="lg"
                      data-testid="choose-folder"
                    >
                      Choose folder
                    </MotionButton>
                    <MotionInput
                      monoValue
                      placeholder={DEFAULT_EXPORT}
                      value={exportFolder}
                      onChange={(e) => setExportFolder(e.target.value)}
                      aria-label="Export folder path"
                      data-testid="export-folder-input"
                      hint="Or paste a path here (useful for browser-only environments)."
                    />
                  </div>
                </WizardCard>
              ) : null}

              {step === 5 ? (
                <WizardCard
                  title="Email reports?"
                  subtitle="Optional: get a notification with the report attached after every finished run."
                  footer={
                    <>
                      <MotionButton onClick={back} variant="ghost">
                        ← Back
                      </MotionButton>
                      <MotionButton
                        onClick={handleFinish}
                        size="lg"
                        isLoading={submitting}
                        data-testid="wizard-finish"
                      >
                        Finish setup
                      </MotionButton>
                    </>
                  }
                >
                  <MotionToggle
                    checked={emailEnabled}
                    onCheckedChange={setEmailEnabled}
                    label="Email me each run's report when it finishes"
                    description="Reports open in your default mail client — no email credentials needed."
                  />
                  <AnimatePresence>
                    {emailEnabled ? (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={springSoft}
                      >
                        <MotionInput
                          type="email"
                          placeholder="you@example.com"
                          value={emailRecipient}
                          onChange={(e) => setEmailRecipient(e.target.value)}
                          aria-label="Recipient email"
                          data-testid="email-recipient"
                        />
                      </motion.div>
                    ) : null}
                  </AnimatePresence>
                </WizardCard>
              ) : null}
            </motion.div>
          </AnimatePresence>
        </main>

        <footer className="px-6 py-4 text-center md:px-10">
          <ol className="mx-auto flex max-w-md items-center justify-center gap-2" aria-label="Progress">
            {Array.from({ length: TOTAL_STEPS }).map((_, i) => (
              <motion.li
                key={i}
                layout
                transition={springSoft}
                className={`h-1.5 rounded-full ${
                  i + 1 === step
                    ? 'w-10 bg-sky-500'
                    : i + 1 < step
                      ? 'w-6 bg-sky-300'
                      : 'w-6 bg-neutral-200 dark:bg-neutral-700'
                }`}
              />
            ))}
          </ol>
        </footer>
      </div>
    </div>
  );
}
