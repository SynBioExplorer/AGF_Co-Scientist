"""Routing, parameters and pricing for the models the AGF website offers.

Stdlib unittest because pytest is not installed in the deploy image. The
Dockerfile copies neither tests/ nor cloudformation/, so mount both from the
source tree. buildspec.yml does this after building the image, with a runner
that also fails when no test runs (none discovered, or all skipped); by hand:
    docker run --rm -v "$PWD/tests:/app/tests:ro" \
        -v "$PWD/cloudformation:/app/cloudformation:ro" --entrypoint python <image> \
        -m unittest discover -s /app/tests -v

In the public repository cloudformation/ and buildspec.yml are not included, so the two
tests that read the stack template are skipped.
"""
import asyncio
import json
import os
import re
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "04_Scripts"))
# Settings requires a Google key at import time; these tests never call Google.
os.environ.setdefault("GOOGLE_API_KEY", "unit-test-placeholder")

import boto3  # noqa: E402
from botocore.exceptions import (  # noqa: E402
    ClientError, ConnectionClosedError, ConnectTimeoutError, EndpointConnectionError,
    HTTPClientError, ProxyConnectionError, ReadTimeoutError, ResponseStreamingError,
    SSLError,
)

from cost_tracker import CostTracker, GEMINI_PROMOTIONS, MODEL_PRICING, gemini_rate  # noqa: E402
from src.config import settings  # noqa: E402
from src.llm import bedrock, google  # noqa: E402
from src.utils.errors import RetryableError  # noqa: E402
from src.utils.retry import classify_error, is_retryable_error  # noqa: E402

# Every model the website catalog offers (05_Website co-scientist page + route).
BEDROCK_MODELS = [
    "anthropic.claude-opus-4-8",
    "anthropic.claude-sonnet-5",
    "openai.gpt-6-astra",
    "openai.gpt-6-luna",
    "moonshotai.kimi-k3",
]
GOOGLE_MODELS = ["gemini-4-argon", "gemini-3.8-flash"]
AGENTS = ["generation", "reflection", "ranking", "evolution", "meta_review", "supervisor"]
# The stack template belongs to the private deployment and is not in this repository.
_TEMPLATE_PATH = ROOT / "cloudformation" / "agf-coscientist-stack.yaml"
TEMPLATE = _TEMPLATE_PATH.read_text() if _TEMPLATE_PATH.exists() else None
_NEEDS_TEMPLATE = unittest.skipIf(TEMPLATE is None, "needs the private CloudFormation stack template")


def _template_profile_map() -> dict:
    """The BEDROCK_INFERENCE_PROFILE_ARNS JSON the stack builds, values = ${Var} names."""
    raw = re.search(r"'(\{\"anthropic\.claude-opus-4-8\".*?\})'", TEMPLATE).group(1)
    return json.loads(re.sub(r"\$\{(\w+)\}", r"\1", raw))


def _client(model, agent="generation", thinking_budget=None, env=None):
    with mock.patch.dict(os.environ, env or {}), \
            mock.patch.object(bedrock, "ChatBedrockConverse") as chat:
        client = bedrock.BedrockClient(model, agent, thinking_budget=thinking_budget)
    return client, chat.call_args.kwargs


