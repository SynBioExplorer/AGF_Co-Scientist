# Phase 5D: Frontend Dashboard

## Overview

Build a React-based frontend dashboard for scientist interaction with the AI Co-Scientist system. The frontend will initially run locally and later deploy to AWS Amplify.

**Branch:** `phase5/frontend`
**Worktree:** `worktree-5d-frontend`
**Dependencies:** Phase 4 API complete
**Estimated Duration:** 2 weeks

## Deployment Strategy

1. **Local Development:** React dev server → FastAPI backend (localhost)
2. **Production:** AWS Amplify (React) → API Gateway → FastAPI (Lambda or ECS)

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | React 18 + TypeScript |
| Build Tool | Vite |
| Styling | Tailwind CSS |
| State Management | Zustand or React Query |
| Charts | Recharts or Chart.js |
| Real-time | WebSocket or Server-Sent Events |
| Deployment | AWS Amplify |

## Deliverables

### Directory Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── Loading.tsx
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Layout.tsx
│   │   ├── goals/
│   │   │   ├── GoalForm.tsx
│   │   │   ├── GoalList.tsx
│   │   │   └── GoalCard.tsx
│   │   ├── hypotheses/
│   │   │   ├── HypothesisList.tsx
│   │   │   ├── HypothesisCard.tsx
│   │   │   ├── HypothesisDetail.tsx
│   │   │   └── EloChart.tsx
│   │   ├── tournament/
│   │   │   ├── TournamentBracket.tsx
│   │   │   ├── MatchCard.tsx
│   │   │   └── EloHistory.tsx
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── MessageList.tsx
│   │   │   └── MessageInput.tsx
│   │   └── overview/
│   │       ├── ResearchOverview.tsx
│   │       └── DirectionCard.tsx
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── GoalsPage.tsx
│   │   ├── HypothesesPage.tsx
│   │   ├── TournamentPage.tsx
│   │   └── ChatPage.tsx
│   ├── hooks/
│   │   ├── useGoals.ts
│   │   ├── useHypotheses.ts
│   │   ├── useWebSocket.ts
│   │   └── useApi.ts
│   ├── services/
│   │   ├── api.ts
│   │   └── websocket.ts
│   ├── store/
│   │   └── index.ts
│   ├── types/
│   │   └── index.ts
│   ├── utils/
│   │   └── helpers.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
└── amplify.yml
```

### 1. Project Setup

```bash
# Create React project with Vite
npm create vite@latest frontend -- --template react-ts
cd frontend

# Install dependencies
npm install axios react-router-dom zustand @tanstack/react-query
npm install recharts date-fns
npm install -D tailwindcss postcss autoprefixer
npm install -D @types/node

# Initialize Tailwind
npx tailwindcss init -p
```

### 2. TypeScript Types (`src/types/index.ts`)

```typescript
// Research Goal
export interface ResearchGoal {
  id: string;
  description: string;
  constraints: string[];
  preferences: string[];
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
}

// Hypothesis
export interface Hypothesis {
  id: string;
  research_goal_id: string;
  title: string;
  summary: string;
  hypothesis_statement: string;
  rationale: string;
  mechanism: string;
  elo_rating: number;
  status: string;
  created_at: string;
  reviews: Review[];
  tournament_record: TournamentRecord;
}

// Review
export interface Review {
  id: string;
  hypothesis_id: string;
  review_type: string;
  scores: {
    correctness: number;
    quality: number;
    novelty: number;
    testability: number;
    safety: number;
  };
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
}

// Tournament
export interface TournamentMatch {
  id: string;
  hypothesis_a_id: string;
  hypothesis_b_id: string;
  winner_id: string;
  rationale: string;
  elo_change_a: number;
  elo_change_b: number;
  created_at: string;
}

export interface TournamentRecord {
  wins: number;
  losses: number;
  win_rate: number;
}

// Chat
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

