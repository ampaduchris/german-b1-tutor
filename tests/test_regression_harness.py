"""Unit tests for scripts/regression.py, the prompt regression harness.

Zero model calls. `regression.one_turn` and the ADK runner are stubbed, so a
fake model drives the real grading, the real sandboxing and the real
obligation checks.

Why this file exists, stated plainly. Session 5 built the harness and verified
it from scratch scripts in a temp directory that were then deleted. A test
suite whose own correctness is unpinned is the thing tutorial section 9 warns
about: "evaluating by vibe, then attributing improvement to whichever change
you made last". The harness is the instrument used to judge every future prompt
edit, so it needs its own calibration checked more than anything else here.

The single most important test in the file is
test_harness_never_touches_the_real_log, because a check that corrupts the
state it measures is worse than no check at all.
"""

import asyncio
import hashlib
import inspect
import sys
from pathlib import Path

import pytest

import agent
import tools

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import regression  # noqa: E402


# --------------------------------------------------------------------------
# The grader. Pure, exact, and the reason no model is involved.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected, observed, verdict, passes, strict",
    [
        ({"case"}, set(), "missed", False, False),
        ({"case"}, {"case"}, "exact", True, True),
        ({"case"}, {"case", "gender"}, "extra", True, False),
        ({"case"}, {"prepositions"}, "wrong", False, False),
        ({"case"}, {"gender", "spelling"}, "wrong", False, False),
        ({"register", "word_order"}, {"register", "word_order"}, "exact", True, True),
        ({"register", "word_order"}, {"register"}, "wrong", False, False),
    ],
)
def test_grade_truth_table(expected, observed, verdict, passes, strict):
    result = regression.grade(expected, observed)
    assert (result["verdict"], result["pass"], result["strict"]) == (
        verdict, passes, strict
    )


def test_grade_reports_the_categories_it_did_not_expect():
    assert regression.grade({"case"}, {"case", "gender"})["extra"] == ["gender"]


def test_a_wrong_expectation_produces_a_failure():
    """H2: a check that cannot fail is not a check.

    Every expectation rotated to a different valid category must fail. This is
    the property that was verified against the live model in session 5 and is
    pinned here so it cannot silently rot.
    """
    rotated = [
        {"konjunktiv_ii"}, {"adjective_endings"}, {"word_order"},
        {"register"}, {"case"},
    ]
    truth = [{"case"}, {"konjunktiv_ii"}, {"adjective_endings"},
             {"word_order"}, {"register"}]
    for wrong, observed in zip(rotated, truth):
        assert regression.grade(wrong, observed)["pass"] is False


# --------------------------------------------------------------------------
# The five sentences are the spec's five, and each carries ONE category
# --------------------------------------------------------------------------


def test_five_sentences_covering_the_five_planted_errors():
    assert len(regression.SENTENCES) == 5
    assert [sorted(s["expect"])[0] for s in regression.SENTENCES] == [
        "case", "konjunktiv_ii", "adjective_endings", "word_order", "register"
    ]


def test_every_expected_category_is_in_the_closed_set():
    for spec in regression.SENTENCES:
        assert spec["expect"] <= set(tools.CATEGORIES)
    assert regression.AUFGABE_SUBMISSION["expect"] <= set(tools.CATEGORIES)


def test_the_adjective_sentence_has_a_correct_article():
    """Regression on the fix itself.

    `Ich habe einen neuen Auto gekauft` carried one mistake in two slots and
    was categorised `gender` twice, deterministically, so no single expected
    category could be right. The article must stay correct or the sentence
    stops isolating the adjective ending and the row goes permanently red.
    """
    text = regression.SENTENCES[2]["text"]
    assert "ein neuen Auto" in text
    assert "einen neuen Auto" not in text


# --------------------------------------------------------------------------
# The elicitation table is READ from tutor.md, never copied
# --------------------------------------------------------------------------


def test_elicitation_table_parses_every_category_plus_the_cold_start():
    rows = regression.elicitation_rows()
    assert set(tools.CATEGORIES) <= set(rows)
    assert regression.COLD_START_KEY in rows
    assert rows["konjunktiv_ii"].startswith("Was würden Sie machen")


def test_control_message_table_does_not_leak_into_the_elicitation_rows():
    """tutor.md has several three-column tables; only one is the table."""
    rows = regression.elicitation_rows()
    assert not any("SESSION_START" in key for key in rows)
    assert all(question for question in rows.values())


# --------------------------------------------------------------------------
# Obligation 9's indicator, and its honest limits
# --------------------------------------------------------------------------


def test_follow_up_keeps_the_instruction_after_the_question():
    """The part that forces the structure is after the question mark.

    Taking the question alone left the overlap resting on `warum`, a generic
    interrogative that a drifted question would also match.
    """
    reply = 'Ich helfe meinem Bruder.\n\nWarum helfen Sie ihm? Antworten Sie mit „weil".'
    assert regression.follow_up(reply) == 'Warum helfen Sie ihm? Antworten Sie mit „weil".'


