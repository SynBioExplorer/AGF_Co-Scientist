# Phase 4 Parallel Development Workflow

## Overview

This guide explains how to parallelize Phase 4 development using **git worktrees** and multiple **Claude Code instances**. Each worktree handles one independent component, allowing 4 parallel development streams.

---

## Git Worktree Strategy

### Why Worktrees?

- **Parallel Development**: 4 Claude instances work simultaneously on different branches
- **Isolation**: Each component developed in isolation, preventing conflicts
- **Easy Integration**: Merge branches back to main sequentially
- **No Context Switching**: Each Claude instance maintains focus on one task

### Worktree Structure

```
main-repo/                          # Main working directory (coordination)
├── worktree-database/              # Worktree 1: Database layer
├── worktree-supervisor/            # Worktree 2: Supervisor agent
├── worktree-safety/                # Worktree 3: Safety & checkpoints
└── worktree-api/                   # Worktree 4: FastAPI interface
```

---

## Setup Instructions

### Step 1: Create Branches and Worktrees

Run these commands from the main repository:

```bash
# Ensure you're on main and up to date
git checkout main
git pull origin main

# Create branches for each component
git branch phase4/database
git branch phase4/supervisor
git branch phase4/safety
git branch phase4/api

# Create worktrees (relative paths from repo root)
git worktree add ../worktree-database phase4/database
git worktree add ../worktree-supervisor phase4/supervisor
git worktree add ../worktree-safety phase4/safety
git worktree add ../worktree-api phase4/api

# Verify worktrees created
git worktree list
```

### Step 2: Set Up Conda Environment in Each Worktree

Each worktree needs the conda environment activated:

```bash
# In each worktree directory
cd ../worktree-database
conda activate coscientist

cd ../worktree-supervisor
conda activate coscientist

cd ../worktree-safety
conda activate coscientist

cd ../worktree-api
conda activate coscientist
```

### Step 3: Copy Instructions to Each Worktree

Copy the relevant instruction file to each worktree (created below):

```bash
cp PHASE4_AGENT_DATABASE.md ../worktree-database/
cp PHASE4_AGENT_SUPERVISOR.md ../worktree-supervisor/
cp PHASE4_AGENT_SAFETY.md ../worktree-safety/
cp PHASE4_AGENT_API.md ../worktree-api/
```

---

## Development Workflow

### Phase 1: Parallel Development (Weeks 1-4)

**Spawn 4 Claude Code instances** (in separate terminal windows/tabs):

```bash
# Terminal 1 - Database Agent
cd ../worktree-database
code .  # Or your preferred editor/IDE

# Terminal 2 - Supervisor Agent
cd ../worktree-supervisor
code .

# Terminal 3 - Safety Agent
cd ../worktree-safety
code .

# Terminal 4 - API Agent
cd ../worktree-api
code .
```

**Each Claude instance**:
1. Reads its instruction file (PHASE4_AGENT_*.md)
2. Implements assigned components
3. Runs tests locally
4. Commits to its branch regularly
5. Pushes branch when complete

### Phase 2: Sequential Integration (Week 5)

**Integration Order** (dependencies):

1. **Database First** (no dependencies)
   ```bash
   git checkout main
   git merge phase4/database
   git push origin main
   ```

2. **Supervisor Second** (depends on database)
   ```bash
   git checkout phase4/supervisor
   git rebase main  # Get database changes
   # Resolve any conflicts
   git checkout main
   git merge phase4/supervisor
   git push origin main
   ```

3. **Safety Third** (depends on database + supervisor)
   ```bash
   git checkout phase4/safety
   git rebase main  # Get database + supervisor
   git checkout main
   git merge phase4/safety
   git push origin main
   ```

4. **API Last** (depends on all)
   ```bash
   git checkout phase4/api
   git rebase main  # Get all previous work
   git checkout main
   git merge phase4/api
   git push origin main
   ```

### Phase 3: End-to-End Testing

After all merges:
```bash
cd main-repo/
python test_phase4.py
```

---

## Agent Instructions (Summary)

### Agent 1: Database Layer
- **Branch**: `phase4/database`
- **Files**: `src/storage/base.py`, `src/storage/postgres.py`, `src/storage/cache.py`, `src/storage/factory.py`, `src/storage/schema.sql`, `scripts/migrate_db.py`
- **Dependencies**: None (standalone)
- **Deliverables**: Complete database abstraction, PostgreSQL implementation, Redis cache, migration script
- **Tests**: Database CRUD operations, connection pooling, JSONB serialization

### Agent 2: Supervisor Agent
- **Branch**: `phase4/supervisor`
- **Files**: `src/supervisor/task_queue.py`, `src/supervisor/statistics.py`, `src/agents/supervisor.py`
- **Dependencies**: Requires `BaseStorage` interface (from database branch)
- **Deliverables**: Task queue, statistics tracker, supervisor orchestration loop
- **Tests**: Task prioritization, weight adjustment, terminal conditions

