"""
Cost Tracker for AI Co-Scientist

Tracks token usage and costs per agent, with a hard budget limit.
Raises BudgetExceededError when the budget is exhausted.
"""

import json
import os
import logging
import math
import uuid
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from threading import RLock

logger = logging.getLogger(__name__)

# Pricing as of Jan 2026 (USD per 1M tokens)
# Update these when pricing changes
MODEL_PRICING = {
    # =========================================================================
    # GOOGLE GEMINI MODELS
    # =========================================================================
    # Gemini 4 Argon / 3.8 Flash: date-dependent, see GEMINI_PROMOTIONS below.

    # Gemini 3.1 Pro Preview (prompts ≤200k tokens; verify current pricing)
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3.1-pro": {"input": 2.00, "output": 12.00},

    # Gemini 3 Pro Preview (prompts ≤200k tokens)
    # For >200k: input=$4.00, output=$18.00
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3-pro": {"input": 2.00, "output": 12.00},

    # Gemini 3 Flash Preview (has free tier, paid rates below)
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-3-flash": {"input": 0.50, "output": 3.00},

    # Gemini 2.5 Flash (has free tier, paid rates below)
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-preview": {"input": 0.30, "output": 2.50},

    # Gemini 2.0 Flash (fallback/cheap option)
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-exp": {"input": 0.10, "output": 0.40},

    # =========================================================================
    # OPENAI GPT-5 MODELS
    # =========================================================================
    # GPT-5.2 (premium)
    "gpt-5.2": {"input": 1.75, "output": 14.00},
    "gpt-5.2-chat-latest": {"input": 1.75, "output": 14.00},
    "gpt-5.2-codex": {"input": 1.75, "output": 14.00},

    # GPT-5.1 (best quality for budget)
    "gpt-5.1": {"input": 1.25, "output": 10.00},
    "gpt-5.1-chat-latest": {"input": 1.25, "output": 10.00},
    "gpt-5.1-codex": {"input": 1.25, "output": 10.00},
    "gpt-5.1-codex-max": {"input": 1.25, "output": 10.00},

    # GPT-5 (stable)
    "gpt-5": {"input": 1.25, "output": 10.00},
    "gpt-5-chat-latest": {"input": 1.25, "output": 10.00},
    "gpt-5-codex": {"input": 1.25, "output": 10.00},

    # GPT-5-mini (balanced cost)
    "gpt-5-mini": {"input": 0.25, "output": 2.00},

    # GPT-5-nano (cheapest)
    "gpt-5-nano": {"input": 0.05, "output": 0.40},

    # GPT-5 Pro (expensive - not recommended for budget)
    "gpt-5.2-pro": {"input": 21.00, "output": 168.00},
    "gpt-5-pro": {"input": 15.00, "output": 120.00},

    # =========================================================================
    # ANTHROPIC CLAUDE MODELS (direct API)
    # =========================================================================
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},

    # =========================================================================
    # AWS BEDROCK MODELS
    # =========================================================================
    # Bedrock charges the same per-token rate as direct provider APIs for
    # Anthropic models. Verify current pricing at deploy time:
    #   https://aws.amazon.com/bedrock/pricing/

    # Current AGF website catalog (2026-10-16). Rates from the AWS Price List
    # API (ap-southeast-2, on-demand Standard) and, for GPT-6 Luna, which the
    # Price List does not carry yet, its Bedrock model card. Keyed by the
    # foundation-model ID, which is what BedrockClient passes as `model`.
    # Claude runs through au.* (Australia geo, 10% over global); GPT-6 and
    # Kimi K3 are global-only from Sydney. GPT-6 rates are the short-context
    # tier (<=272K input tokens).
    "anthropic.claude-opus-4-8":   {"input": 5.50,  "output": 27.50},
    "anthropic.claude-sonnet-5":   {"input": 2.20,  "output": 11.00},
    "openai.gpt-6-astra":          {"input": 10.00, "output": 50.00},
    "openai.gpt-6-luna":           {"input": 0.10,  "output": 0.50},
    "moonshotai.kimi-k3":          {"input": 3.00,  "output": 15.00},

    # Anthropic Claude (via Bedrock) — same pricing as direct API.
    # Verified via list-foundation-models on 2026-05-05; ap-southeast-2.
    # Opus 4.7 = Pro tier (generation/evolution/meta-review)
    # Sonnet 4.6 = Flash tier (reflection/ranking/supervisor)
    # No Haiku — AGF policy: keep all agents on Sonnet 4.6 or above.
    # Opus 4.7 / Sonnet 4.6 are INFERENCE_PROFILE-only on Bedrock — must be
    # invoked via cross-region profile (au.* in ap-southeast-2). Pricing is the
    # same as the underlying foundation model. Both forms keyed for safety.
    "au.anthropic.claude-opus-4-7":              {"input": 15.00, "output": 75.00},
    "au.anthropic.claude-sonnet-4-6":            {"input": 3.00,  "output": 15.00},
    "global.anthropic.claude-opus-4-7":          {"input": 15.00, "output": 75.00},
    "global.anthropic.claude-sonnet-4-6":        {"input": 3.00,  "output": 15.00},
    "anthropic.claude-opus-4-7":                 {"input": 15.00, "output": 75.00},
    "anthropic.claude-sonnet-4-6":               {"input": 3.00,  "output": 15.00},
    # Older revisions kept for back-compat with any existing saved runs.
    "anthropic.claude-opus-4-5-20251101-v1:0":   {"input": 15.00, "output": 75.00},
    "anthropic.claude-opus-4-6-v1":              {"input": 15.00, "output": 75.00},
    "anthropic.claude-sonnet-4-5-20250929-v1:0": {"input": 3.00,  "output": 15.00},
    "anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 3.00,  "output": 15.00},

    # DeepSeek (via Bedrock) — only V3.x available in ap-southeast-2 (no R1).
    "deepseek.v3.2":      {"input": 0.27, "output": 1.10},
    "deepseek.v3-v1:0":   {"input": 0.27, "output": 1.10},  # V3.1

    # OpenAI GPT-OSS (via Bedrock — open-source models hosted on Bedrock)
    # 120B = Pro tier; 20B = Flash tier. Note: id suffix is `-1:0`, not `-v1:0`.
    "openai.gpt-oss-120b-1:0": {"input": 1.50, "output": 6.00},
    "openai.gpt-oss-20b-1:0":  {"input": 0.20, "output": 0.80},

    # Moonshot Kimi (via Bedrock) — official ap-southeast-2 rates.
    # K2 Thinking = Pro tier (generation/evolution/meta-review).
    # K2.5        = Flash tier (reflection/ranking/supervisor).
    "moonshot.kimi-k2-thinking": {"input": 0.6180, "output": 2.5750},
    "moonshotai.kimi-k2.5":      {"input": 0.6180, "output": 3.0900},

    # Mistral (via Bedrock) — published rates ap-southeast-2.
    "mistral.mistral-large-2402-v1:0":    {"input": 4.00, "output": 12.00},
    "mistral.mixtral-8x7b-instruct-v0:1": {"input": 0.45, "output": 0.70},
    "mistral.mistral-7b-instruct-v0:2":   {"input": 0.15, "output": 0.20},

    # NVIDIA Nemotron (via Bedrock) — newer to ap-southeast-2.
    # Published Bedrock pricing for older Nemotron Super 49B was $0.92/$3.68.
    # The 3.x family rates below are best-effort estimates aligned to model
    # size; refine if AWS publishes official figures (the cost reporter uses
    # these only for AUD/USD display; runs aren't blocked by inaccuracy).
    "nvidia.nemotron-super-3-120b": {"input": 1.50, "output": 4.50},
    "nvidia.nemotron-nano-3-30b":   {"input": 0.30, "output": 0.60},
    "nvidia.nemotron-nano-12b-v2":  {"input": 0.15, "output": 0.30},
    "nvidia.nemotron-nano-9b-v2":   {"input": 0.10, "output": 0.20},
}

