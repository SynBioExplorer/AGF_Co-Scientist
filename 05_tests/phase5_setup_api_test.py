#!/usr/bin/env python3
"""Tests for the setup wizard / secrets / agent-models API (Phase A)."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="agf_phase5_setup_api_")
os.environ["AGF_DATA_DIR"] = _TMP
os.environ.setdefault("GOOGLE_API_KEY", "dummy")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "03_architecture"))
sys.path.insert(0, str(PROJECT_ROOT / "04_Scripts"))

# Stub out src.api package init so we don't transitively import the full
# FastAPI app (which depends on PyMuPDF + cost_tracker + everything else).
_api_pkg = types.ModuleType("src.api")
_api_pkg.__path__ = [str(PROJECT_ROOT / "src" / "api")]
sys.modules.setdefault("src.api", _api_pkg)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.setup import router as setup_router  # noqa: E402
from src.utils import keychain  # noqa: E402


def _build_app():
    app = FastAPI()
    app.include_router(setup_router)
    return app


class TestSetupAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agf_setup_api_run_"))
        os.environ["AGF_DATA_DIR"] = str(self.tmp)
        keychain.force_fallback(True)
        # Reset per-agent config cache after AGF_DATA_DIR change.
        from src.config import agent_models

        agent_models.reset_cache()
        self.app = _build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        keychain.force_fallback(False)
        self.client.close()

    # ------------------------------------------------------------------

    def test_initial_status_is_incomplete(self):
        r = self.client.get("/api/setup/status")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["completed"])
        self.assertIn("providers", body["missing_steps"])

    def test_validate_key_format_failure(self):
        r = self.client.post(
            "/api/setup/validate-key",
            json={"provider": "openai", "api_key": "x"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["valid"])

    def test_validate_key_with_mocked_live_check(self):
        async def fake_live(provider, key):
            return True, None

        with mock.patch("src.api.setup._live_validate", side_effect=fake_live):
            r = self.client.post(
                "/api/setup/validate-key",
                json={
                    "provider": "openai",
                    "api_key": "sk-thisismorethaneightchars",
                },
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["valid"])
        self.assertGreater(len(body["available_models"]), 0)

    def test_complete_flow(self):
        export_dir = self.tmp / "exports"
        body = {
            "providers": {
                "gemini": "AIza-fake-gemini-key-abc123",
                "openai": None,
                "deepseek": None,
                "anthropic": None,
            },
            "optional": {
                "tavily": None,
                "ncbi": None,
                "semantic_scholar": False,
            },
            "export_folder": str(export_dir),
            "email": {"enabled": False, "recipient": None},
        }
        r = self.client.post("/api/setup/complete", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["success"])

        # status should now be completed
        s = self.client.get("/api/setup/status")
        self.assertTrue(s.json()["completed"])

        # secrets endpoint reports masked key
        sec = self.client.get("/api/settings/secrets").json()
        self.assertTrue(sec["providers"]["gemini"]["set"])
        self.assertIsNotNone(sec["providers"]["gemini"]["masked"])
        self.assertTrue(sec["providers"]["gemini"]["masked"].startswith("..."))

    def test_delete_secret(self):
        # First set a secret.
        keychain.set_secret("openai_api_key", "sk-some-test-key")
        r = self.client.delete("/api/settings/secrets/openai")
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(keychain.get_secret("openai_api_key"))

    def test_available_models(self):
        for provider in ("gemini", "openai", "deepseek", "anthropic"):
            r = self.client.get(
                "/api/settings/available-models", params={"provider": provider}
            )
            self.assertEqual(r.status_code, 200, r.text)
            models = r.json()["models"]
            self.assertIsInstance(models, list)
            self.assertGreater(len(models), 0)

    def test_available_models_unknown_provider(self):
        r = self.client.get(
            "/api/settings/available-models", params={"provider": "bogus"}
        )
        self.assertEqual(r.status_code, 400)

    def test_agent_models_roundtrip(self):
        r = self.client.get("/api/settings/agent-models")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("default", body)
        self.assertIn("agents", body)

        new_body = {
            "default": {
                "provider": "gemini",
                "model": "gemini-2.5-pro",
                "temperature": 0.7,
            },
            "agents": {
                "generation": {
                    "provider": "openai",
                    "model": "gpt-5",
                    "temperature": 0.3,
                },
                "reflection": None,
                "ranking": None,
                "evolution": None,
                "proximity": None,
                "meta_review": None,
                "supervisor": None,
                "safety": {
                    "provider": "anthropic",
                    "model": "claude-haiku-4-5",
                    "temperature": 0.2,
                },
            },
        }
        r2 = self.client.put("/api/settings/agent-models", json=new_body)
        self.assertEqual(r2.status_code, 200, r2.text)
        saved = r2.json()
        self.assertEqual(saved["default"]["provider"], "gemini")
        self.assertEqual(saved["agents"]["generation"]["provider"], "openai")
        self.assertEqual(saved["agents"]["safety"]["provider"], "anthropic")
        # The other agents remain None.
        self.assertIsNone(saved["agents"]["ranking"])


if __name__ == "__main__":
    unittest.main()
