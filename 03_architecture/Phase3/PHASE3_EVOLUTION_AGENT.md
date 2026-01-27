# Phase 3: Evolution Agent

## Overview

The Evolution Agent continuously refines and improves existing hypotheses using various strategies, creating new hypotheses that inherit lineage from parents.

**File:** `src/agents/evolution.py`
**Status:** ✅ Complete

## Capabilities

Based on Google AI Co-Scientist paper (Section 3.3.5):

1. **Grounding** - Enhance with literature support
2. **Coherence** - Improve logical consistency
3. **Feasibility** - Make more practical
4. **Simplification** - Simplify for testing
5. **Inspiration** - Draw from other hypotheses
6. **Combination** - Merge best aspects
7. **Out-of-box** - Divergent thinking

## Implementation

```python
from typing import List, Optional
from src.agents.base import BaseAgent
from src.llm.base import BaseLLMClient
from src.prompts.loader import get_prompt_loader
from src.utils.ids import generate_hypothesis_id
from schemas import (
    Hypothesis, Review, EvolutionStrategy, ResearchGoal
)
import structlog

logger = structlog.get_logger()

class EvolutionAgent(BaseAgent):
    """Agent for evolving and refining hypotheses"""

    # Strategies using feasibility prompt
    FEASIBILITY_STRATEGIES = {
        EvolutionStrategy.GROUNDING,
        EvolutionStrategy.COHERENCE,
        EvolutionStrategy.FEASIBILITY,
        EvolutionStrategy.SIMPLIFICATION
    }

    # Strategies using out-of-box prompt
    OUTOFBOX_STRATEGIES = {
        EvolutionStrategy.INSPIRATION,
        EvolutionStrategy.COMBINATION,
        EvolutionStrategy.OUT_OF_BOX
    }

    def __init__(self, llm_client: BaseLLMClient):
        super().__init__(llm_client, "EvolutionAgent")
        self.prompt_loader = get_prompt_loader()

    async def execute(
        self,
        hypothesis: Hypothesis,
        review: Review,
        research_goal: ResearchGoal,
        strategy: EvolutionStrategy = EvolutionStrategy.FEASIBILITY,
        inspiration_hypotheses: Optional[List[Hypothesis]] = None
    ) -> Hypothesis:
        """Evolve a hypothesis using specified strategy

        Args:
            hypothesis: Hypothesis to evolve
            review: Review of the hypothesis
            research_goal: Research goal for context
            strategy: Evolution strategy to apply
            inspiration_hypotheses: Other hypotheses for inspiration

        Returns:
            New evolved Hypothesis (parent unchanged)
        """
        self.log_execution(
            task="hypothesis_evolution",
            hypothesis_id=hypothesis.id,
            strategy=strategy.value
        )

        # Select prompt based on strategy
        if strategy in self.FEASIBILITY_STRATEGIES:
            evolved = await self._evolve_feasibility(
                hypothesis, review, research_goal, strategy
            )
        else:
            evolved = await self._evolve_outofbox(
                hypothesis, review, research_goal, strategy,
                inspiration_hypotheses
            )

        logger.info(
            "Hypothesis evolved",
            parent_id=hypothesis.id,
            evolved_id=evolved.id,
            strategy=strategy.value
        )

        return evolved

    async def _evolve_feasibility(
        self,
        hypothesis: Hypothesis,
        review: Review,
        goal: ResearchGoal,
        strategy: EvolutionStrategy
    ) -> Hypothesis:
        """Evolve using feasibility/grounding prompt"""

        prompt = self.prompt_loader.get_evolution_feasibility_prompt(
            hypothesis=self._format_hypothesis(hypothesis),
            review=self._format_review(review),
            goal=goal.description,
            preferences=", ".join(goal.preferences)
        )

        prompt += f"""

        Strategy: {strategy.value}

        For {strategy.value}, focus on:
        - GROUNDING: Add literature citations and evidence
        - COHERENCE: Fix logical inconsistencies
        - FEASIBILITY: Make experiments more practical
        - SIMPLIFICATION: Remove unnecessary complexity

        Return the improved hypothesis as JSON:
        {{
            "title": "Improved title",
            "hypothesis_statement": "Refined statement",
            "rationale": "Updated rationale with improvements",
            "mechanism": "Clarified mechanism",
            "evolution_rationale": "What was improved and why",
            "experimental_protocol": {{...}},
            "citations": [...]
        }}
        """

        response = await self.llm_client.generate(prompt)
        return self._parse_evolved_hypothesis(
            response, hypothesis, strategy, goal.id
        )

    async def _evolve_outofbox(
        self,
        hypothesis: Hypothesis,
        review: Review,
        goal: ResearchGoal,
        strategy: EvolutionStrategy,
        inspiration: Optional[List[Hypothesis]] = None
    ) -> Hypothesis:
        """Evolve using out-of-box/inspiration prompt"""

        # Format hypotheses for inspiration
        if inspiration and strategy in {
            EvolutionStrategy.INSPIRATION,
            EvolutionStrategy.COMBINATION
        }:
            hypotheses_text = "\n\n".join(
                self._format_hypothesis(h) for h in inspiration[:3]
            )
        else:
            hypotheses_text = self._format_hypothesis(hypothesis)

        prompt = self.prompt_loader.get_evolution_outofbox_prompt(
            hypotheses=hypotheses_text,
            goal=goal.description,
            preferences=", ".join(goal.preferences)
        )

        prompt += f"""

        Strategy: {strategy.value}

        For {strategy.value}, focus on:
        - INSPIRATION: Draw novel ideas from the provided hypotheses
        - COMBINATION: Merge the best aspects of multiple hypotheses
        - OUT_OF_BOX: Think divergently, challenge assumptions

        Return a new hypothesis as JSON:
        {{
            "title": "Novel title",
            "hypothesis_statement": "New statement",
            "rationale": "Creative rationale",
            "mechanism": "Novel mechanism",
            "evolution_rationale": "How this differs and why",
            "experimental_protocol": {{...}},
            "citations": [...]
        }}
        """

        response = await self.llm_client.generate(prompt)
        return self._parse_evolved_hypothesis(
            response, hypothesis, strategy, goal.id
        )

    def _parse_evolved_hypothesis(
        self,
        response: str,
        parent: Hypothesis,
        strategy: EvolutionStrategy,
        goal_id: str
    ) -> Hypothesis:
        """Parse LLM response into evolved Hypothesis"""
        from src.utils.json_parser import parse_llm_json
        from schemas import ExperimentalProtocol, Citation, HypothesisStatus

        data = parse_llm_json(response)

        # Build protocol
        protocol_data = data.get("experimental_protocol", {})
        protocol = ExperimentalProtocol(
            objective=protocol_data.get("objective", ""),
            methodology=protocol_data.get("methodology", ""),
            controls=protocol_data.get("controls", []),
            expected_outcomes=protocol_data.get("expected_outcomes", []),
            success_criteria=protocol_data.get("success_criteria", "")
        )

        # Build citations
        citations = [
            Citation(
                title=c.get("title", ""),
                relevance=c.get("relevance", "")
            )
            for c in data.get("citations", [])
        ]

        # Create evolved hypothesis
        # Inherits parent's Elo rating
        return Hypothesis(
            id=generate_hypothesis_id(),
            research_goal_id=goal_id,
            title=data.get("title", f"Evolved: {parent.title}"),
            summary=data.get("summary", ""),
            hypothesis_statement=data.get("hypothesis_statement", ""),
            rationale=data.get("rationale", ""),
            mechanism=data.get("mechanism", ""),
            experimental_protocol=protocol,
            citations=citations,
            elo_rating=parent.elo_rating,  # Inherit parent's Elo
            status=HypothesisStatus.GENERATED,
            parent_hypothesis_id=parent.id,  # Track lineage
            evolution_strategy=strategy,
            evolution_rationale=data.get("evolution_rationale", "")
        )

    def _format_hypothesis(self, hyp: Hypothesis) -> str:
        return f"""
        Title: {hyp.title}
        Statement: {hyp.hypothesis_statement}
        Rationale: {hyp.rationale}
        Mechanism: {hyp.mechanism}
        """

    def _format_review(self, rev: Review) -> str:
        return f"""
        Quality: {rev.quality_score}
        Novelty: {rev.novelty_score}
        Weaknesses: {', '.join(rev.weaknesses)}
        Suggestions: {', '.join(rev.suggestions)}
        """
```

