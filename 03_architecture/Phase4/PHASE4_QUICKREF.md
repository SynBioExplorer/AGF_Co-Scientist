# Phase 4: Quick Reference Card

## 🚀 30-Second Setup

```bash
# Create branches & worktrees
git branch phase4/{database,supervisor,safety,api}
git worktree add ../worktree-database phase4/database
git worktree add ../worktree-supervisor phase4/supervisor
git worktree add ../worktree-safety phase4/safety
git worktree add ../worktree-api phase4/api

# Copy instruction files
for agent in database supervisor safety api; do
  cp PHASE4_AGENT_${agent^^}.md ../worktree-$agent/
done

# Open 4 terminals, navigate to each worktree, start Claude Code
```

---

## 📋 Agent Responsibilities

| Agent | Week | Files Created | Key Deliverable |
|-------|------|---------------|-----------------|
| **Database** | 1 | `base.py`, `postgres.py`, `schema.sql` | `BaseStorage` interface (Day 1!) |
| **Supervisor** | 2 | `task_queue.py`, `supervisor.py` | Orchestration loop |
| **Safety** | 3 | `safety.py`, `checkpoint.py` | Safety reviews + checkpoints |
| **API** | 4 | `main.py`, `chat.py` | FastAPI with 8+ endpoints |

---

## 🔗 Dependencies

```
Database (Week 1)
    ↓
Supervisor (Week 2) ──┐
    ↓                 ↓
Safety (Week 3) ──────┤
    ↓                 ↓
API (Week 4) ─────────┘
```

**Merge Order**: Database → Supervisor → Safety → API → Integration Testing

---

## ⚡ Critical Milestones

### Week 1, Day 1
- [ ] Database agent publishes `BaseStorage` interface
- [ ] Interface committed and pushed to `phase4/database`
- [ ] Supervisor agent can begin work

### Week 1, End
- [ ] Database agent merges to main
- [ ] All 13 tables created in PostgreSQL
- [ ] Storage factory switches between memory/postgres

### Week 2, End
- [ ] Supervisor agent merges to main
- [ ] Task queue operational
- [ ] Dynamic agent weighting works

### Week 3, End
- [ ] Safety agent merges to main
- [ ] Safety reviews integrated
- [ ] Checkpoint/resume functional

### Week 4, End
- [ ] API agent merges to main
- [ ] FastAPI running on localhost:8000
- [ ] All endpoints tested

---

## 🧪 Quick Tests

```bash
# Database
python test_storage.py

# Supervisor
python test_supervisor.py

# Safety
python test_safety.py
python test_checkpoint.py

# API
python test_api.py
pytest test_api.py -v

# Integration (after all merged)
python test_phase4.py
```

---

## 📊 Files Created (35 total)

### Database Agent (10 files)
- `src/storage/base.py` ⭐ Critical
- `src/storage/postgres.py`
- `src/storage/cache.py`
- `src/storage/factory.py`
- `src/storage/schema.sql`
- `src/storage/memory.py` (refactored)
- `scripts/migrate_db.py`
- `test_storage.py`
- `src/config.py` (modified)
- `03_architecture/environment.yml` (modified)

### Supervisor Agent (6 files)
- `src/supervisor/__init__.py`
- `src/supervisor/task_queue.py`
- `src/supervisor/statistics.py`
- `src/agents/supervisor.py`
- `test_supervisor.py`
- `src/storage/mock_storage.py` (temporary)

### Safety Agent (5 files)
- `src/agents/safety.py`
- `src/supervisor/checkpoint.py`
- `test_safety.py`
- `test_checkpoint.py`
- `src/agents/supervisor.py` (modified for checkpoints)

### API Agent (8 files)
- `src/api/__init__.py`
- `src/api/main.py`
- `src/api/chat.py`
- `src/api/models.py`
- `src/api/background.py`
- `test_api.py`
- `requirements-api.txt`
- `src/config.py` (modified for API settings)

---

## 🎯 Success Checklist