class ResolveTarget(unittest.TestCase):
    def test_each_model_uses_its_own_application_profile(self):
        arns = {m: f"arn:aws:bedrock:ap-southeast-2:1:application-inference-profile/{i}"
                for i, m in enumerate(BEDROCK_MODELS)}
        with mock.patch.dict(os.environ, {"BEDROCK_INFERENCE_PROFILE_ARNS": json.dumps(arns)}):
            for m in BEDROCK_MODELS:
                target, provider = bedrock._resolve_target(m)
                self.assertEqual(target, arns[m])
                self.assertEqual(provider, m.split(".")[0])

    def test_falls_back_to_system_profile_without_map(self):
        with mock.patch.dict(os.environ, {"BEDROCK_INFERENCE_PROFILE_ARNS": "{}"}):
            self.assertEqual(bedrock._resolve_target("anthropic.claude-opus-4-8"),
                             ("au.anthropic.claude-opus-4-8", "anthropic"))
            self.assertEqual(bedrock._resolve_target("openai.gpt-6-luna"),
                             ("global.openai.gpt-6-luna", "openai"))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("BEDROCK_INFERENCE_PROFILE_ARNS", None)
            self.assertEqual(bedrock._resolve_target("moonshotai.kimi-k3"),
                             ("global.moonshotai.kimi-k3", "moonshotai"))

    def test_every_offered_model_has_a_system_profile(self):
        self.assertEqual(sorted(bedrock._SYSTEM_PROFILES), sorted(BEDROCK_MODELS))

    @_NEEDS_TEMPLATE
    def test_template_map_keys_match_the_code(self):
        self.assertEqual(sorted(_template_profile_map()), sorted(bedrock._SYSTEM_PROFILES))

    @_NEEDS_TEMPLATE
    def test_each_template_profile_copies_the_model_its_key_names(self):
        # A copy-paste slip (Sonnet's profile under the Opus key) would run one
        # model while the cost tracker prices another.
        for key, var in _template_profile_map().items():
            resource = re.search(rf"\b{var}: !GetAtt (\w+)\.InferenceProfileArn", TEMPLATE).group(1)
            block = TEMPLATE.split(f"\n  {resource}:\n", 1)[1].split("\n\n", 1)[0]
            source = re.search(r"inference-profile/([\w.-]+)'", block).group(1)
            self.assertTrue(source.endswith("." + key), (key, resource, source))


class ClientParameters(unittest.TestCase):
    def test_provider_set_and_temperature_omitted(self):
        arn = "arn:aws:bedrock:ap-southeast-2:1:application-inference-profile/x"
        client, kwargs = _client("openai.gpt-6-astra",
                                 env={"BEDROCK_INFERENCE_PROFILE_ARNS": json.dumps({"openai.gpt-6-astra": arn})})
        self.assertEqual(kwargs["model"], arn)
        self.assertEqual(kwargs["provider"], "openai")
        # Without base_model_id langchain_aws calls bedrock:GetInferenceProfile,
        # which the task role does not grant.
        self.assertEqual(kwargs["base_model_id"], "openai.gpt-6-astra")
        self.assertNotIn("temperature", kwargs)
        self.assertEqual(kwargs["max_tokens"], 16384)
        # The cost tracker must price the model that actually runs.
        self.assertEqual(client.model, "openai.gpt-6-astra")

    def test_botocore_makes_exactly_one_attempt(self):
        # Checked on a real client: in a retries dict, "max_attempts" counts
        # RETRIES, so max_attempts=1 still meant 2 requests per call.
        _, kwargs = _client("anthropic.claude-opus-4-8")
        real = boto3.client("bedrock-runtime", region_name="ap-southeast-2", config=kwargs["config"],
                            aws_access_key_id="x", aws_secret_access_key="x")
        self.assertEqual(real.meta.config.retries["total_max_attempts"], 1)

    def test_timeout_is_long_enough_for_a_full_answer_and_shared(self):
        client, kwargs = _client("moonshotai.kimi-k3")
        self.assertGreaterEqual(client.timeout, 900)
        self.assertGreaterEqual(client.timeout, settings.llm_timeout_seconds)
        # botocore read timeout and the asyncio per-attempt timeout move together.
        self.assertEqual(kwargs["config"].read_timeout, client.timeout)

    def test_async_attempt_timeout_is_the_same_value(self):
        # ainvoke runs the blocking call in an executor thread asyncio cannot
        # cancel, so only an equal read timeout bounds an abandoned attempt.
        fake = mock.AsyncMock(return_value=("t", mock.Mock(
            usage_metadata={"input_tokens": 1, "output_tokens": 1})))
        client, _ = _client("moonshotai.kimi-k3")
        client.cost_tracker = CostTracker()
        with mock.patch.object(bedrock, "retry_async", fake):
            asyncio.run(client.ainvoke("p"))
        self.assertEqual(fake.call_args.kwargs["timeout"], client.timeout)

    def test_claude_thinking_disabled_only_where_budget_is_zero(self):
        _, ranking = _client("anthropic.claude-sonnet-5", "ranking", thinking_budget=0)
        self.assertEqual(ranking["additional_model_request_fields"], {"thinking": {"type": "disabled"}})
        _, generation = _client("anthropic.claude-opus-4-8", "generation", thinking_budget=None)
        self.assertIsNone(generation["additional_model_request_fields"])
        _, reflection = _client("anthropic.claude-sonnet-5", "reflection", thinking_budget=512)
        self.assertIsNone(reflection["additional_model_request_fields"])
        _, luna = _client("openai.gpt-6-luna", "ranking", thinking_budget=0)
        self.assertIsNone(luna["additional_model_request_fields"])


