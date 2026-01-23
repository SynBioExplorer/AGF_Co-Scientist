# Phase 4: Quick Setup Guide

## Overview

This guide walks you through setting up **4 parallel git worktrees** and spawning **4 Claude Code instances** to build Phase 4 simultaneously.

**Estimated Time**: 5 weeks total (4 weeks parallel + 1 week integration)
**Budget**: ~$10 AUD for development/testing

---

## Prerequisites

- Git repository with Phases 1-3 complete
- Conda environment (`coscientist`) set up
- Claude Code installed in all terminals/workspaces

---

## Step-by-Step Setup

### 1. Create Branches and Worktrees (5 minutes)

Run from your main repository:

```bash
# Navigate to main repo
cd "/Users/felix/Library/CloudStorage/OneDrive-SharedLibraries-MacquarieUniversity/Australian Genome Foundry - AWS cloud infrastructure/12_AI_Co-scientist/Google co-scientist"

# Ensure you're on main and up to date
git checkout main
git pull origin main

# Create branches for each component
git branch phase4/database
git branch phase4/supervisor
git branch phase4/safety
git branch phase4/api

# Create worktrees (one level up from repo)
git worktree add ../worktree-database phase4/database
git worktree add ../worktree-supervisor phase4/supervisor
git worktree add ../worktree-safety phase4/safety
git worktree add ../worktree-api phase4/api

# Verify worktrees created
git worktree list
```

You should see:
```
/Users/.../Google co-scientist            main
/Users/.../worktree-database              phase4/database
/Users/.../worktree-supervisor            phase4/supervisor
/Users/.../worktree-safety                phase4/safety
/Users/.../worktree-api                   phase4/api
```

### 2. Copy Instruction Files (2 minutes)

```bash
# Copy instruction files to each worktree
cp PHASE4_AGENT_DATABASE.md ../worktree-database/
cp PHASE4_AGENT_SUPERVISOR.md ../worktree-supervisor/
cp PHASE4_AGENT_SAFETY.md ../worktree-safety/
cp PHASE4_AGENT_API.md ../worktree-api/

# Copy the main plan for reference
cp /Users/felix/.claude/plans/memoized-booping-allen.md ../worktree-database/PHASE4_PLAN.md
cp /Users/felix/.claude/plans/memoized-booping-allen.md ../worktree-supervisor/PHASE4_PLAN.md
cp /Users/felix/.claude/plans/memoized-booping-allen.md ../worktree-safety/PHASE4_PLAN.md
cp /Users/felix/.claude/plans/memoized-booping-allen.md ../worktree-api/PHASE4_PLAN.md
```

### 3. Spawn Claude Code Instances (5 minutes)

Open **4 terminal windows/tabs**:

**Terminal 1 - Database Agent**:
```bash
cd ../worktree-database
conda activate coscientist
code .  # Opens VSCode (or use your IDE)
```

**Terminal 2 - Supervisor Agent**:
```bash
cd ../worktree-supervisor
conda activate coscientist
code .
```

**Terminal 3 - Safety Agent**:
```bash
cd ../worktree-safety
conda activate coscientist
code .
```

**Terminal 4 - API Agent**:
```bash
cd ../worktree-api
conda activate coscientist
code .
```

### 4. Initial Prompt for Each Claude Instance

In each VSCode/IDE window, start Claude Code and provide this initial prompt:

**Database Agent** (Terminal 1):
```
I'm working on Phase 4 of the AI Co-Scientist project as the Database Agent.

Please read the instruction file PHASE4_AGENT_DATABASE.md in this worktree and begin implementing the database layer.

My mission: Build the PostgreSQL + Redis storage abstraction layer.
Timeline: Week 1 (7 days)
Priority: HIGHEST - publish BaseStorage interface by Day 1

Start by reading PHASE4_AGENT_DATABASE.md and confirming you understand the task.
```

**Supervisor Agent** (Terminal 2):
```
I'm working on Phase 4 of the AI Co-Scientist project as the Supervisor Agent.

Please read the instruction file PHASE4_AGENT_SUPERVISOR.md in this worktree.

My mission: Build the task orchestration and supervisor agent.
Timeline: Week 2 (7 days)
Dependencies: Waiting for BaseStorage interface from Database Agent (will use mock initially)

Start by reading PHASE4_AGENT_SUPERVISOR.md and confirming you understand the task.
```

**Safety Agent** (Terminal 3):
```
I'm working on Phase 4 of the AI Co-Scientist project as the Safety Agent.

Please read the instruction file PHASE4_AGENT_SAFETY.md in this worktree.

My mission: Build safety review and checkpoint/resume functionality.
Timeline: Week 3 (7 days)
Dependencies: Database and Supervisor agents (will start once they merge to main)

Start by reading PHASE4_AGENT_SAFETY.md and confirming you understand the task. You can begin planning but wait for dependencies before implementing.
```

**API Agent** (Terminal 4):
```
I'm working on Phase 4 of the AI Co-Scientist project as the API Agent.

Please read the instruction file PHASE4_AGENT_API.md in this worktree.

My mission: Build the FastAPI web interface.
Timeline: Week 4 (7 days)
Dependencies: All other agents (Database, Supervisor, Safety)

Start by reading PHASE4_AGENT_API.md and confirming you understand the task. You can begin planning and scaffolding but wait for dependencies before full implementation.
```

---

## Development Timeline

### Week 1: Database Agent Works Solo

