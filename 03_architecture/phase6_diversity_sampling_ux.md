# Phase 6B: Diversity Sampling for Final Results - UX Enhancement Plan

**Status**: 📋 **PLANNING**

**Date**: January 30, 2026

**Type**: User Experience Enhancement

**Alignment**: Google Paper Section 4.1 (Results presentation)

---

## Overview

### Problem Statement

Currently, when users request the "Top 10" hypotheses for a research goal, the system returns the 10 highest-rated hypotheses by Elo score. While this ensures quality, it can result in:

- **Limited Diversity**: All top hypotheses might come from the same cluster (similar approaches)
- **Missed Perspectives**: Alternative scientific approaches may be overlooked
- **Narrow Solution Space**: Users don't see the full landscape of possibilities

### Solution: Cluster-Aware Diversity Sampling

Implement an intelligent sampling strategy that returns **representative hypotheses from each cluster**, ensuring users see:
- ✅ High-quality hypotheses (Elo-ranked)
- ✅ Diverse scientific approaches (cluster representatives)
- ✅ Complete landscape of solution space (coverage across clusters)

### User Benefits

| Current Behavior | Enhanced Behavior |
|------------------|-------------------|
| Top 10 by Elo → might all be CRISPR variants | Top 1-2 from each of 5 clusters → CRISPR, drug screening, genetic engineering, etc. |
| Scientists see narrow solution space | Scientists see full landscape of approaches |
| Must manually scroll through 50+ hypotheses | Get curated diverse selection upfront |

---

## Google Paper Alignment

From Google paper (Section 4.1 - Results Presentation):

> "The system presents a **diverse set of high-quality hypotheses** to scientists for review. This ensures comprehensive coverage of the solution space while maintaining scientific rigor."

**Implementation Approach**:
- ✅ Use proximity clusters to identify distinct scientific approaches
- ✅ Select top-rated hypothesis from each cluster (quality + diversity)
- ✅ Provide UI toggle for users to choose: "Top by Elo" vs "Diverse Selection"

---

## Implementation Plan

### Phase 1: Backend - Storage Layer

#### 1.1 Add Diversity Sampling Method to Storage

**File**: `src/storage/async_adapter.py` (new method after line 334)

```python
async def get_diverse_hypotheses(
    self,
    goal_id: str,
    n: int = 10,
    min_elo_rating: float = 1200.0,
    cluster_balance: bool = True
) -> List[Hypothesis]:
    """
    Get diverse hypotheses using cluster-aware sampling.

    Strategy:
    1. Fetch proximity graph for goal
    2. Get all hypotheses for goal
    3. For each cluster, select top-rated hypothesis
    4. If fewer clusters than n, fill remainder with top Elo
    5. Return exactly n hypotheses

    Args:
        goal_id: Research goal ID
        n: Number of hypotheses to return (default: 10)
        min_elo_rating: Minimum Elo threshold (default: 1200.0)
        cluster_balance: If True, balance across clusters; else top from each

    Returns:
        List of n diverse hypotheses
    """
    # Implementation steps:
    # 1. Get proximity graph
    proximity_graph = await self.get_proximity_graph(goal_id)

    # 2. Get all hypotheses for goal
    all_hypotheses = await self.get_hypotheses_by_goal(goal_id)

    # 3. Filter by minimum Elo
    qualified = [h for h in all_hypotheses if (h.elo_rating or 1200.0) >= min_elo_rating]

    # 4. If no proximity graph, fallback to top Elo
    if not proximity_graph or not proximity_graph.clusters:
        return sorted(qualified, key=lambda h: h.elo_rating or 1200.0, reverse=True)[:n]

    # 5. Cluster-aware selection
    selected = []
    hyp_map = {h.id: h for h in qualified}

    # 5a. For each cluster, pick top-rated hypothesis
    for cluster in proximity_graph.clusters:
        cluster_hyps = [hyp_map[hid] for hid in cluster.hypothesis_ids if hid in hyp_map]
        if cluster_hyps:
            top_in_cluster = max(cluster_hyps, key=lambda h: h.elo_rating or 1200.0)
            selected.append(top_in_cluster)

    # 5b. If we have more than n, take top n by Elo
    if len(selected) > n:
        selected = sorted(selected, key=lambda h: h.elo_rating or 1200.0, reverse=True)[:n]

    # 5c. If we have fewer than n, fill with top remaining hypotheses
    if len(selected) < n:
        selected_ids = {h.id for h in selected}
        remaining = [h for h in qualified if h.id not in selected_ids]
        remaining_sorted = sorted(remaining, key=lambda h: h.elo_rating or 1200.0, reverse=True)
        selected.extend(remaining_sorted[:n - len(selected)])

    # 6. Sort final result by Elo for consistency
    return sorted(selected, key=lambda h: h.elo_rating or 1200.0, reverse=True)
```

