"""Regression harness for prompts/tutor.md. The fixed check of spec section 11.

Runs the five planted-error sentences through the real agent and checks two
different things about what came back:

  1. CATEGORIES. The categories that reached `log_error`, compared against the
     categories the spec says those errors are. A set comparison, exact.
  2. OBLIGATIONS. Whether the standing contract in `tutor.md` was actually
     honoured on the wire: was `get_focus` called before the first German
     output, was `get_recent_errors` called at session start, was `log_error`
     called once per error rather than narrated in prose.

Run it before a prompt edit and after one, then diff the two JSON files. That
is the whole purpose: spec section 11 says "keep those five sentences as a
fixed regression check for every subsequent prompt edit", and tutorial section
7 asks "what is the smallest test that tells me whether this prompt edit
helped?". This is that test.

WHY NO MODEL GRADES THIS, and it is the load-bearing design decision here.

Correctness is `expected <= observed` on two Python sets of strings. Nothing
interprets, paraphrases or judges. If a model graded the output, three things
would break at once. First, the grader would have the same blind spots as the
model under test — a model that thinks a Dativ error is `prepositions` will
also accept `prepositions` as a reasonable grade for it, so the exact failure
spec section 12 names as the counter-evidence to watch would be the one failure
this harness could never see. Second, the result would stop being reproducible:
two runs over identical output could disagree, so a diff between two JSON files
would no longer isolate the prompt edit. Third, it would cost model calls, and
section 3 of the tutorial is that arithmetic and set membership are free,
exact, and unit-testable while a model call is none of those. The categories
are a closed set of thirteen strings precisely so that this comparison can be
mechanical. Using a model here would throw away the reason the set is closed.

WHAT IS EXACT AND WHAT IS ONLY AN INDICATOR

Obligations 2, 4 and 8 are checked by watching the tools actually get called,
so they are exact and they gate the exit code. Obligation 9 — "the follow-up
targets the same category for at least three consecutive turns" — cannot be
decided without language understanding, because `tutor.md` explicitly permits
re-topicking a question into the learner's own world. It is reported as a
lexical-overlap INDICATOR against the elicitation row that the live focus
selected, with the overlapping words printed so a human can see what drove the
verdict, and it deliberately does NOT gate the exit code. A heuristic that can
fail spuriously would make the whole suite flaky, and a flaky suite gets
ignored, which is the failure this file exists to prevent.

WHAT THIS HARNESS NEVER TOUCHES

`data/log.jsonl`. These runs are tests, not study, and a test that pollutes the
state under test corrupts every later `get_focus()` and every weekly review.
`tools.LOG_PATH` and `tools.CARDS_PATH` are redirected into a throwaway
directory for the duration of each run and restored afterwards. The real log is
checksummed before and after and both digests are printed, so the claim is
evidence rather than an assertion.

Run:  uv run scripts/regression.py [--runs 3] [--pace 25]

Results land in `data/regression-YYYY-MM-DD.json`, the filename the session
prompt specified. Consequence worth knowing before it bites: a second run on
the same day OVERWRITES the first. Copy the file aside before re-running if you
want to keep it. This is deliberate rather than fixed - inventing a filename
scheme would break the one the file was asked to have.

A 429 ends the whole invocation. No retry, no backoff: session 3 refused those
because they hide the free-tier ceiling behind a spinner, and the ceiling is
information you need. Measured ceiling on this key: 20 requests per day and 5
per minute, and one run of five sentences costs about 12.

Exit codes: 0 everything passed - 1 a category or an exact obligation failed
- 2 usage error - 3 a run could not complete (quota, network, no key).
"""

import argparse
import asyncio
import functools
import hashlib
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import errors as genai_errors  # noqa: E402
from google.genai import types  # noqa: E402

import agent  # noqa: E402
import tools  # noqa: E402

