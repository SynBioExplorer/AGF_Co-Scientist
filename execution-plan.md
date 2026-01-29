# Phase 5 Execution Plan

> **Generated:** 2025-01-29
> **Risk Score:** 296 (HIGH - Requires human review before proceeding)

## Overview

This plan decomposes Phase 5 of the AI Co-Scientist project into 7 parallelizable tasks that build:
- Vector storage with ChromaDB for fast hypothesis similarity
- LangSmith observability for LLM tracing
- PubMed tool integration for literature research
- PDF literature processing with semantic search
- Settings API for runtime configuration
- React frontend dashboard
- Final integration and testing

## Risk Factors

| Factor | Value | Impact |
|--------|-------|--------|
| Sensitive paths | 2 | `.env` file, API key handling |
| Task count | 7 | Moderate complexity |
| File count | 73 | Large frontend component count |
| Hot files | 9 | Multiple config patches needed |
| Contracts | 6 | Interface dependencies |
| Test coverage | 86% | Some files lack explicit tests |

## Execution Waves

The tasks are organized into 4 execution waves based on dependencies:

```
Wave 1 (Parallel - 4 tasks)
├── task-vector-storage    # Embeddings & ChromaDB
├── task-observability     # LangSmith tracing
├── task-settings-api      # Settings endpoints
└── task-tool-integration  # PubMed tool

Wave 2 (Sequential)
└── task-literature-processing  # Depends on vector storage

Wave 3 (Sequential)
└── task-frontend              # Depends on all API tasks

Wave 4 (Sequential)
└── task-integration           # Final integration, depends on all
```

## Task Details

### Wave 1: Foundation Tasks (Parallel)

#### Task 1: Vector Storage (task-vector-storage)
**Purpose:** Enable fast semantic similarity for hypothesis clustering

**New Modules:**
- `src/embeddings/` - Embedding client abstraction with Google/OpenAI implementations
- `src/storage/vector.py` - ChromaDB vector store

**Config Changes:**
- Add `vector_store_type`, `embedding_provider` to Settings
- Add embedding model configuration

**Test File:** `05_tests/phase5_vector_test.py`

---

#### Task 2: Observability (task-observability)
**Purpose:** Add LangSmith tracing for debugging and cost monitoring

**New Modules:**
- `src/observability/tracing.py` - Tracing utilities, decorators

**Patches:**
- `src/llm/base.py` - Add callbacks property
- `src/llm/google.py` - Add tracing to LLM calls
- `src/llm/openai.py` - Add tracing to LLM calls

**Test File:** `05_tests/phase5_tracing_test.py`

---

#### Task 3: Settings API (task-settings-api)
**Purpose:** Enable runtime configuration from frontend

**New Files:**
- `src/api/settings.py` - Settings router

**Test File:** `05_tests/phase5_settings_test.py`

---

#### Task 4: Tool Integration (task-tool-integration)
**Purpose:** Add PubMed literature search capability

**New Modules:**
- `src/tools/base.py` - Tool interface
- `src/tools/registry.py` - Tool registry
- `src/tools/pubmed.py` - PubMed API client
- `src/api/tools.py` - Tools router

**Config Changes:**
- Add `pubmed_api_key`, `tool_timeout_seconds`

**Test File:** `05_tests/phase5_tools_test.py`

---

### Wave 2: Literature Processing

#### Task 5: Literature Processing (task-literature-processing)
**Depends on:** task-vector-storage

**Purpose:** Enable PDF upload, parsing, and semantic search

**New Modules:**
- `src/literature/pdf_parser.py` - PyMuPDF-based parser
- `src/literature/chunker.py` - Text chunking
- `src/literature/citation_extractor.py` - Citation parsing
- `src/literature/citation_graph.py` - Citation networks
- `src/literature/repository.py` - Private document repository
- `src/api/documents.py` - Documents router

**Test File:** `05_tests/phase5_literature_test.py`

