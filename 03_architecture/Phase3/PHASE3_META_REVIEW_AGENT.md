# Phase 3: Meta-review Agent

## Overview

The Meta-review Agent synthesizes feedback patterns across reviews and tournament results, enabling continuous improvement. It also generates comprehensive research overviews for scientists.

**File:** `src/agents/meta_review.py`
**Status:** ✅ Complete

## Capabilities

Based on Google AI Co-Scientist paper (Section 3.3.6):

1. **Feedback Synthesis** - Identify recurring patterns in reviews
2. **Win/Loss Analysis** - Analyze tournament debate patterns
3. **Agent Feedback** - Provide specific feedback for each agent
4. **Research Overview** - Synthesize top hypotheses into overview
5. **Contact Identification** - Suggest domain experts

## Implementation

```python
from typing import List
from src.agents.base import BaseAgent
from src.llm.base import BaseLLMClient
from src.prompts.loader import get_prompt_loader
from src.utils.ids import generate_id
from schemas import (
    Review, TournamentMatch, MetaReviewCritique,
    ResearchOverview, ResearchDirection, ResearchContact,
    Hypothesis, ResearchGoal
)
import structlog

logger = structlog.get_logger()

class MetaReviewAgent(BaseAgent):
    """Agent for meta-review and research overview synthesis"""

    def __init__(self, llm_client: BaseLLMClient):
        super().__init__(llm_client, "MetaReviewAgent")
        self.prompt_loader = get_prompt_loader()

    async def execute(
        self,
        reviews: List[Review],
        matches: List[TournamentMatch],
        research_goal: ResearchGoal
    ) -> MetaReviewCritique:
        """Synthesize meta-review from reviews and tournament results

        Args:
            reviews: All reviews for the research goal
            matches: All tournament matches
            research_goal: Research goal for context

        Returns:
            MetaReviewCritique with synthesized feedback
        """
        self.log_execution(
            task="meta_review_synthesis",
            review_count=len(reviews),
            match_count=len(matches)
        )

        # Build prompt with reviews and tournament data
        prompt = self.prompt_loader.get_meta_review_prompt(
            reviews=self._format_reviews(reviews),
            tournament_results=self._format_matches(matches),
            goal=research_goal.description
        )

        prompt += """

        Analyze the reviews and tournament results to identify:
        1. Recurring strengths across hypotheses
        2. Recurring weaknesses and issues
        3. Suggested improvements for future hypotheses
        4. Patterns in tournament wins/losses
        5. Feedback for specific agents (generation, reflection, ranking)

        Return JSON:
        {
            "recurring_strengths": ["strength1", "strength2"],
            "recurring_weaknesses": ["weakness1", "weakness2"],
            "suggested_improvements": ["improvement1", "improvement2"],
            "win_loss_patterns": ["pattern1", "pattern2"],
            "agent_feedback": {
                "generation": "Feedback for generation agent",
                "reflection": "Feedback for reflection agent",
                "ranking": "Feedback for ranking agent"
            }
        }
        """

        response = await self.llm_client.generate(prompt)

        from src.utils.json_parser import parse_llm_json
        data = parse_llm_json(response)

        critique = MetaReviewCritique(
            id=generate_id("meta"),
            research_goal_id=research_goal.id,
            recurring_strengths=data.get("recurring_strengths", []),
            recurring_weaknesses=data.get("recurring_weaknesses", []),
            suggested_improvements=data.get("suggested_improvements", []),
            win_loss_patterns=data.get("win_loss_patterns", []),
            agent_feedback=data.get("agent_feedback", {})
        )

        logger.info(
            "Meta-review completed",
            strengths=len(critique.recurring_strengths),
            weaknesses=len(critique.recurring_weaknesses)
        )

        return critique

    async def generate_research_overview(
        self,
        hypotheses: List[Hypothesis],
        reviews: List[Review],
        research_goal: ResearchGoal,
        research_goal_id: str
    ) -> ResearchOverview:
        """Generate comprehensive research overview

        Args:
            hypotheses: Top-ranked hypotheses
            reviews: Reviews for the hypotheses
            research_goal: Research goal
            research_goal_id: ID for the overview

        Returns:
            ResearchOverview with directions and contacts
        """
        self.log_execution(
            task="research_overview",
            hypothesis_count=len(hypotheses)
        )

        # Format hypotheses for prompt
        hypotheses_text = "\n\n".join(
            f"Hypothesis {i+1} (Elo: {h.elo_rating:.0f}):\n"
            f"Title: {h.title}\n"
            f"Statement: {h.hypothesis_statement}\n"
            f"Mechanism: {h.mechanism}"
            for i, h in enumerate(hypotheses[:5])
        )

        prompt = f"""
        Research Goal: {research_goal.description}
        Preferences: {', '.join(research_goal.preferences)}

        Top Hypotheses:
        {hypotheses_text}

        Generate a comprehensive research overview:

        1. Executive Summary (2-3 paragraphs)
        2. Current Knowledge Boundary (what is known vs unknown)
        3. Research Directions (2-4 promising directions)
        4. Top Hypotheses Summary
        5. Suggested Domain Experts (2-3)
        6. Recommended Next Steps

        Return JSON:
        {{
            "executive_summary": "Overview paragraph",
            "current_knowledge_boundary": "What is known and what gaps remain",
            "research_directions": [
                {{
                    "title": "Direction title",
                    "description": "What this direction explores",
                    "feasibility_score": 0.0-1.0,
                    "suggested_experiments": ["exp1", "exp2"]
                }}
            ],
            "top_hypothesis_ids": ["id1", "id2"],
            "research_contacts": [
                {{
                    "name": "Expert Name",
                    "affiliation": "Institution",
                    "expertise": "Area of expertise",
                    "relevance": "Why relevant"
                }}
            ],
            "next_steps": ["step1", "step2"]
        }}
        """

        response = await self.llm_client.generate(prompt)

        from src.utils.json_parser import parse_llm_json
        data = parse_llm_json(response)

        # Build research directions
        directions = [
            ResearchDirection(
                title=d.get("title", ""),
                description=d.get("description", ""),
                feasibility_score=d.get("feasibility_score", 0.5),
                suggested_experiments=d.get("suggested_experiments", [])
            )
            for d in data.get("research_directions", [])
        ]

        # Build contacts
        contacts = [
            ResearchContact(
                name=c.get("name", ""),
                affiliation=c.get("affiliation", ""),
                expertise=c.get("expertise", ""),
                relevance=c.get("relevance", "")
            )
            for c in data.get("research_contacts", [])
        ]

        overview = ResearchOverview(
            id=generate_id("overview"),
            research_goal_id=research_goal_id,
            executive_summary=data.get("executive_summary", ""),
            current_knowledge_boundary=data.get("current_knowledge_boundary", ""),
            research_directions=directions,
            top_hypothesis_ids=data.get("top_hypothesis_ids", []),
            research_contacts=contacts,
            next_steps=data.get("next_steps", [])
        )

        logger.info(
            "Research overview generated",
            directions=len(directions),
            contacts=len(contacts)
        )

        return overview

    def _format_reviews(self, reviews: List[Review]) -> str:
        """Format reviews for prompt"""
        lines = []
        for i, rev in enumerate(reviews[:10], 1):
            lines.append(
                f"Review {i}:\n"
                f"  Quality: {rev.quality_score}, Novelty: {rev.novelty_score}\n"
                f"  Strengths: {', '.join(rev.strengths[:2])}\n"
                f"  Weaknesses: {', '.join(rev.weaknesses[:2])}"
            )
        return "\n".join(lines)

    def _format_matches(self, matches: List[TournamentMatch]) -> str:
        """Format tournament matches for prompt"""
        lines = []
        for i, match in enumerate(matches[:10], 1):
            lines.append(
                f"Match {i}: Winner={match.winner_id[:15]}...\n"
                f"  Rationale: {match.decision_rationale[:100]}..."
            )
        return "\n".join(lines)
```

