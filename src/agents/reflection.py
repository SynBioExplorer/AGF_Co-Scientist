"""Reflection Agent - Review and score hypotheses"""

from typing import Dict, Any
from pydantic import ValidationError as PydanticValidationError
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, Review, ReviewType

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.prompts.loader import prompt_manager
from src.utils.ids import generate_review_id
from src.utils.errors import CoScientistError
from src.config import settings
import json


class ReflectionAgent(BaseAgent):
    """Review hypotheses and provide detailed assessments"""

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.reflection_model,
            agent_name="reflection"
        )
        super().__init__(llm_client, "ReflectionAgent")

    def execute(
        self,
        hypothesis: Hypothesis,
        review_type: ReviewType = ReviewType.INITIAL,
        article: str = ""
    ) -> Review:
        """Review a hypothesis

        Args:
            hypothesis: The hypothesis to review
            review_type: Type of review to perform
            article: Optional article text for observation review

        Returns:
            Review object with scores and feedback
        """

        self.log_execution(
            task="hypothesis_review",
            hypothesis_id=hypothesis.id,
            review_type=review_type.value
        )

        # Format prompt based on review type
        if review_type == ReviewType.OBSERVATION:
            prompt = prompt_manager.format_reflection_prompt(
                goal=hypothesis.hypothesis_statement,
                hypothesis=self._format_hypothesis(hypothesis),
                article=article
            )
        else:
            # For initial review, just evaluate the hypothesis directly
            prompt = self._create_initial_review_prompt(hypothesis)

        # Add structured output instruction
        structured_prompt = f"""{prompt}

IMPORTANT: Return your response as valid JSON matching this schema:
{{
    "passed": true/false,
    "rationale": "Detailed reasoning for decision",
    "correctness_score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "novelty_score": 0.0-1.0,
    "testability_score": 0.0-1.0,
    "safety_score": 0.0-1.0,
    "strengths": ["Strength 1", "Strength 2"],
    "weaknesses": ["Weakness 1", "Weakness 2"],
    "suggestions": ["Suggestion 1", "Suggestion 2"],
    "critiques": ["Critique 1", "Critique 2"],
    "known_aspects": ["Known aspect 1"],
    "novel_aspects": ["Novel aspect 1"],
    "explained_observations": ["Observation 1"]
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

            # Build Review object
            review = Review(
                id=generate_review_id(),
                hypothesis_id=hypothesis.id,
                review_type=review_type,
                passed=data["passed"],
                rationale=data["rationale"],
                correctness_score=data.get("correctness_score"),
                quality_score=data.get("quality_score"),
                novelty_score=data.get("novelty_score"),
                testability_score=data.get("testability_score"),
                safety_score=data.get("safety_score"),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                suggestions=data.get("suggestions", []),
                critiques=data.get("critiques", []),
                known_aspects=data.get("known_aspects", []),
                novel_aspects=data.get("novel_aspects", []),
                explained_observations=data.get("explained_observations", [])
            )

            self.logger.info(
                "Review completed",
                review_id=review.id,
                hypothesis_id=hypothesis.id,
                passed=review.passed,
                quality_score=review.quality_score
            )

            return review

        except (json.JSONDecodeError, PydanticValidationError, KeyError) as e:
            raise CoScientistError(f"Failed to parse LLM response: {e}\nResponse: {response[:500]}")

    def _format_hypothesis(self, hypothesis: Hypothesis) -> str:
        """Format hypothesis for prompt"""
        return f"""
Title: {hypothesis.title}
Statement: {hypothesis.hypothesis_statement}
Rationale: {hypothesis.rationale}
Mechanism: {hypothesis.mechanism or 'Not specified'}
        """.strip()

    def _create_initial_review_prompt(self, hypothesis: Hypothesis) -> str:
        """Create prompt for initial review without external tools"""
        return f"""You are an expert scientific reviewer. Please evaluate the following hypothesis:

{self._format_hypothesis(hypothesis)}

Experimental Protocol:
- Objective: {hypothesis.experimental_protocol.objective if hypothesis.experimental_protocol else 'Not specified'}
- Methodology: {hypothesis.experimental_protocol.methodology if hypothesis.experimental_protocol else 'Not specified'}

Assess the hypothesis on the following criteria:
1. **Correctness**: Is it scientifically sound?
2. **Quality**: Is it well-formulated and clear?
3. **Novelty**: Does it offer new insights?
4. **Testability**: Can it be experimentally tested?
5. **Safety**: Are there ethical or safety concerns?

For each criterion, provide:
- A score from 0.0 (poor) to 1.0 (excellent)
- Specific strengths and weaknesses
- Constructive suggestions for improvement

Determine if the hypothesis PASSES this initial review (true/false) and provide detailed rationale.
"""
