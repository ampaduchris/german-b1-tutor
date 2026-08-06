# Implementation Spec v3: Goethe B1 Schreiben Trainer

Canonical build document. Supersedes Implementation Spec v2 and the Section 12 addendum, which are merged here rather than appended.

Scope: a single-agent German writing corrector with a persistent error log, log-driven elicitation, and a weekly review job. No hand-written code. Build surface is Claude Code plus Google ADK plus free-tier Gemini Flash.

Confidence key: **H** verified this session or structurally certain. **M** well supported, worth confirming. **L** assumption, verify before relying on it.

---

## 0. Corrections carried into this version

| Change | From | To | Basis |
|---|---|---|---|
| Exam venue | Goethe-Institut Amsterdam | Goethe-Institut Frankfurt | You are based in Frankfurt. The Netherlands framing in the earliest draft was wrong. **H** |
| Fee expectation | Unknown | Adult exams in Germany run roughly 155 to 359 EUR by level; single modules bookable at B1 and above | Goethe-Institut Germany pricing **M** |
| Prep material | Generic | Goethe's own free Modell- und Übungssätze, linked from the Frankfurt B1 page | Goethe Frankfurt B1 page **H** |
| Registration model | Single sitting assumed | Modules bookable individually; failed modules repeat alone | Goethe B1 Durchführungsbestimmungen **H** |
| Session initiation | Unspecified | Fully specified in section 5. The agent always speaks first. | Gap identified after v2 **H** |
| Focus selection | Model reads 20 raw entries | Deterministic `get_focus()` | Counting is arithmetic, not judgment **H** |

---

## 1. Prerequisites

| Item | Requirement | Cost |
|---|---|---|
| Claude Code | Native installer, Pro or Max subscription | Bundled |
| Model access | Google AI Studio key, `GOOGLE_API_KEY` | 0 EUR on free tier |

Free-tier ceiling, measured against `gemini-3.6-flash` and confirmed by the
API's own 429 body on 2026-08-05: **20 requests per day, 5 per minute.** One
Gespräch turn costs two model calls, so a session of nine to ten turns spends
the entire daily allowance. "0 EUR" is correct about price and must not be read
as correct about sufficiency: on the free tier this is a one-session-per-day
system, and running the regression check costs roughly twelve of the twenty. **H**
| Runtime | Python 3.10 or later | 0 |
| Storage | Local folder | 0 |

External dependency count: 2 (ADK, Google GenAI client). No database, no server, no container.

---

## 2. Architecture at a glance

```
german-agent/
  agent.py          ADK agent, two modes, the only runtime file calling a model
  tools.py          five deterministic functions, zero model calls
  review.py         weekly aggregation, zero model calls
  data/
    log.jsonl       append-only, the entire persistent state
    cards.csv       Anki import, regenerated weekly
  prompts/
    tutor.md        system prompt, editable without touching code
```

Five system files plus one generated artefact (`cards.csv`, regenerated weekly
from the log). `log.jsonl` is the whole database: append-only, human-readable,
diffable, repairable by hand. Roughly two thirds of system behaviour is
deterministic at v1. **M**

Test scaffolding lives outside this list and is permitted to call a model:
`scripts/smoke_test.py` and `scripts/regression.py`. The rule is that no
*runtime* file except `agent.py` calls a model, not that no file in the
repository does. `tests/`, `pyproject.toml`, `uv.lock`, `.env` and `.gitignore`
are likewise scaffolding rather than architecture.

---

## 3. Data contract

One JSON object per line:

```json
{
  "id": "2026-07-29T19:03:11",
  "date": "2026-07-29",
  "mode": "aufgabe",
  "task_type": "formal_message",
  "learner_text": "Wenn ich Zeit habe, ich gehe ins Kino.",
  "correction": "Wenn ich Zeit habe, gehe ich ins Kino.",
  "category": "word_order",
  "detail": "verb_second_after_subordinate_clause",
  "explanation_en": "After a subordinate clause the main-clause verb comes first.",
  "severity": "blocking"
}
```

**Closed category set.** The model selects from this list and may not invent members:

`case` · `gender` · `adjective_endings` · `word_order` · `verb_form` · `connectors` · `prepositions` · `konjunktiv_ii` · `passiv` · `relative_clauses` · `vocabulary` · `register` · `spelling`

Rationale: an open set produces `case`, `Kasus` and `dative error` as three labels for one phenomenon, which silently under-reports your worst weakness. Anything you intend to count must be constrained at write time. Cleaning it later does not work. **H**

