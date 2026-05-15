#!/usr/bin/env python3
"""Tests for the DeepSeek LLM client (Phase A)."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="agf_phase5_deepseek_")
os.environ["AGF_DATA_DIR"] = _TMP
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
os.environ["DEEPSEEK_API_KEY"] = "sk-deepseek-test"

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "03_architecture"))
sys.path.insert(0, str(PROJECT_ROOT / "04_Scripts"))


def _fake_response(content: str = "hello world", in_tok: int = 10, out_tok: int = 5):
    response = mock.MagicMock()
    response.content = content
    response.usage_metadata = {"input_tokens": in_tok, "output_tokens": out_tok}
    response.response_metadata = {}
    return response


class TestDeepSeekClient(unittest.TestCase):

    def test_factory_registers_deepseek(self):
        from src.llm import HARDCODED_MODELS, get_available_models, normalize_provider

        self.assertIn("deepseek", HARDCODED_MODELS)
        self.assertEqual(normalize_provider("deepseek"), "deepseek")
        models = get_available_models("deepseek")
        self.assertIn("deepseek-chat", models)
        self.assertIn("deepseek-reasoner", models)

    def test_init_requires_key(self):
        from src.config import settings
        from src.llm.deepseek_client import DeepSeekClient

        env = dict(os.environ)
        env.pop("DEEPSEEK_API_KEY", None)
        original_settings_key = getattr(settings, "deepseek_api_key", None)
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("src.llm.deepseek_client.ChatOpenAI"):
            object.__setattr__(settings, "deepseek_api_key", None)
            try:
                with self.assertRaises(Exception):
                    DeepSeekClient(model="deepseek-chat", agent_name="test")
            finally:
                object.__setattr__(settings, "deepseek_api_key", original_settings_key)

    def test_init_with_key(self):
        from src.llm.deepseek_client import (
            DEEPSEEK_BASE_URL,
            DeepSeekClient,
        )

        with mock.patch("src.llm.deepseek_client.ChatOpenAI") as mock_cls:
            client = DeepSeekClient(model="deepseek-chat", agent_name="test")
            self.assertIsNotNone(client)
            kwargs = mock_cls.call_args.kwargs
            self.assertEqual(kwargs["base_url"], DEEPSEEK_BASE_URL)
            self.assertEqual(kwargs["model"], "deepseek-chat")

    def test_invoke_uses_chat_completions(self):
        from src.llm.deepseek_client import DeepSeekClient

        with mock.patch("src.llm.deepseek_client.ChatOpenAI") as mock_cls:
            inst = mock_cls.return_value
            inst.invoke.return_value = _fake_response("ok")
            client = DeepSeekClient(model="deepseek-chat", agent_name="test")
            # Bypass retry by patching sync_retry to invoke the function directly.
            with mock.patch(
                "src.llm.deepseek_client.sync_retry",
                side_effect=lambda fn, *a, **kw: fn(*a),
            ):
                result = client.invoke("hello?")
            self.assertEqual(result, "ok")
            inst.invoke.assert_called_once_with("hello?")

    def test_ainvoke_routes_correctly(self):
        from src.llm.deepseek_client import DeepSeekClient

        async def _go():
            with mock.patch("src.llm.deepseek_client.ChatOpenAI") as mock_cls:
                inst = mock_cls.return_value

                async def fake_ainvoke(prompt):
                    return _fake_response("async ok")

                inst.ainvoke = fake_ainvoke
                client = DeepSeekClient(model="deepseek-chat", agent_name="test")

                async def fake_retry(fn, *a, **kw):
                    return await fn(*a)

                with mock.patch(
                    "src.llm.deepseek_client.retry_async", side_effect=fake_retry
                ):
                    return await client.ainvoke("hi")

        result = asyncio.run(_go())
        self.assertEqual(result, "async ok")

    def test_create_llm_client_returns_deepseek(self):
        from src.llm import create_llm_client

        with mock.patch("src.llm.deepseek_client.ChatOpenAI"):
            client = create_llm_client(
                provider="deepseek",
                model="deepseek-reasoner",
                agent_name="test",
            )
            self.assertEqual(client.model, "deepseek-reasoner")

    def test_default_model_is_deepseek_chat(self):
        from src.llm import get_default_model

        self.assertEqual(get_default_model("deepseek"), "deepseek-chat")


if __name__ == "__main__":
    unittest.main()
