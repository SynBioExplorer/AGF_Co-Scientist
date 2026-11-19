"""Resource limits apply before a request and while a phase is running."""
import asyncio
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / '03_architecture', ROOT / '04_Scripts'):
    sys.path.insert(0, str(path))
os.environ.setdefault('GOOGLE_API_KEY', 'unit-test-placeholder')

import cost_tracker
from cost_tracker import CostTracker, BudgetExceededError, USD_TO_AUD
from schemas import AgentTask, AgentType, ResearchGoal
from src.agents.supervisor import SupervisorAgent
from src.config import settings
from src.llm.base import BaseLLMClient
from src.llm.bedrock import BedrockClient
from src.llm import google as google_module
from src.llm import openai as openai_module
from src.supervisor.task_queue import TaskQueue
from src.storage.async_adapter import AsyncStorageAdapter
from src.utils.errors import RunAbortedError


def phase_supervisor(seconds=21600, elapsed=0):
    sup = SupervisorAgent.__new__(SupervisorAgent)
    sup.task_queue = TaskQueue()
    sup.agent_weights = {AgentType.GENERATION: 0.25}
    sup.iteration, sup._stalled_iterations, sup._last_task_error = 1, 0, None
    sup._drain_iterations = 0
    sup._workflow_started_at = datetime.now() - timedelta(seconds=elapsed)
    sup._max_execution_time_seconds = seconds
    sup._worker_semaphore = asyncio.Semaphore(4)
    sup.cost_tracker = CostTracker(budget_aud=100)
    sup._create_task_for_agent = mock.AsyncMock(side_effect=[
        AgentTask(id=f't{i}',agent_type=AgentType.GENERATION,task_type='generate_hypothesis',priority=5)
        for i in range(3)])
    sup._execute_task = mock.AsyncMock(return_value={'ok':True})
    sup._queue_full_reviews_for_top_initial = mock.AsyncMock()
    return sup


class Deadlines(unittest.IsolatedAsyncioTestCase):
    async def test_goal_parsing_is_inside_the_run_deadline(self):
        sup=SupervisorAgent.__new__(SupervisorAgent)
        sup.name,sup.logger,sup.storage='Bounded supervisor',mock.Mock(),AsyncStorageAdapter()
        sup.cost_tracker=CostTracker(budget_aud=50)
        client=BedrockClient.__new__(BedrockClient)
        BaseLLMClient.__init__(client,'unit-budget-model',sup.cost_tracker)

        async def parse(goal):
            self.assertLessEqual(client._request_timeout(300),0.1,
                                 'Goal parsing must not run outside the configured deadline')
            raise RunAbortedError('Boundary checked')

        sup._parse_research_goal=parse
        with self.assertRaises(RunAbortedError):
            await sup.execute(ResearchGoal(id='g',description='Question'),max_execution_time_seconds=0.1)

    async def test_unmatched_hypotheses_cannot_extend_the_deadline(self):
        sup = phase_supervisor()
        sup.storage = mock.Mock()
        sup.storage.get_all_matches = mock.AsyncMock(return_value=[])
        sup.storage.get_hypotheses_by_goal = mock.AsyncMock(return_value=[SimpleNamespace(id='h')])
        stop, reason = await sup._check_terminal_conditions(
            SimpleNamespace(research_goal_id='g'),1,0.8,0.01,
            datetime.now()-timedelta(hours=8),21600)
        self.assertTrue(stop)
        self.assertIn('time', reason.lower())

    async def test_expired_run_starts_no_new_phase_work(self):
        sup = phase_supervisor(seconds=1,elapsed=2)
        with mock.patch.object(settings,'proximity_aware_pairing',False), \
                mock.patch.object(settings,'drain_phase_start_fraction',10):
            await sup._execute_iteration(ResearchGoal(id='g',description='A bounded test'))
        sup._execute_task.assert_not_called()

    async def test_inflight_phase_is_cancelled_at_the_run_deadline(self):
        sup = phase_supervisor(seconds=0.025)
        cancelled = asyncio.Event()

        async def blocked(*args):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        sup._execute_task.side_effect = blocked
        with mock.patch.object(settings,'proximity_aware_pairing',False):
            try:
                await asyncio.wait_for(sup._execute_iteration(ResearchGoal(id='g',description='A bounded test')),0.2)
            except asyncio.TimeoutError:
                self.fail('A running phase exceeded the remaining run deadline')
        self.assertTrue(cancelled.is_set())


