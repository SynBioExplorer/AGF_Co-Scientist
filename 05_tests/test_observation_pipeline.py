"""Observation reviews must use retrieved evidence and retain its provenance."""
import asyncio
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT/'03_architecture', ROOT/'04_Scripts'):
    sys.path.insert(0,str(path))
os.environ.setdefault('GOOGLE_API_KEY','unit-test-placeholder')

from schemas import (AgentType, ExperimentalProtocol, GenerationMethod, Hypothesis,
                     ResearchGoal, Observation, ObservationType, AgentTask, Review, ReviewType)
from src.agents.generation import GenerationAgent
from src.agents.observation_review import ObservationReviewAgent
from src.agents.reflection import ReflectionAgent
from src.agents.supervisor import SupervisorAgent
from src.config import settings
from src.literature.citation_graph import CitationGraph
from src.storage.async_adapter import AsyncStorageAdapter
from src.supervisor.task_queue import TaskQueue
from src.utils.errors import CoScientistError


def hypothesis():
    return Hypothesis(id='h',research_goal_id='g',title='A scientific hypothesis',summary='s',
        hypothesis_statement='A predicts B',rationale='r',mechanism='m',
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        experimental_protocol=ExperimentalProtocol(objective='o',methodology='m',success_criteria='c'))


def agent():
    reviewer=ObservationReviewAgent.__new__(ObservationReviewAgent)
    reviewer.name,reviewer.logger,reviewer.llm_client='Observation test',mock.Mock(),mock.Mock()
    return reviewer


class EvidenceHandoff(unittest.IsolatedAsyncioTestCase):
    async def test_passing_full_review_prioritizes_verification(self):
        goal=ResearchGoal(id='g',description='Question')
        sup=SupervisorAgent.__new__(SupervisorAgent)
        sup.storage,sup.task_queue=AsyncStorageAdapter(),TaskQueue()
        sup._context_insights,sup._explored_directions=[],[]
        await sup.storage.add_hypothesis(hypothesis())
        reviewer=mock.Mock()
        reviewer.execute=mock.AsyncMock(return_value=Review(id='full',hypothesis_id='h',
            review_type=ReviewType.FULL,passed=True,rationale='Supported'))
        sup._agents={AgentType.REFLECTION:reviewer}
        sup.task_queue.add_task(AgentTask(id='fresh',agent_type=AgentType.REFLECTION,
            task_type='review_hypothesis',priority=9,
            parameters={'hypothesis_id':'new_h','review_type':'initial'}))
        await sup._execute_task(AgentTask(id='full_task',agent_type=AgentType.REFLECTION,
            task_type='review_hypothesis',parameters={'hypothesis_id':'h','review_type':'full'}),goal)
        next_task=sup.task_queue.get_next_task(AgentType.REFLECTION)
        self.assertEqual(next_task.parameters['review_type'],'deep_verification')

    async def test_deep_verification_uses_the_supplied_evidence_context(self):
        reviewer=ReflectionAgent.__new__(ReflectionAgent)
        reviewer.name,reviewer.logger,reviewer.llm_client='Reflection test',mock.Mock(),mock.Mock()
        reviewer.llm_client.ainvoke=mock.AsyncMock(return_value=json.dumps({'assumptions':[], 'overall_valid':False}))
        await reviewer.execute(hypothesis(),ReviewType.DEEP_VERIFICATION,
            use_refutation_search=False,context_guidance='SOURCE_CONTEXT_SENTINEL')
        prompt=reviewer.llm_client.ainvoke.call_args.args[0]
        self.assertIn('SOURCE_CONTEXT_SENTINEL',prompt)

    async def test_scheduled_review_receives_the_generation_evidence(self):
        goal=ResearchGoal(id='g',description='A scientific question')
        graph=CitationGraph()
        graph.add_paper(paper_id='paper',title='A measured result',authors=[],doi='10.9999/source',
                        abstract='We measured a reproducible SOURCE_SENTINEL result.')
        generator=GenerationAgent.__new__(GenerationAgent)
        generator._literature_by_goal={'g':('Retrieved source context',graph)}
        reviewer=agent()

        def answer(prompt):
            self.assertIn('SOURCE_SENTINEL',prompt)
            oid=re.search(r'ID: ([^)]+)',prompt).group(1)
            return json.dumps({'explanations':[{'observation_id':oid,'explains':True,
                'explanation_score':0.8,'reasoning':'The cited observation supports this step'}],
                'overall_score':0.8,'observations_explained_count':1,'observations_total_count':1,
                'summary':'One retrieved observation evaluated'})

        reviewer.llm_client.invoke.side_effect=answer
        reviewer.llm_client.ainvoke=mock.AsyncMock(side_effect=answer)
        sup=SupervisorAgent.__new__(SupervisorAgent)
        sup.storage=AsyncStorageAdapter()
        await sup.storage.add_hypothesis(hypothesis())
        sup.task_queue=TaskQueue()
        sup._agents={AgentType.GENERATION:generator,AgentType.OBSERVATION_REVIEW:reviewer}
        with mock.patch.object(settings,'enable_web_search',True):
            task=await sup._create_task_for_agent(AgentType.OBSERVATION_REVIEW,goal)
            self.assertIsNotNone(task,'Retrieved evidence must be scheduled for observation review')
            await sup._execute_task(task,goal)
        result=await sup.storage.get_observation_review('h')
        self.assertIsNotNone(result)
        self.assertEqual(result.observations_total_count,1)
        self.assertEqual(result.observations[0].paper_id,'10.9999/source')

    async def test_missing_evidence_is_unknown_not_a_zero_score(self):
        result=await agent().execute_with_citation_graph(hypothesis(),CitationGraph(),
                ResearchGoal(id='g',description='A scientific question'))
        self.assertIsNone(result.overall_score)

    async def test_model_cannot_invent_observations(self):
        reviewer=agent()
        reply=json.dumps({'explanations':[{'observation_id':'invented','explains':True,
            'explanation_score':1,'reasoning':'unsupported'}], 'overall_score':1,
            'observations_explained_count':99,'observations_total_count':99,'summary':'Everything works'})
        reviewer.llm_client.invoke.return_value=reply
        reviewer.llm_client.ainvoke=mock.AsyncMock(return_value=reply)
        observations=[Observation(id='known',paper_id='doi',paper_title='Source',
            observation_type=ObservationType.EXPERIMENTAL,text='Measured result',context='Reported source context')]
        with self.assertRaises(CoScientistError):
            await reviewer.execute(hypothesis(),observations,ResearchGoal(id='g',description='Question'))

    async def test_counts_are_derived_from_the_supplied_observations(self):
        reviewer=agent()
        reply=json.dumps({'explanations':[{'observation_id':'known','explains':False,
            'explanation_score':0.2,'reasoning':'Does not account for this observation'}],
            'overall_score':1,'observations_explained_count':99,'observations_total_count':99,'summary':'One result'})
        reviewer.llm_client.invoke.return_value=reply
        reviewer.llm_client.ainvoke=mock.AsyncMock(return_value=reply)
        observations=[Observation(id='known',paper_id='doi',paper_title='Source',
            observation_type=ObservationType.EXPERIMENTAL,text='Measured result',context='Reported source context')]
        result=await reviewer.execute(hypothesis(),observations,ResearchGoal(id='g',description='Question'))
        self.assertEqual(result.observations_total_count,1)
        self.assertEqual(result.observations_explained_count,0)
        self.assertEqual(result.overall_score,0.2)


if __name__=='__main__':
    unittest.main()
