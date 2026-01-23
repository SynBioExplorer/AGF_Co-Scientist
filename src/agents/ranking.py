"""Ranking Agent - Pairwise hypothesis comparison with Elo updates"""

from typing import Dict, Any, Optional
from pydantic import ValidationError as PydanticValidationError
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, TournamentMatch, DebateTurn

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.prompts.loader import prompt_manager
from src.utils.ids import generate_match_id
from src.utils.errors import CoScientistError
from src.config import settings
import json


class RankingAgent(BaseAgent):
    """Compare hypotheses and determine winners for Elo ranking"""

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.ranking_model,
            agent_name="ranking"
        )
        super().__init__(llm_client, "RankingAgent")

    def execute(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis,
        method: str = "tournament",  # "tournament" or "debate"
        multi_turn: bool = False,
        goal: str = ""
    ) -> TournamentMatch:
        """Compare two hypotheses and determine winner

        Args:
            hypothesis_a: First hypothesis to compare
            hypothesis_b: Second hypothesis to compare
            method: Comparison method ("tournament" or "debate")
            multi_turn: Whether to use multi-turn debate (for top-ranked hypotheses)

        Returns:
            TournamentMatch with winner and Elo changes
        """

        self.log_execution(
            task="hypothesis_comparison",
            hypothesis_a_id=hypothesis_a.id,
            hypothesis_b_id=hypothesis_b.id,
            method=method,
            multi_turn=multi_turn
        )

        # Format prompt
        prompt = prompt_manager.format_ranking_prompt(
            hypothesis_a=self._format_hypothesis(hypothesis_a),
            hypothesis_b=self._format_hypothesis(hypothesis_b),
            method=method,
            goal=goal or "Compare hypotheses for tournament ranking"
        )

        # Add structured output instruction
        structured_prompt = f"""{prompt}

IMPORTANT: Return your response as valid JSON matching this schema:
{{
    "winner_id": "{hypothesis_a.id}" or "{hypothesis_b.id}",
    "decision_rationale": "Detailed reasoning for choosing the winner",
    "comparison_criteria": ["novelty", "correctness", "testability", "feasibility"]
}}

Respond with ONLY the JSON object, no additional text."""

        # Invoke LLM
        response = self.llm_client.invoke(structured_prompt)

        # Parse response
        try:
            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # Validate winner_id
            winner_id = data["winner_id"]
            if winner_id not in [hypothesis_a.id, hypothesis_b.id]:
                raise CoScientistError(f"Invalid winner_id: {winner_id}")

            # Debate turns will be added in Phase 3
            debate_turns = []

            # Calculate Elo changes (basic implementation - will be improved with tournament module)
            k_factor = 32  # Standard Elo K-factor
            expected_a = 1 / (1 + 10 ** ((hypothesis_b.elo_rating - hypothesis_a.elo_rating) / 400))
            expected_b = 1 - expected_a

            if winner_id == hypothesis_a.id:
                elo_change_a = k_factor * (1 - expected_a)
                elo_change_b = k_factor * (0 - expected_b)
            else:
                elo_change_a = k_factor * (0 - expected_a)
                elo_change_b = k_factor * (1 - expected_b)

            # Build TournamentMatch object
            match = TournamentMatch(
                id=generate_match_id(),
                hypothesis_a_id=hypothesis_a.id,
                hypothesis_b_id=hypothesis_b.id,
                debate_turns=debate_turns,
                is_multi_turn=multi_turn,
                winner_id=winner_id,
                decision_rationale=data["decision_rationale"],
                comparison_criteria=data.get("comparison_criteria", []),
                elo_change_a=elo_change_a,
                elo_change_b=elo_change_b
            )

            self.logger.info(
                "Match completed",
                match_id=match.id,
                winner_id=winner_id,
                elo_change_a=elo_change_a,
                elo_change_b=elo_change_b
            )

            return match

        except (json.JSONDecodeError, PydanticValidationError, KeyError) as e:
            raise CoScientistError(f"Failed to parse LLM response: {e}\nResponse: {response[:500]}")

    def _format_hypothesis(self, hypothesis: Hypothesis) -> str:
        """Format hypothesis for prompt"""
        citations_str = "\n".join([
            f"- {c.title} ({c.doi}): {c.relevance}"
            for c in hypothesis.literature_citations
        ]) if hypothesis.literature_citations else "None"

        return f"""
**Hypothesis {hypothesis.id}**
Title: {hypothesis.title}
Statement: {hypothesis.hypothesis_statement}
Rationale: {hypothesis.rationale}
Mechanism: {hypothesis.mechanism or 'Not specified'}
Current Elo Rating: {hypothesis.elo_rating}

Experimental Protocol:
- Objective: {hypothesis.experimental_protocol.objective if hypothesis.experimental_protocol else 'Not specified'}
- Methodology: {hypothesis.experimental_protocol.methodology if hypothesis.experimental_protocol else 'Not specified'}
- Success Criteria: {hypothesis.experimental_protocol.success_criteria if hypothesis.experimental_protocol else 'Not specified'}

Supporting Literature:
{citations_str}
        """.strip()