# Gemini 4 Argon / 3.8 Flash: Google's paid Standard tier, checked 2026-10-16.
# Both are on introductory pricing that doubles after the listed last day.
# Pricing at the full rate before then would show users twice their real spend
# and stop runs at half their budget, so each run is priced at the rate in
# force when its container starts. Output includes thinking tokens.
GEMINI_PROMOTIONS = {
    # model: (last promotional day, promotional rate, full rate)
    "gemini-4-argon": (date(2026, 11, 30),
                       {"input": 2.00, "output": 10.00}, {"input": 4.00, "output": 20.00}),
    "gemini-3.8-flash": (date(2026, 12, 31),
                         {"input": 0.75, "output": 3.75}, {"input": 1.50, "output": 7.50}),
}


def gemini_rate(model: str, today: date) -> dict:
    """The rate in force for a GEMINI_PROMOTIONS model on a given day."""
    last_promo_day, promo, full = GEMINI_PROMOTIONS[model]
    return promo if today <= last_promo_day else full


for _model in GEMINI_PROMOTIONS:
    MODEL_PRICING[_model] = gemini_rate(_model, date.today())

# USD to AUD conversion (update periodically)
USD_TO_AUD = 1.55


class BudgetExceededError(Exception):
    """Raised when the cost budget has been exceeded."""
    def __init__(self, current_cost: float, budget: float, currency: str = "AUD",
                 reserve: float = 0.0):
        self.current_cost = current_cost
        self.budget = budget
        self.currency = currency
        self.reserve = reserve
        note = (f" (${reserve:.2f} {currency} of it kept for the final synthesis)"
                if reserve > 0 else "")
        super().__init__(
            f"Budget exceeded! Current cost: ${current_cost:.2f} {currency}, "
            f"Budget: ${budget:.2f} {currency}{note}"
        )