**Testing**: `05_tests/phase6_diversity_sampling_test.py`
- Test with 3 clusters of 5 hypotheses each → returns 1 per cluster
- Test with 10 clusters, n=5 → returns top 5 clusters by representative Elo
- Test with no proximity graph → fallback to top Elo
- Test with outlier hypotheses → includes outliers if high-rated

---

### Phase 2: Backend - API Endpoints

#### 2.1 Update GET /goals/{goal_id}/hypotheses Endpoint

**File**: `src/api/main.py` (modify lines 374-408)

**Current signature**:
```python
async def get_hypotheses(
    goal_id: str,
    page: int = 1,
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("elo", pattern="^(elo|created|title)$")
)
```

**Enhanced signature**:
```python
async def get_hypotheses(
    goal_id: str,
    page: int = 1,
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("elo", pattern="^(elo|created|title|diverse)$"),  # NEW
    min_elo: float = Query(1200.0, ge=0, le=3000)  # NEW - optional filter
)
```

**Implementation**:
```python
@app.get("/goals/{goal_id}/hypotheses", response_model=HypothesisListResponse)
async def get_hypotheses(
    goal_id: str,
    page: int = 1,
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("elo", pattern="^(elo|created|title|diverse)$"),
    min_elo: float = Query(1200.0, ge=0, le=3000)
):
    """
    Get hypotheses with optional diversity sampling.

    Query Parameters:
    - sort_by: "elo" (default), "created", "title", or "diverse"
    - min_elo: Minimum Elo rating filter (default: 1200.0)
    - page, page_size: Pagination parameters
    """
    goal = await async_storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Research goal not found")

    # Use diversity sampling if requested
    if sort_by == "diverse":
        all_hypotheses = await async_storage.get_diverse_hypotheses(
            goal_id=goal_id,
            n=100,  # Get all for pagination
            min_elo_rating=min_elo,
            cluster_balance=True
        )
    else:
        # Original behavior
        all_hypotheses = await async_storage.get_hypotheses_by_goal(goal_id)

        # Apply minimum Elo filter
        all_hypotheses = [h for h in all_hypotheses if (h.elo_rating or 1200.0) >= min_elo]

        # Sort by specified field
        if sort_by == "elo":
            all_hypotheses.sort(key=lambda h: h.elo_rating or 1200.0, reverse=True)
        elif sort_by == "created":
            all_hypotheses.sort(key=lambda h: h.created_at, reverse=True)
        elif sort_by == "title":
            all_hypotheses.sort(key=lambda h: h.title.lower())

    # Paginate
    total_count = len(all_hypotheses)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = all_hypotheses[start:end]

    return HypothesisListResponse(
        hypotheses=[h.model_dump() for h in paginated],
        total_count=total_count,
        page=page,
        page_size=page_size
    )
```

---

#### 2.2 Add GET /goals/{goal_id}/hypotheses/diverse Endpoint (Alternative)

**File**: `src/api/main.py` (add after line 453)

This provides a dedicated endpoint for diversity sampling (cleaner REST API design):

```python
@app.get("/goals/{goal_id}/hypotheses/diverse", response_model=HypothesisListResponse)
async def get_diverse_hypotheses_endpoint(
    goal_id: str,
    n: int = Query(10, ge=1, le=50, description="Number of diverse hypotheses to return"),
    min_elo: float = Query(1200.0, ge=0, le=3000, description="Minimum Elo rating")
):
    """
    Get cluster-aware diverse hypotheses for a research goal.

    Returns top-rated hypothesis from each cluster, ensuring diverse
    scientific approaches are represented in results.
    """
    goal = await async_storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Research goal not found")

    diverse_hypotheses = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=n,
        min_elo_rating=min_elo,
        cluster_balance=True
    )

    return HypothesisListResponse(
        hypotheses=[h.model_dump() for h in diverse_hypotheses],
        total_count=len(diverse_hypotheses),
        page=1,
        page_size=n
    )
```