class ContentFilter(unittest.TestCase):
    def test_filtered_response_raises_after_charging_input_tokens(self):
        client, _ = _client("anthropic.claude-opus-4-8")
        client.cost_tracker = mock.Mock()
        resp = mock.Mock(response_metadata={"stopReason": "content_filtered"}, content=[],
                         usage_metadata={"input_tokens": 30000, "output_tokens": 0})
        with self.assertRaises(bedrock.ContentFilteredError):
            client._check_filtered(resp)
        charged = client.cost_tracker.check_and_add_usage.call_args.kwargs
        self.assertEqual((charged["input_tokens"], charged["output_tokens"]), (30000, 0))
        self.assertEqual(charged["model"], "anthropic.claude-opus-4-8")

    def test_normal_response_passes(self):
        client, _ = _client("anthropic.claude-opus-4-8")
        client._check_filtered(mock.Mock(response_metadata={"stopReason": "end_turn"}, content="ok"))

    def test_filter_error_is_never_retried(self):
        # The filter is deterministic for a prompt; retrying only burns tokens.
        # Checked by type, so transient-sounding words in the text change nothing.
        for agent in AGENTS:
            for model in BEDROCK_MODELS:
                err = bedrock.ContentFilteredError(
                    f"Bedrock safety filter blocked the {agent} prompt on {model} "
                    "(stopReason=content_filtered)")
                self.assertFalse(is_retryable_error(err), (agent, model))
        self.assertFalse(is_retryable_error(
            bedrock.ContentFilteredError("500 connection reset timeout quota")))
        filtered = bedrock.ContentFilteredError("429 rate limit")
        self.assertIs(classify_error(filtered), filtered)


def _aws_error(code, message="x", status=None):
    response = {"Error": {"Code": code, "Message": message}}
    if status is not None:
        response["ResponseMetadata"] = {"HTTPStatusCode": status}
    return ClientError(response, "Converse")


