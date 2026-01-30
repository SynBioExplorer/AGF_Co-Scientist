import axios from 'axios';
import { useSettingsStore } from '../store/settingsStore';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Add settings to requests
api.interceptors.request.use((config) => {
  const settings = useSettingsStore.getState();

  // Add API keys based on provider
  if (settings.llmProvider === 'google' && settings.googleApiKey) {
    config.headers['X-Google-API-Key'] = settings.googleApiKey;
  } else if (settings.llmProvider === 'openai' && settings.openaiApiKey) {
    config.headers['X-OpenAI-API-Key'] = settings.openaiApiKey;
  }

  // Add Anthropic API key if available
  if (settings.anthropicApiKey) {
    config.headers['X-Anthropic-API-Key'] = settings.anthropicApiKey;
  }

  // Add Tavily API key if available
  if (settings.tavilyApiKey) {
    config.headers['X-Tavily-API-Key'] = settings.tavilyApiKey;
  }

  // Add PubMed API key if available
  if (settings.pubmedApiKey) {
    config.headers['X-PubMed-API-Key'] = settings.pubmedApiKey;
  }

  // Add LangSmith API key if available
  if (settings.langsmithApiKey) {
    config.headers['X-LangSmith-API-Key'] = settings.langsmithApiKey;
  }

  return config;
});

// Goals
export const createGoal = async (data: {
  description: string;
  constraints?: string[];
  preferences?: string[];
}) => {
  const settings = useSettingsStore.getState();
  const response = await api.post('/goals', {
    ...data,
    config: {
      llm_provider: settings.llmProvider,
      default_model: settings.defaultModel,
      default_temperature: settings.defaultTemperature,
      agent_models: settings.agentModels,
      max_iterations: settings.maxIterations,
      enable_evolution: settings.enableEvolution,
      enable_web_search: settings.enableWebSearch,
    },
  });
  return response.data;
};

export const getGoalStatus = async (goalId: string) => {
  const response = await api.get(`/goals/${goalId}`);
  return response.data;
};

// Hypotheses
export const getHypotheses = async (
  goalId: string,
  page = 1,
  pageSize = 10,
  sortBy = 'elo'
) => {
  const response = await api.get(`/goals/${goalId}/hypotheses`, {
    params: { page, page_size: pageSize, sort_by: sortBy },
  });
  return response.data;
};

export const getHypothesisDetail = async (hypothesisId: string) => {
  const response = await api.get(`/hypotheses/${hypothesisId}`);
  return response.data;
};

export const submitFeedback = async (
  hypothesisId: string,
  rating: number,
  comments: string
) => {
  const response = await api.post(`/hypotheses/${hypothesisId}/feedback`, {
    hypothesis_id: hypothesisId,
    rating,
    comments,
  });
  return response.data;
};

// Statistics
export const getStatistics = async (goalId: string) => {
  const response = await api.get(`/goals/${goalId}/stats`);
  return response.data;
};

// Chat
export const sendChatMessage = async (goalId: string, message: string) => {
  const response = await api.post('/api/v1/chat', {
    goal_id: goalId,
    message,
  });
  return response.data;
};

export const getChatHistory = async (goalId: string) => {
  const response = await api.get(`/api/v1/chat/${goalId}/history`);
  return response.data;
};

// Settings
export const getSettings = async () => {
  const response = await api.get('/settings');
  return response.data;
};

export const updateSettings = async (settings: Record<string, any>) => {
  const response = await api.put('/settings', settings);
  return response.data;
};

// Health
export const healthCheck = async () => {
  try {
    await api.get('/health');
    return true;
  } catch {
    return false;
  }
};

export default api;