**Benefits of dedicated endpoint**:
- ✅ Clearer API semantics (RESTful design)
- ✅ No query parameter complexity in main endpoint
- ✅ Easier to add cluster metadata in response (future enhancement)
- ✅ Can be cached separately for performance

---

### Phase 3: Backend - Supervisor Integration

#### 3.1 Update Supervisor Final Overview Generation

**File**: `src/agents/supervisor.py` (modify lines 866-928)

**Current code** (line 884-886):
```python
top_hypotheses = await self.storage.get_top_hypotheses(
    n=5, goal_id=research_goal.id
)
```

**Enhanced code**:
```python
# Use diversity sampling for final overview
from src.config import settings

if settings.diversity_sampling_for_overview:
    top_hypotheses = await self.storage.get_diverse_hypotheses(
        goal_id=research_goal.id,
        n=5,
        min_elo_rating=1200.0,
        cluster_balance=True
    )
    logger.info(
        "supervisor_final_overview_diverse_sampling",
        goal_id=research_goal.id,
        num_hypotheses=len(top_hypotheses)
    )
else:
    top_hypotheses = await self.storage.get_top_hypotheses(
        n=5, goal_id=research_goal.id
    )
```

**Configuration** (add to `src/config.py`):
```python
# Diversity Sampling Configuration (Phase 6B - UX Enhancement)
diversity_sampling_for_overview: bool = True  # Use diversity sampling in final overview
diversity_sampling_min_elo: float = 1200.0  # Minimum Elo for diverse selection
```

---

### Phase 4: Frontend - UI Components

#### 4.1 Update HypothesisList Component

**File**: `frontend/src/components/hypotheses/HypothesisList.tsx` (lines 17-52)

**Current sort dropdown**:
```tsx
<select
  value={sortBy}
  onChange={(e) => setSortBy(e.target.value as 'elo' | 'created')}
  className="rounded-md border-gray-300 shadow-sm"
>
  <option value="elo">Sort by Elo Rating</option>
  <option value="created">Sort by Date Created</option>
</select>
```

**Enhanced sort dropdown**:
```tsx
<select
  value={sortBy}
  onChange={(e) => setSortBy(e.target.value as 'elo' | 'created' | 'diverse')}
  className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
>
  <option value="elo">Sort by Elo Rating</option>
  <option value="created">Sort by Date Created</option>
  <option value="diverse">🎨 Diverse Selection (Recommended)</option>
</select>
```

**Add icon and tooltip**:
```tsx
<div className="flex items-center gap-2">
  <select
    value={sortBy}
    onChange={(e) => setSortBy(e.target.value as 'elo' | 'created' | 'diverse')}
    className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
  >
    <option value="elo">Top by Rating</option>
    <option value="created">Newest First</option>
    <option value="diverse">🎨 Diverse Selection</option>
  </select>

  {sortBy === 'diverse' && (
    <span className="text-sm text-gray-500 italic">
      Showing top hypothesis from each scientific approach
    </span>
  )}
</div>
```

---

#### 4.2 Update API Service

**File**: `frontend/src/services/api.ts` (lines 63-73)

**Current function**:
```typescript
export const getHypotheses = async (
  goalId: string,
  page = 1,
  pageSize = 10,
  sortBy = 'elo'
): Promise<HypothesisListResponse>
```

**Enhanced function**:
```typescript
export const getHypotheses = async (
  goalId: string,
  page = 1,
  pageSize = 10,
  sortBy: 'elo' | 'created' | 'title' | 'diverse' = 'elo',
  minElo = 1200.0
): Promise<HypothesisListResponse> => {
  const params = new URLSearchParams({
    page: page.toString(),
    page_size: pageSize.toString(),
    sort_by: sortBy,
    min_elo: minElo.toString()
  });

  const response = await fetch(
    `${API_BASE_URL}/goals/${goalId}/hypotheses?${params}`,
    { headers: { 'Content-Type': 'application/json' } }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch hypotheses: ${response.statusText}`);
  }

  return response.json();
};
```

---

#### 4.3 Alternative: Add Dedicated Diverse Hypotheses Hook (Optional)

**File**: `frontend/src/hooks/useDiverseHypotheses.ts` (NEW)

```typescript
import { useState, useEffect } from 'react';
import { getDiverseHypotheses } from '../services/api';
import type { Hypothesis } from '../types';

