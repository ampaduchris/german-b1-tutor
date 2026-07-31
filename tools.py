"""Five deterministic functions. Zero model calls, ever.

This is the two thirds of the system that cannot hallucinate. Nothing here
imports ADK, opens a socket, or asks a model anything. Every function is
exactly reproducible and unit-testable, which is the whole point of the
deterministic boundary in tutorial section 3.

Per spec-v3.md section 4:

    log_error            appends one line          registered as a tool
    get_recent_errors    last n objects            registered as a tool
    get_focus            top blocking category     registered as a tool
    get_error_summary    counts by category        NOT registered
    export_anki_csv      writes cards.csv          NOT registered

Registration happens in session 3, in agent.py. Nothing in this file knows
that some of these will become tools; that is the point.

Storage is append-only JSON Lines at data/log.jsonl. One JSON object per
line, per the data contract in spec-v3.md section 3.
"""

import csv
import json
import logging
import os
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Paths and constants
# --------------------------------------------------------------------------

# Module-level rather than function parameters on purpose. Three of these
# functions become ADK tools in session 3, and every parameter of a registered
# function is published to the model in the tool schema. A `log_path` argument
# would invite the model to pass one. Tests override these attributes instead
# (monkeypatch.setattr), which is why every function reads them at call time
# rather than capturing them in a default argument.
PROJECT_ROOT = Path(__file__).resolve().parent
LOG_PATH = PROJECT_ROOT / "data" / "log.jsonl"
CARDS_PATH = PROJECT_ROOT / "data" / "cards.csv"