## Evolution Strategies

### Grounding
Add literature citations and evidence:
```
Input: "KIRA6 may inhibit AML"
Output: "KIRA6 inhibits IRE1α (Smith et al., 2023) which is overexpressed in AML (Jones et al., 2022)"
```

### Coherence
Fix logical inconsistencies:
```
Input: Mechanism contradicts rationale
Output: Aligned mechanism and rationale
```

### Feasibility
Make experiments more practical:
```
Input: "In vivo mouse model required"
Output: "Initial in vitro IC50 assay, then mouse model if successful"
```

### Simplification
Remove unnecessary complexity:
```
Input: 5-step experimental protocol
Output: 3 essential steps with clear success criteria
```

### Inspiration
Draw from other hypotheses:
```
Input: Top 3 hypotheses about different targets
Output: Novel hypothesis combining insights
```

### Combination
Merge best aspects:
```
Input: Hypothesis A (strong mechanism) + Hypothesis B (strong protocol)
Output: New hypothesis with both strengths
```

### Out-of-box
Challenge assumptions:
```
Input: "Target X for disease Y"
Output: "What if we target the regulatory pathway of X instead?"
```

## Lineage Tracking

Evolved hypotheses track their parent:

```python
evolved = Hypothesis(
    ...
    parent_hypothesis_id=parent.id,      # Track lineage
    evolution_strategy=strategy,          # How evolved
    evolution_rationale="..."             # Why evolved
)
```