class Retries(unittest.TestCase):
    def test_aws_transient_errors_are_retried_by_code(self):
        # botocore's own retries are off, so these must be caught here; the
        # substring checks alone missed all of them.
        for code, message in [("InternalServerException", "x"),
                              ("ServiceUnavailableException", "x"),
                              ("ThrottlingException", "Too many tokens, please wait"),
                              ("ModelTimeoutException", "x"),
                              ("ModelNotReadyException", "x")]:
            self.assertTrue(is_retryable_error(_aws_error(code, message)), code)

    def test_unmodelled_5xx_and_429_are_retried_by_status(self):
        # Without x-amzn-errortype botocore sets Code to the status string.
        # botocore's standard mode retried the 5xx whatever the code; 429 is
        # retried here in addition.
        for status in (429, 500, 502, 503, 504):
            err = ClientError({"Error": {"Code": str(status), "Message": ""},
                               "ResponseMetadata": {"HTTPStatusCode": status}}, "Converse")
            self.assertTrue(is_retryable_error(err), status)

    def test_connection_failures_are_retried(self):
        for err in (ConnectTimeoutError(endpoint_url="https://x"),
                    EndpointConnectionError(endpoint_url="https://x"),
                    ReadTimeoutError(endpoint_url="https://x"),
                    ConnectionClosedError(endpoint_url="https://x"),
                    SSLError(endpoint_url="https://x", error="handshake")):
            self.assertTrue(is_retryable_error(err), type(err).__name__)

    def test_http_client_errors_are_retried_by_class(self):
        # Messages without timeout, connection or 5xx wording, so the class
        # check and not the substring fallback must catch them.
        for err in (HTTPClientError(error="x"), ResponseStreamingError(error="x"),
                    ProxyConnectionError(proxy_url="http://p", error="x")):
            self.assertTrue(is_retryable_error(err), type(err).__name__)

    def test_aws_permanent_errors_are_not_retried(self):
        # Decided by code, so a message that merely mentions a timeout or a 500
        # does not make a validation or access error look transient.
        self.assertFalse(is_retryable_error(_aws_error("ValidationException", "read timeout is 500")))
        self.assertFalse(is_retryable_error(_aws_error("AccessDeniedException")))

    def test_permanent_aws_errors_keep_their_type(self):
        # "429" inside an ARN must not turn an access error into a rate limit.
        err = _aws_error("AccessDeniedException", "arn:aws:iam::429:role/x is not authorized")
        self.assertIs(classify_error(err), err)

    def test_permanent_errors_at_their_real_status_are_not_retried(self):
        # Real botocore errors carry ResponseMetadata, so the status rule must
        # not catch any of these either.
        for code, status in [("ValidationException", 400), ("AccessDeniedException", 403),
                             ("ResourceNotFoundException", 404),
                             ("ServiceQuotaExceededException", 400),
                             ("ModelErrorException", 424), ("400", 400), ("403", 403),
                             ("404", 404), ("408", 408), ("424", 424)]:
            err = _aws_error(code, status=status)
            self.assertFalse(is_retryable_error(err), (code, status))
            self.assertIs(classify_error(err), err, (code, status))

    def test_transient_aws_errors_are_labelled_retryable(self):
        for err in (_aws_error("ThrottlingException", "Too many tokens", status=429),
                    _aws_error("503", "", status=503)):
            self.assertIsInstance(classify_error(err), RetryableError)


class GeminiUsage(unittest.TestCase):
    def _usage(self, response):
        client = object.__new__(google.GoogleGeminiClient)
        return google.GoogleGeminiClient._extract_usage(client, response, "", "")

    def test_thinking_tokens_counted_once(self):
        # langchain-google-genai already folds thoughts into output_tokens and
        # repeats them in output_token_details.reasoning.
        resp = mock.Mock(usage_metadata={"input_tokens": 10, "output_tokens": 1000,
                                         "output_token_details": {"reasoning": 800}},
                         response_metadata={})
        self.assertEqual(self._usage(resp), (10, 1000))

    def test_raw_metadata_fallback_adds_thoughts(self):
        # Google's raw candidates_token_count excludes thoughts.
        resp = mock.Mock(usage_metadata=None,
                         response_metadata={"usage_metadata": {"prompt_token_count": 10,
                                                               "candidates_token_count": 200,
                                                               "thoughts_token_count": 800}})
        self.assertEqual(self._usage(resp), (10, 1000))


class Pricing(unittest.TestCase):
    def test_every_offered_model_has_a_price_row(self):
        # A missing row falls back to $1/$4 per MTok, far below Opus 4.8 or GPT-6 Astra.
        for m in BEDROCK_MODELS + GOOGLE_MODELS:
            self.assertIn(m, MODEL_PRICING, m)

    def test_gemini_promotional_rate_until_its_last_day_then_full(self):
        for model, (last_day, promo, full) in GEMINI_PROMOTIONS.items():
            self.assertEqual(gemini_rate(model, last_day), promo, model)
            self.assertEqual(gemini_rate(model, date.fromordinal(last_day.toordinal() + 1)), full, model)
            self.assertEqual(full["input"], 2 * promo["input"], model)


if __name__ == "__main__":
    unittest.main()
