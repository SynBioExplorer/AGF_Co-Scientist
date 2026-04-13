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

    async def _generate_via_debate(
        self,
        research_goal: ResearchGoal,
        literature_context: str = "",
        existing_titles: list = None,
    ) -> Hypothesis:
        """Generate a hypothesis through simulated multi-expert scientific debate.

        Paper Section 3.3.1: "simulates scientific debates among experts by
        employing self-critique and self-play techniques. These debates typically
        involve multiple turns of conversations leading to a refined hypothesis."

        Args:
            research_goal: Research goal to address.
            literature_context: Literature context from prior search.

        Returns:
            Hypothesis refined through multi-expert debate.
        """
        from src.utils.json_parser import parse_llm_json

        expert_roles = [
            ("Domain Expert",
             f"You are a leading domain expert on: {research_goal.description[:200]}. "
             "You bring mechanistic insights, cite relevant prior work, and propose concrete hypotheses."),
            ("Methodologist",
             "You are an experimental methodologist. You evaluate proposals for feasibility, "
             "statistical power, appropriate controls, and potential confounders."),
            ("Devil's Advocate",
             "You are a critical reviewer who challenges assumptions, identifies logical gaps, "
             "highlights failure modes, and pushes toward more robust and novel hypotheses."),
        ]

        transcript = ""
        num_turns = 3

        for turn in range(1, num_turns + 1):
            for name, persona in expert_roles:
                turn_prompt = f"""{persona}

Turn {turn}/{num_turns} of a scientific debate to develop a novel hypothesis.

Research Goal: {research_goal.description}
{f"Hard constraints: " + "; ".join(research_goal.constraints) if research_goal.constraints else ""}
{f"Literature Context: {literature_context[:3000]}" if literature_context else ""}
{f"DEBATE SO FAR:{transcript}" if transcript else "This is the opening. No prior discussion."}

As {name}, contribute:
- If early: propose or refine hypothesis ideas
- Build on strengths, challenge weaknesses from prior speakers
- In later turns: converge toward a refined, testable hypothesis

Respond as {name}:"""

                response = await self.llm_client.ainvoke(turn_prompt)
                transcript += f"\n\n--- Turn {turn}, {name} ---\n{response}"

        # Synthesis
        synthesis_prompt = f"""Synthesize this multi-expert debate into a single refined hypothesis.

Research Goal: {research_goal.description}

FULL DEBATE:
{transcript}

Extract the strongest ideas, address criticisms, and produce a coherent hypothesis.

CRITICAL: The hypothesis MUST be specifically about: {research_goal.description}
Do NOT propose ideas about unrelated topics, organisms, or fields.
{f"Hard constraints: " + "; ".join(research_goal.constraints) if research_goal.constraints else ""}
{f"EXISTING HYPOTHESES (do NOT duplicate): " + "; ".join(existing_titles[:10]) if existing_titles else ""}

Cite the most relevant papers discussed during the debate. Include title, DOI, and relevance.

Design the experiment in 2-3 phases with explicit go/no-go criteria. Phase 1 must validate the single highest-risk component before integration.

Return ONLY valid JSON:
{{
    "title": "Brief hypothesis title",
    "statement": "Full hypothesis statement",
    "rationale": "Scientific reasoning from debate",
    "mechanism": "Proposed mechanism",
    "experimental_protocol": {{
        "objective": "What the experiment tests",
        "methodology": "Experimental approach",
        "controls": ["Control 1"],
        "expected_outcomes": ["Outcome 1"],
        "success_criteria": "What constitutes success",
        "materials": ["Key reagent/strain 1", "Key equipment 1"],
        "limitations": ["Known limitation 1"],
        "estimated_timeline": "Estimated duration (e.g., 6-9 months)",
        "phased_milestones": [
            {{"phase": "Phase 1: Validate highest-risk component", "go_no_go": "Criteria to proceed"}},
            {{"phase": "Phase 2: Integrate and test", "go_no_go": "Criteria for success"}}
        ]
    }},
    "citations": [{{"title": "Paper", "doi": "", "relevance": "Why relevant"}}]
}}"""

        synthesis = await self.llm_client.ainvoke(synthesis_prompt)
        data = parse_llm_json(synthesis, agent_name="GenerationAgent-Debate")

        protocol_data = data.get("experimental_protocol", {})
        # Resilient protocol parsing for debate path
        def _coerce(v, as_list):
            if as_list and isinstance(v, str):
                return [v]
            if not as_list and isinstance(v, list):
                return "\n".join(str(x) for x in v)
            return v

        hypothesis = Hypothesis(
            id=generate_hypothesis_id(),
            research_goal_id=research_goal.id,
            title=data.get("title", "Debate-generated hypothesis"),
            summary=data.get("title", ""),
            hypothesis_statement=data.get("statement", ""),
            rationale=data.get("rationale", ""),
            mechanism=data.get("mechanism"),
            experimental_protocol=ExperimentalProtocol(
                objective=_coerce(protocol_data.get("objective", ""), as_list=False),
                methodology=_coerce(protocol_data.get("methodology", ""), as_list=False),
                controls=_coerce(protocol_data.get("controls", []), as_list=True),
                expected_outcomes=_coerce(protocol_data.get("expected_outcomes", []), as_list=True),
                success_criteria=_coerce(protocol_data.get("success_criteria", ""), as_list=False),
                materials=_coerce(protocol_data.get("materials", []), as_list=True),
                limitations=_coerce(protocol_data.get("limitations", []), as_list=True),
                estimated_timeline=protocol_data.get("estimated_timeline"),
                phased_milestones=protocol_data.get("phased_milestones", []) or [],
            ),
            literature_citations=[
                Citation(**c) for c in data.get("citations", [])
                if isinstance(c, dict) and "title" in c
            ],
            generation_method=GenerationMethod.SIMULATED_DEBATE,
            elo_rating=1200.0
        )

        self.logger.info(
            "Debate synthesis complete",
            hypothesis_id=hypothesis.id,
            title=hypothesis.title,
        )
        return hypothesis

    async def _generate_via_iterative_assumptions(
        self,
        research_goal: ResearchGoal,
        existing_titles: list = None,
    ) -> Optional[Hypothesis]:
        """Generate a hypothesis via iterative assumption identification.

        Paper Section 3.3.1: 'iteratively identifies testable intermediate
        assumptions, which, if proven true, can lead to novel scientific
        discovery. These plausible assumptions and their sub-assumptions are
        identified through conditional reasoning hops and subsequently
        aggregated into complete hypotheses.'
        """
        existing_block = ""
        if existing_titles:
            existing_block = "\nExisting hypotheses (propose something DIFFERENT):\n" + "\n".join(
                f"- {t}" for t in existing_titles[:15]
            )
            # Detect thematic monoculture
            if len(existing_titles) > 5:
                from collections import Counter as _Counter
                _themes = _Counter()
                for _t in existing_titles:
                    _tl = _t.lower()
                    if any(k in _tl for k in ['nif', 'nitrogen', 'diazotrop', 'ammonia']):
                        _themes['nitrogen fixation'] += 1
                    elif any(k in _tl for k in ['eps', 'capsul', 'exopoly']):
                        _themes['EPS/capsule'] += 1
                    elif any(k in _tl for k in ['redox', 'bdo', 'butanediol', 'nadh']):
                        _themes['redox/BDO'] += 1
                    elif any(k in _tl for k in ['buoyanc', 'gas vesicle', 'float']):
                        _themes['buoyancy'] += 1
                    elif any(k in _tl for k in ['biofilm', 'toggle', 'hyster']):
                        _themes['biofilm circuits'] += 1
                    else:
                        _themes['other'] += 1
                if _themes:
                    _dominant = _themes.most_common(1)[0]
                    if _dominant[1] / len(existing_titles) > 0.4:
                        existing_block += (
                            f"\nWARNING: {_dominant[1]}/{len(existing_titles)} existing hypotheses "
                            f"are about '{_dominant[0]}'. You MUST propose something in a "
                            f"DIFFERENT thematic area.\n"
                        )

        constraints_block = ""
        if research_goal.constraints:
            constraints_block = "\nConstraints:\n" + "\n".join(f"- {c}" for c in research_goal.constraints)

        # Step 1: Identify untested assumptions in the research field
        assumptions_prompt = f"""You are an expert scientist analyzing the research landscape for:
{research_goal.description}
{constraints_block}
{existing_block}

Identify 5 key scientific assumptions in this field that are:
- Widely assumed to be true but NOT rigorously tested experimentally
- Testable with current synthetic biology methods
- If proven true OR false, would open a novel line of research

For each assumption, provide:
1. The assumption itself (one sentence)
2. Current evidence level: STRONG / MODERATE / WEAK / NONE
3. A brief experiment that could test it
4. What new research direction opens if confirmed or refuted

Return as JSON array:
[
  {{"assumption": "...", "evidence": "WEAK", "test": "...", "opens": "..."}},
  ...
]"""

        assumptions_response = await self.llm_client.ainvoke(assumptions_prompt)

        # Step 2: Build a hypothesis from the most impactful assumption
        synthesis_prompt = f"""Based on the following analysis of untested assumptions in the field of:
{research_goal.description}
{constraints_block}

UNTESTED ASSUMPTIONS IDENTIFIED:
{assumptions_response}

Select the most impactful assumption (preferring those with WEAK or no evidence) and construct
a complete, testable hypothesis using conditional reasoning:

IF [assumption A] is true, THEN [intermediate conclusion B] follows,
WHICH ENABLES [experiment C] that tests [deeper question D].

Build this into a rigorous experimental proposal.
{existing_block}

Cite relevant published papers that support or test each assumption in the reasoning chain.
Include title, DOI, and relevance in the citations array.

IMPORTANT: All experimental protocol fields are REQUIRED. You must provide:
- materials: at least 3 key reagents, strains, or equipment items
- limitations: at least 2 known limitations or risks
- estimated_timeline: realistic duration estimate (e.g., "6-9 months")
- phased_milestones: 2-3 phases with go/no-go criteria
Do not leave any protocol field empty.

Design the experiment in 2-3 phases. Phase 1 must validate the single highest-risk component before integration. Do not propose a fully integrated system without intermediate validation steps.

Return ONLY valid JSON:
{{
    "title": "Brief hypothesis title",
    "statement": "Full hypothesis statement built from the reasoning chain",
    "rationale": "Why this assumption is worth testing and the reasoning chain",
    "mechanism": "Proposed mechanism connecting assumption to prediction",
    "experimental_protocol": {{
        "objective": "What the experiment aims to test",
        "methodology": "Experimental approach",
        "controls": ["Control 1", "Control 2"],
        "expected_outcomes": ["Outcome 1", "Outcome 2"],
        "success_criteria": "What constitutes success",
        "materials": ["Key reagent/strain 1"],
        "limitations": ["Known limitation 1"],
        "estimated_timeline": "Estimated duration",
        "phased_milestones": [
            {{"phase": "Phase 1: Validate highest-risk component", "go_no_go": "Criteria to proceed"}},
            {{"phase": "Phase 2: Integrate and test", "go_no_go": "Criteria for success"}}
        ]
    }},
    "citations": [{{"title": "Paper", "doi": "", "relevance": "Why relevant"}}]
}}"""

        synthesis = await self.llm_client.ainvoke(synthesis_prompt)
        data = parse_llm_json(synthesis, agent_name="GenerationAgent-Assumptions")

        protocol_data = data.get("experimental_protocol", {})
        for k in ("controls", "expected_outcomes", "materials", "limitations"):
            if isinstance(protocol_data.get(k), str):
                protocol_data[k] = [protocol_data[k]]
        for k in ("objective", "methodology", "success_criteria", "estimated_timeline"):
            if isinstance(protocol_data.get(k), list):
                protocol_data[k] = "\n".join(str(x) for x in protocol_data[k])
        protocol_data.setdefault("objective", "")
        protocol_data.setdefault("methodology", "")
        protocol_data.setdefault("controls", [])
        protocol_data.setdefault("expected_outcomes", [])
        protocol_data.setdefault("success_criteria", "")

        hypothesis = Hypothesis(
            id=generate_hypothesis_id(),
            research_goal_id=research_goal.id,
            title=data.get("title", "Untitled"),
            summary=data.get("statement", "")[:200],
            hypothesis_statement=data.get("statement", ""),
            rationale=data.get("rationale", ""),
            mechanism=data.get("mechanism", ""),
            experimental_protocol=ExperimentalProtocol(**protocol_data),
            literature_citations=[
                Citation(**c) for c in data.get("citations", [])
                if isinstance(c, dict) and c.get("title")
            ],
            generation_method=GenerationMethod.ITERATIVE_ASSUMPTIONS,
            elo_rating=1200.0
        )

        self.logger.info(
            "Assumptions hypothesis generated",
            hypothesis_id=hypothesis.id,
            title=hypothesis.title,
        )
        return hypothesis

    async def _generate_via_expansion(
        self,
        research_goal: ResearchGoal,
        research_overview: Optional[object] = None,
        meta_review: Optional[object] = None,
        existing_titles: Optional[list] = None,
    ) -> Optional[Hypothesis]:
        """Generate a hypothesis via research expansion.

        Paper Section 3.3.1: 'reviews existing hypotheses and the research
        overview and feedback provided by the Meta-review agent... to inform
        additional exploration directions in the research hypothesis space.'

        Returns None if no research overview is available yet (early iterations).
        """
        if research_overview is None:
            self.logger.warning("research_expansion_fallback", reason="no_research_overview")
            return None

        from src.utils.json_parser import parse_llm_json

        # Build compact views of the overview, meta-review, and existing work
        directions_block = ""
        if hasattr(research_overview, 'research_directions'):
            dir_lines = []
            for d in (research_overview.research_directions or [])[:10]:
                direction = getattr(d, 'direction', None) or getattr(d, 'title', None) or str(d)
                justification = getattr(d, 'justification', '')
                dir_lines.append(f"- {direction}: {justification[:200]}")
            directions_block = "\n".join(dir_lines) if dir_lines else "No directions listed"

        meta_block = ""
        if meta_review is not None:
            opps = getattr(meta_review, 'improvement_opportunities', []) or []
            if opps:
                meta_block = "Improvement opportunities from meta-review:\n" + \
                    "\n".join(f"- {o}" for o in opps[:5])

        titles_block = ""
        if existing_titles:
            titles_block = "Existing hypothesis titles (avoid repeating these directions):\n" + \
                "\n".join(f"- {t}" for t in existing_titles[:25])

        prompt = f"""You are generating a NEW hypothesis for a research goal via RESEARCH EXPANSION.

Research Goal: {research_goal.description}

Preferences: {', '.join(research_goal.preferences) if research_goal.preferences else 'Standard scientific rigor'}

Research Overview Directions:
{directions_block}

{meta_block}

{titles_block}

YOUR TASK:
1. Identify ONE research direction from the overview that is LEAST explored by the existing
   hypotheses above, or is only mentioned in the meta-review improvement opportunities.
2. Generate a NOVEL hypothesis in that under-explored direction.
3. The hypothesis MUST directly address the research goal and MUST NOT duplicate any
   existing hypothesis titled above.

Return ONLY valid JSON:
{{
    "title": "Brief hypothesis title",
    "statement": "Full hypothesis statement",
    "rationale": "Why this direction is under-explored and worth pursuing",
    "mechanism": "Proposed mechanism",
    "experimental_protocol": {{
        "objective": "What the experiment tests",
        "methodology": "Experimental approach",
        "controls": ["Control 1"],
        "expected_outcomes": ["Outcome 1"],
        "success_criteria": "What constitutes success"
    }},
    "citations": [{{"title": "Paper", "doi": "", "relevance": "Why relevant"}}],
    "chosen_direction": "Which direction from the overview this explores"
}}"""

        response = await self.llm_client.ainvoke(prompt)
        data = parse_llm_json(response, agent_name="GenerationAgent-Expansion")

        # Resilient protocol parsing (mirror the debate path)
        protocol_data = data.get("experimental_protocol", {})
        def _coerce(v, as_list):
            if as_list and isinstance(v, str):
                return [v]
            if not as_list and isinstance(v, list):
                return "\n".join(str(x) for x in v)
            return v

        hypothesis = Hypothesis(
            id=generate_hypothesis_id(),
            research_goal_id=research_goal.id,
            title=data.get("title", "Expansion-generated hypothesis"),
            summary=data.get("title", ""),
            hypothesis_statement=data.get("statement", ""),
            rationale=data.get("rationale", ""),
            mechanism=data.get("mechanism"),
            experimental_protocol=ExperimentalProtocol(
                objective=_coerce(protocol_data.get("objective", ""), as_list=False),
                methodology=_coerce(protocol_data.get("methodology", ""), as_list=False),
                controls=_coerce(protocol_data.get("controls", []), as_list=True),
                expected_outcomes=_coerce(protocol_data.get("expected_outcomes", []), as_list=True),
                success_criteria=_coerce(protocol_data.get("success_criteria", ""), as_list=False),
                materials=_coerce(protocol_data.get("materials", []), as_list=True),
                limitations=_coerce(protocol_data.get("limitations", []), as_list=True),
                estimated_timeline=protocol_data.get("estimated_timeline"),
                phased_milestones=protocol_data.get("phased_milestones", []) or [],
            ),
            literature_citations=[
                Citation(**c) for c in data.get("citations", [])
                if isinstance(c, dict) and c.get("title")
            ],
            generation_method=GenerationMethod.RESEARCH_EXPANSION,
            elo_rating=1200.0
        )

        self.logger.info(
            "research_expansion_complete",
            hypothesis_id=hypothesis.id,
            title=hypothesis.title,
            chosen_direction=data.get("chosen_direction", "")[:100],
        )
        return hypothesis

    @trace_agent("GenerationAgent")
    async def execute(
        self,
        research_goal: ResearchGoal,
        method: GenerationMethod = GenerationMethod.LITERATURE_EXPLORATION,
        use_literature_expansion: bool = True,
        context_instructions: str = "",
        research_overview: Optional[object] = None,
        meta_review: Optional[object] = None,
        existing_titles: Optional[list] = None,
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

        # Route to iterative assumptions pathway if requested
        if method == GenerationMethod.ITERATIVE_ASSUMPTIONS:
            hypothesis = await self._generate_via_iterative_assumptions(
                research_goal=research_goal,
                existing_titles=existing_titles,
            )
            if hypothesis is not None:
                if use_literature_expansion:
                    hypothesis = await self._validate_citations(hypothesis, citation_graph)
                return hypothesis
            self.logger.info("assumptions_fallback_to_literature")

        # Route to debate pathway if requested
        if method == GenerationMethod.SIMULATED_DEBATE:
            hypothesis = await self._generate_via_debate(
                research_goal=research_goal,
                literature_context=literature_context,
                existing_titles=existing_titles,
            )
            if use_literature_expansion:
                hypothesis = await self._validate_citations(hypothesis, citation_graph)
            return hypothesis

        # Route to research expansion pathway if requested
        if method == GenerationMethod.RESEARCH_EXPANSION:
            hypothesis = await self._generate_via_expansion(
                research_goal=research_goal,
                research_overview=research_overview,
                meta_review=meta_review,
                existing_titles=existing_titles,
            )
            if hypothesis is not None:
                if use_literature_expansion:
                    hypothesis = await self._validate_citations(hypothesis, citation_graph)
                return hypothesis
            # Fall through to literature exploration if expansion unavailable
            self.logger.info("falling_back_to_literature_exploration")

        # Literature exploration pathway
        method_str = "literature"
        prompt = prompt_manager.format_generation_prompt(
            goal=research_goal.description,
            preferences=research_goal.preferences,
            constraints=research_goal.constraints,
            method=method_str,
            articles_with_reasoning=literature_context,
            instructions=context_instructions
        )

        # Add structured output instruction
        # Add existing titles for deduplication with theme saturation warning
        existing_block = ""
        if existing_titles:
            titles_list = "\n".join(f"- {t}" for t in existing_titles[:20])
            existing_block = f"\nEXISTING HYPOTHESES in this goal (do NOT duplicate; propose something distinct):\n{titles_list}\n"

            # Detect thematic monoculture and force diversification
            if len(existing_titles) > 5:
                from collections import Counter as _Counter
                _themes = _Counter()
                for _t in existing_titles:
                    _tl = _t.lower()
                    if any(k in _tl for k in ['nif', 'nitrogen', 'diazotrop', 'ammonia']):
                        _themes['nitrogen fixation'] += 1
                    elif any(k in _tl for k in ['eps', 'capsul', 'exopoly']):
                        _themes['EPS/capsule'] += 1
                    elif any(k in _tl for k in ['redox', 'bdo', 'butanediol', 'nadh']):
                        _themes['redox/BDO'] += 1
                    elif any(k in _tl for k in ['buoyanc', 'gas vesicle', 'float']):
                        _themes['buoyancy'] += 1
                    elif any(k in _tl for k in ['biofilm', 'toggle', 'hyster']):
                        _themes['biofilm circuits'] += 1
                    else:
                        _themes['other'] += 1
                if _themes:
                    _dominant = _themes.most_common(1)[0]
                    if _dominant[1] / len(existing_titles) > 0.4:
                        existing_block += (
                            f"\nWARNING: {_dominant[1]}/{len(existing_titles)} existing hypotheses "
                            f"are about '{_dominant[0]}'. You MUST propose something in a "
                            f"DIFFERENT thematic area to ensure diversity.\n"
                        )

        structured_prompt = f"""{prompt}
{existing_block}
When formulating your hypothesis, cite the most relevant papers from the literature context above. Include their title, DOI, and relevance in the citations array.

Design the experiment in 2-3 phases with explicit go/no-go criteria. Phase 1 must validate the single highest-risk component before integration. Do not propose a fully integrated system without intermediate validation steps.

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
        "success_criteria": "What constitutes success",
        "materials": ["Key reagent/strain 1", "Key equipment 1"],
        "limitations": ["Known limitation 1"],
        "estimated_timeline": "Estimated duration (e.g., 6-9 months)",
        "phased_milestones": [
            {{"phase": "Phase 1: Validate highest-risk component", "go_no_go": "Criteria to proceed"}},
            {{"phase": "Phase 2: Integrate and test", "go_no_go": "Criteria for success"}}
        ]
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
                experimental_protocol=ExperimentalProtocol(
                    **{
                        **{"objective": "", "methodology": "", "controls": [],
                           "expected_outcomes": [], "success_criteria": ""},
                        **{
                            k: (
                                # List fields: wrap string as list
                                [v] if isinstance(v, str) and k in ("controls", "expected_outcomes")
                                # String fields: join list as string
                                else "\n".join(str(x) for x in v) if isinstance(v, list) and k in ("objective", "methodology", "success_criteria")
                                else v
                            )
                            for k, v in data.get("experimental_protocol", {}).items()
                        }
                    }
                ),
                literature_citations=[
                    Citation(**c) for c in data.get("citations", [])
                    if isinstance(c, dict) and c.get("title")
                ],
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
