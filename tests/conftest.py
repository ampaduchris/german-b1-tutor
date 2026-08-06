"""Shared pytest fixtures for the deterministic layer.

Nothing here imports ADK, opens a socket, or calls a model, for the same
reason tools.py does not: this whole layer is supposed to be exactly
reproducible.

Both fixtures work by monkeypatching the module-level paths in tools.py rather
than by passing a path argument. That is deliberate and mirrors the reason
those paths are module-level in the first place: three of these functions
become ADK tools in session 3, and every parameter of a registered function is
published to the model in the tool schema. A `log_path` parameter would be a
knob the model could turn. Tests get the same flexibility without giving the
model any.
"""

from pathlib import Path

import pytest

import tools

# The committed 14-entry fixture. Its known answers are asserted in
# test_tools.py, where they are also documented in full.
FIXTURE_LOG = Path(__file__).resolve().parent / "fixtures" / "log_sample.jsonl"


@pytest.fixture
def temp_log(tmp_path, monkeypatch):
    """Point tools at a throwaway log inside tmp_path.

    Note that `data/` is NOT created here. A fresh clone has no `data/`
    directory at all, because it is gitignored, so log_error creating its own
    parent directory is a real requirement and is tested rather than papered
    over by this fixture.
    """
    log = tmp_path / "data" / "log.jsonl"
    monkeypatch.setattr(tools, "LOG_PATH", log)
    monkeypatch.setattr(tools, "CARDS_PATH", tmp_path / "data" / "cards.csv")
    return log


@pytest.fixture
def sample_log(tmp_path, monkeypatch):
    """Point tools at the committed 14-entry fixture, read-only.

    CARDS_PATH is redirected into tmp_path so that an export test cannot write
    into the repository.
    """
    monkeypatch.setattr(tools, "LOG_PATH", FIXTURE_LOG)
    monkeypatch.setattr(tools, "CARDS_PATH", tmp_path / "cards.csv")
    return FIXTURE_LOG


@pytest.fixture
def write_entry(temp_log):
    """Append one entry with sensible defaults, overridable per call."""

    def _write(**overrides):
        payload = {
            "learner_text": "Wenn ich Zeit habe, ich gehe ins Kino.",
            "correction": "Wenn ich Zeit habe, gehe ich ins Kino.",
            "category": "word_order",
            "detail": "verb_second_after_subordinate_clause",
            "explanation_en": "After a subordinate clause the verb comes first.",
            "severity": "blocking",
            # `gespraech`, not the fixture's historical "conversation": session
            # 5 closed the mode vocabulary in tools.MODES, so log_error now
            # rejects any other spelling. The committed fixture still holds the
            # old strings on purpose — reads do not validate, and it is
            # evidence of exactly the drift the closure prevents.
            "mode": "gespraech",
        }
        payload.update(overrides)
        return tools.log_error(**payload)

    return _write
