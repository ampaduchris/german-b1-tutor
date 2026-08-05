"""Weekly aggregation job. Zero model calls, zero network, ever.

Reads data/log.jsonl and nothing else. Writes data/review-YYYY-MM-DD.md and
regenerates data/cards.csv. It never opens the log for writing.

Per spec-v3.md section 6 the report carries four things: the top three blocking
categories with one example each, a week-on-week delta, next week's grammar
focus, and a regenerated cards.csv.

Written for the case spec-v3.md section 10 describes and tutorial section 6
teaches: a 06:00 invocation with no human present and no memory of any previous
run. Everything it knows arrives off disk. Four consequences shaped the code.

  1. No wall-clock time appears anywhere in the output. Two runs of the same
     week must produce byte-identical markdown or nobody can diff them, and a
     "generated at 06:00:03" line would destroy that for no information gain.
     Dates come from the data and the anchor, never from the moment of running.
  2. Every degenerate state of the log is a sentence in the report, not an
     exception. A missing log is a fact about the week. The four required
     sections are always emitted, whatever the data, so the shape of the mail
     a human skims at 06:05 does not change with the week.
  3. Every fatal path prints one sentence naming the file, the reason and the
     fix. The only reader is cron mail, and it does not have the source open.
  4. stdout is forced to UTF-8. Cron supplies no locale, and this report is
     full of umlauts.

Run:     uv run review.py [YYYY-MM-DD]
Import:  from review import run; markdown, path = run()

Exit codes: 0 success · 1 log unreadable · 2 usage error · 3 output unwritable.
"""

import argparse
import os
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import tools

# The one week the report covers, and how many categories it names.
# spec-v3.md section 6 says "top three"; get_error_summary's default is 7 days.
WINDOW_DAYS = 7
TOP_N = 3

# Exit codes. 2 is usage because that is what argparse already exits with on a
# malformed argument, and two different meanings for one code is exactly the
# ambiguity a human reading cron mail cannot resolve.
EXIT_OK = 0
EXIT_LOG_UNREADABLE = 1
EXIT_USAGE = 2
EXIT_OUTPUT_UNWRITABLE = 3


