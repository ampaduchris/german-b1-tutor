# Build Sessions: Claude Code Prompt Pack v2

Supersedes section 7 of `spec-v3.md` and the first version of this pack. Five prompts, each written for a cold session with no inherited context, each self-verifying.

Design principle: a new Claude Code session is stateless in exactly the way section 5.1 of the spec describes for the agent itself. Continuity lives in two files every prompt must read, not in your memory of what you asked last time.

What changed in v2: verification moved from three or four lines to a tiered block the session executes on itself, plus stop conditions, a fixed reporting format, and an honesty clause. The reason is specific. Coding agents reliably report success they have not demonstrated, so the prompt has to make the difference between "ran and observed" and "believe it works" structurally visible rather than trusting the model to volunteer it.

---

## Setup

You already have `german-agent/docs/` containing `spec-v3.md`, `tutorial.md`, `BUILD-LOG.md`, `build-sessions.md` and `explainer.html`.

Launch Claude Code from `german-agent/` every time. All reading paths resolve relative to that directory.

`BUILD-LOG.md` is the build process running the same architecture as the agent it produces: append-only, read first, written last.

---

## Verification tiers

Every session uses the same ladder, so you learn to read the reports at a glance.

| Tier | Question | Typical form |
|---|---|---|
| V1 | Does it exist and run at all | Environment, versions, static inspection |
| V2 | Does it do the thing | Happy-path functional checks |
| V3 | Does it fail correctly | Negative and adversarial inputs |
| V4 | Does it match the spec | Line-by-line conformance audit |
| V5 | Did it break what already worked | Regression against prior sessions |
| V6 | What did it not verify | Self-audit and honest gaps |

---

## Session 1: Scaffold

