"""Scientific findings must survive identity checks and the final run status.

The worker runs unchanged against in-memory research state; only external AWS
and rendering calls are supplied by the established entrypoint test harness.
"""
import asyncio
import json
import os
import sys
import unittest
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT, ROOT / '03_architecture', ROOT / '04_Scripts'):
    sys.path.insert(0, str(directory))
os.environ.setdefault('GOOGLE_API_KEY', 'unit-test-placeholder')

import cost_tracker
from schemas import (Citation, ExperimentalProtocol, GenerationMethod, Hypothesis,
                     ResearchOverview, ResearchGoal, Review, ReviewType, AgentType,
                     Observation, ObservationExplanation, ObservationReviewScore, ObservationType)
from src.agents.generation import GenerationAgent
from src.literature.citation_graph import CitationGraph
from src.agents.supervisor import SupervisorAgent
from src.storage.async_adapter import AsyncStorageAdapter
from src.config import settings
from src.utils import html_report
import test_llm_failure_abort as entrypoint_fixture


def hypothesis(hid, goal_id, elo=1200):
    return Hypothesis(id=hid, research_goal_id=goal_id, title='A testable proposal',
        summary='s', hypothesis_statement='A testable claim', rationale='r', mechanism='m',
        generation_method=GenerationMethod.LITERATURE_EXPLORATION, elo_rating=elo,
        experimental_protocol=ExperimentalProtocol(objective='o', methodology='m',
                                                   success_criteria='c'))


def observation_review(hid, goal_id):
    observation = Observation(id=f'obs_{hid}',paper_id='10.9999/paper',paper_title='A real paper',
        observation_type=ObservationType.EXPERIMENTAL,text='A measured observation',context='The complete source context')
    explanation = ObservationExplanation(observation_id=observation.id,hypothesis_id=hid,
        explains=True,explanation_score=0.8,reasoning='Consistent with the supplied observation')
    return ObservationReviewScore(id=f'obs_review_{hid}',hypothesis_id=hid,research_goal_id=goal_id,
        observations=[observation],explanations=[explanation],overall_score=0.8,
        observations_explained_count=1,observations_total_count=1,summary='One source assessed')


def report_fixture(context_memory=None):
    hypotheses, reviews, observations = [], [], []
    for hid,elo,passed,title in [('bad',1300,False,'Unsupported high-Elo proposal'),
                                 ('good',1200,True,'Supported lower-Elo proposal')]:
        h=hypothesis(hid,'g',elo)
        h.title=title
        h.literature_citations=[Citation(title='A real paper',doi='10.9999/paper',relevance='r',
            verification_status='verified',canonical_title='A real paper')]
        hypotheses.append(h.model_dump(mode='json'))
        for kind in (ReviewType.FULL,ReviewType.DEEP_VERIFICATION):
            reviews.append(Review(id=f'{hid}_{kind.value}',hypothesis_id=hid,review_type=kind,
                passed=passed,rationale='Supported' if passed else 'Critical premise is false',
                quality_score=0.9 if not passed else 0.7).model_dump(mode='json'))
        observations.append(observation_review(hid,'g').model_dump(mode='json'))
    return {'goal':{'description':'A scientific report fixture'},'hypotheses':hypotheses,
        'reviews':reviews,'observation_reviews':observations,'matches':[],
        'context_memory':context_memory,'scientific_status':'partial',
        'warning':'The highest-Elo hypothesis failed scientific review.'}


class CitationIdentity(unittest.TestCase):
    def check(self, claimed, canonical):
        agent = GenerationAgent.__new__(GenerationAgent)
        agent.logger, agent.tool_registry = mock.Mock(), {}
        h = hypothesis('h', 'g')
        h.literature_citations = [Citation(title=claimed, doi='10.9999/identity', relevance='r')]
        graph = CitationGraph()
        graph.add_paper(paper_id='p', title=canonical, authors=[], doi='10.9999/identity')
        result = asyncio.run(agent._validate_citations(h, graph))
        return result.literature_citations[0]

    def test_opposite_meaning_title_is_not_verified(self):
        citation = self.check('Protein abundance increases cell growth',
                              'Protein abundance decreases cell growth')
        self.assertEqual(citation.verification_status, 'title_mismatch')
        self.assertEqual(citation.canonical_title, 'Protein abundance decreases cell growth')

    def test_added_negation_is_not_verified(self):
        self.assertEqual(self.check('Kinase activity does not regulate cell growth',
                                    'Kinase activity regulates cell growth').verification_status,
                         'title_mismatch')

    def test_title_word_reordering_is_not_verified(self):
        self.assertEqual(self.check('Protein A inhibits protein B',
                                    'Protein B inhibits protein A').verification_status,
                         'title_mismatch')

    def test_typesetting_differences_do_not_change_identity(self):
        self.assertEqual(self.check('CO2 fixation in yeast: a measured result.',
                                    'CO₂ fixation in yeast — a measured result').verification_status,
                         'verified')


