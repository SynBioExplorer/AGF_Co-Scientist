"""A run whose LLM calls keep failing ends as failed, not as an empty "complete".

The supervisor runs with its real agents and BedrockClient over a stand-in for
ChatBedrockConverse, so a failed call takes the production path: BedrockClient
raises, the retry layer retries or not, the agent lets it through and the
supervisor counts the stalled iteration. A fake clock stands in for the
supervisor's datetime and asyncio.sleep, so pauses cost no time. Stdlib
unittest, run by buildspec.yml inside the built image like
test_bedrock_routing.py.
"""
import asyncio
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from botocore.exceptions import ClientError, ReadTimeoutError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# supervisor.py appends "03_Architecture", which resolves only on a
# case-insensitive filesystem; the image is Linux.
sys.path.insert(0, str(ROOT / "03_architecture"))
sys.path.insert(0, str(ROOT / "04_Scripts"))
# Settings requires a Google key at import time; these tests never call Google.
os.environ.setdefault("GOOGLE_API_KEY", "unit-test-placeholder")

import cost_tracker  # noqa: E402
from cost_tracker import BudgetExceededError  # noqa: E402
from schemas import (  # noqa: E402
    AgentTask, AgentType, ExperimentalProtocol, GenerationMethod, Hypothesis, ResearchGoal,
    Citation, Review, ReviewType, Observation, ObservationType, ObservationExplanation, ObservationReviewScore,
    ResearchOverview,
)
from src.agents import supervisor as supervisor_module  # noqa: E402
from src.agents.generation import GenerationAgent  # noqa: E402
from src.agents.supervisor import (  # noqa: E402
    STALLED_ITERATIONS_LIMIT, TRANSIENT_STALL_MIN_SECONDS, SupervisorAgent,
)
from src.config import settings  # noqa: E402
from src.literature.citation_graph import CitationGraph  # noqa: E402
from src.llm import bedrock  # noqa: E402
from src.storage.async_adapter import AsyncStorageAdapter  # noqa: E402
from src.utils.errors import (  # noqa: E402
    CoScientistError, ContentFilteredError, LLMClientError, LLMRateLimitError,
    LLMTimeoutError, RetryableError, RunAbortedError,
    RunTimeLimitError,
)
from src.utils import html_report  # noqa: E402
from src.utils.ids import generate_task_id  # noqa: E402
from src.utils.retry import classify_error  # noqa: E402

GOAL = ResearchGoal(
    id="goal_abort_test",
    description="Engineer a Pseudomonas putida strain that degrades PET at 30 C.",
)
# Pinned so the messages under test do not follow config.py defaults.
GENERATION_MODEL = "anthropic.claude-opus-4-8"
SUPERVISOR_MODEL = "anthropic.claude-sonnet-5"
_PATCHES = []


def setUpModule():
    # The cost tracker persists its spend to ./data and reloads it on the next
    # start; keep what these tests charge in memory.
    patch = mock.patch.object(cost_tracker, "_tracker", cost_tracker.CostTracker(
        budget_aud=settings.budget_aud, persist_path=None))
    patch.start()
    _PATCHES.append(patch)


def tearDownModule():
    for patch in _PATCHES:
        patch.stop()


class _Chat:
    """Stands in for ChatBedrockConverse and records every prompt it is sent."""

    def __init__(self, **kwargs):
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return self.respond(prompt)

    async def ainvoke(self, prompt):
        return self.invoke(prompt)


def _reply(text):
    return mock.Mock(response_metadata={"stopReason": "end_turn"}, content=text,
                     usage_metadata={"input_tokens": 10, "output_tokens": 10})


class _FilteredChat(_Chat):
    """Bedrock's content filter blocks every prompt."""

    def respond(self, prompt):
        return mock.Mock(response_metadata={"stopReason": "content_filtered"}, content=[],
                         usage_metadata={"input_tokens": 1000, "output_tokens": 0})


class _ThrottledChat(_Chat):
    def respond(self, prompt):
        raise ClientError({"Error": {"Code": "ThrottlingException",
                                     "Message": "Too many requests, please wait."}}, "Converse")


class _UnparsableChat(_Chat):
    def respond(self, prompt):
        return _reply("I am unable to help with that request.")


class _GoalParsingChat(_Chat):
    """Answers the supervisor's goal parsing so the loop starts."""

    def respond(self, prompt):
        return _reply('{"evaluation_criteria": ["novelty", "feasibility"]}')


HYPOTHESIS_JSON = """{"title": "PETase surface display", "statement": "s", "rationale": "r",
 "mechanism": "m", "experimental_protocol": {"objective": "o", "methodology": "m",
 "controls": [], "expected_outcomes": [], "success_criteria": "c"}, "citations": [],
 "assumptions": [{"statement": "a", "is_fundamental": true}]}"""


