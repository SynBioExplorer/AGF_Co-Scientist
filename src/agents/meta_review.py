"""Meta-review Agent - Synthesize feedback patterns"""

from typing import List
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import (
    Review, TournamentMatch, MetaReviewCritique, ResearchOverview,
    ResearchDirection, ResearchContact, Hypothesis
)

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.prompts.loader import prompt_manager
from src.config import settings
from src.utils.errors import CoScientistError
from src.utils.ids import generate_id
import json


class MetaReviewAgent(BaseAgent):
    """Synthesize feedback patterns and generate research overviews"""

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.meta_review_model,
            agent_name="meta_review"
        )
        super().__init__(llm_client, "MetaReviewAgent")

    def execute(
        self,
        reviews: List[Review],
        matches: List[TournamentMatch],
        goal: str,
        preferences: List[str] = None,
        instructions: str = ""
    ) -> MetaReviewCritique:
        """Generate meta-review from reviews and tournament results

        Args:
            reviews: All reviews to synthesize
            matches: Tournament match results
            goal: Research goal description
            preferences: User preferences
            instructions: Additional instructions

        Returns:
            MetaReviewCritique with synthesized feedback
        """

        self.log_execution(
            task="meta_review_generation",
            num_reviews=len(reviews),
            num_matches=len(matches)
        )

        # Format reviews and tournament results
        reviews_text = self._format_reviews(reviews)
        tournament_text = self._format_tournament_results(matches)

        # Format prompt
        prompt = prompt_manager.format_meta_review_prompt(
            goal=goal,
            preferences="\n".join(f"- {p}" for p in preferences) if preferences else "Standard scientific rigor",
            instructions=instructions,
            reviews=reviews_text
        )

        # Add tournament context
        full_prompt = f"""{prompt}

Tournament Results Summary:
{tournament_text}

IMPORTANT: Return your response as valid JSON matching this schema:
{{
    "recurring_strengths": ["strength1", "strength2", ...],
    "recurring_weaknesses": ["weakness1", "weakness2", ...],
    "improvement_opportunities": ["opportunity1", "opportunity2", ...],
    "generation_feedback": ["feedback1", "feedback2", ...],
    "reflection_feedback": ["feedback1", "feedback2", ...],
    "evolution_feedback": ["feedback1", "feedback2", ...]
}}

Respond with ONLY the JSON object, no additional text."""

        # Invoke LLM
        response = self.llm_client.invoke(full_prompt)

        # Parse response
        try:
            # Extract JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # Build MetaReviewCritique
            meta_review = MetaReviewCritique(
                id=generate_id("meta_review"),
                research_goal_id=goal,  # Use goal description as ID for now
                recurring_strengths=data.get("recurring_strengths", []),
                recurring_weaknesses=data.get("recurring_weaknesses", []),
                improvement_opportunities=data.get("improvement_opportunities", []),
                generation_feedback=data.get("generation_feedback", []),
                reflection_feedback=data.get("reflection_feedback", []),
                evolution_feedback=data.get("evolution_feedback", [])
            )

            self.logger.info(
                "Meta-review generated",
                num_strengths=len(meta_review.recurring_strengths),
                num_weaknesses=len(meta_review.recurring_weaknesses),
                num_improvements=len(meta_review.improvement_opportunities)
            )

            return meta_review

        except (json.JSONDecodeError, KeyError) as e:
            raise CoScientistError(f"Failed to parse meta-review response: {e}\nResponse: {response[:500]}")

    def generate_research_overview(
        self,
        goal: str,
        top_hypotheses: List[Hypothesis],
        meta_review: MetaReviewCritique,
        preferences: List[str] = None,
        research_goal_id: str = None
    ) -> ResearchOverview:
        """Generate comprehensive research overview

        Args:
            goal: Research goal description
            top_hypotheses: Top-ranked hypotheses
            meta_review: Meta-review critique
            preferences: User preferences

        Returns:
            ResearchOverview with directions and recommendations
        """

        self.log_execution(
            task="research_overview_generation",
            num_hypotheses=len(top_hypotheses)
        )

        # Format top hypotheses
        hypotheses_text = "\n\n".join([
            f"Hypothesis {i+1} (Elo: {h.elo_rating:.1f}):\n"
            f"Title: {h.title}\n"
            f"Statement: {h.hypothesis_statement[:200]}...\n"
            f"Mechanism: {h.mechanism[:150]}..."
            for i, h in enumerate(top_hypotheses)
        ])

        prompt = f"""Generate a comprehensive research overview for the following goal:

Goal: {goal}

Preferences:
{chr(10).join(f"- {p}" for p in preferences) if preferences else "Standard scientific rigor"}

Top Hypotheses:
{hypotheses_text}

Meta-Review Insights:
- Recurring Strengths: {', '.join(meta_review.recurring_strengths)}
- Recurring Weaknesses: {', '.join(meta_review.recurring_weaknesses)}
- Improvement Opportunities: {', '.join(meta_review.improvement_opportunities)}

Based on this analysis, provide:

1. Summary of key findings (2-3 paragraphs)
2. Promising research directions (3-5 directions with rationale)
3. Suggested domain experts to consult (3-5 experts with specializations)
4. Recommended next steps

Return ONLY a JSON object:
{{
    "executive_summary": "Comprehensive 2-3 paragraph summary of key findings",
    "current_knowledge_boundary": "What we currently know vs. what remains unknown in this research area",
    "research_directions": [
        {{
            "name": "Direction name",
            "description": "What to explore",
            "justification": "Why this is promising",
            "suggested_experiments": ["exp1", "exp2"],
            "example_topics": ["topic1", "topic2"],
            "related_hypothesis_ids": []
        }}
    ],
    "suggested_contacts": [
        {{
            "name": "Dr. [Name] or [Institution]",
            "affiliation": "Institution name",
            "expertise": ["expertise1", "expertise2"],
            "relevance_reasoning": "Why this expert is relevant",
            "publications": []
        }}
    ],
    "recommended_next_steps": ["step1", "step2", "step3"]
}}

Respond with ONLY the JSON object, no additional text."""

        # Invoke LLM
        response = self.llm_client.invoke(prompt)

        # Parse response
        try:
            # Extract JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # Build ResearchOverview
            overview = ResearchOverview(
                id=generate_id("overview"),
                research_goal_id=research_goal_id or goal,
                executive_summary=data.get("executive_summary", ""),
                current_knowledge_boundary=data.get("current_knowledge_boundary", ""),
                research_directions=[
                    ResearchDirection(**d) for d in data.get("research_directions", [])
                ],
                top_hypotheses=top_hypotheses,
                suggested_contacts=[
                    ResearchContact(**c) for c in data.get("suggested_contacts", [])
                ],
                recommended_next_steps=data.get("recommended_next_steps", [])
            )

            self.logger.info(
                "Research overview generated",
                num_directions=len(overview.research_directions),
                num_contacts=len(overview.suggested_contacts)
            )

            return overview

        except (json.JSONDecodeError, KeyError) as e:
            raise CoScientistError(f"Failed to parse overview response: {e}\nResponse: {response[:500]}")

    def _format_reviews(self, reviews: List[Review]) -> str:
        """Format reviews for prompt"""
        formatted = []
        for i, review in enumerate(reviews, 1):
            formatted.append(f"""Review {i}:
- Hypothesis ID: {review.hypothesis_id}
- Type: {review.review_type.value}
- Passed: {review.passed}
- Scores: Correctness={review.correctness_score}, Quality={review.quality_score}, Novelty={review.novelty_score}
- Strengths: {', '.join(review.strengths) if review.strengths else 'N/A'}
- Weaknesses: {', '.join(review.weaknesses) if review.weaknesses else 'N/A'}
- Rationale: {review.rationale[:200]}...
""")
        return "\n".join(formatted[:20])  # Limit to 20 reviews to avoid context overflow

    def _format_tournament_results(self, matches: List[TournamentMatch]) -> str:
        """Format tournament results for prompt"""
        formatted = []
        for i, match in enumerate(matches, 1):
            formatted.append(f"""Match {i}:
- Hypotheses: {match.hypothesis_a_id} vs {match.hypothesis_b_id}
- Winner: {match.winner_id}
- Elo Changes: A={match.elo_change_a:.1f}, B={match.elo_change_b:.1f}
- Rationale: {match.decision_rationale[:150]}...
""")
        return "\n".join(formatted[:15])  # Limit to 15 matches