```
SESSION 1 OF 5. SCAFFOLD ONLY.

MANDATORY READING. Read these in full before writing anything. Do not
skim. Do not act on assumptions about ADK from memory or training data.

  1. docs/spec-v3.md, sections 1, 2 and 3. This is the authoritative
     technical implementation spec. If anything in this prompt conflicts
     with it, follow the spec and tell me exactly where the conflict was.
  2. docs/tutorial.md, sections 1 and 2.
  3. docs/BUILD-LOG.md in full, including the entry format and rules.

CONFIRMATION GATE. Before any file is created, output exactly five lines:
  - the five files in the project tree, with one clause on each role
  - which single file is the only one permitted to call a model
  - the external dependency count the spec commits to
  - the two concepts tutorial sections 1 and 2 cover
  - the BUILD-LOG rule about ambiguities
If you cannot produce these from the documents, stop and say so.

CONTEXT
Empty directory except docs/. Python 3.10 or later. Target is Google ADK
against free-tier Gemini Flash, key in GOOGLE_API_KEY. I will not write
code at any point in this project, so favour clarity I can review over
cleverness I cannot.

TASK
  1. Create the project tree exactly as specified in spec section 2.
  2. Virtual environment, install google-adk and its client, pin every
     version in requirements.txt.
  3. Read the key from .env. Add .env and data/ to .gitignore. git init
     and make one initial commit.
  4. Create data/ and prompts/ with placeholder files only.
  5. Write scripts/smoke_test.py: a minimal ADK agent, no tools, that
     sends one German instruction and prints the reply. Its only job is
     to prove the model is reachable and the key resolves.
  6. Start the Session 1 entry in docs/BUILD-LOG.md using the documented
     entry format.

CONSTRAINTS
  - No agent logic beyond the smoke test. No tools. No log schema.
  - prompts/tutor.md gets a TODO comment and nothing else.
  - Do not invent files the spec does not list.
  - Do not install anything not required to run the smoke test.

VERIFICATION. Run every check yourself. Do not ask me to run anything.

  V1 ENVIRONMENT AND STATIC
    1.1  python --version. Expect 3.10 or higher. Print it.
    1.2  Confirm the venv is active and packages installed into it, not
         globally. Print the interpreter path.
    1.3  pip show google-adk. Print name and version.
    1.4  Print the full dependency tree depth 1 and count direct
         dependencies. Compare with the spec's stated count of two and
         report the difference if any.
    1.5  Confirm GOOGLE_API_KEY resolves as a non-empty value. Print a
         boolean only. Never print the key, any prefix of it, or its
         length.

  V2 FUNCTIONAL
    2.1  Run scripts/smoke_test.py. Print the full German reply.
    2.2  Print the exact model string used, sourced from the code rather
         than from memory.
    2.3  Run it a second time and confirm it still succeeds. Note whether
         the reply differs, and say in one line why that is expected.

  V3 NEGATIVE
    3.1  Temporarily unset GOOGLE_API_KEY and run the smoke test. Expect
         a clear, human-readable failure, not an unhandled traceback. If
         it produces a raw traceback, fix it, then re-run.
    3.2  Set GOOGLE_API_KEY to an obviously invalid value and run.
         Confirm the failure names authentication rather than something
         misleading. Restore the real key afterwards and confirm 2.1
         still passes.

  V4 SPEC CONFORMANCE
    4.1  Print the actual tree, excluding the venv and .git. Compare it
         file by file against spec section 2. Report any file present
         that the spec does not list, and any spec file missing.
    4.2  State whether the dependency count matches the spec's claim.
         If it does not, say what pulled in the extra and whether the
         spec should be corrected.

  V5 HYGIENE
    5.1  git status. Confirm neither .env nor data/ contents are staged
         or tracked. Print the output.
    5.2  Print .gitignore in full.
    5.3  Run a repository-wide search for the literal key value across
         all tracked files and confirm zero matches. Report the match
         count only, never the search string.
    5.4  Confirm data/ and prompts/ exist and contain only placeholders.

  V6 SELF-AUDIT
    6.1  List anything you created that the spec does not require.
    6.2  List anything the spec requires that you did not create.
    6.3  List every check above you could not run, with the reason.
    6.4  State any decision you made where the spec was silent.

STOP CONDITIONS. Halt and report rather than working around, if:
  - the confirmation gate cannot be satisfied from the documents
  - V2.1 fails after one honest attempt at diagnosis
  - satisfying any requirement would need a file outside spec section 2

REPORTING FORMAT. End with a single table: check ID, what you ran,
expected, observed, PASS or FAIL or NOT VERIFIED. One row per numbered
check above. No check may be omitted from the table.

HONESTY CLAUSE. Do not mark a check PASS unless you executed it and
observed the result in this session. If you inferred, assumed, or are
reasoning from how the library usually behaves, mark it NOT VERIFIED and
say why. A NOT VERIFIED row costs me nothing. A false PASS costs me an
hour in session 3.

TEACH ME. In prose, no code:
  1. What ADK's runner does between my call and the reply.
  2. Where the agent loop would terminate and what caps it, even though
     this smoke test never iterates.
  3. What "agent" means in ADK's vocabulary versus the tutorial's
     one-sentence thesis, and whether they conflict.

BEFORE YOU FINISH. Append the Session 1 entry to docs/BUILD-LOG.md in
the documented format: built, decisions taken, verification results,
deviations from spec, wanted but not built, and for the next session.
```

---

## Session 2: The deterministic layer