Set chosen for the A2 to B1 gap. Adjective endings, connectors, Konjunktiv II, Passiv and relative clauses are the level gatekeepers. `register` is included because Schreiben Aufgabe 3 is a formal message and du/Sie slippage is scored. **M**

`severity` splits errors that cost exam points from stylistic wobble. Only `blocking` drives elicitation and the weekly focus.

**Four fields are closed, not one.** `category` (the thirteen above), `severity` (`blocking` · `minor`), `mode` (`aufgabe` · `gespraech`) and `task_type` (`informal_email` · `forum_post` · `formal_message`, or null in Gespräch). All four are validated in `log_error` and rejected with a `ValueError`, case-sensitively and without coercion.

`mode` and `task_type` were left open until session 5, and the delay was the point: session 2 refused to invent a vocabulary the spec had not defined, session 3 chose one and could only enforce it in the prompt, and session 5 closed it in code once it was settled. The interim cost was real — four spellings for two modes existed across these documents at one point, which is exactly the drift the closed category set exists to prevent, one field over. A missing `task_type` is still accepted even in Aufgabe: nothing downstream reads it, so refusing the write would trade a whole correction for a descriptive label. **H**

---

## 4. Component 1: tools.py

Five plain functions. None calls a model.

| Function | Returns | Registered as a tool | Why it is not an agent |
|---|---|---|---|
| `log_error(...)` | appends one line | Yes | File write, no judgment |
| `get_recent_errors(n=20)` | last n objects | Yes | List slice |
| `get_focus()` | top blocking category over last 20, or `None` if that window holds no blocking entries | Yes | Counting and sorting |
| `get_error_summary(days=7)` | counts by category, blocking only, ordered by count descending with ties in first-seen order | No | Arithmetic, consumed by review.py |
| `export_anki_csv()` | writes `cards.csv` | No | String formatting |

Three registered, two not. Register a function only when the decision to call it, or the arguments to call it with, genuinely require language understanding.

`get_focus()` exists because handing the model twenty raw entries and asking which category is most frequent invites a miscount that then mis-aims the entire session with no error raised. **H**

---

## 5. Component 2: agent.py

One ADK `LlmAgent` on free-tier Gemini Flash. Registered tools: `log_error`, `get_recent_errors`, `get_focus`.

### 5.1 Initiation model

| Question | v1 answer |
|---|---|
| Who starts a session | You. `python agent.py`. **H** |
| Does the agent contact you first | No. No daemon, no notification, no cron. **H** |
| Who speaks first inside a session | The agent, always |
| What do you send first | A mode number, not German |
| What ends a session | You do, or the task completes |

Nothing you write is unprompted. Proactive prompting is a deferred extension whose trigger is you starting to skip days. Building it before the symptom means debugging a scheduler instead of learning German. **H**

Opening sequence: you launch, the agent asks for mode, you send `1` or `2`, the runtime calls `get_focus()`, the agent issues the prompt in German, and only then do you write.

### 5.2 Session shapes

| | Aufgabe | Gespräch |
|---|---|---|
| Duration | 20 min | 15 min |
| Prompt source | One of three Goethe task types | A question engineered from your log |
| Your unit of output | One complete text | One to three sentences |
| Submissions | One, under a timer | Roughly 10 turns |
| Correction timing | After submission, all at once | Immediately, every turn |
| Model calls | 3 to 6 | 25 to 35 |
| Log lines | 2 to 6 | 8 to 15 |
| Trains | Exam performance under time | Structure accuracy through volume |
| Weekly slot | Tue, Thu | Mon, Wed, Fri |

Sunday is `review.py` only: no conversation, no model call.

Aufgabe task types:

| Task | Form | Approx. length |
|---|---|---|
| 1 | Informal or semi-formal email | ~80 words **L** |
| 2 | Forum post defending a position | ~80 words **L** |
| 3 | Formal message or request | ~40 words **L** |

Lengths marked **L** deliberately. Confirm against the official Übungssatz before trusting the agent's scoring.

### 5.3 Elicitation: the log writes the prompt

A generic tutor asks how your weekend was, and you answer using only structures you already control. This agent reads your recent errors, takes the most frequent blocking category, and selects a question that cannot be answered correctly without that structure. Practice volume then lands where the points are rather than where you are comfortable. **M**

