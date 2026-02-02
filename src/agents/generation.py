"""Generation Agent - Create hypotheses via literature exploration or debate"""

from typing import Dict, Any, List, Tuple, Optional
from pydantic import ValidationError as PydanticValidationError
import asyncio
import sys
import json
import re
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, ResearchGoal, Citation, ExperimentalProtocol, GenerationMethod

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.prompts.loader import prompt_manager
from src.utils.ids import generate_hypothesis_id
from src.utils.errors import CoScientistError
from src.utils.web_search import get_search_client
from src.utils.json_parser import parse_llm_json
from src.config import settings
from src.observability.tracing import trace_agent
from src.tools.registry import get_tool_registry, initialize_tools
from src.literature.citation_graph import CitationGraph
from src.literature.graph_expander import CitationGraphExpander, ExpansionStrategy
from src.literature.source_merger import CitationSourceMerger
from src.storage.cache import RedisCache
# Phase 6: Evidence quality enhancement imports
from src.literature.quality_scorer import PaperQualityScorer
from src.literature.limitations_extractor import LimitationsExtractor
import json
import hashlib


class GenerationAgent(BaseAgent):
    """Generate hypotheses via literature exploration or simulated debate"""

    def __init__(self, cache: Optional[RedisCache] = None):
        llm_client = get_llm_client(
            model=settings.generation_model,
            agent_name="generation"
        )
        super().__init__(llm_client, "GenerationAgent")

        # Initialize tool registry
        self.tool_registry = initialize_tools()

        # Initialize merger and cache (Phase 6 Week 4)
        self.merger = CitationSourceMerger(
            source_priority=settings.citation_source_priority
        )
        self.cache = cache  # Optional Redis cache

        # Phase 6: Evidence quality enhancement
        self.quality_scorer = PaperQualityScorer(
            citation_weight=settings.quality_citation_weight,
            recency_weight=settings.quality_recency_weight,
            journal_weight=settings.quality_journal_weight,
            min_threshold=settings.quality_min_threshold,
            recency_halflife_years=settings.quality_recency_halflife_years
        )
        self.limitations_extractor = LimitationsExtractor(
            min_confidence=settings.limitations_min_confidence
        )

    def _enrich_papers_with_quality(
        self,
        papers: List[Any]
    ) -> List[Any]:
        """
        Score papers and filter by quality threshold.

        Phase 6 integration: Uses PaperQualityScorer to rank and filter papers
        before including them in LLM context.

        Args:
            papers: List of CitationNode objects from search

        Returns:
            Filtered and ranked list of papers (highest quality first)
        """
        if not settings.enable_quality_scoring or not papers:
            return papers

        # Score each paper
        for paper in papers:
            paper.quality_score = self.quality_scorer.compute_quality_score(paper)

        # Filter by threshold
        filtered = self.quality_scorer.filter_by_quality(papers)

        # Rank by quality (highest first)
        ranked = self.quality_scorer.rank_papers_by_quality(filtered, top_k=len(filtered))

        self.logger.info(
            "Papers enriched with quality scores",
            total=len(papers),
            passed_filter=len(ranked),
            threshold=settings.quality_min_threshold
        )

        return ranked

    def _extract_paper_limitations(
        self,
        papers: List[Any]
    ) -> str:
        """
        Extract limitations from papers for LLM context.

        Phase 6 integration: Uses LimitationsExtractor to surface caveats
        and negative results from literature.

        Args:
            papers: List of CitationNode objects

        Returns:
            Formatted limitations string or empty if disabled
        """
        if not settings.enable_limitations_extraction or not papers:
            return ""

        # Batch extract from abstracts (full text not available in this pipeline)
        limitations_data = self.limitations_extractor.batch_extract(papers)

        # Format for context
        context = self.limitations_extractor.format_batch_for_context(
            papers,
            limitations_data,
            min_confidence=settings.limitations_min_confidence
        )

        if context:
            papers_with_limitations = sum(
                1 for d in limitations_data.values() if d.get("limitations")
            )
            self.logger.info(
                "Limitations extracted",
                papers_with_limitations=papers_with_limitations,
                total_papers=len(papers)
            )

        return context

    async def _search_literature_tools(
        self,
        research_goal: ResearchGoal,
        max_results: int = 10
    ) -> Tuple[List[Dict[str, Any]], CitationGraph]:
        """
        Search literature using tool registry (PubMed + Semantic Scholar).
        Uses CitationSourceMerger to deduplicate and caching for performance.

        Args:
            research_goal: Research goal for context
            max_results: Maximum papers to retrieve

        Returns:
            Tuple of (search_results, citation_graph)
        """
        # Check cache first (Phase 6 Week 4)
        cache_key = None
        if self.cache:
            query_hash = hashlib.sha256(research_goal.description.encode()).hexdigest()[:16]
            cache_key = f"goal:{research_goal.id}:{query_hash}"
            cached_graph = await self.cache.get_citation_graph(cache_key)

            if cached_graph:
                self.logger.info("Citation graph cache hit", key=cache_key)
                # Convert graph nodes to results list
                results = [
                    {
                        "title": node.title,
                        "authors": node.authors,
                        "year": node.year,
                        "doi": node.doi,
                        "pmid": node.pmid,
                        "citation_count": node.citation_count,
                        "abstract": node.abstract
                    }
                    for node in cached_graph.nodes.values()
                ]
                return results, cached_graph

        # Cache miss - search from sources
        pubmed_results = []
        semantic_results = []

        # Try PubMed tool (biomedical)
        pubmed_tool = self.tool_registry.get("pubmed")
        if pubmed_tool:
            try:
                pubmed_result = await pubmed_tool.execute(
                    research_goal.description,
                    max_results=max_results // 2
                )
                if pubmed_result.success:
                    # Add source tag for merger
                    for paper in pubmed_result.data:
                        paper["source"] = "pubmed"
                    pubmed_results = pubmed_result.data

                    self.logger.info(
                        "PubMed search successful",
                        num_results=len(pubmed_results)
                    )
            except Exception as e:
                self.logger.warning("PubMed search failed", error=str(e))

        # Try Semantic Scholar tool (cross-disciplinary)
        semantic_tool = self.tool_registry.get("semantic_scholar")
        if semantic_tool:
            try:
                semantic_result = await semantic_tool.execute(
                    research_goal.description,
                    max_results=max_results // 2
                )
                if semantic_result.success:
                    # Add source tag for merger
                    for paper in semantic_result.data:
                        paper["source"] = "semantic_scholar"
                    semantic_results = semantic_result.data

                    self.logger.info(
                        "Semantic Scholar search successful",
                        num_results=len(semantic_results)
                    )
            except Exception as e:
                self.logger.warning("Semantic Scholar search failed", error=str(e))

        # Merge papers from multiple sources (Phase 6 Week 4)
        all_papers = pubmed_results + semantic_results
        if all_papers:
            # Wrap sync merger in thread to avoid blocking event loop
            merged_papers = await asyncio.to_thread(self.merger.merge_papers, all_papers)

            # Log merge statistics
            stats = await asyncio.to_thread(
                self.merger.get_merge_statistics,
                all_papers,
                merged_papers
            )
            self.logger.info(
                "Papers merged",
                total_before=stats["total_before"],
                total_after=stats["total_after"],
                duplicates_removed=stats["duplicates_removed"]
            )

            results = merged_papers
        else:
            results = []

        # Return empty graph (will be populated during expansion)
        graph = CitationGraph()

        return results, graph

    async def _expand_citation_graph(
        self,
        search_results: List[Dict[str, Any]],
        graph: CitationGraph,
        max_depth: int = 1,
        research_goal: Optional[ResearchGoal] = None
    ) -> CitationGraph:
        """
        Expand citation graph from search results with parallel processing and caching.

        Args:
            search_results: Initial papers from search
            graph: Citation graph to expand
            max_depth: Depth of citation expansion
            research_goal: Optional research goal for cache key generation

        Returns:
            Expanded CitationGraph
        """
        # Get Semantic Scholar tool for citation expansion
        semantic_tool = self.tool_registry.get("semantic_scholar")
        if not semantic_tool or not search_results:
            return graph

        # Create expander
        expander = CitationGraphExpander(
            graph=graph,
            tools={"semantic_scholar": semantic_tool}
        )

        try:
            # Expand from top results (backward strategy to find foundational work)
            # Phase 6 Week 4: Parallel expansion if enabled
            if settings.enable_parallel_expansion:
                # Expand multiple papers in parallel (limited by max_parallel_expansions)
                import asyncio
                top_papers = search_results[:settings.max_parallel_expansions]

                tasks = [
                    expander.expand_from_paper(
                        paper_id=paper.get("doi") or paper.get("pmid") or paper.get("paperId"),
                        strategy=ExpansionStrategy.BACKWARD,
                        max_depth=max_depth,
                        limit_per_direction=10
                    )
                    for paper in top_papers
                    if paper.get("doi") or paper.get("pmid") or paper.get("paperId")
                ]

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Sequential expansion (original behavior)
                await expander.expand_from_results(
                    search_results,
                    depth=max_depth,
                    strategy=ExpansionStrategy.BACKWARD,
                    limit_per_direction=10
                )

            self.logger.info(
                "Citation graph expanded",
                total_papers=len(graph.nodes),
                total_edges=len(graph.edges),
                parallel=settings.enable_parallel_expansion
            )

            # Cache the expanded graph (Phase 6 Week 4)
            if self.cache and research_goal:
                query_hash = hashlib.sha256(research_goal.description.encode()).hexdigest()[:16]
                cache_key = f"goal:{research_goal.id}:{query_hash}"
                await self.cache.set_citation_graph(cache_key, graph)
                self.logger.info("Citation graph cached", key=cache_key)

        except Exception as e:
            self.logger.warning("Citation expansion failed", error=str(e))

        return graph

    def _format_citation_graph_context(
        self,
        graph: CitationGraph,
        max_papers: int = 20
    ) -> str:
        """
        Format citation graph as context for LLM.

        Phase 6 enhancement: Includes quality labels and skips retracted papers.

        Args:
            graph: Citation graph to format
            max_papers: Maximum papers to include

        Returns:
            Formatted string with paper summaries and quality labels
        """
        if not graph.nodes:
            return ""

        # Get papers, optionally sorted by quality score if available
        papers_list = list(graph.nodes.values())

        # Phase 6: Filter out retracted papers
        non_retracted = [
            p for p in papers_list
            if not getattr(p, 'is_retracted', False)
        ]

        if len(non_retracted) < len(papers_list):
            retracted_count = len(papers_list) - len(non_retracted)
            self.logger.warning(
                "Retracted papers excluded from context",
                retracted_count=retracted_count
            )

        # Rank by quality score if available, otherwise by citation count
        if any(getattr(p, 'quality_score', None) is not None for p in non_retracted):
            papers = sorted(
                non_retracted,
                key=lambda p: getattr(p, 'quality_score', 0) or 0,
                reverse=True
            )[:max_papers]
        else:
            papers = sorted(
                non_retracted,
                key=lambda p: p.citation_count or 0,
                reverse=True
            )[:max_papers]

        context_parts = ["**Citation Network Analysis:**\n"]

        paper_num = 0
        for paper in papers:
            paper_num += 1

            # Phase 6: Get quality label
            quality_score = getattr(paper, 'quality_score', None)
            if quality_score is not None:
                quality_label = self.quality_scorer.get_quality_label(quality_score)
            else:
                quality_label = "UNSCORED"

            # Get citations this paper makes
            citations = graph.get_citations(paper.id)
            cited_by = graph.get_cited_by(paper.id)

            context_parts.append(
                f"\n**Paper {paper_num}:** {paper.title}\n"
                f"[QUALITY: {quality_label}]\n"
                f"Authors: {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}\n"
                f"Year: {paper.year or 'N/A'}\n"
                f"DOI: {paper.doi or 'N/A'}\n"
                f"Citations: {paper.citation_count} | References: {paper.reference_count}\n"
                f"Graph connections: Cites {len(citations)} papers, Cited by {len(cited_by)} papers\n"
            )

        return "\n".join(context_parts)

    def _search_tavily_fallback(self, research_goal: ResearchGoal) -> str:
        """
        Fallback to Tavily web search if literature tools fail.

        Args:
            research_goal: Research goal for search query

        Returns:
            Formatted search results string
        """
        if not settings.tavily_api_key:
            return ""

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
                "Tavily fallback search completed",
                num_articles=len(results)
            )

            return articles_with_reasoning

        except Exception as e:
            self.logger.warning(
                "Tavily fallback failed",
                error=str(e)
            )
            return ""

    @trace_agent("GenerationAgent")
    async def execute(
        self,
        research_goal: ResearchGoal,
        method: GenerationMethod = GenerationMethod.LITERATURE_EXPLORATION,
        use_literature_expansion: bool = True
    ) -> Hypothesis:
        """Generate a hypothesis

        Args:
            research_goal: Research goal to address
            method: Generation method (literature or debate)
            use_literature_expansion: Whether to use literature tools + citation expansion

        Returns:
            Generated Hypothesis
        """

        self.log_execution(
            task="hypothesis_generation",
            goal=research_goal.description[:100],
            method=method.value,
            literature_expansion=use_literature_expansion
        )

        # Literature context
        literature_context = ""
        limitations_context = ""
        citation_graph = CitationGraph()  # Initialize empty graph

        if use_literature_expansion:
            try:
                # Try structured literature tools first
                search_results, citation_graph = await self._search_literature_tools(
                    research_goal,
                    max_results=10
                )

                if search_results:
                    # Expand citation graph (depth=1) with caching
                    citation_graph = await self._expand_citation_graph(
                        search_results,
                        citation_graph,
                        max_depth=1,
                        research_goal=research_goal
                    )

                    # Phase 6: Enrich papers with quality scores
                    graph_papers = list(citation_graph.nodes.values())
                    quality_papers = self._enrich_papers_with_quality(graph_papers)

                    # Phase 6: Extract limitations from papers
                    limitations_context = self._extract_paper_limitations(quality_papers)

                    # Format as context (now includes quality labels)
                    literature_context = self._format_citation_graph_context(
                        citation_graph,
                        max_papers=20
                    )

                    # Append limitations if available
                    if limitations_context:
                        literature_context = f"{literature_context}\n\n{limitations_context}"

                # Fallback to Tavily if no results
                if not literature_context:
                    self.logger.info("No results from literature tools, trying Tavily fallback")
                    literature_context = self._search_tavily_fallback(research_goal)

            except Exception as e:
                self.logger.warning(
                    "Literature expansion failed, trying Tavily fallback",
                    error=str(e)
                )
                literature_context = self._search_tavily_fallback(research_goal)

        # Format prompt
        method_str = "literature" if method == GenerationMethod.LITERATURE_EXPLORATION else "debate"
        prompt = prompt_manager.format_generation_prompt(
            goal=research_goal.description,
            preferences=research_goal.preferences,
            method=method_str,
            articles_with_reasoning=literature_context
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
            data = parse_llm_json(response, agent_name="GenerationAgent")

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

            # Validate and enrich citations if literature expansion was used
            if use_literature_expansion:
                hypothesis = await self._validate_citations(hypothesis, citation_graph)

            self.logger.info(
                "Hypothesis generated",
                hypothesis_id=hypothesis.id,
                title=hypothesis.title,
                num_citations=len(hypothesis.literature_citations)
            )

            return hypothesis

        except (json.JSONDecodeError, PydanticValidationError, KeyError) as e:
            raise CoScientistError(f"Failed to parse LLM response: {e}\nResponse: {response[:500]}")

    async def _validate_citations(
        self,
        hypothesis: Hypothesis,
        citation_graph: CitationGraph
    ) -> Hypothesis:
        """
        Validate and enrich hypothesis citations.

        Phase 6 enhancement: Also checks retraction status.

        Args:
            hypothesis: Generated hypothesis
            citation_graph: Citation graph from expansion

        Returns:
            Hypothesis with validated citations
        """
        if not hypothesis.literature_citations:
            return hypothesis

        validated_citations = []
        semantic_tool = self.tool_registry.get("semantic_scholar")

        for citation in hypothesis.literature_citations:
            # Check if DOI exists in citation graph
            doi_in_graph = False
            is_retracted = False

            if citation.doi:
                for node in citation_graph.nodes.values():
                    if node.doi == citation.doi:
                        doi_in_graph = True
                        # Enrich with graph data
                        citation.title = citation.title or node.title

                        # Phase 6: Check retraction status
                        if getattr(node, 'is_retracted', False):
                            is_retracted = True
                            self.logger.warning(
                                "Citation references retracted paper",
                                citation_title=citation.title,
                                doi=citation.doi
                            )
                        break

            # If not in graph and we have Semantic Scholar, fetch it
            if not doi_in_graph and citation.doi and semantic_tool:
                try:
                    paper = await semantic_tool.get_paper(f"DOI:{citation.doi}")
                    if paper:
                        # Add to graph for future use
                        citation_graph.add_paper(
                            paper_id=paper.paper_id,
                            title=paper.title,
                            authors=paper.authors,
                            year=paper.year,
                            doi=paper.doi
                        )
                        self.logger.info(
                            "Citation validated and added to graph",
                            doi=citation.doi
                        )
                except Exception as e:
                    self.logger.warning(
                        "Could not validate citation",
                        doi=citation.doi,
                        error=str(e)
                    )

            # Only include non-retracted citations
            if not is_retracted:
                validated_citations.append(citation)
            else:
                self.logger.info(
                    "Excluding retracted citation",
                    title=citation.title
                )

        hypothesis.literature_citations = validated_citations
        return hypothesis