class _Clock:
    """The supervisor's wall clock: moves only by the pauses it sleeps and by
    the time a chat stand-in says a call took."""

    def __init__(self):
        self.offset = timedelta(0)
        self.pauses = []
        clock = self

        class _Datetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.now(tz) + clock.offset

        self._datetime = _Datetime

    def advance(self, seconds):
        self.offset += timedelta(seconds=seconds)

    async def _sleep(self, seconds, *args, **kwargs):
        if seconds:
            self.pauses.append(seconds)
            self.advance(seconds)

    @contextlib.contextmanager
    def installed(self):
        with mock.patch.object(supervisor_module, "datetime", self._datetime), \
                mock.patch("asyncio.sleep", self._sleep):
            yield self


@contextlib.contextmanager
def _bedrock(chat_cls):
    """Every agent on Bedrock over chat_cls, with no literature or web search
    and no wait between the client's retries."""
    # These cases isolate outage/retry behavior, not admission limits. Each gets
    # a fresh generous ledger because missing responses now retain reservations.
    # The small-budget concurrency/uncertainty tests live in test_run_limits.py.
    with mock.patch.object(cost_tracker, "_tracker", cost_tracker.CostTracker(budget_aud=1000)), \
            mock.patch.object(settings, "budget_aud", 1000), \
            mock.patch.object(settings, "llm_provider", "bedrock"), \
            mock.patch.object(settings, "bedrock_generation_model", GENERATION_MODEL), \
            mock.patch.object(settings, "bedrock_supervisor_model", SUPERVISOR_MODEL), \
            mock.patch.object(settings, "enable_refutation_search", False), \
            mock.patch.object(settings, "llm_retry_base_delay", 0.0), \
            mock.patch.object(settings, "llm_retry_max_delay", 0.0), \
            mock.patch.object(bedrock, "ChatBedrockConverse", chat_cls), \
            mock.patch.object(GenerationAgent, "_search_literature_tools",
                              mock.AsyncMock(return_value=([], CitationGraph()))), \
            mock.patch.object(GenerationAgent, "_search_tavily_fallback", return_value=""):
        yield


def _supervisor():
    """Call inside _bedrock(): agents are created lazily during execute()."""
    sup = SupervisorAgent(AsyncStorageAdapter())
    sup.llm_client.llm = _GoalParsingChat()
    return sup


def _generation_prompts(sup):
    return sup._agents[AgentType.GENERATION].llm_client.llm.prompts


def _hypothesis(i, goal_id=GOAL.id):
    return Hypothesis(
        id=f"hyp_seed_{i}", research_goal_id=goal_id, title=f"Seeded hypothesis {i}",
        summary="s", hypothesis_statement="h", rationale="r",
        experimental_protocol=ExperimentalProtocol(objective="o", methodology="m",
                                                   success_criteria="c"),
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
    )


def _run(sup, max_iterations=20, seed=0):
    async def go():
        for i in range(seed):
            await sup.storage.add_hypothesis(_hypothesis(i))
        return await sup.execute(GOAL, max_iterations=max_iterations)
    return asyncio.run(go())


