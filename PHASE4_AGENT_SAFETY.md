# Phase 4 Agent: Safety Mechanisms & Checkpoints

**Branch**: `phase4/safety`
**Timeline**: Week 3 (7 days)
**Dependencies**: Database layer (BaseStorage) + Supervisor agent
**Priority**: MEDIUM (blocks API agent)

---

## Mission

Implement safety review mechanisms for research goals and hypotheses, plus checkpoint/resume functionality for workflow state persistence and recovery.

---

## Context

You are working in a **git worktree** on branch `phase4/safety`. Database and Supervisor agents have completed their work.

**Current System State**:
- Database persistence working (PostgreSQL + Redis)
- Supervisor orchestrating agents
- No safety reviews
- No checkpoint/resume capability

**Your Goal**:
- Create Safety agent for ethical review of goals and hypotheses
- Implement checkpoint system for state persistence
- Integrate safety reviews into workflow
- Enable workflow resumption from checkpoints

---

## Deliverables

### Files to Create

1. **src/agents/safety.py** - Safety review agent
2. **src/supervisor/checkpoint.py** - Checkpoint manager
3. **test_safety.py** - Safety agent tests
4. **test_checkpoint.py** - Checkpoint system tests

### Files to Modify

1. **src/graphs/workflow.py** - Add safety review nodes (optional)
2. **src/agents/supervisor.py** - Add checkpoint calls

---

## Implementation Guide

### Step 1: Rebase on Main (Day 1)

```bash
# Ensure you have latest database + supervisor code
git fetch origin main
git rebase origin/main

# Resolve any conflicts
# Test that existing code still works
python test_phase3.py
```

### Step 2: Implement Safety Agent (Days 1-3)

**File**: `src/agents/safety.py`

