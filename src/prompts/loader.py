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
        articles_with_reasoning: str = ""
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
            articles_with_reasoning=articles_with_reasoning or "Initial hypothesis generation - no prior literature review."
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
        **kwargs
    ) -> str:
        """Format ranking agent prompt"""
        if method == "tournament":
            template = self.load_prompt("04_Ranking_Agent_Hypothesis_Comparison_Tournament.txt")
        else:
            template = self.load_prompt("05_Ranking_Agent_Hypothesis_Comparison_Scientific_Debate.txt")

        return template.format(
            hypothesis_a=hypothesis_a,
            hypothesis_b=hypothesis_b,
            **kwargs
        )

    def format_evolution_prompt(
        self,
        hypothesis: str,
        strategy: str = "feasibility",  # "feasibility" or "out_of_box"
        **kwargs
    ) -> str:
        """Format evolution agent prompt"""
        if strategy == "feasibility":
            template = self.load_prompt("06_Evolution_Agent_Hypothesis_Feasibility_Improvement.txt")
        else:
            template = self.load_prompt("07_Evolution_Agent_Hypothesis_Out_of_the_Box_Thinking.txt")

        return template.format(
            hypothesis=hypothesis,
            **kwargs
        )

    def format_meta_review_prompt(
        self,
        reviews: str,
        tournament_results: str,
        **kwargs
    ) -> str:
        """Format meta-review agent prompt"""
        template = self.load_prompt("08_Meta_Review_Agent_Meta_Review_Generation.txt")
        return template.format(
            reviews=reviews,
            tournament_results=tournament_results,
            **kwargs
        )


# Global instance
prompt_manager = PromptManager()