class RunStopsWhenLlmCallsKeepFailing(unittest.TestCase):
    def test_blocked_generation_fails_the_run_after_three_iterations(self):
        with _bedrock(_FilteredChat), _Clock().installed() as clock:
            sup = _supervisor()
            with self.assertRaises(RunAbortedError) as ctx:
                _run(sup)
        msg = str(ctx.exception)
        self.assertIn("No hypotheses were produced", msg)
        self.assertIn(f"content filter blocked the generation prompt on {GENERATION_MODEL}", msg)
        self.assertIn("Google Gemini or OpenAI GPT-6 variant", msg)
        # One generation task per iteration with an empty pool, each sent once:
        # the filter is never retried, and nothing is waited out.
        self.assertEqual(sup.iteration, STALLED_ITERATIONS_LIMIT)
        self.assertEqual(len(_generation_prompts(sup)), STALLED_ITERATIONS_LIMIT)
        self.assertEqual(clock.pauses, [])
        # No final overview was attempted for an empty pool.
        self.assertNotIn(AgentType.META_REVIEW, sup._agents)

    def test_persistent_timeouts_fail_the_run_after_three_iterations(self):
        clock = _Clock()

        class TimingOutChat(_Chat):
            def respond(self, prompt):
                clock.advance(settings.llm_timeout_seconds)
                raise ReadTimeoutError(endpoint_url="https://bedrock-runtime.example")

        with _bedrock(TimingOutChat), clock.installed():
            sup = _supervisor()
            with self.assertRaises(RunAbortedError) as ctx:
                _run(sup)
        msg = str(ctx.exception)
        self.assertIn("No hypotheses were produced (No LLM task succeeded in 3 iterations "
                      "in a row): the LLM calls timed out. Last error: LLMTimeoutError", msg)
        # Every call was retried by the client, so each stalled iteration took
        # (1 + llm_max_retries) x llm_timeout_seconds and the stall outlasted
        # the transient window by the third.
        attempts = 1 + settings.llm_max_retries
        self.assertEqual(sup.iteration, STALLED_ITERATIONS_LIMIT)
        self.assertEqual(len(_generation_prompts(sup)), STALLED_ITERATIONS_LIMIT * attempts)
        self.assertEqual(clock.pauses, [30, 60])

    def test_the_stall_window_counts_the_first_stalled_iteration(self):
        clock = _Clock()

        class SlowTimingOutChat(_Chat):
            def respond(self, prompt):
                clock.advance(100)
                raise ReadTimeoutError(endpoint_url="https://bedrock-runtime.example")

        # One 100 s attempt per call: 600 s from the start of the first stalled
        # iteration are reached in iteration 4 (100+30+100+60+100+120+100).
        with _bedrock(SlowTimingOutChat), clock.installed(), \
                mock.patch.object(settings, "llm_max_retries", 0):
            sup = _supervisor()
            with self.assertRaises(RunAbortedError):
                _run(sup)
        self.assertEqual(sup.iteration, 4)
        self.assertEqual(clock.pauses, [30, 60, 120])

    def test_brief_throttling_is_waited_out_before_the_run_fails(self):
        with _bedrock(_ThrottledChat), _Clock().installed() as clock:
            sup = _supervisor()
            with self.assertRaises(RunAbortedError) as ctx:
                _run(sup)
        msg = str(ctx.exception)
        self.assertIn("the LLM service was throttling or unavailable. Last error: RetryableError", msg)
        self.assertIn("ThrottlingException", msg)
        # Pauses double from 30 s up to 5 min; the run stops at the first
        # stalled iteration at least TRANSIENT_STALL_MIN_SECONDS into the stall.
        self.assertEqual(clock.pauses, [30, 60, 120, 240, 300])
        self.assertLess(sum(clock.pauses[:-1]), TRANSIENT_STALL_MIN_SECONDS)
        self.assertGreaterEqual(sum(clock.pauses), TRANSIENT_STALL_MIN_SECONDS)
        self.assertEqual(sup.iteration, 6)

    def test_a_bad_reply_right_after_throttling_does_not_cut_the_wait(self):
        class RecoveringBadlyChat(_Chat):
            """Throttled for two generation tasks, then answers in prose."""

            def respond(self, prompt):
                if len(self.prompts) <= 2 * (1 + settings.llm_max_retries):
                    return _ThrottledChat.respond(self, prompt)
                return _reply("I am unable to help with that request.")

        with _bedrock(_FilteredChat), _Clock().installed() as clock:
            sup = _supervisor()
            sup._get_agent(AgentType.GENERATION).llm_client.llm = RecoveringBadlyChat()
            with self.assertRaises(RunAbortedError) as ctx:
                _run(sup)
        # The prose replies after the outage keep the stall going but do not
        # end it at three iterations: the streak stays transient.
        self.assertTrue(sup._stall_transient)
        self.assertEqual(clock.pauses, [30, 60, 120, 240, 300])
        self.assertEqual(sup.iteration, 6)
        self.assertIn("the model's replies could not be used", str(ctx.exception))

    def test_a_run_that_ends_mid_stall_says_so_without_a_last_pause(self):
        with _bedrock(_ThrottledChat), _Clock().installed() as clock:
            sup = _supervisor()
            result = _run(sup, max_iterations=5, seed=2)
        # The 10 min window is not reached in 5 iterations, so max_iterations
        # ends the loop; no pause follows the last iteration.
        self.assertIn("Reason: max iterations reached", result)
        self.assertEqual(clock.pauses, [30, 60, 120, 240])
        self.assertEqual(
            sup.stall_warning,
            "The run ended while its LLM calls were failing: no LLM task succeeded in its "
            "last 5 iterations (the LLM service was throttling or unavailable).")

    def test_filter_blocks_after_a_cleared_outage_are_not_waited_out(self):
        class ThrottledThenAnswersThenFiltered(_Chat):
            def respond(self, prompt):
                attempts = 1 + settings.llm_max_retries
                if len(self.prompts) <= attempts:
                    return _ThrottledChat.respond(self, prompt)
                if len(self.prompts) == attempts + 1:
                    return _reply(HYPOTHESIS_JSON)
                return _FilteredChat.respond(self, prompt)

        with _bedrock(_FilteredChat), _Clock().installed() as clock:
            sup = _supervisor()
            sup._get_agent(AgentType.GENERATION).llm_client.llm = ThrottledThenAnswersThenFiltered()
            _run(sup)
        # Iteration 1 stalled on throttling and was waited out; iteration 2
        # produced a hypothesis; the new streak of filter blocks is not
        # transient, so it ends the loop at its third iteration with no pause.
        self.assertEqual(clock.pauses, [30])
        self.assertFalse(sup._stall_transient)
        self.assertEqual(sup.iteration, 2 + STALLED_ITERATIONS_LIMIT)
        self.assertIn("content filter", sup.stall_warning)

    def test_execute_starts_with_a_clean_stall_state(self):
        with _bedrock(_FilteredChat), _Clock().installed():
            sup = _supervisor()
            _run(sup, seed=2)
            self.assertIsNotNone(sup.stall_warning)
            # A second run on the same instance (as resume_from_checkpoint does)
            # must not inherit the first run's stall.
            _run(sup, max_iterations=0)
        self.assertEqual(sup._stalled_iterations, 0)
        self.assertIsNone(sup.stall_warning)

    def test_only_an_iteration_that_stalled_is_followed_by_a_pause(self):
        with _bedrock(_FilteredChat), _Clock().installed() as clock:
            sup = _supervisor()

            async def one_stall_then_idle(research_goal):
                # A transient stall, then passes with nothing to do (as when
                # the drain cap skips scheduling).
                if sup.iteration == 1:
                    sup._stalled_iterations = 1
                    sup._stall_transient = True
                    sup._stall_started_at = supervisor_module.datetime.now()
                    return True
                return False

            sup._execute_iteration = one_stall_then_idle
            _run(sup, max_iterations=4, seed=1)
        self.assertEqual(clock.pauses, [30])

    def test_throttling_that_clears_is_survived(self):
        class ClearingChat(_Chat):
            """Throttled for the first generation task's attempts, then answers."""

            def respond(self, prompt):
                if len(self.prompts) <= 1 + settings.llm_max_retries:
                    return _ThrottledChat.respond(self, prompt)
                return _reply(HYPOTHESIS_JSON)

        with _bedrock(_FilteredChat), _Clock().installed() as clock:
            sup = _supervisor()
            sup._get_agent(AgentType.GENERATION).llm_client.llm = ClearingChat()
            result = _run(sup, max_iterations=4)
            hypotheses = asyncio.run(sup.storage.get_hypotheses_by_goal(GOAL.id))
        self.assertIn("Supervisor completed after 4 iterations", result)
        self.assertGreater(len(hypotheses), 0)
        self.assertIsNone(sup.stall_warning)
        self.assertEqual(clock.pauses, [30])

    def test_replies_that_never_parse_fail_an_empty_run_after_three_iterations(self):
        with _bedrock(_UnparsableChat), _Clock().installed() as clock:
            sup = _supervisor()
            with self.assertRaises(RunAbortedError) as ctx:
                _run(sup)
        self.assertIn("No hypotheses were produced", str(ctx.exception))
        self.assertNotIsInstance(sup._last_task_error, LLMClientError)
        self.assertEqual(sup.iteration, STALLED_ITERATIONS_LIMIT)
        self.assertEqual(clock.pauses, [])

    def test_blocked_goal_parsing_fails_the_run_with_the_same_advice(self):
        with _bedrock(_FilteredChat):
            sup = SupervisorAgent(AsyncStorageAdapter())
            with self.assertRaises(RunAbortedError) as ctx:
                _run(sup)
        self.assertIn(f"content filter blocked the supervisor prompt on {SUPERVISOR_MODEL}",
                      str(ctx.exception))
        self.assertIn("Google Gemini or OpenAI GPT-6 variant", str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, ContentFilteredError)
        self.assertEqual(sup.iteration, 0)

    def test_stalled_run_with_hypotheses_ends_early_and_keeps_them(self):
        with _bedrock(_FilteredChat), _Clock().installed():
            sup = _supervisor()
            result = _run(sup, seed=2)
            hypotheses = asyncio.run(sup.storage.get_hypotheses_by_goal(GOAL.id))
            proximity_graph = asyncio.run(sup.storage.get_proximity_graph(GOAL.id))
        # Proximity ran every iteration and succeeded by swallowing its blocked
        # calls; that must not hide that every other task was blocked.
        self.assertIsNotNone(proximity_graph)
        self.assertIsInstance(sup._last_task_error, ContentFilteredError)
        self.assertIn("Reason: No LLM task succeeded in 3 iterations in a row", result)
        self.assertEqual(sup.iteration, STALLED_ITERATIONS_LIMIT)
        self.assertEqual(len(hypotheses), 2)
        self.assertEqual(sup.stall_warning,
                         "The run stopped early: no LLM task succeeded in 3 iterations in a "
                         "row (Bedrock's content filter blocked the prompts).")