def test_follow_up_is_empty_when_the_reply_asks_nothing():
    assert regression.follow_up("Richtig. Gut gemacht.") == ""


def test_on_target_separates_a_real_follow_up_from_a_drifted_one():
    row = regression.elicitation_rows()[regression.COLD_START_KEY]
    good = regression.on_target(
        'Warum brauchen Sie Deutsch? Antworten Sie bitte mit dem Wort „weil".', row
    )
    drift = regression.on_target("Was haben Sie am Wochenende gemacht?", row)
    assert good["on_target"] is True
    assert "weil" in good["shared"]
    assert drift["on_target"] is False
    assert drift["shared"] == []


def test_content_words_drops_stopwords_and_short_tokens():
    assert regression.content_words("Sie haben ein Auto") == {"auto"}


# --------------------------------------------------------------------------
# Instrumentation must not change what the model sees
# --------------------------------------------------------------------------


def test_instrumenting_preserves_the_tool_surface():
    """ADK builds tool declarations from name, docstring and signature.

    Without functools.wraps the model would see a different tool surface than
    production does, and a run would be measuring the harness.
    """
    names = ("get_focus", "get_recent_errors", "log_error")
    before = {
        n: (getattr(agent, n).__name__, getattr(agent, n).__doc__,
            str(inspect.signature(getattr(agent, n))))
        for n in names
    }
    original = regression.instrument([])
    try:
        for n in names:
            after = (getattr(agent, n).__name__, getattr(agent, n).__doc__,
                     str(inspect.signature(getattr(agent, n))))
            assert after == before[n]
    finally:
        regression.restore(original)
    assert agent.get_focus is tools.get_focus


def test_instrumentation_records_calls_in_order():
    trace = []
    original = regression.instrument(trace)
    try:
        agent.get_focus()
        agent.get_recent_errors()
    finally:
        regression.restore(original)
    assert [t["tool"] for t in trace] == ["get_focus", "get_recent_errors"]


# --------------------------------------------------------------------------
# A whole run, driven by a fake model
# --------------------------------------------------------------------------


class FakeRunner:
    def __init__(self, *args, **kwargs):
        class Sessions:
            async def create_session(self, **kwargs):
                return type("S", (), {"id": "sim"})()

        self.session_service = Sessions()

    async def close(self):
        pass


def drive(monkeypatch, categories, aufgabe_categories=("register", "word_order"),
          score="72 / 100", state_limit=True):
    """Install a fake model that calls the real tools with scripted answers."""
    step = {"n": -1}

    async def fake_turn(runner, session_id, text):
        # Behave the way ADK's flow does: the before-model callback runs first,
        # and a non-None return IS the model's answer, so no call is made. This
        # matters — without it the silence test would pass trivially, because a
        # fake model that never consults the gate can never be blocked by it.
        gated = agent.gate(None, None)
        if gated is not None:
            return gated.content.parts[0].text
        step["n"] += 1
        if text.startswith("SESSION_START mode=gespraech"):
            agent.get_focus()
            agent.get_recent_errors()
            return 'Warum lernen Sie Deutsch? Antworten Sie mit „weil".'
        if text.startswith("SESSION_START mode=aufgabe"):
            limit = "20 Minuten" if state_limit else "eine Weile"
            return f"Schreiben Sie eine formelle Nachricht. Länge: ca. 80 Wörter. Zeitlimit: {limit}."
        if text.startswith("SUBMISSION"):
            for category in aufgabe_categories:
                agent.log_error("x", "y", category, "sim", "sim.", "blocking",
                                "aufgabe", "formal_message")
            return f"Korrigiert. Erfüllung: gut. Gesamt: {score}. Über der 60-Prozent-Linie."
        index = step["n"]
        category = categories[index - 1] if index - 1 < len(categories) else None
        if category:
            agent.log_error(text, text + " ok", category, "sim", "sim.",
                            "blocking", "gespraech")
        return 'Korrigiert.\n\nWarum ist das so? Antworten Sie mit „weil".'

    monkeypatch.setattr(regression, "one_turn", fake_turn)
    monkeypatch.setattr(regression, "InMemoryRunner", FakeRunner)


ALL_RIGHT = ["case", "konjunktiv_ii", "adjective_endings", "word_order", "register"]


def test_a_perfect_run_passes_everything(monkeypatch):
    drive(monkeypatch, ALL_RIGHT)
    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))
    summary = regression.summarise([result])
    assert [row["verdict"] for row in result["sentences"]] == ["exact"] * 5
    assert result["obligations"]["o8_get_focus_called_before_first_output"]
    assert result["obligations"]["o4_get_recent_errors_called_at_start"]
    assert result["aufgabe"]["verdict"] == "exact"
    assert summary["all_passed"] is True


def test_a_narrated_log_error_fails_obligation_2(monkeypatch):
    """The silent failure this harness was extended to catch.

    Session 3 saw the Aufgabe scoring turn print the log_error arguments as a
    markdown list and write nothing. On screen it looked perfect.
    """
    drive(monkeypatch, ALL_RIGHT, aufgabe_categories=())
    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))
    assert result["aufgabe"]["o2_log_error_called"] is False
    assert result["aufgabe"]["lines_written"] == 0
    assert regression.summarise([result])["obligations_ok"] is False


