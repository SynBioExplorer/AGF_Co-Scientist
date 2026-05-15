#!/usr/bin/env python3
"""Tests for the keychain abstraction (Phase A)."""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_TMP = tempfile.mkdtemp(prefix="agf_phase5_keychain_")
os.environ["AGF_DATA_DIR"] = _TMP

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import keychain  # noqa: E402


class TestKeychainAPI(unittest.TestCase):
    """Test the public API using the fallback (encrypted SQLite) backend
    so we don't depend on the host OS keychain."""

    def setUp(self):
        # Use an isolated app-data dir per test so the fallback DB is fresh.
        self.tmp = Path(tempfile.mkdtemp(prefix="agf_keychain_run_"))
        os.environ["AGF_DATA_DIR"] = str(self.tmp)
        # Force the keyring backend off so we exercise the SQLite fallback.
        keychain.force_fallback(True)

    def tearDown(self):
        keychain.force_fallback(False)

    def test_round_trip(self):
        keychain.set_secret("openai_api_key", "sk-test-12345")
        self.assertEqual(keychain.get_secret("openai_api_key"), "sk-test-12345")

    def test_overwrite(self):
        keychain.set_secret("k", "first")
        keychain.set_secret("k", "second")
        self.assertEqual(keychain.get_secret("k"), "second")

    def test_delete(self):
        keychain.set_secret("k", "v")
        keychain.delete_secret("k")
        self.assertIsNone(keychain.get_secret("k"))

    def test_list_keys(self):
        keychain.set_secret("a", "1")
        keychain.set_secret("b", "2")
        keys = set(keychain.list_keys())
        self.assertTrue({"a", "b"}.issubset(keys))
        keychain.delete_secret("a")
        keys2 = set(keychain.list_keys())
        self.assertNotIn("a", keys2)
        self.assertIn("b", keys2)

    def test_get_missing(self):
        self.assertIsNone(keychain.get_secret("never_set"))

    def test_mask(self):
        self.assertEqual(keychain.mask("sk-1234567890"), "...7890")
        self.assertIsNone(keychain.mask(None))
        self.assertEqual(keychain.mask("a"), "*")

    def test_force_fallback_reports_fallback(self):
        self.assertTrue(keychain.is_using_fallback())


class TestKeychainKeyringPath(unittest.TestCase):
    """Test that when keyring IS usable, we delegate to it."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="agf_keychain_run2_"))
        os.environ["AGF_DATA_DIR"] = str(self.tmp)
        keychain.force_fallback(False)

    def test_set_calls_keyring(self):
        with mock.patch.object(keychain, "_keyring_usable", return_value=True), \
             mock.patch.object(keychain, "keyring") as mock_kr:
            mock_kr.set_password = mock.MagicMock()
            mock_kr.get_password = mock.MagicMock(return_value="abc")
            mock_kr.delete_password = mock.MagicMock()
            keychain.set_secret("openai_api_key", "abc")
            mock_kr.set_password.assert_called_once_with(
                keychain.SERVICE_NAME, "openai_api_key", "abc"
            )

    def test_get_uses_keyring(self):
        with mock.patch.object(keychain, "_keyring_usable", return_value=True), \
             mock.patch.object(keychain, "keyring") as mock_kr:
            mock_kr.get_password = mock.MagicMock(return_value="from-keyring")
            self.assertEqual(keychain.get_secret("k"), "from-keyring")
            mock_kr.get_password.assert_called_once()


if __name__ == "__main__":
    unittest.main()
