# Phase 1: Generation Agent

## Overview

The Generation Agent creates initial hypotheses via literature exploration and simulated scientific debates. It's the first working agent in the system, producing structured Hypothesis objects validated against Pydantic schemas.

**File:** `src/agents/generation.py`
**Status:** ✅ Complete

## Capabilities

Based on Google AI Co-Scientist paper (Section 3.3.1):

1. **Literature Exploration** - Search web, retrieve articles, synthesize into hypotheses
2. **Simulated Scientific Debates** - Multi-turn self-play debates for refinement
3. **Iterative Assumptions** - Identify testable intermediate assumptions
4. **Research Expansion** - Explore unexplored areas based on meta-review feedback

## Implementation

```python
from typing import Optional
import json
from src.agents.base import BaseAgent
from src.llm.base import BaseLLMClient
from src.prompts.loader import get_prompt_loader
from src.utils.ids import generate_hypothesis_id
from src.utils.json_parser import parse_llm_json
from schemas import (
    Hypothesis, ResearchGoal, ExperimentalProtocol,
    Citation, HypothesisStatus, GenerationMethod
)
import structlog

logger = structlog.get_logger()

class GenerationAgent(BaseAgent):
    """Agent for generating initial research hypotheses"""

    def __init__(self, llm_client: BaseLLMClient):
        super().__init__(llm_client, "GenerationAgent")
        self.prompt_loader = get_prompt_loader()

    async def execute(
        self,
        research_goal: ResearchGoal,
        method: GenerationMethod = GenerationMethod.LITERATURE_EXPLORATION,
        articles_with_reasoning: str = "",
        use_web_search: bool = False
    ) -> Hypothesis:
        """Generate a hypothesis for the given research goal

        Args:
            research_goal: The research goal to address
            method: Generation method (literature or debate)
            articles_with_reasoning: Pre-retrieved literature
            use_web_search: Whether to search for additional literature

        Returns:
            Generated Hypothesis with experimental protocol
        """
        self.log_execution(
            task="hypothesis_generation",
            goal=research_goal.description[:100],
            method=method.value
        )

        # Optionally search for literature
        if use_web_search and not articles_with_reasoning:
            articles_with_reasoning = await self._search_literature(
                research_goal.description
            )

        # Get appropriate prompt
        if method == GenerationMethod.LITERATURE_EXPLORATION:
            prompt = self.prompt_loader.get_generation_prompt(
                goal=research_goal.description,
                preferences=", ".join(research_goal.preferences),
                notes=", ".join(research_goal.constraints),
                articles_with_reasoning=articles_with_reasoning
            )
        else:
            prompt = self.prompt_loader.get_generation_debate_prompt(
                goal=research_goal.description,
                preferences=", ".join(research_goal.preferences),
                notes=", ".join(research_goal.constraints)
            )

        # Add schema guidance
        prompt += self._get_schema_instructions()

        # Generate hypothesis
        response = await self.llm_client.generate(prompt)

        # Parse and validate
        hypothesis = self._parse_hypothesis(
            response,
            research_goal.id,
            method
        )

        logger.info(
            "Hypothesis generated",
            hypothesis_id=hypothesis.id,
            title=hypothesis.title[:50],
            elo=hypothesis.elo_rating
        )

        return hypothesis

    def _get_schema_instructions(self) -> str:
        """Add JSON schema instructions to prompt"""
        return """

        Return your hypothesis as JSON with this structure:
        {
            "title": "Short descriptive title",
            "summary": "2-3 sentence summary",
            "hypothesis_statement": "The core hypothesis claim",
            "rationale": "Scientific reasoning and background",
            "mechanism": "Proposed mechanism of action",
            "experimental_protocol": {
                "objective": "What the experiment tests",
                "methodology": "How to conduct the experiment",
                "controls": ["Control 1", "Control 2"],
                "expected_outcomes": ["Outcome 1", "Outcome 2"],
                "success_criteria": "How to determine success"
            },
            "citations": [
                {"title": "Paper title", "relevance": "Why relevant"}
            ]
        }
        """

    def _parse_hypothesis(
        self,
        response: str,
        research_goal_id: str,
        method: GenerationMethod
    ) -> Hypothesis:
        """Parse LLM response into Hypothesis object"""
        # Use robust JSON parser
        data = parse_llm_json(response)

        # Build experimental protocol
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
                title=c.get("title", "Unknown"),
                relevance=c.get("relevance", "")
            )
            for c in data.get("citations", [])
        ]

        # Create hypothesis with initial Elo rating
        # Per Google paper (p.11): "We set the initial Elo rating of 1200"
        return Hypothesis(
            id=generate_hypothesis_id(),
            research_goal_id=research_goal_id,
            title=data.get("title", "Untitled Hypothesis"),
            summary=data.get("summary", ""),
            hypothesis_statement=data.get("hypothesis_statement", ""),
            rationale=data.get("rationale", ""),
            mechanism=data.get("mechanism", ""),
            experimental_protocol=protocol,
            citations=citations,
            elo_rating=1200.0,  # Google paper specification
            status=HypothesisStatus.GENERATED,
            generation_method=method
        )

    async def _search_literature(self, query: str) -> str:
        """Search for relevant literature via web search"""
        from src.utils.web_search import TavilySearchClient
        from src.config import settings

        if not settings.tavily_api_key:
            return "No literature search configured."

        client = TavilySearchClient(settings.tavily_api_key)
        results = await client.search_scientific_literature(query)

        # Format results
        formatted = []
        for i, result in enumerate(results[:5], 1):
            formatted.append(
                f"[{i}] {result.get('title', 'Unknown')}\n"
                f"    {result.get('content', '')[:200]}..."
            )

        return "\n\n".join(formatted)
```