# ---------------------------------------------------------------------------
# The five sentences. spec-v3.md section 11, item 2.
#
# `expect` is a set because the comparison is a set comparison. Each holds one
# category today; it is a set so that a sentence carrying two planted errors
# could be added later without changing the grading rule.
#
# NOTE ON SENTENCE 3, because it was changed on 2026-08-05 and the change must
# not look like a test being edited until it passed. The original sentence was
# `Ich habe einen neuen Auto gekauft.`, which the pinned model categorised as
# `gender` in two independent runs, with the accurate detail `das_auto_is_neuter`.
# That sentence carries ONE underlying error - the learner believes `Auto` is
# masculine - surfacing in TWO morphological slots: the article (`einen` for
# `ein`) and the adjective ending (`neuen` for `neues`). `gender` is a
# defensible, arguably better, diagnosis of it, so the sentence does not
# isolate the adjective ending that spec section 11 says it plants, and no
# single expected category can be correct. The replacement keeps the article
# correct (`ein` IS neuter accusative) so the only error left is the adjective
# ending. The original finding is preserved in docs/BUILD-LOG.md session 5.
# ---------------------------------------------------------------------------

SENTENCES = (
    {
        "n": 1,
        "text": "Ich helfe meinen Bruder.",
        "expect": {"case"},
        "planted": "Dativ error: helfen governs the dative",
    },
    {
        "n": 2,
        "text": "Wenn ich Zeit habe, würde ich mehr lesen.",
        "expect": {"konjunktiv_ii"},
        "planted": "Konjunktiv II: an unreal condition needs hätte, not habe",
    },
    {
        "n": 3,
        "text": "Ich habe ein neuen Auto gekauft.",
        "expect": {"adjective_endings"},
        "planted": "adjective ending: after neuter `ein` the ending is -es, not -en",
    },
    {
        "n": 4,
        "text": "Wenn ich Zeit habe, ich gehe ins Kino.",
        "expect": {"word_order"},
        "planted": "word order: verb second after a subordinate clause",
    },
    {
        "n": 5,
        "text": "Sehr geehrter Herr Meier, kannst du mir helfen?",
        "expect": {"register"},
        "planted": "du/Sie slip in a formal message",
    },
)

SESSION_OPENER = "SESSION_START mode=gespraech"
COLD_START_KEY = "kein Fokus"

# Free-tier ceiling measured in build-log session 3 and confirmed by the API in
# session 5: 5 requests per minute and 20 per day on this model and key. One
# turn costs one or two model calls, so turns are paced apart rather than fired
# back to back. Set --pace 0 to disable.
DEFAULT_PACE = 25.0
DEFAULT_RUNS = 3

# Obligation 9's three-turn minimum, spec section 5.4.
TARGET_TURNS = 3

# Words dropped before the obligation-9 overlap check. Short and deliberately
# incomplete: it exists to stop `Sie`, `haben` and friends matching everything,
# not to be a German stopword list. Tokens under 4 characters are dropped too.
STOPWORDS = frozenset("""
    sie ihr ihre ihren ihrem haben hatte sind eine einen einem eines nicht
    mehr dass oder aber auch dann sich mich mir dich dir uns euch der die das
    den dem des ein bitte mit dem wort für von zum zur ist war werden wird
""".split())

EXIT_OK = 0
EXIT_FAILURES = 1
EXIT_USAGE = 2
EXIT_INCOMPLETE = 3


# ---------------------------------------------------------------------------
# Grading. Pure functions, no I/O, no model.
# ---------------------------------------------------------------------------


def grade(expected: set[str], observed: set[str]) -> dict:
    """Compare two sets of category strings. This is the entire grader.

    Four verdicts, and the distinction between the middle two is deliberate:

      missed  nothing was logged for this sentence at all
      exact   observed == expected
      extra   expected is a subset of observed, plus categories not asked for
      wrong   something was logged, but the expected category is not in it

    `pass` is `expected <= observed`, so `exact` and `extra` both pass. A second
    genuine error found in the same sentence is not a miscategorisation of the
    planted one. `strict` is `observed == expected` and is reported separately,
    so the looser number can never be quoted without the tighter one beside it.
    """
    if not observed:
        return {"verdict": "missed", "pass": False, "strict": False, "extra": []}
    if observed == expected:
        return {"verdict": "exact", "pass": True, "strict": True, "extra": []}
    if expected <= observed:
        return {
            "verdict": "extra",
            "pass": True,
            "strict": False,
            "extra": sorted(observed - expected),
        }
    return {
        "verdict": "wrong",
        "pass": False,
        "strict": False,
        "extra": sorted(observed - expected),
    }


