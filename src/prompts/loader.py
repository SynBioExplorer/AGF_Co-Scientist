"""Prompt loading and formatting utilities"""

from pathlib import Path
from typing import Dict
from src.config import settings
from src.utils.errors import PromptLoadError


class PromptManager:
    """Manage loading and formatting of agent prompts"""

    def __init__(self, prompts_dir: Path = None):
        self.prompts_dir = prompts_dir or settings.prompts_dir
        self._cache: Dict[str, str] = {}

    def load_prompt(self, filename: str) -> str:
        """Load prompt from file, cache result"""
        if filename in self._cache:
            return self._cache[filename]

        filepath = self.prompts_dir / filename
        if not filepath.exists():
            raise PromptLoadError(f"Prompt file not found: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        self._cache[filename] = content
        return content

    def format_generation_prompt(
        self,
        goal: str,
        preferences: list[str],
        method: str = "literature",  # "literature" or "debate"
        source_hypothesis: str = "",
        instructions: str = "",
        articles_with_reasoning: str = "",
        transcript: str = ""
    ) -> str:
        """Format generation agent prompt"""
        if method == "literature":
            template = self.load_prompt("01_Generation_Agent_Hypothesis_After_Literature_Review.txt")
        else:
            template = self.load_prompt("02_Generation_Agent_Hypothesis_After_Scientific_Debate.txt")

        # Format template with variables
        formatted = template.format(
            goal=goal,
            preferences="\n".join(f"- {p}" for p in preferences) if preferences else "Standard scientific rigor",
            source_hypothesis=source_hypothesis or "None",
            instructions=instructions or "",
            articles_with_reasoning=articles_with_reasoning or "Initial hypothesis generation - no prior literature review.",
            transcript=transcript or "No prior debate transcript available."
        )
        return formatted

    def format_reflection_prompt(
        self,
        goal: str,
        hypothesis: str,
        **kwargs
    ) -> str:
        """Format reflection agent prompt"""
        template = self.load_prompt("03_Reflection_Agent_Generating_Observations.txt")
        return template.format(
            goal=goal,
            hypothesis=hypothesis,
            **kwargs
        )

    def format_ranking_prompt(
        self,
        hypothesis_a: str,
        hypothesis_b: str,
        method: str = "tournament",  # "tournament" or "debate"
        goal: str = "",
        idea_attributes: str = "novelty, correctness, testability, feasibility",
        preferences: str = "",
        notes: str = "",
        review_a: str = "",
        review_b: str = "",
        **kwargs
    ) -> str:
        """Format ranking agent prompt"""
        if method == "tournament":
            template = self.load_prompt("04_Ranking_Agent_Hypothesis_Comparison_Tournament.txt")
        else:
            template = self.load_prompt("05_Ranking_Agent_Hypothesis_Comparison_Scientific_Debate.txt")

        # Use correct template variable names
        return template.format(
            goal=goal or "Compare hypotheses",
            idea_attributes=idea_attributes,
            preferences=preferences or "Standard scientific rigor",
            notes=notes or "Focus on scientific merit",
            **{"hypothesis 1": hypothesis_a, "hypothesis 2": hypothesis_b},
            **{"review 1": review_a or "No review available", "review 2": review_b or "No review available"},
            **kwargs
        )

    def format_evolution_prompt(
        self,
        hypothesis: str,
        strategy: str = "feasibility",  # "feasibility" or "out_of_box"
        goal: str = "",
        preferences: str = "",
        **kwargs
    ) -> str:
        """Format evolution agent prompt"""
        if strategy == "feasibility":
            template = self.load_prompt("06_Evolution_Agent_Hypothesis_Feasibility_Improvement.txt")
        else:
            template = self.load_prompt("07_Evolution_Agent_Hypothesis_Out_of_the_Box_Thinking.txt")

        return template.format(
            hypothesis=hypothesis,
            goal=goal or "Improve the hypothesis",
            preferences=preferences or "Novelty, correctness, testability, and feasibility",
            **kwargs
        )

    def format_meta_review_prompt(
        self,
        reviews: str,
        goal: str = "",
        preferences: str = "",
        instructions: str = "",
        **kwargs
    ) -> str:
        """Format meta-review agent prompt"""
        template = self.load_prompt("08_Meta_Review_Agent_Meta_Review_Generation.txt")
        return template.format(
            reviews=reviews,
            goal=goal,
            preferences=preferences,
            instructions=instructions,
            **kwargs
        )


# Global instance
prompt_manager = PromptManager()