class AdmissionBudget(unittest.IsolatedAsyncioTestCase):
    def client(self, llm):
        tracker = CostTracker(budget_aud=1.5)
        client = BedrockClient.__new__(BedrockClient)
        BaseLLMClient.__init__(client,'unit-budget-model',tracker)
        client.agent_name, client.max_tokens, client.timeout = 'generation', 1000, 1
        client.llm = llm
        return client

    async def test_simultaneous_requests_cannot_oversubscribe_the_budget(self):
        release = asyncio.Event()
        requested_caps = []

        class Provider:
            max_tokens = 1000

            async def ainvoke(self, prompt, **kwargs):
                requested_caps.append(kwargs.get('maxTokens', kwargs.get('max_tokens', self.max_tokens)))
                await release.wait()
                return SimpleNamespace(content='{}',usage_metadata={'input_tokens':1,'output_tokens':10},response_metadata={})

        client = self.client(Provider())
        # A full 1,000-token response would cost exactly one AUD at this rate.
        rate = {'input':0,'output':1_000_000/1000/USD_TO_AUD}
        with mock.patch.dict(cost_tracker.MODEL_PRICING, {'unit-budget-model':rate}):
            tasks = [asyncio.create_task(client.ainvoke('A short prompt')) for _ in range(2)]
            await asyncio.sleep(0.04)
            committed = sum(requested_caps)/1000
            release.set()
            await asyncio.gather(*tasks,return_exceptions=True)
        self.assertLessEqual(committed,1.5,
            'Concurrent request output caps committed more money than the run owns')

    async def test_provider_wait_is_bounded_by_the_run_deadline(self):
        provider=mock.Mock()
        async def blocked(*args,**kwargs):
            await asyncio.sleep(10)
        provider.ainvoke=mock.AsyncMock(side_effect=blocked)
        client=self.client(provider)
        client.cost_tracker.deadline_monotonic=time.monotonic()+0.025
        rate={'input':0,'output':1_000_000/1000/USD_TO_AUD}
        with mock.patch.dict(cost_tracker.MODEL_PRICING,{'unit-budget-model':rate}):
            try:
                await asyncio.wait_for(client.ainvoke('A short prompt'),0.2)
            except asyncio.TimeoutError:
                self.fail('Provider/retry waits outlived the run deadline')
            except Exception as error:
                self.assertIn('time limit',str(error).lower())
            else:
                self.fail('Expected an explicit run time limit failure')
        self.assertEqual(provider.ainvoke.call_count,1)

    async def test_sync_retry_backoff_cannot_extend_the_run_deadline(self):
        provider=mock.Mock()
        provider.invoke.side_effect=RuntimeError('503 service unavailable')
        client=self.client(provider)
        client.cost_tracker.deadline_monotonic=time.monotonic()+0.025
        rate={'input':0,'output':1_000_000/1000/USD_TO_AUD}
        started=time.monotonic()
        with mock.patch.dict(cost_tracker.MODEL_PRICING,{'unit-budget-model':rate}), \
                mock.patch.object(settings,'llm_retry_base_delay',0.1), \
                mock.patch.object(settings,'llm_retry_max_delay',0.1), \
                mock.patch.object(settings,'llm_max_retries',1):
            try:
                client.invoke('A short prompt')
            except Exception as error:
                self.assertIn('time limit',str(error).lower())
            else:
                self.fail('Expected an explicit run time limit failure')
        self.assertLess(time.monotonic()-started,0.09)

    async def test_unused_reservation_is_available_after_a_response(self):
        calls = []

        class Provider:
            async def ainvoke(self,prompt,**kwargs):
                calls.append(prompt)
                return SimpleNamespace(content='{}',usage_metadata={'input_tokens':1,'output_tokens':10},response_metadata={})

        client = self.client(Provider())
        rate = {'input':0,'output':1_000_000/1000/USD_TO_AUD}
        with mock.patch.dict(cost_tracker.MODEL_PRICING, {'unit-budget-model':rate}):
            await client.ainvoke('First')
            await client.ainvoke('Second')
        self.assertEqual(calls,['First','Second'])

    async def test_response_that_exactly_fills_its_reservation_is_kept(self):
        provider = mock.Mock()
        provider.ainvoke = mock.AsyncMock(return_value=SimpleNamespace(content='Useful result',
            usage_metadata={'input_tokens':1,'output_tokens':1000},response_metadata={}))
        client = self.client(provider)
        client.cost_tracker.budget_aud = 1.0
        rate = {'input':0,'output':1_000_000/1000/USD_TO_AUD}
        with mock.patch.dict(cost_tracker.MODEL_PRICING, {'unit-budget-model':rate}):
            try:
                result = await client.ainvoke('A short prompt')
            except BudgetExceededError:
                self.fail('The already-paid response fitted the cap and must be retained')
        self.assertEqual(result,'Useful result')

    async def test_lost_response_cannot_make_possible_spend_disappear(self):
        provider = mock.Mock()
        provider.ainvoke = mock.AsyncMock(side_effect=RuntimeError('Response lost after acceptance'))
        client = self.client(provider)
        rate = {'input':0,'output':1_000_000/1000/USD_TO_AUD}
        with mock.patch.dict(cost_tracker.MODEL_PRICING, {'unit-budget-model':rate}):
            for _ in range(2):
                try:
                    await client.ainvoke('A short prompt')
                except Exception:
                    pass
        self.assertEqual(provider.ainvoke.call_count,1,
            'A request with unknown billing must retain its budget reservation')

    async def test_missing_usage_metadata_keeps_possible_spend_reserved(self):
        provider = mock.Mock()
        provider.ainvoke = mock.AsyncMock(return_value=SimpleNamespace(content='Useful result',
            usage_metadata=None,response_metadata={}))
        client = self.client(provider)
        rate = {'input':0,'output':1_000_000/1000/USD_TO_AUD}
        with mock.patch.dict(cost_tracker.MODEL_PRICING, {'unit-budget-model':rate}):
            self.assertEqual(await client.ainvoke('First'),'Useful result')
            try:
                await client.ainvoke('Second')
            except BudgetExceededError:
                pass
        self.assertEqual(provider.ainvoke.call_count,1)

    async def test_possible_spend_survives_tracker_reload(self):
        provider = mock.Mock()
        provider.ainvoke = mock.AsyncMock(side_effect=RuntimeError('Response lost after acceptance'))
        client = self.client(provider)
        rate = {'input':0,'output':1_000_000/1000/USD_TO_AUD}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(cost_tracker.MODEL_PRICING, {'unit-budget-model':rate}):
            path = Path(tmp)/'cost.json'
            client.cost_tracker = CostTracker(budget_aud=1.5,persist_path=str(path))
            try:
                await client.ainvoke('First')
            except Exception:
                pass
            self.assertTrue(path.exists(),'The admission ledger must be persisted before dispatch')
            client.cost_tracker = CostTracker(budget_aud=1.5,persist_path=str(path))
            try:
                await client.ainvoke('Second')
            except Exception:
                pass
        self.assertEqual(provider.ainvoke.call_count,1)