@entrypoint_fixture.NEEDS_ENTRYPOINT
class ScientificCompletion(unittest.TestCase):
    def run_worker(self, leader_passed, secondary_reviewed=True,
                   leader_review_type=ReviewType.FULL, failed_deep=False,
                   citation_status='verified', with_deep=True, with_observations=True):
        fixture = entrypoint_fixture.Entrypoint()
        fixture.ENV = {**fixture.ENV, 'RUN_ID': 'scientific-completion-test'}

        class Supervisor:
            def __init__(self, storage):
                self.storage, self.stall_warning, self.terminal_reason = storage, None, None

            async def execute(self, goal, max_iterations, **kwargs):
                for hid, elo in [('leader', 1300), ('secondary', 1200)]:
                    h = hypothesis(hid, goal.id, elo)
                    h.literature_citations = [Citation(title='A real paper', doi='10.9999/paper',
                        relevance='The relevant observation', canonical_title='A real paper',
                        verification_status=citation_status if hid == 'leader' else 'verified')]
                    await self.storage.add_hypothesis(h)
                await self.storage.add_review(Review(id='leader_full', hypothesis_id='leader',
                    review_type=leader_review_type, passed=leader_passed,
                    rationale='The critical premise is supported' if leader_passed else 'The critical premise is false'))
                if with_deep:
                    await self.storage.add_review(Review(id='leader_deep', hypothesis_id='leader',
                        review_type=ReviewType.DEEP_VERIFICATION, passed=not failed_deep,
                        rationale='A necessary assumption remains uncertain'))
                if secondary_reviewed:
                    await self.storage.add_review(Review(id='secondary_full', hypothesis_id='secondary',
                        review_type=ReviewType.FULL, passed=True, rationale='Supported'))
                if with_observations:
                    for hid in ('leader','secondary'):
                        await self.storage.add_observation_review(observation_review(hid,goal.id))
                await self.storage.save_research_overview(ResearchOverview(id='overview',
                    research_goal_id=goal.id, executive_summary='Summary of the work',
                    current_knowledge_boundary='Experimental validation remains necessary'))
                return 'Finished'

        try:
            with mock.patch.object(cost_tracker, 'get_tracker',
                                   return_value=cost_tracker.CostTracker(budget_aud=50)):
                code, ddb, s3, ses = fixture._main(Supervisor)
            self.assertEqual(code, 0)
            payload = next(json.loads(c.kwargs['Body']) for c in s3.put_object.call_args_list
                           if c.kwargs.get('Key', '').endswith('/output/run.json'))
            metadata = next(json.loads(c.kwargs['Body']) for c in s3.put_object.call_args_list
                            if c.kwargs.get('Key', '').endswith('/metadata/status.json'))
            return payload, metadata
        finally:
            fixture.doCleanups()

    def test_failed_leading_full_review_keeps_the_run_partial(self):
        payload, metadata = self.run_worker(leader_passed=False)
        self.assertEqual(payload['scientific_status'], 'partial')
        self.assertEqual(metadata['scientific_status'], 'partial')
        self.assertIn('failed', payload['warning'].lower())

    def test_unreviewed_secondary_hypothesis_is_visible(self):
        payload, _ = self.run_worker(leader_passed=True, secondary_reviewed=False)
        self.assertEqual(payload['scientific_status'], 'partial')
        self.assertIn('review', payload['warning'].lower())

    def test_a_reviewed_supported_result_can_complete(self):
        payload, metadata = self.run_worker(leader_passed=True)
        self.assertEqual(payload['scientific_status'], 'complete')
        self.assertIsNone(payload['warning'])
        self.assertEqual(payload.get('scientific_review_version'),1)
        self.assertEqual(metadata.get('scientific_review_version'),1)

    def test_initial_screening_is_not_a_complete_scientific_review(self):
        payload, _ = self.run_worker(leader_passed=True, leader_review_type=ReviewType.INITIAL)
        self.assertEqual(payload['scientific_status'], 'partial')

    def test_failed_deep_verification_is_not_overridden_by_a_passing_full_review(self):
        payload, _ = self.run_worker(leader_passed=True, failed_deep=True)
        self.assertEqual(payload['scientific_status'], 'partial')

    def test_unverified_supporting_citation_prevents_scientific_completion(self):
        payload, _ = self.run_worker(leader_passed=True, citation_status='title_mismatch')
        self.assertEqual(payload['scientific_status'], 'partial')

    def test_missing_deep_verification_keeps_the_result_partial(self):
        payload,_=self.run_worker(leader_passed=True,with_deep=False)
        self.assertEqual(payload['scientific_status'],'partial')

    def test_missing_evidence_assessment_keeps_the_result_partial(self):
        payload,_=self.run_worker(leader_passed=True,with_observations=False)
        self.assertEqual(payload['scientific_status'],'partial')

    def test_observation_evidence_is_exported_with_the_result(self):
        payload,_=self.run_worker(leader_passed=True)
        self.assertIn('observation_reviews',payload)
        self.assertEqual(payload['observation_reviews'][0]['observations'][0]['paper_id'],'10.9999/paper')


