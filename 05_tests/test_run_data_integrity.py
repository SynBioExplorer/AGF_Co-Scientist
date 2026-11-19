"""What a run reads and writes survives intact.

PubMed records keep their whole title and every abstract section; literature
seeds reach Semantic Scholar in a form it resolves (live 2026-10-28: a bare
DOI resolves, a bare PMID is a 404, "PMID:<id>" resolves), and a publisher-
elided reference list does not break expansion; a call that crosses the budget
is still counted, since it has run and been billed, and the report makes no
call once the budget is spent; and model-written text can neither end nor
derail the report's inline script, nor inject into its HTML. Stdlib unittest,
run by buildspec.yml inside the built image like the other tests.
"""
import asyncio
import json
import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "03_architecture"))
sys.path.insert(0, str(ROOT / "04_Scripts"))
# Settings requires a Google key at import time; these tests never call Google.
os.environ.setdefault("GOOGLE_API_KEY", "unit-test-placeholder")

import cost_tracker  # noqa: E402
from schemas import (  # noqa: E402
    ExperimentalProtocol, GenerationMethod, Hypothesis, ResearchGoal,
)
from src.agents import generation as generation_module  # noqa: E402
from src.literature.citation_graph import CitationGraph  # noqa: E402
from src.tools import semantic_scholar as semantic_scholar_module  # noqa: E402
from src.tools.pubmed import PubMedTool  # noqa: E402
from src.utils import html_report  # noqa: E402

PUBMED_RECORD = """<PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
<ArticleTitle>Role of <i>Cas9</i> in DNA repair</ArticleTitle>
<Abstract>
<AbstractText Label="BACKGROUND">Cas9 cuts DNA.</AbstractText>
<AbstractText Label="RESULTS">Repair follows within 2 h<sup>-1</sup> of cutting.</AbstractText>
<AbstractText Label="CONCLUSIONS">It works.</AbstractText>
</Abstract>
</Article></MedlineCitation></PubmedArticle>"""


class PubMedParseTest(unittest.TestCase):
    def test_title_and_structured_abstract_are_kept_whole(self):
        article = PubMedTool()._parse_article(ET.fromstring(PUBMED_RECORD))
        self.assertEqual(article.title, "Role of Cas9 in DNA repair")
        self.assertEqual(article.abstract.splitlines(), [
            "BACKGROUND: Cas9 cuts DNA.",
            "RESULTS: Repair follows within 2 h-1 of cutting.",
            "CONCLUSIONS: It works.",
        ])


class _RecordingExpander:
    seeds = []

    def __init__(self, graph, tools):
        pass

    async def expand_from_paper(self, paper_id, **kwargs):
        _RecordingExpander.seeds.append(paper_id)


class ExpansionSeedTest(unittest.TestCase):
    def test_seeds_are_ids_semantic_scholar_resolves(self):
        agent = generation_module.GenerationAgent.__new__(generation_module.GenerationAgent)
        agent.tool_registry = {"semantic_scholar": object()}
        agent.logger = mock.Mock()
        agent.cache = None
        _RecordingExpander.seeds = []
        papers = [{"pmid": "22745249"},
                  {"doi": "10.1126/science.1225829", "pmid": "22745249"},
                  {"paper_id": "0b7d0a0f"}]  # a Semantic Scholar search result
        with mock.patch.object(generation_module, "CitationGraphExpander", _RecordingExpander):
            asyncio.run(agent._expand_citation_graph(papers, CitationGraph()))
        self.assertEqual(_RecordingExpander.seeds,
                         ["PMID:22745249", "10.1126/science.1225829", "0b7d0a0f"])


