# Phase 2: Elo Tournament System

## Overview

Elo-based tournament rating system for hypothesis ranking, implementing standard Elo calculations with smart match pairing strategies.

**File:** `src/tournament/elo.py`
**Status:** ✅ Complete

## Background

From Google AI Co-Scientist paper (Section 3.3.3):
> "The Ranking agent employs and orchestrates an Elo-based tournament to assess and prioritize the generated hypotheses."

> "We set the initial Elo rating of 1200 for the newly added hypothesis"

## Implementation

```python
from typing import List, Tuple
from schemas import Hypothesis, TournamentMatch
import structlog

logger = structlog.get_logger()

class EloCalculator:
    """Calculate Elo rating changes for tournament matches"""

    def __init__(self, k_factor: float = 32):
        """
        Args:
            k_factor: Rating change sensitivity (default 32)
        """
        self.k_factor = k_factor

    def calculate_expected_score(
        self,
        rating_a: float,
        rating_b: float
    ) -> Tuple[float, float]:
        """Calculate expected scores for both players

        Args:
            rating_a: Rating of player A
            rating_b: Rating of player B

        Returns:
            (expected_a, expected_b) - probabilities summing to 1.0
        """
        expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
        expected_b = 1 - expected_a
        return expected_a, expected_b

    def calculate_rating_change(
        self,
        rating_a: float,
        rating_b: float,
        winner_is_a: bool
    ) -> Tuple[float, float]:
        """Calculate rating changes after a match

        Args:
            rating_a: Rating of hypothesis A
            rating_b: Rating of hypothesis B
            winner_is_a: True if A won, False if B won

        Returns:
            (change_a, change_b) - rating changes (zero-sum)
        """
        expected_a, expected_b = self.calculate_expected_score(rating_a, rating_b)

        # Actual scores (1.0 for win, 0.0 for loss)
        actual_a = 1.0 if winner_is_a else 0.0
        actual_b = 1.0 - actual_a

        # Rating changes
        change_a = self.k_factor * (actual_a - expected_a)
        change_b = self.k_factor * (actual_b - expected_b)

        logger.debug(
            "Elo calculation",
            rating_a=rating_a,
            rating_b=rating_b,
            expected_a=expected_a,
            change_a=change_a
        )

        return change_a, change_b

    def apply_match_results(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis,
        match: TournamentMatch
    ) -> Tuple[Hypothesis, Hypothesis]:
        """Apply match results to hypothesis ratings

        Args:
            hypothesis_a: First hypothesis
            hypothesis_b: Second hypothesis
            match: Completed tournament match

        Returns:
            Updated (hypothesis_a, hypothesis_b)
        """
        # Update ratings
        hypothesis_a.elo_rating += match.elo_change_a
        hypothesis_b.elo_rating += match.elo_change_b

        return hypothesis_a, hypothesis_b


class TournamentRanker:
    """Manage tournament ranking and match selection"""

    def __init__(self):
        self.elo_calculator = EloCalculator()

    def rank_hypotheses(
        self,
        hypotheses: List[Hypothesis]
    ) -> List[Hypothesis]:
        """Sort hypotheses by Elo rating (descending)

        Args:
            hypotheses: List of hypotheses

        Returns:
            Sorted list (highest Elo first)
        """
        return sorted(
            hypotheses,
            key=lambda h: h.elo_rating,
            reverse=True
        )

    def select_match_pairs(
        self,
        hypotheses: List[Hypothesis],
        max_pairs: int = 5
    ) -> List[Tuple[Hypothesis, Hypothesis]]:
        """Select hypothesis pairs for tournament matches

        Pairing strategy:
        1. Top hypotheses: round-robin among top 5
        2. Similar ratings: pair hypotheses with close Elo
        3. New hypotheses: pair with established ones

        Args:
            hypotheses: Available hypotheses
            max_pairs: Maximum pairs to return

        Returns:
            List of (hypothesis_a, hypothesis_b) pairs
        """
        if len(hypotheses) < 2:
            return []

        pairs = []
        ranked = self.rank_hypotheses(hypotheses)

        # Strategy 1: Top hypotheses compete
        top_hypotheses = ranked[:5]
        for i, hyp_a in enumerate(top_hypotheses):
            for hyp_b in top_hypotheses[i+1:]:
                pairs.append((hyp_a, hyp_b))
                if len(pairs) >= max_pairs:
                    return pairs

        # Strategy 2: Similar ratings
        for i, hyp_a in enumerate(ranked):
            if len(pairs) >= max_pairs:
                break

            # Find closest rating that hasn't been paired
            for hyp_b in ranked[i+1:]:
                if abs(hyp_a.elo_rating - hyp_b.elo_rating) < 100:
                    pair = (hyp_a, hyp_b)
                    if pair not in pairs:
                        pairs.append(pair)
                        break

        # Strategy 3: New vs established
        new_hypotheses = [h for h in hypotheses if h.elo_rating == 1200]
        established = [h for h in hypotheses if h.elo_rating > 1200]

        for new_hyp in new_hypotheses[:3]:
            if len(pairs) >= max_pairs:
                break
            if established:
                pairs.append((new_hyp, established[0]))

        return pairs[:max_pairs]

    def should_use_multi_turn(
        self,
        hypothesis_a: Hypothesis,
        hypothesis_b: Hypothesis
    ) -> bool:
        """Decide if match should use multi-turn debate

        Use multi-turn for:
        - Both hypotheses in top 5 (by rank)
        - Both hypotheses Elo > 1300
        - Close Elo ratings (within 50 points)

        Args:
            hypothesis_a: First hypothesis
            hypothesis_b: Second hypothesis

        Returns:
            True if should use multi-turn debate
        """
        # Both high-rated
        if hypothesis_a.elo_rating > 1300 and hypothesis_b.elo_rating > 1300:
            return True

        # Very close ratings
        if abs(hypothesis_a.elo_rating - hypothesis_b.elo_rating) < 50:
            return True

        return False
```