// Statistics
export interface SystemStatistics {
  hypothesis_count: number;
  reviewed_count: number;
  tournament_matches: number;
  convergence_score: number;
  top_elo: number;
  avg_quality: number;
}

// Research Overview
export interface ResearchOverview {
  id: string;
  executive_summary: string;
  research_directions: ResearchDirection[];
  top_hypotheses: Hypothesis[];
  suggested_contacts: ResearchContact[];
}

export interface ResearchDirection {
  title: string;
  description: string;
  feasibility_score: number;
  suggested_experiments: string[];
}

export interface ResearchContact {
  name: string;
  affiliation: string;
  expertise: string[];
  reason: string;
}
```

### 3. API Service (`src/services/api.ts`)

```typescript
import axios from 'axios';
import type {
  ResearchGoal,
  Hypothesis,
  ChatMessage,
  SystemStatistics,
  ResearchOverview
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Goals
export const createGoal = async (goal: Partial<ResearchGoal>): Promise<ResearchGoal> => {
  const { data } = await api.post('/goals', goal);
  return data;
};

export const getGoal = async (goalId: string): Promise<ResearchGoal> => {
  const { data } = await api.get(`/goals/${goalId}`);
  return data;
};

export const listGoals = async (): Promise<ResearchGoal[]> => {
  const { data } = await api.get('/goals');
  return data.goals;
};

// Hypotheses
export const getHypotheses = async (goalId: string): Promise<Hypothesis[]> => {
  const { data } = await api.get(`/goals/${goalId}/hypotheses`);
  return data.hypotheses;
};

export const getHypothesis = async (hypothesisId: string): Promise<Hypothesis> => {
  const { data } = await api.get(`/hypotheses/${hypothesisId}`);
  return data;
};

export const submitFeedback = async (
  hypothesisId: string,
  feedback: { rating: number; comments: string }
): Promise<void> => {
  await api.post(`/hypotheses/${hypothesisId}/feedback`, feedback);
};

// Statistics
export const getStatistics = async (goalId: string): Promise<SystemStatistics> => {
  const { data } = await api.get(`/goals/${goalId}/stats`);
  return data;
};

// Overview
export const getOverview = async (goalId: string): Promise<ResearchOverview> => {
  const { data } = await api.get(`/goals/${goalId}/overview`);
  return data;
};

// Chat
export const sendChatMessage = async (
  goalId: string,
  message: string
): Promise<ChatMessage> => {
  const { data } = await api.post('/chat', { goal_id: goalId, message });
  return data;
};

export const getChatHistory = async (goalId: string): Promise<ChatMessage[]> => {
  const { data } = await api.get(`/chat/${goalId}/history`);
  return data.messages;
};

// Health
export const healthCheck = async (): Promise<boolean> => {
  try {
    await api.get('/health');
    return true;
  } catch {
    return false;
  }
};

export default api;
```

### 4. WebSocket Service (`src/services/websocket.ts`)

```typescript
type MessageHandler = (data: any) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  connect(goalId: string): void {
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
    this.ws = new WebSocket(`${wsUrl}/ws/${goalId}`);

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const handlers = this.handlers.get(data.type) || [];
      handlers.forEach((handler) => handler(data.payload));
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
      this.attemptReconnect(goalId);
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  private attemptReconnect(goalId: string): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => this.connect(goalId), 1000 * this.reconnectAttempts);
    }
  }

  subscribe(eventType: string, handler: MessageHandler): () => void {
    const handlers = this.handlers.get(eventType) || [];
    handlers.push(handler);
    this.handlers.set(eventType, handlers);

    // Return unsubscribe function
    return () => {
      const updated = this.handlers.get(eventType)?.filter((h) => h !== handler) || [];
      this.handlers.set(eventType, updated);
    };
  }

  disconnect(): void {
    this.ws?.close();
    this.ws = null;
  }
}