def sha256(path: Path) -> str:
    """Digest a file, or the word 'absent'. Used for the log-untouched proof."""
    if not path.exists():
        return "absent"
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Obligation 9: the elicitation table is read from tutor.md, never copied here
# ---------------------------------------------------------------------------


def elicitation_rows() -> dict[str, str]:
    """Parse `get_focus() returns` -> question out of prompts/tutor.md.

    Read from the prompt rather than duplicated into this file, for the reason
    session 4 gave for not copying the table into review.py: two copies drift
    the first time either is edited, and `tutor.md` owns it. A prompt edit that
    rewrites a question therefore changes what this harness compares against,
    which is correct - the question IS the contract.
    """
    rows: dict[str, str] = {}
    for line in (PROJECT_ROOT / "prompts" / "tutor.md").read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[1] in ("You ask", "---"):
            continue
        key, question = cells[0], cells[1]
        if COLD_START_KEY in key:
            rows[COLD_START_KEY] = question
        else:
            for name in re.findall(r"`([a-z_]+)`", key):
                rows[name] = question
    return rows


def content_words(text: str) -> set[str]:
    """Lower-case tokens of 4+ letters that are not in STOPWORDS."""
    tokens = re.findall(r"[a-zA-ZäöüÄÖÜß]+", text.lower())
    return {t for t in tokens if len(t) >= 4 and t not in STOPWORDS}


def follow_up(reply: str) -> str:
    """The tutor's follow-up: its last question AND everything after it.

    tutor.md requires exactly one question per Gespraech turn, placed last. The
    trailing text matters and must not be dropped: in the `word_order` row the
    question is `Warum lernen Sie Deutsch?` but the part that actually forces
    the structure is the instruction after it, `Antworten Sie mit "weil"`.
    Taking the question alone left the overlap resting on `warum`, which is a
    generic interrogative and would mark a drifted `Warum ...?` on target.
    """
    marks = [m.start() for m in re.finditer(r"\?", reply)]
    if not marks:
        return ""
    boundary = max(
        (reply.rfind(ch, 0, marks[-1]) for ch in (".", "!", "?", "\n")), default=-1
    )
    return reply[boundary + 1:].strip()


def on_target(follow_up: str, row_question: str) -> dict:
    """INDICATOR, not proof. Lexical overlap with the focus row's question.

    tutor.md explicitly allows re-topicking a question into the learner's own
    world, so an exact match would be wrong and a model would be needed to
    decide the general case. Overlap of content words is the strongest thing
    that stays deterministic. The overlapping words are returned so a human
    reading the report can see exactly what the verdict rests on.
    """
    shared = sorted(content_words(follow_up) & content_words(row_question))
    return {"follow_up": follow_up, "shared": shared, "on_target": bool(shared)}


# ---------------------------------------------------------------------------
# Obligations 2, 4 and 8: watch the tools actually being called
# ---------------------------------------------------------------------------


def instrument(trace: list) -> dict:
    """Wrap the three registered tools so the call order is visible.

    The wrappers are installed on `agent`, not on `tools`, because agent.py did
    `from tools import ...` at import time and build_agent() resolves those
    names out of its own module globals. Nothing in tools.py or agent.py is
    edited; the names are rebound for the duration of a run and restored after.

    functools.wraps is not cosmetic here. ADK builds each tool declaration from
    the function's name, docstring and signature, and those declarations are
    sent to the model on every call. Without wraps the model would see a
    different tool surface than production does, and the run would be measuring
    the harness instead of the prompt.
    """
    original = {}
    for name in ("get_focus", "get_recent_errors", "log_error"):
        fn = getattr(agent, name)
        original[name] = fn

        def make(inner, label):
            @functools.wraps(inner)
            def wrapper(*args, **kwargs):
                result = inner(*args, **kwargs)
                trace.append({"tool": label, "result": result if label == "get_focus" else None})
                return result

            return wrapper

        setattr(agent, name, make(fn, name))
    return original


def restore(original: dict) -> None:
    for name, fn in original.items():
        setattr(agent, name, fn)


