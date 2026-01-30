# Phase 5D Frontend Dashboard - Execution Plan

> **Generated:** 2025-01-29
> **Risk Score:** 286 (HIGH - Requires human review)
> **Project:** AI Co-Scientist Frontend Dashboard

## Overview

This plan decomposes the Phase 5D Frontend Dashboard into 6 parallelizable tasks that build a complete React frontend for the AI Co-Scientist system:

| Task | Description | Files |
|------|-------------|-------|
| task-a | Foundation & Infrastructure | 22 |
| task-b | Settings Panel & Store | 9 |
| task-c | Layout & Navigation | 11 |
| task-d | Chat Interface | 8 |
| task-e | Hypothesis Browser & Visualizations | 13 |
| task-f | Literature Page & PDF Upload | 8 |

**Total Files:** 71 frontend files

## Risk Factors

| Factor | Value | Impact |
|--------|-------|--------|
| Sensitive paths | 3 | `.env` files, API key handling |
| Task count | 6 | Moderate complexity |
| File count | 72 | Large frontend component count |
| Test coverage | 0% | Frontend uses browser-based testing |

**Note:** The high risk score is primarily due to the API key handling in settings (expected for a configuration panel) and the large number of component files. This is typical for a frontend project.

## Execution Waves

The tasks are organized into 2 execution waves based on dependencies:

```
Wave 1 (Sequential - 1 task)
└── task-a (Foundation)
    ├── Project setup (Vite, TypeScript, Tailwind)
    ├── API service layer
    ├── TypeScript types
    ├── Core hooks (usePolling, useApi)
    └── Common UI components

Wave 2 (Parallel - 5 tasks, max 3 concurrent)
├── task-b (Settings)       # Settings panel, Zustand store
├── task-c (Layout)         # App shell, routing, dashboard
├── task-d (Chat)           # Chat interface
├── task-e (Hypotheses)     # Hypothesis browser, visualizations
└── task-f (Literature)     # Literature page, PDF upload
```

## Task Details

### Wave 1: Foundation (Sequential)

#### Task A: Foundation & Infrastructure
**Purpose:** Set up the React project and create shared infrastructure