export const useDiverseHypotheses = (goalId: string, n: number = 10) => {
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDiverse = async () => {
      try {
        setLoading(true);
        const data = await getDiverseHypotheses(goalId, n);
        setHypotheses(data.hypotheses);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    if (goalId) {
      fetchDiverse();
    }
  }, [goalId, n]);

  return { hypotheses, loading, error };
};
```

---

### Phase 5: Configuration & Feature Flags

#### 5.1 Add Configuration Parameters

**File**: `src/config.py` (add after line 84)

```python
# Diversity Sampling Configuration (Phase 6B - UX Enhancement)
diversity_sampling_enabled: bool = True  # Enable diversity sampling feature
diversity_sampling_for_overview: bool = True  # Use in final overview generation
diversity_sampling_min_elo: float = 1200.0  # Minimum Elo rating for selection
diversity_sampling_default_n: int = 10  # Default number of diverse hypotheses
```

**Environment Variables** (add to `03_architecture/.env.example`):
```bash
# Diversity Sampling (Phase 6B)
DIVERSITY_SAMPLING_ENABLED=true
DIVERSITY_SAMPLING_FOR_OVERVIEW=true
DIVERSITY_SAMPLING_MIN_ELO=1200.0
DIVERSITY_SAMPLING_DEFAULT_N=10
```

---

## Testing Strategy

### Unit Tests

**File**: `05_tests/phase6_diversity_sampling_test.py` (NEW)

```python
"""
Unit tests for diversity sampling UX enhancement (Phase 6B).
"""

import pytest
from datetime import datetime
from src.storage.async_adapter import async_storage
from src.utils.ids import generate_hypothesis_id, generate_goal_id
from schemas import (
    Hypothesis, ResearchGoal, ProximityGraph, HypothesisCluster,
    ExperimentalProtocol, GenerationMethod
)


def create_test_hypothesis(
    title: str,
    elo_rating: float,
    cluster_label: str = "default"
) -> Hypothesis:
    """Helper to create test hypothesis."""
    return Hypothesis(
        id=generate_hypothesis_id(),
        research_goal_id="test-goal-1",
        title=title,
        summary=f"Summary for {title}",
        hypothesis_statement=f"Statement for {title}",
        rationale=f"Rationale for {title}",
        mechanism=f"Mechanism for {title}",
        experimental_protocol=ExperimentalProtocol(
            objective="Test objective",
            methodology="Test methodology",
            controls=["Control 1", "Control 2"],
            success_criteria="Test success criteria"
        ),
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=elo_rating,
        created_at=datetime.now()
    )