# ---------------------------------------------------------------------------
# One run
# ---------------------------------------------------------------------------


async def one_turn(runner, session_id: str, text: str) -> str:
    """Send one message, return the tutor's final text. Same shape as agent.turn."""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    out = []
    async for ev in runner.run_async(
        user_id=agent.USER_ID, session_id=session_id, new_message=message
    ):
        if ev.is_final_response() and ev.content and ev.content.parts:
            out.extend(p.text for p in ev.content.parts if p.text)
    return "".join(out).strip()


def skipped_run(index: int, reason: str) -> dict:
    """A run that was never launched. Costs no calls and is never scored."""
    return {
        "run": index, "model": None, "started": None, "sandbox_log": None,
        "opening": None, "model_calls": 0, "aborted": reason, "quota": True,
        "obligations": {},
        "sentences": [
            {
                "n": s["n"], "text": s["text"], "planted": s["planted"],
                "expected": sorted(s["expect"]), "observed": [], "lines_written": 0,
                "verdict": "not_run", "pass": False, "strict": False, "extra": [],
            }
            for s in SENTENCES
        ],
    }


async def run_once(index: int, model: str, pace: float) -> dict:
    """One session: opener plus the five sentences, graded per sentence.

    A fresh throwaway log per run, so `get_focus()` sees the cold-start case
    exactly as a first-ever session would, and so run N cannot be contaminated
    by run N-1. The real log is never opened.
    """
    sandbox = Path(tempfile.mkdtemp(prefix="regression-"))
    real_log, real_cards, real_model = tools.LOG_PATH, tools.CARDS_PATH, agent.MODEL
    tools.LOG_PATH = sandbox / "log.jsonl"
    tools.CARDS_PATH = sandbox / "cards.csv"
    agent.MODEL = model
    agent.STATE.update({"drafting": False, "calls": 0, "blocked": 0})

    trace: list = []
    original = instrument(trace)
    rows = elicitation_rows()

    result = {
        "run": index,
        "model": model,
        "started": datetime.now().isoformat(timespec="seconds"),
        "sandbox_log": str(tools.LOG_PATH),
        "opening": None,
        "sentences": [],
        "obligations": {},
        "model_calls": 0,
        "aborted": None,
        "quota": False,
    }

    runner = None
    try:
        runner = InMemoryRunner(agent=agent.build_agent(), app_name=agent.APP_NAME)
        session = await runner.session_service.create_session(
            app_name=agent.APP_NAME, user_id=agent.USER_ID
        )

        # ---- the opening turn. Obligations 8 and 4 are decided here. --------
        trace.clear()
        result["opening"] = await one_turn(runner, session.id, SESSION_OPENER)
        opening_tools = [t["tool"] for t in trace]
        focus = next((t["result"] for t in trace if t["tool"] == "get_focus"), None)
        row_key = focus if focus in rows else COLD_START_KEY
        result["obligations"] = {
            # Exact. "Call get_focus() before your first German output."  The
            # final text of a turn is produced after every tool call in it, so
            # a get_focus in this turn's trace IS before the first output.
            "o8_get_focus_called_before_first_output": "get_focus" in opening_tools,
            # Exact. "Call get_recent_errors at session start."
            "o4_get_recent_errors_called_at_start": "get_recent_errors" in opening_tools,
            "opening_tool_calls": opening_tools,
            "focus_returned": focus,
            "elicitation_row_used": row_key,
            "elicitation_row_question": rows.get(row_key, ""),
        }

        seen = 0
        follow_ups = []
        for spec in SENTENCES:
            if pace:
                time.sleep(pace)
            trace.clear()
            reply = await one_turn(runner, session.id, spec["text"])
            entries, malformed = tools._read_log()
            fresh = entries[seen:]
            seen = len(entries)
            observed = {e.get("category") for e in fresh if e.get("category")}
            calls = [t["tool"] for t in trace]
            row = {
                "n": spec["n"],
                "text": spec["text"],
                "planted": spec["planted"],
                "expected": sorted(spec["expect"]),
                "observed": sorted(observed),
                "lines_written": len(fresh),
                "malformed": malformed,
                "tool_calls": calls,
                # Exact. Obligation 2, "correct every error, then call log_error
                # once per error". Every one of these five sentences contains a
                # known planted error, so zero calls is a violation, not a
                # judgment. This is the detector for the silent failure session
                # 3 recorded: a model that prints the log_error arguments as
                # prose instead of calling the tool looks perfect on screen.
                "o2_log_error_called": calls.count("log_error") >= 1,
                "reply": reply,
                "logged": [
                    {
                        "category": e.get("category"),
                        "severity": e.get("severity"),
                        "mode": e.get("mode"),
                        "detail": e.get("detail"),
                        "learner_text": e.get("learner_text"),
                        "correction": e.get("correction"),
                    }
                    for e in fresh
                ],
            }
            row.update(grade(spec["expect"], observed))
            row["o9"] = on_target(follow_up(reply), rows.get(row_key, ""))
            follow_ups.append(row["o9"]["on_target"])
            result["sentences"].append(row)

        # Obligation 9's three-turn minimum, over the first turns of the session.
        streak = 0
        for hit in follow_ups:
            if not hit:
                break
            streak += 1
        result["obligations"].update({
            "o9_consecutive_on_target": streak,
            "o9_minimum": TARGET_TURNS,
            "o9_indicator_met": streak >= TARGET_TURNS,
            "o9_is_indicator_not_proof": True,
        })
    except genai_errors.APIError as err:
        result["aborted"] = f"HTTP {err.code}: {err.message}"
        result["quota"] = err.code == 429
    except Exception as err:  # noqa: BLE001 - a harness must report, not crash
        result["aborted"] = f"{type(err).__name__}: {err}"
    finally:
        restore(original)
        if runner is not None:
            await runner.close()
        result["model_calls"] = agent.STATE["calls"]
        tools.LOG_PATH, tools.CARDS_PATH, agent.MODEL = real_log, real_cards, real_model
        shutil.rmtree(sandbox, ignore_errors=True)

    for spec in SENTENCES[len(result["sentences"]):]:
        result["sentences"].append(
            {
                "n": spec["n"], "text": spec["text"], "planted": spec["planted"],
                "expected": sorted(spec["expect"]), "observed": [], "lines_written": 0,
                "verdict": "not_run", "pass": False, "strict": False, "extra": [],
            }
        )
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def summarise(runs: list[dict]) -> dict:
    """Per-sentence catch rate across runs, and which sentences varied."""
    per_sentence = {}
    for spec in SENTENCES:
        rows = [r for run in runs for r in run["sentences"] if r["n"] == spec["n"]]
        scored = [r for r in rows if r["verdict"] != "not_run"]
        verdicts = [r["verdict"] for r in scored]
        per_sentence[spec["n"]] = {
            "text": spec["text"],
            "expected": sorted(spec["expect"]),
            "runs_scored": len(scored),
            "passed": sum(1 for r in scored if r["pass"]),
            "strict": sum(1 for r in scored if r["strict"]),
            "verdicts": verdicts,
            "observed_per_run": [r["observed"] for r in scored],
            "varied": len(set(verdicts)) > 1
            or len({tuple(r["observed"]) for r in scored}) > 1,
        }
    scored_runs = [r for r in runs if r["aborted"] is None]
    categories_ok = bool(scored_runs) and all(
        r["pass"] for run in scored_runs for r in run["sentences"]
    )
    # Only the exact obligations gate. Obligation 9 is an indicator and is
    # reported beside these, never folded into them.
    obligations_ok = bool(scored_runs) and all(
        run["obligations"].get("o8_get_focus_called_before_first_output")
        and run["obligations"].get("o4_get_recent_errors_called_at_start")
        and all(r.get("o2_log_error_called") for r in run["sentences"])
        for run in scored_runs
    )
    return {
        "runs_requested": len(runs),
        "runs_completed": len(scored_runs),
        "per_sentence": per_sentence,
        "categories_ok": categories_ok,
        "obligations_ok": obligations_ok,
        "all_passed": categories_ok and obligations_ok,
        "o9_streaks": [
            run["obligations"].get("o9_consecutive_on_target") for run in scored_runs
        ],
        "model_calls_total": sum(r["model_calls"] for r in runs),
    }


