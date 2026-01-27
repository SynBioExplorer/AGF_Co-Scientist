# Phase 2: Ranking Agent

## Overview

The Ranking Agent conducts pairwise hypothesis comparisons for Elo-based tournament ranking, determining winners based on novelty, correctness, testability, and feasibility.

**File:** `src/agents/ranking.py`
**Status:** ✅ Complete

## Capabilities

Based on Google AI Co-Scientist paper (Section 3.3.3):

1. **Pairwise Comparison** - Compare two hypotheses directly
2. **Multi-turn Scientific Debates** - Deep comparison for top hypotheses
3. **Winner Determination** - Clear decision with rationale
4. **Elo Calculation** - Rating changes based on outcome

## Implementation

```python
from typing import Optional, List
from src.agents.base import BaseAgent
from src.llm.base import BaseLLMClient
from src.prompts.loader import get_prompt_loader
from src.utils.ids import generate_match_id
from src.tournament.elo import EloCalculator
from schemas import (
    Hypothesis, Review, TournamentMatch, DebateTurn,
    ResearchGoal
)
import structlog

logger = structlog.get_logger()

class RankingAgent(BaseAgent):
    """Agent for tournament-based hypothesis ranking"""

    def __init__(self, llm_client: BaseLLMClient):
        super().__init__(llm_client, "RankingAgent")
        self.prompt_loader = get_prompt_loader()
        self.elo_calculator = EloCalculator()

    async def execute(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis,
        review_a: Review,
        review_b: Review,
        research_goal: ResearchGoal,
        multi_turn: bool = False
    ) -> TournamentMatch:
        """Compare two hypotheses in tournament match

        Args:
            hypothesis_a: First hypothesis
            hypothesis_b: Second hypothesis
            review_a: Review of first hypothesis
            review_b: Review of second hypothesis
            research_goal: Research goal for context
            multi_turn: Use multi-turn debate format

        Returns:
            TournamentMatch with winner and Elo changes
        """
        self.log_execution(
            task="tournament_match",
            hypothesis_a=hypothesis_a.id,
            hypothesis_b=hypothesis_b.id,
            multi_turn=multi_turn
        )

        # Run comparison (debate or single-turn)
        if multi_turn:
            winner_id, rationale, debate_turns = await self._run_multi_turn_debate(
                hypothesis_a, hypothesis_b,
                review_a, review_b,
                research_goal
            )
        else:
            winner_id, rationale = await self._run_single_comparison(
                hypothesis_a, hypothesis_b,
                review_a, review_b,
                research_goal
            )
            debate_turns = []

        # Calculate Elo changes
        winner_is_a = winner_id == hypothesis_a.id
        elo_change_a, elo_change_b = self.elo_calculator.calculate_rating_change(
            rating_a=hypothesis_a.elo_rating,
            rating_b=hypothesis_b.elo_rating,
            winner_is_a=winner_is_a
        )

        match = TournamentMatch(
            id=generate_match_id(),
            hypothesis_a_id=hypothesis_a.id,
            hypothesis_b_id=hypothesis_b.id,
            winner_id=winner_id,
            decision_rationale=rationale,
            elo_change_a=elo_change_a,
            elo_change_b=elo_change_b,
            debate_turns=debate_turns
        )

        logger.info(
            "Tournament match completed",
            match_id=match.id,
            winner=winner_id,
            elo_change_a=elo_change_a,
            elo_change_b=elo_change_b
        )

        return match

    async def _run_single_comparison(
        self,
        hyp_a: Hypothesis,
        hyp_b: Hypothesis,
        rev_a: Review,
        rev_b: Review,
        goal: ResearchGoal
    ) -> tuple[str, str]:
        """Single-turn pairwise comparison"""

        prompt = self.prompt_loader.get_ranking_tournament_prompt(
            hypothesis_1=self._format_hypothesis(hyp_a),
            hypothesis_2=self._format_hypothesis(hyp_b),
            review_1=self._format_review(rev_a),
            review_2=self._format_review(rev_b),
            goal=goal.description,
            preferences=", ".join(goal.preferences),
            idea_attributes="novelty, correctness, testability, feasibility"
        )

        prompt += """

        Compare these hypotheses and determine which is better.

        Return JSON:
        {
            "winner": 1 or 2,
            "rationale": "Why this hypothesis is better"
        }
        """

        response = await self.llm_client.generate(prompt)
        data = parse_llm_json(response)

        winner_num = data.get("winner", 1)
        winner_id = hyp_a.id if winner_num == 1 else hyp_b.id
        rationale = data.get("rationale", "")

        return winner_id, rationale

    async def _run_multi_turn_debate(
        self,
        hyp_a: Hypothesis,
        hyp_b: Hypothesis,
        rev_a: Review,
        rev_b: Review,
        goal: ResearchGoal,
        num_turns: int = 3
    ) -> tuple[str, str, List[DebateTurn]]:
        """Multi-turn scientific debate for deeper comparison"""

        debate_turns = []
        context = ""

        for turn_num in range(1, num_turns + 1):
            # Hypothesis A argues
            turn_a = await self._generate_debate_turn(
                hypothesis=hyp_a,
                opponent=hyp_b,
                context=context,
                turn_number=turn_num,
                goal=goal
            )
            debate_turns.append(turn_a)
            context += f"\n\nTurn {turn_num} - Hypothesis A:\n{turn_a.argument}"

            # Hypothesis B argues
            turn_b = await self._generate_debate_turn(
                hypothesis=hyp_b,
                opponent=hyp_a,
                context=context,
                turn_number=turn_num,
                goal=goal
            )
            debate_turns.append(turn_b)
            context += f"\n\nTurn {turn_num} - Hypothesis B:\n{turn_b.argument}"

        # Final judgment
        winner_id, rationale = await self._judge_debate(
            hyp_a, hyp_b, debate_turns, goal
        )

        return winner_id, rationale, debate_turns

    async def _generate_debate_turn(
        self,
        hypothesis: Hypothesis,
        opponent: Hypothesis,
        context: str,
        turn_number: int,
        goal: ResearchGoal
    ) -> DebateTurn:
        """Generate one debate turn"""

        prompt = f"""
        You are arguing for this hypothesis:
        {self._format_hypothesis(hypothesis)}

        Against this opponent:
        {self._format_hypothesis(opponent)}

        Research goal: {goal.description}

        Prior debate:
        {context or "This is the first turn."}

        Generate argument for turn {turn_number}:
        - Address opponent's points if any
        - Cite supporting literature
        - Highlight your hypothesis's strengths

        Return JSON:
        {{
            "argument": "2-3 paragraph argument",
            "counterpoints": ["point1", "point2"]
        }}
        """

        response = await self.llm_client.generate(prompt)
        data = parse_llm_json(response)

        return DebateTurn(
            hypothesis_id=hypothesis.id,
            turn_number=turn_number,
            argument=data.get("argument", ""),
            counterpoints=data.get("counterpoints", [])
        )

    def _format_hypothesis(self, hyp: Hypothesis) -> str:
        """Format hypothesis for prompt"""
        return f"""
        Title: {hyp.title}
        Statement: {hyp.hypothesis_statement}
        Rationale: {hyp.rationale}
        Mechanism: {hyp.mechanism}
        Elo Rating: {hyp.elo_rating}
        """

    def _format_review(self, rev: Review) -> str:
        """Format review for prompt"""
        return f"""
        Quality: {rev.quality_score}
        Novelty: {rev.novelty_score}
        Testability: {rev.testability_score}
        Strengths: {', '.join(rev.strengths)}
        Weaknesses: {', '.join(rev.weaknesses)}
        """
```