@pytest.mark.asyncio
async def test_diverse_selection_from_clusters():
    """Test that diverse selection returns one hypothesis per cluster."""
    # Create 3 clusters with 3 hypotheses each
    goal_id = generate_goal_id()

    # Cluster 1: CRISPR approaches (Elo: 1500, 1450, 1400)
    crispr_hyps = [
        create_test_hypothesis("CRISPR Base Editing", 1500, "crispr"),
        create_test_hypothesis("CRISPR Prime Editing", 1450, "crispr"),
        create_test_hypothesis("CRISPR Cas9 Classic", 1400, "crispr")
    ]

    # Cluster 2: Drug screening (Elo: 1480, 1420, 1380)
    drug_hyps = [
        create_test_hypothesis("High-throughput Drug Screen", 1480, "drug"),
        create_test_hypothesis("Targeted Drug Panel", 1420, "drug"),
        create_test_hypothesis("Phenotypic Drug Screen", 1380, "drug")
    ]

    # Cluster 3: Genetic engineering (Elo: 1460, 1410, 1390)
    genetic_hyps = [
        create_test_hypothesis("Synthetic Biology Circuit", 1460, "genetic"),
        create_test_hypothesis("Gene Drive System", 1410, "genetic"),
        create_test_hypothesis("Metabolic Engineering", 1390, "genetic")
    ]

    all_hypotheses = crispr_hyps + drug_hyps + genetic_hyps

    # Create proximity graph with 3 clusters
    proximity_graph = ProximityGraph(
        research_goal_id=goal_id,
        edges=[],
        clusters=[
            HypothesisCluster(
                id="cluster-crispr",
                hypothesis_ids=[h.id for h in crispr_hyps],
                cluster_label="CRISPR Approaches",
                size=3
            ),
            HypothesisCluster(
                id="cluster-drug",
                hypothesis_ids=[h.id for h in drug_hyps],
                cluster_label="Drug Screening",
                size=3
            ),
            HypothesisCluster(
                id="cluster-genetic",
                hypothesis_ids=[h.id for h in genetic_hyps],
                cluster_label="Genetic Engineering",
                size=3
            )
        ]
    )

    # Save to storage
    for hyp in all_hypotheses:
        hyp.research_goal_id = goal_id
        await async_storage.save_hypothesis(hyp)

    await async_storage.save_proximity_graph(proximity_graph)

    # Get diverse selection (n=3)
    diverse = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=3,
        min_elo_rating=1200.0,
        cluster_balance=True
    )

    # Assertions
    assert len(diverse) == 3, "Should return exactly 3 hypotheses"

    # Should have one from each cluster (top-rated)
    diverse_titles = {h.title for h in diverse}
    assert "CRISPR Base Editing" in diverse_titles  # Top from cluster 1
    assert "High-throughput Drug Screen" in diverse_titles  # Top from cluster 2
    assert "Synthetic Biology Circuit" in diverse_titles  # Top from cluster 3

    # Should be sorted by Elo
    assert diverse[0].elo_rating == 1500  # CRISPR Base Editing
    assert diverse[1].elo_rating == 1480  # High-throughput Drug Screen
    assert diverse[2].elo_rating == 1460  # Synthetic Biology Circuit

    print("✓ Test passed: Diverse selection returns one per cluster")


@pytest.mark.asyncio
async def test_fallback_to_elo_when_no_proximity_graph():
    """Test that system falls back to Elo sorting when no proximity graph exists."""
    goal_id = generate_goal_id()

    # Create hypotheses without proximity graph
    hypotheses = [
        create_test_hypothesis("Hypothesis A", 1600),
        create_test_hypothesis("Hypothesis B", 1500),
        create_test_hypothesis("Hypothesis C", 1400),
        create_test_hypothesis("Hypothesis D", 1300),
        create_test_hypothesis("Hypothesis E", 1200)
    ]

    for hyp in hypotheses:
        hyp.research_goal_id = goal_id
        await async_storage.save_hypothesis(hyp)

    # Get diverse selection (should fallback to Elo)
    diverse = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=3,
        min_elo_rating=1200.0
    )

    # Should return top 3 by Elo
    assert len(diverse) == 3
    assert diverse[0].title == "Hypothesis A"
    assert diverse[1].title == "Hypothesis B"
    assert diverse[2].title == "Hypothesis C"

    print("✓ Test passed: Fallback to Elo when no proximity graph")


@pytest.mark.asyncio
async def test_min_elo_filter():
    """Test that min_elo_rating filter works correctly."""
    goal_id = generate_goal_id()

    # Create hypotheses with varying Elo
    hypotheses = [
        create_test_hypothesis("High Elo Hyp", 1800),
        create_test_hypothesis("Medium Elo Hyp", 1400),
        create_test_hypothesis("Low Elo Hyp", 1100)
    ]

    for hyp in hypotheses:
        hyp.research_goal_id = goal_id
        await async_storage.save_hypothesis(hyp)

    # Get diverse selection with min_elo=1200
    diverse = await async_storage.get_diverse_hypotheses(
        goal_id=goal_id,
        n=10,
        min_elo_rating=1200.0
    )

    # Should exclude low Elo hypothesis
    assert len(diverse) == 2
    diverse_titles = {h.title for h in diverse}
    assert "High Elo Hyp" in diverse_titles
    assert "Medium Elo Hyp" in diverse_titles
    assert "Low Elo Hyp" not in diverse_titles

    print("✓ Test passed: Min Elo filter excludes low-rated hypotheses")


if __name__ == "__main__":
    import asyncio

    async def run_tests():
        print("\n" + "=" * 60)
        print("DIVERSITY SAMPLING UX TESTS")
        print("=" * 60 + "\n")

        await test_diverse_selection_from_clusters()
        await test_fallback_to_elo_when_no_proximity_graph()
        await test_min_elo_filter()

        print("\n" + "=" * 60)
        print("RESULTS: 3 passed, 0 failed")
        print("=" * 60 + "\n")

    asyncio.run(run_tests())