class RecommendationEligibility(unittest.IsolatedAsyncioTestCase):
    async def run_overview(self, include_good=True):
        storage=AsyncStorageAdapter()
        for hid,elo,passed in [('bad',1300,False)]+([('good',1200,True)] if include_good else []):
            h=hypothesis(hid,'g',elo)
            h.literature_citations=[Citation(title='A real paper',doi='10.9999/paper',relevance='r',
                verification_status='verified',canonical_title='A real paper')]
            await storage.add_hypothesis(h)
            for kind in (ReviewType.FULL,ReviewType.DEEP_VERIFICATION):
                await storage.add_review(Review(id=f'{hid}_{kind.value}',hypothesis_id=hid,review_type=kind,
                    passed=passed,rationale='Supported' if passed else 'Critical premise is false'))
            await storage.add_observation_review(observation_review(hid,'g'))
        storage.get_meta_review=mock.AsyncMock(return_value=object())
        meta=mock.Mock()
        meta.generate_research_overview.return_value=ResearchOverview(id='overview',research_goal_id='g',
            executive_summary='A synthesis',current_knowledge_boundary='Further experiments are needed')
        sup=SupervisorAgent.__new__(SupervisorAgent)
        sup.storage,sup.cost_tracker,sup._agents=storage,cost_tracker.CostTracker(),{AgentType.META_REVIEW:meta}
        with mock.patch.object(settings,'diversity_sampling_for_overview',False):
            result=await sup._generate_final_overview(ResearchGoal(id='g',description='Question'))
        return result,meta

    async def test_failed_high_elo_candidate_is_not_sent_as_a_recommendation(self):
        _,meta=await self.run_overview()
        self.assertEqual([h.id for h in meta.generate_research_overview.call_args.kwargs['top_hypotheses']],['good'])

    async def test_no_supported_candidates_produces_no_model_generated_recommendation(self):
        result,meta=await self.run_overview(include_good=False)
        meta.generate_research_overview.assert_not_called()
        self.assertEqual(result.research_directions,[])


class ReportEvidence(unittest.TestCase):
    def prepare(self, context_memory):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(html_report,'_derive_themes_via_llm',return_value={}):
            path=Path(tmp)/'run.json'
            path.write_text(json.dumps(report_fixture(context_memory)))
            return html_report._prepare_data(path)

    def test_ready_candidate_precedes_failed_high_elo_in_report_data(self):
        prepared=self.prepare({})
        self.assertEqual([h['id'] for h in prepared['hyp_cards']],['good','bad'])

    def test_absent_context_memory_does_not_break_the_report(self):
        try:
            prepared=self.prepare(None)
        except AttributeError:
            self.fail('A valid worker result with no context memory must still render')
        self.assertEqual(prepared['insights'],[])

    def test_failure_reporting_does_not_start_more_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(html_report,'_derive_themes_via_llm',return_value={}) as themes:
            data=report_fixture({})
            data['execution_status']='failed'
            path=Path(tmp)/'run.json';path.write_text(json.dumps(data))
            html_report.generate_html_report(str(path))
        themes.assert_not_called()


if __name__ == '__main__':
    unittest.main()