### Agent 3: Safety & Checkpoints
- **Branch**: `phase4/safety`
- **Files**: `src/agents/safety.py`, `src/supervisor/checkpoint.py`
- **Dependencies**: Requires storage and supervisor interfaces
- **Deliverables**: Safety review agent, checkpoint manager
- **Tests**: Safety scoring, checkpoint save/restore

### Agent 4: FastAPI Interface
- **Branch**: `phase4/api`
- **Files**: `src/api/main.py`, `src/api/chat.py`
- **Dependencies**: Requires all previous components
- **Deliverables**: REST API endpoints, chat interface
- **Tests**: API endpoint responses, chat functionality

---

## Communication Protocol

### Daily Sync (Optional)

Create a shared document (e.g., `PHASE4_STATUS.md`) that each agent updates:

```markdown
# Phase 4 Development Status

## Database Agent (phase4/database)
- **Status**: In Progress (Day 3/7)
- **Completed**: schema.sql, base.py, postgres.py (50%)
- **Blocked**: None
- **Notes**: Working on async connection pooling

## Supervisor Agent (phase4/supervisor)
- **Status**: In Progress (Day 2/7)
- **Completed**: task_queue.py
- **Blocked**: Waiting for BaseStorage interface definition
- **Notes**: Using mock storage for now

## Safety Agent (phase4/safety)
- **Status**: Not Started
- **Completed**: N/A
- **Blocked**: Waiting for database + supervisor
- **Notes**: Reviewed plan, ready to start when dependencies merge

## API Agent (phase4/api)
- **Status**: Not Started
- **Completed**: N/A
- **Blocked**: Waiting for all dependencies
- **Notes**: Preparing FastAPI project structure
```

### Interface Contracts

To minimize integration conflicts, each agent should:

1. **Database Agent**: Publish `BaseStorage` interface early (Day 1)
2. **Supervisor Agent**: Use mock storage initially, swap after merge
3. **Safety Agent**: Define safety review schema early
4. **API Agent**: Mock all dependencies initially

---

## Dependency Management

### Shared Dependencies (Install in All Worktrees)

```bash
# In each worktree
conda activate coscientist
conda install -c conda-forge asyncpg redis-py fastapi uvicorn python-multipart
```

### Environment Consistency

Each worktree should use the **same conda environment** to avoid conflicts:

```bash
# Verify environment
conda env export > environment-snapshot.yml
# Compare across worktrees
```

---

## Conflict Resolution Strategy

### Minimal Conflicts Expected

Since components are isolated, conflicts should be rare. Common conflict areas:

1. **src/config.py** - Multiple agents may add settings
   - **Solution**: Each agent uses unique setting names (e.g., `database_url`, `api_port`)

2. **03_architecture/environment.yml** - Dependency additions
   - **Solution**: Merge manually, keep all dependencies

3. **CLAUDE.md** - Documentation updates
   - **Solution**: Each agent updates their own section

### Conflict Resolution Process

If conflicts occur during merge:

```bash
# Example: Merging supervisor after database
git checkout main
git merge phase4/supervisor

# If conflicts:
git status  # See conflicted files
# Manually edit conflicted files
git add <resolved-files>
git commit -m "Merge phase4/supervisor: resolved conflicts in config.py"
```

---

## Cleanup After Phase 4

Once all branches merged and tested:

```bash
# Remove worktrees
git worktree remove ../worktree-database
git worktree remove ../worktree-supervisor
git worktree remove ../worktree-safety
git worktree remove ../worktree-api

# Delete branches (optional, keep for history)
git branch -d phase4/database
git branch -d phase4/supervisor
git branch -d phase4/safety
git branch -d phase4/api
```

---

## Benefits of This Approach

1. **Speed**: 4x parallelization for independent work
2. **Focus**: Each Claude instance has a single, clear task
3. **Quality**: Isolated testing reduces integration bugs
4. **Safety**: No risk of overwriting each other's work
5. **Rollback**: Easy to discard a branch if needed

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Interface changes after database merge | Supervisor/Safety agents rebase and adapt |
| Integration conflicts in config.py | Use unique setting names, merge carefully |
| Test failures after merge | Each agent includes comprehensive tests |
| Dependency version mismatches | Use same conda environment across all worktrees |

---

## Timeline Estimate

**Week 1**: Database Agent completes, merges to main
**Week 2**: Supervisor Agent rebases on main, completes, merges
**Week 3**: Safety Agent rebases, completes, merges
**Week 4**: API Agent rebases, completes, merges
**Week 5**: Integration testing and bug fixes

**Total**: 5 weeks with parallel work, vs. 8-10 weeks sequential

---

## Next Steps

1. **Create worktrees** (see Setup Instructions above)
2. **Review agent instruction files** (PHASE4_AGENT_*.md, created next)
3. **Spawn Claude Code instances** in each worktree
4. **Begin parallel development**
5. **Merge in dependency order** (Database → Supervisor → Safety → API)
6. **Run integration tests**
7. **Celebrate Phase 4 completion!** 🎉

---

This workflow maximizes parallelization while minimizing integration pain. Each Claude agent has clear instructions and boundaries, making Phase 4 development efficient and organized.