export const wsService = new WebSocketService();
```

### 5. Key Components

#### Dashboard (`src/pages/Dashboard.tsx`)

```tsx
import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getStatistics, getHypotheses } from '../services/api';
import { EloChart } from '../components/hypotheses/EloChart';
import { HypothesisList } from '../components/hypotheses/HypothesisList';
import { StatCard } from '../components/common/StatCard';
import type { SystemStatistics, Hypothesis } from '../types';

export const Dashboard: React.FC = () => {
  const { goalId } = useParams<{ goalId: string }>();
  const [stats, setStats] = useState<SystemStatistics | null>(null);
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!goalId) return;

    const fetchData = async () => {
      setLoading(true);
      const [statsData, hypData] = await Promise.all([
        getStatistics(goalId),
        getHypotheses(goalId),
      ]);
      setStats(statsData);
      setHypotheses(hypData);
      setLoading(false);
    };

    fetchData();
  }, [goalId]);

  if (loading) {
    return <div className="flex justify-center p-8">Loading...</div>;
  }

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Research Dashboard</h1>

      {/* Statistics Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          title="Hypotheses"
          value={stats?.hypothesis_count || 0}
          icon="🧬"
        />
        <StatCard
          title="Reviewed"
          value={stats?.reviewed_count || 0}
          icon="📝"
        />
        <StatCard
          title="Tournament Matches"
          value={stats?.tournament_matches || 0}
          icon="🏆"
        />
        <StatCard
          title="Convergence"
          value={`${((stats?.convergence_score || 0) * 100).toFixed(1)}%`}
          icon="📈"
        />
      </div>

      {/* Elo Rating Chart */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-4">Elo Ratings Over Time</h2>
        <EloChart hypotheses={hypotheses} />
      </div>

      {/* Top Hypotheses */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-4">Top Hypotheses</h2>
        <HypothesisList
          hypotheses={hypotheses.slice(0, 5)}
          compact
        />
      </div>
    </div>
  );
};
```

#### Elo Chart (`src/components/hypotheses/EloChart.tsx`)

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
  // Sort by Elo rating for display
  const sortedHypotheses = [...hypotheses]
    .sort((a, b) => b.elo_rating - a.elo_rating)
    .slice(0, 10);

  const data = sortedHypotheses.map((h, index) => ({
    name: h.title.substring(0, 30) + '...',
    elo: h.elo_rating,
    rank: index + 1,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="rank" label={{ value: 'Rank', position: 'bottom' }} />
        <YAxis
          domain={[1000, 1600]}
          label={{ value: 'Elo Rating', angle: -90, position: 'left' }}
        />
        <Tooltip />
        <Legend />
        <Line
          type="monotone"
          dataKey="elo"
          stroke="#8884d8"
          strokeWidth={2}
          dot={{ fill: '#8884d8' }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
};
```

#### Chat Window (`src/components/chat/ChatWindow.tsx`)

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
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadHistory = async () => {
      const history = await getChatHistory(goalId);
      setMessages(history);
    };
    loadHistory();
  }, [goalId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (content: string) => {
    // Add user message immediately
    const userMessage: ChatMessage = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await sendChatMessage(goalId, content);
      setMessages((prev) => [...prev, response]);
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
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <MessageList messages={messages} />
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 border-t">
        <MessageInput onSend={handleSend} disabled={loading} />
      </div>
    </div>
  );
};
```

#### Hypothesis Card (`src/components/hypotheses/HypothesisCard.tsx`)

```tsx
import React from 'react';
import { Link } from 'react-router-dom';
import type { Hypothesis } from '../../types';

interface Props {
  hypothesis: Hypothesis;
  compact?: boolean;
}

