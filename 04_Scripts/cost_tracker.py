"""
Cost Tracker for AI Co-Scientist

Tracks token usage and costs per agent, with a hard budget limit.
Raises BudgetExceededError when the budget is exhausted.
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from threading import Lock

logger = logging.getLogger(__name__)

# Pricing as of Jan 2026 (USD per 1M tokens)
# Update these when pricing changes
MODEL_PRICING = {
    # =========================================================================
    # GOOGLE GEMINI MODELS
    # =========================================================================
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
    # ANTHROPIC CLAUDE MODELS
    # =========================================================================
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
}

# USD to AUD conversion (update periodically)
USD_TO_AUD = 1.55


class BudgetExceededError(Exception):
    """Raised when the cost budget has been exceeded."""
    def __init__(self, current_cost: float, budget: float, currency: str = "AUD"):
        self.current_cost = current_cost
        self.budget = budget
        self.currency = currency
        super().__init__(
            f"Budget exceeded! Current cost: ${current_cost:.2f} {currency}, "
            f"Budget: ${budget:.2f} {currency}"
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
    _lock: Lock = field(default_factory=Lock, repr=False)

    def __post_init__(self):
        if self.persist_path:
            self._load()

    @property
    def total_cost_aud(self) -> float:
        """Get total cost in AUD."""
        return self.total_cost_usd * USD_TO_AUD

    @property
    def budget_remaining_aud(self) -> float:
        """Get remaining budget in AUD."""
        return max(0, self.budget_aud - self.total_cost_aud)

    @property
    def budget_percentage_used(self) -> float:
        """Get percentage of budget used."""
        return (self.total_cost_aud / self.budget_aud) * 100

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
            if self.total_cost_aud >= self.budget_aud:
                raise BudgetExceededError(self.total_cost_aud, self.budget_aud)
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
            BudgetExceededError: If this call would exceed the budget
        """
        with self._lock:
            # Calculate cost for this call
            pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 4.0})
            input_cost = (input_tokens / 1_000_000) * pricing["input"]
            output_cost = (output_tokens / 1_000_000) * pricing["output"]
            call_cost_usd = input_cost + output_cost
            call_cost_aud = call_cost_usd * USD_TO_AUD

            # Check if this call would exceed budget BEFORE adding
            projected_total_aud = self.total_cost_aud + call_cost_aud
            if projected_total_aud >= self.budget_aud:
                raise BudgetExceededError(projected_total_aud, self.budget_aud)

            # Safe to add - budget check passed
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
        return {
            "budget_aud": self.budget_aud,
            "total_cost_aud": round(self.total_cost_aud, 4),
            "total_cost_usd": round(self.total_cost_usd, 4),
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