# The closed category set, spec-v3.md section 3, verbatim and in spec order.
# Defined exactly once. Every validation and every count reads this constant,
# so the list cannot drift between functions.
CATEGORIES = (
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

# spec-v3.md section 3: "severity splits errors that cost exam points from
# stylistic wobble. Only blocking drives elicitation and the weekly focus."
SEVERITIES = ("blocking", "minor")

# spec-v3.md section 4: get_focus works over "the last 20".
FOCUS_WINDOW = 20


# --------------------------------------------------------------------------
# Internal helpers. Not part of the five functions the spec lists.
# --------------------------------------------------------------------------


def _validate_choice(value: object, allowed: tuple[str, ...], field: str) -> str:
    """Reject anything not in the closed set. Never coerce, never nearest-match.

    This is the single most load-bearing function in the file. spec-v3.md
    section 9 lists "invented category labels" as a failure mode whose fix is
    "validate category in log_error, reject unknowns", and tutorial section 8
    explains why: a field you intend to count must be constrained at write
    time, because cleaning it later does not work.

    Case-sensitive on purpose. "Case" does not become "case". Normalising is
    a form of cleaning, and accepting near misses teaches the caller that the
    closed set is advisory. See the build log, marked [AMBIGUOUS].
    """
    if not isinstance(value, str) or value not in allowed:
        raise ValueError(
            f"Invalid {field}: {value!r}. "
            f"{field} must be exactly one of: {', '.join(allowed)}. "
            "Values are case-sensitive and are never coerced or nearest-matched."
        )
    return value


def _read_log(path: Path | None = None) -> tuple[list[dict], int]:
    """Read every valid entry, skipping and counting malformed lines.

    spec-v3.md section 9 lists "one malformed line breaks the read" as a
    failure mode. One corrupt line must cost you that line and nothing else,
    so parsing is per line and a failure is counted rather than raised.

    Returns (entries, malformed_count). The count is returned so tests can
    assert on it exactly, and is also logged as a warning so a human running
    the agent sees that the log has damage.

    A missing file is not an error. It is an empty log, which is what a fresh
    clone has: data/ is gitignored, so it does not exist until first write.
    """
    path = Path(path) if path is not None else LOG_PATH

    if not path.exists():
        return [], 0

    entries: list[dict] = []
    malformed = 0

    with open(path, encoding="utf-8") as handle:
        for lineno, raw in enumerate(handle, start=1):
            stripped = raw.strip()
            if not stripped:
                # Blank lines carry no data and destroy none. Skipped silently
                # and not counted as damage.
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError as err:
                malformed += 1
                logger.warning("%s line %d: not valid JSON (%s)", path, lineno, err.msg)
                continue
            if not isinstance(obj, dict):
                malformed += 1
                logger.warning(
                    "%s line %d: valid JSON but not an object (%s)",
                    path,
                    lineno,
                    type(obj).__name__,
                )
                continue
            entries.append(obj)

    if malformed:
        logger.warning(
            "%s: skipped %d malformed line(s), returned %d valid entries",
            path,
            malformed,
            len(entries),
        )

    return entries, malformed


def _blocking(entries: list[dict]) -> list[dict]:
    """Entries that cost exam points and carry a category from the closed set.

    An entry whose category is not in CATEGORIES cannot be a focus and cannot
    be counted, so it is dropped here rather than silently distorting a total.
    That only happens if the log was hand-edited; log_error cannot write one.
    """
    kept = []
    for entry in entries:
        if entry.get("severity") != "blocking":
            continue
        if entry.get("category") not in CATEGORIES:
            logger.warning(
                "Ignoring entry %r: category %r is not in the closed set",
                entry.get("id"),
                entry.get("category"),
            )
            continue
        kept.append(entry)
    return kept


# --------------------------------------------------------------------------
# The five functions from spec-v3.md section 4
# --------------------------------------------------------------------------


def log_error(
    learner_text: str,
    correction: str,
    category: str,
    detail: str,
    explanation_en: str,
    severity: str,
    mode: str,
    task_type: str | None = None,
) -> dict:
    """Append exactly one error to the log. Registered as a tool.

    Validates `category` and `severity` against the closed sets and raises
    ValueError on anything else. Nothing is coerced and nothing is
    nearest-matched: an invalid value is rejected, so the caller has to fix it
    rather than have a wrong label silently recorded.

    `id` and `date` are generated here rather than accepted as arguments. The
    caller has no business deciding when an event happened, and in session 3
    the caller is a language model.

    `detail` is deliberately free text. It is the pressure valve that makes a
    closed category set tolerable: expressiveness lives there, where it cannot
    corrupt a count.

    Returns the entry that was written, so a caller can confirm what landed.
    """
    _validate_choice(category, CATEGORIES, "category")
    _validate_choice(severity, SEVERITIES, "severity")

    now = datetime.now()
    entry = {
        "id": now.isoformat(timespec="seconds"),
        "date": now.date().isoformat(),
        "mode": mode,
        "task_type": task_type,
        "learner_text": learner_text,
        "correction": correction,
        "category": category,
        "detail": detail,
        "explanation_en": explanation_en,
        "severity": severity,
    }

    path = LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    # ensure_ascii=False keeps umlauts as umlauts, so the log stays
    # human-readable and diffable, which spec-v3.md section 2 calls for.
    # json.dumps escapes any newline inside a value as \n, so a multi-line
    # learner_text cannot break the one-object-per-line format.
    line = json.dumps(entry, ensure_ascii=False) + "\n"

    # Atomicity, and its exact limit.
    #
    # Opening with "a" sets O_APPEND, so the kernel moves to end-of-file and
    # writes as one indivisible step. A previously written line therefore can
    # never be overwritten or interleaved, no matter when the process dies.
    # The line is serialised in full first and handed to a single write call,
    # so there is no window in which half a record has been written and the
    # rest is still being computed.
    #
    # What this does NOT promise: if the machine loses power mid-write, the
    # final line may land truncated. That is why _read_log skips and counts
    # malformed lines instead of raising. The guarantee is that damage is
    # confined to the record being written, never to the ones already there.
    #
    # fsync forces the write past the OS cache to the disk before this
    # function returns, so a crash immediately after logging does not lose the
    # entry that the model has already been told was saved.
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())

    return entry


def get_recent_errors(n: int = 20) -> list[dict]:
    """Return the last n entries, oldest first. Registered as a tool.

    A list slice, which is why it is a function and not a judgment. Order is
    chronological, matching the file, so the last element is the most recent
    error.

    Malformed lines are skipped, not raised on. A missing or empty log gives
    an empty list.
    """
    entries, _ = _read_log()
    if n <= 0:
        return []
    return entries[-n:]