class StallCount(unittest.TestCase):
    """_execute_iteration's bookkeeping, with each agent type's task outcome set."""

    def _iteration(self, outcomes, stalled_before=0, pool=0, transient_before=False,
                   last_error_before=None):
        with _bedrock(_FilteredChat):
            sup = SupervisorAgent(AsyncStorageAdapter())
        sup.iteration = 1
        sup._workflow_started_at = datetime.now()
        sup._max_execution_time_seconds = 3600
        sup._drain_iterations = 0
        sup._stalled_iterations = stalled_before
        sup._stall_transient = transient_before
        sup._last_task_error = last_error_before

        async def create(agent_type, research_goal):
            if agent_type not in outcomes:
                return None
            return AgentTask(id=generate_task_id(), agent_type=agent_type,
                             task_type="stub", priority=5, parameters={})

        async def execute(task, research_goal):
            if outcomes[task.agent_type] is not None:
                raise outcomes[task.agent_type]
            return {}

        async def go():
            for i in range(pool):
                await sup.storage.add_hypothesis(_hypothesis(i))
            sup.returned = await sup._execute_iteration(GOAL)

        sup._create_task_for_agent = create
        sup._execute_task = execute
        asyncio.run(go())
        return sup

    def test_an_iteration_where_every_task_fails_stalls(self):
        timeout = LLMTimeoutError("Bedrock ainvoke (reflection) timed out after 300s (attempt 4/4)")
        sup = self._iteration({AgentType.GENERATION: ContentFilteredError("blocked"),
                               AgentType.REFLECTION: timeout}, stalled_before=1, pool=1)
        self.assertEqual(sup._stalled_iterations, 2)
        self.assertTrue(sup._stall_transient)
        self.assertTrue(sup.returned)

    def test_a_filter_block_alone_is_not_transient(self):
        sup = self._iteration({AgentType.GENERATION: ContentFilteredError("blocked")})
        self.assertEqual(sup._stalled_iterations, 1)
        self.assertFalse(sup._stall_transient)
        self.assertIsNotNone(sup._stall_started_at)

    def test_a_transient_streak_stays_transient(self):
        sup = self._iteration({AgentType.GENERATION: ContentFilteredError("blocked")},
                              stalled_before=2, transient_before=True)
        self.assertEqual(sup._stalled_iterations, 3)
        self.assertTrue(sup._stall_transient)

    def test_the_stall_names_the_counted_error_not_a_later_parse_failure(self):
        # Gather order is phase order: the evolution parse failure comes last.
        blocked = ContentFilteredError("blocked")
        sup = self._iteration({AgentType.GENERATION: blocked,
                               AgentType.EVOLUTION: CoScientistError("Failed to parse")}, pool=1)
        self.assertEqual(sup._stalled_iterations, 1)
        self.assertIs(sup._last_task_error, blocked)

    def test_a_successful_llm_task_resets_the_count(self):
        sup = self._iteration({AgentType.GENERATION: ContentFilteredError("blocked"),
                               AgentType.REFLECTION: None}, stalled_before=2)
        self.assertEqual(sup._stalled_iterations, 0)

    def test_proximity_and_observation_review_successes_do_not_reset_it(self):
        sup = self._iteration({AgentType.GENERATION: ContentFilteredError("blocked"),
                               AgentType.PROXIMITY: None,
                               AgentType.OBSERVATION_REVIEW: None}, stalled_before=2)
        self.assertEqual(sup._stalled_iterations, 3)

    def test_a_reply_that_does_not_parse_neither_stalls_nor_resets_a_run_with_hypotheses(self):
        # The LLM call worked; a flaky JSON reply must not end a run that has
        # results, nor replace the error the open stall is about.
        timeout = LLMTimeoutError("timed out after 300s (attempt 4/4)")
        parse_error = CoScientistError("Failed to parse LLM response after 2 attempts")
        sup = self._iteration({AgentType.GENERATION: parse_error}, stalled_before=2, pool=1,
                              transient_before=True, last_error_before=timeout)
        self.assertEqual(sup._stalled_iterations, 2)
        self.assertIs(sup._last_task_error, timeout)
        self.assertFalse(sup.returned)

    def test_any_failure_stalls_a_run_without_hypotheses(self):
        sup = self._iteration({AgentType.GENERATION: CoScientistError("Failed to parse")})
        self.assertEqual(sup._stalled_iterations, 1)
        self.assertFalse(sup._stall_transient)

    def test_budget_exhaustion_is_not_a_stall(self):
        sup = self._iteration({AgentType.GENERATION: BudgetExceededError(50.1, 50.0)},
                              stalled_before=1)
        self.assertEqual(sup._stalled_iterations, 1)
        self.assertIsNone(sup._last_task_error)

    def test_an_iteration_without_tasks_leaves_the_count(self):
        sup = self._iteration({}, stalled_before=2)
        self.assertEqual(sup._stalled_iterations, 2)