## Elo Inheritance

Evolved hypotheses start with parent's Elo:

```python
elo_rating=parent.elo_rating  # Inherit parent's Elo
```

This gives refined hypotheses a fair starting point while still requiring them to prove themselves in tournaments.

## Usage

```python
from src.agents.evolution import EvolutionAgent
from src.llm.factory import get_llm_client
from schemas import EvolutionStrategy

agent = EvolutionAgent(get_llm_client())

# Feasibility improvement
evolved = await agent.execute(
    hypothesis=original,
    review=review,
    research_goal=goal,
    strategy=EvolutionStrategy.FEASIBILITY
)

# Combination of multiple hypotheses
combined = await agent.execute(
    hypothesis=hyp_a,
    review=review_a,
    research_goal=goal,
    strategy=EvolutionStrategy.COMBINATION,
    inspiration_hypotheses=[hyp_b, hyp_c]
)

print(f"Parent: {original.id}")
print(f"Evolved: {evolved.id}")
print(f"Strategy: {evolved.evolution_strategy}")
print(f"Rationale: {evolved.evolution_rationale}")
```

## Testing

```python
@pytest.mark.asyncio
async def test_evolution_agent():
    """Test hypothesis evolution"""
    agent = EvolutionAgent(get_llm_client())

    evolved = await agent.execute(
        hypothesis=sample_hypothesis,
        review=sample_review,
        research_goal=goal,
        strategy=EvolutionStrategy.FEASIBILITY
    )

    assert evolved.id != sample_hypothesis.id
    assert evolved.parent_hypothesis_id == sample_hypothesis.id
    assert evolved.evolution_strategy == EvolutionStrategy.FEASIBILITY
    assert len(evolved.evolution_rationale) > 0
```