## Output Schemas

### MetaReviewCritique

```python
class MetaReviewCritique(BaseModel):
    id: str
    research_goal_id: str
    recurring_strengths: List[str]
    recurring_weaknesses: List[str]
    suggested_improvements: List[str]
    win_loss_patterns: List[str]
    agent_feedback: Dict[str, str]  # agent_name -> feedback
```

### ResearchOverview

```python
class ResearchOverview(BaseModel):
    id: str
    research_goal_id: str
    executive_summary: str
    current_knowledge_boundary: str
    research_directions: List[ResearchDirection]
    top_hypothesis_ids: List[str]
    research_contacts: List[ResearchContact]
    next_steps: List[str]
```

## Self-Improving Loop

The meta-review enables in-context learning:

```
Generate → Review → Tournament → Meta-review → Feedback → Generate...
                                      │
                                      ▼
                              Appended to prompts
                              in next iteration
```

From Google paper (Section 3.3.6):
> "The meta-review provides valuable feedback... which is simply appended to their prompts in the next iteration"

## Usage

```python
from src.agents.meta_review import MetaReviewAgent
from src.llm.factory import get_llm_client

agent = MetaReviewAgent(get_llm_client())

# Generate meta-review critique
critique = await agent.execute(
    reviews=all_reviews,
    matches=all_matches,
    research_goal=goal
)

print("Recurring Strengths:")
for strength in critique.recurring_strengths:
    print(f"  - {strength}")

print("\nSuggested Improvements:")
for improvement in critique.suggested_improvements:
    print(f"  - {improvement}")

print("\nAgent Feedback:")
for agent_name, feedback in critique.agent_feedback.items():
    print(f"  {agent_name}: {feedback}")

# Generate research overview
overview = await agent.generate_research_overview(
    hypotheses=top_hypotheses,
    reviews=reviews,
    research_goal=goal,
    research_goal_id=goal.id
)

print(f"\nExecutive Summary:\n{overview.executive_summary}")

print("\nResearch Directions:")
for direction in overview.research_directions:
    print(f"  - {direction.title} (feasibility: {direction.feasibility_score})")

print("\nSuggested Contacts:")
for contact in overview.research_contacts:
    print(f"  - {contact.name} ({contact.affiliation})")
```

## Feedback Integration

Agent feedback is appended to prompts in subsequent iterations:

```python
# In Generation Agent
meta_feedback = critique.agent_feedback.get("generation", "")
prompt = f"""
{base_prompt}

Meta-review feedback from previous iterations:
{meta_feedback}
"""
```

## Testing

```python
@pytest.mark.asyncio
async def test_meta_review():
    """Test meta-review synthesis"""
    agent = MetaReviewAgent(get_llm_client())

    critique = await agent.execute(
        reviews=sample_reviews,
        matches=sample_matches,
        research_goal=goal
    )

    assert len(critique.recurring_strengths) > 0
    assert len(critique.recurring_weaknesses) > 0
    assert "generation" in critique.agent_feedback

@pytest.mark.asyncio
async def test_research_overview():
    """Test research overview generation"""
    agent = MetaReviewAgent(get_llm_client())

    overview = await agent.generate_research_overview(
        hypotheses=top_hypotheses,
        reviews=reviews,
        research_goal=goal,
        research_goal_id=goal.id
    )

    assert len(overview.executive_summary) > 0
    assert len(overview.research_directions) > 0
    assert overview.research_goal_id == goal.id
```