class StallLimit(unittest.TestCase):
    def _limit_reached(self, stalled, transient, stalled_for):
        with _bedrock(_FilteredChat):
            sup = SupervisorAgent(AsyncStorageAdapter())
        sup._stalled_iterations = stalled
        sup._stall_transient = transient
        sup._stall_started_at = datetime.now() - timedelta(seconds=stalled_for)
        return sup._stall_limit_reached()

    def test_deterministic_failures_end_the_loop_at_the_limit(self):
        self.assertFalse(self._limit_reached(STALLED_ITERATIONS_LIMIT - 1, False, 0))
        self.assertTrue(self._limit_reached(STALLED_ITERATIONS_LIMIT, False, 0))

    def test_transient_failures_also_need_the_minimum_stall_time(self):
        self.assertFalse(self._limit_reached(5, True, TRANSIENT_STALL_MIN_SECONDS - 5))
        self.assertTrue(self._limit_reached(STALLED_ITERATIONS_LIMIT, True,
                                            TRANSIENT_STALL_MIN_SECONDS + 5))


class FailureReason(unittest.TestCase):
    def _reason(self, err, terminal_reason=None):
        with _bedrock(_FilteredChat):
            sup = SupervisorAgent(AsyncStorageAdapter())
        sup._last_task_error = err
        return sup._no_hypotheses_reason(terminal_reason)

    def test_a_non_claude_block_suggests_gemini_only(self):
        msg = self._reason(ContentFilteredError("blocked", agent="generation",
                                                model="openai.gpt-6-astra"))
        self.assertIn("blocked the generation prompt on openai.gpt-6-astra", msg)
        self.assertIn("Resubmit with the Google Gemini variant,", msg)

    def test_a_block_without_model_details_still_reads(self):
        msg = self._reason(ContentFilteredError("blocked"))
        self.assertIn("blocked the LLM prompt on the selected model", msg)

    def test_other_failures_give_the_reason_the_cause_and_the_last_error(self):
        msg = self._reason(LLMClientError("Bedrock invocation failed: AccessDeniedException"),
                           "No LLM task succeeded in 3 iterations in a row")
        self.assertEqual(msg, "No hypotheses were produced (No LLM task succeeded in 3 "
                              "iterations in a row): the LLM calls failed. Last error: "
                              "LLMClientError: Bedrock invocation failed: AccessDeniedException")
        self.assertEqual(self._reason(None), "No hypotheses were produced (max iterations reached).")

    def test_a_code_fault_is_not_blamed_on_the_model(self):
        reason = "No LLM task succeeded in 3 iterations in a row"
        self.assertIn("): a task failed. Last error: AttributeError",
                      self._reason(AttributeError("'NoneType' object has no attribute 'x'"), reason))
        self.assertIn("): the model's replies could not be used. Last error: JSONDecodeError",
                      self._reason(json.JSONDecodeError("Expecting value", "", 0), reason))