```
SESSION 2 OF 5. tools.py ONLY. NO MODEL CALLS ANYWHERE IN THIS SESSION.

MANDATORY READING. Read in full before writing anything. You have no
memory of session 1, so read rather than assume.

  1. docs/spec-v3.md, sections 3, 4 and 9. Section 3 is the data
     contract, section 4 the function table, section 9 the failure
     modes. Authoritative.
  2. docs/tutorial.md, sections 3 and 8.
  3. docs/BUILD-LOG.md in full, especially anything session 1 flagged
     as ambiguous or left open.
  4. requirements.txt and the existing project tree.

CONFIRMATION GATE. Before writing code, output exactly six lines:
  - the thirteen categories, verbatim and in spec order
  - which three of the five functions are registered as tools and which
    two are not
  - the one-sentence reason get_focus exists as a function rather than a
    model judgment
  - the two failure modes in spec section 9 that this session's code is
    responsible for preventing
  - what session 1 left open, per the build log
  - any ambiguity session 1 flagged that affects this session

CONTEXT
This session builds the two thirds of the system that cannot hallucinate.
Nothing here imports ADK, touches the network, or calls a model.

TASK
  1. Implement all five functions from spec section 4 in tools.py.
  2. log_error validates category against the closed list and raises on
     an unknown value. Reject, never coerce or nearest-match. Validate
     severity against blocking and minor the same way.
  3. Appends must be atomic enough that an interrupted write cannot
     corrupt a previously written line.
  4. Readers must survive a malformed line: skip it, count it, and
     surface the count rather than failing the whole read.
  5. get_focus returns the single most frequent blocking category across
     the last 20 entries. Define, document and test the tie-break rule.
  6. Write pytest tests as specified in verification below.
  7. Create tests/fixtures/log_sample.jsonl with 14 entries mirroring
     the category mix in spec section 3, with a documented known answer
     for get_focus.

CONSTRAINTS
  - No ADK import, no network, no model, no configuration beyond paths.
  - Do not register anything as a tool in this session.
  - Do not add functions the spec does not list. If you believe one is
    missing, say so in the build log and do not build it.

VERIFICATION. Run every check yourself.

  V1 STATIC
    1.1  Search tools.py for imports of adk, google, requests, httpx,
         urllib, openai or anthropic. Expect zero. Print the import list.
    1.2  Print the line count of tools.py and the five function
         signatures exactly as defined.
    1.3  Confirm the closed category list exists as a single constant,
         not duplicated across functions. Print it.

  V2 FUNCTIONAL
    2.1  Write three valid entries to a temporary log, read them back,
         and assert field-by-field equality. Print the diff result.
    2.2  Run get_focus against tests/fixtures/log_sample.jsonl. Print
         the result and the documented expected answer side by side.
    2.3  Run get_error_summary against the fixture. Print the full
         category counts and confirm they sum to the blocking-entry
         count in the fixture.
    2.4  Run export_anki_csv against the fixture. Print the first three
         rows and the total row count.
    2.5  Write 100 entries in a loop. Confirm exactly 100 valid lines
         parse afterwards and the file has no truncated final line.

  V3 NEGATIVE AND ADVERSARIAL
    3.1  Append with category "kasus". Expect a raised exception naming
         the invalid value. Print the exception type and message.
    3.2  Append with severity "critical". Expect the same treatment.
    3.3  Append with a category differing only by case, such as "Case".
         Decide and state whether this raises or normalises, then test
         the behaviour you chose. Record the decision as [AMBIGUOUS].
    3.4  Inject a malformed line into the middle of a copy of the
         fixture. Confirm reads skip it, report the skip count, and
         return every valid line either side of it intact.
    3.5  Run every read function against an empty log file. Expect
         sensible empty results, not exceptions. Print each return value.
    3.6  Run every read function against an absent log file. Same
         expectation. Print each return value.
    3.7  Run get_focus against a log with no blocking entries at all.
         Print what it returns and confirm it is documented behaviour.
    3.8  Run get_focus against a deliberate two-way tie. Confirm the
         documented tie-break rule fires and print which side won.

  V4 SPEC CONFORMANCE
    4.1  Print the thirteen categories from the code constant. Diff them
         against spec section 3 and report any difference in content or
         order.
    4.2  For each of the five functions, state its return type as built
         and confirm it matches the spec section 4 table.
    4.3  State which two failure modes from spec section 9 this code now
         prevents, and name the specific check above that proves each.

  V5 REGRESSION
    5.1  Run scripts/smoke_test.py from session 1. Confirm it still
         passes and nothing this session installed broke it.
    5.2  pytest with verbose output. Print the full pass count and any
         skips. Zero failures is the bar.

  V6 SELF-AUDIT
    6.1  List every place the spec was ambiguous enough that you decided
         on your own authority. Mark each [AMBIGUOUS].
    6.2  List any function or helper you wanted to add and did not.
    6.3  List every check above you could not run, with the reason.
    6.4  State your test count and, honestly, which function is least
         well covered.

STOP CONDITIONS. Halt and report rather than working around, if:
  - the confirmation gate cannot be satisfied from the documents
  - preventing a section 9 failure mode requires changing the data
    contract in spec section 3
  - session 1's smoke test no longer passes

REPORTING FORMAT. Single table: check ID, what you ran, expected,
observed, PASS or FAIL or NOT VERIFIED. Every numbered check appears.

HONESTY CLAUSE. Do not mark a check PASS unless you executed it and
observed the result in this session. Reasoning from how Python usually
behaves is NOT VERIFIED, not PASS.

TEACH ME. In prose, no code:
  1. Why three functions are registered and two are not, and what would
     actually go wrong if I registered all five.
  2. What ADK sends the model to describe a Python function, and what
     the model sends back when it wants one called.
  3. What the spec means by constraining a field at write time rather
     than cleaning it later, using the category list as the worked
     example, and what your V3.1 check demonstrates about that.

BEFORE YOU FINISH. Append the Session 2 entry to docs/BUILD-LOG.md in
the documented format. Every [AMBIGUOUS] decision goes in explicitly so
I can overrule it in session 3.
```

