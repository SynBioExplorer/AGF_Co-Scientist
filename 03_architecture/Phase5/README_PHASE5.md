# Phase 5: Frontend UI & Advanced Features

> **Deployment Target: LOCAL ONLY**
>
> This phase is designed for local development and single-user operation.
> No cloud deployment, authentication, or multi-user features are included.
> Run everything on `localhost` - no external hosting required.

## Overview

Phase 5 extends the AI Co-Scientist system with a React frontend, vector storage, literature tools, and LangSmith observability.

**Prerequisites:** Phase 4 complete (Storage, Supervisor, Safety, API)
**Target Environment:** Local development (localhost)

## Phase 5 Components

| Phase | Component | Description | Status |
|-------|-----------|-------------|--------|
| **5A** | Vector Storage | ChromaDB for hypothesis embeddings | Planned |
| **5B** | Literature Tools | PubMed integration for research | Planned |
| **5C** | Literature Processing | PDF parsing, chunking, semantic search | Planned |
| **5D** | Frontend Dashboard | React UI with settings, chat, visualizations | Planned |
| **5F** | Observability | LangSmith tracing integration | Planned |

## Deferred Components

| Phase | Component | Reason |
|-------|-----------|--------|
| **5E** | Authentication | Not needed for MVP |
| **5G** | Deployment | Defer until production needed |

## Recommended Execution Order

```
5A (Vector) → 5F (LangSmith) → 5B (Tools) → 5C (Literature) → 5D (Frontend)
```

**Rationale:**
- 5A enables semantic search for literature and hypotheses
- 5F provides debugging visibility during development
- 5B/5C add literature research capabilities
- 5D ties everything together with the UI

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │  Chat   │ │Hypotheses│ │ Settings│ │Literature│          │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘          │
│       └───────────┴───────────┴───────────┘                │
│                         │                                   │
└─────────────────────────┼───────────────────────────────────┘
                          │ REST API
┌─────────────────────────┼───────────────────────────────────┐
│                    FastAPI Backend                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐          │
│  │ Agents  │ │ Storage │ │  Tools  │ │Literature│          │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘          │
│       │           │           │           │                 │
│       └───────────┴─────┬─────┴───────────┘                │
│                         │                                   │
│              ┌──────────┴──────────┐                       │
│              │     LangSmith       │                       │
│              │   (Tracing/Debug)   │                       │
│              └─────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              │       ChromaDB        │
              │   (Vector Storage)    │
              └───────────────────────┘
```

## Quick Links

- [Phase 5A: Vector Storage](./PHASE5A_VECTOR_STORAGE.md)
- [Phase 5B: Literature Tools](./PHASE5B_TOOL_INTEGRATION.md)
- [Phase 5C: Literature Processing](./PHASE5C_LITERATURE_PROCESSING.md)
- [Phase 5D: Frontend Dashboard](./PHASE5D_FRONTEND_DASHBOARD.md)
- [Phase 5F: Observability (LangSmith)](./PHASE5F_OBSERVABILITY.md)

## Success Criteria

Phase 5 is complete when:

- [ ] ChromaDB storing hypothesis embeddings
- [ ] PubMed search returning relevant literature
- [ ] PDF upload and semantic search working
- [ ] React frontend with chat, settings, visualizations
- [ ] LangSmith traces visible for all LLM calls
- [ ] All tests passing

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + TypeScript + Vite + Tailwind |
| Charts | Recharts |
| State | Zustand + React Query |
| Vector DB | ChromaDB |
| Observability | LangSmith |
| Literature | PubMed API + PyMuPDF |

## How to Run (Local)

```bash
# Terminal 1: Start backend
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend && npm run dev
```

Access at:
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

No Docker, no cloud services, no deployment configuration needed.