class FinalOverview(unittest.TestCase):
    def _overview_calls(self, error):
        with _bedrock(_FilteredChat):
            sup = SupervisorAgent(AsyncStorageAdapter())
        # A supported candidate is necessary to reach the model-call/retry path.
        # Recommendation rejection is covered separately by readiness tests.
        async def prepare():
            h = _hypothesis(0)
            h.literature_citations = [Citation(title="Source",doi="10.9999/source",relevance="r",
                                               verification_status="verified")]
            await sup.storage.add_hypothesis(h)
            for kind in (ReviewType.FULL, ReviewType.DEEP_VERIFICATION):
                await sup.storage.add_review(Review(id=kind.value,hypothesis_id=h.id,
                    review_type=kind,passed=True,rationale="Supported"))
            obs = Observation(id="obs",paper_id="10.9999/source",paper_title="Source",
                observation_type=ObservationType.EXPERIMENTAL,text="Result",context="Source context")
            exp = ObservationExplanation(observation_id="obs",hypothesis_id=h.id,
                explains=True,explanation_score=1,reasoning="Consistent")
            await sup.storage.add_observation_review(ObservationReviewScore(id="obs_review",
                hypothesis_id=h.id,research_goal_id=GOAL.id,observations=[obs],explanations=[exp],
                overall_score=1,observations_total_count=1,observations_explained_count=1,summary="Reviewed"))
        asyncio.run(prepare())
        agent = mock.Mock()
        agent.generate_research_overview.side_effect = error
        sup._agents[AgentType.META_REVIEW] = agent
        sup.storage.get_meta_review = mock.AsyncMock(return_value=mock.Mock())
        self.assertIsNone(asyncio.run(sup._generate_final_overview(GOAL)))
        return agent.generate_research_overview.call_count

    def test_a_filtered_overview_is_not_retried(self):
        self.assertEqual(self._overview_calls(ContentFilteredError("blocked")), 1)

    def test_a_timed_out_overview_is_not_retried(self):
        # The client already made 1 + llm_max_retries attempts.
        self.assertEqual(self._overview_calls(LLMTimeoutError("timed out after 300s")), 1)

    def test_run_deadline_does_not_retry_the_final_overview(self):
        self.assertEqual(self._overview_calls(RunTimeLimitError("Run time limit reached")),1)

    def test_an_over_budget_overview_is_not_retried(self):
        # Raised after the call returned: a retry would be billed and discarded.
        self.assertEqual(self._overview_calls(BudgetExceededError(50.1, 50.0)), 1)

    def test_no_overview_is_attempted_with_the_budget_spent(self):
        with _bedrock(_FilteredChat):
            sup = SupervisorAgent(AsyncStorageAdapter())
        agent = mock.Mock()
        sup._agents[AgentType.META_REVIEW] = agent
        sup.cost_tracker = mock.Mock()
        sup.cost_tracker.check_budget.side_effect = BudgetExceededError(50.1, 50.0)
        self.assertIsNone(asyncio.run(sup._generate_final_overview(GOAL)))
        agent.generate_research_overview.assert_not_called()
        agent.execute.assert_not_called()

    def test_failed_finalization_does_not_keep_stale_recommendations(self):
        with _bedrock(_FilteredChat):
            sup=SupervisorAgent(AsyncStorageAdapter())
        old=ResearchOverview(id='old',research_goal_id=GOAL.id,
            executive_summary='Stale recommendation from an earlier review state',current_knowledge_boundary='Old state')
        asyncio.run(sup.storage.save_research_overview(old))
        sup.cost_tracker=mock.Mock()
        sup.cost_tracker.check_budget.side_effect=BudgetExceededError(50.1,50)
        asyncio.run(sup._generate_final_overview(GOAL))
        self.assertIsNone(asyncio.run(sup.storage.get_research_overview(GOAL.id)))

    def test_throttling_and_other_errors_are_still_retried(self):
        self.assertEqual(self._overview_calls(LLMRateLimitError("429 Too many requests")), 3)
        self.assertEqual(self._overview_calls(RetryableError("503 Service unavailable")), 3)
        self.assertEqual(self._overview_calls(RuntimeError("generator didn't stop after throw()")), 3)