@dataclass
class AgentUsage:
    """Track usage for a single agent."""
    agent_name: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    cost_usd: float = 0.0

    def add_usage(self, input_tokens: int, output_tokens: int, model: str):
        """Add token usage and calculate cost."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1
        self.model = model

        pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 4.0})
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        self.cost_usd += input_cost + output_cost


@dataclass
class CostTracker:
    """
    Track costs across all agents with a hard budget limit.

    Usage:
        tracker = CostTracker(budget_aud=50.0)

        # Before each LLM call
        tracker.check_budget()  # Raises BudgetExceededError if over budget

        # After each LLM call
        tracker.add_usage(
            agent="generation",
            model="gemini-3-pro-preview",
            input_tokens=10000,
            output_tokens=2000
        )
    """
    budget_aud: float = 50.0
    persist_path: Optional[str] = None
    agent_usage: dict = field(default_factory=dict)
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_calls: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    # Kept back from the budget until begin_finalization(): the run's loop
    # stops at budget_aud - finalization_reserve_aud, so its final synthesis
    # still has money for its calls (the supervisor sets it).
    finalization_reserve_aud: float = 0.0
    finalizing: bool = False
    deadline_monotonic: Optional[float] = None
    _reservations: dict = field(default_factory=dict, repr=False)
    _lock: RLock = field(default_factory=RLock, repr=False)

    def __post_init__(self):
        self._validate_budget()
        if self.persist_path:
            self._load()
        self._validate_budget()

    def _validate_budget(self) -> None:
        if not math.isfinite(float(self.budget_aud)) or self.budget_aud < 0:
            raise ValueError("The run budget must be finite and non-negative")

    def remaining_run_seconds(self) -> Optional[float]:
        return (None if self.deadline_monotonic is None
                else max(0.0, self.deadline_monotonic - time.monotonic()))

    @property
    def committed_cost_aud(self) -> float:
        """Reported usage plus the bounds of outstanding/uncertain requests."""
        with self._lock:
            return self.total_cost_aud + sum(r["cost_aud"] for r in self._reservations.values())

    def reserve_usage(self, *, agent: str, model: str,
                      max_input_tokens: int, max_output_tokens: int) -> str:
        """Atomically reserve the configured-price upper bound before dispatch.

        Unpriced models fail closed. A caller must settle reported usage or leave
        an uncertain reservation; a missing response cannot make possible spend
        available to another request.
        """
        if model not in MODEL_PRICING:
            raise ValueError(f"No configured price for model {model}; request not sent")
        if max_input_tokens < 0 or max_output_tokens <= 0:
            raise ValueError("Request token bounds must be non-negative with a positive output cap")
        pricing = MODEL_PRICING[model]
        amount = (max_input_tokens * pricing["input"] + max_output_tokens * pricing["output"]) / 1_000_000 * USD_TO_AUD
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Invalid configured request price")
        with self._lock:
            self._validate_budget()
            if self.committed_cost_aud + amount > self.spend_limit_aud + 1e-9:
                raise BudgetExceededError(self.committed_cost_aud, self.budget_aud,
                                          reserve=self.finalization_reserve_aud if not self.finalizing else 0)
            key = uuid.uuid4().hex
            self._reservations[key] = {"agent": agent, "model": model,
                "cost_aud": amount, "state": "pending",
                "max_input_tokens": max_input_tokens, "max_output_tokens": max_output_tokens}
            try:
                if self.persist_path:
                    self._save()
            except Exception:
                del self._reservations[key]
                raise
            return key

    def settle_usage(self, reservation: str, *, input_tokens: int, output_tokens: int) -> None:
        """Replace a request bound with reported usage, retaining a paid result
        that exactly fills its admitted budget."""
        with self._lock:
            request = self._reservations.pop(reservation)
            try:
                self.check_and_add_usage(agent=request["agent"], model=request["model"],
                                         input_tokens=input_tokens, output_tokens=output_tokens)
            except BudgetExceededError:
                if self.committed_cost_aud > self.spend_limit_aud + 1e-9:
                    raise
            finally:
                if self.persist_path:
                    self._save()

    def abandon_reservation(self, reservation: str) -> None:
        """Retain the bound when a response or its billing metadata is missing."""
        with self._lock:
            if reservation in self._reservations:
                self._reservations[reservation]["state"] = "uncertain"
                if self.persist_path:
                    self._save()

    @property
    def spend_limit_aud(self) -> float:
        """What may be spent now: the whole budget once finalizing, before
        that the budget less the finalization reserve."""
        if self.finalizing:
            return self.budget_aud
        return max(0.0, self.budget_aud - self.finalization_reserve_aud)

    def begin_finalization(self) -> None:
        """Release the finalization reserve for the run's final calls."""
        self.finalizing = True

    def limit_reached(self) -> bool:
        """Whether the spend limit is reached (no call may start)."""
        with self._lock:
            return self.committed_cost_aud >= self.spend_limit_aud

    def _exceeded(self) -> BudgetExceededError:
        reserve = 0.0 if self.finalizing else min(self.finalization_reserve_aud, self.budget_aud)
        return BudgetExceededError(self.committed_cost_aud, self.budget_aud, reserve=reserve)

    def ensure_budget_available(self) -> None:
        """Raise BudgetExceededError before a call is made once the spend
        limit is reached. The LLM clients call this first: the cost of a
        call is known only after it ran, so without it every call started
        past the limit was billed and then refused."""
        with self._lock:
            self._validate_budget()
            if self.committed_cost_aud >= self.spend_limit_aud:
                raise self._exceeded()

    @property
    def total_cost_aud(self) -> float:
        """Get total cost in AUD."""
        return self.total_cost_usd * USD_TO_AUD

    @property
    def budget_remaining_aud(self) -> float:
        """Get remaining budget in AUD."""
        return max(0, self.budget_aud - self.committed_cost_aud)

    @property
    def budget_percentage_used(self) -> float:
        """Get percentage of budget used."""
        return ((self.committed_cost_aud / self.budget_aud) * 100
                if self.budget_aud else (100.0 if self.committed_cost_aud else 0.0))

    def check_budget(self) -> bool:
        """
        Check if budget is exceeded. Raises BudgetExceededError if so.

        DEPRECATED for LLM usage tracking: This method has a race condition when
        used with add_usage(). Two threads can both pass check_budget() before
        either calls add_usage(), allowing both to proceed and exceed the budget.

        For LLM usage tracking, use check_and_add_usage() instead.

        Still safe for: Standalone budget checks in flow control (e.g., checking
        if workflow should continue) where no add_usage() call follows.
        """
        logger.warning(
            "check_budget() is deprecated for LLM usage tracking. "
            "Use check_and_add_usage() for atomic budget checking and tracking. "
            "Standalone checks for flow control are still acceptable."
        )
        with self._lock:
            if self.committed_cost_aud >= self.spend_limit_aud:
                raise self._exceeded()
            return True

    def check_and_add_usage(
        self,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Atomically check budget and add usage in a single operation.

        This prevents race conditions where two concurrent threads could both
        pass a separate check_budget() call before either adds usage.

        Args:
            agent: Agent name (e.g., "generation", "reflection")
            model: Model name (e.g., "gemini-3-pro-preview")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost of this call in AUD

        Raises:
            BudgetExceededError: If this call takes the total to the spend
                limit (see spend_limit_aud). The call is recorded first: it has
                already run and been billed.
        """
        with self._lock:
            # Calculate cost for this call
            pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 4.0})
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            call_cost_usd = input_cost + output_cost
            call_cost_aud = call_cost_usd * USD_TO_AUD

            if agent not in self.agent_usage:
                self.agent_usage[agent] = AgentUsage(agent_name=agent, model=model)
            self.agent_usage[agent].add_usage(input_tokens, output_tokens, model)

            # Update totals
            self.total_cost_usd += call_cost_usd
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_calls += 1

            # Persist if path is set
            if self.persist_path:
                self._save()

            if self.total_cost_aud >= self.spend_limit_aud:
                raise self._exceeded()

            return call_cost_aud

    def add_usage(
        self,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Add token usage for an agent. Returns the cost of this call in AUD.

        DEPRECATED: This method has a race condition when used with check_budget().
        Two threads can both pass check_budget() before either calls add_usage(),
        allowing both to proceed and exceed the budget.

        Use check_and_add_usage() instead for atomic budget enforcement.

        Args:
            agent: Agent name (e.g., "generation", "reflection")
            model: Model name (e.g., "gemini-3-pro-preview")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost of this call in AUD
        """
        logger.warning(
            "add_usage() is deprecated due to race condition risk. "
            "Use check_and_add_usage() for atomic budget checking and tracking."
        )
        with self._lock:
            # Calculate cost for this call
            pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 4.0})
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            call_cost_usd = input_cost + output_cost
            call_cost_aud = call_cost_usd * USD_TO_AUD

            # Update agent-specific tracking
            if agent not in self.agent_usage:
                self.agent_usage[agent] = AgentUsage(agent_name=agent, model=model)
            self.agent_usage[agent].add_usage(input_tokens, output_tokens, model)

            # Update totals
            self.total_cost_usd += call_cost_usd
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_calls += 1

            # Persist if path is set
            if self.persist_path:
                self._save()

            # Check budget after adding (for logging purposes)
            if self.total_cost_aud >= self.budget_aud:
                raise BudgetExceededError(self.total_cost_aud, self.budget_aud)

            return call_cost_aud

    def get_summary(self) -> dict:
        """Get a summary of all costs."""
        with self._lock:
            return self._summary_locked()

    def _summary_locked(self) -> dict:
        uncertain = [r for r in self._reservations.values() if r["state"] == "uncertain"]
        unconfirmed_cost = sum(r["cost_aud"] for r in uncertain)
        return {
            "budget_aud": self.budget_aud,
            "total_cost_aud": round(self.total_cost_aud + unconfirmed_cost, 4),
            "total_cost_usd": round(self.total_cost_usd + unconfirmed_cost / USD_TO_AUD, 4),
            "confirmed_cost_aud": round(self.total_cost_aud, 4),
            "unconfirmed_cost_aud": round(unconfirmed_cost, 4),
            "unconfirmed_calls": len(uncertain),
            "pending_cost_aud": round(sum(r["cost_aud"] for r in self._reservations.values()
                                          if r["state"] == "pending"), 4),
            "budget_remaining_aud": round(self.budget_remaining_aud, 4),
            "budget_percentage_used": round(self.budget_percentage_used, 2),
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "started_at": self.started_at,
            "agents": {
                name: {
                    "model": usage.model,
                    "calls": usage.calls,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_usd": round(usage.cost_usd, 4),
                    "cost_aud": round(usage.cost_usd * USD_TO_AUD, 4),
                }
                for name, usage in self.agent_usage.items()
            }
        }

    def print_summary(self):
        """Print a formatted summary to console."""
        summary = self.get_summary()

        print("\n" + "=" * 60)
        print("💰 AI CO-SCIENTIST COST TRACKER")
        print("=" * 60)
        print(f"Budget:     ${summary['budget_aud']:.2f} AUD")
        print(f"Spent:      ${summary['total_cost_aud']:.2f} AUD ({summary['budget_percentage_used']:.1f}%)")
        print(f"Remaining:  ${summary['budget_remaining_aud']:.2f} AUD")
        print(f"Total Calls: {summary['total_calls']}")
        print(f"Total Tokens: {summary['total_input_tokens']:,} in / {summary['total_output_tokens']:,} out")
        print("-" * 60)
        print("Per-Agent Breakdown:")
        print("-" * 60)

        for agent_name, agent_data in summary['agents'].items():
            print(f"  {agent_name}:")
            print(f"    Model:  {agent_data['model']}")
            print(f"    Calls:  {agent_data['calls']}")
            print(f"    Tokens: {agent_data['input_tokens']:,} in / {agent_data['output_tokens']:,} out")
            print(f"    Cost:   ${agent_data['cost_aud']:.4f} AUD")

        print("=" * 60 + "\n")

    def _save(self):
        """Save tracker state to disk."""
        if not self.persist_path:
            return

        path = Path(self.persist_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "budget_aud": self.budget_aud,
            "total_cost_usd": self.total_cost_usd,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_calls": self.total_calls,
            "started_at": self.started_at,
            "reservations": self._reservations,
            "agent_usage": {
                name: asdict(usage)
                for name, usage in self.agent_usage.items()
            }
        }

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def _load(self):
        """Load tracker state from disk."""
        if not self.persist_path:
            return

        path = Path(self.persist_path)
        if not path.exists():
            return

        with open(path, 'r') as f:
            data = json.load(f)

        self.budget_aud = data.get("budget_aud", self.budget_aud)
        self.total_cost_usd = data.get("total_cost_usd", 0.0)
        self.total_input_tokens = data.get("total_input_tokens", 0)
        self.total_output_tokens = data.get("total_output_tokens", 0)
        self.total_calls = data.get("total_calls", 0)
        self.started_at = data.get("started_at", self.started_at)
        # No coroutine from the old process can settle a restored request.
        self._reservations = data.get("reservations", {})
        for request in self._reservations.values():
            request["state"] = "uncertain"

        for name, usage_data in data.get("agent_usage", {}).items():
            self.agent_usage[name] = AgentUsage(**usage_data)

    def reset(self):
        """Reset all tracking data."""
        with self._lock:
            self.agent_usage = {}
            self.total_cost_usd = 0.0
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.total_calls = 0
            self._reservations = {}
            self.started_at = datetime.now().isoformat()

            if self.persist_path:
                self._save()