| Log says | Agent asks | Why it forces the structure |
|---|---|---|
| `konjunktiv_ii` | Was würden Sie machen, wenn Sie ein Jahr frei hätten? | Unreal condition needs hätte plus würde |
| `word_order` | Warum lernen Sie Deutsch? Antworten Sie mit "weil". | Names the subordinator, forcing verb-final |
| `case` | Wem haben Sie letzte Woche geholfen? | helfen governs Dativ |
| `adjective_endings` | Beschreiben Sie Ihr Büro. Was für Möbel stehen dort? | Description forces attributive adjectives |
| `relative_clauses` | Was ist eine Betriebsversammlung? Ein Satz. | One-sentence definitions need a relative clause |
| `passiv` | Wie werden bei Ihnen neue Projekte entschieden? | Process questions pull out the passive |
| `prepositions` | Worauf freuen Sie sich diesen Monat? | Fixed verb plus preposition, auf not für |
| `connectors` | Sollten drei Tage Homeoffice normal sein? Zwei Gründe. | Opinion plus justification forces deshalb, obwohl |
| `verb_form` | Was haben Sie am Wochenende gemacht? | Perfect tense exposes sein versus haben |
| `register` | Switch to Aufgabe 3 | Register is drilled by task type, not conversation |
| `gender`, `spelling`, `vocabulary` | No dedicated pattern | Too diffuse to elicit deliberately **L** |

Topic selection should draw on your own domain where possible: meetings, projects, contracts, relocation admin. Vocabulary you will reuse beats textbook scenarios. **M**

### 5.4 System prompt contract

`prompts/tutor.md`. Eleven standing obligations:

1. Reply in German at A2 to B1. Explanations in English, one or two lines maximum.
2. Correct every error, then call `log_error` once per error.
3. Select `category` strictly from the closed list. If nothing fits, use `vocabulary` and say so.
4. Call `get_recent_errors` at session start and steer corrections toward those patterns.
5. Never lecture. Correct, explain in one line, continue.
6. In Aufgabe mode, score on task fulfilment, coherence, vocabulary, grammatical accuracy, against the 60 percent line.
7. At session start, ask for mode. Accept `1` for Aufgabe and `2` for Gespräch. Ask nothing else.
8. Call `get_focus()` before your first German output. Open with an elicitation targeting that category.
9. In Gespräch, keep your turns to one question. After each correction, ask a follow-up targeting the same category, for at least three consecutive turns.
10. In Aufgabe, issue the task, state the word count and time limit, then stay silent until the learner submits. Do not correct partial drafts.
11. Never ask an open question answerable with structures the learner already controls.

Obligation 10 is load-bearing: an agent that corrects a half-finished draft destroys the exam condition Aufgabe exists to rehearse. **H** Obligations 5 and 11 are the most likely to decay under prompt editing; keep both in the regression check.

---

## 6. Component 3: review.py

Weekly. Zero model calls at v1.

Output: top three blocking categories with one example each, week-on-week delta, next week's grammar focus, regenerated `cards.csv`.

Add an LLM only if raw counts prove unreadable. That symptom is the trigger. Waiting for it is the discipline.

---

## 7. Claude Code prompt sequence

Paste one at a time. Review the diff before continuing.

**P1, scaffold.** "Create a Python project `german-agent` using Google ADK against free-tier Gemini Flash via `GOOGLE_API_KEY`. Folders: `agent.py`, `tools.py`, `review.py`, `data/`, `prompts/`. Install dependencies and add a smoke test confirming model reachability. No agent logic yet. Then explain each file's role and how ADK's agent loop executes a single turn."

**P2, log layer.** "In `tools.py` implement five functions with no LLM calls: `log_error`, `get_recent_errors`, `get_focus`, `get_error_summary`, `export_anki_csv`, per the schema and closed category list below. Storage is append-only JSON Lines at `data/log.jsonl`. Add unit tests, including one that proves `get_focus` returns the correct category on a fixture log. Then explain why these are functions and not agent capabilities." [paste sections 3 and 4]

**P3, tutor.** "Build `agent.py` as one ADK `LlmAgent` registering `log_error`, `get_recent_errors` and `get_focus`, with the two session shapes and eleven obligations specified below. Put the system prompt in `prompts/tutor.md` so I can edit it without touching code. Then walk me through ADK tool-calling: how the model signals a call, who executes it, and what re-enters the context." [paste section 5]

**P4, review job.** "Build `review.py` per the spec below. Pure Python, no model calls, runnable manually now and schedulable later. Then explain what changes if this runs on a cron trigger instead of me invoking it, specifically what 'no memory between invocations' forces into the design." [paste section 6]

**P5, architecture debrief. Do not skip.** "Walk me through the finished system as an architecture: what is deterministic versus model-driven, where state lives, what the failure modes are, and the single change that would most improve it. Name anything you consider over-built."

P1 to P4 produce a tool. P5 produces the understanding, which is the secondary goal.

---