# The AWS worker entrypoint belongs to the private deployment and is not in this repository.
ENTRYPOINT = ROOT / "scripts" / "aws_entrypoint.py"
NEEDS_ENTRYPOINT = unittest.skipUnless(ENTRYPOINT.exists(), "needs scripts/aws_entrypoint.py (private deployment worker)")


def _load_entrypoint():
    spec = importlib.util.spec_from_file_location(
        "aws_entrypoint_under_test", ENTRYPOINT)
    entrypoint = importlib.util.module_from_spec(spec)
    # Its module-level boto3 clients would otherwise look for credentials,
    # down to the EC2 metadata endpoint.
    with mock.patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
                                      "AWS_EC2_METADATA_DISABLED": "true"}):
        spec.loader.exec_module(entrypoint)
    return entrypoint


@NEEDS_ENTRYPOINT
class Entrypoint(unittest.TestCase):
    ENV = {"RUN_ID": "run-abort-test", "S3_BUCKET": "bucket", "INPUT_KEY": "in.yaml",
           "OUTPUT_PREFIX": "out", "USER_EMAIL": "user@example.org", "RUN_TABLE": "runs",
           "USER_ID": "", "BUDGET_AUD_RESERVED": "50"}

    def _main(self, supervisor_cls, env=None, report_renders=True,
              input_yaml=b"goals:\n  - description: PET\n"):
        entrypoint = _load_entrypoint()

        def render(json_path):
            if report_renders:
                Path(json_path).with_suffix(".html").write_text("<html>report</html>")

        # The report generator is patched out: it asks an LLM to label themes.
        with mock.patch.dict(os.environ, {**self.ENV, **(env or {})}), \
                mock.patch.object(entrypoint, "_ddb") as ddb, \
                mock.patch.object(entrypoint, "_s3") as s3, \
                mock.patch.object(entrypoint, "_ses") as ses, \
                mock.patch.object(supervisor_module, "SupervisorAgent", supervisor_cls), \
                mock.patch.object(html_report, "generate_html_report", side_effect=render), \
                mock.patch.object(settings, "budget_aud", settings.budget_aud), \
                mock.patch.object(settings, "enable_evolution", settings.enable_evolution), \
                mock.patch.object(settings, "enable_web_search", settings.enable_web_search), \
                mock.patch.object(settings, "enable_refutation_search",
                                  settings.enable_refutation_search), \
                mock.patch("traceback.print_exc"):
            s3.get_object.return_value = {"Body": io.BytesIO(input_yaml)}
            code = entrypoint.main()
            self.settings_seen = {k: getattr(settings, k) for k in (
                "enable_evolution", "enable_web_search", "enable_refutation_search")}
        self.addCleanup(lambda: [p.unlink(missing_ok=True) for p in
                                 Path("/tmp/run_outputs").glob(f"run_{self.ENV['RUN_ID']}.*")])
        return code, ddb, s3, ses

    def test_generic_failure_preserves_partial_work_and_estimated_cost(self):
        class BrokenSupervisor:
            def __init__(self,storage):
                self.storage=storage

            async def execute(self,goal,max_iterations,**kwargs):
                await self.storage.add_hypothesis(_hypothesis(0,goal.id))
                raise RuntimeError('Failure after partial work')

        tracker=mock.Mock()
        tracker.get_summary.return_value={'total_cost_aud':3.5,'total_cost_usd':2.25}
        with mock.patch.object(cost_tracker,'get_tracker',return_value=tracker):
            code,ddb,s3,ses=self._main(BrokenSupervisor)
        self.assertEqual(code,1)
        values=ddb.update_item.call_args_list[-1].kwargs['ExpressionAttributeValues']
        self.assertIn(':v_cost_aud',values)
        self.assertEqual(values[':v_cost_aud']['N'],'3.5')
        outputs=[json.loads(c.kwargs['Body']) for c in s3.put_object.call_args_list
                 if c.kwargs.get('Key','').endswith('/output/run.json')]
        self.assertEqual(len(outputs),1,'Partial scientific work must survive an execution error')
        self.assertEqual(outputs[0]['total_hypotheses'],1)
        self.assertEqual(outputs[0]['scientific_status'],'partial')

    def test_an_aborted_run_is_failed_with_the_reason_its_cost_and_no_success_email(self):
        reason = ("No hypotheses were produced: Bedrock's content filter blocked the "
                  "generation prompt on anthropic.claude-opus-4-8.")

        class AbortingSupervisor:
            def __init__(self, storage):
                pass

            async def execute(self, goal, max_iterations, **kwargs):
                raise RunAbortedError(reason)

        tracker = mock.Mock()
        tracker.get_summary.return_value = {"total_cost_aud": 3.5, "total_cost_usd": 2.25}
        with mock.patch.object(cost_tracker, "get_tracker", return_value=tracker):
            code, ddb, s3, ses = self._main(AbortingSupervisor, env={"USER_ID": "user-1"})
        self.assertEqual(code, 1)

        updates = [c.kwargs["ExpressionAttributeValues"] for c in ddb.update_item.call_args_list]
        statuses = [u[":ns"]["S"] for u in updates if ":ns" in u]
        self.assertEqual(statuses, ["running", "failed"])
        failed = next(u for u in updates if u.get(":ns", {}).get("S") == "failed")
        # Stored without the exception's type name: the run page shows it as is.
        self.assertEqual(failed[":v_error_message"]["S"], reason)
        self.assertEqual(failed[":v_cost_aud"]["N"], "3.5")
        # The spend counts against the user's daily budget; the rest is released.
        release = next(u for u in updates if ":release" in u)
        self.assertEqual(float(release[":release"]["N"]), -46.5)
        subjects = [c.kwargs["Content"]["Simple"]["Subject"]["Data"]
                    for c in ses.send_email.call_args_list]
        self.assertEqual(len(subjects), 1)
        self.assertIn("Your run failed", subjects[0])
        output = next(json.loads(c.kwargs["Body"]) for c in s3.put_object.call_args_list
                      if c.kwargs.get("Key", "").endswith("/output/run.json"))
        self.assertEqual(output["execution_status"], "failed")
        self.assertEqual(output["scientific_status"], "partial")
        self.assertEqual(output["total_hypotheses"], 0)

    def test_a_completed_run_with_a_stall_warning_says_so(self):
        stall_warning = ("The run stopped early: no LLM task succeeded in 3 iterations in a "
                         "row (Bedrock's content filter blocked the prompts).")

        class StoppedEarlySupervisor:
            def __init__(self, storage):
                self.storage = storage
                self.stall_warning = stall_warning

            async def execute(self, goal, max_iterations, **kwargs):
                await self.storage.add_hypothesis(_hypothesis(0, goal.id))
                return "Supervisor completed after 3 iterations."

        code, ddb, s3, ses = self._main(StoppedEarlySupervisor)
        self.assertEqual(code, 0)
        # The stall, then what the result lacks: no overview, an unreviewed leader
        expected = (f"{stall_warning} No research overview was produced. The highest-ranked "
                    f"hypothesis has no review, so its rank rests on tournament matches alone. "
                    f"The report covers what was produced: 1 hypothesis, "
                    f"0 reviews and 0 tournament matches.")
        complete = ddb.update_item.call_args_list[-1].kwargs["ExpressionAttributeValues"]
        self.assertEqual(complete[":ns"]["S"], "complete")
        self.assertEqual(complete[":v_warning_message"]["S"], expected)
        email = ses.send_email.call_args.kwargs["Content"]["Simple"]
        self.assertIn("Your run finished with a warning", email["Subject"]["Data"])
        self.assertIn(expected, email["Body"]["Text"]["Data"])
        # The report (run.json feeds report.html) and status.json carry it too.
        uploads = {c.kwargs["Key"]: c.kwargs["Body"] for c in s3.put_object.call_args_list}
        self.assertEqual(json.loads(uploads["out/output/run.json"])["warning"], expected)
        self.assertEqual(json.loads(uploads["out/metadata/status.json"])["warning"], expected)


