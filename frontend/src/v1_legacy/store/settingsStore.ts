import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { AgentType, AgentModelConfig } from '../types';
import { DEFAULT_AGENT_MODELS } from '../constants/models';

interface SettingsState {
  // Model
  llmProvider: 'google' | 'openai';
  defaultModel: string;
  defaultTemperature: number;
  agentModels: Record<AgentType, AgentModelConfig>;

  // API Keys
  googleApiKey: string;
  openaiApiKey: string;
  anthropicApiKey: string;
  tavilyApiKey: string;
  pubmedApiKey: string;
  langsmithApiKey: string;

  // Parameters
  maxIterations: number;
  tournamentRounds: number;
  eloKFactor: number;
  budgetAud: number;
  safetyThreshold: number;
  llmTimeoutSeconds: number;

  // Features
  enableEvolution: boolean;
  enableWebSearch: boolean;
  enableLiteratureSearch: boolean;

  // Actions
  setProvider: (provider: 'google' | 'openai') => void;
  setDefaultModel: (model: string) => void;
  setDefaultTemperature: (temp: number) => void;
  setAgentModel: (agentType: AgentType, config: AgentModelConfig) => void;
  setGoogleApiKey: (key: string) => void;
  setOpenaiApiKey: (key: string) => void;
  setAnthropicApiKey: (key: string) => void;
  setTavilyApiKey: (key: string) => void;
  setPubmedApiKey: (key: string) => void;
  setLangsmithApiKey: (key: string) => void;
  setMaxIterations: (max: number) => void;
  setTournamentRounds: (rounds: number) => void;
  setEloKFactor: (k: number) => void;
  setBudgetAud: (aud: number) => void;
  setSafetyThreshold: (threshold: number) => void;
  setLlmTimeoutSeconds: (seconds: number) => void;
  setEnableEvolution: (enabled: boolean) => void;
  setEnableWebSearch: (enabled: boolean) => void;
  setEnableLiteratureSearch: (enabled: boolean) => void;
  resetAgentModelsToDefaults: () => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      // Default values
      llmProvider: 'google',
      defaultModel: 'gemini-3-pro-preview',
      defaultTemperature: 0.7,
      agentModels: DEFAULT_AGENT_MODELS.google,
      googleApiKey: '',
      openaiApiKey: '',
      anthropicApiKey: '',
      tavilyApiKey: '',
      pubmedApiKey: '',
      langsmithApiKey: '',
      maxIterations: 20,
      tournamentRounds: 3,
      eloKFactor: 32,
      budgetAud: 50,
      safetyThreshold: 0,
      llmTimeoutSeconds: 300,
      enableEvolution: true,
      enableWebSearch: true,
      enableLiteratureSearch: false,

      // Actions
      setProvider: (provider) => {
        const defaults = DEFAULT_AGENT_MODELS[provider];
        set({
          llmProvider: provider,
          agentModels: defaults,
          defaultModel: defaults.generation.model,
        });
      },
      setDefaultModel: (model) => set({ defaultModel: model }),
      setDefaultTemperature: (temp) => set({ defaultTemperature: temp }),
      setAgentModel: (agentType, config) =>
        set((state) => ({
          agentModels: {
            ...state.agentModels,
            [agentType]: config,
          },
        })),
      setGoogleApiKey: (key) => set({ googleApiKey: key }),
      setOpenaiApiKey: (key) => set({ openaiApiKey: key }),
      setAnthropicApiKey: (key) => set({ anthropicApiKey: key }),
      setTavilyApiKey: (key) => set({ tavilyApiKey: key }),
      setPubmedApiKey: (key) => set({ pubmedApiKey: key }),
      setLangsmithApiKey: (key) => set({ langsmithApiKey: key }),
      setMaxIterations: (max) => set({ maxIterations: max }),
      setTournamentRounds: (rounds) => set({ tournamentRounds: rounds }),
      setEloKFactor: (k) => set({ eloKFactor: k }),
      setBudgetAud: (aud) => set({ budgetAud: aud }),
      setSafetyThreshold: (threshold) => set({ safetyThreshold: threshold }),
      setLlmTimeoutSeconds: (seconds) => set({ llmTimeoutSeconds: seconds }),
      setEnableEvolution: (enabled) => set({ enableEvolution: enabled }),
      setEnableWebSearch: (enabled) => set({ enableWebSearch: enabled }),
      setEnableLiteratureSearch: (enabled) => set({ enableLiteratureSearch: enabled }),
      resetAgentModelsToDefaults: () => {
        const provider = get().llmProvider;
        const defaults = DEFAULT_AGENT_MODELS[provider];
        set({ agentModels: defaults });
      },
    }),
    {
      name: 'coscientist-settings',
    }
  )
);
