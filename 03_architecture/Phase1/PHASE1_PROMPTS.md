# Phase 1: Prompt Manager

## Overview

Template loading and formatting system for agent prompts, loading from `02_Prompts/*.txt` files with variable substitution and caching.

**File:** `src/prompts/loader.py`
**Status:** ✅ Complete

## Prompt Files

Located in `02_Prompts/`:

| File | Agent | Method |
|------|-------|--------|
| `01_Generation_Agent_Hypothesis_After_Literature_Review.txt` | Generation | Literature exploration |
| `02_Generation_Agent_Hypothesis_After_Scientific_Debate.txt` | Generation | Simulated debate |
| `03_Reflection_Agent_Generating_Observations.txt` | Reflection | Observation review |
| `04_Ranking_Agent_Hypothesis_Comparison_Tournament.txt` | Ranking | Tournament match |
| `05_Ranking_Agent_Hypothesis_Comparison_Scientific_Debate.txt` | Ranking | Multi-turn debate |
| `06_Evolution_Agent_Hypothesis_Feasibility_Improvement.txt` | Evolution | Feasibility |
| `07_Evolution_Agent_Hypothesis_Out_of_the_Box_Thinking.txt` | Evolution | Out-of-box |
| `08_Meta_Review_Agent_Meta_Review_Generation.txt` | Meta-review | Synthesis |

## Implementation

```python
from pathlib import Path
from functools import lru_cache
from src.config import settings

class PromptLoader:
    """Load and format agent prompts"""

    def __init__(self, prompts_dir: Path = None):
        self.prompts_dir = prompts_dir or settings.prompts_dir
        self._cache = {}

    @lru_cache(maxsize=20)
    def _load_template(self, filename: str) -> str:
        """Load prompt template from file (cached)"""
        path = self.prompts_dir / filename
        if not path.exists():
            raise PromptLoadError(f"Prompt file not found: {path}")
        return path.read_text(encoding="utf-8")

    def get_generation_prompt(
        self,
        goal: str,
        preferences: str,
        notes: str = "",
        articles_with_reasoning: str = "",
        transcript: str = ""
    ) -> str:
        """Get formatted generation prompt for literature method"""
        template = self._load_template(
            "01_Generation_Agent_Hypothesis_After_Literature_Review.txt"
        )
        return template.format(
            goal=goal,
            preferences=preferences,
            notes=notes,
            articles_with_reasoning=articles_with_reasoning or "No prior articles provided.",
            transcript=transcript or "No prior debate transcript available."
        )

    def get_generation_debate_prompt(
        self,
        goal: str,
        preferences: str,
        notes: str = "",
        transcript: str = ""
    ) -> str:
        """Get formatted generation prompt for debate method"""
        template = self._load_template(
            "02_Generation_Agent_Hypothesis_After_Scientific_Debate.txt"
        )
        return template.format(
            goal=goal,
            preferences=preferences,
            notes=notes,
            transcript=transcript or "No prior debate transcript available."
        )

    def get_reflection_prompt(
        self,
        goal: str,
        preferences: str,
        hypothesis: str,
        review_type: str = "observation"
    ) -> str:
        """Get formatted reflection prompt"""
        template = self._load_template(
            "03_Reflection_Agent_Generating_Observations.txt"
        )
        return template.format(
            goal=goal,
            preferences=preferences,
            hypothesis=hypothesis
        )

    def get_ranking_tournament_prompt(
        self,
        hypothesis_1: str,
        hypothesis_2: str,
        review_1: str,
        review_2: str,
        goal: str,
        preferences: str,
        idea_attributes: str,
        notes: str = ""
    ) -> str:
        """Get formatted ranking prompt for tournament"""
        template = self._load_template(
            "04_Ranking_Agent_Hypothesis_Comparison_Tournament.txt"
        )
        return template.format(**{
            "hypothesis 1": hypothesis_1,
            "hypothesis 2": hypothesis_2,
            "review 1": review_1,
            "review 2": review_2,
            "goal": goal,
            "preferences": preferences,
            "idea_attributes": idea_attributes,
            "notes": notes
        })

    def get_ranking_debate_prompt(
        self,
        hypothesis_1: str,
        hypothesis_2: str,
        review_1: str,
        review_2: str,
        goal: str,
        preferences: str,
        idea_attributes: str,
        notes: str = ""
    ) -> str:
        """Get formatted ranking prompt for multi-turn debate"""
        template = self._load_template(
            "05_Ranking_Agent_Hypothesis_Comparison_Scientific_Debate.txt"
        )
        return template.format(**{
            "hypothesis 1": hypothesis_1,
            "hypothesis 2": hypothesis_2,
            "review 1": review_1,
            "review 2": review_2,
            "goal": goal,
            "preferences": preferences,
            "idea_attributes": idea_attributes,
            "notes": notes
        })

    def get_evolution_feasibility_prompt(
        self,
        hypothesis: str,
        review: str,
        goal: str,
        preferences: str
    ) -> str:
        """Get formatted evolution prompt for feasibility improvement"""
        template = self._load_template(
            "06_Evolution_Agent_Hypothesis_Feasibility_Improvement.txt"
        )
        return template.format(
            hypothesis=hypothesis,
            review=review,
            goal=goal,
            preferences=preferences
        )

    def get_evolution_outofbox_prompt(
        self,
        hypotheses: str,
        goal: str,
        preferences: str
    ) -> str:
        """Get formatted evolution prompt for out-of-box thinking"""
        template = self._load_template(
            "07_Evolution_Agent_Hypothesis_Out_of_the_Box_Thinking.txt"
        )
        return template.format(
            hypotheses=hypotheses,
            goal=goal,
            preferences=preferences
        )

    def get_meta_review_prompt(
        self,
        reviews: str,
        tournament_results: str,
        goal: str
    ) -> str:
        """Get formatted meta-review prompt"""
        template = self._load_template(
            "08_Meta_Review_Agent_Meta_Review_Generation.txt"
        )
        return template.format(
            reviews=reviews,
            tournament_results=tournament_results,
            goal=goal
        )

# Global instance
_loader = None

def get_prompt_loader() -> PromptLoader:
    """Get global prompt loader instance"""
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader
```

