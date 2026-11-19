"""AWS Bedrock client with cost tracking, retry logic, and timeouts.

Wraps langchain_aws.ChatBedrockConverse so AGF can route Anthropic Claude,
OpenAI GPT-6 and Moonshot Kimi calls through Bedrock instead of
provider-specific APIs.

Auth: IAM (the ECS task role grants bedrock:InvokeModel*). No API key needed.

Routing: every model the AGF website offers is INFERENCE_PROFILE-only on
Bedrock, so a bare foundation-model ID cannot be invoked. Each call goes to
that model's own Application Inference Profile, looked up by foundation-model
ID in the BEDROCK_INFERENCE_PROFILE_ARNS JSON map that the task definition
sets, so spend attributes per tool in Cost Explorer / CUR. A model missing
from the map falls back to its system inference profile in _SYSTEM_PROFILES.
"""

import json
import os
import sys
from contextlib import contextmanager
import boto3
from botocore.client import BaseClient

from botocore.config import Config
from langchain_aws import ChatBedrockConverse

from src.llm.base import BaseLLMClient
from src.config import settings
from src.utils.errors import ContentFilteredError, LLMClientError, RunTimeLimitError
from src.utils.retry import retry_async, sync_retry
from src.observability.tracing import trace_llm_call
import structlog

sys.path.append(str(settings.project_root / "04_Scripts"))
from cost_tracker import get_tracker, BudgetExceededError

logger = structlog.get_logger()


# System inference profile per foundation model, used when the task definition
# provides no Application Inference Profile for it (e.g. local runs). au.* keeps
# Claude inside Australia; GPT-6 and Kimi K3 are only offered through global.*
# from ap-southeast-2 (list-inference-profiles, 2026-10-16).
_SYSTEM_PROFILES = {
    "anthropic.claude-opus-4-8": "au.anthropic.claude-opus-4-8",
    "anthropic.claude-sonnet-5": "au.anthropic.claude-sonnet-5",
    "openai.gpt-6-astra": "global.openai.gpt-6-astra",
    "openai.gpt-6-luna": "global.openai.gpt-6-luna",
    "moonshotai.kimi-k3": "global.moonshotai.kimi-k3",
}

# Shared by reasoning and the answer: Claude's adaptive thinking, GPT-6 and
# Kimi K3 all spend output tokens on reasoning (Kimi K3 used up to ~8.7k on one
# generation prompt), so 8192 left long hypotheses too little room.
_MAX_OUTPUT_TOKENS = 16384

# Per-attempt wait for one Converse call. Converse is non-streaming, so the
# whole answer must be generated within it: at the measured ~43-49 output
# tokens/s, GPT-6 Astra and Kimi K3 need ~330-380 s to fill the 16384 cap, and
# one sampled Kimi K3 call took 307 s, over the 300 s default. Applied to both
# the botocore read timeout and the asyncio per-attempt timeout so they move
# together.
_MIN_BEDROCK_TIMEOUT_SECONDS = 900


def _resolve_target(model: str) -> tuple[str, str]:
    """Map a foundation-model ID to (ID or ARN to invoke, provider).

    langchain_aws cannot infer the provider from an ARN, so it is taken from
    the foundation-model ID ("openai.gpt-6-astra" -> "openai").
    """
    profiles = json.loads(os.environ.get("BEDROCK_INFERENCE_PROFILE_ARNS") or "{}")
    target = profiles.get(model) or _SYSTEM_PROFILES.get(model, model)
    if model not in profiles and os.environ.get("ECS_CONTAINER_METADATA_URI_V4"):
        # In ECS every offered model should have its own tagged profile; a miss
        # (e.g. a task definition revision without the map) still runs, but
        # untagged, so the spend drops out of per-tool attribution.
        logger.warning("bedrock_profile_missing", model=model, fallback=target)
    return target, model.split(".", 1)[0]


