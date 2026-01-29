# Phase 5D: Frontend Dashboard

> **Local Development Only** - No cloud deployment, no authentication.

## Overview

Build a React-based frontend for scientist interaction with the AI Co-Scientist system, including chat interface, model/parameter configuration, and visualizations.

**Dependencies:** Phase 4 API complete
**Target:** Local development (http://localhost:5173 → http://localhost:8000)
**Tech Stack:** React 18 + TypeScript + Vite + Tailwind CSS + Recharts

## Key Features

| Feature | Description |
|---------|-------------|
| Chat Interface | Context-aware conversation with AI |
| Settings Panel | Model selection, API keys, parameters |
| Hypothesis Browser | List/detail views with Elo ratings |
| Visualizations | Elo chart, quality distribution |
| Literature Page | PDF upload, semantic search |
| Dashboard | Statistics and overview |

## Directory Structure

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Slider.tsx
│   │   │   ├── Select.tsx
│   │   │   └── Loading.tsx
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Layout.tsx
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageList.tsx
│   │   │   └── MessageInput.tsx
│   │   ├── hypotheses/
│   │   │   ├── HypothesisList.tsx
│   │   │   ├── HypothesisCard.tsx
│   │   │   └── HypothesisDetail.tsx
│   │   ├── settings/
│   │   │   ├── SettingsPanel.tsx
│   │   │   ├── ModelSelector.tsx
│   │   │   ├── ApiKeyInput.tsx
│   │   │   └── ParameterSliders.tsx
│   │   ├── literature/
│   │   │   ├── PdfUpload.tsx
│   │   │   ├── DocumentList.tsx
│   │   │   └── SearchResults.tsx
│   │   └── visualizations/
│   │       ├── EloChart.tsx
│   │       ├── QualityDistribution.tsx
│   │       └── AgentActivity.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── ChatPage.tsx
│   │   ├── HypothesesPage.tsx
│   │   ├── LiteraturePage.tsx
│   │   └── SettingsPage.tsx
│   ├── hooks/
│   │   ├── useApi.ts
│   │   ├── usePolling.ts
│   │   └── useSettings.ts
│   ├── services/
│   │   └── api.ts
│   ├── store/
│   │   └── settingsStore.ts
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── vite.config.ts
└── tailwind.config.js
```

## Project Setup

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend

npm install axios react-router-dom zustand @tanstack/react-query
npm install recharts
npm install -D tailwindcss postcss autoprefixer @types/node

npx tailwindcss init -p
```

## Settings Schema

The settings panel allows runtime configuration of the system:

```typescript
interface Settings {
  // Model selection
  llmProvider: 'google' | 'openai';
  model: string;  // e.g., 'gemini-1.5-pro', 'gpt-4-turbo'

  // API keys (stored in localStorage)
  googleApiKey?: string;
  openaiApiKey?: string;
  tavilyApiKey?: string;

  // Parameters
  temperature: number;        // 0.0 - 1.0, default 0.7
  maxIterations: number;      // 1 - 50, default 20
  tournamentRounds: number;   // 1 - 10, default 5
  eloKFactor: number;         // 16 - 64, default 32

  // Feature toggles
  enableEvolution: boolean;
  enableWebSearch: boolean;
  enableLiteratureSearch: boolean;
}
```

## Key Components

### Settings Panel (`src/components/settings/SettingsPanel.tsx`)

```tsx
import React from 'react';
import { useSettingsStore } from '../../store/settingsStore';
import { ModelSelector } from './ModelSelector';
import { ApiKeyInput } from './ApiKeyInput';
import { ParameterSliders } from './ParameterSliders';

export const SettingsPanel: React.FC = () => {
  const settings = useSettingsStore();

  return (
    <div className="space-y-6 p-4">
      <h2 className="text-xl font-bold">Settings</h2>

      {/* Model Selection */}
      <section>
        <h3 className="text-lg font-semibold mb-2">Model</h3>
        <ModelSelector
          provider={settings.llmProvider}
          model={settings.model}
          onProviderChange={settings.setProvider}
          onModelChange={settings.setModel}
        />
      </section>

      {/* API Keys */}
      <section>
        <h3 className="text-lg font-semibold mb-2">API Keys</h3>
        <div className="space-y-2">
          <ApiKeyInput
            label="Google API Key"
            value={settings.googleApiKey}
            onChange={settings.setGoogleApiKey}
          />
          <ApiKeyInput
            label="OpenAI API Key"
            value={settings.openaiApiKey}
            onChange={settings.setOpenaiApiKey}
          />
          <ApiKeyInput
            label="Tavily API Key"
            value={settings.tavilyApiKey}
            onChange={settings.setTavilyApiKey}
          />
        </div>
      </section>

      {/* Parameters */}
      <section>
        <h3 className="text-lg font-semibold mb-2">Parameters</h3>
        <ParameterSliders />
      </section>

      {/* Feature Toggles */}
      <section>
        <h3 className="text-lg font-semibold mb-2">Features</h3>
        <div className="space-y-2">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.enableEvolution}
              onChange={(e) => settings.setEnableEvolution(e.target.checked)}
            />
            Enable Hypothesis Evolution
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.enableWebSearch}
              onChange={(e) => settings.setEnableWebSearch(e.target.checked)}
            />
            Enable Web Search
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={settings.enableLiteratureSearch}
              onChange={(e) => settings.setEnableLiteratureSearch(e.target.checked)}
            />
            Enable Literature Search
          </label>
        </div>
      </section>
    </div>
  );
};
```

### Model Selector (`src/components/settings/ModelSelector.tsx`)

```tsx
import React from 'react';

interface Props {
  provider: 'google' | 'openai';
  model: string;
  onProviderChange: (provider: 'google' | 'openai') => void;
  onModelChange: (model: string) => void;
}

const MODELS = {
  google: [
    { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro' },
    { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash' },
    { id: 'gemini-2.0-flash-exp', name: 'Gemini 2.0 Flash (Experimental)' },
  ],
  openai: [
    { id: 'gpt-4-turbo', name: 'GPT-4 Turbo' },
    { id: 'gpt-4o', name: 'GPT-4o' },
    { id: 'gpt-4o-mini', name: 'GPT-4o Mini' },
  ],
};

export const ModelSelector: React.FC<Props> = ({
  provider,
  model,
  onProviderChange,
  onModelChange,
}) => {
  return (
    <div className="space-y-3">
      {/* Provider Selection */}
      <div>
        <label className="block text-sm font-medium mb-1">Provider</label>
        <select
          value={provider}
          onChange={(e) => onProviderChange(e.target.value as 'google' | 'openai')}
          className="w-full p-2 border rounded"
        >
          <option value="google">Google (Gemini)</option>
          <option value="openai">OpenAI (GPT)</option>
        </select>
      </div>

      {/* Model Selection */}
      <div>
        <label className="block text-sm font-medium mb-1">Model</label>
        <select
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          className="w-full p-2 border rounded"
        >
          {MODELS[provider].map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};
```

### Parameter Sliders (`src/components/settings/ParameterSliders.tsx`)

```tsx
import React from 'react';
import { useSettingsStore } from '../../store/settingsStore';

export const ParameterSliders: React.FC = () => {
  const settings = useSettingsStore();

  return (
    <div className="space-y-4">
      {/* Temperature */}
      <div>
        <label className="flex justify-between text-sm mb-1">
          <span>Temperature</span>
          <span className="font-mono">{settings.temperature.toFixed(2)}</span>
        </label>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={settings.temperature}
          onChange={(e) => settings.setTemperature(parseFloat(e.target.value))}
          className="w-full"
        />
        <p className="text-xs text-gray-500">
          Lower = more focused, Higher = more creative
        </p>
      </div>

      {/* Max Iterations */}
      <div>
        <label className="flex justify-between text-sm mb-1">
          <span>Max Iterations</span>
          <span className="font-mono">{settings.maxIterations}</span>
        </label>
        <input
          type="range"
          min="1"
          max="50"
          step="1"
          value={settings.maxIterations}
          onChange={(e) => settings.setMaxIterations(parseInt(e.target.value))}
          className="w-full"
        />
      </div>

      {/* Tournament Rounds */}
      <div>
        <label className="flex justify-between text-sm mb-1">
          <span>Tournament Rounds</span>
          <span className="font-mono">{settings.tournamentRounds}</span>
        </label>
        <input
          type="range"
          min="1"
          max="10"
          step="1"
          value={settings.tournamentRounds}
          onChange={(e) => settings.setTournamentRounds(parseInt(e.target.value))}
          className="w-full"
        />
      </div>

      {/* Elo K-Factor */}
      <div>
        <label className="flex justify-between text-sm mb-1">
          <span>Elo K-Factor</span>
          <span className="font-mono">{settings.eloKFactor}</span>
        </label>
        <input
          type="range"
          min="16"
          max="64"
          step="4"
          value={settings.eloKFactor}
          onChange={(e) => settings.setEloKFactor(parseInt(e.target.value))}
          className="w-full"
        />
        <p className="text-xs text-gray-500">
          Higher = ratings change faster after matches
        </p>
      </div>
    </div>
  );
};
```

### Settings Store (`src/store/settingsStore.ts`)

```typescript
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SettingsState {
  // Model
  llmProvider: 'google' | 'openai';
  model: string;

  // API Keys
  googleApiKey: string;
  openaiApiKey: string;
  tavilyApiKey: string;

  // Parameters
  temperature: number;
  maxIterations: number;
  tournamentRounds: number;
  eloKFactor: number;

  // Features
  enableEvolution: boolean;
  enableWebSearch: boolean;
  enableLiteratureSearch: boolean;

  // Actions
  setProvider: (provider: 'google' | 'openai') => void;
  setModel: (model: string) => void;
  setGoogleApiKey: (key: string) => void;
  setOpenaiApiKey: (key: string) => void;
  setTavilyApiKey: (key: string) => void;
  setTemperature: (temp: number) => void;
  setMaxIterations: (max: number) => void;
  setTournamentRounds: (rounds: number) => void;
  setEloKFactor: (k: number) => void;
  setEnableEvolution: (enabled: boolean) => void;
  setEnableWebSearch: (enabled: boolean) => void;
  setEnableLiteratureSearch: (enabled: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      // Default values
      llmProvider: 'google',
      model: 'gemini-1.5-pro',
      googleApiKey: '',
      openaiApiKey: '',
      tavilyApiKey: '',
      temperature: 0.7,
      maxIterations: 20,
      tournamentRounds: 5,
      eloKFactor: 32,
      enableEvolution: true,
      enableWebSearch: true,
      enableLiteratureSearch: false,

      // Actions
      setProvider: (provider) => set({ llmProvider: provider }),
      setModel: (model) => set({ model }),
      setGoogleApiKey: (key) => set({ googleApiKey: key }),
      setOpenaiApiKey: (key) => set({ openaiApiKey: key }),
      setTavilyApiKey: (key) => set({ tavilyApiKey: key }),
      setTemperature: (temp) => set({ temperature: temp }),
      setMaxIterations: (max) => set({ maxIterations: max }),
      setTournamentRounds: (rounds) => set({ tournamentRounds: rounds }),
      setEloKFactor: (k) => set({ eloKFactor: k }),
      setEnableEvolution: (enabled) => set({ enableEvolution: enabled }),
      setEnableWebSearch: (enabled) => set({ enableWebSearch: enabled }),
      setEnableLiteratureSearch: (enabled) => set({ enableLiteratureSearch: enabled }),
    }),
    {
      name: 'coscientist-settings',
    }
  )
);
```

### Chat Window (`src/components/chat/ChatWindow.tsx`)

```tsx
import React, { useState, useEffect, useRef } from 'react';
import { sendChatMessage, getChatHistory } from '../../services/api';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import type { ChatMessage } from '../../types';

interface Props {
  goalId: string;
}

export const ChatWindow: React.FC<Props> = ({ goalId }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [contextIds, setContextIds] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadHistory = async () => {
      const history = await getChatHistory(goalId);
      setMessages(history.messages || []);
    };
    loadHistory();
  }, [goalId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (content: string) => {
    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'scientist',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await sendChatMessage(goalId, content);
      const aiMessage: ChatMessage = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: response.message,
        timestamp: response.timestamp,
      };
      setMessages((prev) => [...prev, aiMessage]);
      setContextIds(response.context_used || []);
    } catch (error) {
      console.error('Failed to send message:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      <div className="p-4 border-b">
        <h2 className="text-lg font-semibold">Chat with AI Co-Scientist</h2>
        {contextIds.length > 0 && (
          <p className="text-sm text-gray-500">
            Using context from {contextIds.length} hypothesis(es)
          </p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <MessageList messages={messages} />
        {loading && (
          <div className="flex items-center gap-2 text-gray-500">
            <div className="animate-pulse">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t">
        <MessageInput onSend={handleSend} disabled={loading} />
      </div>
    </div>
  );
};
```

### Elo Chart (`src/components/visualizations/EloChart.tsx`)

```tsx
import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import type { Hypothesis } from '../../types';

interface Props {
  hypotheses: Hypothesis[];
}

export const EloChart: React.FC<Props> = ({ hypotheses }) => {
  const sortedHypotheses = [...hypotheses]
    .sort((a, b) => b.elo_rating - a.elo_rating)
    .slice(0, 10);

  const data = sortedHypotheses.map((h, index) => ({
    rank: index + 1,
    name: h.title.substring(0, 25) + (h.title.length > 25 ? '...' : ''),
    elo: Math.round(h.elo_rating),
  }));

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold mb-4">Top 10 Hypotheses by Elo Rating</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="rank"
            label={{ value: 'Rank', position: 'bottom', offset: -5 }}
          />
          <YAxis
            domain={['dataMin - 50', 'dataMax + 50']}
            label={{ value: 'Elo Rating', angle: -90, position: 'insideLeft' }}
          />
          <Tooltip
            formatter={(value: number) => [value, 'Elo']}
            labelFormatter={(rank) => `Rank #${rank}`}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="elo"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ fill: '#6366f1', strokeWidth: 2 }}
            name="Elo Rating"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};
