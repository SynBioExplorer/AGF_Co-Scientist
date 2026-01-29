"""Proximity Agent - Build similarity graphs and cluster hypotheses"""

from typing import List, Tuple, Optional, Dict
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, ProximityGraph, ProximityEdge, HypothesisCluster

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.config import settings
from src.utils.errors import CoScientistError
from src.utils.ids import generate_id
from src.observability.tracing import trace_agent
import json


class ProximityAgent(BaseAgent):
    """Build similarity graphs and cluster similar hypotheses

    Supports both vector-based similarity (fast, using embeddings) and
    LLM-based similarity (slower, more nuanced). Falls back to LLM
    when vector store is not available.
    """

    def __init__(
        self,
        vector_store=None,
        embedding_client=None,
        use_vectors: bool = True
    ):
        """Initialize Proximity Agent

        Args:
            vector_store: Optional vector store for fast similarity search
            embedding_client: Optional embedding client for generating vectors
            use_vectors: Whether to use vector similarity (requires vector_store and embedding_client)
        """
        llm_client = get_llm_client(
            model=settings.supervisor_model,  # Use fast model for similarity
            agent_name="proximity"
        )
        super().__init__(llm_client, "ProximityAgent")

        self.vector_store = vector_store
        self.embedding_client = embedding_client
        self.use_vectors = use_vectors and vector_store is not None and embedding_client is not None

        # Cache embeddings to avoid regenerating
        self._embedding_cache: Dict[str, List[float]] = {}

    @trace_agent("ProximityAgent")
    def execute(
        self,
        hypotheses: List[Hypothesis],
        research_goal_id: str,
        similarity_threshold: float = 0.7
    ) -> ProximityGraph:
        """Build proximity graph for hypotheses

        Args:
            hypotheses: List of hypotheses to analyze
            research_goal_id: Research goal ID for this graph
            similarity_threshold: Minimum similarity score for edge creation

        Returns:
            ProximityGraph with edges and clusters
        """

        self.log_execution(
            task="proximity_graph_building",
            num_hypotheses=len(hypotheses),
            threshold=similarity_threshold,
            using_vectors=self.use_vectors
        )

        # Calculate pairwise similarities
        edges = []
        for i in range(len(hypotheses)):
            for j in range(i + 1, len(hypotheses)):
                if self.use_vectors:
                    similarity = self._calculate_vector_similarity(
                        hypotheses[i],
                        hypotheses[j]
                    )
                else:
                    similarity = self._calculate_llm_similarity(
                        hypotheses[i],
                        hypotheses[j]
                    )

                if similarity >= similarity_threshold:
                    edge = ProximityEdge(
                        hypothesis_a_id=hypotheses[i].id,
                        hypothesis_b_id=hypotheses[j].id,
                        similarity_score=similarity,
                        common_themes=self._extract_common_themes(
                            hypotheses[i],
                            hypotheses[j]
                        )
                    )
                    edges.append(edge)

        self.logger.info(
            "Proximity edges created",
            num_edges=len(edges),
            avg_similarity=sum(e.similarity_score for e in edges) / len(edges) if edges else 0.0
        )

        # Cluster hypotheses using simple connected components
        clusters = self._build_clusters(hypotheses, edges)

        self.logger.info(
            "Hypothesis clusters created",
            num_clusters=len(clusters)
        )

        return ProximityGraph(
            research_goal_id=research_goal_id,
            edges=edges,
            clusters=clusters
        )

    def find_similar(
        self,
        hypothesis: Hypothesis,
        min_similarity: float = 0.7,
        limit: int = 10
    ) -> List[Tuple[str, float]]:
        """Find similar hypotheses to the given one

        Args:
            hypothesis: The hypothesis to find similar ones for
            min_similarity: Minimum similarity threshold
            limit: Maximum number of similar hypotheses to return

        Returns:
            List of (hypothesis_id, similarity_score) tuples
        """
        if not self.use_vectors:
            self.logger.warning(
                "find_similar called without vector support",
                falling_back_to="full graph computation"
            )
            return []

        # Get embedding for the hypothesis
        embedding = self._get_embedding(hypothesis)

        # Search vector store
        import asyncio
        results = asyncio.run(self.vector_store.search(
            query_embedding=embedding,
            collection_name="hypotheses",
            limit=limit,
            min_similarity=min_similarity
        ))

        # Convert to (id, score) tuples, excluding the query hypothesis itself
        similar = [
            (result.document.metadata.get("hypothesis_id", result.document.id), result.similarity)
            for result in results
            if result.document.metadata.get("hypothesis_id") != hypothesis.id
        ]

        return similar[:limit]

    def _get_embedding(self, hypothesis: Hypothesis) -> List[float]:
        """Get or compute embedding for a hypothesis

        Args:
            hypothesis: The hypothesis to embed

        Returns:
            Embedding vector
        """
        # Check cache first
        if hypothesis.id in self._embedding_cache:
            return self._embedding_cache[hypothesis.id]

        # Create text representation for embedding
        text = self._hypothesis_to_text(hypothesis)

        # Generate embedding
        embedding = self.embedding_client.embed(text)

        # Cache it
        self._embedding_cache[hypothesis.id] = embedding

        return embedding

    def _hypothesis_to_text(self, hypothesis: Hypothesis) -> str:
        """Convert hypothesis to text for embedding

        Args:
            hypothesis: The hypothesis

        Returns:
            Text representation
        """
        parts = [
            f"Title: {hypothesis.title}",
            f"Statement: {hypothesis.hypothesis_statement}",
        ]

        if hypothesis.mechanism:
            parts.append(f"Mechanism: {hypothesis.mechanism}")

        if hypothesis.rationale:
            parts.append(f"Rationale: {hypothesis.rationale[:200]}")

        return "\n".join(parts)

    def _calculate_vector_similarity(
        self,
        hyp_a: Hypothesis,
        hyp_b: Hypothesis
    ) -> float:
        """Calculate similarity using vector embeddings

        Args:
            hyp_a: First hypothesis
            hyp_b: Second hypothesis

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        try:
            embedding_a = self._get_embedding(hyp_a)
            embedding_b = self._get_embedding(hyp_b)

            # Calculate cosine similarity
            from src.storage.vector import BaseVectorStore
            similarity = BaseVectorStore.cosine_similarity(embedding_a, embedding_b)

            return float(similarity)

        except Exception as e:
            self.logger.warning(
                "Vector similarity calculation failed, falling back to LLM",
                error=str(e),
                hyp_a_id=hyp_a.id,
                hyp_b_id=hyp_b.id
            )
            return self._calculate_llm_similarity(hyp_a, hyp_b)

    def _calculate_llm_similarity(
        self,
        hyp_a: Hypothesis,
        hyp_b: Hypothesis
    ) -> float:
        """Calculate similarity between two hypotheses using LLM

        This is the fallback method when vector embeddings are not available.
        More nuanced but slower than vector-based similarity.
        """

        prompt = f"""Compare the similarity of these two scientific hypotheses on a scale of 0.0 to 1.0.

