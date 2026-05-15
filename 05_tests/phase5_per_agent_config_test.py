#!/usr/bin/env python3
"""Tests for per-agent LLM model configuration (Phase A)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="agf_phase5_agent_models_")
os.environ["AGF_DATA_DIR"] = _TMP
os.environ.setdefault("GOOGLE_API_KEY", "dummy")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "03_architecture"))
sys.path.insert(0, str(PROJECT_ROOT / "04_Scripts"))


class TestAgentModelConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agf_pac_"))
        os.environ["AGF_DATA_DIR"] = str(self.tmp)
        # Bust caches that may have been bound to the previous data dir.
        from src.config import agent_models

        agent_models.reset_cache()

    def test_pydantic_model(self):
        from src.config.agent_models import AgentModelConfig

        cfg = AgentModelConfig(provider="openai", model="gpt-5", temperature=0.3)
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.model, "gpt-5")
        self.assertEqual(cfg.temperature, 0.3)

    def test_provider_alias_normalization(self):
        from src.config.agent_models import AgentModelConfig

        self.assertEqual(AgentModelConfig(provider="google", model="x").provider, "gemini")
        self.assertEqual(AgentModelConfig(provider="gpt", model="x").provider, "openai")
        self.assertEqual(AgentModelConfig(provider="claude", model="x").provider, "anthropic")

    def test_agent_names_complete(self):
        from src.config.agent_models import AGENT_NAMES

        expected = {
            "generation",
            "reflection",
            "ranking",
            "evolution",
            "proximity",
            "meta_review",
            "supervisor",
            "safety",
        }
        self.assertEqual(set(AGENT_NAMES), expected)

    def test_set_and_get_default(self):
        from src.config.agent_models import (
            AgentModelConfig,
            get_default_config,
            set_default_config,
        )

        cfg = AgentModelConfig(provider="openai", model="gpt-5", temperature=0.5)
        set_default_config(cfg)
        loaded = get_default_config()
        self.assertEqual(loaded.provider, "openai")
        self.assertEqual(loaded.model, "gpt-5")

    def test_per_agent_override_roundtrip(self):
        from src.config.agent_models import (
            AgentModelConfig,
            clear_agent_override,
            get_agent_override,
            set_agent_override,
        )

        cfg = AgentModelConfig(provider="anthropic", model="claude-opus-4-1")
        set_agent_override("generation", cfg)
        loaded = get_agent_override("generation")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.provider, "anthropic")
        clear_agent_override("generation")
        self.assertIsNone(get_agent_override("generation"))

    def test_runtime_config_none_when_no_file(self):
        # Fresh tmp dir, no file written yet.
        from src.config.agent_models import get_agent_runtime_config, reset_cache

        reset_cache()
        self.assertIsNone(get_agent_runtime_config("generation"))

    def test_runtime_config_respects_override(self):
        from src.config.agent_models import (
            AgentModelConfig,
            get_agent_runtime_config,
            set_agent_override,
            set_default_config,
        )

        set_default_config(AgentModelConfig(provider="gemini", model="gemini-2.5-pro"))
        set_agent_override(
            "generation",
            AgentModelConfig(provider="openai", model="gpt-5", temperature=0.2),
        )
        # Per-agent override wins.
        cfg = get_agent_runtime_config("generation")
        self.assertEqual(cfg["provider"], "openai")
        self.assertEqual(cfg["model"], "gpt-5")
        self.assertEqual(cfg["temperature"], 0.2)
        # Default applies to other agents.
        cfg_r = get_agent_runtime_config("ranking")
        self.assertEqual(cfg_r["provider"], "gemini")

    def test_invalid_agent_name(self):
        from src.config.agent_models import (
            AgentModelConfig,
            set_agent_override,
        )

        with self.assertRaises(ValueError):
            set_agent_override(
                "not_a_real_agent",
                AgentModelConfig(provider="gemini", model="gemini-2.5-pro"),
            )

    def test_settings_get_agent_config(self):
        from src.config import settings
        from src.config.agent_models import (
            AgentModelConfig,
            set_agent_override,
        )

        set_agent_override(
            "safety",
            AgentModelConfig(provider="deepseek", model="deepseek-chat"),
        )
        cfg = settings.get_agent_config("safety")
        self.assertEqual(cfg["provider"], "deepseek")
        self.assertEqual(cfg["model"], "deepseek-chat")

    def test_factory_uses_per_agent_config(self):
        """get_llm_client should honor the per-agent override."""
        from src.config.agent_models import (
            AgentModelConfig,
            set_agent_override,
        )

        set_agent_override(
            "generation",
            AgentModelConfig(provider="openai", model="gpt-5", temperature=0.1),
        )

        from src.llm import factory as factory_mod

        captured = {}

        class FakeClient:
            def __init__(self, model, agent_name, **kw):
                captured["model"] = model
                captured["agent"] = agent_name
                captured["kw"] = kw

        with mock.patch.object(factory_mod, "OpenAIClient", FakeClient):
            client = factory_mod.get_llm_client(
                model="ignored-by-override",
                agent_name="generation",
            )
        self.assertEqual(captured["model"], "gpt-5")
        self.assertEqual(captured["agent"], "generation")


if __name__ == "__main__":
    unittest.main()