## Elo Formula

Standard Elo calculation:

**Expected Score:**
```
E_a = 1 / (1 + 10^((R_b - R_a) / 400))
```

**Rating Change:**
```
Δ_a = K × (S_a - E_a)
```

Where:
- `R_a`, `R_b` = current ratings
- `E_a` = expected score for A
- `S_a` = actual score (1.0 win, 0.0 loss)
- `K` = K-factor (32)

## Examples

### Equal Ratings
- A (1200) beats B (1200)
- Expected: 0.5 vs 0.5
- Actual: 1.0 vs 0.0
- Change: **+16** for A, **-16** for B

### Upset
- A (1200) beats B (1400)
- Expected: 0.24 vs 0.76
- Actual: 1.0 vs 0.0
- Change: **+24** for A, **-24** for B

### Expected Win
- A (1400) beats B (1200)
- Expected: 0.76 vs 0.24
- Actual: 1.0 vs 0.0
- Change: **+8** for A, **-8** for B

## Match Pairing Strategy

### Priority 1: Top Hypotheses
Top 5 by Elo compete in round-robin:
```
1 vs 2, 1 vs 3, 1 vs 4, 1 vs 5
2 vs 3, 2 vs 4, 2 vs 5
...
```

### Priority 2: Similar Ratings
Pair hypotheses within 100 Elo points:
```
1250 vs 1230  ✓ (20 point diff)
1250 vs 1100  ✗ (150 point diff)
```

### Priority 3: New vs Established
New hypotheses (1200) vs proven ones:
```
new_hyp vs top_5[0]
```

## Usage

```python
from src.tournament.elo import EloCalculator, TournamentRanker

# Calculate Elo changes
calc = EloCalculator(k_factor=32)
change_a, change_b = calc.calculate_rating_change(
    rating_a=1200,
    rating_b=1250,
    winner_is_a=True
)
print(f"A: {change_a:+.1f}, B: {change_b:+.1f}")

# Select match pairs
ranker = TournamentRanker()
pairs = ranker.select_match_pairs(hypotheses, max_pairs=3)
for hyp_a, hyp_b in pairs:
    print(f"{hyp_a.title} vs {hyp_b.title}")

# Decide debate format
use_debate = ranker.should_use_multi_turn(hyp_a, hyp_b)
```

## Testing

```python
def test_elo_equal_ratings():
    """Test Elo with equal ratings"""
    calc = EloCalculator()
    change_a, change_b = calc.calculate_rating_change(
        rating_a=1200,
        rating_b=1200,
        winner_is_a=True
    )
    assert change_a == 16.0
    assert change_b == -16.0
    assert change_a + change_b == 0  # Zero-sum

def test_elo_upset():
    """Test Elo upset (lower beats higher)"""
    calc = EloCalculator()
    change_a, change_b = calc.calculate_rating_change(
        rating_a=1200,
        rating_b=1400,
        winner_is_a=True
    )
    assert change_a > 16  # Bigger gain for upset
    assert change_b < -16  # Bigger loss for upset

def test_match_pairing():
    """Test match pair selection"""
    ranker = TournamentRanker()
    pairs = ranker.select_match_pairs(hypotheses)

    # Top hypotheses should be paired
    top_ids = {h.id for h in hypotheses[:5]}
    for hyp_a, hyp_b in pairs[:3]:
        assert hyp_a.id in top_ids or hyp_b.id in top_ids
```