**Database Complete**:
- [ ] `BaseStorage` interface defined with 30+ methods
- [ ] PostgreSQL schema creates 13 tables
- [ ] `PostgreSQLStorage` implements all methods
- [ ] Redis cache stores/retrieves top hypotheses
- [ ] Storage factory switches backends via config
- [ ] All CRUD operations tested

**Supervisor Complete**:
- [ ] Task queue maintains priority order
- [ ] Statistics tracker computes convergence
- [ ] Agent weights adjust dynamically
- [ ] Terminal conditions detect (convergence, budget, quality)
- [ ] Supervisor orchestrates execution loop

**Safety Complete**:
- [ ] Safety agent reviews goals (dual-use, biosafety, etc.)
- [ ] Safety agent reviews hypotheses (chemical, biological hazards)
- [ ] Checkpoint saves to database every 5 iterations
- [ ] Workflow can resume from checkpoint
- [ ] Safety scores 0.0-1.0 computed correctly

**API Complete**:
- [ ] FastAPI app runs on port 8000
- [ ] 8+ endpoints functional (goals, hypotheses, stats, chat, etc.)
- [ ] Background task manager handles long-running jobs
- [ ] Chat interface provides context-aware responses
- [ ] Auto-generated docs at `/docs`

---

## 🔧 Common Commands

```bash
# View worktrees
git worktree list

# View branch commits
git log phase4/database --oneline
git log phase4/supervisor --oneline

# Merge to main (in main repo)
git checkout main
git merge phase4/database
git push origin main

# Run API server
uvicorn src.api.main:app --reload --port 8000

# Run database migration
python scripts/migrate_db.py

# Check cost tracker
python -c "from cost_tracker import get_tracker; get_tracker().print_summary()"
```

---

## 📞 Agent Communication

**Database Agent** → Supervisor/Safety/API:
- ✅ "BaseStorage interface published at `src/storage/base.py`"
- ✅ "All methods documented with type hints"
- ✅ "Use `get_storage()` factory to get implementation"

**Supervisor Agent** → Safety/API:
- ✅ "Supervisor orchestrates via `execute(research_goal, max_iterations)`"
- ✅ "Statistics available via `SupervisorStatistics.compute_statistics()`"
- ✅ "Task queue uses `TaskQueue.add_task()` and `get_next_task()`"

**Safety Agent** → API:
- ✅ "Safety reviews via `SafetyAgent.review_goal()` and `review_hypothesis()`"
- ✅ "Checkpoints saved via `CheckpointManager.save_checkpoint()`"
- ✅ "Resume via `CheckpointManager.resume_workflow()`"

---

## 💡 Pro Tips

1. **Database Agent**: Commit `base.py` ASAP (Day 1) - everyone needs it
2. **Supervisor Agent**: Use mock storage until database merges
3. **Safety Agent**: Rebase frequently to get latest database/supervisor code
4. **API Agent**: Scaffold endpoints early, implement handlers when dependencies ready
5. **All Agents**: Push daily commits with descriptive messages

---

## 🎓 Reading Order

1. **[README_PHASE4.md](README_PHASE4.md)** - Overview (you are here)
2. **[PHASE4_SETUP_GUIDE.md](PHASE4_SETUP_GUIDE.md)** - Step-by-step setup
3. **[PHASE4_PARALLEL_WORKFLOW.md](PHASE4_PARALLEL_WORKFLOW.md)** - Detailed workflow
4. **[PHASE4_AGENT_*.md](PHASE4_AGENT_DATABASE.md)** - Agent-specific instructions

---

## 🆘 Emergency Contacts

**If Database Agent is blocked**: They are the foundation - critical priority
**If Supervisor Agent is blocked**: Check if BaseStorage is available
**If Safety Agent is blocked**: Rebase on main to get latest code
**If API Agent is blocked**: All dependencies should be merged by Week 4

---

**Total Implementation Time**: 5 weeks (4 parallel + 1 integration)
**Estimated Budget**: ~$10 AUD for development/testing
**Lines of Code**: ~3,000-4,000 across all components

---

**Ready? Start with [PHASE4_SETUP_GUIDE.md](PHASE4_SETUP_GUIDE.md)!** 🚀
