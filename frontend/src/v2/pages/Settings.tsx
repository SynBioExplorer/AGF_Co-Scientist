import * as React from 'react';
import * as Tabs from '@radix-ui/react-tabs';
import * as Slider from '@radix-ui/react-slider';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { toast } from 'sonner';

import { MotionButton } from '../components/MotionButton';
import { MotionInput } from '../components/MotionInput';
import { MotionToggle } from '../components/MotionToggle';
import { ProviderInput } from '../components/ProviderInput';
import { AgentModelRow } from '../components/AgentModelRow';
import { ThemeToggle } from '../components/ThemeToggle';

import {
  deleteProviderSecret,
  getAgentModels,
  getSecrets,
  putAgentModels,
  putSecrets,
} from '../lib/api';
import {
  AGENT_TYPES,
  PROVIDERS,
  type AgentModelConfig,
  type AgentModelsResponse,
  type AgentType,
  type ProviderId,
  type SecretsResponse,
  type SetupCompletePayload,
} from '../lib/types';
import { springSoft } from '../lib/motion';

const APP_VERSION = '1.0.0-phaseC';

function SecretsTab(): React.ReactElement {
  const [data, setData] = React.useState<SecretsResponse | null>(null);
  const [providerKeys, setProviderKeys] = React.useState<Record<ProviderId, string>>({
    gemini: '',
    openai: '',
    deepseek: '',
    anthropic: '',
  });
  const [tavily, setTavily] = React.useState('');
  const [semanticScholar, setSemanticScholar] = React.useState(true);
  const [pubmed, setPubmed] = React.useState('');
  const [exportFolder, setExportFolder] = React.useState('~/Documents/AGF Co-Scientist');
  const [emailEnabled, setEmailEnabled] = React.useState(false);
  const [emailRecipient, setEmailRecipient] = React.useState('');

  React.useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const s = await getSecrets();
        if (cancelled) return;
        setData(s);
        setSemanticScholar(s.optional.semantic_scholar.enabled);
        setEmailEnabled(s.email.enabled);
        setEmailRecipient(s.email.recipient ?? '');
        setExportFolder(s.export_folder ?? '~/Documents/AGF Co-Scientist');
      } catch {
        /* leave empty */
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSave(): Promise<void> {
    const providers: Partial<Record<ProviderId, string>> = {};
    for (const id of Object.keys(providerKeys) as ProviderId[]) {
      const v = providerKeys[id].trim();
      if (v) providers[id] = v;
    }
    const payload: SetupCompletePayload = {
      providers,
      optional: {
        tavily: tavily.trim() || undefined,
        semantic_scholar: semanticScholar,
        pubmed: pubmed.trim() || undefined,
      },
      export_folder: exportFolder,
      email: {
        enabled: emailEnabled,
        recipient: emailEnabled ? emailRecipient : undefined,
      },
    };
    try {
      await putSecrets(payload);
      toast.success('Secrets saved');
    } catch (e) {
      const m = e instanceof Error ? e.message : 'Failed to save';
      toast.error(m);
    }
  }

  async function handleRemove(provider: ProviderId): Promise<void> {
    try {
      await deleteProviderSecret(provider);
      toast.success(`${provider} key removed`);
      setData((prev) =>
        prev
          ? {
              ...prev,
              providers: {
                ...prev.providers,
                [provider]: { set: false, masked: '' },
              },
            }
          : prev,
      );
    } catch (e) {
      const m = e instanceof Error ? e.message : 'Failed to delete';
      toast.error(m);
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-3 text-base font-semibold tracking-tight">Model providers</h3>
        <div className="space-y-3">
          {PROVIDERS.map((p) => {
            const existing = data?.providers?.[p.id];
            return (
              <div key={p.id}>
                <ProviderInput
                  provider={p}
                  value={providerKeys[p.id]}
                  onChange={(v) => setProviderKeys((prev) => ({ ...prev, [p.id]: v }))}
                  initiallyMasked
                />
                {existing?.set ? (
                  <div className="mt-1 flex items-center justify-between px-1 text-xs text-neutral-500">
                    <span className="mono">stored: {existing.masked}</span>
                    <button
                      type="button"
                      className="text-red-500 hover:text-red-600"
                      onClick={() => handleRemove(p.id)}
                      data-testid={`delete-${p.id}`}
                    >
                      Remove
                    </button>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      </section>

      <section className="card p-5">
        <h3 className="mb-2 text-base font-semibold tracking-tight">Optional services</h3>
        <div className="space-y-3">
          <MotionInput
            type="password"
            monoValue
            label="Tavily key"
            placeholder="tvly-…"
            value={tavily}
            onChange={(e) => setTavily(e.target.value)}
          />
          <MotionToggle
            checked={semanticScholar}
            onCheckedChange={setSemanticScholar}
            label="Use Semantic Scholar"
            description="Free, no key needed."
          />
          <MotionInput
            type="password"
            monoValue
            label="PubMed key"
            placeholder="NCBI API key"
            value={pubmed}
            onChange={(e) => setPubmed(e.target.value)}
          />
        </div>
      </section>

      <section className="card p-5">
        <h3 className="mb-3 text-base font-semibold tracking-tight">Export & email</h3>
        <div className="space-y-3">
          <MotionInput
            monoValue
            label="Export folder"
            value={exportFolder}
            onChange={(e) => setExportFolder(e.target.value)}
          />
          <MotionToggle
            checked={emailEnabled}
            onCheckedChange={setEmailEnabled}
            label="Email me each run's report"
          />
          {emailEnabled ? (
            <MotionInput
              type="email"
              label="Recipient email"
              value={emailRecipient}
              onChange={(e) => setEmailRecipient(e.target.value)}
            />
          ) : null}
        </div>
      </section>

      <div className="flex justify-end">
        <MotionButton onClick={handleSave} data-testid="save-secrets">
          Save changes
        </MotionButton>
      </div>
    </div>
  );
}

function ModelsTab(): React.ReactElement {
  const [data, setData] = React.useState<AgentModelsResponse | null>(null);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const d = await getAgentModels();
        if (!cancelled) setData(d);
      } catch {
        if (!cancelled) {
          setData({
            default: { provider: 'gemini', model: 'gemini-2.5-flash', temperature: 0.7 },
            agents: AGENT_TYPES.reduce(
              (acc, a) => ({ ...acc, [a]: null }),
              {} as Record<AgentType, AgentModelConfig | null>,
            ),
          });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  function updateAgent(agent: AgentType, value: AgentModelConfig | null): void {
    setData((prev) => (prev ? { ...prev, agents: { ...prev.agents, [agent]: value } } : prev));
  }

  function updateDefault(patch: Partial<AgentModelsResponse['default']>): void {
    setData((prev) => (prev ? { ...prev, default: { ...prev.default, ...patch } } : prev));
  }

  async function handleSave(): Promise<void> {
    if (!data) return;
    setSaving(true);
    try {
      await putAgentModels(data);
      toast.success('Models saved');
    } catch (e) {
      const m = e instanceof Error ? e.message : 'Failed to save';
      toast.error(m);
    } finally {
      setSaving(false);
    }
  }

  if (!data) {
    return (
      <div className="card flex h-40 items-center justify-center text-sm text-neutral-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="card p-5">
        <h3 className="mb-3 text-base font-semibold tracking-tight">Default model</h3>
        <p className="mb-4 text-xs text-neutral-500">
          Used whenever an agent is set to "Use default".
        </p>
        <div className="grid grid-cols-1 items-center gap-3 md:grid-cols-12">
          <label className="md:col-span-3 text-sm font-medium">Provider</label>
          <div className="md:col-span-3">
            <select
              value={data.default.provider}
              onChange={(e) => updateDefault({ provider: e.target.value as ProviderId })}
              className="w-full rounded-lg border border-neutral-200 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
              aria-label="Default provider"
              data-testid="default-provider"
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
          </div>
          <div className="md:col-span-4">
            <MotionInput
              label="Default model"
              monoValue
              value={data.default.model}
              onChange={(e) => updateDefault({ model: e.target.value })}
            />
          </div>
          <div className="md:col-span-2">
            <p className="mb-1 text-xs font-medium text-neutral-700 dark:text-neutral-300">
              Temperature
            </p>
            <Slider.Root
              className="relative flex h-5 w-full touch-none select-none items-center"
              min={0}
              max={2}
              step={0.1}
              value={[data.default.temperature]}
              onValueChange={(v) => updateDefault({ temperature: v[0] ?? 0 })}
              aria-label="Default temperature"
            >
              <Slider.Track className="relative h-1.5 grow rounded-full bg-neutral-200 dark:bg-neutral-700">
                <Slider.Range className="absolute h-full rounded-full bg-sky-500" />
              </Slider.Track>
              <Slider.Thumb
                className="block h-4 w-4 rounded-full bg-white shadow ring-1 ring-neutral-300"
                aria-label="Temperature"
              />
            </Slider.Root>
            <p className="mono mt-1 text-[10px] text-neutral-500">
              {data.default.temperature.toFixed(1)}
            </p>
          </div>
        </div>
      </section>

      <section>
        <h3 className="mb-3 text-base font-semibold tracking-tight">Per-agent overrides</h3>
        <div className="space-y-3">
          {AGENT_TYPES.map((a) => (
            <AgentModelRow
              key={a}
              agent={a}
              value={data.agents[a]}
              defaultLabel={data.default.model || 'default'}
              onChange={(next) => updateAgent(a, next)}
            />
          ))}
        </div>
      </section>

      <div className="flex justify-end">
        <MotionButton onClick={handleSave} isLoading={saving} data-testid="save-models">
          Save changes
        </MotionButton>
      </div>
    </div>
  );
}

function ExportTab(): React.ReactElement {
  // Re-use Secrets export section: split into its own tab for the spec
  const [data, setData] = React.useState<SecretsResponse | null>(null);
  const [folder, setFolder] = React.useState('~/Documents/AGF Co-Scientist');
  const [emailEnabled, setEmailEnabled] = React.useState(false);
  const [emailRecipient, setEmailRecipient] = React.useState('');

  React.useEffect(() => {
    let cancelled = false;
    async function load(): Promise<void> {
      try {
        const s = await getSecrets();
        if (cancelled) return;
        setData(s);
        setFolder(s.export_folder ?? folder);
        setEmailEnabled(s.email.enabled);
        setEmailRecipient(s.email.recipient ?? '');
      } catch {
        /* ignore */
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function pickFolder(): Promise<void> {
    if (window.electronAPI?.openFolder) {
      const next = await window.electronAPI.openFolder();
      if (next) setFolder(next);
    } else {
      toast.message('Folder picker requires the desktop app.');
    }
  }

  async function save(): Promise<void> {
    if (!data) return;
    const payload: SetupCompletePayload = {
      providers: {},
      optional: {
        semantic_scholar: data.optional.semantic_scholar.enabled,
      },
      export_folder: folder,
      email: { enabled: emailEnabled, recipient: emailEnabled ? emailRecipient : undefined },
    };
    try {
      await putSecrets(payload);
      toast.success('Export settings saved');
    } catch (e) {
      const m = e instanceof Error ? e.message : 'Failed to save';
      toast.error(m);
    }
  }

  return (
    <div className="space-y-4">
      <section className="card p-5">
        <h3 className="mb-3 text-base font-semibold tracking-tight">Export folder</h3>
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <div className="flex-1">
            <MotionInput
              monoValue
              value={folder}
              onChange={(e) => setFolder(e.target.value)}
              label="Path"
            />
          </div>
          <MotionButton variant="secondary" onClick={pickFolder}>
            Choose…
          </MotionButton>
        </div>
      </section>

      <section className="card p-5">
        <h3 className="mb-2 text-base font-semibold tracking-tight">Email reports</h3>
        <MotionToggle
          checked={emailEnabled}
          onCheckedChange={setEmailEnabled}
          label="Email me each run's report"
        />
        {emailEnabled ? (
          <div className="mt-2">
            <MotionInput
              type="email"
              label="Recipient"
              value={emailRecipient}
              onChange={(e) => setEmailRecipient(e.target.value)}
            />
          </div>
        ) : null}
      </section>

      <div className="flex justify-end">
        <MotionButton onClick={save}>Save changes</MotionButton>
      </div>
    </div>
  );
}

function AboutTab(): React.ReactElement {
  const [checking, setChecking] = React.useState(false);

  async function check(): Promise<void> {
    if (!window.electronAPI?.checkForUpdates) {
      toast.message('Update check requires the desktop app.');
      return;
    }
    setChecking(true);
    try {
      const res = await window.electronAPI.checkForUpdates();
      if (res.update_available) {
        toast.success(`Update available: ${res.latest_version}`);
      } else {
        toast.success('You are up to date.');
      }
    } catch (e) {
      const m = e instanceof Error ? e.message : 'Update check failed';
      toast.error(m);
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="card space-y-4 p-6">
      <div>
        <p className="mono text-[10px] uppercase tracking-widest text-neutral-500">Version</p>
        <p className="mt-1 text-lg font-semibold">{APP_VERSION}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <MotionButton onClick={check} variant="secondary" isLoading={checking}>
          Check for updates
        </MotionButton>
        <a
          href="https://github.com/AGF-Australian-Genome-Foundation/AGF_Co-Scientist"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm font-medium text-sky-600 hover:text-sky-700 dark:text-sky-400"
        >
          GitHub →
        </a>
      </div>
      <p className="text-xs text-neutral-500">Released under the MIT license.</p>
    </div>
  );
}

export default function Settings(): React.ReactElement {
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
            <span className="font-semibold tracking-tight">Settings</span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
        <motion.h1
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={springSoft}
          className="mb-8 text-3xl font-bold tracking-tightest"
        >
          Settings
        </motion.h1>

        <Tabs.Root defaultValue="models">
          <Tabs.List
            className="mb-6 flex gap-1 border-b border-neutral-200 dark:border-neutral-800"
            aria-label="Settings sections"
          >
            {[
              ['models', 'Models'],
              ['secrets', 'Secrets'],
              ['export', 'Export'],
              ['about', 'About'],
            ].map(([value, label]) => (
              <Tabs.Trigger
                key={value}
                value={value}
                className="relative px-4 py-2 text-sm font-medium text-neutral-500 transition-colors hover:text-neutral-900 data-[state=active]:text-sky-600 dark:hover:text-neutral-100 dark:data-[state=active]:text-sky-400"
                data-testid={`tab-${value}`}
              >
                {label}
              </Tabs.Trigger>
            ))}
          </Tabs.List>

          <Tabs.Content value="models">
            <ModelsTab />
          </Tabs.Content>
          <Tabs.Content value="secrets">
            <SecretsTab />
          </Tabs.Content>
          <Tabs.Content value="export">
            <ExportTab />
          </Tabs.Content>
          <Tabs.Content value="about">
            <AboutTab />
          </Tabs.Content>
        </Tabs.Root>
      </main>
    </div>
  );
}