class SemanticScholarTest(unittest.TestCase):
    def test_elided_reference_list_reads_as_empty(self):
        tool = semantic_scholar_module.SemanticScholarTool()
        client = mock.AsyncMock()
        client.__aenter__.return_value = client
        client.get.return_value = mock.Mock(**{"json.return_value": {"data": None}})
        with mock.patch.object(semantic_scholar_module.httpx, "AsyncClient",
                               return_value=client), \
                mock.patch.object(tool, "_rate_limit", mock.AsyncMock()):
            self.assertEqual(asyncio.run(tool.get_references("DOI:10.1000/x")), [])

    def test_concurrent_callers_are_spaced_by_the_interval(self):
        tool = semantic_scholar_module.SemanticScholarTool()  # 1 request/s
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(round(seconds, 3))

        async def five_callers():
            await asyncio.gather(*(tool._rate_limit() for _ in range(5)))

        with mock.patch.object(semantic_scholar_module.time, "time", return_value=1000.0), \
                mock.patch.object(semantic_scholar_module.asyncio, "sleep", fake_sleep):
            asyncio.run(five_callers())
        self.assertEqual(sleeps, [1.0, 2.0, 3.0, 4.0])


class BudgetTest(unittest.TestCase):
    def test_call_that_crosses_the_budget_is_counted_before_the_stop(self):
        tracker = cost_tracker.CostTracker(budget_aud=1.0)
        with self.assertRaises(cost_tracker.BudgetExceededError):
            # Unpriced model: the $1/$4 per million fallback, about 6 AUD here
            tracker.check_and_add_usage(agent="generation", model="unit-test-model",
                                        input_tokens=0, output_tokens=1_000_000)
        self.assertEqual(tracker.total_calls, 1)
        self.assertGreater(tracker.total_cost_aud, 1.0)

    def test_report_makes_no_theme_call_once_the_budget_is_spent(self):
        tracker = cost_tracker.CostTracker(budget_aud=1.0)
        tracker.total_cost_usd = 10.0
        client = mock.Mock(cost_tracker=tracker)
        with mock.patch("src.llm.factory.get_llm_client", return_value=client):
            themes = html_report._derive_themes_via_llm([{"id": "h", "title": "t"}], "goal")
        self.assertIsNone(themes)
        client.invoke.assert_not_called()


TITLE = "Edited </script><script>window.__injected=1</script> see <!-- <script> title"
THEME = "X</script><script>window.__injected=2</script> <!-- <script>"


class ReportScriptTest(unittest.TestCase):
    def _page(self):
        hypothesis = Hypothesis(
            id="hyp_report", research_goal_id="goal_report", title=TITLE,
            summary="s", hypothesis_statement="h", rationale="r",
            experimental_protocol=ExperimentalProtocol(objective="o", methodology="m",
                                                       success_criteria="c"),
            generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        )
        run = {"goal": ResearchGoal(id="goal_report", description="g").model_dump(mode="json"),
               "run_timestamp": "2026-10-28T00:00:00",
               "hypotheses": [hypothesis.model_dump(mode="json")], "reviews": [],
               "matches": [], "context_memory": {}}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(html_report, "_derive_themes_via_llm",
                                  return_value={"hyp_report": THEME}):
            path = Path(tmp) / "run.json"
            path.write_text(json.dumps(run))
            return Path(html_report.generate_html_report(str(path))).read_text()

    def test_model_text_cannot_end_or_derail_the_inline_script(self):
        page = self._page()
        for name in ("DATA", "THEMES", "METHODS", "STATUSES", "INSIGHTS"):
            value = re.search(rf"const {name} = (.*);\n", page).group(1)
            self.assertNotIn("<", value, name)
            json.loads(value)
        data = json.loads(re.search(r"const DATA = (.*);\n", page).group(1))
        self.assertEqual(data[0]["title"], TITLE)
        self.assertIn(THEME, json.loads(re.search(r"const THEMES = (.*);\n", page).group(1)))

    def test_model_text_cannot_inject_into_the_page(self):
        page = self._page()
        self.assertNotIn("<script>window.__injected", page)
        self.assertNotIn("<!-- <script>", page)
        self.assertIn(escape(THEME), page)  # the strongest theme, shown as text


if __name__ == "__main__":
    unittest.main()
