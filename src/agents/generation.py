"""Generation Agent - Create hypotheses via literature exploration or debate"""

from typing import Dict, Any
from pydantic import ValidationError as PydanticValidationError
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, ResearchGoal, Citation, ExperimentalProtocol, GenerationMethod

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.prompts.loader import prompt_manager
from src.utils.ids import generate_hypothesis_id
from src.utils.errors import CoScientistError
from src.utils.web_search import get_search_client
from src.config import settings
import json


class GenerationAgent(BaseAgent):
    """Generate hypotheses via literature exploration or simulated debate"""

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.generation_model,
            agent_name="generation"
        )
        super().__init__(llm_client, "GenerationAgent")

    def execute(
        self,
        research_goal: ResearchGoal,
        method: GenerationMethod = GenerationMethod.LITERATURE_EXPLORATION,
        use_web_search: bool = False
    ) -> Hypothesis:
        """Generate a hypothesis

        Args:
            research_goal: Research goal to address
            method: Generation method (literature or debate)
            use_web_search: Whether to perform web search for literature context

        Returns:
            Generated Hypothesis
        """

        self.log_execution(
            task="hypothesis_generation",
            goal=research_goal.description[:100],
            method=method.value,
            web_search=use_web_search
        )

        # Optionally search for literature
        articles_with_reasoning = ""
        if use_web_search and settings.tavily_api_key:
            try:
                search_client = get_search_client()
                results = search_client.search_scientific_literature(
                    query=research_goal.description,
                    max_results=5
                )

                articles_with_reasoning = "\n\n".join([
                    f"**Article {i+1}:** {r['title']}\n"
                    f"URL: {r['url']}\n"
                    f"Content: {r['content'][:300]}..."
                    for i, r in enumerate(results) if r['url']  # Skip AI summary
                ])

                self.logger.info(
                    "Literature search completed",
                    num_articles=len(results)
                )

            except Exception as e:
                self.logger.warning(
                    "Literature search failed, proceeding without",
                    error=str(e)
                )

        # Format prompt
        method_str = "literature" if method == GenerationMethod.LITERATURE_EXPLORATION else "debate"
        prompt = prompt_manager.format_generation_prompt(
            goal=research_goal.description,
            preferences=research_goal.preferences,
            method=method_str,
            articles_with_reasoning=articles_with_reasoning
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
        "objective": "What the experiment aims to test",
        "methodology": "Experimental approach",
        "controls": ["Control 1", "Control 2"],
        "expected_outcomes": ["Outcome 1", "Outcome 2"],
        "success_criteria": "What constitutes success"
    }},
    "citations": [
        {{"title": "Paper title", "doi": "10.xxxx/xxxxx", "relevance": "Why this paper is relevant"}}
    ]
}}

Respond with ONLY the JSON object, no additional text."""

        # Invoke LLM
        response = self.llm_client.invoke(structured_prompt)

        # Parse response
        try:
            # Extract JSON from response (might have markdown code blocks)
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # Build Hypothesis object
            hypothesis = Hypothesis(
                id=generate_hypothesis_id(),
                research_goal_id=research_goal.id,
                title=data["title"],
                summary=data["title"],  # Use title as summary for now
                hypothesis_statement=data["statement"],
                rationale=data["rationale"],
                mechanism=data.get("mechanism"),
                experimental_protocol=ExperimentalProtocol(**data["experimental_protocol"]),
                literature_citations=[Citation(**c) for c in data.get("citations", [])],
                generation_method=method,
                elo_rating=1200.0  # Initial Elo per Google paper (page 11)
            )

            self.logger.info(
                "Hypothesis generated",
                hypothesis_id=hypothesis.id,
                title=hypothesis.title
            )

            return hypothesis

        except (json.JSONDecodeError, PydanticValidationError, KeyError) as e:
            raise CoScientistError(f"Failed to parse LLM response: {e}\nResponse: {response[:500]}")