def get_focus() -> str | None:
    """Return the most frequent blocking category in the last 20 entries.

    Registered as a tool. This is counting and sorting, which a model does
    unreliably and silently: spec-v3.md section 4 exists precisely because
    handing over twenty raw entries and asking which is most frequent invites
    a miscount that mis-aims the whole session with no error raised.

    The window is the last 20 entries of any severity, which are then filtered
    to blocking. Not the last 20 blocking entries. See the build log, marked
    [AMBIGUOUS].

    TIE-BREAK RULE: when two or more categories are tied on count, the one
    whose most recent blocking occurrence is latest in the log wins. Rationale:
    a tie means both are equally frequent, so recency is the only signal left
    that says which you are still getting wrong now. The alternative,
    alphabetical order, is deterministic but arbitrary, and would pin the agent
    to `adjective_endings` for as long as a tie persisted.

    Returns None when the window holds no blocking entries at all. None means
    "no focus available", and the caller should open with something else rather
    than be handed an invented category. Documented behaviour, not an accident.
    """
    entries, _ = _read_log()
    window = entries[-FOCUS_WINDOW:]
    blocking = _blocking(window)

    if not blocking:
        return None

    counts = Counter(entry["category"] for entry in blocking)
    highest = max(counts.values())
    tied = [category for category, count in counts.items() if count == highest]

    if len(tied) == 1:
        return tied[0]

    # Tie-break: latest most-recent occurrence wins. blocking is in file order,
    # so a later index is a more recent entry.
    most_recent_index = {}
    for index, entry in enumerate(blocking):
        most_recent_index[entry["category"]] = index

    return max(tied, key=lambda category: most_recent_index[category])


def get_error_summary(days: int = 7) -> dict[str, int]:
    """Count blocking errors by category over the last `days` days.

    NOT registered as a tool. It is arithmetic with no argument a model needs
    to choose, and its consumer is review.py, which is code.

    The window is `days` calendar days ending today, inclusive: days=7 means
    today and the six days before it. Entries are selected on their `date`
    field, not their `id`. See the build log, marked [AMBIGUOUS].

    Returns a dict of category to count, ordered most frequent first, omitting
    categories with no errors in the window. An empty dict means a clean week,
    or an empty log.
    """
    entries, _ = _read_log()
    cutoff = date.today() - timedelta(days=max(days, 1) - 1)

    in_window = []
    for entry in _blocking(entries):
        raw_date = entry.get("date")
        try:
            entry_date = date.fromisoformat(str(raw_date))
        except (TypeError, ValueError):
            logger.warning(
                "Ignoring entry %r: unparseable date %r", entry.get("id"), raw_date
            )
            continue
        if entry_date >= cutoff:
            in_window.append(entry)

    counts = Counter(entry["category"] for entry in in_window)
    return dict(counts.most_common())


def export_anki_csv() -> int:
    """Write every logged error to data/cards.csv for Anki import.

    NOT registered as a tool. String formatting, no judgment.

    Two columns, no header row: front is the learner's own wrong sentence,
    back is the correction plus the English explanation plus the category in
    brackets. No header, because Anki imports the first row as a note unless
    told otherwise, and a header row would become a card. Column choice is
    [AMBIGUOUS]; the spec asks only that the file import without
    transformation.

    Every entry is exported, not just blocking ones. spec-v3.md section 4
    marks get_error_summary "blocking only" and does not mark this function,
    so the asymmetry is read as deliberate: minor errors are still worth
    drilling even though they do not drive the weekly focus.

    Written to a temporary file and moved into place with os.replace, which is
    atomic. An interrupted export therefore leaves the previous cards.csv
    intact rather than half-written. Note the contrast with log_error: appends
    want O_APPEND, whole-file regeneration wants write-then-rename.

    Returns the number of rows written.
    """
    entries, _ = _read_log()

    path = CARDS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")

    rows = 0
    with open(temporary, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for entry in entries:
            learner_text = entry.get("learner_text")
            correction = entry.get("correction")
            if not learner_text or not correction:
                logger.warning(
                    "Skipping entry %r: missing learner_text or correction",
                    entry.get("id"),
                )
                continue
            explanation = entry.get("explanation_en") or ""
            category = entry.get("category") or ""
            back = f"{correction} — {explanation} [{category}]"
            writer.writerow([learner_text, back])
            rows += 1

    os.replace(temporary, path)
    return rows
