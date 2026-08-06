"""Unit tests for the deterministic layer.

Zero model calls, zero network, no ADK import. Every assertion here is exact,
which is the whole argument of tutorial section 3: this is the part of the
system that can be tested rather than merely observed.

THE FIXTURE AND ITS KNOWN ANSWERS
---------------------------------
tests/fixtures/log_sample.jsonl holds 14 entries drawn from the closed
category set in spec-v3.md section 3, dated 2026-07-25 to 2026-07-31.

    severity   count
    blocking       9
    minor          5

    blocking by category        all severities by category
    word_order          3       spelling            4   <- decoy
    case                2       word_order          3
    adjective_endings   1       case                2
    konjunktiv_ii       1       adjective_endings   1
    passiv              1       konjunktiv_ii       1
    register            1       passiv              1
                                register            1
                                vocabulary          1

    get_focus()  ->  "word_order"        DOCUMENTED KNOWN ANSWER

The four `spelling` entries are a deliberate decoy. They are the most frequent
category in the file, and they are all `minor`. An implementation that counted
every entry rather than only the blocking ones would answer "spelling", so the
fixture discriminates between the correct rule and the most likely wrong one
rather than merely agreeing with the code.

Entry 14 contains commas, a colon, double quotes and an umlaut, so the CSV
export is exercised against the characters most likely to break a naive
formatter.
"""

import csv
import json
import logging
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import tools

# Mirrors the tables above. Kept as literals, not computed from the fixture,
# so that a test fails if someone edits the fixture without re-reading this.
FIXTURE_ENTRY_COUNT = 14
FIXTURE_BLOCKING_COUNT = 9
FIXTURE_EXPECTED_FOCUS = "word_order"
FIXTURE_BLOCKING_COUNTS = {
    "word_order": 3,
    "case": 2,
    "adjective_endings": 1,
    "konjunktiv_ii": 1,
    "passiv": 1,
    "register": 1,
}
FIXTURE_OLDEST_DATE = date(2026, 7, 25)

