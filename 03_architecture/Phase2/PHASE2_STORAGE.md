# Phase 2: In-Memory Storage

## Overview

In-memory state management for hypotheses, reviews, and tournament matches, providing the foundation for the persistence layer.

**File:** `src/storage/memory.py`
**Status:** ✅ Complete

## Implementation

```python
from typing import Dict, List, Optional
from schemas import (
    ResearchGoal, Hypothesis, Review, TournamentMatch,
    HypothesisStatus
)
import structlog

logger = structlog.get_logger()

class InMemoryStorage:
    """In-memory storage for development and testing"""

    def __init__(self):
        self._research_goals: Dict[str, ResearchGoal] = {}
        self._hypotheses: Dict[str, Hypothesis] = {}
        self._reviews: Dict[str, Review] = {}
        self._matches: Dict[str, TournamentMatch] = {}

    # ==================== Research Goals ====================

    def add_research_goal(self, goal: ResearchGoal) -> ResearchGoal:
        """Add research goal"""
        self._research_goals[goal.id] = goal
        logger.info("Research goal added", goal_id=goal.id)
        return goal

    def get_research_goal(self, goal_id: str) -> Optional[ResearchGoal]:
        """Get research goal by ID"""
        return self._research_goals.get(goal_id)

    def get_all_research_goals(self) -> List[ResearchGoal]:
        """Get all research goals"""
        return list(self._research_goals.values())

    # ==================== Hypotheses ====================

    def add_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Add hypothesis"""
        self._hypotheses[hypothesis.id] = hypothesis
        logger.info("Hypothesis added", hypothesis_id=hypothesis.id)
        return hypothesis

    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Get hypothesis by ID"""
        return self._hypotheses.get(hypothesis_id)

    def update_hypothesis(self, hypothesis: Hypothesis) -> Hypothesis:
        """Update existing hypothesis"""
        if hypothesis.id not in self._hypotheses:
            raise ValueError(f"Hypothesis not found: {hypothesis.id}")
        self._hypotheses[hypothesis.id] = hypothesis
        logger.info(
            "Hypothesis updated",
            hypothesis_id=hypothesis.id,
            elo=hypothesis.elo_rating
        )
        return hypothesis

    def get_hypotheses_by_goal(
        self,
        goal_id: str,
        status: Optional[HypothesisStatus] = None
    ) -> List[Hypothesis]:
        """Get hypotheses for a research goal"""
        hypotheses = [
            h for h in self._hypotheses.values()
            if h.research_goal_id == goal_id
        ]
        if status:
            hypotheses = [h for h in hypotheses if h.status == status]
        return hypotheses

    def get_top_hypotheses(
        self,
        n: int = 10,
        goal_id: Optional[str] = None
    ) -> List[Hypothesis]:
        """Get top N hypotheses by Elo rating"""
        if goal_id:
            hypotheses = self.get_hypotheses_by_goal(goal_id)
        else:
            hypotheses = list(self._hypotheses.values())

        return sorted(
            hypotheses,
            key=lambda h: h.elo_rating,
            reverse=True
        )[:n]

    def get_all_hypotheses(self) -> List[Hypothesis]:
        """Get all hypotheses"""
        return list(self._hypotheses.values())

    # ==================== Reviews ====================

    def add_review(self, review: Review) -> Review:
        """Add review"""
        self._reviews[review.id] = review
        logger.info(
            "Review added",
            review_id=review.id,
            hypothesis_id=review.hypothesis_id
        )
        return review

    def get_review(self, review_id: str) -> Optional[Review]:
        """Get review by ID"""
        return self._reviews.get(review_id)

    def get_reviews_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[Review]:
        """Get all reviews for a hypothesis"""
        return [
            r for r in self._reviews.values()
            if r.hypothesis_id == hypothesis_id
        ]

    def get_all_reviews(self) -> List[Review]:
        """Get all reviews"""
        return list(self._reviews.values())

    # ==================== Tournament Matches ====================

    def add_match(self, match: TournamentMatch) -> TournamentMatch:
        """Add tournament match"""
        self._matches[match.id] = match
        logger.info(
            "Match added",
            match_id=match.id,
            winner=match.winner_id
        )
        return match

    def get_match(self, match_id: str) -> Optional[TournamentMatch]:
        """Get match by ID"""
        return self._matches.get(match_id)

    def get_matches_for_hypothesis(
        self,
        hypothesis_id: str
    ) -> List[TournamentMatch]:
        """Get all matches involving a hypothesis"""
        return [
            m for m in self._matches.values()
            if m.hypothesis_a_id == hypothesis_id
            or m.hypothesis_b_id == hypothesis_id
        ]

    def get_all_matches(self) -> List[TournamentMatch]:
        """Get all tournament matches"""
        return list(self._matches.values())

    # ==================== Statistics ====================

    def get_hypothesis_win_rate(self, hypothesis_id: str) -> float:
        """Calculate win rate for hypothesis"""
        matches = self.get_matches_for_hypothesis(hypothesis_id)
        if not matches:
            return 0.0

        wins = sum(1 for m in matches if m.winner_id == hypothesis_id)
        return wins / len(matches)

    def get_statistics(self) -> Dict:
        """Get storage statistics"""
        return {
            "research_goals": len(self._research_goals),
            "hypotheses": len(self._hypotheses),
            "reviews": len(self._reviews),
            "matches": len(self._matches)
        }

    # ==================== Utility ====================

    def clear(self):
        """Clear all data (for testing)"""
        self._research_goals.clear()
        self._hypotheses.clear()
        self._reviews.clear()
        self._matches.clear()
        logger.info("Storage cleared")


# Global storage instance
storage = InMemoryStorage()

def get_storage() -> InMemoryStorage:
    """Get global storage instance"""
    return storage
```