## 8. Acceptance criteria

Testable, not aspirational.

1. A 15 minute session writes correctly categorised lines to `log.jsonl` with no manual editing.
2. Aufgabe mode issues a task, times it, and returns a score you judge plausible against 60 percent.
3. `review.py` output changes your next week's plan.
4. `cards.csv` imports into Anki without transformation.
5. You can explain unprompted why `get_error_summary` is not an agent.
6. Launching produces a mode prompt, not a blank cursor.
7. Planting five `konjunktiv_ii` errors causes the next Gespräch session to open with a hypothetical.
8. In Aufgabe, the agent stays silent between issuing the task and your submission.
9. Gespräch follow-ups stay on the target structure for at least three consecutive turns.

---

## 9. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Opens with generic small talk | `get_focus()` not called or ignored | Make obligation 8 unconditional |
| Corrects your half-finished Aufgabe | Obligation 10 overridden by helpfulness | Strengthen wording, add to regression check |
| Same category targeted for weeks | Accuracy improved but severity still logged as blocking | Verify corrected structures stop generating entries |
| Conversation drifts off target after turn two | Obligation 9 too weak | State the three-turn minimum explicitly |
| Invented category labels | Closed list not enforced at write time | Validate `category` in `log_error`, reject unknowns |
| One malformed line breaks the read | No line-level error handling | Ask Claude Code how it handles a corrupt entry |
| You stop opening it | No trigger exists | This is the symptom that unlocks scheduling |

---

## 10. Not building, and the trigger that unlocks each

| Extension | Trigger symptom | Concept it teaches |
|---|---|---|
| Retrieval over error history | Log stops fitting comfortably in context | RAG, grounding |
| Scheduled daily prompt | You skip days | Triggers, statelessness |
| Structured correction output | You want trends charted | Structured output |
| Voice in and out | Sprechen becomes weakest module | Multimodal, latency |
| Anki via MCP | Manual CSV import is what you drop | MCP integration |
| Split grammar and conversation agents | One prompt visibly overloaded | Subagents, context isolation |

Note on the scheduling extension: it replaces initiation only. The agent gains a trigger, not a memory. A cron invocation starts with an empty context and reads the log, which is exactly what a manual launch already does. The architecture does not change, because the log was already carrying all continuity. That is the payoff for building state properly at v1. **H**

---

## 11. Verify before building

1. **Exact Schreiben formats and word counts** from the official Goethe Übungssatz. The agent's scoring is only as good as the criteria you hand it. Current values are **L**.
2. **Free-tier Flash quality on German correction.** First session, plant five known errors: a Dativ error, a Konjunktiv II error, an adjective ending, a word-order error after a subordinate clause, and a du/Sie slip. All five caught and correctly categorised means run everything free. Misses on the subtle two are the only justification for a paid model.

Keep those five sentences as a fixed regression check for every subsequent prompt edit. They are implemented in `scripts/regression.py`.

**Each planted sentence must carry exactly one error, and that is a real constraint on how they are written.** The original sentence for the adjective ending was `Ich habe einen neuen Auto gekauft.`, which carries a single underlying mistake — the learner believes `Auto` is masculine — surfacing in two morphological slots, the article and the adjective ending. Free-tier Flash categorised it `gender`, twice, deterministically, and that is a defensible reading, so no single expected category could be correct and the check would have stayed red forever. It is now `Ich habe ein neuen Auto gekauft.`, where the article is correct and only the ending is wrong. A regression sentence whose right answer is arguable is worse than no sentence, because a permanently failing check trains you to skim past the report. **H**

---

## 12. Confidence and counter-evidence

| Claim | Confidence | Counter-evidence to watch |
|---|---|---|
| Free-tier Flash is sufficient for A2 to B1 correction | M | A model that fluently mislabels a Dativ error as `case` versus `prepositions` degrades your weekly counts silently |
| Agent should not target Lesen or Hören | H | None material. Official free material covers both in exam format. |
| Agent cannot serve Sprechen | H | It rehearses content and structure only. The exam is a paired oral with a second candidate. Book a human partner. |
| Closed category set beats free text | H | Costs expressiveness. Mitigation is the `detail` field, which stays free text. |
| Log-driven elicitation beats open conversation | M | Unproven for you specifically. Watch for the opposite failure: targeting so narrow that sessions become monotonous and you stop opening it. |
| Two thirds deterministic | M | Holds at v1. Adding retrieval or generation shifts the ratio toward model calls. |
| Manual initiation is correct at v1 | M | The counter-case is real: if adherence collapses in week three, the scheduling extension moves from deferred to urgent. |
