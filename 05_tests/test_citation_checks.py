"""Evolved hypotheses cite only validated papers, and retractions are detected.

Evolution may cite only papers the source hypotheses already cite: the model
sees that list, anything else it names is dropped, and a malformed entry never
fails the parse. check_retractions asks PubMed for the publication type a
retracted article carries, by PMID or by bare DOI, in one query. Checked
against live E-utilities on 2026-10-28: '"<doi>"[doi] AND "retracted
publication"[pt]' finds the retracted PMID 9500320 (Wakefield 1998) and not
22745249 (Jinek 2012); 'retracted[pt] OR retraction[pt]' matches nothing; a
doi.org URL in place of the bare DOI matches nothing. A fake PubMed answering
the same way stands in for the network; RUN_LIVE_PUBMED=1 runs the real one.
Stdlib unittest, run by buildspec.yml inside the built image like the other
tests.
"""
import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "03_architecture"))
sys.path.insert(0, str(ROOT / "04_Scripts"))
# Settings requires a Google key at import time; these tests never call Google.
os.environ.setdefault("GOOGLE_API_KEY", "unit-test-placeholder")

from schemas import (  # noqa: E402
    Citation, EvolutionStrategy, ExperimentalProtocol, GenerationMethod, Hypothesis,
)
from src.agents import evolution as evolution_module  # noqa: E402
from src.agents.reflection import ReflectionAgent  # noqa: E402
from src.tools import pubmed as pubmed_module  # noqa: E402
from src.tools.base import ToolResult  # noqa: E402
from src.tools.refutation_search import RefutationSearchTool  # noqa: E402

RETRACTED_DOI = "10.1016/S0140-6736(97)11096-0"  # Wakefield 1998, PMID 9500320
INTACT_DOI = "10.1126/science.1225829"  # Jinek 2012, PMID 22745249
SOURCE_CITATIONS = [
    Citation(title="Paper A", doi="10.1000/a", relevance="supports the parent"),
    Citation(title="Paper B", doi="10.1000/b", relevance="supports the parent"),
]


def _hypothesis(citations=()):
    return Hypothesis(
        id="hyp_parent", research_goal_id="goal_citations", title="Parent hypothesis",
        summary="s", hypothesis_statement="h", rationale="r",
        experimental_protocol=ExperimentalProtocol(objective="o", methodology="m",
                                                   success_criteria="c"),
        literature_citations=list(citations),
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
    )


class _ScriptedLLM:
    """Answers the evolution prompt with the given citations."""

    def __init__(self, citations):
        self.citations = citations
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return json.dumps({
            "title": "Evolved hypothesis", "summary": "s", "statement": "h",
            "rationale": "r", "mechanism": "m",
            "experimental_protocol": {"methodology": "m", "controls": "c",
                                      "success_criteria": "c"},
            "citations": self.citations,
            "evolution_rationale": "e",
        })


def _evolve(source_citations, answered_citations):
    llm = _ScriptedLLM(answered_citations)
    with mock.patch.object(evolution_module, "get_llm_client", return_value=llm):
        agent = evolution_module.EvolutionAgent()
    evolved = agent.execute(_hypothesis(source_citations), EvolutionStrategy.GROUNDING)
    return evolved, llm.prompts[-1]


class EvolutionCitationTest(unittest.TestCase):
    def test_cited_source_paper_is_kept_with_its_new_relevance(self):
        evolved, prompt = _evolve(SOURCE_CITATIONS, [
            {"title": "Paper A", "doi": "10.1000/a", "relevance": "supports the evolved one"}])
        self.assertIn('"doi": "10.1000/b"', prompt)  # the model sees what it may cite
        self.assertEqual([(c.title, c.relevance) for c in evolved.literature_citations],
                         [("Paper A", "supports the evolved one")])

    def test_recalled_and_malformed_citations_are_dropped_without_failing(self):
        evolved, _ = _evolve(SOURCE_CITATIONS, [
            {"title": "Invented", "doi": "10.9999/invented", "relevance": "r"},
            {"title": "Paper B", "relevance": None, "authors": "One string",
             "year": "2012 (online)"},
            "not a citation",
        ])
        self.assertEqual([(c.title, c.relevance) for c in evolved.literature_citations],
                         [("Paper B", "supports the parent")])

    def test_without_source_citations_nothing_is_cited(self):
        evolved, prompt = _evolve([], [{"title": "Paper A", "doi": "10.1000/a",
                                        "relevance": "r"}])
        self.assertIn('return "citations": []', prompt)
        self.assertEqual(evolved.literature_citations, [])