export const HypothesisCard: React.FC<Props> = ({ hypothesis, compact }) => {
  const { id, title, elo_rating, status, tournament_record } = hypothesis;

  if (compact) {
    return (
      <Link
        to={`/hypotheses/${id}`}
        className="block p-3 border rounded hover:bg-gray-50"
      >
        <div className="flex justify-between items-center">
          <span className="font-medium truncate flex-1">{title}</span>
          <span className="ml-2 px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
            Elo: {elo_rating.toFixed(0)}
          </span>
        </div>
      </Link>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex justify-between items-start mb-2">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span
          className={`px-2 py-1 rounded text-sm ${
            status === 'in_tournament'
              ? 'bg-green-100 text-green-800'
              : 'bg-gray-100 text-gray-800'
          }`}
        >
          {status}
        </span>
      </div>

      <p className="text-gray-600 mb-4">{hypothesis.summary}</p>

      <div className="flex gap-4 text-sm">
        <div className="flex items-center gap-1">
          <span className="font-medium">Elo:</span>
          <span className="text-blue-600">{elo_rating.toFixed(0)}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="font-medium">Record:</span>
          <span className="text-green-600">{tournament_record.wins}W</span>
          <span className="text-red-600">{tournament_record.losses}L</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="font-medium">Win Rate:</span>
          <span>{(tournament_record.win_rate * 100).toFixed(1)}%</span>
        </div>
      </div>

      <Link
        to={`/hypotheses/${id}`}
        className="mt-4 inline-block text-blue-600 hover:underline"
      >
        View Details →
      </Link>
    </div>
  );
};
```

### 6. AWS Amplify Configuration (`amplify.yml`)

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - cd frontend
        - npm ci
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: frontend/dist
    files:
      - '**/*'
  cache:
    paths:
      - frontend/node_modules/**/*

  customHeaders:
    - pattern: '**/*'
      headers:
        - key: 'Cache-Control'
          value: 'public, max-age=31536000, immutable'
    - pattern: 'index.html'
      headers:
        - key: 'Cache-Control'
          value: 'public, max-age=0, must-revalidate'
```

### 7. Environment Configuration

#### Development (`.env.development`)
```bash
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

#### Production (`.env.production`)
```bash
VITE_API_URL=https://api.your-domain.com
VITE_WS_URL=wss://api.your-domain.com
```

#### Amplify Environment Variables
Set in AWS Amplify Console:
- `VITE_API_URL` - Your API Gateway URL
- `VITE_WS_URL` - Your WebSocket API URL

## Backend WebSocket Support

Add WebSocket endpoint to FastAPI (`src/api/websocket.py`):

```python
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, goal_id: str):
        await websocket.accept()
        if goal_id not in self.active_connections:
            self.active_connections[goal_id] = set()
        self.active_connections[goal_id].add(websocket)

    def disconnect(self, websocket: WebSocket, goal_id: str):
        self.active_connections.get(goal_id, set()).discard(websocket)

    async def broadcast(self, goal_id: str, message: dict):
        for connection in self.active_connections.get(goal_id, []):
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{goal_id}")
async def websocket_endpoint(websocket: WebSocket, goal_id: str):
    await manager.connect(websocket, goal_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket, goal_id)
```

## Success Criteria

- [ ] React app runs locally with hot reload
- [ ] Dashboard shows real-time statistics
- [ ] Hypothesis list with Elo ratings and sorting
- [ ] Hypothesis detail view with reviews
- [ ] Chat interface working with backend
- [ ] Elo rating chart visualization
- [ ] WebSocket updates for real-time changes
- [ ] AWS Amplify deployment working
- [ ] Environment-specific API URLs
- [ ] Responsive design (mobile-friendly)

## Local Development

```bash
# Start backend
cd src && uvicorn api.main:app --reload

# Start frontend (separate terminal)
cd frontend && npm run dev
```

## Deployment to AWS Amplify

1. Push code to GitHub/GitLab
2. Connect repository in AWS Amplify Console
3. Configure build settings (use `amplify.yml`)
4. Set environment variables
5. Deploy

```bash
# Or use Amplify CLI
amplify init
amplify add hosting
amplify publish
```