class ReviewError(Exception):
    """A fatal condition, carrying the exit code it should produce."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Paths. Derived from tools.LOG_PATH at call time, never captured at import.
# --------------------------------------------------------------------------


def review_path(anchor: date) -> Path:
    """Where this week's markdown lands: data/review-YYYY-MM-DD.md.

    Derived from tools.LOG_PATH rather than from __file__ so that the report
    always lands beside the log it describes, and so a test that redirects the
    log redirects the report with it. tools.LOG_PATH is itself absolute and
    resolved from tools.__file__, which is what makes this correct from any
    working directory.
    """
    return Path(tools.LOG_PATH).parent / f"review-{anchor.isoformat()}.md"


# --------------------------------------------------------------------------
# Reading. Read-only on the log, always.
# --------------------------------------------------------------------------


def read_log() -> tuple[list[dict], int]:
    """Every valid entry plus the malformed-line count. Never opens for write.

    Uses tools._read_log rather than the public get_recent_errors for two
    reasons. It returns the malformed-line count, which session 2 left
    available for exactly this caller, and which at 06:00 reaches a human only
    if this report carries it. And it keeps one parser for the log format:
    a second line-level JSON reader in this file would be the drift that
    spec-v3.md section 3 warns about, one layer up. Flagged in the build log.

    A missing file is not an error; it is an empty log. An unreadable one is,
    and is translated here into a sentence rather than a traceback.
    """
    try:
        return tools._read_log()
    except (OSError, UnicodeDecodeError) as err:
        raise ReviewError(
            f"cannot read the error log at {tools.LOG_PATH}: {err}. "
            "No review was produced and no file was written. "
            "Fix the file's permissions or restore it, then run review.py again.",
            EXIT_LOG_UNREADABLE,
        ) from err


def _dated(entries: list[dict]) -> tuple[list[tuple[date, dict]], int]:
    """Pair every entry with its parsed date. Count the ones that have none.

    An entry with an unparseable date cannot be placed in a week, so it cannot
    be counted. get_error_summary drops the same entries silently to a log
    warning; here the count is surfaced in the report, because a warning on
    stderr at 06:00 is only seen if somebody reads the mail closely.
    """
    dated: list[tuple[date, dict]] = []
    undated = 0
    for entry in entries:
        try:
            dated.append((date.fromisoformat(str(entry.get("date"))), entry))
        except (TypeError, ValueError):
            undated += 1
    return dated, undated


# --------------------------------------------------------------------------
# Arithmetic. This is the whole "intelligence" of the file, and it is counting.
# --------------------------------------------------------------------------


def _ranked(blocking: list[dict]) -> dict[str, int]:
    """Blocking counts by category, ordered exactly as get_error_summary orders.

    get_error_summary returns dict(Counter(...).most_common()). most_common
    sorts by count descending with a stable sort, so ties fall in first-seen
    order. That rule is reproduced explicitly here rather than inherited,
    because review.py cannot call get_error_summary: that function's window is
    anchored to date.today() and this file must be able to re-run a past week.
    Reproducing the order means the review can never disagree with the tool.
    Verified check V2.2. Deviation recorded in the build log.
    """
    counts = Counter(entry["category"] for entry in blocking)
    first_seen: dict[str, int] = {}
    for index, entry in enumerate(blocking):
        first_seen.setdefault(entry["category"], index)
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], first_seen[kv[0]]))
    return dict(ordered)


def _focus(blocking: list[dict]) -> tuple[str | None, list[str]]:
    """Next week's category, and the categories it was tied with.

    Frequency first; ties go to the category whose most recent blocking entry
    is latest, which is the rule get_focus already uses and the human ratified
    (build log, session 2 addendum item 3). One system, one tie-break, so the
    weekly report and the agent's live focus cannot be argued to disagree on
    principle. Note they can still name different categories on the same day,
    because get_focus looks at the last 20 entries and this looks at 7 days.

    Returns (None, []) when nothing blocking was logged. There is no default
    category: inventing a focus is the exact silent wrongness get_focus exists
    to prevent, and a cron run with nobody watching is where it would survive
    longest unnoticed.
    """
    if not blocking:
        return None, []
    counts = Counter(entry["category"] for entry in blocking)
    highest = max(counts.values())
    tied = [category for category, count in counts.items() if count == highest]
    if len(tied) == 1:
        return tied[0], []
    latest: dict[str, int] = {}
    for index, entry in enumerate(blocking):
        latest[entry["category"]] = index
    return max(tied, key=lambda category: latest[category]), sorted(tied)


def _example(blocking: list[dict], category: str) -> dict | None:
    """The most recent blocking entry in that category, or None.

    Most recent rather than first, because the report's question is what you
    are getting wrong now, not what you got wrong on Monday.
    """
    for entry in reversed(blocking):
        if entry.get("category") == category:
            return entry
    return None


def _oneline(value: object) -> str:
    """Collapse whitespace so a multi-line learner_text cannot break a table.

    log_error escapes newlines into the JSON, so they survive the round trip
    and arrive here as real newlines inside a value.
    """
    return " ".join(str(value).split()) if value else ""


def _delta(now: int, before: int) -> str:
    change = now - before
    return "0" if change == 0 else f"{change:+d}"


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------


def build_report(
    anchor: date,
    entries: list[dict],
    malformed: int,
    cards_line: str,
    log_present: bool,
) -> str:
    """The whole markdown report, as a string. No side effects, no clock.

    Pure apart from reading tools.LOG_PATH for display. Given the same
    arguments it returns the same bytes, which is what makes V4.1 possible.
    """
    start = anchor - timedelta(days=WINDOW_DAYS - 1)
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=WINDOW_DAYS - 1)

    dated, undated = _dated(entries)
    window = [entry for day, entry in dated if start <= day <= anchor]
    prior = [entry for day, entry in dated if prior_start <= day <= prior_end]
    earliest = min((day for day, _ in dated), default=None)

    # "No prior week" is not "a prior week of zero". The first means the log
    # does not reach back that far; the second means you logged nothing that
    # week. Flattening them produces a delta of -9 against a week that never
    # existed, which is the misleading zero this distinction exists to avoid.
    has_baseline = earliest is not None and earliest < start

    window_blocking = tools._blocking(window)
    prior_blocking = tools._blocking(prior)
    this_counts = _ranked(window_blocking)
    prior_counts = _ranked(prior_blocking)

    out: list[str] = []
    add = out.append

    add(f"# Weekly review — week ending {anchor.isoformat()}")
    add("")
    add(f"Window: **{start.isoformat()} to {anchor.isoformat()}**, "
        f"{WINDOW_DAYS} calendar days inclusive.")
    add("")

    # ---- state of the log ------------------------------------------------
    add("## The log")
    add("")
    if not log_present:
        add(f"**No log file at `{tools.LOG_PATH}`.** Nothing has ever been "
            "logged, so every section below is empty. This is the normal state "
            "of a fresh install. It is also what a wrong path or an unmounted "
            "disk looks like, so if you have been practising this week, that is "
            "the thing to check first.")
    elif not entries:
        add(f"**The log file `{tools.LOG_PATH}` exists but holds no entries.** "
            "Nothing has been logged yet. Every section below is empty for that "
            "reason and not because you had a clean week.")
    else:
        days_seen = len({day for day, _ in dated if start <= day <= anchor})
        add(f"`{tools.LOG_PATH}` — {len(entries)} entries in the whole log, "
            f"{len(window)} in this window, of which "
            f"**{len(window_blocking)} blocking**.")
        add("")
        add(f"Coverage: entries on {days_seen} of the {WINDOW_DAYS} days. "
            f"First entry in the log: {earliest.isoformat()}.")
        # Strictly after `start`: an earliest entry landing exactly on the first
        # day of the window is a full week, not a partial one.
        if earliest is not None and start < earliest <= anchor:
            covered = (anchor - earliest).days + 1
            add("")
            add(f"**Fewer than {WINDOW_DAYS} days of data.** The log begins "
                f"inside this window ({earliest.isoformat()}), so these counts "
                f"cover {covered} day(s), not {WINDOW_DAYS}. A category with a "
                "low count may simply have had fewer days to appear in.")
        elif earliest is not None and earliest > anchor:
            add("")
            add("**The log holds no entries on or before the anchor date.** "
                f"Its first entry is {earliest.isoformat()}, which is after "
                f"{anchor.isoformat()}. If you meant to review a past week, "
                "check the date you passed.")

    if malformed:
        add("")
        add(f"**{malformed} malformed line(s) were skipped** while reading the "
            "log. They are counted nowhere below. Open the file and look for a "
            "truncated line, most likely the last one written before a crash.")
    if undated:
        add("")
        add(f"**{undated} entry/entries have an unparseable `date` field** and "
            "could not be placed in any week. They are excluded from every "
            "count below.")
    add("")

    # ---- 1. top three blocking categories, one example each --------------
    add(f"## Top {TOP_N} blocking categories")
    add("")
    if not this_counts:
        if window:
            minor = len(window) - len(window_blocking)
            add(f"**No blocking errors this week.** The window holds "
                f"{len(window)} entries, {minor} of them non-blocking. Nothing "
                "here costs exam points.")
        else:
            add("**No entries at all in this window.** Nothing to rank.")
        add("")
    else:
        ranked = list(this_counts.items())
        for rank, (category, count) in enumerate(ranked[:TOP_N], start=1):
            add(f"### {rank}. `{category}` — {count}")
            add("")
            example = _example(window_blocking, category)
            if example is None:  # unreachable: the count came from these entries
                add("_No example available._")
            else:
                add(f"- Wrote: {_oneline(example.get('learner_text'))}")
                add(f"- Should be: {_oneline(example.get('correction'))}")
                add(f"- Why: {_oneline(example.get('explanation_en'))}")
                add(f"- Logged {example.get('date')} · "
                    f"`{_oneline(example.get('detail'))}`")
            add("")
        if len(ranked) > TOP_N:
            cut = ranked[TOP_N - 1][1]
            also = [c for c, n in ranked[TOP_N:] if n == cut]
            add(f"{len(ranked)} categories had blocking errors this week; "
                f"the rest are in the table below.")
            if also:
                add("")
                add(f"Note: rank {TOP_N} is tied at {cut} with "
                    + ", ".join(f"`{c}`" for c in also)
                    + ". Order among ties follows first appearance in the "
                      "window, which is how `get_error_summary` orders them.")
            add("")

    # ---- 2. week on week -------------------------------------------------
    add("## Week on week")
    add("")
    add(f"Prior window: {prior_start.isoformat()} to {prior_end.isoformat()}.")
    add("")
    if not has_baseline:
        add("**No prior week to compare against.** The log does not reach back "
            f"before {start.isoformat()}"
            + (f" — its first entry is {earliest.isoformat()}."
               if earliest is not None else ".")
            + " The prior-week column below reads `—`, not `0`: zero would say "
              "you made no errors that week, when the truth is that there was "
              "no week. There will be a real delta next Sunday.")
        add("")
    elif not prior_counts:
        add("The prior week exists in the log but holds no blocking errors, so "
            "every delta below is measured against a genuine zero.")
        add("")

    if this_counts or prior_counts:
        add("| Category | This week | Prior week | Delta |")
        add("|---|---:|---:|---:|")
        seen = list(this_counts)
        seen += [c for c in prior_counts if c not in this_counts]
        for category in seen:
            now = this_counts.get(category, 0)
            before = prior_counts.get(category, 0)
            if has_baseline:
                add(f"| `{category}` | {now} | {before} | {_delta(now, before)} |")
            else:
                add(f"| `{category}` | {now} | — | — |")
        total_now = len(window_blocking)
        total_before = len(prior_blocking)
        if has_baseline:
            add(f"| **Total blocking** | **{total_now}** | **{total_before}** "
                f"| **{_delta(total_now, total_before)}** |")
        else:
            add(f"| **Total blocking** | **{total_now}** | — | — |")
    else:
        add("_No blocking errors in either window, so there is nothing to "
            "compare._")
    add("")

    # ---- 3. next week's focus -------------------------------------------
    focus, tied = _focus(window_blocking)
    add("## Next week's focus")
    add("")
    if focus is None:
        if not entries:
            add("**None.** Nothing has been logged, so there is no evidence to "
                "choose a focus from. Run a session before next Sunday and this "
                "section will fill itself.")
        elif not window:
            add("**None.** No entries fall in this window. Nothing was "
                "practised, so nothing is prescribed.")
        else:
            add("**None.** Entries exist this week but none is `blocking`, so "
                "no category is costing you exam points. Keep going; there is "
                "nothing to aim at.")
    else:
        count = this_counts[focus]
        add(f"**`{focus}`** — {count} blocking error(s) this week"
            + (f", {prior_counts.get(focus, 0)} the week before."
               if has_baseline else ", with no prior week to compare."))
        if tied:
            add("")
            add("Chosen from a tie at "
                + f"{count} between " + ", ".join(f"`{c}`" for c in tied)
                + ". The tie-break is the category whose most recent blocking "
                  "error is latest, the same rule `get_focus` uses.")
        add("")
        add("Rule: the most frequent blocking category in the window. This is "
            "the week's verdict. `agent.py` still calls `get_focus()` live at "
            "the start of every session, which reads the last 20 entries rather "
            "than 7 days, so mid-week it may target something else. That is not "
            "a conflict; it is a shorter horizon.")
    add("")

    # ---- 4. cards --------------------------------------------------------
    add("## Cards")
    add("")
    add(cards_line)
    add("")
    add("---")
    add("")
    add(f"Report file: `{review_path(anchor)}`")
    add("Generated by `review.py`. No model was called, and the log was opened "
        "read-only.")
    add("")

    return "\n".join(out)


# --------------------------------------------------------------------------
# Side effects: two files written, neither of them the log
# --------------------------------------------------------------------------


def regenerate_cards(entries: list[dict]) -> str:
    """Rewrite data/cards.csv, unless the log is empty. Returns a report line.

    The guard is deliberate and is the one place this file refuses to do what it
    was told. export_anki_csv rewrites the whole file from the log, so an empty
    log produces an empty cards.csv — and at 06:00 with nobody watching, a log
    that has gone missing or is being read from the wrong path would silently
    destroy a deck you have been building for months. There is no recovery from
    within this system: the log is the only source. So an empty log leaves the
    previous cards.csv untouched and says so in the report. [AMBIGUOUS] The spec
    says "regenerated cards.csv" and does not consider the empty case.
    """
    if not entries:
        return (f"**Not regenerated.** The log holds no entries, and rewriting "
                f"`{tools.CARDS_PATH}` from an empty log would delete every card "
                "already in it with no way back. The existing file, if any, is "
                "untouched.")
    try:
        rows = tools.export_anki_csv()
    except OSError as err:
        raise ReviewError(
            f"cannot write the Anki export at {tools.CARDS_PATH}: {err}. "
            "The review was not written either. Check the directory's "
            "permissions and free space, then run review.py again.",
            EXIT_OUTPUT_UNWRITABLE,
        ) from err
    return (f"`{tools.CARDS_PATH}` regenerated: **{rows} rows**, one per logged "
            "error including non-blocking ones. Two columns, no header, ready "
            "to import.")


def write_report(path: Path, report: str) -> None:
    """Write the markdown, atomically, in UTF-8 with fixed newlines.

    Write-then-rename for the same reason export_anki_csv uses it: an
    interrupted run leaves last week's file intact rather than half of this
    week's. newline="\\n" is pinned so the bytes do not depend on the platform,
    which is what lets two runs be compared with cmp.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
        os.replace(temporary, path)
    except OSError as err:
        raise ReviewError(
            f"cannot write the review at {path}: {err}. "
            "The report was produced but not saved; it is on stdout above. "
            "Check the directory's permissions and free space, then run "
            "review.py again.",
            EXIT_OUTPUT_UNWRITABLE,
        ) from err