class ReportWarning(unittest.TestCase):
    def _render(self, warning):
        run = {"goal": GOAL.model_dump(mode="json"), "run_timestamp": "2026-10-20T00:00:00",
               "hypotheses": [_hypothesis(0).model_dump(mode="json")], "reviews": [],
               "matches": [], "context_memory": {}, "warning": warning}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(html_report, "_derive_themes_via_llm", return_value=None):
            path = Path(tmp) / "run.json"
            path.write_text(json.dumps(run))
            return Path(html_report.generate_html_report(str(path))).read_text()

    def test_the_report_shows_the_warning_escaped(self):
        page = self._render("The run stopped early: <filter> & co.")
        self.assertIn('<div class="run-warning">The run stopped early: &lt;filter&gt; &amp; co.</div>',
                      page)

    def test_a_report_without_a_warning_has_no_banner(self):
        self.assertNotIn('class="run-warning"', self._render(None))


class RetryClassification(unittest.TestCase):
    def test_classify_error_keeps_content_filtered_error(self):
        # A date-stamped model ID contains "429"; the filter is not a rate limit.
        for text in ("blocked on anthropic.claude-x-20250429-v1:0", "blocked after timeout"):
            err = ContentFilteredError(text, agent="generation", model="anthropic.claude-x")
            self.assertIs(classify_error(err), err)


if __name__ == "__main__":
    unittest.main()
