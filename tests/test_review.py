"""Unit tests for review.py, the weekly aggregation job.

Zero model calls, zero network. review.py imports nothing that could make one.

Why this file exists. Session 4 built review.py under a prompt that said
"review.py ONLY", verified every check by hand, and recorded in the build log
that this was "the largest omission of the session": everything in V2 through
V5 was hand-verified and *none of it was pinned*. It named the four tests that
should exist first. They are the first four sections below.

The most load-bearing of them is the ordering guard. review.py deliberately
does NOT call get_error_summary — it reproduces that function's window and its
tie ordering, because get_error_summary is hard-anchored to date.today() and
review.py must be able to re-run a past week. Two implementations of one rule
can drift silently, and the build log says of that risk: "V2.2 is the guard on
this and must be re-run if either file changes. It is currently a manual
check." It is no longer manual.
"""

import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

import review
import tools

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def log(tmp_path, monkeypatch):
    """Redirect the log, the cards and therefore the review file into tmp."""
    path = tmp_path / "data" / "log.jsonl"
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(tools, "LOG_PATH", path)
    monkeypatch.setattr(tools, "CARDS_PATH", tmp_path / "data" / "cards.csv")
    return path


def write(path, rows):
    """Write entries at day offsets from today. Raw, because log_error stamps
    its own date and a weekly report needs history."""
    lines = []
    for offset, category, severity in rows:
        day = (date.today() - timedelta(days=offset)).isoformat()
        lines.append(json.dumps({
            "id": f"{day}T09:00:00", "date": day, "mode": "gespraech",
            "task_type": None, "learner_text": f"falsch {category}",
            "correction": f"richtig {category}", "category": category,
            "detail": f"{category}_detail",
            "explanation_en": f"The rule for {category}.", "severity": severity,
        }, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# 1. The ordering guard: _ranked must agree with get_error_summary exactly
# --------------------------------------------------------------------------


def test_ranked_matches_get_error_summary_in_content_and_order(log):
    """V2.2. The one check standing between two implementations of one rule.

    get_error_summary returns dict(Counter(...).most_common()), which sorts by
    count descending with ties in first-seen order. _ranked reproduces that
    explicitly. If either changes, this fails and nothing else would.
    """
    write(log, [
        (6, "word_order", "blocking"), (5, "case", "blocking"),
        (5, "word_order", "blocking"), (4, "spelling", "minor"),
        (3, "case", "blocking"), (2, "word_order", "blocking"),
        (1, "konjunktiv_ii", "blocking"), (0, "passiv", "blocking"),
    ])
    entries, _ = tools._read_log()
    anchor = date.today()
    start = anchor - timedelta(days=review.WINDOW_DAYS - 1)
    window = [e for e in entries if start <= date.fromisoformat(e["date"]) <= anchor]

    ranked = review._ranked(tools._blocking(window))
    summary = tools.get_error_summary(review.WINDOW_DAYS)

    assert ranked == summary
    assert list(ranked) == list(summary), "tie ordering diverged"
    assert list(ranked)[:3] == ["word_order", "case", "konjunktiv_ii"]


def test_ranked_breaks_ties_in_first_seen_order(log):
    write(log, [(3, "passiv", "blocking"), (2, "case", "blocking")])
    entries, _ = tools._read_log()
    assert list(review._ranked(tools._blocking(entries))) == ["passiv", "case"]


def test_focus_breaks_ties_by_recency_not_first_seen(log):
    """The two tie-breaks differ on purpose, each mirroring its own function.

    The table follows get_error_summary; the focus follows get_focus, which the
    human ratified. When they disagree the report says so.
    """
    write(log, [(3, "passiv", "blocking"), (2, "case", "blocking")])
    entries, _ = tools._read_log()
    focus, tied = review._focus(tools._blocking(entries))
    assert focus == "case"
    assert tied == ["case", "passiv"]


# --------------------------------------------------------------------------
# 2. "No prior week" is not "a prior week of zero"
# --------------------------------------------------------------------------


def test_no_prior_week_renders_em_dash_never_zero(log):
    """V3.5. A prior column of 0 claims a clean week that never existed."""
    write(log, [(2, "word_order", "blocking"), (1, "case", "blocking")])
    report, _ = review.run()

    assert "No prior week to compare against" in report
    table = [line for line in report.splitlines() if line.startswith("| `")]
    assert table, "no delta table rendered"
    for row in table:
        assert row.rstrip().endswith("| — | — |"), row
    assert "**Total blocking** | **2** | — | — |" in report


def test_a_real_prior_week_produces_signed_deltas(log):
    write(log, [
        (13, "case", "blocking"), (12, "case", "blocking"),
        (11, "passiv", "blocking"),
        (5, "word_order", "blocking"), (4, "word_order", "blocking"),
        (3, "case", "blocking"),
    ])
    report, _ = review.run()
    assert "| `word_order` | 2 | 0 | +2 |" in report
    assert "| `case` | 1 | 2 | -1 |" in report
    assert "| `passiv` | 0 | 1 | -1 |" in report


def test_a_prior_week_that_exists_but_is_empty_says_so(log):
    write(log, [(13, "spelling", "minor"), (2, "case", "blocking")])
    report, _ = review.run()
    assert "prior week exists in the log but holds no blocking errors" in report


# --------------------------------------------------------------------------
# 3. An empty log must not destroy cards.csv
# --------------------------------------------------------------------------


def test_an_empty_log_leaves_an_existing_cards_file_untouched(log):
    """V3.2. export_anki_csv rewrites the whole file from the log, so at 06:00
    a log that has gone missing would silently delete a deck built over months,
    with no recovery: the log is the only source."""
    cards = Path(tools.CARDS_PATH)
    cards.parent.mkdir(parents=True, exist_ok=True)
    cards.write_text("vorne,hinten\n", encoding="utf-8")
    log.write_text("", encoding="utf-8")

    report, _ = review.run()

    assert cards.read_text(encoding="utf-8") == "vorne,hinten\n"
    assert "**Not regenerated.**" in report


def test_an_absent_log_does_not_create_cards(log):
    log.unlink(missing_ok=True)   # the fixture creates data/, never the file
    report, _ = review.run()
    assert not Path(tools.CARDS_PATH).exists()
    assert "No log file at" in report


def test_a_non_empty_log_does_regenerate_cards(log):
    write(log, [(1, "case", "blocking"), (0, "spelling", "minor")])
    report, _ = review.run()
    assert Path(tools.CARDS_PATH).exists()
    assert "regenerated: **2 rows**" in report


# --------------------------------------------------------------------------
# 4. Two runs of the same week must be byte-identical
# --------------------------------------------------------------------------


def test_two_runs_produce_identical_bytes(log):
    """V4.1. Anything that reads the clock breaks the ability to diff runs,
    which is the only way to tell whether a change helped."""
    write(log, [(3, "case", "blocking"), (1, "word_order", "blocking")])
    first, path = review.run()
    first_bytes = path.read_bytes()
    second, again = review.run()
    assert first == second
    assert again.read_bytes() == first_bytes


def test_no_clock_leaks_into_the_report(log):
    """The report may name dates from the data or the anchor, never a time."""
    write(log, [(1, "case", "blocking")])
    report, _ = review.run()
    assert "Generated by `review.py`" in report
    for token in (":0", ":1", ":2", ":3", ":4", ":5"):
        assert f"{token}:" not in report, "a wall-clock time reached the report"


# --------------------------------------------------------------------------
# Degenerate logs: every section still renders
# --------------------------------------------------------------------------


@pytest.mark.parametrize("rows, marker", [
    ([], "exists but holds no entries"),
    ([(1, "spelling", "minor"), (0, "vocabulary", "minor")], "No blocking errors this week"),
    ([(30, "case", "blocking")], "No entries at all in this window"),
])
def test_all_sections_render_whatever_the_data(log, rows, marker):
    """A report whose shape changes with the data forces the reader to work out
    whether a section is missing or the code broke."""
    write(log, rows) if rows else log.write_text("", encoding="utf-8")
    report, _ = review.run()
    for heading in ("## The log", "## Top 3 blocking categories",
                    "## Week on week", "## Next week's focus", "## Cards"):
        assert heading in report
    assert marker in report


def test_no_category_is_invented_when_nothing_is_blocking(log):
    write(log, [(1, "spelling", "minor")])
    report, _ = review.run()
    assert "**None.**" in report
    assert "no category is costing you exam points" in report


def test_malformed_lines_are_counted_in_the_report(log):
    write(log, [(1, "case", "blocking")])
    with open(log, "a", encoding="utf-8") as handle:
        handle.write('{"id": "truncated\n')
        handle.write("not json at all\n")
    report, _ = review.run()
    assert "**2 malformed line(s) were skipped**" in report


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def test_a_past_anchor_scopes_the_window_and_the_filename(log):
    write(log, [(20, "passiv", "blocking"), (1, "case", "blocking")])
    anchor = date.today() - timedelta(days=18)
    report, path = review.run(anchor)
    assert path.name == f"review-{anchor.isoformat()}.md"
    assert "`passiv`" in report
    assert "`case`" not in report.split("## Week on week")[0]


@pytest.mark.parametrize("argv, code", [
    (["2026-13-45"], review.EXIT_USAGE),
    ([(date.today() + timedelta(days=1)).isoformat()], review.EXIT_USAGE),
])
def test_bad_dates_exit_with_a_usage_error(argv, code):
    with pytest.raises(SystemExit) as exc:
        review.main(argv)
    assert exc.value.code == code


def test_an_unreadable_log_exits_1_with_an_empty_stdout(log, capsys):
    log.write_text("{}\n", encoding="utf-8")
    log.chmod(0o000)
    try:
        assert review.main([]) == review.EXIT_LOG_UNREADABLE
    finally:
        log.chmod(0o644)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "cannot read the error log" in captured.err


def test_review_runs_from_any_working_directory(tmp_path):
    """Paths derive from tools.LOG_PATH, itself resolved from tools.__file__.

    A cron line has no working directory of yours. This runs the real script as
    a subprocess against the real (0-byte or absent) log, from /tmp.
    """
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "review.py")],
        cwd=tmp_path, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)},
    )
    assert result.returncode == review.EXIT_OK, result.stderr
    assert "# Weekly review" in result.stdout
    assert str(PROJECT_ROOT / "data") in result.stdout


def test_review_never_opens_the_log_for_writing(log):
    """It is a reader. The digest and the inode must both survive a run."""
    write(log, [(1, "case", "blocking")])
    before = (log.read_bytes(), log.stat().st_ino)
    review.run()
    assert (log.read_bytes(), log.stat().st_ino) == before
