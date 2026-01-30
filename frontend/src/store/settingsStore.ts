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
  tavilyApiKey: string;
  langsmithApiKey: string;

  // Parameters
  maxIterations: number;
  tournamentRounds: number;
  eloKFactor: number;

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
  setTavilyApiKey: (key: string) => void;
  setLangsmithApiKey: (key: string) => void;
  setMaxIterations: (max: number) => void;
  setTournamentRounds: (rounds: number) => void;
  setEloKFactor: (k: number) => void;
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
      tavilyApiKey: '',
      langsmithApiKey: '',
      maxIterations: 20,
      tournamentRounds: 5,
      eloKFactor: 32,
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
      setTavilyApiKey: (key) => set({ tavilyApiKey: key }),
      setLangsmithApiKey: (key) => set({ langsmithApiKey: key }),
      setMaxIterations: (max) => set({ maxIterations: max }),
      setTournamentRounds: (rounds) => set({ tournamentRounds: rounds }),
      setEloKFactor: (k) => set({ eloKFactor: k }),
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