---

## Session 3: The agent

```
SESSION 3 OF 5. agent.py AND prompts/tutor.md.

MANDATORY READING. The largest reading list of the five. None optional.

  1. docs/spec-v3.md, section 5 in full: 5.1 initiation, 5.2 session
     shapes, 5.3 elicitation, 5.4 the eleven obligations. Then sections
     3 and 4 for the data contract and tool table. Authoritative.
  2. docs/tutorial.md, sections 2, 4 and 7.
  3. docs/BUILD-LOG.md in full, both prior sessions, paying attention to
     every [AMBIGUOUS] decision.
  4. tools.py and its tests, as source. Do not assume the signatures.

CONFIRMATION GATE. Before writing code, output exactly seven lines:
  - the opening sequence from launch to my first German sentence, in
    order, naming who speaks at each step
  - the eleven obligations, one clause each
  - the difference between Aufgabe and Gespräch in unit of output and in
    correction timing
  - which obligation the spec calls load-bearing, and why
  - the three registered tools with exact signatures read from tools.py
  - what sessions 1 and 2 left open, per the build log
  - every [AMBIGUOUS] decision from session 2 that affects this session

CONTEXT
This is the only file in the project permitted to call a model.
Everything it needs to count has already been built as a function. Your
job is to wire, not to reimplement.

TASK
  1. agent.py as one ADK LlmAgent on free-tier Gemini Flash, registering
     exactly log_error, get_recent_errors and get_focus.
  2. prompts/tutor.md containing all eleven obligations verbatim and the
     full elicitation table from spec 5.3. Nothing behavioural belongs
     in agent.py.
  3. Mode selection per obligation 7: ask for mode, accept 1 or 2, ask
     nothing else.
  4. The Aufgabe timer and the obligation 10 silence rule. Make silence
     structural where you can rather than merely requested in the prompt,
     and state which mechanism you used.
  5. CLI entry point so python agent.py starts a session.

CONSTRAINTS
  - Never ask the model to count, rank or aggregate. Focus selection
    comes from get_focus and nowhere else.
  - The agent does not correct a partial Aufgabe draft under any
    phrasing of helpfulness.
  - No third mode, config system, retrieval, subagents or web interface.
    If you believe one is needed, say so in the build log and do not
    build it.
  - agent.py stays under 150 lines. If it grows past that, tell me what
    is bloating it rather than splitting it silently.

VERIFICATION. Run every check yourself. Model behaviour is
probabilistic, so any check on model output runs three times and reports
all three results, not the best one.

  V1 STATIC
    1.1  Print agent.py line count against the 150 limit.
    1.2  Search agent.py for counting or ranking logic: Counter, sorted,
         max, most_common. Expect none. Print what you found.
    1.3  Print the tool registry as the agent actually holds it at
         runtime. Confirm exactly three tools and print their names.
    1.4  Confirm no obligation text is hardcoded in agent.py. Print any
         string over 100 characters found there.

  V2 PROMPT INTEGRITY
    2.1  Print prompts/tutor.md in full.
    2.2  Confirm all eleven obligations are present and numbered 1 to 11.
         Report any missing or merged.
    2.3  Confirm the elicitation table has a row for every category in
         spec 5.3. Print the row count and any missing category.
    2.4  Print the fully assembled system prompt as sent on the first
         call, and its approximate token count.

  V3 FUNCTIONAL, GESPRÄCH
    3.1  Seed a test log with five blocking konjunktiv_ii entries.
    3.2  Start a Gespräch session three times. For each run, print the
         opening question and state whether it targets konjunktiv_ii.
         Report all three, not a summary.
    3.3  Submit "Wenn ich einen Monat frei habe, ich würde nach Japan
         reisen, weil ich mag die Kultur." Print every log line written
         and the categories assigned. Expected: konjunktiv_ii and
         word_order at minimum.
    3.4  Continue three turns. Confirm each follow-up still targets
         konjunktiv_ii, per obligation 9. Print all three questions.
    3.5  Count model calls for one complete turn and print the number.

  V4 FUNCTIONAL, AUFGABE
    4.1  Start Aufgabe. Confirm the task states a word count and a time
         limit. Print the full task text.
    4.2  Send a partial draft mid-task, such as a single unfinished
         sentence. Confirm the agent does not correct it. Print exactly
         what it replied. This is the load-bearing check: run it three
         times and report all three.
    4.3  Submit a complete text. Confirm correction plus a score against
         the four criteria. Print both.
    4.4  Confirm log lines were written only after submission, never
         during drafting. Print timestamps as evidence.

  V5 NEGATIVE
    5.1  Send "3" at the mode prompt. Confirm it re-asks rather than
         guessing.
    5.2  Send English at the mode prompt. Confirm graceful handling.
    5.3  Reply in English mid-Gespräch. Print what it does and state
         whether that matches obligation 1.
    5.4  Make data/log.jsonl read-only and start a session. Confirm the
         failure is visible and comprehensible, not silent.
    5.5  Start a session against an empty log. Confirm get_focus
         returning nothing does not crash the opening.

  V6 SPEC CONFORMANCE
    6.1  Walk all eleven obligations. For each: OBSERVED, NOT OBSERVED,
         or NOT VERIFIED, naming the check above that provides evidence.
         An obligation with no corresponding check is NOT VERIFIED.
    6.2  Confirm the opening sequence matches spec 5.1 step for step.

  V7 REGRESSION
    7.1  pytest from session 2. Confirm all still pass.
    7.2  Confirm no change to tools.py this session. If you changed it,
         say what and why.

  V8 SELF-AUDIT
    8.1  List everything you wanted to add and did not.
    8.2  List every check you could not run, with the reason.
    8.3  Name the obligation you found hardest to enforce and say
         whether you enforced it structurally or by prompt wording.
    8.4  State your honest confidence that obligation 10 holds under
         phrasings you did not test.

STOP CONDITIONS. Halt and report rather than working around, if:
  - V4.2 fails on any of three runs
  - agent.py cannot stay under 150 lines without splitting behaviour
  - enforcing an obligation requires a tool not in spec section 4

REPORTING FORMAT. Single table: check ID, what you ran, expected,
observed, PASS or FAIL or NOT VERIFIED. Probabilistic checks report all
three runs in the observed column.

HONESTY CLAUSE. Do not mark a check PASS unless you executed it and
observed the result. For model-behaviour checks, one passing run out of
three is PARTIAL, not PASS, and I need to see that.

TEACH ME. In prose, no code:
  1. Trace one Gespräch turn end to end: how many model calls fired,
     what each asked for, what re-entered context between them.
  2. Why the number of model calls per turn is decided at runtime rather
     than by me, and what that means for forecasting cost.
  3. Which of the eleven obligations is most likely to decay if I edit
     this prompt carelessly, and what the cheapest test for that decay
     is.

BEFORE YOU FINISH. Append the Session 3 entry to docs/BUILD-LOG.md,
including the observed model call count per turn and the mechanism you
used to enforce Aufgabe silence.
```

