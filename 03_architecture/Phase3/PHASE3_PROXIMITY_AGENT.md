# Phase 3: Proximity Agent

## Overview

The Proximity Agent calculates similarity between hypotheses and builds a proximity graph for clustering similar ideas, enabling deduplication and efficient exploration.

**File:** `src/agents/proximity.py`
**Status:** ✅ Complete

## Capabilities

Based on Google AI Co-Scientist paper (Section 3.3.4):

1. **Pairwise Similarity** - Calculate similarity between hypothesis pairs
2. **Proximity Graph** - Build graph with similarity edges
3. **Clustering** - Group similar hypotheses
4. **Theme Extraction** - Identify common themes in clusters

## Implementation

```python
from typing import List, Tuple
from src.agents.base import BaseAgent
from src.llm.base import BaseLLMClient
from schemas import (
    Hypothesis, ProximityGraph, ProximityEdge,
    HypothesisCluster, ResearchGoal
)
import structlog

logger = structlog.get_logger()

class ProximityAgent(BaseAgent):
    """Agent for computing hypothesis similarity and clustering"""

    def __init__(self, llm_client: BaseLLMClient):
        super().__init__(llm_client, "ProximityAgent")

    async def execute(
        self,
        hypotheses: List[Hypothesis],
        research_goal: ResearchGoal,
        similarity_threshold: float = 0.7
    ) -> ProximityGraph:
        """Build proximity graph for hypotheses

        Args:
            hypotheses: List of hypotheses to analyze
            research_goal: Research goal for context
            similarity_threshold: Min similarity for edge creation

        Returns:
            ProximityGraph with edges and clusters
        """
        self.log_execution(
            task="proximity_analysis",
            hypothesis_count=len(hypotheses),
            threshold=similarity_threshold
        )

        # Calculate pairwise similarities
        edges = await self._compute_pairwise_similarities(
            hypotheses, research_goal, similarity_threshold
        )

        # Build clusters from edges
        clusters = self._build_clusters(hypotheses, edges)

        # Extract themes for each cluster
        for cluster in clusters:
            cluster.common_themes = await self._extract_themes(
                cluster, research_goal
            )

        graph = ProximityGraph(
            research_goal_id=research_goal.id,
            edges=edges,
            clusters=clusters
        )

        logger.info(
            "Proximity graph built",
            edges=len(edges),
            clusters=len(clusters)
        )

        return graph

    async def _compute_pairwise_similarities(
        self,
        hypotheses: List[Hypothesis],
        goal: ResearchGoal,
        threshold: float
    ) -> List[ProximityEdge]:
        """Compute similarity between all hypothesis pairs"""
        edges = []

        for i, hyp_a in enumerate(hypotheses):
            for hyp_b in hypotheses[i+1:]:
                similarity = await self._compute_similarity(
                    hyp_a, hyp_b, goal
                )

                if similarity >= threshold:
                    edge = ProximityEdge(
                        hypothesis_a_id=hyp_a.id,
                        hypothesis_b_id=hyp_b.id,
                        similarity_score=similarity
                    )
                    edges.append(edge)

                    logger.debug(
                        "Similarity computed",
                        hyp_a=hyp_a.id[:15],
                        hyp_b=hyp_b.id[:15],
                        similarity=similarity
                    )

        return edges

    async def _compute_similarity(
        self,
        hyp_a: Hypothesis,
        hyp_b: Hypothesis,
        goal: ResearchGoal
    ) -> float:
        """Compute similarity between two hypotheses using LLM"""

        prompt = f"""
        Research Goal: {goal.description}

        Hypothesis A:
        Title: {hyp_a.title}
        Statement: {hyp_a.hypothesis_statement}
        Mechanism: {hyp_a.mechanism}

        Hypothesis B:
        Title: {hyp_b.title}
        Statement: {hyp_b.hypothesis_statement}
        Mechanism: {hyp_b.mechanism}

        How similar are these hypotheses in terms of:
        - Core concept/approach
        - Target/mechanism
        - Experimental strategy

        Return a similarity score from 0.0 (completely different) to 1.0 (nearly identical).

        Return JSON:
        {{
            "similarity_score": 0.0-1.0,
            "reasoning": "Brief explanation"
        }}
        """

        response = await self.llm_client.generate(prompt)

        from src.utils.json_parser import parse_llm_json
        data = parse_llm_json(response)

        return data.get("similarity_score", 0.0)

    def _build_clusters(
        self,
        hypotheses: List[Hypothesis],
        edges: List[ProximityEdge]
    ) -> List[HypothesisCluster]:
        """Build clusters using connected components algorithm"""

        # Build adjacency list
        adjacency = {h.id: set() for h in hypotheses}
        for edge in edges:
            adjacency[edge.hypothesis_a_id].add(edge.hypothesis_b_id)
            adjacency[edge.hypothesis_b_id].add(edge.hypothesis_a_id)

        # Find connected components using BFS
        visited = set()
        clusters = []
        cluster_id = 0

        for hyp in hypotheses:
            if hyp.id in visited:
                continue

            # BFS to find component
            component = []
            queue = [hyp.id]

            while queue:
                node_id = queue.pop(0)
                if node_id in visited:
                    continue

                visited.add(node_id)
                component.append(node_id)

                for neighbor in adjacency[node_id]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            # Only create cluster if more than 1 hypothesis
            if len(component) > 1:
                clusters.append(HypothesisCluster(
                    id=f"cluster_{cluster_id}",
                    hypothesis_ids=component,
                    common_themes=[]  # Filled later
                ))
                cluster_id += 1

        return clusters

    async def _extract_themes(
        self,
        cluster: HypothesisCluster,
        goal: ResearchGoal
    ) -> List[str]:
        """Extract common themes from clustered hypotheses"""

        # Get hypothesis titles/statements for the cluster
        # (In practice, would fetch from storage)
        prompt = f"""
        Research Goal: {goal.description}

        These hypotheses have been clustered together:
        {', '.join(cluster.hypothesis_ids)}

        What are the 2-3 common themes that unite these hypotheses?

        Return JSON:
        {{
            "themes": ["theme1", "theme2", "theme3"]
        }}
        """

        response = await self.llm_client.generate(prompt)

        from src.utils.json_parser import parse_llm_json
        data = parse_llm_json(response)

        return data.get("themes", [])

    async def find_similar(
        self,
        hypothesis: Hypothesis,
        candidates: List[Hypothesis],
        goal: ResearchGoal,
        top_k: int = 5
    ) -> List[Tuple[Hypothesis, float]]:
        """Find most similar hypotheses to a given one

        Args:
            hypothesis: Reference hypothesis
            candidates: Hypotheses to compare against
            goal: Research goal for context
            top_k: Number of similar hypotheses to return

        Returns:
            List of (hypothesis, similarity_score) sorted by similarity
        """
        similarities = []

        for candidate in candidates:
            if candidate.id == hypothesis.id:
                continue

            score = await self._compute_similarity(
                hypothesis, candidate, goal
            )
            similarities.append((candidate, score))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]
```

