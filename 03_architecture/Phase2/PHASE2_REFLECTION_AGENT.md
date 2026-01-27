# Phase 2: Reflection Agent

## Overview

The Reflection Agent reviews and scores hypotheses across multiple criteria, simulating the role of a scientific peer reviewer. It critically examines correctness, quality, and novelty of generated hypotheses.

**File:** `src/agents/reflection.py`
**Status:** ✅ Complete

## Capabilities

Based on Google AI Co-Scientist paper (Section 3.3.2):

1. **Initial Review** - Quick assessment without web search
2. **Full Review** - Thorough review with literature search
3. **Deep Verification** - Assumption decomposition
4. **Observation Review** - Explain experimental observations
5. **Simulation Review** - Step-wise mechanism simulation
6. **Tournament Review** - Adapts based on tournament results

## Implementation

```python
from typing import Optional
from src.agents.base import BaseAgent
from src.llm.base import BaseLLMClient
from src.prompts.loader import get_prompt_loader
from src.utils.ids import generate_review_id
from schemas import (
    Hypothesis, Review, ReviewType, ResearchGoal
)
import structlog

logger = structlog.get_logger()

class ReflectionAgent(BaseAgent):
    """Agent for reviewing and scoring hypotheses"""

    def __init__(self, llm_client: BaseLLMClient):
        super().__init__(llm_client, "ReflectionAgent")
        self.prompt_loader = get_prompt_loader()

    async def execute(
        self,
        hypothesis: Hypothesis,
        research_goal: ResearchGoal,
        review_type: ReviewType = ReviewType.INITIAL
    ) -> Review:
        """Review a hypothesis

        Args:
            hypothesis: Hypothesis to review
            research_goal: Associated research goal
            review_type: Type of review to perform

        Returns:
            Review with scores and feedback
        """
        self.log_execution(
            task="hypothesis_review",
            hypothesis_id=hypothesis.id,
            review_type=review_type.value
        )

        # Build review prompt
        prompt = self._build_review_prompt(
            hypothesis,
            research_goal,
            review_type
        )

        # Generate review
        response = await self.llm_client.generate(prompt)

        # Parse into Review object
        review = self._parse_review(
            response,
            hypothesis.id,
            review_type
        )

        logger.info(
            "Review completed",
            review_id=review.id,
            hypothesis_id=hypothesis.id,
            quality_score=review.quality_score
        )

        return review

    def _build_review_prompt(
        self,
        hypothesis: Hypothesis,
        goal: ResearchGoal,
        review_type: ReviewType
    ) -> str:
        """Build prompt for review type"""

        hypothesis_text = f"""
        Title: {hypothesis.title}
        Statement: {hypothesis.hypothesis_statement}
        Rationale: {hypothesis.rationale}
        Mechanism: {hypothesis.mechanism}
        """

        base_prompt = f"""
        Review this scientific hypothesis:

        Research Goal: {goal.description}
        Preferences: {', '.join(goal.preferences)}

        {hypothesis_text}

        Evaluate on these criteria (score 0.0 to 1.0):
        1. Correctness - Is the hypothesis logically sound?
        2. Quality - Is it well-formulated and clear?
        3. Novelty - Does it propose something new?
        4. Testability - Can it be experimentally validated?
        5. Safety - Are there ethical concerns?

        Return JSON:
        {{
            "correctness_score": 0.0-1.0,
            "quality_score": 0.0-1.0,
            "novelty_score": 0.0-1.0,
            "testability_score": 0.0-1.0,
            "safety_score": 0.0-1.0,
            "strengths": ["strength1", "strength2"],
            "weaknesses": ["weakness1", "weakness2"],
            "suggestions": ["suggestion1"],
            "known_aspects": "What is already known",
            "novel_aspects": "What is new",
            "overall_assessment": "Summary assessment"
        }}
        """

        return base_prompt

    def _parse_review(
        self,
        response: str,
        hypothesis_id: str,
        review_type: ReviewType
    ) -> Review:
        """Parse LLM response into Review object"""
        from src.utils.json_parser import parse_llm_json

        data = parse_llm_json(response)

        return Review(
            id=generate_review_id(),
            hypothesis_id=hypothesis_id,
            review_type=review_type,
            correctness_score=data.get("correctness_score", 0.5),
            quality_score=data.get("quality_score", 0.5),
            novelty_score=data.get("novelty_score", 0.5),
            testability_score=data.get("testability_score", 0.5),
            safety_score=data.get("safety_score", 1.0),
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            suggestions=data.get("suggestions", []),
            known_aspects=data.get("known_aspects", ""),
            novel_aspects=data.get("novel_aspects", ""),
            overall_assessment=data.get("overall_assessment", "")
        )
```

## Review Types

### Initial Review
Quick assessment without external tools:
- No web search
- Fast filtering of obviously flawed hypotheses
- Preliminary safety check

### Full Review
Thorough review with literature:
- Web search for relevant papers
- Evidence for/against hypothesis
- Detailed novelty assessment

### Deep Verification
Assumption decomposition:
- Break hypothesis into assumptions
- Each assumption into sub-assumptions
- Identify potential invalidating factors

### Observation Review
Explain experimental findings:
- Can hypothesis explain observed phenomena?
- Better than existing explanations?

## Output Schema

```python
class Review(BaseModel):
    id: str                      # rev_YYYYMMDD_random
    hypothesis_id: str           # Link to hypothesis
    review_type: ReviewType

    # Scores (0.0 to 1.0)
    correctness_score: float
    quality_score: float
    novelty_score: float
    testability_score: float
    safety_score: float

    # Qualitative feedback
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]

    # Novelty analysis
    known_aspects: str
    novel_aspects: str

    # Summary
    overall_assessment: str
```

## Usage

```python
from src.agents.reflection import ReflectionAgent
from src.llm.factory import get_llm_client
from schemas import ReviewType

# Create agent
client = get_llm_client(
    model=settings.reflection_model,
    agent_name="reflection"
)
agent = ReflectionAgent(client)

# Review hypothesis
review = await agent.execute(
    hypothesis=hypothesis,
    research_goal=goal,
    review_type=ReviewType.FULL
)

print(f"Quality: {review.quality_score}")
print(f"Novelty: {review.novelty_score}")
print(f"Strengths: {review.strengths}")
```

## Example Output

```json
{
    "id": "rev_20260123_a1b2c3d4",
    "hypothesis_id": "hyp_20260122_x7y8z9",
    "review_type": "full",
    "correctness_score": 0.8,
    "quality_score": 0.85,
    "novelty_score": 0.7,
    "testability_score": 0.9,
    "safety_score": 1.0,
    "strengths": [
        "Clear mechanism of action",
        "Well-supported by literature",
        "Feasible experimental design"
    ],
    "weaknesses": [
        "Limited consideration of off-target effects",
        "Missing dose-response predictions"
    ],
    "suggestions": [
        "Include selectivity assays",
        "Add pharmacokinetic considerations"
    ],
    "known_aspects": "IRE1α role in UPR is established",
    "novel_aspects": "Application to AML is underexplored",
    "overall_assessment": "Promising hypothesis with strong testability"
}
```

## Testing

```python
@pytest.mark.asyncio
async def test_reflection_agent():
    """Test hypothesis review"""
    agent = ReflectionAgent(get_llm_client())

    review = await agent.execute(
        hypothesis=sample_hypothesis,
        research_goal=sample_goal,
        review_type=ReviewType.INITIAL
    )

    assert review.id.startswith("rev_")
    assert 0.0 <= review.quality_score <= 1.0
    assert len(review.strengths) > 0
```