def run(anchor: date | None = None) -> tuple[str, Path]:
    """Do the whole job. Returns (markdown, path written). The importable entry.

    anchor is the last day of the week under review, defaulting to today. The
    default is the only thing in this file that reads the clock.
    """
    anchor = anchor or date.today()
    log_present = Path(tools.LOG_PATH).exists()
    entries, malformed = read_log()
    cards_line = regenerate_cards(entries)
    report = build_report(anchor, entries, malformed, cards_line, log_present)
    path = review_path(anchor)
    write_report(path, report)
    return report, path


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _parse_args(argv: list[str] | None) -> date:
    parser = argparse.ArgumentParser(
        prog="review.py",
        description="Weekly review of data/log.jsonl. No model calls, ever.",
        epilog="Exit codes: 0 ok, 1 log unreadable, 2 usage, 3 output unwritable.",
    )
    parser.add_argument(
        "date",
        nargs="?",
        help="Last day of the week to review, YYYY-MM-DD. Defaults to today. "
             "Pass a past date to re-run an earlier week.",
    )
    args = parser.parse_args(argv)
    if args.date is None:
        return date.today()
    try:
        anchor = date.fromisoformat(args.date)
    except ValueError:
        parser.error(
            f"not a date: {args.date!r}. Use YYYY-MM-DD, for example "
            f"{date.today().isoformat()}."
        )
    if anchor > date.today():
        # A future window can only ever be empty, so this is a typo every time.
        parser.error(
            f"{anchor.isoformat()} is in the future. A week ending then cannot "
            "have any data in it yet. Did you mean a date in the past?"
        )
    return anchor


def main(argv: list[str] | None = None) -> int:
    # Cron gives a process no locale, so stdout may default to ASCII and every
    # umlaut in this report would raise UnicodeEncodeError halfway through. This
    # is the single line that makes the difference between a review and a
    # traceback in the 06:05 mail. Guarded because stdout is not always a
    # TextIOWrapper: under pytest's capture, for instance, it is not.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    anchor = _parse_args(argv)
    try:
        report, _ = run(anchor)
    except ReviewError as err:
        print(f"review.py: {err}", file=sys.stderr)
        return err.code
    print(report)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
