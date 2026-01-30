"""Observation Review Agent - Validate hypotheses against literature observations (Phase 6 Week 3)"""

from typing import List, Optional
import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import (
    Hypothesis,
    Observation,
    ObservationExplanation,
    ObservationReviewScore,
    ObservationType,
    ResearchGoal
)

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.utils.ids import generate_id
from src.utils.errors import CoScientistError
from src.utils.json_parser import parse_llm_json
from src.config import settings
from src.observability.tracing import trace_agent
from src.literature.citation_graph import CitationGraph
import structlog

logger = structlog.get_logger()


class ObservationReviewAgent(BaseAgent):
    """
    Validate hypotheses against observations from scientific literature.

    Implements "Observation Review" from Google paper - evaluates how well
    hypotheses explain concrete experimental findings, clinical results, and
    mechanistic observations from the literature.
    """

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.reflection_model,  # Use reflection model for critical analysis
            agent_name="observation_review"
        )
        super().__init__(llm_client, "ObservationReviewAgent")

    def extract_observations_from_papers(
        self,
        citation_graph: CitationGraph,
        research_goal: ResearchGoal,
        max_observations: int = 20
    ) -> List[Observation]:
        """
        Extract key observations from papers in the citation graph.

        Args:
            citation_graph: Citation graph containing papers
            research_goal: Research goal for context
            max_observations: Maximum number of observations to extract

        Returns:
            List of Observation objects
        """
        observations = []

        # Sort papers by citation count (prioritize high-impact papers)
        papers = sorted(
            citation_graph.nodes.values(),
            key=lambda p: p.citation_count,
            reverse=True
        )[:max_observations]

        for paper in papers:
            # Extract observation from abstract or key findings
            # For now, create observations from paper metadata
            # In production, this would use NLP to extract from full text

            if paper.abstract:
                # Create observation from abstract
                observation = Observation(
                    id=generate_id("obs"),
                    paper_id=paper.doi or paper.pmid or paper.id,
                    paper_title=paper.title,
                    observation_type=self._infer_observation_type(paper.abstract),
                    text=self._extract_key_finding(paper.abstract),
                    context=paper.abstract[:300],  # First 300 chars as context
                    relevance_score=self._calculate_relevance(paper, research_goal),
                    citation_count=paper.citation_count
                )
                observations.append(observation)

        self.logger.info(
            "Observations extracted from citation graph",
            num_observations=len(observations),
            num_papers=len(papers)
        )

        return observations

    def _infer_observation_type(self, abstract: str) -> ObservationType:
        """Infer observation type from abstract text."""
        abstract_lower = abstract.lower()

        # Simple keyword-based classification
        if any(word in abstract_lower for word in ["clinical trial", "patient", "clinical study"]):
            return ObservationType.CLINICAL
        elif any(word in abstract_lower for word in ["experiment", "assay", "measured"]):
            return ObservationType.EXPERIMENTAL
        elif any(word in abstract_lower for word in ["dataset", "database", "cohort"]):
            return ObservationType.DATASET
        elif any(word in abstract_lower for word in ["mechanism", "pathway", "signaling"]):
            return ObservationType.MECHANISM
        elif any(word in abstract_lower for word in ["result", "finding", "showed"]):
            return ObservationType.RESULT
        else:
            return ObservationType.PHENOMENON

    def _extract_key_finding(self, abstract: str) -> str:
        """Extract key finding from abstract (simplified version)."""
        # In production, use NLP to extract the main finding
        # For now, return first sentence that contains result indicators
        sentences = abstract.split('. ')
        for sentence in sentences:
            if any(word in sentence.lower() for word in ["showed", "demonstrated", "found", "revealed", "resulted"]):
                return sentence.strip()

        # Fallback: return first sentence
        return sentences[0].strip() if sentences else abstract[:200]

    def _calculate_relevance(self, paper, research_goal: ResearchGoal) -> float:
        """Calculate relevance of paper to research goal (simplified)."""
        # In production, use embeddings for semantic similarity
        # For now, simple keyword matching
        goal_lower = research_goal.description.lower()
        title_lower = paper.title.lower()

        # Count overlapping keywords
        goal_keywords = set(word for word in goal_lower.split() if len(word) > 4)
        title_keywords = set(word for word in title_lower.split() if len(word) > 4)

        if not goal_keywords:
            return 0.5  # Default relevance

        overlap = len(goal_keywords & title_keywords)
        relevance = min(1.0, overlap / len(goal_keywords))

        return relevance

    def _load_observation_review_prompt(self) -> str:
        """Load observation review prompt template."""
        prompt_path = settings.prompts_dir / "03_Observation_Review_Agent.txt"
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _format_observations_for_prompt(self, observations: List[Observation]) -> str:
        """Format observations as context for LLM prompt."""
        formatted = []

        for i, obs in enumerate(observations, 1):
            formatted.append(
                f"**Observation {i}** (ID: {obs.id})\n"
                f"Source: {obs.paper_title}\n"
                f"Type: {obs.observation_type.value}\n"
                f"Citation Count: {obs.citation_count}\n"
                f"Finding: {obs.text}\n"
                f"Context: {obs.context}\n"
            )

        return "\n\n".join(formatted)

    @trace_agent("ObservationReviewAgent")
    async def execute(
        self,
        hypothesis: Hypothesis,
        observations: List[Observation],
        research_goal: ResearchGoal
    ) -> ObservationReviewScore:
        """
        Evaluate how well hypothesis explains observations.

        Args:
            hypothesis: Hypothesis to evaluate
            observations: List of observations to check against
            research_goal: Research goal for context

        Returns:
            ObservationReviewScore with detailed evaluation
        """
        self.log_execution(
            task="observation_review",
            hypothesis_id=hypothesis.id,
            num_observations=len(observations)
        )

        # Format prompt
        template = self._load_observation_review_prompt()
        observations_text = self._format_observations_for_prompt(observations)

        prompt = template.format(
            goal=research_goal.description,
            hypothesis_title=hypothesis.title,
            hypothesis_statement=hypothesis.hypothesis_statement,
            mechanism=hypothesis.mechanism or "Not specified",
            rationale=hypothesis.rationale,
            observations=observations_text
        )

        # Add structured output instruction
        structured_prompt = f"""{prompt}

IMPORTANT: Return ONLY valid JSON matching the schema shown above. Do not include any text before or after the JSON."""

        # Call LLM (using asyncio.to_thread for sync LLM client)
        import asyncio
        response = await asyncio.to_thread(self.llm_client.invoke, structured_prompt)

        # Parse response
        try:
            data = parse_llm_json(response)

            # Create ObservationExplanation objects
            explanations = []
            for exp_data in data.get("explanations", []):
                explanation = ObservationExplanation(
                    observation_id=exp_data["observation_id"],
                    hypothesis_id=hypothesis.id,
                    explains=exp_data["explains"],
                    explanation_score=exp_data["explanation_score"],
                    reasoning=exp_data["reasoning"],
                    mechanism_match=exp_data.get("mechanism_match", False),
                    prediction_match=exp_data.get("prediction_match", False)
                )
                explanations.append(explanation)

            # Create review score
            review_score = ObservationReviewScore(
                id=generate_id("obs_review"),
                hypothesis_id=hypothesis.id,
                research_goal_id=research_goal.id,
                observations=observations,
                explanations=explanations,
                overall_score=data["overall_score"],
                observations_explained_count=data["observations_explained_count"],
                observations_total_count=data["observations_total_count"],
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                summary=data["summary"]
            )

            self.logger.info(
                "Observation review completed",
                hypothesis_id=hypothesis.id,
                overall_score=review_score.overall_score,
                explained_count=review_score.observations_explained_count,
                total_count=review_score.observations_total_count
            )

            return review_score

        except (json.JSONDecodeError, KeyError) as e:
            raise CoScientistError(
                f"Failed to parse observation review response: {e}\nResponse: {response[:500]}"
            )

    @trace_agent("ObservationReviewAgent")
    async def execute_with_citation_graph(
        self,
        hypothesis: Hypothesis,
        citation_graph: CitationGraph,
        research_goal: ResearchGoal,
        max_observations: int = 20
    ) -> ObservationReviewScore:
        """
        Execute observation review using citation graph.

        Convenience method that extracts observations from citation graph
        and performs the review.

        Args:
            hypothesis: Hypothesis to evaluate
            citation_graph: Citation graph with papers
            research_goal: Research goal for context
            max_observations: Maximum observations to extract

        Returns:
            ObservationReviewScore
        """
        # Extract observations from graph
        observations = self.extract_observations_from_papers(
            citation_graph,
            research_goal,
            max_observations
        )

        if not observations:
            self.logger.warning(
                "No observations extracted from citation graph",
                hypothesis_id=hypothesis.id
            )
            # Return empty review
            return ObservationReviewScore(
                id=generate_id("obs_review"),
                hypothesis_id=hypothesis.id,
                research_goal_id=research_goal.id,
                observations=[],
                explanations=[],
                overall_score=0.0,
                observations_explained_count=0,
                observations_total_count=0,
                strengths=[],
                weaknesses=["No observations available for review"],
                summary="Unable to perform observation review - no observations extracted from citation graph."
            )

        # Perform review
        return await self.execute(hypothesis, observations, research_goal)