Hypothesis A:
Title: {hyp_a.title}
Statement: {hyp_a.hypothesis_statement}
Mechanism: {hyp_a.mechanism}

Hypothesis B:
Title: {hyp_b.title}
Statement: {hyp_b.hypothesis_statement}
Mechanism: {hyp_b.mechanism}

Consider:
- Do they address the same research question?
- Do they propose similar mechanisms?
- Do they target similar entities (genes, pathways, compounds)?
- Would they require similar experimental approaches?

Return ONLY a JSON object:
{{
    "similarity_score": 0.0-1.0,
    "reasoning": "Brief explanation"
}}"""

        try:
            response = self.llm_client.invoke(prompt)

            # Extract JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)
            return float(data["similarity_score"])

        except Exception as e:
            self.logger.warning(
                "Similarity calculation failed, using default",
                error=str(e),
                hyp_a_id=hyp_a.id,
                hyp_b_id=hyp_b.id
            )
            return 0.0

    def _extract_common_themes(
        self,
        hyp_a: Hypothesis,
        hyp_b: Hypothesis
    ) -> List[str]:
        """Extract common themes between hypotheses"""

        prompt = f"""Identify common themes between these two hypotheses.

Hypothesis A: {hyp_a.title}
{hyp_a.hypothesis_statement[:200]}

Hypothesis B: {hyp_b.title}
{hyp_b.hypothesis_statement[:200]}

Return ONLY a JSON object with a list of common themes:
{{
    "common_themes": ["theme1", "theme2", "theme3"]
}}

Limit to 3-5 most important themes."""

        try:
            response = self.llm_client.invoke(prompt)

            # Extract JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)
            return data.get("common_themes", [])

        except Exception as e:
            self.logger.warning(
                "Theme extraction failed",
                error=str(e)
            )
            return []

    def _build_clusters(
        self,
        hypotheses: List[Hypothesis],
        edges: List[ProximityEdge]
    ) -> List[HypothesisCluster]:
        """Build clusters using connected components algorithm"""

        # Build adjacency list
        adj = {h.id: set() for h in hypotheses}
        for edge in edges:
            adj[edge.hypothesis_a_id].add(edge.hypothesis_b_id)
            adj[edge.hypothesis_b_id].add(edge.hypothesis_a_id)

        # Find connected components
        visited = set()
        clusters = []

        def dfs(node_id: str, component: set):
            visited.add(node_id)
            component.add(node_id)
            for neighbor in adj[node_id]:
                if neighbor not in visited:
                    dfs(neighbor, component)

        for hyp in hypotheses:
            if hyp.id not in visited:
                component = set()
                dfs(hyp.id, component)

                if len(component) > 1:  # Only create cluster if multiple hypotheses
                    # Find common themes across all hypotheses in cluster
                    cluster_hypotheses = [h for h in hypotheses if h.id in component]
                    common_themes = self._find_cluster_themes(cluster_hypotheses)

                    # Generate cluster name from themes
                    cluster_name = ", ".join(common_themes[:2]) if common_themes else f"Cluster of {len(component)} hypotheses"

                    cluster = HypothesisCluster(
                        id=generate_id("cluster"),
                        name=cluster_name,
                        hypothesis_ids=list(component),
                        representative_id=cluster_hypotheses[0].id if cluster_hypotheses else None,
                        common_themes=common_themes,
                        cluster_summary=f"Cluster of {len(component)} similar hypotheses"
                    )
                    clusters.append(cluster)

        return clusters

    def _find_cluster_themes(self, hypotheses: List[Hypothesis]) -> List[str]:
        """Find common themes across cluster of hypotheses"""

        if len(hypotheses) < 2:
            return []

        # Combine all hypothesis titles and statements
        combined_text = "\n\n".join([
            f"{h.title}: {h.hypothesis_statement[:150]}"
            for h in hypotheses
        ])

        prompt = f"""Identify the main common themes across these related hypotheses:

{combined_text}

Return ONLY a JSON object:
{{
    "common_themes": ["theme1", "theme2", "theme3"]
}}

Limit to 3-5 most important common themes."""

        try:
            response = self.llm_client.invoke(prompt)

            # Extract JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)
            return data.get("common_themes", [])

        except Exception as e:
            self.logger.warning(
                "Cluster theme extraction failed",
                error=str(e)
            )
            return []