## Output Schema

The agent produces a `Hypothesis` object:

```python
class Hypothesis(BaseModel):
    id: str                          # hyp_YYYYMMDD_random
    research_goal_id: str            # Link to research goal
    title: str                       # Short descriptive title
    summary: str                     # 2-3 sentence summary
    hypothesis_statement: str        # Core claim
    rationale: str                   # Scientific reasoning
    mechanism: str                   # Proposed mechanism
    experimental_protocol: ExperimentalProtocol
    citations: List[Citation]
    elo_rating: float = 1200.0       # Initial Elo (per Google paper)
    status: HypothesisStatus
    generation_method: GenerationMethod
```

## Elo Rating

Per Google paper (Section 3.3.3):
> "We set the initial Elo rating of 1200 for the newly added hypothesis"

All generated hypotheses start at 1200.0 Elo.

## JSON Parsing

Uses robust parser from `src/utils/json_parser.py`:
- Extracts JSON from markdown code blocks
- Handles invalid escape sequences (e.g., `\e`, `\K`)
- Falls back to regex cleanup if standard parsing fails

## Usage

```python
from src.agents.generation import GenerationAgent
from src.llm.factory import get_llm_client
from schemas import ResearchGoal

# Create agent
client = get_llm_client(agent_name="generation")
agent = GenerationAgent(client)

# Define research goal
goal = ResearchGoal(
    id="goal_001",
    description="Identify drug repurposing candidates for AML",
    constraints=["FDA-approved drugs only"],
    preferences=["Prioritize testability"]
)

# Generate hypothesis
hypothesis = await agent.execute(
    research_goal=goal,
    method=GenerationMethod.LITERATURE_EXPLORATION,
    use_web_search=True
)

print(f"Generated: {hypothesis.title}")
print(f"Elo: {hypothesis.elo_rating}")
```

## Example Output

```json
{
    "id": "hyp_20260122_a1b2c3d4",
    "title": "KIRA6 as IRE1α Inhibitor for AML Treatment",
    "summary": "KIRA6 may inhibit AML proliferation through IRE1α pathway disruption",
    "hypothesis_statement": "KIRA6 inhibits IRE1α kinase activity, reducing AML cell viability",
    "rationale": "AML cells show elevated UPR signaling...",
    "mechanism": "KIRA6 binds IRE1α kinase domain, preventing XBP1 splicing...",
    "experimental_protocol": {
        "objective": "Test KIRA6 IC50 in MOLM13 cells",
        "methodology": "Cell viability assay with dose-response",
        "controls": ["Vehicle control", "Known IRE1α inhibitor"],
        "expected_outcomes": ["IC50 < 1µM", "Dose-dependent response"],
        "success_criteria": "IC50 comparable to clinical concentrations"
    },
    "citations": [
        {"title": "IRE1α in AML pathogenesis", "relevance": "Establishes target"}
    ],
    "elo_rating": 1200.0,
    "status": "generated",
    "generation_method": "literature_exploration"
}
```

## Testing

```python
@pytest.mark.asyncio
async def test_generation_agent():
    """Test hypothesis generation"""
    agent = GenerationAgent(get_llm_client())

    goal = ResearchGoal(
        id="test",
        description="Test drug repurposing",
        constraints=[],
        preferences=[]
    )

    hypothesis = await agent.execute(goal)

    assert hypothesis.id.startswith("hyp_")
    assert hypothesis.elo_rating == 1200.0
    assert hypothesis.status == HypothesisStatus.GENERATED
    assert len(hypothesis.title) > 0
```