```python
"""Safety review agent for ethical and experimental risk assessment"""

from typing import Dict, List
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import ResearchGoal, Hypothesis

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.config import settings
from src.utils.errors import CoScientistError
from src.utils.json_parser import parse_llm_json
import structlog

logger = structlog.get_logger()


class SafetyAgent(BaseAgent):
    """Safety review for research goals and hypotheses"""

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.supervisor_model,  # Use fast model
            agent_name="safety"
        )
        super().__init__(llm_client, "SafetyAgent")

    async def review_goal(self, goal: ResearchGoal) -> Dict:
        """Review research goal for ethical and safety concerns

        Args:
            goal: Research goal to review

        Returns:
            Dict with:
                - safety_score: 0.0-1.0 (1.0 = completely safe)
                - concerns: List of ethical/safety concerns
                - recommendations: List of recommendations
                - requires_ethics_review: Boolean
                - risk_categories: Dict of risk scores by category
        """
        self.log_execution(
            task="goal_safety_review",
            goal_id=goal.id
        )

        prompt = f"""
        Review this research goal for ethical and safety concerns:

        Goal: {goal.description}
        Constraints: {', '.join(goal.constraints)}
        Preferences: {', '.join(goal.preferences)}

        Assess the following risk categories (0.0-1.0, higher = more risk):

        1. **Dual-Use Potential**: Could this research be misused for harmful purposes?
           - Military/weapons applications
           - Surveillance or privacy violations
           - Bioweapons or toxins

        2. **Biosafety Risks**: Does this involve hazardous biological materials?
           - Pathogen enhancement (gain-of-function)
           - Creation of new pathogens
           - Work with high-risk organisms (BSL-3/4)

        3. **Human Subjects**: Does this involve human participants?
           - Requires IRB/ethics board approval?
           - Vulnerable populations involved?
           - Informed consent issues?

        4. **Environmental Impact**: Could this harm the environment?
           - Release of GMOs
           - Toxic waste generation
           - Ecosystem disruption

        5. **Data Privacy**: Does this involve sensitive data?
           - Human genetic data
           - Medical records
           - Personally identifiable information

        Return ONLY a JSON object:
        {{
            "safety_score": 0.0-1.0,
            "concerns": ["concern1", "concern2"],
            "recommendations": ["recommendation1", "recommendation2"],
            "requires_ethics_review": true/false,
            "risk_categories": {{
                "dual_use": 0.0-1.0,
                "biosafety": 0.0-1.0,
                "human_subjects": 0.0-1.0,
                "environmental": 0.0-1.0,
                "data_privacy": 0.0-1.0
            }}
        }}

        Respond with ONLY the JSON object, no additional text.
        """

        # Invoke LLM
        response = await self.llm_client.ainvoke(prompt)

        # Parse response
        try:
            data = parse_llm_json(response, agent_name="SafetyAgent")

            # Calculate overall safety score if not provided
            if "safety_score" not in data:
                risk_scores = data.get("risk_categories", {})
                avg_risk = sum(risk_scores.values()) / len(risk_scores) if risk_scores else 0.0
                data["safety_score"] = 1.0 - avg_risk  # Invert (higher safety score = safer)

            self.logger.info(
                "Goal safety review complete",
                goal_id=goal.id,
                safety_score=data["safety_score"],
                num_concerns=len(data.get("concerns", []))
            )

            return data

        except Exception as e:
            raise CoScientistError(f"Failed to parse safety review: {e}\nResponse: {response[:500]}")

    async def review_hypothesis(self, hypothesis: Hypothesis) -> Dict:
        """Review hypothesis for experimental safety risks

        Args:
            hypothesis: Hypothesis to review

        Returns:
            Dict with:
                - safety_score: 0.0-1.0 (1.0 = completely safe)
                - risks: List of safety risks
                - mitigations: List of recommended mitigations
                - requires_special_approval: Boolean
        """
        self.log_execution(
            task="hypothesis_safety_review",
            hypothesis_id=hypothesis.id
        )

        protocol_text = "No experimental protocol provided"
        if hypothesis.experimental_protocol:
            protocol_text = f"""
            Methodology: {hypothesis.experimental_protocol.methodology}
            Controls: {hypothesis.experimental_protocol.controls}
            Success Criteria: {hypothesis.experimental_protocol.success_criteria}
            """

        prompt = f"""
        Review this hypothesis for experimental safety risks:

        Hypothesis: {hypothesis.statement}
        Rationale: {hypothesis.rationale}
        Mechanism: {hypothesis.mechanism}

        Experimental Protocol:
        {protocol_text}

        Assess safety risks in the proposed experiments:

        1. **Chemical Hazards**: Use of toxic, flammable, or reactive chemicals?
        2. **Biological Hazards**: Use of infectious agents, GMOs, or human samples?
        3. **Physical Hazards**: Radiation, high voltage, cryogenics, high pressure?
        4. **Regulatory Compliance**: Special permits needed (animal use, human subjects, controlled substances)?

        Return ONLY a JSON object:
        {{
            "safety_score": 0.0-1.0,
            "risks": ["risk1", "risk2"],
            "mitigations": ["mitigation1", "mitigation2"],
            "requires_special_approval": true/false,
            "hazard_categories": {{
                "chemical": 0.0-1.0,
                "biological": 0.0-1.0,
                "physical": 0.0-1.0,
                "regulatory": 0.0-1.0
            }}
        }}

        Respond with ONLY the JSON object, no additional text.
        """

        # Invoke LLM
        response = await self.llm_client.ainvoke(prompt)

        # Parse response
        try:
            data = parse_llm_json(response, agent_name="SafetyAgent")

            # Calculate overall safety score if not provided
            if "safety_score" not in data:
                hazard_scores = data.get("hazard_categories", {})
                avg_hazard = sum(hazard_scores.values()) / len(hazard_scores) if hazard_scores else 0.0
                data["safety_score"] = 1.0 - avg_hazard  # Invert

            self.logger.info(
                "Hypothesis safety review complete",
                hypothesis_id=hypothesis.id,
                safety_score=data["safety_score"],
                num_risks=len(data.get("risks", []))
            )

            return data

        except Exception as e:
            raise CoScientistError(f"Failed to parse safety review: {e}\nResponse: {response[:500]}")

    def is_safe(self, safety_assessment: Dict, threshold: float = 0.5) -> bool:
        """Determine if goal/hypothesis passes safety threshold

        Args:
            safety_assessment: Output from review_goal() or review_hypothesis()
            threshold: Minimum safety score to pass (default 0.5)

        Returns:
            True if safe (score >= threshold), False otherwise
        """
        safety_score = safety_assessment.get("safety_score", 0.0)
        return safety_score >= threshold
```

**Test Safety Agent**:

```python
# test_safety.py
import pytest
from src.agents.safety import SafetyAgent
from schemas import ResearchGoal, Hypothesis

@pytest.mark.asyncio
async def test_goal_safety_review():
    """Test goal safety review"""
    agent = SafetyAgent()

    # Test safe goal
    safe_goal = ResearchGoal(
        id="safe_goal",
        description="Develop new diagnostic test for diabetes",
        constraints=[],
        preferences=[]
    )

    assessment = await agent.review_goal(safe_goal)
    assert "safety_score" in assessment
    assert 0.0 <= assessment["safety_score"] <= 1.0

@pytest.mark.asyncio
async def test_hypothesis_safety_review():
    """Test hypothesis safety review"""
    agent = SafetyAgent()

    hypothesis = Hypothesis(
        id="test_hyp",
        research_goal_id="goal",
        title="Test Hypothesis",
        statement="Test in vitro assay",
        rationale="For testing",
        mechanism="Test mechanism",
        elo_rating=1200.0
    )

    assessment = await agent.review_hypothesis(hypothesis)
    assert "safety_score" in assessment
    assert isinstance(assessment["risks"], list)
```

### Step 3: Implement Checkpoint System (Days 4-5)

**File**: `src/supervisor/checkpoint.py`

```python
"""Checkpoint and resume functionality for workflow state"""

from typing import Optional
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import ContextMemory, TournamentState, ProximityGraph
from src.storage.base import BaseStorage
from src.supervisor.task_queue import TaskQueue
from src.utils.ids import generate_id
import structlog

logger = structlog.get_logger()


class CheckpointManager:
    """Save and restore workflow state for resumption"""

    def __init__(self, storage: BaseStorage):
        self.storage = storage

    async def save_checkpoint(
        self,
        goal_id: str,
        iteration: int,
        task_queue: TaskQueue,
        notes: str = ""
    ) -> ContextMemory:
        """Save checkpoint to database

        Args:
            goal_id: Research goal ID
            iteration: Current iteration number
            task_queue: Current task queue state
            notes: Optional supervisor notes

        Returns:
            ContextMemory object saved to database
        """
        logger.info("Saving checkpoint", goal_id=goal_id, iteration=iteration)

        # Build ContextMemory from current state
        # Get tournament state
        all_matches = await self.storage.get_all_matches(goal_id=goal_id)
        all_hypotheses = await self.storage.get_hypotheses_by_goal(goal_id)

        tournament_state = TournamentState(
            elo_ratings={h.id: h.elo_rating for h in all_hypotheses},
            match_history=[m.id for m in all_matches],
            win_loss_patterns={}  # TODO: Calculate patterns
        )

        # Get proximity graph
        proximity_graph = await self.storage.get_proximity_graph(goal_id)

        # Get all reviews
        all_reviews = []
        for h in all_hypotheses:
            reviews = await self.storage.get_reviews_for_hypothesis(h.id)
            all_reviews.extend(reviews)

        # Create ContextMemory
        context = ContextMemory(
            id=generate_id("checkpoint"),
            research_goal_id=goal_id,
            iteration=iteration,
            tournament_state=tournament_state,
            proximity_graph=proximity_graph,
            all_reviews=all_reviews,
            scientist_feedback=[],  # TODO: Get from storage
            supervisor_notes=notes or f"Checkpoint at iteration {iteration}"
        )

        # Save to database
        await self.storage.save_checkpoint(context)

        logger.info("Checkpoint saved successfully", checkpoint_id=context.id)
        return context

    async def load_checkpoint(self, goal_id: str) -> Optional[ContextMemory]:
        """Load most recent checkpoint for research goal

        Args:
            goal_id: Research goal ID

        Returns:
            Most recent ContextMemory, or None if no checkpoint exists
        """
        logger.info("Loading checkpoint", goal_id=goal_id)

        checkpoint = await self.storage.get_latest_checkpoint(goal_id)

        if checkpoint:
            logger.info(
                "Checkpoint loaded",
                checkpoint_id=checkpoint.id,
                iteration=checkpoint.iteration
            )
        else:
            logger.info("No checkpoint found for goal", goal_id=goal_id)

        return checkpoint

    async def resume_workflow(self, goal_id: str) -> Optional[int]:
        """Resume workflow from last checkpoint

        Args:
            goal_id: Research goal ID

        Returns:
            Iteration number to resume from, or None if no checkpoint
        """
        checkpoint = await self.load_checkpoint(goal_id)

        if not checkpoint:
            return None

        logger.info(
            "Resuming workflow from checkpoint",
            goal_id=goal_id,
            iteration=checkpoint.iteration
        )

        # TODO: Restore task queue state
        # TODO: Restore supervisor state

        return checkpoint.iteration

    async def should_checkpoint(self, iteration: int, interval: int = 5) -> bool:
        """Determine if checkpoint should be saved

        Args:
            iteration: Current iteration
            interval: Checkpoint every N iterations (default 5)

        Returns:
            True if should save checkpoint
        """
        return iteration % interval == 0
```