# The thirteen categories, retyped from spec-v3.md section 3 rather than
# imported from tools.py. A test that reads the constant it is checking proves
# nothing; this one fails if the code drifts from the spec.
SPEC_CATEGORIES = (
    "case",
    "gender",
    "adjective_endings",
    "word_order",
    "verb_form",
    "connectors",
    "prepositions",
    "konjunktiv_ii",
    "passiv",
    "relative_clauses",
    "vocabulary",
    "register",
    "spelling",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Every field of the data contract in spec-v3.md section 3, in order.
CONTRACT_FIELDS = (
    "id",
    "date",
    "mode",
    "task_type",
    "learner_text",
    "correction",
    "category",
    "detail",
    "explanation_en",
    "severity",
)


def write_raw(path, lines):
    """Write literal lines to a log, bypassing log_error entirely.

    Needed for the adversarial tests: log_error cannot produce a malformed
    line, so damage has to be injected the way it would really arrive, by a
    crash or a hand edit.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def entry(**overrides):
    """A dict in the shape log_error writes, for building raw fixtures."""
    payload = {
        "id": "2026-07-25T09:00:00",
        "date": "2026-07-25",
        "mode": "conversation",
        "task_type": None,
        "learner_text": "Ich helfe meinen Bruder.",
        "correction": "Ich helfe meinem Bruder.",
        "category": "case",
        "detail": "dative_object_after_helfen",
        "explanation_en": "helfen governs the dative.",
        "severity": "blocking",
    }
    payload.update(overrides)
    return payload


def days_covering_fixture():
    """A `days` window wide enough to include every fixture entry, forever.

    The fixture carries fixed dates. Hard-coding days=7 would make these tests
    pass this week and fail next month, which is the kind of test that teaches
    you to ignore a red suite.
    """
    return max((date.today() - FIXTURE_OLDEST_DATE).days + 1, 1)


# --------------------------------------------------------------------------
# Spec conformance: the closed sets
# --------------------------------------------------------------------------


def test_categories_match_spec_exactly_and_in_order():
    assert tools.CATEGORIES == SPEC_CATEGORIES
    assert len(tools.CATEGORIES) == 13


def test_categories_are_a_single_immutable_constant():
    assert isinstance(tools.CATEGORIES, tuple)


def test_severities_are_blocking_and_minor():
    assert tools.SEVERITIES == ("blocking", "minor")


# --------------------------------------------------------------------------
# log_error: validation. Reject, never coerce, never nearest-match.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("category", SPEC_CATEGORIES)
def test_every_spec_category_is_accepted(write_entry, category):
    written = write_entry(category=category)
    assert written["category"] == category


@pytest.mark.parametrize("severity", ["blocking", "minor"])
def test_both_severities_are_accepted(write_entry, severity):
    assert write_entry(severity=severity)["severity"] == severity


def test_unknown_category_raises_and_names_the_value(write_entry, temp_log):
    with pytest.raises(ValueError) as excinfo:
        write_entry(category="kasus")
    message = str(excinfo.value)
    assert "kasus" in message
    assert "category" in message
    assert not temp_log.exists(), "a rejected entry must not reach the log"


def test_unknown_severity_raises_and_names_the_value(write_entry, temp_log):
    with pytest.raises(ValueError) as excinfo:
        write_entry(severity="critical")
    message = str(excinfo.value)
    assert "critical" in message
    assert "severity" in message
    assert not temp_log.exists()


@pytest.mark.parametrize("wrong_case", ["Case", "CASE", "Word_Order", "Blocking"])
def test_case_variants_are_rejected_not_normalised(write_entry, wrong_case, temp_log):
    """DECISION: differing only by case RAISES. It does not normalise.

    Recorded in the build log as [AMBIGUOUS]. The spec says "reject unknowns"
    and does not say whether "Case" is an unknown or a typo. Normalising is a
    form of cleaning, and tutorial section 8 is explicit that a counted field
    must be constrained at write time because cleaning it later does not work.
    A silent .lower() would also teach the caller that the closed set is
    advisory, and the caller is a language model.
    """
    field = "severity" if wrong_case == "Blocking" else "category"
    with pytest.raises(ValueError) as excinfo:
        write_entry(**{field: wrong_case})
    assert wrong_case in str(excinfo.value)
    assert not temp_log.exists()


@pytest.mark.parametrize("bad", [None, 42, ["case"], ""])
def test_non_string_categories_are_rejected(write_entry, bad):
    with pytest.raises(ValueError):
        write_entry(category=bad)


def test_rejection_message_lists_the_valid_options(write_entry):
    with pytest.raises(ValueError) as excinfo:
        write_entry(category="dative error")
    message = str(excinfo.value)
    for category in SPEC_CATEGORIES:
        assert category in message


# --------------------------------------------------------------------------
# mode and task_type: closed in session 5, after two sessions of being open
#
# Session 2 left these unvalidated and said so; session 3 chose the strings and
# could only enforce them in the prompt and the runtime, recording that this
# was "weaker than the category closure". `category` raised and `mode` did not,
# and once the vocabulary was settled that asymmetry had no defence.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["aufgabe", "gespraech"])
def test_both_modes_are_accepted(write_entry, mode):
    assert write_entry(mode=mode)["mode"] == mode


@pytest.mark.parametrize(
    "bad", ["conversation", "task", "Gespräch", "Aufgabe", "GESPRAECH", "", None, 2]
)
def test_every_other_mode_spelling_is_rejected(write_entry, temp_log, bad):
    """The four spellings for two modes the build log found across the
    documents are exactly what this closes."""
    with pytest.raises(ValueError) as excinfo:
        write_entry(mode=bad)
    assert "mode" in str(excinfo.value)
    assert not temp_log.exists()


@pytest.mark.parametrize(
    "task_type", ["informal_email", "forum_post", "formal_message"]
)
def test_the_three_task_types_are_accepted(write_entry, task_type):
    written = write_entry(mode="aufgabe", task_type=task_type)
    assert written["task_type"] == task_type


def test_task_type_may_be_omitted(write_entry):
    """Gespräch writes null, and Aufgabe is NOT forced to supply one.

    Nothing downstream reads this field, so refusing the write would trade a
    whole correction for a purely descriptive label.
    """
    assert write_entry(mode="gespraech", task_type=None)["task_type"] is None
    assert write_entry(mode="aufgabe", task_type=None)["task_type"] is None


@pytest.mark.parametrize("bad", ["email", "Formal_Message", "aufgabe_3", 1])
def test_an_invented_task_type_is_rejected(write_entry, temp_log, bad):
    with pytest.raises(ValueError) as excinfo:
        write_entry(mode="aufgabe", task_type=bad)
    assert "task_type" in str(excinfo.value)
    assert not temp_log.exists()


def test_reading_does_not_validate_mode(sample_log):
    """The committed fixture still holds the historical "conversation" spelling.

    Validation is at write time only, by design: closing a set must never make
    an existing log unreadable, or one decision would cost the whole history.
    """
    entries, malformed = tools._read_log()
    assert malformed == 0
    assert {e["mode"] for e in entries} == {"conversation", "task"}
    assert tools.get_focus() == "word_order"


# --------------------------------------------------------------------------
# log_error: the write itself
# --------------------------------------------------------------------------


def test_log_error_creates_a_missing_data_directory(write_entry, temp_log):
    assert not temp_log.parent.exists()
    write_entry()
    assert temp_log.exists()


def test_written_entry_has_every_contract_field_in_order(write_entry, temp_log):
    written = write_entry()
    on_disk = json.loads(temp_log.read_text(encoding="utf-8").splitlines()[0])
    assert tuple(on_disk.keys()) == CONTRACT_FIELDS
    assert on_disk == written


def test_id_and_date_are_generated_not_accepted(write_entry):
    written = write_entry()
    # Parses as the spec's second-resolution ISO timestamp.
    parsed = datetime.fromisoformat(written["id"])
    assert written["date"] == parsed.date().isoformat()
    assert parsed.microsecond == 0


def test_three_entries_round_trip_field_by_field(write_entry):
    """V2.1. Write three, read three back, compare field by field."""
    written = [
        write_entry(category="case", detail="one"),
        write_entry(category="word_order", detail="two", severity="minor"),
        write_entry(category="konjunktiv_ii", detail="three"),
    ]
    read_back = tools.get_recent_errors(3)
    assert len(read_back) == 3
    for original, returned in zip(written, read_back):
        for field in CONTRACT_FIELDS:
            assert returned[field] == original[field]


def test_umlauts_survive_the_round_trip(write_entry, temp_log):
    written = write_entry(learner_text="Ich möchte die Besprechung verschieben, weiß nicht wann.")
    assert tools.get_recent_errors(1)[0]["learner_text"] == written["learner_text"]
    # Not escaped to ö on disk: the log stays human-readable and diffable.
    assert "möchte" in temp_log.read_text(encoding="utf-8")


def test_embedded_newline_cannot_break_the_one_line_format(write_entry, temp_log):
    written = write_entry(learner_text="Zeile eins\nZeile zwei")
    assert len(temp_log.read_text(encoding="utf-8").splitlines()) == 1
    assert tools.get_recent_errors(1)[0]["learner_text"] == written["learner_text"]


def test_hundred_appends_all_parse_and_the_file_is_not_truncated(write_entry, temp_log):
    """V2.5. Appends must not corrupt one another."""
    for index in range(100):
        write_entry(detail=f"entry_{index}")

    text = temp_log.read_text(encoding="utf-8")
    assert text.endswith("\n"), "final line is truncated"

    lines = text.splitlines()
    assert len(lines) == 100
    parsed = [json.loads(line) for line in lines]
    assert [item["detail"] for item in parsed] == [f"entry_{i}" for i in range(100)]

    entries, malformed = tools._read_log(temp_log)
    assert (len(entries), malformed) == (100, 0)


def test_a_rejected_write_leaves_earlier_lines_untouched(write_entry, temp_log):
    write_entry(detail="first")
    before = temp_log.read_bytes()
    with pytest.raises(ValueError):
        write_entry(category="Kasus")
    assert temp_log.read_bytes() == before


# --------------------------------------------------------------------------
# get_recent_errors
# --------------------------------------------------------------------------


def test_get_recent_errors_returns_the_last_n_chronologically(write_entry):
    for index in range(5):
        write_entry(detail=f"e{index}")
    recent = tools.get_recent_errors(3)
    assert [item["detail"] for item in recent] == ["e2", "e3", "e4"]


def test_get_recent_errors_defaults_to_twenty(write_entry):
    for index in range(25):
        write_entry(detail=f"e{index}")
    assert len(tools.get_recent_errors()) == 20


def test_get_recent_errors_clamps_to_what_exists(write_entry):
    write_entry()
    assert len(tools.get_recent_errors(20)) == 1


@pytest.mark.parametrize("n", [0, -1])
def test_get_recent_errors_with_non_positive_n(write_entry, n):
    write_entry()
    assert tools.get_recent_errors(n) == []


# --------------------------------------------------------------------------
# get_focus
# --------------------------------------------------------------------------


def test_get_focus_on_the_fixture_returns_the_documented_answer(sample_log):
    """V2.2. The known answer is word_order, documented at the top of this file."""
    assert tools.get_focus() == FIXTURE_EXPECTED_FOCUS


def test_get_focus_ignores_minor_entries(temp_log):
    write_raw(
        temp_log,
        [json.dumps(entry(category="spelling", severity="minor")) for _ in range(5)]
        + [json.dumps(entry(category="case", severity="blocking")) for _ in range(2)],
    )
    assert tools.get_focus() == "case"


def test_get_focus_window_is_the_last_twenty_entries(temp_log):
    """Entries 21 and older cannot influence the focus."""
    old = [json.dumps(entry(category="passiv", detail=f"old{i}")) for i in range(10)]
    recent = [json.dumps(entry(category="connectors", detail=f"new{i}")) for i in range(20)]
    write_raw(temp_log, old + recent)
    assert tools.get_focus() == "connectors"


def test_get_focus_returns_none_when_no_blocking_entries(temp_log):
    """V3.7. Documented behaviour: None means no focus available."""
    write_raw(
        temp_log,
        [json.dumps(entry(category="spelling", severity="minor")) for _ in range(4)],
    )
    assert tools.get_focus() is None


def test_get_focus_tie_break_most_recent_occurrence_wins(temp_log):
    """V3.8. Two-way tie, two-two. The later-occurring category wins."""
    write_raw(
        temp_log,
        [
            json.dumps(entry(category="case", detail="a")),
            json.dumps(entry(category="word_order", detail="b")),
            json.dumps(entry(category="case", detail="c")),
            json.dumps(entry(category="word_order", detail="d")),
        ],
    )
    assert tools.get_focus() == "word_order"


def test_get_focus_tie_break_is_recency_not_alphabetical_order(temp_log):
    """The same tie with the order reversed must flip the answer.

    This is the test that distinguishes the documented rule from an accident:
    alphabetically `case` precedes `word_order`, so a sort-based tie-break
    would answer `case` in both directions.
    """
    write_raw(
        temp_log,
        [
            json.dumps(entry(category="word_order", detail="a")),
            json.dumps(entry(category="case", detail="b")),
            json.dumps(entry(category="word_order", detail="c")),
            json.dumps(entry(category="case", detail="d")),
        ],
    )
    assert tools.get_focus() == "case"


def test_get_focus_ignores_a_category_outside_the_closed_set(temp_log):
    """A hand-edited log cannot introduce a focus log_error would have refused."""
    write_raw(
        temp_log,
        [json.dumps(entry(category="Kasus")) for _ in range(5)]
        + [json.dumps(entry(category="gender"))],
    )
    assert tools.get_focus() == "gender"


# --------------------------------------------------------------------------
# get_error_summary
# --------------------------------------------------------------------------


def test_error_summary_on_the_fixture_matches_the_documented_counts(sample_log):
    """V2.3. Counts must equal the documented blocking mix and sum to 9."""
    summary = tools.get_error_summary(days=days_covering_fixture())
    assert summary == FIXTURE_BLOCKING_COUNTS
    assert sum(summary.values()) == FIXTURE_BLOCKING_COUNT


def test_error_summary_is_ordered_most_frequent_first(sample_log):
    summary = tools.get_error_summary(days=days_covering_fixture())
    counts = list(summary.values())
    assert counts == sorted(counts, reverse=True)


def test_error_summary_excludes_minor_entries(temp_log):
    write_raw(
        temp_log,
        [
            json.dumps(entry(category="case", severity="blocking", date=date.today().isoformat())),
            json.dumps(entry(category="spelling", severity="minor", date=date.today().isoformat())),
        ],
    )
    assert tools.get_error_summary(days=7) == {"case": 1}


def test_error_summary_window_excludes_older_entries(temp_log):
    today = date.today()
    write_raw(
        temp_log,
        [
            json.dumps(entry(category="case", date=(today - timedelta(days=30)).isoformat())),
            json.dumps(entry(category="passiv", date=(today - timedelta(days=6)).isoformat())),
            json.dumps(entry(category="passiv", date=today.isoformat())),
        ],
    )
    # days=7 is today plus the six days before it, inclusive.
    assert tools.get_error_summary(days=7) == {"passiv": 2}


def test_error_summary_boundary_is_inclusive(temp_log):
    today = date.today()
    write_raw(
        temp_log,
        [
            json.dumps(entry(category="case", date=(today - timedelta(days=6)).isoformat())),
            json.dumps(entry(category="gender", date=(today - timedelta(days=7)).isoformat())),
        ],
    )
    assert tools.get_error_summary(days=7) == {"case": 1}


def test_error_summary_skips_an_unparseable_date(temp_log):
    write_raw(
        temp_log,
        [
            json.dumps(entry(category="case", date="not-a-date")),
            json.dumps(entry(category="gender", date=date.today().isoformat())),
        ],
    )
    assert tools.get_error_summary(days=7) == {"gender": 1}


# --------------------------------------------------------------------------
# export_anki_csv
# --------------------------------------------------------------------------


def test_export_writes_one_row_per_entry(sample_log):
    """V2.4. All 14 entries export, minor ones included."""
    assert tools.export_anki_csv() == FIXTURE_ENTRY_COUNT
    with open(tools.CARDS_PATH, encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == FIXTURE_ENTRY_COUNT
    assert all(len(row) == 2 for row in rows)


def test_export_front_is_the_learner_sentence(sample_log):
    tools.export_anki_csv()
    with open(tools.CARDS_PATH, encoding="utf-8", newline="") as handle:
        first = next(csv.reader(handle))
    assert first[0] == "Wenn ich Zeit habe, ich gehe ins Kino."
    assert first[1].startswith("Wenn ich Zeit habe, gehe ich ins Kino.")
    assert "[word_order]" in first[1]


def test_export_survives_commas_quotes_and_umlauts(sample_log):
    tools.export_anki_csv()
    with open(tools.CARDS_PATH, encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    last = rows[-1]
    assert last[0] == 'Ich mache eine Entscheidung, wie mein Chef sagt: "so schnell wie möglich".'
    assert "möglich" in last[1]


def test_export_has_no_header_row(sample_log):
    tools.export_anki_csv()
    with open(tools.CARDS_PATH, encoding="utf-8", newline="") as handle:
        first = next(csv.reader(handle))
    assert first[0] != "front"


def test_export_leaves_no_temporary_file_behind(sample_log):
    tools.export_anki_csv()
    leftovers = list(tools.CARDS_PATH.parent.glob("*.tmp"))
    assert leftovers == []


def test_export_skips_entries_with_no_learner_text(temp_log):
    write_raw(
        temp_log,
        [
            json.dumps(entry(learner_text="")),
            json.dumps(entry(detail="kept")),
        ],
    )
    assert tools.export_anki_csv() == 1


def test_export_on_an_absent_log_writes_an_empty_file(temp_log):
    assert tools.export_anki_csv() == 0
    assert tools.CARDS_PATH.exists()
    assert tools.CARDS_PATH.read_text(encoding="utf-8") == ""


# --------------------------------------------------------------------------
# Malformed lines. One corrupt entry costs you that entry and nothing else.
# --------------------------------------------------------------------------


def test_malformed_line_is_skipped_and_neighbours_survive(temp_log):
    """V3.4. Damage is confined to the damaged line."""
    write_raw(
        temp_log,
        [
            json.dumps(entry(detail="before")),
            '{"id": "2026-07-26T10:00:00", "category": "case", "sev',  # truncated
            json.dumps(entry(detail="after")),
        ],
    )
    entries, malformed = tools._read_log(temp_log)
    assert malformed == 1
    assert [item["detail"] for item in entries] == ["before", "after"]


def test_malformed_count_is_surfaced_as_a_warning(temp_log, caplog):
    write_raw(temp_log, [json.dumps(entry()), "{not json at all"])
    with caplog.at_level(logging.WARNING, logger="tools"):
        tools.get_recent_errors()
    assert any("malformed" in record.getMessage() for record in caplog.records)


def test_valid_json_that_is_not_an_object_counts_as_malformed(temp_log):
    write_raw(temp_log, [json.dumps(entry()), "[1, 2, 3]", '"a bare string"'])
    entries, malformed = tools._read_log(temp_log)
    assert (len(entries), malformed) == (1, 2)


def test_blank_lines_are_ignored_and_not_counted_as_damage(temp_log):
    write_raw(temp_log, [json.dumps(entry()), "", "   ", json.dumps(entry())])
    entries, malformed = tools._read_log(temp_log)
    assert (len(entries), malformed) == (2, 0)


def test_every_reader_survives_a_malformed_line(temp_log):
    write_raw(
        temp_log,
        [
            json.dumps(entry(category="case", date=date.today().isoformat())),
            "}{ broken",
            json.dumps(entry(category="case", date=date.today().isoformat())),
        ],
    )
    assert len(tools.get_recent_errors()) == 2
    assert tools.get_focus() == "case"
    assert tools.get_error_summary(days=7) == {"case": 2}
    assert tools.export_anki_csv() == 2


# --------------------------------------------------------------------------
# Empty and absent logs. Sensible empty results, never an exception.
# --------------------------------------------------------------------------


def test_every_reader_on_an_empty_log(temp_log):
    """V3.5."""
    temp_log.parent.mkdir(parents=True, exist_ok=True)
    temp_log.write_text("", encoding="utf-8")
    assert tools.get_recent_errors() == []
    assert tools.get_focus() is None
    assert tools.get_error_summary() == {}
    assert tools.export_anki_csv() == 0


def test_every_reader_on_an_absent_log(temp_log):
    """V3.6."""
    assert not temp_log.exists()
    assert tools.get_recent_errors() == []
    assert tools.get_focus() is None
    assert tools.get_error_summary() == {}
    assert tools.export_anki_csv() == 0


def test_reading_an_absent_log_does_not_create_it(temp_log):
    tools.get_recent_errors()
    tools.get_focus()
    tools.get_error_summary()
    assert not temp_log.exists()


# --------------------------------------------------------------------------
# The fixture itself. If it drifts, the known answers above are lies.
# --------------------------------------------------------------------------


def test_fixture_is_fourteen_well_formed_contract_entries(sample_log):
    entries, malformed = tools._read_log(sample_log)
    assert malformed == 0
    assert len(entries) == FIXTURE_ENTRY_COUNT
    for item in entries:
        assert tuple(item.keys()) == CONTRACT_FIELDS
        assert item["category"] in tools.CATEGORIES
        assert item["severity"] in tools.SEVERITIES


def test_fixture_severity_split_is_nine_blocking_five_minor(sample_log):
    entries, _ = tools._read_log(sample_log)
    blocking = [item for item in entries if item["severity"] == "blocking"]
    assert len(blocking) == FIXTURE_BLOCKING_COUNT
    assert len(entries) - len(blocking) == 5


def test_fixture_decoy_holds_spelling_is_the_most_common_overall(sample_log):
    """The decoy only works if `spelling` really does outnumber `word_order`."""
    entries, _ = tools._read_log(sample_log)
    counts = {}
    for item in entries:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    assert counts["spelling"] == 4
    assert counts["word_order"] == 3
    assert max(counts.values()) == counts["spelling"]


# --------------------------------------------------------------------------
# Concurrency: the atomicity claim, demonstrated rather than argued
#
# Session 2 wrote: "What was NOT demonstrated is a process killed mid-write or
# two processes writing at once." The second half is demonstrable cheaply, and
# it is the half that matters here: log_error serialises the whole line first
# and hands it to one write() on a handle opened "a", so O_APPEND should make
# concurrent appends indivisible rather than interleaved.
# --------------------------------------------------------------------------


def test_two_processes_appending_concurrently_produce_no_torn_lines(tmp_path):
    log = tmp_path / "data" / "log.jsonl"
    writer = tmp_path / "writer.py"
    writer.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
        "import tools\n"
        "from pathlib import Path\n"
        f"tools.LOG_PATH = Path({str(log)!r})\n"
        "tag = sys.argv[1]\n"
        # Few iterations, big records. log_error fsyncs every write, so the
        # count is what costs seconds while the record SIZE is what makes a
        # torn line possible in the first place. 600+ byte lines, 20 each.
        "for i in range(20):\n"
        "    tools.log_error('x' * 200, 'y' * 200, 'case', f'{tag}_{i}',\n"
        "                    'z' * 200, 'blocking', 'gespraech')\n",
        encoding="utf-8",
    )
    procs = [
        subprocess.Popen([sys.executable, str(writer), tag])
        for tag in ("alpha", "beta")
    ]
    for proc in procs:
        assert proc.wait(timeout=120) == 0

    entries, malformed = tools._read_log(log)
    assert malformed == 0, "a line was torn by concurrent appends"
    assert len(entries) == 40
    details = {entry["detail"] for entry in entries}
    assert len(details) == 40, "an append overwrote another"
    assert all(len(entry["learner_text"]) == 200 for entry in entries)
