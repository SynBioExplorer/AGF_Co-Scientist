# Phase 5: Parallel Workflow Guide

## Overview

This guide explains how to use git worktrees and tmux to develop Phase 5 components in parallel, following the same pattern established in Phase 4.

## Prerequisites

- tmux installed (`tmux -V` should show 3.x)
- Git 2.x+ with worktree support
- Phase 4 complete and merged to main

## Setup Git Worktrees

### 1. Create Worktree Directory Structure

```bash
# From the main repository root
cd "/Users/felix/Library/CloudStorage/OneDrive-SharedLibraries-MacquarieUniversity/Australian Genome Foundry - AWS cloud infrastructure/12_AI_Co-scientist/Google co-scientist"

# Create worktrees for each Phase 5 component
git worktree add ../worktree-5a-vector phase5/vector -b phase5/vector
git worktree add ../worktree-5b-tools phase5/tools -b phase5/tools
git worktree add ../worktree-5c-literature phase5/literature -b phase5/literature
git worktree add ../worktree-5d-frontend phase5/frontend -b phase5/frontend
git worktree add ../worktree-5e-auth phase5/auth -b phase5/auth
git worktree add ../worktree-5f-observability phase5/observability -b phase5/observability
git worktree add ../worktree-5g-deployment phase5/deployment -b phase5/deployment
```

### 2. Verify Worktrees

```bash
git worktree list
```

Expected output:
```
/path/to/Google co-scientist           abc1234 [main]
/path/to/worktree-5a-vector            def5678 [phase5/vector]
/path/to/worktree-5b-tools             ghi9012 [phase5/tools]
/path/to/worktree-5c-literature        jkl3456 [phase5/literature]
/path/to/worktree-5d-frontend          mno7890 [phase5/frontend]
/path/to/worktree-5e-auth              pqr1234 [phase5/auth]
/path/to/worktree-5f-observability     stu5678 [phase5/observability]
/path/to/worktree-5g-deployment        vwx9012 [phase5/deployment]
```

## tmux Session Setup

### 1. Create tmux Session with Panes

```bash
# Create new tmux session named "phase5"
tmux new-session -d -s phase5 -n orchestrator

# Create windows for each agent
tmux new-window -t phase5 -n 5a-vector
tmux new-window -t phase5 -n 5b-tools
tmux new-window -t phase5 -n 5c-literature
tmux new-window -t phase5 -n 5d-frontend
tmux new-window -t phase5 -n 5e-auth
tmux new-window -t phase5 -n 5f-observability
tmux new-window -t phase5 -n 5g-deployment

# Navigate each window to its worktree
tmux send-keys -t phase5:5a-vector "cd ../worktree-5a-vector && conda activate coscientist" Enter
tmux send-keys -t phase5:5b-tools "cd ../worktree-5b-tools && conda activate coscientist" Enter
tmux send-keys -t phase5:5c-literature "cd ../worktree-5c-literature && conda activate coscientist" Enter
tmux send-keys -t phase5:5d-frontend "cd ../worktree-5d-frontend && conda activate coscientist" Enter
tmux send-keys -t phase5:5e-auth "cd ../worktree-5e-auth && conda activate coscientist" Enter
tmux send-keys -t phase5:5f-observability "cd ../worktree-5f-observability && conda activate coscientist" Enter
tmux send-keys -t phase5:5g-deployment "cd ../worktree-5g-deployment && conda activate coscientist" Enter

# Attach to session
tmux attach -t phase5
```

### 2. tmux Quick Reference

| Command | Action |
|---------|--------|
| `Ctrl-b c` | Create new window |
| `Ctrl-b n` | Next window |
| `Ctrl-b p` | Previous window |
| `Ctrl-b 0-9` | Switch to window N |
| `Ctrl-b d` | Detach from session |
| `Ctrl-b %` | Split pane vertically |
| `Ctrl-b "` | Split pane horizontally |
| `Ctrl-b o` | Switch pane |