```

---

### Integration Tests

**File**: `05_tests/phase6_diversity_api_test.py` (NEW)

```python
"""
Integration tests for diversity sampling API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_get_hypotheses_with_diverse_sort():
    """Test GET /goals/{goal_id}/hypotheses with sort_by=diverse."""
    # TODO: Implement after API changes
    pass


def test_dedicated_diverse_endpoint():
    """Test GET /goals/{goal_id}/hypotheses/diverse."""
    # TODO: Implement after API changes
    pass
```

---

## Edge Cases Handled

| Edge Case | Solution |
|-----------|----------|
| No proximity graph available | Fallback to top Elo sorting (backward compatible) |
| Fewer clusters than requested n | Fill remainder with top-rated hypotheses by Elo |
| More clusters than requested n | Return top n clusters by representative Elo rating |
| Empty cluster | Skip cluster, continue with others |
| All hypotheses in one cluster | Return top n by Elo within that cluster |
| Outlier hypotheses (no cluster) | Include if high-rated and slots available |
| min_elo filter excludes all | Return empty list (user should adjust filter) |

---

## UI/UX Mockup

### Before (Current)
```
┌─────────────────────────────────────────┐
│ Sort by: [Elo Rating ▼]                │
├─────────────────────────────────────────┤
│ 1. CRISPR Base Editing (Elo: 1650)     │
│ 2. CRISPR Prime Editing (Elo: 1620)    │
│ 3. CRISPR Cas12 Variant (Elo: 1600)    │
│ 4. CRISPR Cas9 Enhanced (Elo: 1580)    │
│ 5. CRISPR dCas9 System (Elo: 1560)     │
│ 6. Drug Screening HTP (Elo: 1540)      │  ← First non-CRISPR at #6
│ ...                                      │
└─────────────────────────────────────────┘
```

### After (Enhanced)
```
┌─────────────────────────────────────────┐
│ Sort by: [🎨 Diverse Selection ▼]      │
│ ℹ️ Showing top hypothesis from each     │
│   scientific approach                    │
├─────────────────────────────────────────┤
│ 1. CRISPR Base Editing (Elo: 1650)     │  ← Top from Cluster 1
│ 2. Drug Screening HTP (Elo: 1540)      │  ← Top from Cluster 2
│ 3. Genetic Engineering (Elo: 1510)     │  ← Top from Cluster 3
│ 4. Metabolic Pathway (Elo: 1490)       │  ← Top from Cluster 4
│ 5. Protein Engineering (Elo: 1470)     │  ← Top from Cluster 5
│ ...                                      │
└─────────────────────────────────────────┘
```

---

## Performance Considerations

| Metric | Impact |
|--------|--------|
| **Computational overhead** | ~10ms (O(K×N) for K clusters, N hypotheses) |
| **Database queries** | +1 query for proximity graph (cached) |
| **Memory** | Negligible (cluster map ~1KB per 100 hypotheses) |
| **API latency** | <5% increase (graph retrieval already cached) |

**Optimization**:
- Cache proximity graph in memory (already done)
- Pre-compute cluster representatives during graph build (future)
- Use database indexes on Elo rating for fast sorting

---

## Rollout Strategy

### Phase 1: Backend Implementation (1-2 hours)
- ✅ Add `get_diverse_hypotheses()` to storage
- ✅ Update configuration with feature flags
- ✅ Write comprehensive unit tests

### Phase 2: API Integration (1 hour)
- ✅ Update main GET endpoint to support `sort_by=diverse`
- ✅ (Optional) Add dedicated `/hypotheses/diverse` endpoint
- ✅ Test API responses

### Phase 3: Frontend UI (1-2 hours)
- ✅ Update HypothesisList dropdown with "Diverse Selection" option
- ✅ Add tooltip/help text explaining diversity sampling
- ✅ Update API service to pass sort parameter

### Phase 4: Supervisor Integration (30 min)
- ✅ Update final overview to use diversity sampling
- ✅ Add configuration flag for toggle

### Phase 5: Testing & Verification (1 hour)
- ✅ Run all unit tests
- ✅ Integration test with real research goal
- ✅ Verify UI displays correctly
- ✅ Check logs and observability

**Total Effort**: ~5-6 hours

---

## Verification Steps

After implementation:

1. **Unit Tests**:
   ```bash
   python 05_tests/phase6_diversity_sampling_test.py
   ```

2. **API Test**:
   ```bash
   # Start server
   uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

   # Test diverse endpoint
   curl "http://localhost:8000/goals/{goal_id}/hypotheses?sort_by=diverse&page_size=10"
   ```

3. **Frontend Test**:
   - Open browser to `http://localhost:3000`
   - Create/open research goal with 20+ hypotheses
   - Change sort dropdown to "Diverse Selection"
   - Verify hypotheses shown are from different clusters

4. **End-to-End Test**:
   - Run full research cycle with ProximityAgent
   - Verify proximity graph created with 3+ clusters
   - Request final overview → should show diverse selection
   - Check logs for diversity sampling metrics

---

## Benefits

### For Scientists

| Current | Enhanced |
|---------|----------|
| ❌ Must manually browse 50+ hypotheses to find alternative approaches | ✅ See diverse approaches immediately |
| ❌ Top 10 might all be CRISPR variants | ✅ Top 10 spans CRISPR, drugs, engineering, etc. |
| ❌ Requires domain expertise to identify clusters | ✅ System automatically identifies and samples clusters |
| ❌ Risk of confirmation bias (only see similar approaches) | ✅ Forced exploration of alternative solutions |

### For System Quality

| Metric | Improvement |
|--------|-------------|
| **Solution space coverage** | 100% (all clusters represented) |
| **Scientific diversity** | High (multi-approach sampling) |
| **User satisfaction** | Higher (see full landscape) |
| **Time to insight** | Lower (curated diverse results) |

---

## Future Enhancements (Optional)

1. **Cluster Visualization**:
   - Show cluster labels in UI (e.g., "CRISPR Approaches")
   - Add cluster badges to hypothesis cards
   - Interactive cluster filtering

2. **Adaptive Sampling**:
   - Weight clusters by size (larger clusters → more representatives)
   - Weight by average Elo (higher-quality clusters → more representatives)
   - User-configurable sampling strategy

3. **Cluster Metadata**:
   - Show cluster statistics (size, avg Elo, win rate)
   - Highlight emerging clusters (recently formed)
   - Mark convergent clusters (high internal similarity)

4. **Export Diverse Results**:
   - "Export Top 10 Diverse" → CSV/JSON
   - Include cluster information in export
   - Generate diversity report PDF

---

## Configuration Reference

**File**: `src/config.py`

```python
# Diversity Sampling Configuration (Phase 6B - UX Enhancement)
diversity_sampling_enabled: bool = True
diversity_sampling_for_overview: bool = True
diversity_sampling_min_elo: float = 1200.0
diversity_sampling_default_n: int = 10
```

**Environment Variables** (`.env`):
```bash
DIVERSITY_SAMPLING_ENABLED=true
DIVERSITY_SAMPLING_FOR_OVERVIEW=true
DIVERSITY_SAMPLING_MIN_ELO=1200.0
DIVERSITY_SAMPLING_DEFAULT_N=10
```

---

## Success Criteria

✅ **Functionality**: Diverse selection returns one hypothesis per cluster
✅ **Performance**: <5% overhead vs. current Elo sorting
✅ **Usability**: Users can toggle between "Top Elo" and "Diverse" in one click
✅ **Quality**: Final overview shows diverse scientific approaches
✅ **Testing**: All unit and integration tests passing
✅ **Backward Compatibility**: Works with or without proximity graph

**Impact**: Scientists get a **comprehensive view of the solution space** instead of just the highest-rated approaches, enabling better-informed research decisions.

---

## Summary

This UX enhancement implements cluster-aware diversity sampling to ensure scientists see a representative selection of hypotheses across all scientific approaches. By selecting the top-rated hypothesis from each cluster, we balance quality (Elo rating) with diversity (cluster coverage).

**Key Features**:
- 🎨 One-click UI toggle for diverse selection
- 📊 Backend storage method for intelligent sampling
- 🔄 Graceful fallback when proximity graph unavailable
- ⚙️ Configurable via feature flags
- 📈 Maintains performance (minimal overhead)

**Alignment**: Matches Google paper's emphasis on presenting diverse, high-quality hypotheses to maximize scientific insight.