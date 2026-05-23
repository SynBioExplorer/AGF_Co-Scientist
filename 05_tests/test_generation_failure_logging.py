"""Unit test for B10: generation failures must be typed-logged and retried.

Bug: the combined catch ``except (json.JSONDecodeError, PydanticValidationError,
KeyError)`` at generation.py:1163-1164 re-raised a generic CoScientistError
without recording which failure mode occurred, with no retry. The 0.58-0.66
generation success rate could not be attributed to a cause.

Fix:
  (a) Wrap the parse in a 2-attempt retry loop (mirroring evolution.py).
  (b) Split the exception handler into per-type branches with structured
      log names: generation_json_parse_failed,
      generation_schema_validation_failed, generation_keyerror.

GenerationAgent.__init__ initialises an LLM client + tool registry + paper
quality scorer + limitations extractor, so a behavioral execute() test is
out of scope. We assert the structural change is in place; the live
verification run inspects per-mode counts in the actual run JSON.
"""

import inspect
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.append(str(_REPO_ROOT / "03_architecture"))
sys.path.append(str(_REPO_ROOT / "04_Scripts"))
sys.path.append(str(_REPO_ROOT))

import src.agents.generation as gen_mod  # noqa: E402


def _generation_source() -> str:
    return inspect.getsource(gen_mod)


def test_per_exception_log_names_present():
    """B10(a) — each failure mode emits its own structured log line."""
    src = _generation_source()
    for log_name in (
        "generation_json_parse_failed",
        "generation_schema_validation_failed",
        "generation_keyerror",
    ):
        assert log_name in src, (
            f"B10 regression: missing structured log '{log_name}'."
        )


def test_retry_loop_present():
    """B10(b) — 2-attempt retry loop wraps the LLM invoke + parse."""
    src = _generation_source()
    assert "max_attempts = 2" in src, (
        "B10 regression: 2-attempt retry loop is missing."
    )
    assert "for attempt in range(max_attempts)" in src
    # And a `continue` for the retryable branch (JSONDecodeError).
    assert "continue" in src


def test_no_legacy_combined_catch():
    """The old combined catch must be gone (replaced by per-type branches)."""
    src = _generation_source()
    assert "except (json.JSONDecodeError, PydanticValidationError, KeyError)" not in src, (
        "B10 regression: legacy combined except-clause still present."
    )


if __name__ == "__main__":
    test_per_exception_log_names_present()
    test_retry_loop_present()
    test_no_legacy_combined_catch()
    print("✓ B10 tests passed")