class _FakePubMed:
    """Answers like PubMed: only Wakefield 1998, asked for by PMID or bare DOI
    together with "retracted publication"[pt], is a hit."""

    HITS = {'9500320[PMID] AND "retracted publication"[pt]',
            f'"{RETRACTED_DOI}"[doi] AND "retracted publication"[pt]'}

    def __init__(self, fail=False):
        self.fail = fail
        self.queries = []

    async def execute(self, query, **kwargs):
        self.queries.append(query)
        if self.fail:
            return ToolResult.error_result(error="429 Too Many Requests")
        return ToolResult.success_result(data=[{"title": "Retracted"}] if query in self.HITS
                                         else [])


def _check(paper, pubmed=None):
    pubmed = pubmed or _FakePubMed()
    status = asyncio.run(RefutationSearchTool(pubmed_tool=pubmed).check_retractions(paper))
    return status, getattr(pubmed, "queries", [])


class RetractionCheckTest(unittest.TestCase):
    def test_doi_only_paper_is_flagged_in_one_query(self):
        status, queries = _check({"title": "t", "doi": RETRACTED_DOI, "pmid": None})
        self.assertTrue(status["is_retracted"])
        self.assertEqual(len(queries), 1)

    def test_doi_org_url_is_reduced_to_the_bare_doi(self):
        status, _ = _check({"title": "t", "doi": f"https://doi.org/{RETRACTED_DOI}"})
        self.assertTrue(status["is_retracted"])

    def test_intact_paper_is_not_flagged(self):
        status, _ = _check({"title": "t", "doi": INTACT_DOI})
        self.assertFalse(status["is_retracted"])

    def test_paper_with_pmid_is_checked_by_pmid(self):
        status, queries = _check({"title": "t", "pmid": "9500320", "doi": INTACT_DOI})
        self.assertTrue(status["is_retracted"])
        self.assertTrue(queries[0].startswith("9500320[PMID]"))

    def test_pubmed_error_does_not_break_the_check(self):
        status, _ = _check({"title": "t", "doi": RETRACTED_DOI}, _FakePubMed(fail=True))
        self.assertFalse(status["is_retracted"])

    def test_reflection_warns_about_a_retracted_supporting_citation(self):
        agent = ReflectionAgent.__new__(ReflectionAgent)  # needs no LLM or tool registry
        agent.logger = mock.Mock()
        agent.refutation_tool = RefutationSearchTool(pubmed_tool=_FakePubMed())
        hypothesis = _hypothesis([Citation(title="Wakefield 1998", doi=RETRACTED_DOI,
                                           relevance="r")])
        retractions = asyncio.run(agent._check_citation_retractions(hypothesis))
        self.assertTrue(retractions["Wakefield 1998"]["is_retracted"])
        self.assertIn("supporting citation(s) have been RETRACTED",
                      agent._format_refutation_context([], {}, retractions))

    def test_retracted_contradicting_paper_is_not_called_a_supporting_citation(self):
        context = RefutationSearchTool().format_contradictions_for_context(
            [{"title": "X"}], {"X": {"is_retracted": True}})
        self.assertIn("contradicting paper(s) have been RETRACTED", context)
        self.assertNotIn("supporting citation", context)


class PubMedRateLimitTest(unittest.TestCase):
    def test_concurrent_callers_are_spaced_by_the_interval(self):
        tool = pubmed_module.PubMedTool(api_key="unit-test")  # 10 requests/s
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(round(seconds, 3))

        async def four_callers():
            await asyncio.gather(*(tool._rate_limit() for _ in range(4)))

        with mock.patch.object(pubmed_module.time, "time", return_value=1000.0), \
                mock.patch.object(pubmed_module.asyncio, "sleep", fake_sleep):
            asyncio.run(four_callers())
        self.assertEqual(sleeps, [0.1, 0.2, 0.3])


@unittest.skipUnless(os.environ.get("RUN_LIVE_PUBMED") == "1", "set RUN_LIVE_PUBMED=1")
class LivePubMedTest(unittest.TestCase):
    def test_real_pubmed_flags_wakefield_and_not_jinek(self):
        tool = pubmed_module.PubMedTool()
        self.assertTrue(_check({"doi": RETRACTED_DOI}, tool)[0]["is_retracted"])
        self.assertFalse(_check({"doi": INTACT_DOI}, tool)[0]["is_retracted"])


if __name__ == "__main__":
    unittest.main()
