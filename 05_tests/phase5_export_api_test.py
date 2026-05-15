#!/usr/bin/env python3
"""Tests for the email-export API (Phase A)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs

_TMP = tempfile.mkdtemp(prefix="agf_phase5_export_api_")
os.environ["AGF_DATA_DIR"] = _TMP
os.environ.setdefault("GOOGLE_API_KEY", "dummy")

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "03_architecture"))
sys.path.insert(0, str(PROJECT_ROOT / "04_Scripts"))

_api_pkg = types.ModuleType("src.api")
_api_pkg.__path__ = [str(PROJECT_ROOT / "src" / "api")]
sys.modules.setdefault("src.api", _api_pkg)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.export import router as export_router  # noqa: E402


def _build_app():
    app = FastAPI()
    app.include_router(export_router)
    return app


class TestExportAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agf_export_api_run_"))
        os.environ["AGF_DATA_DIR"] = str(self.tmp)
        self.export_dir = self.tmp / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)

        # Seed setup_state.json so export resolves to our temp folder.
        from src.utils.paths import get_app_data_dir

        state_file = get_app_data_dir() / "setup_state.json"
        with open(state_file, "w") as f:
            json.dump(
                {
                    "completed": True,
                    "export_folder": str(self.export_dir),
                    "email": {"enabled": True, "recipient": "user@example.com"},
                },
                f,
            )

        self.app = _build_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def _write_run(self, run_id: str, with_html: bool = True, with_json: bool = True):
        if with_html:
            (self.export_dir / f"{run_id}.html").write_text(
                "<html><body>report</body></html>"
            )
        if with_json:
            (self.export_dir / f"{run_id}.json").write_text(
                json.dumps(
                    {
                        "goal": {"description": "Test goal"},
                        "hypotheses": [
                            {"title": "Hyp A", "elo_rating": 1500},
                            {"title": "Hyp B", "elo_rating": 1200},
                        ],
                    }
                )
            )

    def test_missing_run_returns_404(self):
        r = self.client.post("/api/runs/does_not_exist/export/email")
        self.assertEqual(r.status_code, 404)

    def test_export_builds_mailto(self):
        self._write_run("run42")
        r = self.client.post("/api/runs/run42/export/email")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("mailto_url", body)
        self.assertIn("html_report_path", body)
        # html_report_path is correct
        self.assertTrue(body["html_report_path"].endswith("run42.html"))
        self.assertTrue(Path(body["html_report_path"]).exists())

        # mailto URL must include recipient and decoded summary.
        parsed = urlparse(body["mailto_url"])
        self.assertEqual(parsed.scheme, "mailto")
        recipient = unquote(parsed.path)
        self.assertEqual(recipient, "user@example.com")
        qs = parse_qs(parsed.query)
        self.assertIn("subject", qs)
        self.assertIn("body", qs)
        body_text = unquote(qs["body"][0])
        self.assertIn("Hyp A", body_text)
        self.assertIn("Test goal", body_text)

    def test_export_with_run_prefix(self):
        # Run reports are often saved as "run_<id>.html" by the existing
        # html_report util -- make sure we still find them.
        (self.export_dir / "run_42.html").write_text("<html>x</html>")
        r = self.client.post("/api/runs/42/export/email")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["html_report_path"].endswith("run_42.html"))

    def test_export_with_email_disabled(self):
        # Update state to disable email.
        from src.utils.paths import get_app_data_dir

        state_file = get_app_data_dir() / "setup_state.json"
        with open(state_file, "w") as f:
            json.dump(
                {
                    "completed": True,
                    "export_folder": str(self.export_dir),
                    "email": {"enabled": False, "recipient": None},
                },
                f,
            )
        self._write_run("disabled_run")
        r = self.client.post("/api/runs/disabled_run/export/email")
        self.assertEqual(r.status_code, 200)
        # mailto: with empty recipient is still a valid client behavior --
        # the desktop UI will prompt the user for an address.
        self.assertTrue(r.json()["mailto_url"].startswith("mailto:"))


if __name__ == "__main__":
    unittest.main()