def test_a_missing_score_fails_obligation_6(monkeypatch):
    drive(monkeypatch, ALL_RIGHT, score="sehr gut")
    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))
    assert result["aufgabe"]["o6_score_out_of_100"] is False
    assert regression.summarise([result])["obligations_ok"] is False


def test_a_task_that_hides_the_time_limit_fails_obligation_10(monkeypatch):
    drive(monkeypatch, ALL_RIGHT, state_limit=False)
    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))
    assert result["aufgabe"]["o10_task_states_time_limit"] is False
    assert regression.summarise([result])["obligations_ok"] is False


def test_the_silence_gate_is_exercised_inside_a_real_run(monkeypatch):
    """Obligation 10's code enforcement, checked at zero model calls."""
    drive(monkeypatch, ALL_RIGHT)
    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))
    assert result["aufgabe"]["o10_silence_held"] is True
    assert result["aufgabe"]["o10_model_calls_while_drafting"] == 0
    assert agent.STATE["drafting"] is False


def test_a_wrong_category_is_reported_as_wrong(monkeypatch):
    drive(monkeypatch, ["case", "konjunktiv_ii", "gender", "word_order", "register"])
    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))
    assert result["sentences"][2]["verdict"] == "wrong"
    assert result["sentences"][2]["observed"] == ["gender"]
    assert regression.summarise([result])["categories_ok"] is False


def test_aufgabe_lines_carry_the_closed_mode_and_task_type(monkeypatch):
    drive(monkeypatch, ALL_RIGHT)
    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))
    assert result["aufgabe"]["modes_written"] == ["aufgabe"]
    assert result["aufgabe"]["task_types_written"] == ["formal_message"]


# --------------------------------------------------------------------------
# The property that matters most
# --------------------------------------------------------------------------


def test_harness_never_touches_the_real_log(monkeypatch):
    """A check that pollutes the state it measures is worse than no check.

    Every later get_focus() and every weekly review would be reading test data.
    The fake model here really calls log_error, so the write path is genuinely
    exercised - it just has to land in the sandbox.
    """
    real_log = Path(tools.LOG_PATH)
    real_cards = Path(tools.CARDS_PATH)
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    before = (digest(real_log), digest(real_cards))

    drive(monkeypatch, ALL_RIGHT)
    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))

    assert (digest(real_log), digest(real_cards)) == before
    assert tools.LOG_PATH == real_log            # restored
    assert tools.CARDS_PATH == real_cards
    assert not Path(result["sandbox_log"]).parent.exists()   # cleaned up
    assert result["aufgabe"]["lines_written"] >= 1           # writes did happen


def test_paths_are_restored_even_when_a_run_raises(monkeypatch):
    async def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(regression, "one_turn", explode)
    monkeypatch.setattr(regression, "InMemoryRunner", FakeRunner)
    real_log, real_cards = tools.LOG_PATH, tools.CARDS_PATH

    result = asyncio.run(regression.run_once(1, "SIMULATED", pace=0))

    assert "RuntimeError: boom" in result["aborted"]
    assert (tools.LOG_PATH, tools.CARDS_PATH) == (real_log, real_cards)
    assert all(row["verdict"] == "not_run" for row in result["sentences"])


# --------------------------------------------------------------------------
# Quota
# --------------------------------------------------------------------------


def test_a_429_stops_the_whole_invocation(monkeypatch, tmp_path):
    """No retry and no backoff: they hide the ceiling, and the ceiling is data.

    Before this, each remaining run burned one more call rediscovering that the
    daily quota was still gone.
    """
    launched = []

    async def quota_run(index, model, pace):
        launched.append(index)
        run = regression.skipped_run(index, "x")
        run.update({"aborted": "HTTP 429: ... limit: 20 ...", "quota": True,
                    "model": model})
        return run

    # main() guards on a non-empty key before it launches anything, so without
    # this the guard returns EXIT_INCOMPLETE and no run is ever attempted. The
    # value is never sent anywhere: run_once is monkeypatched above. Set here
    # rather than in a fixture so the suite stays green on a fresh clone, which
    # has no .env at all -- load_dotenv does not override an existing variable.
    monkeypatch.setenv("GOOGLE_API_KEY", "not-a-real-key")
    monkeypatch.setattr(regression, "run_once", quota_run)
    monkeypatch.setattr(tools, "LOG_PATH", tmp_path / "log.jsonl")
    (tmp_path / "log.jsonl").write_text("")

    code = regression.main(["--runs", "3", "--pace", "0"])

    assert launched == [1]
    assert code == regression.EXIT_INCOMPLETE


def test_skipped_runs_are_never_scored_as_misses():
    """A sentence a run never reached is a quota failure, not a model failure."""
    run = regression.skipped_run(2, "not launched")
    summary = regression.summarise([run])
    assert all(s["runs_scored"] == 0 for s in summary["per_sentence"].values())
    assert summary["all_passed"] is False
