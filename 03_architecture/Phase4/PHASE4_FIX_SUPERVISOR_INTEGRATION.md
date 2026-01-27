# Agent Task 1: Integrate SupervisorAgent into API

## Objective

Replace the simplified `CoScientistWorkflow` with the full `SupervisorAgent` for goal execution in the REST API.

---

## Problem Statement

The SupervisorAgent ([src/agents/supervisor.py](src/agents/supervisor.py), 877 lines) implements sophisticated orchestration:
- Dynamic task queue with weighted agent selection
- Terminal condition detection (budget, convergence, quality)
- Checkpoint/resume capability
- Statistics tracking for weight adaptation

**However, it is never used.** The API directly calls `CoScientistWorkflow` instead.

---

## Evidence

### Current Implementation (Bypasses Supervisor)

**[src/api/main.py:76-79](src/api/main.py#L76-L79):**
```python
def run_workflow(goal: ResearchGoal, max_iterations: int, enable_evolution: bool):
    """Run the workflow synchronously (for background execution)"""
    workflow = CoScientistWorkflow(enable_evolution=enable_evolution)
    return workflow.run(research_goal=goal, max_iterations=max_iterations)
```

**[src/api/main.py:178](src/api/main.py#L178):**
```python
task_id = task_manager.start_sync_task(
    goal_id=goal.id,
    func=run_workflow,  # Uses CoScientistWorkflow, NOT SupervisorAgent
    goal=goal,
    max_iterations=config.max_iterations,
    enable_evolution=config.enable_evolution,
)
```

### What Should Be Used

**[src/agents/supervisor.py:152-265](src/agents/supervisor.py#L152-L265):**
```python
async def execute(
    self,
    research_goal: ResearchGoal,
    max_iterations: int = 20,
    checkpoint_interval: int = 5,
    resume_from: Optional[str] = None
) -> Dict[str, Any]:
    """Execute the full co-scientist workflow with supervisor orchestration"""
    # ... sophisticated orchestration logic
```

---

## Files to Modify

| File | Action |
|------|--------|
| [src/api/main.py](src/api/main.py) | Replace `run_workflow` with supervisor execution |
| [src/api/background.py](src/api/background.py) | May need `start_async_task` support |

---

## Implementation Steps

### Step 1: Add SupervisorAgent Import

In [src/api/main.py](src/api/main.py), add:
```python
from src.agents.supervisor import SupervisorAgent
```

### Step 2: Create Async Supervisor Runner

Replace or modify `run_workflow` function:

```python
async def run_supervisor_workflow(goal_id: str, max_iterations: int):
    """Run supervisor-orchestrated workflow asynchronously"""
    from src.storage.memory import MemoryStorage

    storage = MemoryStorage()
    supervisor = SupervisorAgent(storage)

    # Retrieve goal from storage (or pass it in)
    goal = await storage.get_research_goal(goal_id)

    return await supervisor.execute(
        research_goal=goal,
        max_iterations=max_iterations
    )
```

### Step 3: Update Goal Submission Endpoint

Modify the `submit_goal` function at [src/api/main.py:145-199](src/api/main.py#L145-L199):

```python
@app.post("/goals", response_model=GoalStatusResponse, tags=["Goals"])
async def submit_goal(request: SubmitGoalRequest, config: Optional[WorkflowConfigRequest] = None):
    # ... existing validation code ...

    # Option A: If background.py supports async tasks
    task_id = await task_manager.start_async_task(
        goal_id=goal.id,
        coroutine=run_supervisor_workflow(goal.id, config.max_iterations)
    )

    # Option B: If keeping sync execution (wrap async in sync)
    # task_id = task_manager.start_sync_task(
    #     goal_id=goal.id,
    #     func=lambda: asyncio.run(run_supervisor_workflow(goal.id, config.max_iterations)),
    #     ...
    # )
```

### Step 4: Handle Storage Integration

The SupervisorAgent expects an async storage adapter. Check [src/api/main.py](src/api/main.py) for existing storage setup and ensure compatibility.

---

## Verification

1. **Run existing tests:**
   ```bash
   python 05_tests/phase4_supervisor_test.py
   python 05_tests/phase4_api_test.py
   ```

2. **Add logging to confirm SupervisorAgent is used:**
   ```python
   # In run_supervisor_workflow
   import logging
   logging.info("Starting SupervisorAgent execution")
   ```

3. **Integration test:**
   ```bash
   uvicorn src.api.main:app --reload --port 8000
   # POST to /goals and verify supervisor-style logs appear
   ```

4. **Check terminal conditions are evaluated:**
   - Budget enforcement
   - Convergence detection
   - Quality thresholds

---

## Rollback Plan

If issues arise, revert to `CoScientistWorkflow` by:
1. Restoring original `run_workflow` function
2. Removing SupervisorAgent import
3. Reverting `submit_goal` to call `run_workflow`

---

## Dependencies

- [src/agents/supervisor.py](src/agents/supervisor.py) - SupervisorAgent implementation
- [src/storage/](src/storage/) - Storage abstraction layer
- [src/api/background.py](src/api/background.py) - Background task management

---

## Success Criteria

- [ ] API uses SupervisorAgent for goal execution
- [ ] Dynamic task weighting is active
- [ ] Terminal conditions (budget, convergence) are checked
- [ ] Existing API tests pass
- [ ] No regression in goal processing