---

### Wave 3: Frontend

#### Task 6: Frontend Dashboard (task-frontend)
**Depends on:** task-settings-api, task-tool-integration, task-literature-processing

**Purpose:** Build React UI for scientist interaction

**New Module:** `frontend/`
- Vite + React + TypeScript + Tailwind
- 45+ component files
- Chat, hypotheses, literature, settings pages
- Zustand state management
- React Query for data fetching

**Verification:** `npm install && npm run build`

---

### Wave 4: Integration

#### Task 7: Integration (task-integration)
**Depends on:** All previous tasks

**Purpose:** Wire everything together, final testing

**Actions:**
- Register all new routers in `src/api/main.py`
- Update `environment.yml` with new dependencies
- Update Phase 5 status documentation

**Test File:** `05_tests/phase5_integration_test.py`

## Interface Contracts

The following contracts define interfaces between tasks:

| Contract | File | Consumers |
|----------|------|-----------|
| EmbeddingClientProtocol | `contracts/embedding_interface.py` | vector-storage, literature |
| VectorStoreProtocol | `contracts/vector_store_interface.py` | vector-storage, literature |
| ToolProtocol | `contracts/tool_interface.py` | tool-integration |
| TracingProtocol | `contracts/tracing_interface.py` | observability |
| LiteratureProtocols | `contracts/literature_interface.py` | literature |
| APIContracts | `contracts/api_interface.py` | all API tasks |

## New Dependencies

Add to `03_architecture/environment.yml`:
```yaml
- chromadb>=0.4.0      # Vector storage
- pymupdf>=1.23.0      # PDF parsing
- langsmith>=0.1.0     # Observability
- aiofiles>=23.0.0     # Async file operations
```

## Verification Commands

Each task includes verification commands:

```bash
# Vector Storage
python -c 'from src.embeddings.base import BaseEmbeddingClient; print("OK")'
python -c 'from src.storage.vector import ChromaVectorStore; print("OK")'
python 05_tests/phase5_vector_test.py

# Observability
python -c 'from src.observability.tracing import get_tracer, LANGSMITH_ENABLED; print("OK")'
python 05_tests/phase5_tracing_test.py

# Tools
python -c 'from src.tools.pubmed import PubMedTool; print("OK")'
python 05_tests/phase5_tools_test.py

# Literature
python -c 'from src.literature.pdf_parser import PDFParser; print("OK")'
python 05_tests/phase5_literature_test.py

# Settings
python -c 'from src.api.settings import router; print("OK")'
python 05_tests/phase5_settings_test.py

# Frontend
cd frontend && npm install && npm run build

# Integration
python 05_tests/phase5_integration_test.py
```

## Sensitive Files

The following files contain or handle sensitive data:
- `frontend/.env` - API URL configuration
- `frontend/src/components/settings/ApiKeyInput.tsx` - API key input (stored in localStorage)

**Security Note:** API keys are stored in browser localStorage, not sent to backend except in request headers for LLM calls.

## How to Execute

### Option 1: Parallel Worktrees (Recommended)

```bash
# Create worktrees for Wave 1 tasks
git worktree add ../worktree-vector phase5/vector
git worktree add ../worktree-observability phase5/observability
git worktree add ../worktree-settings phase5/settings
git worktree add ../worktree-tools phase5/tools

# Run Wave 1 in parallel (4 terminals)
# ... implement each task in its worktree ...

# Merge Wave 1, then continue with Wave 2, etc.
```

### Option 2: Sequential Execution

Execute tasks in order:
1. task-vector-storage
2. task-observability
3. task-settings-api
4. task-tool-integration
5. task-literature-processing
6. task-frontend
7. task-integration

## Approval Required

**Risk Score: 296 (HIGH)**

Before proceeding with execution:
1. Review the task decomposition above
2. Confirm contract interfaces are acceptable
3. Approve the execution plan

**Proceed with execution? [Y/n]**