## Output Schema

```python
class ProximityEdge(BaseModel):
    hypothesis_a_id: str
    hypothesis_b_id: str
    similarity_score: float  # 0.0 to 1.0

class HypothesisCluster(BaseModel):
    id: str                      # cluster_0, cluster_1, ...
    hypothesis_ids: List[str]
    common_themes: List[str]

class ProximityGraph(BaseModel):
    research_goal_id: str
    edges: List[ProximityEdge]
    clusters: List[HypothesisCluster]
```

## Clustering Algorithm

Uses connected components via BFS:

```
1. Build adjacency list from edges (threshold > 0.7)
2. BFS from each unvisited node
3. Each connected component = cluster
4. Extract themes for each cluster
```

Example:
```
Hypotheses: A, B, C, D, E
Edges (sim > 0.7): A-B, B-C, D-E

Clusters:
- Cluster 0: [A, B, C]  (connected through B)
- Cluster 1: [D, E]      (connected directly)
```

## Use Cases

### Deduplication
Identify near-duplicate hypotheses:
```python
# Find hypotheses with similarity > 0.95
duplicates = [e for e in graph.edges if e.similarity_score > 0.95]
```

### Theme Discovery
Identify research patterns:
```python
for cluster in graph.clusters:
    print(f"Cluster themes: {cluster.common_themes}")
```

### Tournament Pairing
The Ranking Agent uses proximity for match selection:
```python
# Pair similar hypotheses for meaningful comparisons
similar = await proximity_agent.find_similar(hyp, candidates, goal, top_k=3)
match_opponent = similar[0][0]  # Most similar
```

## Usage

```python
from src.agents.proximity import ProximityAgent
from src.llm.factory import get_llm_client

agent = ProximityAgent(get_llm_client())

# Build proximity graph
graph = await agent.execute(
    hypotheses=all_hypotheses,
    research_goal=goal,
    similarity_threshold=0.7
)

print(f"Edges: {len(graph.edges)}")
print(f"Clusters: {len(graph.clusters)}")

for cluster in graph.clusters:
    print(f"\nCluster {cluster.id}:")
    print(f"  Hypotheses: {len(cluster.hypothesis_ids)}")
    print(f"  Themes: {cluster.common_themes}")

# Find similar hypotheses
similar = await agent.find_similar(
    hypothesis=new_hypothesis,
    candidates=existing_hypotheses,
    goal=goal,
    top_k=3
)

for hyp, score in similar:
    print(f"  {hyp.title}: {score:.2f}")
```

## Testing

```python
@pytest.mark.asyncio
async def test_proximity_agent():
    """Test proximity graph building"""
    agent = ProximityAgent(get_llm_client())

    # Create hypotheses with known similarity
    similar_hyps = [hyp_a, hyp_b]  # Similar
    different_hyp = hyp_c         # Different

    graph = await agent.execute(
        hypotheses=similar_hyps + [different_hyp],
        research_goal=goal,
        similarity_threshold=0.7
    )

    # Should have edge between similar hypotheses
    assert len(graph.edges) >= 1
    assert graph.edges[0].similarity_score >= 0.7

@pytest.mark.asyncio
async def test_find_similar():
    """Test similar hypothesis search"""
    agent = ProximityAgent(get_llm_client())

    similar = await agent.find_similar(
        hypothesis=target,
        candidates=candidates,
        goal=goal,
        top_k=3
    )

    assert len(similar) <= 3
    # Should be sorted by similarity
    scores = [s[1] for s in similar]
    assert scores == sorted(scores, reverse=True)
```