## Elo Rating Changes

The Ranking Agent calculates Elo changes using standard formulas:

- **K-factor:** 32 (standard for new players)
- **Expected score:** `1 / (1 + 10^((opponent_rating - player_rating) / 400))`
- **Rating change:** `K * (actual_score - expected_score)`

Example:
- Hypothesis A (1200) beats Hypothesis B (1200)
- Expected: 0.5 vs 0.5
- Actual: 1.0 vs 0.0
- Change: +16 for A, -16 for B

## Multi-turn Debate Format

For top-ranked hypotheses (Elo > 1300 or rank < 5):

```
Turn 1: Hypothesis A argues → Hypothesis B responds
Turn 2: Hypothesis A argues → Hypothesis B responds
Turn 3: Hypothesis A argues → Hypothesis B responds
Final: Judge determines winner based on debate
```

## Output Schema

```python
class TournamentMatch(BaseModel):
    id: str                      # match_YYYYMMDD_random
    hypothesis_a_id: str
    hypothesis_b_id: str
    winner_id: str
    decision_rationale: str
    elo_change_a: float          # Change for hypothesis A
    elo_change_b: float          # Change for hypothesis B
    debate_turns: List[DebateTurn]  # Empty if single-turn

class DebateTurn(BaseModel):
    hypothesis_id: str           # Which hypothesis argued
    turn_number: int
    argument: str                # 2-3 paragraphs
    counterpoints: List[str]     # Against opponent
```

## Usage

```python
from src.agents.ranking import RankingAgent
from src.llm.factory import get_llm_client

agent = RankingAgent(get_llm_client())

match = await agent.execute(
    hypothesis_a=hyp_a,
    hypothesis_b=hyp_b,
    review_a=rev_a,
    review_b=rev_b,
    research_goal=goal,
    multi_turn=True  # Use debate format
)

print(f"Winner: {match.winner_id}")
print(f"Rationale: {match.decision_rationale}")
print(f"Elo change A: {match.elo_change_a:+.1f}")
```

## Testing

```python
@pytest.mark.asyncio
async def test_ranking_agent():
    """Test tournament comparison"""
    agent = RankingAgent(get_llm_client())

    match = await agent.execute(
        hypothesis_a=hyp_a,
        hypothesis_b=hyp_b,
        review_a=rev_a,
        review_b=rev_b,
        research_goal=goal
    )

    assert match.winner_id in [hyp_a.id, hyp_b.id]
    assert match.elo_change_a + match.elo_change_b == 0  # Zero-sum
```