## Template Variables

### Generation (Literature)
| Variable | Description |
|----------|-------------|
| `{goal}` | Research goal description |
| `{preferences}` | Scientist preferences |
| `{notes}` | Additional notes |
| `{articles_with_reasoning}` | Retrieved literature summaries |
| `{transcript}` | Prior debate transcript (if any) |

### Ranking (Tournament)
| Variable | Description |
|----------|-------------|
| `{hypothesis 1}` | First hypothesis text |
| `{hypothesis 2}` | Second hypothesis text |
| `{review 1}` | Review of first hypothesis |
| `{review 2}` | Review of second hypothesis |
| `{goal}` | Research goal |
| `{preferences}` | Evaluation preferences |
| `{idea_attributes}` | Attributes to compare |
| `{notes}` | Additional notes |

## Usage

```python
from src.prompts.loader import get_prompt_loader

loader = get_prompt_loader()

# Get generation prompt
prompt = loader.get_generation_prompt(
    goal="Identify drug repurposing candidates for AML",
    preferences="Focus on FDA-approved drugs",
    articles_with_reasoning="[1] KIRA6 shows IRE1α inhibition..."
)

# Get ranking prompt
prompt = loader.get_ranking_tournament_prompt(
    hypothesis_1="KIRA6 for AML...",
    hypothesis_2="Disulfiram for AML...",
    review_1="Strong mechanism...",
    review_2="Clinical evidence...",
    goal="AML drug repurposing",
    preferences="Testability",
    idea_attributes="novelty, feasibility"
)
```

## Caching

Templates are cached using `@lru_cache`:
- First load reads from disk
- Subsequent calls return cached template
- Cache size: 20 templates

## Error Handling

```python
from src.utils.errors import PromptLoadError

try:
    template = loader._load_template("nonexistent.txt")
except PromptLoadError as e:
    logger.error(f"Failed to load prompt: {e}")
```

## Testing

```python
def test_prompt_loading():
    """Test prompt templates load correctly"""
    loader = get_prompt_loader()

    prompt = loader.get_generation_prompt(
        goal="Test goal",
        preferences="Test prefs"
    )

    assert "Test goal" in prompt
    assert len(prompt) > 100
```
