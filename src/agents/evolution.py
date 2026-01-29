"""Evolution Agent - Refine and improve hypotheses"""

from typing import Dict, Any, Optional
from pydantic import ValidationError
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, Review, EvolutionStrategy, ExperimentalProtocol, Citation

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.prompts.loader import prompt_manager
from src.utils.ids import generate_hypothesis_id
from src.utils.errors import CoScientistError
from src.config import settings
from src.observability.tracing import trace_agent
import json


class EvolutionAgent(BaseAgent):
    """Refine hypotheses through various evolution strategies"""

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.evolution_model,
            agent_name="evolution"
        )
        super().__init__(llm_client, "EvolutionAgent")

    @trace_agent("EvolutionAgent")
    def execute(
        self,
        hypothesis: Hypothesis,
        strategy: EvolutionStrategy,
        reviews: Optional[list[Review]] = None,
        similar_hypotheses: Optional[list[Hypothesis]] = None
    ) -> Hypothesis:
        """Evolve a hypothesis using specified strategy

        Args:
            hypothesis: Hypothesis to evolve
            strategy: Evolution strategy to apply
            reviews: Reviews of the hypothesis (for grounding/feasibility)
            similar_hypotheses: Similar hypotheses (for combination/out-of-box)

        Returns:
            Evolved hypothesis
        """

        self.log_execution(
            task="hypothesis_evolution",
            hypothesis_id=hypothesis.id,
            strategy=strategy.value
        )

        # Format prompt based on strategy
        if strategy in [EvolutionStrategy.GROUNDING, EvolutionStrategy.COHERENCE,
                        EvolutionStrategy.FEASIBILITY, EvolutionStrategy.SIMPLIFICATION]:
            # Use feasibility improvement prompt
            prompt = prompt_manager.format_evolution_prompt(
                hypothesis=self._format_hypothesis(hypothesis),
                strategy="feasibility",
                goal=hypothesis.research_goal_id,
                reviews=self._format_reviews(reviews) if reviews else ""
            )
        else:
            # Use out-of-box thinking prompt
            prompt = prompt_manager.format_evolution_prompt(
                hypothesis=self._format_hypothesis(hypothesis),
                strategy="out_of_box",
                goal=hypothesis.research_goal_id,
                similar_hypotheses=self._format_hypotheses(similar_hypotheses) if similar_hypotheses else ""
            )

        # Add structured output instruction
        structured_prompt = f"""{prompt}

IMPORTANT: Return your response as valid JSON matching this schema:
{{
    "title": "Brief hypothesis title",
    "statement": "Full hypothesis statement",
    "rationale": "Scientific reasoning",
    "mechanism": "Proposed mechanism",
    "experimental_protocol": {{
        "methodology": "Experimental approach",
        "controls": "Control conditions",
        "success_criteria": "What constitutes success"
    }},
    "citations": [
        {{"doi": "10.xxxx/xxxxx", "relevance": "Why this paper is relevant"}}
    ],
    "evolution_rationale": "Explanation of how this hypothesis was evolved from the original"
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

            # Build evolved Hypothesis object
            evolved_hypothesis = Hypothesis(
                id=generate_hypothesis_id(),
                research_goal_id=hypothesis.research_goal_id,
                title=data["title"],
                summary=hypothesis.summary,  # Keep original summary
                hypothesis_statement=data["statement"],
                rationale=data["rationale"],
                mechanism=data["mechanism"],
                experimental_protocol=ExperimentalProtocol(**data["experimental_protocol"]),
                citations=[Citation(**c) for c in data.get("citations", [])],
                generation_method=hypothesis.generation_method,
                parent_hypothesis_id=hypothesis.id,  # Track evolution lineage
                evolution_strategy=strategy,
                evolution_rationale=data.get("evolution_rationale", ""),
                elo_rating=hypothesis.elo_rating  # Inherit parent's Elo
            )

            self.logger.info(
                "Hypothesis evolved",
                original_id=hypothesis.id,
                evolved_id=evolved_hypothesis.id,
                strategy=strategy.value,
                title=evolved_hypothesis.title
            )

            return evolved_hypothesis

        except (json.JSONDecodeError, ValidationError, KeyError) as e:
            raise CoScientistError(f"Failed to parse LLM response: {e}\nResponse: {response[:500]}")

    def _format_hypothesis(self, hypothesis: Hypothesis) -> str:
        """Format hypothesis for prompt"""
        return f"""Title: {hypothesis.title}

Statement: {hypothesis.hypothesis_statement}

Rationale: {hypothesis.rationale}

Mechanism: {hypothesis.mechanism}

Experimental Protocol:
- Methodology: {hypothesis.experimental_protocol.methodology}
- Controls: {hypothesis.experimental_protocol.controls}
- Success Criteria: {hypothesis.experimental_protocol.success_criteria}
"""

    def _format_hypotheses(self, hypotheses: list[Hypothesis]) -> str:
        """Format multiple hypotheses for prompt"""
        formatted = []
        for i, hyp in enumerate(hypotheses, 1):
            formatted.append(f"""Hypothesis {i}:
{self._format_hypothesis(hyp)}
""")
        return "\n".join(formatted)

    def _format_reviews(self, reviews: list[Review]) -> str:
        """Format reviews for prompt"""
        formatted = []
        for i, review in enumerate(reviews, 1):
            formatted.append(f"""Review {i}:
- Passed: {review.passed}
- Correctness: {review.correctness_score}
- Quality: {review.quality_score}
- Novelty: {review.novelty_score}

Strengths: {', '.join(review.strengths) if review.strengths else 'N/A'}
Weaknesses: {', '.join(review.weaknesses) if review.weaknesses else 'N/A'}
Suggestions: {', '.join(review.suggestions) if review.suggestions else 'N/A'}
""")
        return "\n".join(formatted)