---

## Session 4: The weekly job

```
SESSION 4 OF 5. review.py ONLY. NO MODEL CALLS.

MANDATORY READING. Read in full before writing anything.

  1. docs/spec-v3.md, sections 6, 4 and 10, including the scheduling
     note at the end of section 10. Authoritative.
  2. docs/tutorial.md, sections 5 and 6. Section 6 is the point of this
     entire session.
  3. docs/BUILD-LOG.md in full, all three prior sessions.
  4. tools.py, for get_error_summary and export_anki_csv.

CONFIRMATION GATE. Before writing code, output exactly five lines:
  - what review.py is permitted to read, and what it is not
  - the number of model calls the spec allows it at v1
  - what the spec says changes, and what it says does not change, when
    this runs under cron rather than by hand
  - what session 3 left open, per the build log
  - the signatures of the two tools.py functions you will use

CONTEXT
This will eventually run at 06:00 with no human present. Write it as
though that were already true, even though I will run it manually.

TASK
  1. Implement review.py per spec section 6: top three blocking
     categories with one example each, week-on-week delta, next week's
     focus, regenerated cards.csv.
  2. Markdown to stdout and to data/review-YYYY-MM-DD.md.
  3. Handle every degenerate case explicitly, per verification below.
  4. Importable and CLI-runnable, taking an optional date so I can rerun
     a past week.
  5. Non-zero exit code on failure, with a message a human reading cron
     mail at 06:05 would understand without opening the code.

CONSTRAINTS
  - Zero model calls. If you think a summary needs one, say so in the
    build log and do not add it.
  - Assume no session preceded this run and no human is watching.
  - Read-only on log.jsonl.
  - No scheduler, daemon or notification. Initiation stays manual at v1.

VERIFICATION. Run every check yourself.

  V1 STATIC
    1.1  Search review.py for model, network and ADK imports. Expect
         zero. Print the import list.
    1.2  Search for any file open on log.jsonl in write or append mode.
         Expect zero. Print what you found.
    1.3  Print the line count and the CLI signature.

  V2 FUNCTIONAL
    2.1  Run against the 14-entry fixture. Print the full markdown.
    2.2  Confirm the top three categories match what get_error_summary
         returns independently. Print both side by side.
    2.3  Confirm data/review-YYYY-MM-DD.md was written and print its
         path and size.
    2.4  Run with an explicit past date and confirm it scopes correctly.

  V3 DEGENERATE CASES. Five separate runs, each printed.
    3.1  Absent log file.
    3.2  Empty log file.
    3.3  Fewer than seven days of data.
    3.4  Data present but zero blocking entries.
    3.5  A first week with no prior week to compare against. Confirm the
         delta section degrades gracefully rather than showing a
         misleading zero.

  V4 IDEMPOTENCY AND ISOLATION
    4.1  Run twice in succession. Diff the two outputs and confirm they
         are identical. Print the diff result.
    4.2  Confirm log.jsonl is byte-identical before and after a run.
         Print the checksum both times.
    4.3  Run from a different working directory. Confirm it either
         resolves paths correctly or fails with a clear message.
    4.4  Run with a minimal environment, as cron would provide. Confirm
         it does not depend on shell variables that happen to be set in
         my interactive session. Print the result.

  V5 OUTPUT CONTRACT
    5.1  Parse the generated cards.csv with a CSV reader. Confirm the
         column count, the header, and that no field breaks on embedded
         commas, quotes or umlauts. Print the first three parsed rows.
    5.2  Confirm the file is UTF-8 and German characters survive a round
         trip. Print one card containing an umlaut.
    5.3  Force a failure, such as an unreadable log. Print the exit code
         and the message, and confirm the message is comprehensible
         without reading the source.

  V6 SPEC CONFORMANCE AND SELF-AUDIT
    6.1  Confirm every output element required by spec section 6 is
         present. List them and mark each found or missing.
    6.2  State your verdict on the spec section 10 claim that adding a
         scheduler later will not change the architecture. Give evidence
         from V4.4 specifically.
    6.3  List every check you could not run, with the reason.
    6.4  List anything you wanted to add and did not.

STOP CONDITIONS. Halt and report rather than working around, if:
  - any degenerate case in V3 requires writing to log.jsonl to handle
  - producing the delta requires a model call
  - V4.2 shows the log changed during a run

REPORTING FORMAT. Single table: check ID, what you ran, expected,
observed, PASS or FAIL or NOT VERIFIED. Every numbered check appears.

HONESTY CLAUSE. V4.4 is the check most likely to be assumed rather than
run. Run it with an actually minimal environment. If you cannot, mark it
NOT VERIFIED and say so plainly.

TEACH ME. In prose, no code:
  1. Assume this fires at 06:00 with no human. Walk through exactly what
     it knows at the moment of invocation and where every piece of that
     knowledge came from.
  2. Explain what "no memory between invocations" forced into this
     design that would have been unnecessary in an interactive script.
  3. Give your verdict on the spec's architectural claim, and say what
     would have to be true for it to be wrong.

BEFORE YOU FINISH. Append the Session 4 entry to docs/BUILD-LOG.md,
including the degenerate cases handled, exit codes chosen, and your
verdict on the scheduling claim.
```