## Query Methods

### Hypotheses

| Method | Description |
|--------|-------------|
| `add_hypothesis(hyp)` | Add new hypothesis |
| `get_hypothesis(id)` | Get by ID |
| `update_hypothesis(hyp)` | Update existing (e.g., Elo) |
| `get_hypotheses_by_goal(goal_id)` | Filter by research goal |
| `get_top_hypotheses(n)` | Top N by Elo |

### Reviews

| Method | Description |
|--------|-------------|
| `add_review(review)` | Add new review |
| `get_review(id)` | Get by ID |
| `get_reviews_for_hypothesis(hyp_id)` | All reviews for hypothesis |

### Matches

| Method | Description |
|--------|-------------|
| `add_match(match)` | Add tournament match |
| `get_matches_for_hypothesis(hyp_id)` | Match history |
| `get_hypothesis_win_rate(hyp_id)` | Calculate win percentage |

## Usage

```python
from src.storage.memory import storage

# Add research goal
goal = ResearchGoal(id="goal_001", description="AML drug repurposing", ...)
storage.add_research_goal(goal)

# Add hypothesis
hypothesis = Hypothesis(id="hyp_001", elo_rating=1200, ...)
storage.add_hypothesis(hypothesis)

# Update Elo after match
hypothesis.elo_rating += 16
storage.update_hypothesis(hypothesis)

# Get top hypotheses
top_5 = storage.get_top_hypotheses(n=5, goal_id="goal_001")

# Get win rate
win_rate = storage.get_hypothesis_win_rate("hyp_001")
print(f"Win rate: {win_rate:.1%}")

# Get statistics
stats = storage.get_statistics()
print(f"Total hypotheses: {stats['hypotheses']}")
```

## Data Flow

```
Generation Agent
    │
    ▼
┌─────────────────┐
│ add_hypothesis  │
└────────┬────────┘
         │
         ▼
Reflection Agent
    │
    ▼
┌─────────────────┐
│   add_review    │
└────────┬────────┘
         │
         ▼
Ranking Agent
    │
    ▼
┌─────────────────┐     ┌────────────────────┐
│   add_match     │ --> │ update_hypothesis  │
└─────────────────┘     │   (Elo change)     │
                        └────────────────────┘
```

## Testing

```python
def test_storage_hypothesis():
    """Test hypothesis storage"""
    storage = InMemoryStorage()

    hyp = Hypothesis(
        id="test_hyp",
        research_goal_id="goal",
        elo_rating=1200,
        ...
    )

    storage.add_hypothesis(hyp)
    retrieved = storage.get_hypothesis("test_hyp")

    assert retrieved.id == "test_hyp"
    assert retrieved.elo_rating == 1200

def test_storage_elo_update():
    """Test Elo update"""
    storage.add_hypothesis(hyp)

    hyp.elo_rating = 1216
    storage.update_hypothesis(hyp)

    retrieved = storage.get_hypothesis(hyp.id)
    assert retrieved.elo_rating == 1216

def test_top_hypotheses():
    """Test top N query"""
    storage = InMemoryStorage()

    # Add hypotheses with different Elo
    for i, elo in enumerate([1200, 1250, 1300, 1180]):
        hyp = Hypothesis(id=f"hyp_{i}", elo_rating=elo, ...)
        storage.add_hypothesis(hyp)

    top_2 = storage.get_top_hypotheses(n=2)
    assert top_2[0].elo_rating == 1300
    assert top_2[1].elo_rating == 1250
```

## Migration Path

Phase 4 replaces `InMemoryStorage` with `AsyncStorageAdapter`:

```python
# Phase 2: In-memory
from src.storage.memory import storage

# Phase 4: Async adapter (same interface)
from src.storage.async_adapter import AsyncStorageAdapter
storage = AsyncStorageAdapter()
```

Interface remains the same, enabling seamless transition.