class ProviderRetryOwnership(unittest.TestCase):
    def test_google_sdk_does_not_retry_outside_the_budget_controller(self):
        with mock.patch.object(google_module,'ChatGoogleGenerativeAI') as sdk, \
                mock.patch.object(google_module,'get_tracker',return_value=CostTracker()):
            google_module.GoogleGeminiClient('gemini-4-argon','generation')
        self.assertEqual(sdk.call_args.kwargs.get('max_retries'),0)


class UsageAccounting(unittest.TestCase):
    def test_nonfinite_or_negative_budget_is_rejected(self):
        for budget in [float('nan'),float('inf'),-1.0]:
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                CostTracker(budget_aud=budget)

    def test_openai_reasoning_is_already_in_total_output_tokens(self):
        client = openai_module.OpenAIClient.__new__(openai_module.OpenAIClient)
        reply = SimpleNamespace(usage_metadata={'input_tokens':20,'output_tokens':10,
            'output_token_details':{'reasoning':4}},response_metadata={})
        self.assertEqual(client._extract_usage(reply,'prompt','answer'),(20,10))

    def test_google_zero_candidates_does_not_discard_thinking_usage(self):
        client = google_module.GoogleGeminiClient.__new__(google_module.GoogleGeminiClient)
        reply = SimpleNamespace(usage_metadata=None,response_metadata={'usage_metadata':{
            'prompt_token_count':20,'candidates_token_count':0,'thoughts_token_count':10}})
        self.assertEqual(client._extract_usage(reply,'prompt',''),(20,10))

    def test_openai_sdk_does_not_retry_outside_the_budget_controller(self):
        with mock.patch.dict(os.environ,{'OPENAI_API_KEY':'unit-test-placeholder'}), \
                mock.patch.object(openai_module,'ChatOpenAI') as sdk, \
                mock.patch.object(openai_module,'get_tracker',return_value=CostTracker()):
            openai_module.OpenAIClient('gpt-5','generation')
        self.assertEqual(sdk.call_args.kwargs.get('max_retries'),0)


if __name__ == '__main__':
    unittest.main()