def report(runs: list[dict], summary: dict, before: str, after: str, out: Path) -> None:
    """Print every run in full. No averaging: an average hides the variance."""
    print("=" * 78)
    print("REGRESSION HARNESS - spec-v3.md section 11, five planted errors")
    print("=" * 78)
    print()
    print("Grading is a set comparison in Python: expected <= observed, on two")
    print("sets of strings from the closed thirteen-category list. No model")
    print("grades this run. A model grader would share the blind spots of the")
    print("model under test, would not be reproducible between runs, and would")
    print("cost calls. The category set is closed so that this can be mechanical.")
    print()
    print("Obligations 2, 4 and 8 are exact: the tools are watched being called.")
    print("Obligation 9 is a lexical INDICATOR against the elicitation row in")
    print("tutor.md, because re-topicking is permitted. It never gates the exit")
    print("code; read it, do not automate on it.")
    print()
    print(f"data/log.jsonl sha256 BEFORE : {before}")
    print(f"data/log.jsonl sha256 AFTER  : {after}")
    print(f"log untouched                : {before == after}")
    print()

    for run in runs:
        print("-" * 78)
        print(f"RUN {run['run']}  model={run['model']}  calls={run['model_calls']}")
        print("-" * 78)
        if run["aborted"]:
            print(f"  ABORTED: {run['aborted']}")
            if run["quota"] and "per_minute" in str(run["aborted"]):
                print("  -> that is the per-minute limit. Raise --pace and re-run.")
            elif run["quota"]:
                print("  -> that is the daily cap. No further runs were launched.")
        ob = run.get("obligations") or {}
        if ob:
            print(f"  opening: {(run['opening'] or '')[:200]}")
            print(f"  opening tool calls: {ob.get('opening_tool_calls')}")
            print(f"  get_focus() returned: {ob.get('focus_returned')!r}  "
                  f"-> elicitation row: {ob.get('elicitation_row_used')!r}")
            print(f"  [{'PASS' if ob.get('o8_get_focus_called_before_first_output') else 'FAIL'}]"
                  f" obligation 8  get_focus called before the first German output")
            print(f"  [{'PASS' if ob.get('o4_get_recent_errors_called_at_start') else 'FAIL'}]"
                  f" obligation 4  get_recent_errors called at session start")
        print()
        for row in run["sentences"]:
            mark = {
                "exact": "PASS", "extra": "PASS", "wrong": "FAIL",
                "missed": "FAIL", "not_run": "----",
            }[row["verdict"]]
            print(f"  [{mark}] {row['n']}. {row['text']}")
            print(f"         expected {row['expected']}  observed {row['observed']}")
            # A sentence a run never reached is not a miss. Printing "MISSED"
            # there reads as a model failure when it is a quota failure.
            if row["verdict"] == "not_run":
                caught = "not reached - the run aborted first"
            elif row["lines_written"]:
                caught = "caught"
            else:
                caught = "MISSED - nothing logged"
            note = {
                "exact": "category correct",
                "extra": "category correct, plus extra: " + ", ".join(row["extra"]),
                "wrong": "CATEGORY WRONG",
                "missed": "no category at all",
                "not_run": "not run",
            }[row["verdict"]]
            print(f"         {caught}; {note}  ({row['lines_written']} log line(s))")
            if row["verdict"] != "not_run":
                o2 = "PASS" if row["o2_log_error_called"] else "FAIL"
                print(f"         [{o2}] obligation 2  log_error called, not narrated"
                      f"   tools: {row['tool_calls']}")
                o9 = row["o9"]
                print(f"         [{'on' if o9['on_target'] else 'OFF'} target]"
                      f" obligation 9 indicator  shared: {o9['shared'] or 'none'}")
                print(f"                  follow-up: {o9['follow_up'][:100]}")
        if ob.get("o9_minimum"):
            met = ob.get("o9_indicator_met")
            print(f"\n  obligation 9 indicator: {ob['o9_consecutive_on_target']} "
                  f"consecutive on-target follow-ups, minimum "
                  f"{ob['o9_minimum']} -> {'met' if met else 'NOT MET'} "
                  f"(indicator only, does not gate)")
        print()

    print("=" * 78)
    print("PER-SENTENCE CATCH RATE ACROSS RUNS")
    print("=" * 78)
    for n, stat in summary["per_sentence"].items():
        flag = "  <-- VARIED BETWEEN RUNS" if stat["varied"] else ""
        print(
            f"  {n}. {stat['passed']}/{stat['runs_scored']} pass "
            f"({stat['strict']}/{stat['runs_scored']} exact)  "
            f"{stat['verdicts']}{flag}"
        )
        print(f"     observed per run: {stat['observed_per_run']}")
    print()
    print(f"  runs completed   : {summary['runs_completed']}/{summary['runs_requested']}")
    print(f"  model calls      : {summary['model_calls_total']}")
    print(f"  categories ok    : {summary['categories_ok']}")
    print(f"  obligations ok   : {summary['obligations_ok']}  (2, 4, 8 - exact)")
    print(f"  obligation 9     : {summary['o9_streaks']} consecutive on target "
          f"per run (indicator)")
    print(f"  ALL PASSED       : {summary['all_passed']}")
    print()
    print(f"Results written to {out}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def main_async(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="regression.py",
        description="Run the five planted-error sentences through the tutor.",
        epilog="Exit codes: 0 all passed, 1 failures, 2 usage, 3 incomplete.",
    )
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS,
                        help=f"how many times to run all five (default {DEFAULT_RUNS})")
    parser.add_argument("--pace", type=float, default=DEFAULT_PACE,
                        help="seconds to wait between turns, for the 5 rpm free-tier "
                             f"limit (default {DEFAULT_PACE}, 0 disables)")
    parser.add_argument("--model", default=agent.MODEL,
                        help="override the pinned model. Recorded in the JSON so a "
                             "substitute run can never be mistaken for a pinned one.")
    args = parser.parse_args(argv)
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    logging.getLogger("google_adk").addHandler(logging.NullHandler())
    logging.getLogger("google_adk").propagate = False
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        print(f"GOOGLE_API_KEY is empty. Put a key in {PROJECT_ROOT / '.env'}",
              file=sys.stderr)
        return EXIT_INCOMPLETE

    real_log = Path(tools.LOG_PATH)
    before = sha256(real_log)

    # A 429 ends the whole invocation. No retry and no backoff, on purpose:
    # session 3 refused those because they hide the free-tier ceiling behind a
    # spinner, and the ceiling is information. Launching the next run after a
    # quota failure cannot produce data and costs one more call to rediscover
    # what the previous run already reported.
    runs: list[dict] = []
    for index in range(1, args.runs + 1):
        outcome = await run_once(index, args.model, args.pace)
        runs.append(outcome)
        if outcome["quota"]:
            runs.extend(
                skipped_run(later, f"not launched: quota exhausted on run {index}")
                for later in range(index + 1, args.runs + 1)
            )
            break

    after = sha256(real_log)
    summary = summarise(runs)
    payload = {
        "date": date.today().isoformat(),
        "generated": datetime.now().isoformat(timespec="seconds"),
        "model": args.model,
        "pinned_model": agent.MODEL,
        "runs_requested": args.runs,
        "pace_seconds": args.pace,
        "prompt_sha256": sha256(PROJECT_ROOT / "prompts" / "tutor.md"),
        "agent_sha256": sha256(PROJECT_ROOT / "agent.py"),
        "tools_sha256": sha256(PROJECT_ROOT / "tools.py"),
        "log_sha256_before": before,
        "log_sha256_after": after,
        "log_untouched": before == after,
        "runs": runs,
        "summary": summary,
    }

    out = real_log.parent / f"regression-{date.today().isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temporary, out)

    report(runs, summary, before, after, out)

    if before != after:
        print("\nFATAL: data/log.jsonl changed during the run.", file=sys.stderr)
        return EXIT_INCOMPLETE
    if summary["runs_completed"] < args.runs:
        return EXIT_INCOMPLETE
    return EXIT_OK if summary["all_passed"] else EXIT_FAILURES


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(main_async(argv))


if __name__ == "__main__":
    sys.exit(main())