**Files Created:**
- Project configuration: `package.json`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.js`
- Entry point: `src/main.tsx`, `src/index.css`
- Types: `src/types/index.ts`, `src/types/api.ts`
- API Service: `src/services/api.ts`
- Hooks: `src/hooks/useApi.ts`, `src/hooks/usePolling.ts`
- Common components: `Button`, `Card`, `Loading`, `Select`, `Slider`, `Input`

**Verification:**
```bash
cd frontend && npm install && npm run build
cd frontend && npx tsc --noEmit
```

---

### Wave 2: Feature Tasks (Parallel - max 3 workers)

#### Task B: Settings Panel & Store
**Depends on:** task-a

**Purpose:** Implement settings management with Zustand

**Files Created:**
- Store: `src/store/settingsStore.ts`
- Components: `SettingsPanel`, `ModelSelector`, `ApiKeyInput`, `ParameterSliders`, `FeatureToggles`
- Page: `src/pages/SettingsPage.tsx`
- Hook: `src/hooks/useSettings.ts`

**Settings Schema:**
```typescript
interface Settings {
  llmProvider: 'google' | 'openai';
  model: string;
  googleApiKey: string;
  openaiApiKey: string;
  tavilyApiKey: string;
  temperature: number;        // 0.0 - 1.0
  maxIterations: number;      // 1 - 50
  tournamentRounds: number;   // 1 - 10
  eloKFactor: number;         // 16 - 64
  enableEvolution: boolean;
  enableWebSearch: boolean;
  enableLiteratureSearch: boolean;
}
```

---

#### Task C: Layout & Navigation + App Shell
**Depends on:** task-a

**Purpose:** Create the application shell and routing

**Files Created:**
- Layout: `Header`, `Sidebar`, `Layout`
- App: `src/App.tsx` (React Router setup)
- Dashboard: `src/pages/Dashboard.tsx`
- Dashboard components: `StatCard`, `GoalSelector`, `StatusIndicator`
- Store: `src/store/goalStore.ts`

**Routes:**
- `/` - Dashboard
- `/chat` - Chat interface
- `/hypotheses` - Hypothesis browser
- `/literature` - Literature page
- `/settings` - Settings

---

#### Task D: Chat Interface
**Depends on:** task-a

**Purpose:** Implement chat with AI Co-Scientist

**Files Created:**
- Components: `ChatWindow`, `MessageList`, `MessageInput`, `ChatMessage`, `ContextIndicator`
- Page: `src/pages/ChatPage.tsx`
- Store: `src/store/chatStore.ts`

**API Integration:**
- `POST /api/v1/chat` - Send message
- `GET /api/v1/chat/{goal_id}/history` - Get chat history

---

#### Task E: Hypothesis Browser & Visualizations
**Depends on:** task-a

**Purpose:** Display hypotheses with Elo ratings and charts

**Files Created:**
- Hypothesis components: `HypothesisList`, `HypothesisCard`, `HypothesisDetail`, `FeedbackForm`, `TournamentRecord`
- Visualization components: `EloChart`, `QualityDistribution`, `AgentActivity`
- Page: `src/pages/HypothesesPage.tsx`
- Store: `src/store/hypothesisStore.ts`

**API Integration:**
- `GET /goals/{goal_id}/hypotheses` - List hypotheses
- `GET /hypotheses/{hypothesis_id}` - Hypothesis detail
- `POST /hypotheses/{hypothesis_id}/feedback` - Submit feedback
- `GET /goals/{goal_id}/stats` - Get statistics

---

#### Task F: Literature Page & PDF Upload
**Depends on:** task-a

**Purpose:** Manage private document repository

**Files Created:**
- Components: `PdfUpload`, `DocumentList`, `SearchResults`, `DocumentCard`, `SearchBar`
- Page: `src/pages/LiteraturePage.tsx`
- Store: `src/store/literatureStore.ts`

**API Integration:**
- `POST /api/v1/documents/upload` - Upload PDF
- `GET /api/v1/documents/search` - Search documents
- `GET /api/v1/documents` - List documents

---

## File Ownership Matrix

Each task has exclusive ownership of its files to prevent merge conflicts:

| Task | Owned Directories/Files |
|------|------------------------|
| task-a | `frontend/src/types/*`, `frontend/src/services/*`, `frontend/src/hooks/useApi.ts`, `frontend/src/hooks/usePolling.ts`, `frontend/src/components/common/*`, config files |
| task-b | `frontend/src/store/settingsStore.ts`, `frontend/src/components/settings/*`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/hooks/useSettings.ts` |
| task-c | `frontend/src/App.tsx`, `frontend/src/components/layout/*`, `frontend/src/components/dashboard/*`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/store/goalStore.ts` |
| task-d | `frontend/src/components/chat/*`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/store/chatStore.ts` |
| task-e | `frontend/src/components/hypotheses/*`, `frontend/src/components/visualizations/*`, `frontend/src/pages/HypothesesPage.tsx`, `frontend/src/store/hypothesisStore.ts` |
| task-f | `frontend/src/components/literature/*`, `frontend/src/pages/LiteraturePage.tsx`, `frontend/src/store/literatureStore.ts` |

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18.x | UI framework |
| TypeScript | 5.x | Type safety |
| Vite | 5.x | Build tool |
| Tailwind CSS | 3.x | Styling |
| Zustand | 4.x | State management |
| React Query | 5.x | Data fetching |
| React Router | 6.x | Routing |
| Recharts | 2.x | Visualizations |
| Axios | 1.x | HTTP client |

## Verification Commands

### Task A (Foundation)
```bash
cd frontend && npm install && npm run build
cd frontend && npx tsc --noEmit
```

### Tasks B-F (Features)
```bash
cd frontend && npx tsc --noEmit
cd frontend && npm run build
```

### Final Integration
```bash
# Terminal 1: Start backend
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend && npm run dev
```

## Integration with App.tsx

Task C (Layout) creates the `App.tsx` file with routes for all pages. The imports are:

```tsx
import { Dashboard } from './pages/Dashboard';
import { ChatPage } from './pages/ChatPage';
import { HypothesesPage } from './pages/HypothesesPage';
import { LiteraturePage } from './pages/LiteraturePage';
import { SettingsPage } from './pages/SettingsPage';
```

Since each page is in a separate file owned by its respective task, there are no merge conflicts.

## Success Criteria

From the Phase 5D specification:

- [ ] React app builds and runs locally
- [ ] Settings panel with model/parameter controls
- [ ] Chat interface sending/receiving messages
- [ ] Hypothesis list with Elo ratings and sorting
- [ ] Hypothesis detail view with reviews
- [ ] Elo chart visualization working
- [ ] Statistics dashboard displaying metrics
- [ ] Polling updates goal status
- [ ] Settings persist in localStorage

## How to Execute

### Option 1: Parallel Worktrees with Supervisor (Recommended)

The Supervisor agent will:
1. Create git worktree for task-a
2. Execute task-a, verify, merge to main
3. Create 5 worktrees for tasks b-f (or 3 at a time based on worker limit)
4. Execute in parallel using tmux sessions
5. Verify each task completes successfully
6. Merge all tasks to main
7. Run final integration verification

### Option 2: Manual Sequential Execution

Execute tasks in order:
1. task-a (Foundation)
2. task-b through task-f (any order, but after task-a)

## Approval Required

**Risk Score: 286 (HIGH)**

The risk is elevated due to:
- API key handling in settings (expected and intentional)
- Large number of files (typical for React projects)
- No automated tests (frontend testing typically done with browser-based tools)

Before proceeding with execution:
1. Review the task decomposition above
2. Confirm file ownership boundaries are acceptable
3. Approve the execution plan

**Proceed with execution? [Y/n]**