---

## Session 5: Regression harness and architecture debrief

```
SESSION 5 OF 5. NO NEW FEATURES. TESTING AND TEACHING ONLY.

MANDATORY READING. Read all of it. This session justifies the other
four, so do not economise here.

  1. docs/spec-v3.md in full, including sections 8, 9, 11 and 12.
  2. docs/tutorial.md in full, including the ten questions at the end.
  3. docs/BUILD-LOG.md in full, all four prior sessions, including every
     [AMBIGUOUS] decision and every NOT VERIFIED check.
  4. Every source file in the project.

CONFIRMATION GATE. Before starting, output exactly six lines:
  - the nine acceptance criteria from spec section 8
  - the seven failure modes from spec section 9
  - the five planted errors in spec section 11 and their expected
    categories
  - the claims in spec section 12 rated M rather than H (there are four,
    not three: Flash sufficiency, log-driven elicitation, two thirds
    deterministic, manual initiation)
  - every [AMBIGUOUS] decision earlier sessions recorded
  - every check earlier sessions marked NOT VERIFIED

PART ONE: THE REGRESSION HARNESS

Build scripts/regression.py. It runs these five sentences through the
tutor and checks the categories logged:

  1. "Ich helfe meinen Bruder."                        expect case
  2. "Wenn ich Zeit habe, würde ich mehr lesen."       expect konjunktiv_ii
  3. "Ich habe ein neuen Auto gekauft."                 expect adjective_endings
  4. "Wenn ich Zeit habe, ich gehe ins Kino."          expect word_order
  5. "Sehr geehrter Herr Meier, kannst du mir helfen?" expect register

Requirements:
  - Correctness is a set comparison against expected categories. No
    model grades this. State in the output why that matters.
  - Report per sentence: caught or missed, category correct or wrong.
  - Write results to data/regression-YYYY-MM-DD.json so I can diff runs
    after a prompt edit.
  - These runs must not write to log.jsonl. They are tests, not study.
  - Accept a --runs flag, default 3.

VERIFICATION OF THE HARNESS ITSELF
  H1  Confirm regression.py does not write to data/log.jsonl. Checksum
      the log before and after and print both.
  H2  Run the harness with a deliberately wrong expectation and confirm
      it reports a failure rather than passing. A test suite that cannot
      fail is not a test suite.
  H3  Run the real harness three times. Print all three result sets in
      full, not an average.
  H4  Report per-sentence catch rate across the three runs and identify
      any sentence whose result varied between runs.
  H5  State what the variance implies about free-tier Flash on this task,
      and whether spec section 12's M-rated claim about model
      sufficiency now has evidence in either direction.

PART TWO: FAILURE MODE AUDIT
Attempt to trigger each of the seven failure modes in spec section 9
deliberately. For each: what you did, what happened, and whether the
system prevents it, detects it, or neither. Do not skip a mode because
it seems unlikely.

PART THREE: ACCEPTANCE AUDIT
Check the finished system against all nine acceptance criteria in spec
section 8. For each: PASS, FAIL or NOT VERIFIED, with the specific
evidence. Do not soften a FAIL. Criterion 5 is about my understanding
rather than the code, so mark it NOT APPLICABLE and say why.

PART FOUR: THE DEBRIEF
In prose, no code, and be blunt. Flattery is worthless to me and a soft
assessment costs more than a harsh one.

  1. Walk the whole system as an architecture: what is deterministic,
     what is model-driven, where state lives, how a turn flows.
  2. Answer the ten questions at the end of docs/tutorial.md, in order.
     Question ten is "what did you build that I did not ask for", and I
     want a real answer, not none.
  3. Name everything over-built and everything under-built. Both lists.
     If a list is empty, say why it is empty.
  4. Of the three M-rated claims in spec section 12, say which the build
     produced evidence about, and in which direction.
  5. Revisit every [AMBIGUOUS] decision from the build log. For each,
     say whether you would now decide the same way.
  6. Name the single change that would most improve this system, and the
     single component you would delete.
  7. List everything still marked NOT VERIFIED across all five sessions
     and say which one worries you most.

CONSTRAINTS
  - No new features. No refactor beyond what a failing acceptance
    criterion requires.
  - Fix nothing silently. Report it, then ask.

STOP CONDITIONS. Halt and report rather than working around, if:
  - H2 shows the harness cannot fail
  - three or more acceptance criteria fail
  - a failure mode in part two is neither prevented nor detected

REPORTING FORMAT. Three tables: harness checks, failure mode audit,
acceptance criteria. Then the prose debrief.

HONESTY CLAUSE. This session exists to tell me the truth about what the
previous four built. A generous assessment here is worse than useless,
because I will act on it. If the system is weaker than the spec claims,
that is the most valuable output of the whole project.

BEFORE YOU FINISH. Append the Session 5 entry to docs/BUILD-LOG.md: the
regression results across all runs, the acceptance table, the failure
mode audit, and the over-built and under-built lists. This entry is what
I will read before making any change to this system in future.
```

---

## Why each element is there

| Element | Purpose |
|---|---|
| Mandatory reading list | A cold session has no context. The spec is the only authority and is read first every time. |
| Confirmation gate | Forces reading over claimed reading. A wrong confirmation is caught in thirty seconds; wrong code is caught in an hour. |
| Spec wins on conflict | Stops a casually worded prompt from silently overriding a considered decision. |
| Tiered verification | Separates "it runs" from "it fails correctly" from "it matches the spec". Most agent verification stops at the first tier. |
| Three runs on model checks | Model output is probabilistic. A single passing run is not evidence, and reporting the best of three is how a false PASS enters the build log. |
| Stop conditions | Prevents the most expensive failure mode: an agent inventing a workaround that quietly violates the architecture. |
| Honesty clause | Coding agents report success they did not demonstrate. NOT VERIFIED must be cheaper to say than a false PASS. |
| Reporting format | A fixed table makes five sessions comparable and makes an omitted check visible. |
| Teach me | The secondary goal. The section that feels skippable when tired and is not. |
| Build log append | The build process running the agent's own architecture: append-only state, read first, written last. |