**Integrate into Supervisor**:

Modify `src/agents/supervisor.py` to call checkpoint manager:

```python
# In SupervisorAgent.__init__:
from src.supervisor.checkpoint import CheckpointManager
self.checkpoint_manager = CheckpointManager(storage)

# In execute() loop:
async def execute(self, research_goal: ResearchGoal, max_iterations: int = 20) -> str:
    # ... existing code ...

    iteration = 0
    while iteration < max_iterations:
        # ... existing iteration code ...

        # Save checkpoint periodically
        if await self.checkpoint_manager.should_checkpoint(iteration):
            await self.checkpoint_manager.save_checkpoint(
                goal_id=research_goal.id,
                iteration=iteration,
                task_queue=self.task_queue,
                notes=f"Checkpoint at iteration {iteration}"
            )

        iteration += 1
```

### Step 4: Integration Testing (Days 6-7)

**Test Checkpoint System**:

```python
# test_checkpoint.py
import pytest
from src.supervisor.checkpoint import CheckpointManager
from src.storage.factory import get_storage

@pytest.mark.asyncio
async def test_save_load_checkpoint():
    """Test checkpoint save/load"""
    storage = get_storage()
    await storage.connect()

    checkpoint_manager = CheckpointManager(storage)

    # Create test goal
    from schemas import ResearchGoal
    goal = ResearchGoal(
        id="test_goal",
        description="Test",
        constraints=[],
        preferences=[]
    )
    await storage.add_research_goal(goal)

    # Save checkpoint
    from src.supervisor.task_queue import TaskQueue
    task_queue = TaskQueue()

    checkpoint = await checkpoint_manager.save_checkpoint(
        goal_id=goal.id,
        iteration=5,
        task_queue=task_queue,
        notes="Test checkpoint"
    )

    assert checkpoint.iteration == 5

    # Load checkpoint
    loaded = await checkpoint_manager.load_checkpoint(goal.id)
    assert loaded.id == checkpoint.id
    assert loaded.iteration == 5

    await storage.disconnect()
```

### Step 5: Workflow Integration (Day 7)

**Optional**: Add safety review nodes to workflow:

```python
# In src/graphs/workflow.py (if modifying workflow)

from src.agents.safety import SafetyAgent

class CoScientistWorkflow:
    def __init__(self, ...):
        # ... existing code ...
        self.safety_agent = SafetyAgent()

    def safety_review_node(self, state: WorkflowState) -> WorkflowState:
        """Review hypotheses for safety before adding to tournament"""
        hypotheses = state["hypotheses"]
        safe_hypotheses = []

        for hyp in hypotheses:
            assessment = await self.safety_agent.review_hypothesis(hyp)
            if self.safety_agent.is_safe(assessment, threshold=0.5):
                safe_hypotheses.append(hyp)
            else:
                logger.warning(
                    "Hypothesis failed safety review",
                    hypothesis_id=hyp.id,
                    safety_score=assessment["safety_score"]
                )

        state["hypotheses"] = safe_hypotheses
        return state
```

---

## Testing Checklist

- [ ] Safety agent reviews goals
- [ ] Safety agent reviews hypotheses
- [ ] Safety scores between 0.0-1.0
- [ ] Unsafe content flagged correctly
- [ ] Checkpoint saves to database
- [ ] Checkpoint loads from database
- [ ] Workflow can resume from checkpoint
- [ ] Periodic checkpointing works

---

## Success Criteria

**Week 3 Complete When**:

1. ✅ Safety agent reviews goals and hypotheses
2. ✅ Safety scores computed correctly
3. ✅ Checkpoint system saves/loads state
4. ✅ Supervisor integrates checkpointing
5. ✅ Tests pass
6. ✅ Committed and pushed to `phase4/safety` branch

---

## Git Workflow

```bash
# Daily commits
git add .
git commit -m "feat(safety): [description]"
git push origin phase4/safety

# Example commits:
# Day 1: "feat(safety): implement goal safety review"
# Day 2: "feat(safety): implement hypothesis safety review"
# Day 3: "test(safety): add safety agent tests"
# Day 4: "feat(safety): implement checkpoint save"
# Day 5: "feat(safety): implement checkpoint load/resume"
# Day 6: "test(safety): add checkpoint tests"
# Day 7: "docs(safety): finalize safety & checkpoint components"
```

---

Your mission: Make the AI Co-Scientist safe and resilient! 🛡️
