"""Reflection Agent - Review and score hypotheses"""

from typing import Dict, Any, List, Tuple, Optional
from pydantic import ValidationError as PydanticValidationError
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import Hypothesis, Review, ReviewType

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.prompts.loader import prompt_manager
from src.utils.ids import generate_review_id
from src.utils.errors import CoScientistError
from src.config import settings
from src.observability.tracing import trace_agent
# Phase 6: Refutation search imports
from src.tools.refutation_search import RefutationSearchTool
from src.literature.limitations_extractor import LimitationsExtractor
from src.tools.registry import initialize_tools
import json


class ReflectionAgent(BaseAgent):
    """Review hypotheses and provide detailed assessments"""

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.reflection_model,
            agent_name="reflection"
        )
        super().__init__(llm_client, "ReflectionAgent")

        # Phase 6: Initialize refutation search tools
        self.tool_registry = initialize_tools()

        # Get PubMed and Semantic Scholar tools for refutation search
        pubmed_tool = self.tool_registry.get("pubmed")
        semantic_tool = self.tool_registry.get("semantic_scholar")

        self.refutation_tool = RefutationSearchTool(
            pubmed_tool=pubmed_tool,
            semantic_scholar_tool=semantic_tool,
            max_results=settings.refutation_max_results,
            min_quality_score=settings.refutation_min_quality_score
        )

        self.limitations_extractor = LimitationsExtractor(
            min_confidence=settings.limitations_min_confidence
        )

    async def _search_for_refutation(
        self,
        hypothesis: Hypothesis
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        Search for evidence that contradicts the hypothesis.

        Phase 6 integration: Uses RefutationSearchTool to find papers
        with opposing conclusions, failed replications, or retractions.

        Args:
            hypothesis: Hypothesis object to find refutations for

        Returns:
            Tuple of (contradictions list, retraction_status dict)
        """
        if not settings.enable_refutation_search:
            return [], {}

        # Extract core claim from hypothesis statement (first 200 chars)
        core_claim = hypothesis.hypothesis_statement[:200]

        # Search for contradictions
        try:
            contradictions = await self.refutation_tool.search_contradictions(
                hypothesis_statement=hypothesis.hypothesis_statement,
                core_claim=core_claim
            )
        except Exception as e:
            self.logger.warning(
                "Refutation search failed",
                hypothesis_id=hypothesis.id,
                error=str(e)
            )
            contradictions = []

        # Check retractions for each contradiction found
        retraction_status = {}
        if settings.refutation_check_retractions:
            for paper in contradictions:
                if paper.get('pmid'):
                    try:
                        status = await self.refutation_tool.check_retractions(paper)
                        retraction_status[paper.get('title', 'Unknown')] = status
                    except Exception as e:
                        self.logger.warning(
                            "Retraction check failed",
                            paper_title=paper.get('title'),
                            error=str(e)
                        )

        self.logger.info(
            "Refutation search complete",
            hypothesis_id=hypothesis.id,
            contradictions_found=len(contradictions),
            retractions_checked=len(retraction_status)
        )

        return contradictions, retraction_status

    async def _check_citation_retractions(
        self,
        hypothesis: Hypothesis
    ) -> Dict[str, Dict[str, Any]]:
        """
        Check if any supporting citations have been retracted.

        Phase 6 integration: Validates that supporting evidence has not
        been retracted or corrected.

        Args:
            hypothesis: Hypothesis with literature_citations

        Returns:
            Dict mapping citation title to retraction status
        """
        if not settings.refutation_check_retractions:
            return {}

        if not hypothesis.literature_citations:
            return {}

        retraction_status = {}

        for citation in hypothesis.literature_citations:
            # Build paper dict for retraction check
            paper_dict = {
                'title': citation.title,
                'doi': citation.doi,
                'pmid': None  # Would need DOI->PMID lookup for full check
            }

            # Only check if we have some identifier
            if citation.doi:
                try:
                    status = await self.refutation_tool.check_retractions(paper_dict)
                    retraction_status[citation.title] = status
                except Exception as e:
                    self.logger.warning(
                        "Retraction check failed for citation",
                        citation=citation.title,
                        error=str(e)
                    )

        if retraction_status:
            retracted_count = sum(
                1 for s in retraction_status.values()
                if s.get('is_retracted')
            )
            if retracted_count > 0:
                self.logger.warning(
                    "Retracted supporting citations found",
                    hypothesis_id=hypothesis.id,
                    retracted_count=retracted_count
                )

        return retraction_status

    def _format_refutation_context(
        self,
        contradictions: List[Dict[str, Any]],
        retraction_status: Dict[str, Dict[str, Any]],
        citation_retractions: Dict[str, Dict[str, Any]]
    ) -> str:
        """
        Format all refutation evidence for LLM review context.

        Phase 6 integration: Provides counter-evidence to the LLM reviewer
        so it can make a more informed assessment.

        Args:
            contradictions: Found contradictory papers
            retraction_status: Retraction info for contradictions
            citation_retractions: Retraction info for hypothesis citations

        Returns:
            Formatted warning string for LLM prompt
        """
        parts = []

        # Format contradictions using refutation tool
        contradiction_context = self.refutation_tool.format_contradictions_for_context(
            contradictions,
            retraction_status
        )
        if contradiction_context:
            parts.append(contradiction_context)

        # Add warnings for retracted supporting citations
        retracted_citations = [
            title for title, status in citation_retractions.items()
            if status.get('is_retracted')
        ]

        if retracted_citations:
            parts.append(
                f"\nWARNING: {len(retracted_citations)} supporting citation(s) have been RETRACTED:\n" +
                "\n".join(f"  - {title}" for title in retracted_citations)
            )

        # Add warnings for corrected citations
        corrected_citations = [
            title for title, status in citation_retractions.items()
            if status.get('has_correction') and not status.get('is_retracted')
        ]

        if corrected_citations:
            parts.append(
                f"\nNOTE: {len(corrected_citations)} supporting citation(s) have corrections/errata:\n" +
                "\n".join(f"  - {title}" for title in corrected_citations)
            )

        return "\n\n".join(parts) if parts else ""

    async def _deep_verification_review(
        self,
        hypothesis: Hypothesis,
    ) -> "DeepVerificationReview":
        """Decompose hypothesis into assumptions and independently verify each.

        Paper Section 3.3.2: "decomposes the hypothesis into constituent
        assumptions, each broken into fundamental sub-assumptions,
        decontextualized, and independently evaluated for correctness."

        Args:
            hypothesis: Hypothesis to deeply verify.

        Returns:
            DeepVerificationReview with verified/invalidated assumptions.
        """
        from schemas import Assumption, DeepVerificationReview

        prompt = f"""You are performing a Deep Verification Review of a scientific hypothesis.

HYPOTHESIS: {hypothesis.title}
STATEMENT: {hypothesis.hypothesis_statement}
RATIONALE: {hypothesis.rationale}
MECHANISM: {hypothesis.mechanism or 'Not specified'}

Perform the following analysis:
1. Decompose this hypothesis into 3-7 CORE ASSUMPTIONS that must hold true.
2. For each core assumption, identify 2-4 TESTABLE SUB-ASSUMPTIONS.
   Decontextualize each sub-assumption so it can be evaluated independently.
3. Evaluate each sub-assumption: is it valid, invalid, or uncertain?
   Provide a confidence score (0.0-1.0) and supporting evidence.
4. For each assumption, classify whether it is FUNDAMENTAL (core hypothesis
   collapses if wrong) or NON-FUNDAMENTAL (can be refined without invalidating
   the core idea).

Return ONLY valid JSON:
{{
  "assumptions": [
    {{
      "statement": "Core assumption text",
      "is_fundamental": true,
      "sub_assumptions": [
        {{
          "statement": "Testable sub-assumption",
          "verification_status": "valid|invalid|uncertain",
          "confidence": 0.85,
          "evidence": ["reason 1", "reason 2"]
        }}
      ]
    }}
  ],
  "overall_valid": true,
  "quality_score": 0.8,
  "strengths": ["strength 1"],
  "weaknesses": ["weakness 1"],
  "invalidation_reasons": ["reason if any assumptions are fundamentally invalid"]
}}"""

        response = await self.llm_client.ainvoke(prompt)

        # Parse response
        from src.utils.json_parser import parse_llm_json
        data = parse_llm_json(response, agent_name="ReflectionAgent-DeepVerification")

        # Build Assumption objects
        verified = []
        invalidated = []
        invalidation_reasons = data.get("invalidation_reasons", [])

        for a_data in data.get("assumptions", []):
            sub_assumptions = []
            has_fundamental_failure = False

            for sa_data in a_data.get("sub_assumptions", []):
                sa = Assumption(
                    id=generate_id("sa"),
                    statement=sa_data["statement"],
                    verification_status=sa_data.get("verification_status", "uncertain"),
                    evidence=sa_data.get("evidence", []),
                    is_fundamental=a_data.get("is_fundamental", True),
                )
                sub_assumptions.append(sa)
                if sa.verification_status == "invalid" and a_data.get("is_fundamental", True):
                    has_fundamental_failure = True

            assumption = Assumption(
                id=generate_id("asmp"),
                statement=a_data["statement"],
                is_fundamental=a_data.get("is_fundamental", True),
                sub_assumptions=sub_assumptions,
                verification_status="invalid" if has_fundamental_failure else "valid",
            )

            if has_fundamental_failure:
                invalidated.append(assumption)
            else:
                verified.append(assumption)

        # Hypothesis passes if no fundamental assumptions are invalidated
        passed = len(invalidated) == 0
        quality_score = data.get("quality_score", 0.7 if passed else 0.3)

        review = DeepVerificationReview(
            id=generate_id("rev"),
            hypothesis_id=hypothesis.id,
            review_type=ReviewType.DEEP_VERIFICATION,
            correctness_score=quality_score,
            quality_score=quality_score,
            novelty_score=None,
            testability_score=None,
            safety_score=None,
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            suggestions=[],
            failure_modes=[],
            passed=passed,
            rationale=f"Deep verification: {len(verified)} verified, {len(invalidated)} invalidated assumptions",
            verified_assumptions=verified,
            invalidated_assumptions=invalidated,
            invalidation_reasons=invalidation_reasons,
        )

        self.logger.info(
            "Deep verification complete",
            hypothesis_id=hypothesis.id,
            passed=passed,
            verified=len(verified),
            invalidated=len(invalidated),
        )

        return review

    @trace_agent("ReflectionAgent")
    async def execute(
        self,
        hypothesis: Hypothesis,
        review_type: ReviewType = ReviewType.INITIAL,
        article: str = "",
        use_refutation_search: bool = True,
        context_guidance: str = "",
        research_goal: object = None,
    ) -> Review:
        """Review a hypothesis

        Phase 6 enhancement: Now performs refutation search to find
        contradictory evidence before review.

        Args:
            hypothesis: The hypothesis to review
            review_type: Type of review to perform
            article: Optional article text for observation review
            use_refutation_search: Whether to search for contradictory evidence

        Returns:
            Review object with scores and feedback
        """

        self.log_execution(
            task="hypothesis_review",
            hypothesis_id=hypothesis.id,
            review_type=review_type.value,
            refutation_search=use_refutation_search
        )

        # Phase 6: Search for refutation evidence
        refutation_context = ""
        if use_refutation_search and settings.enable_refutation_search:
            try:
                # Search for contradictory evidence
                contradictions, retraction_status = await self._search_for_refutation(
                    hypothesis
                )

                # Check if supporting citations have been retracted
                citation_retractions = await self._check_citation_retractions(
                    hypothesis
                )

                # Format all refutation evidence
                refutation_context = self._format_refutation_context(
                    contradictions,
                    retraction_status,
                    citation_retractions
                )

            except Exception as e:
                self.logger.warning(
                    "Refutation search failed, continuing without",
                    error=str(e)
                )

        # Deep verification has its own complete flow
        if review_type == ReviewType.DEEP_VERIFICATION:
            return await self._deep_verification_review(hypothesis)

        # Format prompt based on review type
        if review_type == ReviewType.OBSERVATION:
            prompt = prompt_manager.format_reflection_prompt(
                goal=hypothesis.hypothesis_statement,
                hypothesis=self._format_hypothesis(hypothesis),
                article=article
            )
        elif review_type == ReviewType.FULL:
            # Paper Section 3.3.2: Full review leverages literature search
            # and applies a stricter scoring rubric than initial review.
            prompt = self._create_full_review_prompt(hypothesis)
        else:
            # For initial review, just evaluate the hypothesis directly
            prompt = self._create_initial_review_prompt(hypothesis)

        # Add refutation context if available
        if refutation_context:
            prompt = f"""{prompt}

COUNTER-EVIDENCE TO CONSIDER:
{refutation_context}

When scoring this hypothesis, carefully consider:
1. Any contradictory evidence found in the literature
2. Whether supporting citations have been retracted or corrected
3. The strength and recency of contradictory studies
"""

        # Add context memory guidance if available
        if context_guidance:
            prompt = f"""{prompt}

{context_guidance}
"""

        # Append constraints from research goal so reviewer checks compliance
        if research_goal and hasattr(research_goal, 'constraints') and research_goal.constraints:
            constraints_text = "\n".join(f"- {c}" for c in research_goal.constraints)
            prompt = f"""{prompt}

CONSTRAINTS (the hypothesis must satisfy these; flag violations):
{constraints_text}
"""

        # Add structured output instruction
        structured_prompt = f"""{prompt}

FEASIBILITY RUBRIC (be strict — module stacking is the #1 driver of grant-panel rejection):
Count unvalidated modules (pathway steps, regulators, protein chimeras, cofactors,
sensors) that have NOT been demonstrated to work in the host organism or a close relative.
- 0 unvalidated modules → feasibility_score 0.9-1.0
- 1-2 unvalidated modules with literature precedent → 0.6-0.8
- 3+ stacked unvalidated modules, OR missing cofactor / host capability / reagent → <0.3

IMPORTANT: Return your response as valid JSON matching this schema:
{{
    "passed": true/false,
    "rationale": "Detailed reasoning for decision",
    "correctness_score": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "novelty_score": 0.0-1.0,
    "testability_score": 0.0-1.0,
    "safety_score": 0.0-1.0,
    "feasibility_score": 0.0-1.0,
    "strengths": ["Strength 1", "Strength 2"],
    "weaknesses": ["Weakness 1", "Weakness 2"],
    "suggestions": ["Suggestion 1", "Suggestion 2"],
    "critiques": ["Critique 1", "Critique 2"],
    "known_aspects": ["Known aspect 1"],
    "novel_aspects": ["Novel aspect 1"],
    "explained_observations": ["Observation 1"]
}}

Respond with ONLY the JSON object, no additional text."""

        # Invoke LLM
        response = self.llm_client.invoke(structured_prompt)

        # Parse response
        try:
            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            data = json.loads(json_str)

            # Build Review object
            review = Review(
                id=generate_review_id(),
                hypothesis_id=hypothesis.id,
                review_type=review_type,
                passed=data.get("passed", True),
                rationale=data.get("rationale", "No rationale provided"),
                correctness_score=data.get("correctness_score"),
                quality_score=data.get("quality_score"),
                novelty_score=data.get("novelty_score"),
                testability_score=data.get("testability_score"),
                safety_score=data.get("safety_score"),
                feasibility_score=data.get("feasibility_score"),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                suggestions=data.get("suggestions", []),
                critiques=data.get("critiques", []),
                known_aspects=data.get("known_aspects", []),
                novel_aspects=data.get("novel_aspects", []),
                explained_observations=data.get("explained_observations", [])
            )

            self.logger.info(
                "Review completed",
                review_id=review.id,
                hypothesis_id=hypothesis.id,
                passed=review.passed,
                quality_score=review.quality_score,
                refutation_search_used=bool(refutation_context)
            )

            return review

        except (json.JSONDecodeError, PydanticValidationError, KeyError) as e:
            raise CoScientistError(f"Failed to parse LLM response: {e}\nResponse: {response[:500]}")

    def _format_hypothesis(self, hypothesis: Hypothesis) -> str:
        """Format hypothesis for prompt"""
        return f"""
Title: {hypothesis.title}
Statement: {hypothesis.hypothesis_statement}
Rationale: {hypothesis.rationale}
Mechanism: {hypothesis.mechanism or 'Not specified'}
        """.strip()

    def _create_initial_review_prompt(self, hypothesis: Hypothesis) -> str:
        """Create prompt for initial review without external tools"""
        return f"""You are an expert scientific reviewer. Please evaluate the following hypothesis:

{self._format_hypothesis(hypothesis)}

Experimental Protocol:
- Objective: {hypothesis.experimental_protocol.objective if hypothesis.experimental_protocol else 'Not specified'}
- Methodology: {hypothesis.experimental_protocol.methodology if hypothesis.experimental_protocol else 'Not specified'}

Assess the hypothesis on the following criteria:
1. **Correctness**: Is it scientifically sound?
2. **Quality**: Is it well-formulated and clear?
3. **Novelty**: Does it offer new insights?
4. **Testability**: Can it be experimentally tested?
5. **Safety**: Are there ethical or safety concerns?

For each criterion, provide:
- A score from 0.0 (poor) to 1.0 (excellent)
- Specific strengths and weaknesses
- Constructive suggestions for improvement

Determine if the hypothesis PASSES this initial review (true/false) and provide detailed rationale.
"""

    def _create_full_review_prompt(self, hypothesis: Hypothesis) -> str:
        """Create prompt for FULL review - stricter than initial, uses citations.

        Paper Section 3.3.2: Full review 'leverages external tools and web
        searches to identify relevant articles for improved reasoning and
        grounding' and scrutinizes 'underlying assumptions and reasoning'.
        """
        citations_block = "No citations provided."
        if hypothesis.literature_citations:
            citation_lines = []
            for i, c in enumerate(hypothesis.literature_citations, 1):
                citation_lines.append(
                    f"{i}. {c.title}"
                    f" (DOI: {c.doi or 'N/A'})"
                    f" - Claimed relevance: {c.relevance}"
                )
            citations_block = "\n".join(citation_lines)

        return f"""You are an expert scientific reviewer performing a FULL REVIEW of a hypothesis.
This is a STRICTER review than an initial screening. Apply rigorous scrutiny.

{self._format_hypothesis(hypothesis)}

Experimental Protocol:
- Objective: {hypothesis.experimental_protocol.objective if hypothesis.experimental_protocol else 'Not specified'}
- Methodology: {hypothesis.experimental_protocol.methodology if hypothesis.experimental_protocol else 'Not specified'}

Supporting Literature Cited:
{citations_block}

YOUR FULL REVIEW TASKS:
1. **Verify citations support the claim**: For each cited paper, critically assess whether
   it actually supports the hypothesis statement, or whether the cited relevance is
   superficial, generic, or overclaimed. Flag any citation that is weak or tangential.

2. **Probe underlying assumptions**: Identify the 3-5 key assumptions the hypothesis rests on.
   For each, ask: does the cited literature actually establish this assumption? Is there
   contrary evidence you know of? Are any assumptions unstated?

3. **Scrutinize reasoning chains**: Walk through the hypothesis's logical chain from
   premise to prediction. Where are the weakest links? Are there alternative explanations
   that would also fit the same evidence?

4. **Literature grounding check**: Is the hypothesis novel relative to the cited papers,
   or is it largely restating what's already known? A hypothesis that merely repackages
   prior work should fail the novelty criterion.

5. **Experimental rigor check**: Is the proposed experiment able to distinguish the
   hypothesis from plausible alternatives? Are controls adequate? What could confound
   the predicted outcome?

Score each criterion strictly (be harsher than an initial review):
1. **Correctness**: Is it scientifically sound? (literature-grounded)
2. **Quality**: Well-formulated, with precise claims and falsifiable predictions?
3. **Novelty**: Genuinely new relative to the cited literature?
4. **Testability**: Experiment can truly distinguish the hypothesis from alternatives?
5. **Safety**: Ethical/safety concerns?
6. **Biochemical compatibility**: For every enzyme, genetic part, or binding domain proposed,
   check and flag any of the following as CRITICAL WEAKNESS:
   a. Cofactor specificity (e.g., NADH vs NADPH, ATP vs GTP) matches the stated role.
   b. Substrate specificity - the enzyme's real substrate is actually present in the host.
   c. Environmental compatibility - the enzyme functions under the stated conditions
      (aerobic vs anaerobic/microaerobic, pH, temperature).
   d. Host compatibility - the part has been demonstrated in this host or a close relative;
      flag cross-phylum porting (e.g., Gram-positive to Gram-negative).
   e. Binding-domain target - if a binding/anchor domain is used, its cognate ligand
      is actually present in the host's matrix/surface.

A hypothesis should PASS this FULL review only if it clearly meets all criteria under
rigorous scrutiny. Be strict. If citations are weak, assumptions unstated, reasoning
has gaps, or biochemical compatibility issues are found, fail it or flag for revision.

Provide detailed rationale for the pass/fail decision, concrete strengths, concrete
weaknesses (citing specific parts of the hypothesis or citations), and actionable
suggestions for improvement.
"""