## Orchestration Agent

The orchestrator window (window 0) runs the coordination agent that:

1. Monitors progress across all worktrees
2. Handles cross-component dependencies
3. Coordinates merge order
4. Runs integration tests

### Orchestrator Script

```bash
#!/bin/bash
# phase5_orchestrator.sh

WORKTREES=(
    "worktree-5a-vector"
    "worktree-5b-tools"
    "worktree-5c-literature"
    "worktree-5d-frontend"
    "worktree-5e-auth"
    "worktree-5f-observability"
    "worktree-5g-deployment"
)

check_status() {
    echo "=== Phase 5 Status ==="
    for wt in "${WORKTREES[@]}"; do
        if [ -d "../$wt" ]; then
            cd "../$wt"
            branch=$(git branch --show-current)
            commits=$(git rev-list --count main..HEAD 2>/dev/null || echo "0")
            echo "$wt: $branch (+$commits commits)"
            cd - > /dev/null
        fi
    done
}

check_status
```

## Agent Responsibilities

### 5A Vector Agent
- Implement ChromaDB/pgvector integration
- Create embedding generation for hypotheses
- Update Proximity agent to use vector similarity
- Write `test_vector.py`

### 5B Tools Agent
- Implement tool interface abstraction
- Integrate PubMed, DrugBank, ChEMBL APIs
- Add AlphaFold structure prediction
- Write `test_tools.py`

### 5C Literature Agent
- Implement PDF parsing (PyMuPDF/pdfplumber)
- Build citation graph extraction
- Create private repository indexing
- Write `test_literature.py`

### 5D Frontend Agent
- Set up React/Vue project
- Implement dashboard components
- Add real-time WebSocket updates
- Write frontend tests

### 5E Auth Agent
- Implement OAuth2/JWT authentication
- Create user/workspace models
- Add RBAC middleware
- Write `test_auth.py`

### 5F Observability Agent
- Add Prometheus metrics endpoint
- Create Grafana dashboards
- Set up alerting rules
- Write `test_metrics.py`

### 5G Deployment Agent
- Create Dockerfile
- Write docker-compose.yml
- Create Kubernetes manifests
- Set up CI/CD pipeline

## Communication Protocol

### Daily Sync

Each agent commits with descriptive messages:
```bash
git commit -m "[5A] Add ChromaDB client wrapper"
git commit -m "[5B] Implement PubMed API integration"
```

### Dependency Signals

When a component is ready for dependent work:
```bash
# In worktree-5a-vector
echo "READY" > .status
git add .status && git commit -m "[5A] Vector storage ready for 5C integration"
git push origin phase5/vector
```

### Integration Testing

Before merge, run cross-component tests:
```bash
# From main repo
git fetch --all
git checkout main
git merge phase5/vector --no-commit
python -m pytest test_integration.py
```

## Merge Workflow

### 1. Merge 5A (Vector Storage)
```bash
git checkout main
git merge phase5/vector
git push origin main
```

### 2. Rebase 5C on updated main
```bash
cd ../worktree-5c-literature
git fetch origin
git rebase origin/main
```

### 3. Continue with remaining merges in order

## Cleanup

After Phase 5 complete:
```bash
# Remove worktrees
git worktree remove ../worktree-5a-vector
git worktree remove ../worktree-5b-tools
git worktree remove ../worktree-5c-literature
git worktree remove ../worktree-5d-frontend
git worktree remove ../worktree-5e-auth
git worktree remove ../worktree-5f-observability
git worktree remove ../worktree-5g-deployment

# Delete branches (optional)
git branch -d phase5/vector phase5/tools phase5/literature phase5/frontend phase5/auth phase5/observability phase5/deployment
```

## Troubleshooting

### Worktree conflicts
```bash
git worktree repair
```

### Detached HEAD in worktree
```bash
git checkout phase5/vector
```

### tmux session lost
```bash
tmux ls                    # List sessions
tmux attach -t phase5      # Reattach
```