```

## API Service (`src/services/api.ts`)

```typescript
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

  // Add API key based on provider
  if (settings.llmProvider === 'google' && settings.googleApiKey) {
    config.headers['X-Google-API-Key'] = settings.googleApiKey;
  } else if (settings.llmProvider === 'openai' && settings.openaiApiKey) {
    config.headers['X-OpenAI-API-Key'] = settings.openaiApiKey;
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
      model: settings.model,
      temperature: settings.temperature,
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
```

## Polling Hook (`src/hooks/usePolling.ts`)

```typescript
import { useEffect, useRef, useState, useCallback } from 'react';

interface UsePollingOptions {
  interval?: number;
  enabled?: boolean;
}

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  options: UsePollingOptions = {}
) {
  const { interval = 5000, enabled = true } = options;
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const intervalRef = useRef<number>();

  const poll = useCallback(async () => {
    try {
      const result = await fetchFn();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    if (!enabled) return;

    poll();
    intervalRef.current = window.setInterval(poll, interval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [poll, interval, enabled]);

  return { data, loading, error, refetch: poll };
}
```

## TypeScript Types (`src/types/index.ts`)

```typescript
export interface ResearchGoal {
  id: string;
  description: string;
  constraints: string[];
  preferences: string[];
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
}

export interface Hypothesis {
  id: string;
  research_goal_id: string;
  title: string;
  summary: string;
  hypothesis_statement: string;
  rationale: string;
  elo_rating: number;
  status: string;
  created_at: string;
}

export interface Review {
  id: string;
  hypothesis_id: string;
  quality_score: number;
  strengths: string[];
  weaknesses: string[];
  review_type: string;
}

export interface TournamentRecord {
  wins: number;
  losses: number;
  win_rate: number;
  total_matches: number;
}

export interface ChatMessage {
  id: string;
  role: 'scientist' | 'assistant';
  content: string;
  timestamp: string;
}

export interface SystemStatistics {
  goal_id: string;
  hypotheses_generated: number;
  hypotheses_pending_review: number;
  hypotheses_in_tournament: number;
  total_matches: number;
  tournament_convergence: number;
}

export interface HypothesisDetail extends Hypothesis {
  reviews: Review[];
  tournament_record: TournamentRecord;
  evolution_history: Hypothesis[];
}
```

## Environment Configuration

### Local Development (`.env`)
```bash
VITE_API_URL=http://localhost:8000
```

No production configuration needed - this is local-only.

## Local Development

```bash
# Terminal 1: Start backend
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend && npm run dev
```

## Success Criteria

- [ ] React app builds and runs locally
- [ ] Settings panel with model/parameter controls
- [ ] Chat interface sending/receiving messages
- [ ] Hypothesis list with Elo ratings and sorting
- [ ] Hypothesis detail view with reviews
- [ ] Elo chart visualization working
- [ ] Statistics dashboard displaying metrics
- [ ] Polling updates goal status
- [ ] Settings persist in localStorage