class BedrockClient(BaseLLMClient):
    """Bedrock chat client (Converse API) with cost tracking and retries.

    Same interface as GoogleGeminiClient / OpenAIClient. Token usage is
    extracted from response.usage_metadata, which langchain_aws populates
    consistently for all Bedrock model providers.
    """

    def __init__(self, model: str, agent_name: str, thinking_budget: int | None = None):
        cost_tracker = get_tracker(budget_aud=settings.budget_aud)
        super().__init__(model, cost_tracker)

        self.agent_name = agent_name
        self.region = os.environ.get("BEDROCK_REGION") or getattr(
            settings, "bedrock_region", "ap-southeast-2"
        )

        # Each model invokes through its own profile, so the model the user
        # picked is the model that runs and the model the cost tracker prices.
        self.model_id, provider = _resolve_target(model)
        self.max_tokens = _MAX_OUTPUT_TOKENS

        # Converse is non-streaming: nothing arrives until the whole answer,
        # reasoning included, is generated, so botocore's 60 s default read
        # timeout cut long generations off. botocore's own retries are off
        # (total_max_attempts=1; "max_attempts" counts RETRIES, so 1 still
        # meant 2 requests), leaving sync_retry / retry_async as the only retry
        # layer. read_timeout matches the per-attempt asyncio timeout so an
        # abandoned call does not keep running.
        self.timeout = max(settings.llm_timeout_seconds, _MIN_BEDROCK_TIMEOUT_SECONDS)
        botocore_config = Config(
            connect_timeout=10,
            read_timeout=self.timeout,
            retries={"mode": "standard", "total_max_attempts": 1},
        )

        # Thinking off where the agent's budget is 0 (ranking, proximity,
        # safety), mirroring the Gemini budgets; these are the highest-volume
        # calls. Opus 4.8 and Sonnet 5 accept {"type": "disabled"}.
        extra = None
        if thinking_budget == 0 and model.startswith("anthropic."):
            extra = {"thinking": {"type": "disabled"}}

        # No temperature: Claude Opus 4.8 / Sonnet 5, GPT-6 and Kimi K3 all
        # reject the field with a ValidationException (verified 2026-10-16).
        # base_model_id: without it langchain_aws resolves an application
        # profile ARN through bedrock:GetInferenceProfile at construction,
        # which the task role does not grant.
        self.llm = ChatBedrockConverse(
            model=self.model_id,
            provider=provider,
            base_model_id=model,
            region_name=self.region,
            max_tokens=self.max_tokens,
            config=botocore_config,
            additional_model_request_fields=extra,
            callbacks=self.callbacks,
        )

        logger.info(
            "bedrock_client_initialized",
            model=model,
            resolved_model_id=self.model_id,
            region=self.region,
            agent=agent_name,
            via_application_profile=self.model_id.startswith("arn:"),
            max_tokens=self.max_tokens,
            thinking_disabled=extra is not None,
            timeout=self.timeout,
        )

    @staticmethod
    def _extract_text(content) -> str:
        """Flatten langchain_aws response.content into a plain string.

        Reasoning-capable Bedrock models (Kimi K3, GPT-6, Claude with
        adaptive thinking) return content as a list of typed blocks instead
        of a single string, e.g.
        ``[{'type': 'reasoning_content', 'reasoning_content': {'text': '...'}},
        {'type': 'text', 'text': '<answer>'}]``. Calling ``str()`` on that
        list yields the Python repr, which breaks downstream ``json.loads``.
        We keep ``text`` blocks (the actual answer) and drop
        ``reasoning_content`` / ``thinking`` blocks (the model's internal
        scratchpad). Plain-string content passes through unchanged.
        """
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for blk in content:
                if isinstance(blk, str):
                    parts.append(blk)
                    continue
                if not isinstance(blk, dict):
                    continue
                btype = blk.get("type")
                if btype in ("reasoning_content", "thinking", "tool_use"):
                    continue
                if btype == "text" and "text" in blk:
                    parts.append(blk["text"])
                elif "text" in blk:
                    parts.append(blk["text"])
            return "".join(parts)
        return str(content)

    def _estimate_tokens(self, text: str) -> int:
        return int(len(text.split()) * 1.5)

    def _extract_usage(self, response, prompt: str, content: str) -> tuple[int, int]:
        """Pull (input_tokens, output_tokens) from langchain_aws response."""
        usage = getattr(response, "usage_metadata", None)
        if isinstance(usage, dict):
            in_tok = self._usage_value(usage, "input_tokens", "prompt_tokens")
            out_tok = self._usage_value(usage, "output_tokens", "completion_tokens")
            if in_tok is not None and out_tok is not None:
                return int(in_tok), int(out_tok)

        meta = getattr(response, "response_metadata", None) or {}
        if isinstance(meta, dict):
            tu = meta.get("usage") or meta.get("token_usage") or {}
            if isinstance(tu, dict):
                in_tok = self._usage_value(tu, "input_tokens", "prompt_tokens")
                out_tok = self._usage_value(tu, "output_tokens", "completion_tokens")
                if in_tok is not None and out_tok is not None:
                    return int(in_tok), int(out_tok)

        return self._estimate_tokens(prompt), self._estimate_tokens(content)

    def _check_filtered(self, response, record_usage: bool = True) -> None:
        """Raise instead of returning the filter's empty output, which would
        otherwise surface downstream as an unrelated parse error. Warn when
        the answer was cut off by the output cap."""
        meta = getattr(response, "response_metadata", None) or {}
        stop = meta.get("stopReason")
        if stop == "content_filtered":
            # Bedrock still bills the input tokens of a filtered request. Read
            # usage_metadata directly: _extract_usage treats the 0 output tokens
            # as missing and falls back to an estimate of 0.
            usage = getattr(response, "usage_metadata", None) or {}
            if record_usage:
                self.cost_tracker.check_and_add_usage(
                    agent=self.agent_name, model=self.model,
                    input_tokens=int(usage.get("input_tokens") or 0),
                    output_tokens=int(usage.get("output_tokens") or 0),
                )
            raise ContentFilteredError(
                f"Bedrock safety filter blocked the {self.agent_name} prompt on "
                f"{self.model} (stopReason=content_filtered)",
                agent=self.agent_name,
                model=self.model,
            )
        if stop == "max_tokens":
            logger.warning(
                "bedrock_output_truncated",
                agent=self.agent_name,
                model=self.model,
                max_tokens=self.max_tokens,
            )

    @contextmanager
    def _request_model(self):
        timeout = self._request_timeout(self.timeout)
        client = getattr(self.llm, "client", None)
        if isinstance(client, BaseClient) and timeout < self.timeout:
            # Converse uses a synchronous transport even from ainvoke. Bound its
            # connection/read waits as well as the coroutine, without mutating a
            # client shared by concurrent requests.
            connect = min(10.0, timeout / 10)
            config = client.meta.config.merge(Config(connect_timeout=max(0.001, connect),
                read_timeout=max(0.001, timeout - connect)))
            bounded = boto3.client("bedrock-runtime", region_name=self.region, config=config)
            try:
                yield self.llm.model_copy(update={"client": bounded})
            finally:
                bounded.close()
        else:
            yield self.llm

    def _do_invoke(self, prompt: str):
        with self._budgeted_request(prompt, self.max_tokens) as reservation:
            with self._request_model() as model:
                response = model.invoke(prompt)
            content = self._extract_text(response.content)
            self._settle_response(reservation, response, prompt, content)
            self._check_filtered(response, record_usage=False)
            return content, response

    async def _do_ainvoke(self, prompt: str):
        with self._budgeted_request(prompt, self.max_tokens) as reservation:
            with self._request_model() as model:
                response = await model.ainvoke(prompt)
            content = self._extract_text(response.content)
            self._settle_response(reservation, response, prompt, content)
            self._check_filtered(response, record_usage=False)
            return content, response

    def invoke(self, prompt: str) -> str:
        try:
            # Refused before the call once the spend limit is reached
            self.cost_tracker.ensure_budget_available()
            content, response = sync_retry(
                self._do_invoke,
                prompt,
                operation_name=f"Bedrock invoke ({self.agent_name})",
                remaining_time=self.cost_tracker.remaining_run_seconds,
            )
            in_tok, out_tok = self._extract_usage(response, prompt, content)
            logger.debug(
                "bedrock_invoke_success",
                agent=self.agent_name,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )
            return content
        except (BudgetExceededError, RunTimeLimitError):
            raise
        except Exception as e:
            logger.error(
                "bedrock_invoke_failed",
                agent=self.agent_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            if isinstance(e, LLMClientError):
                raise
            raise LLMClientError(f"Bedrock invocation failed: {e}") from e

    @trace_llm_call("bedrock", "converse")
    async def ainvoke(self, prompt: str) -> str:
        try:
            # Refused before the call once the spend limit is reached
            self.cost_tracker.ensure_budget_available()
            content, response = await self._within_run_time(retry_async(
                self._do_ainvoke,
                prompt,
                timeout=self.timeout,
                operation_name=f"Bedrock ainvoke ({self.agent_name})",
            ))
            in_tok, out_tok = self._extract_usage(response, prompt, content)
            logger.debug(
                "bedrock_ainvoke_success",
                agent=self.agent_name,
                input_tokens=in_tok,
                output_tokens=out_tok,
            )
            return content
        except (BudgetExceededError, RunTimeLimitError):
            raise
        except Exception as e:
            logger.error(
                "bedrock_ainvoke_failed",
                agent=self.agent_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            if isinstance(e, LLMClientError):
                raise
            raise LLMClientError(f"Bedrock async invocation failed: {e}") from e