# Global singleton instance
_tracker: Optional[CostTracker] = None


def get_tracker(
    budget_aud: float = 50.0,
    persist_path: Optional[str] = "./data/cost_tracking.json"
) -> CostTracker:
    """
    Get or create the global cost tracker instance.

    Args:
        budget_aud: Maximum budget in AUD (default: 50.0)
        persist_path: Path to persist tracking data (default: ./data/cost_tracking.json)

    Returns:
        CostTracker instance
    """
    global _tracker
    if _tracker is None:
        _tracker = CostTracker(budget_aud=budget_aud, persist_path=persist_path)
    return _tracker


# Example usage and LangChain callback integration
if __name__ == "__main__":
    # Demo usage
    tracker = get_tracker(budget_aud=50.0)

    # Simulate some agent calls
    tracker.add_usage("generation", "gemini-3-pro-preview", 10000, 2000)
    tracker.add_usage("generation", "gemini-3-pro-preview", 8000, 1500)
    tracker.add_usage("reflection", "gemini-2.5-flash", 5000, 800)
    tracker.add_usage("ranking", "gemini-3-flash-preview", 15000, 500)
    tracker.add_usage("supervisor", "gemini-3-flash-preview", 2000, 200)

    tracker.print_summary()

    # Check budget before next call
    try:
        tracker.check_budget()
        print("✅ Budget OK - can continue")
    except BudgetExceededError as e:
        print(f"❌ {e}")