**Database Agent**:
- ✅ Day 1: Install deps, create `schema.sql`, **publish `BaseStorage` interface**
- ✅ Day 2: Refactor `InMemoryStorage` to inherit from `BaseStorage`
- ✅ Day 3-4: Implement `PostgreSQLStorage` (all 30+ methods)
- ✅ Day 5: Add Redis caching, storage factory
- ✅ Day 6-7: Tests, commit, push

**Supervisor/Safety/API Agents**: Planning and preparation

### Week 2: Supervisor Agent Joins

**Database Agent**: Merges to main at start of week

**Supervisor Agent**:
- ✅ Day 1: Rebase on main (get database code), implement task queue
- ✅ Day 2-3: Implement statistics tracker
- ✅ Day 3-5: Implement supervisor agent orchestration
- ✅ Day 6-7: Tests, commit, push

**Safety/API Agents**: Continued planning

### Week 3: Safety Agent Joins

**Supervisor Agent**: Merges to main at start of week

**Safety Agent**:
- ✅ Day 1: Rebase on main (get database + supervisor)
- ✅ Day 1-3: Implement safety review agent
- ✅ Day 4-5: Implement checkpoint/resume system
- ✅ Day 6-7: Tests, commit, push

**API Agent**: Scaffolding and planning

### Week 4: API Agent Completes

**Safety Agent**: Merges to main at start of week

**API Agent**:
- ✅ Day 1: Rebase on main (get all previous work)
- ✅ Day 2-3: Implement background tasks and core endpoints
- ✅ Day 4-5: Implement chat interface and remaining endpoints
- ✅ Day 6-7: Tests, documentation, commit, push

### Week 5: Integration & Testing

**All Agents**: Merge complete, integration testing

---

## Merging Strategy

Merge in dependency order:

```bash
# Week 1 End - Merge Database
git checkout main
git merge phase4/database
git push origin main

# Week 2 End - Merge Supervisor
git checkout main
git merge phase4/supervisor
git push origin main

# Week 3 End - Merge Safety
git checkout main
git merge phase4/safety
git push origin main

# Week 4 End - Merge API
git checkout main
git merge phase4/api
git push origin main

# Week 5 - Integration Testing
python test_phase4.py
```

---

## Communication Protocol

### Option 1: Shared Status File

Each agent updates `PHASE4_STATUS.md` daily:

```bash
# In each worktree, create status file
touch PHASE4_STATUS.md

# Update with your progress
# Example format:
## Database Agent (phase4/database)
- **Status**: Day 3/7 - 50% complete
- **Completed**: schema.sql, base.py, postgres.py (partial)
- **Blocked**: None
- **Notes**: BaseStorage interface published Day 1 ✓
```

### Option 2: Git Commit Messages

Use descriptive commit messages with day markers:

```bash
git commit -m "feat(database): [Day 1] publish BaseStorage interface"
git commit -m "feat(supervisor): [Day 2] implement task queue"
```

---

## Conflict Resolution

### Likely Conflicts

1. **src/config.py** - Multiple agents add settings
   - **Resolution**: Merge manually, keep all settings

2. **03_architecture/environment.yml** - Dependency additions
   - **Resolution**: Combine all dependencies

3. **CLAUDE.md** - Documentation updates
   - **Resolution**: Each agent has their own section

### How to Resolve

```bash
# If conflicts during merge:
git status  # See conflicted files
# Edit files to resolve conflicts
git add <resolved-files>
git commit -m "Merge phase4/[component]: resolved conflicts"
```

---

## Monitoring Progress

### Database Agent Progress

```bash
# Check if BaseStorage published
ls ../worktree-database/src/storage/base.py
```

### Supervisor Agent Progress

```bash
# Check if using database interface
grep "BaseStorage" ../worktree-supervisor/src/agents/supervisor.py
```

### Overall Progress

```bash
# List all worktrees and branches
git worktree list

# Check commit history on each branch
git log phase4/database --oneline
git log phase4/supervisor --oneline
git log phase4/safety --oneline
git log phase4/api --oneline
```

---

## Troubleshooting

### Issue: Worktree won't create

**Solution**: Remove any existing worktrees first:
```bash
git worktree remove ../worktree-database --force
```

### Issue: Agent can't find BaseStorage

**Solution**: Check if database agent has committed and pushed:
```bash
cd ../worktree-database
git log --oneline  # Should see "publish BaseStorage interface"
```

### Issue: Conda environment not found

**Solution**: Activate in each worktree:
```bash
conda activate coscientist
```

### Issue: Import errors across worktrees

**Solution**: Each worktree is independent - imports should work within each worktree. If not, check Python path.

---

## Cleanup After Phase 4

Once all branches merged and tested:

```bash
# Remove worktrees
git worktree remove ../worktree-database
git worktree remove ../worktree-supervisor
git worktree remove ../worktree-safety
git worktree remove ../worktree-api

# Optionally delete branches (or keep for history)
git branch -d phase4/database
git branch -d phase4/supervisor
git branch -d phase4/safety
git branch -d phase4/api
```

---

## Success Criteria

**Phase 4 Complete When**:

1. ✅ All 4 branches merged to main
2. ✅ `test_phase4.py` passes
3. ✅ Database stores all data models
4. ✅ Supervisor orchestrates agents
5. ✅ Safety reviews goals/hypotheses
6. ✅ Checkpoints save/restore state
7. ✅ FastAPI serves 8+ endpoints
8. ✅ Chat interface works
9. ✅ Full end-to-end workflow functional

---

## Next Steps

After Phase 4:
- **Phase 5**: Vector storage, advanced visualization, multi-user support
- **Production Deployment**: Docker, Kubernetes, monitoring
- **Scientific Validation**: Test with real research goals

---

**Ready to begin!** Follow the setup steps above and let the parallel development commence! 🚀
