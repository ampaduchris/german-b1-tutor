# BUILD LOG

Append-only. Each build session reads this file first and appends to it last.

Written for a reader with no memory of the session that produced the entry. Assume the next reader is a cold Claude Code instance that knows nothing except what is on disk.

Rules:

1. Append only. Never edit or delete a previous session's entry. If a later session reverses an earlier decision, record the reversal as a new entry rather than rewriting history.
2. Record decisions, not narration. "Chose X over Y because Z" is useful. "Then I created the file" is not.
3. Flag every ambiguity you resolved on your own authority, so it can be overruled.
4. Record what you could not verify, and why.
5. Never write secrets, API keys, or the contents of `.env` into this file.

Entry format:

```
## Session N: <title>
Date: YYYY-MM-DD

### Built
- files created or changed, one line each

### Decisions taken
- decision, alternatives considered, reason. Mark [AMBIGUOUS] where the spec did not settle it.

### Verification results
- check ID, pass or fail, evidence. Mark [NOT VERIFIED] with a reason where applicable.

### Deviations from spec-v3.md
- what differs, why, and whether the spec should be updated

### Wanted but not built
- suggestions raised and deliberately deferred, per the constraint that nothing is built ahead of its trigger

### For the next session
- open items, gotchas, anything that would waste an hour if rediscovered
```

---

<!-- Session 1 begins below this line -->

## Session 1: Scaffold
Date: 2026-07-30

### Built
- `agent.py`, `tools.py`, `review.py` — docstring-only placeholders naming the session that fills each one. AST-verified as containing no statement other than the docstring.
- `prompts/tutor.md` — one HTML comment, nothing else.
- `data/log.jsonl`, `data/cards.csv` — zero-byte placeholders. Both are gitignored, so neither is tracked.
- `scripts/smoke_test.py` — minimal `LlmAgent`, no tools, one German instruction, prints the reply. Exit codes 0/1/2/3 distinguish success, missing key, auth rejection, other API failure.
- `requirements.txt` — `google-adk==2.5.0`, `google-genai==2.15.0`.
- `.gitignore`, `.env` (placeholder, empty value), `.venv/` (Python 3.13.5), initial commit `3eb68a6` on `main`, plus a second commit `d391611` carrying this log entry. Two commits, because the prompt orders the commit at step 3 and this entry at step 6.

### Decisions taken
- **Python 3.13.5 via `uv`, not system `python3`.** System `/usr/bin/python3` is 3.9.6, below the spec's 3.10 floor, so it could not be used. `uv` was already installed with a 3.13.5 interpreter present, so no download was needed. Alternatives: Homebrew Python (not installed), pyenv (not installed). The venv is a plain `python -m venv`, so it has real `pip` and needs no knowledge of `uv` to use. [AMBIGUOUS] The spec says "3.10 or later" and is silent on how to obtain it.
- **Model string `gemini-2.5-flash`**, a single constant at `scripts/smoke_test.py:36`. [AMBIGUOUS] The spec says "free-tier Gemini Flash" without a version. Chosen because it is by far the most-referenced model in the installed ADK source (301 occurrences versus 43 for `gemini-3.6-flash`) and is stable rather than preview. Free-tier availability could not be confirmed by listing models, because that also needs a key. Session 3 should re-decide this deliberately rather than inherit it.
- **`requirements.txt` pins the two declared dependencies, not the full transitive closure.** "Pin every version" is ambiguous. A full `pip freeze` would put 49 lines in the file and visually contradict the spec's "external dependency count: 2". Two exact pins keep the file reviewable. Cost: transitive versions are not locked, so a rebuild months from now may resolve different sub-dependencies. If that ever bites, the fix is a lock file, which would be a new file and so a spec change.
- **`.gitignore` covers `.venv/`, `__pycache__/`, `*.py[cod]` and `.DS_Store` beyond the mandated `.env` and `data/`.** Without `.venv/` the first `git add -A` would commit 49 packages. [AMBIGUOUS] The spec mandates only the first two.
- **`.env` created with an empty `GOOGLE_API_KEY=` line** rather than a `.env.example`, which would have been a file the spec does not list. The empty value is what makes the missing-key path (check 3.1) reachable and readable.
- **ADK's own exception logging is suppressed in the smoke test** (`silence_adk_logging`, three lines, documented and reversible). On any failed model call ADK writes two complete tracebacks to stderr from `workflow/_node_runner.py` and `runners.py` under the `google_adk` logger. On the first run of check 3.2 those tracebacks were roughly 120 lines and buried the handled one-paragraph explanation, so check 3.1's "not an unhandled traceback" requirement was met only in the technical sense. Suppressing them is why 3.1 and 3.2 now read cleanly.
- **`print(..., flush=True)` on the two stdout status lines.** Without it, buffered stdout arrived after unbuffered stderr and the error text appeared above the model name it referred to.
- **The initial commit was amended, not followed by a second commit**, to honour "one initial commit" after the two smoke-test fixes above. Safe: single commit, never pushed.

### Verification results
- 1.1 PASS — venv interpreter is Python 3.13.5. System `python3` is 3.9.6 and unused.
- 1.2 PASS — `sys.prefix != sys.base_prefix`; `google.adk` resolves inside `.venv/lib/python3.13/site-packages`; system `python3 -c "import google.adk"` raises `ModuleNotFoundError`, proving nothing landed globally.
- 1.3 PASS — `google-adk` 2.5.0.
- 1.4 PASS with a finding. Declared direct dependencies: 2, matching the spec. But `google-adk` itself declares 24 depth-1 requirements and the venv holds 49 packages. See deviations.
- 1.5 **FAIL** — resolves as `False`. No key exists in `.env`, the shell environment, or any shell profile. This is an environment gap, not a code defect.
- 2.1 **NOT VERIFIED** — blocked by 1.5. No live model call was made in this session. Do not read any other row as evidence that the model replied.
- 2.2 PASS — `MODEL = "gemini-2.5-flash"`, read from `scripts/smoke_test.py:36`.
- 2.3 NOT VERIFIED — cannot run twice what has not run once.
- 3.1 PASS — with the key unset, exit 1 and a five-line explanation naming the file, the expected form and where to get a key. No traceback. Required one fix first, see decisions.
- 3.2 PASS in part. With `GOOGLE_API_KEY=not-a-real-key-000` the script exits 2 and prints "Authentication failed: the API rejected GOOGLE_API_KEY", HTTP 400, "API key not valid." — authentication named, nothing misleading. The "restore the real key and confirm 2.1 still passes" half is NOT VERIFIED, as there is no real key to restore.
- 4.1 PASS with a finding. Every spec section 2 path exists. Five extra paths exist: `.env`, `.gitignore`, `requirements.txt`, `scripts/`, `scripts/smoke_test.py`. All five are mandated by the session prompt. See deviations.
- 4.2 PASS with a finding, as 1.4.
- 5.1 PASS — working tree clean, one commit. `git ls-files` matches nothing under `.env` or `data/`. `git check-ignore -v` attributes each to its `.gitignore` line.
- 5.2 PASS — printed, 13 lines.
- 5.3 NOT VERIFIED — no key value exists, so there is no literal string to search for. What was verified instead: 0 of 13 tracked files match the Google AI Studio key shape `AIza` plus 35 characters. Re-run the literal scan once a key is in place.
- 5.4 PASS — `data/` holds two zero-byte files; `prompts/tutor.md` is one comment line; all three `.py` placeholders are AST-verified docstring-only.
- Extra, unnumbered: the reply-extraction branch of `smoke_test.py` was exercised offline against a hand-built ADK `Event`. `is_final_response()` returned `True` and the text was extracted correctly. So the one unproven step in 2.1 is the network call itself, not the parsing around it.

### Deviations from spec-v3.md
- **Five files present that spec section 2 does not list**: `.env`, `.gitignore`, `requirements.txt`, `scripts/`, `scripts/smoke_test.py`. All are required by the session prompt, and section 7's P1 explicitly asks for dependency installation and a smoke test. Reading: section 2 describes the runtime architecture, not an exhaustive repository inventory. **The spec should be corrected** — section 2 should either list the scaffolding files or state that it is deliberately architecture-only. Left as-is because a session may not edit the spec.
- **Section 2 says "Five files" and then lists six paths.** The sixth is `data/cards.csv`. Resolved on my own authority by treating the five as `agent.py`, `tools.py`, `review.py`, `data/log.jsonl`, `prompts/tutor.md`, with `cards.csv` as a regenerated export rather than a system file. `cards.csv` was still created, so nothing was skipped. [AMBIGUOUS] The spec should say six, or say five plus one generated artefact.
- **"External dependency count: 2" is true only of declared dependencies.** Installing `google-adk` alone brings 49 packages, because ADK depends on `fastapi`, `starlette`, `uvicorn`, `opentelemetry-*`, `cryptography`, `authlib` and 18 others. `google-genai` is one of ADK's own dependencies, so strictly only one package needed installing to get both. Nothing extra was installed to satisfy the smoke test. **The spec's claim should be reworded** to "2 declared dependencies" — as written it invites the reader to expect a small install. Note for later: `python-dotenv`, used by the smoke test, arrives free as an ADK dependency, so it adds nothing to the count.
- **`scripts/smoke_test.py` calls a model, and section 2 says `agent.py` is the only file that may.** Session-1-only exception: the smoke test exists to verify reachability before `agent.py` has content. It should be deleted or excluded from that rule once session 3 lands. Flagging it rather than silently allowing two model-calling files to coexist.

### Wanted but not built
- A lock file for transitive dependency versions. No symptom yet, and it would be an unlisted file.
- A `.env.example`. `.env` with an empty value does the same job without adding a file.
- Any model-name fallback or retry in the smoke test. A smoke test that papers over a failure is worse than one that exits non-zero.
- Anything from spec section 10. None of the trigger symptoms has appeared.

### For the next session
- **`GOOGLE_API_KEY` is still empty. Checks 2.1, 2.3, the second half of 3.2, and the literal-key half of 5.3 are outstanding and must be run before anything is trusted.** Put a key in `.env`, then run `.venv/bin/python scripts/smoke_test.py`. The model has never been reached from this machine.
- Use `.venv/bin/python`, not `python3`. Bare `python3` is 3.9.6 and will fail on modern syntax and on importing ADK.
- The project path contains a space (`Vibe Coding /German Lang Agent/`) and a trailing space in `Vibe Coding `. Quote every path in every shell command.
- ADK 2.5.0 specifics confirmed by inspection this session, so no need to rediscover: `google.adk.agents.Agent is LlmAgent`; `Runner.__init__` is keyword-only and needs `session_service`, so `InMemoryRunner(agent=..., app_name=...)` is the short path; `run_async` is keyword-only and takes `user_id`, `session_id`, `new_message`; sessions come from `await runner.session_service.create_session(app_name=..., user_id=...)`; replies are read via `event.is_final_response()` then `event.content.parts[*].text`.
- `Runner.run_debug()` exists and hides all session boilerplate, but its own docstring restricts it to debugging. Not used, on purpose. It may be the right tool for session 5's regression harness.
- Auth failures surface as `google.genai.errors.ClientError` with `code == 400` and reason `API_KEY_INVALID`, not 401. Any code that checks only for 401 will misclassify a bad key.
- ADK logs full tracebacks under the `google_adk` logger on any model-call failure. `agent.py` will need the same suppression or every error a learner sees will be 120 lines of stack.
- `data/` is gitignored, so a fresh clone has no `data/` directory at all. Session 2's `log_error` must create the directory, not assume it.
- The five extra files and the "Five files"/six-paths discrepancy are open spec questions for the human, listed under deviations.

---

## Session 1, addendum: key located, model corrected, uv adopted
Date: 2026-07-30

Recorded as a separate entry rather than by editing the entry above, per rule 1. Three decisions in that entry are now reversed. Read this addendum as authoritative where the two disagree.

### Built
- `pyproject.toml` — declares the same two dependencies, `requires-python = ">=3.10"`, `[tool.uv] package = false`.
- `uv.lock` — 54 packages pinned across Python 3.10 to 3.14. Committed on purpose.
- `requirements.txt` — **deleted.**
- `.env` — now provisioned from macOS Keychain, service `gemini-api-key`, account `chris`.
- `scripts/smoke_test.py` — model constant changed; run instruction is now `uv run scripts/smoke_test.py`.
- `.gitignore` — the `.venv/` comment now names `uv sync` as the rebuild command.

### Decisions taken
- **REVERSAL of "requirements.txt pins the two declared dependencies, not the full transitive closure."** Human directed uv plus `pyproject.toml`. This is strictly better and resolves the ambiguity the earlier entry flagged: `uv.lock` pins all 54 packages transitively, so "pin every version" is now satisfied literally, while `pyproject.toml` still shows only the two declared dependencies. The compromise that entry settled for is no longer needed. `uv tree --depth 1` now prints exactly two children, which is the spec's claim rendered as a command rather than an argument.
- **REVERSAL of the model choice `gemini-2.5-flash`.** Now `gemini-3.6-flash`. The original was selected by counting occurrences in the installed ADK source, which was a bad method and produced a model that returns **404, "no longer available to new users."** Corrected by probing this key against every candidate: `gemini-2.5-flash` 404, `gemini-2.0-flash` 429 quota exhausted, `gemini-3.5-flash` 503 high demand, `gemini-3.6-flash` replied, `gemini-flash-latest` replied. Probe results are recorded in a comment above the constant.
- **`gemini-flash-latest` rejected although it works.** It is a moving alias. Spec section 11 keeps five planted-error sentences as a fixed regression check, and a model that silently changes underneath an alias would invalidate that check with no visible cause. A pinned name fails loudly instead, which is what happened here and is why the defect was caught in session 1 rather than session 3.
- **`.env` provisioned from Keychain rather than by hand.** The value was piped from `security find-generic-password` straight into `.env` and never printed. Keychain stays the master copy; `.env` is a derived, gitignored artefact. Consequence to be aware of: the key is now in plaintext on disk. This follows the prompt's "read the key from `.env`" and leaves the code unchanged.
- **`[tool.uv] package = false`.** This is an application, not a library, so uv needs no build backend and nothing here is importable as a package.
- **`requires-python = ">=3.10"`, matching the spec floor, not the 3.13.5 actually in use.** Both dependencies declare `>=3.10`, so the lock resolves universally across 3.10 to 3.14. This is why the lock holds 54 packages while only 49 install on 3.13: the extra five are gated behind version markers.
- **V1.3 was re-run as `uv pip show`, not `pip show`.** A uv-managed venv ships no `pip` at all — `ls .venv/bin | grep -c '^pip'` returns 0. The check's intent is satisfied; the exact command in the prompt is now unrunnable by design.

### Verification results
Every check was re-run from scratch after the migration. The venv was deleted and rebuilt by `uv sync` before this run, so nothing below inherits pip-era state.

- 1.1 PASS — 3.13.5 via `uv run python --version`.
- 1.2 PASS — `.venv/bin/python3`, `sys.prefix != sys.base_prefix`, adk resolves inside the venv, system `python3` still raises `ModuleNotFoundError`.
- 1.3 PASS — `uv pip show google-adk` → 2.5.0. See the decision above on `pip`.
- 1.4 PASS — `uv tree --depth 1` prints `german-agent v0.1.0` with exactly two children. 2 declared, matching the spec. 49 installed, 54 locked.
- 1.5 **PASS**, was FAIL. Resolves `True`.
- 2.1 **PASS**, was NOT VERIFIED. Full German reply received, exit 0. First attempt still failed, on the model name rather than the key, which is how the model defect surfaced.
- 2.2 PASS — `MODEL = "gemini-3.6-flash"` at `scripts/smoke_test.py:49`.
- 2.3 **PASS**, was NOT VERIFIED. Second run succeeded. The reply differed in wording while keeping the same content, expected because sampling is stochastic at default temperature; identical input does not imply identical tokens. Ran four times in total, four successes, four different sentences.
- 3.1 PASS — re-confirmed under uv with `.env` blanked. Exit 1, no traceback.
- 3.2 PASS — re-confirmed under uv. Exit 2, HTTP 400, "API key not valid."
- 3.2b **PASS**, was NOT VERIFIED. Real key restored, 2.1 re-confirmed immediately afterwards.
- 4.1 PASS with a finding. Extra files are now `.env`, `.gitignore`, `pyproject.toml`, `uv.lock`, `scripts/`, `scripts/smoke_test.py`. Six rather than five; `requirements.txt` is gone and `pyproject.toml` plus `uv.lock` replace it.
- 4.2 PASS — 2 declared, unchanged by the migration.
- 5.1 PASS — `.env` and `data/` still untracked, each attributed to its `.gitignore` line.
- 5.2 PASS — 14 lines.
- 5.3 **PASS**, was NOT VERIFIED. Now runnable because a key exists. 0 of 14 tracked files contain the literal value, and `git grep -F` over `HEAD` finds it in 0 files in committed history. `.env` is not tracked.
- 5.4 PASS — unchanged.
- Extra: `uv lock --check` passes, so the lock matches `pyproject.toml`. `uv sync --frozen --dry-run` reports no changes, so the live venv matches the lock with no drift.
- Correction to the earlier entry's 5.3: the shape-based fallback scan used the pattern `AIza` plus 35 characters. This key is not of that form, so that scan would not have caught a leak of it. It gave less assurance than the entry implied. The literal scan now run supersedes it.

### Deviations from spec-v3.md
- **`requirements.txt` no longer exists.** The session prompt asked for it by name. Overridden by the human in favour of `pyproject.toml` plus `uv.lock`. **The spec and the session-1 prompt should both be updated** to name uv, otherwise session 2 will read the prompt and try to recreate `requirements.txt`.
- Extra-file count is now six rather than five. Same class of deviation as before: scaffolding that section 2 does not describe.
- All deviations recorded in the entry above still stand: the "Five files"/six-paths discrepancy, the dependency-count wording, and `scripts/smoke_test.py` calling a model where section 2 reserves that to `agent.py`.

### Wanted but not built
- A `.python-version` file. It would make interpreter selection deterministic when the venv is absent, at the cost of a seventh unlisted file. One line if wanted.
- Reading the key directly from Keychain instead of `.env`, which would keep it out of plaintext on disk. Not built: it contradicts the prompt's "read the key from `.env`" and would invent a key-loading mechanism the spec does not describe.
- A model-availability preflight check. Tempting after the 404, but it would add a model call to every startup to guard against a failure the pinned name already reports clearly.

### For the next session
- **Use `uv run <script>` and `uv sync`. There is no `pip` in the venv and no `requirements.txt` in the repo.** Add dependencies with `uv add`, which updates both `pyproject.toml` and `uv.lock`. Never `pip install`.
- **The model is `gemini-3.6-flash`, pinned deliberately. Do not switch it to a `-latest` alias.** Reason in the decisions above.
- **`models.list()` is not an availability signal.** It reported `gemini-2.5-flash` as available while `generateContent` returned 404. The only test of whether a model works is calling it.
- Free-tier quota is per model, and `gemini-2.0-flash` already returns 429 on this key. If `gemini-3.6-flash` starts returning 429 mid-session, that is quota, not a code fault.
- The key lives in macOS Keychain, service `gemini-api-key`, account `chris`. To rebuild `.env` on a new machine, pipe `security find-generic-password -s gemini-api-key -a chris -w` into it. Never echo it.
- Everything in the earlier entry's "for the next session" list about ADK 2.5.0 internals still holds: the `google_adk` logger traceback problem, `ClientError` 400 with `API_KEY_INVALID` rather than 401, keyword-only `run_async`, and `data/` being gitignored so `log_error` must create the directory.
- **The agent loop's iteration cap is `RunConfig.max_llm_calls`, default 500.** Found by source inspection this session, closing an item the session-1 report had left open. Enforced in `agents/invocation_context.py` at `increment_llm_call_count`, which counts every model call in one invocation and raises `LlmCallsLimitExceededError` once the count exceeds the limit. Two things to know before session 3: the cap counts model calls per invocation, not tool calls and not turns, so a Gespraech session at the spec's estimated 25 to 35 model calls sits far under it; and setting `max_llm_calls` to 0 or less disables enforcement entirely, with only a logged warning, which is the documented way to get an unbounded loop by accident. Verified by reading the code, not by driving 500 iterations.

---

## Session 2: The deterministic layer
Date: 2026-07-31

### Built
- `tools.py` — all five spec section 4 functions plus three private helpers (`_validate_choice`, `_read_log`, `_blocking`). 408 lines. Imports only `csv`, `json`, `logging`, `os`, `collections.Counter`, `datetime`, `pathlib`. No ADK, no network, no model.
- `tests/test_tools.py` — 73 tests, 0 skips, 0 failures.
- `tests/conftest.py` — three fixtures: `temp_log` (throwaway log, deliberately does not pre-create `data/`), `sample_log` (the committed fixture, read-only), `write_entry` (one-line append with overridable defaults).
- `tests/fixtures/log_sample.jsonl` — 14 entries, 9 blocking and 5 minor, dated 2026-07-25 to 2026-07-31. **Documented known answer: `get_focus()` returns `word_order`.**
- `pyproject.toml` — `[dependency-groups] dev = ["pytest>=9.1.1"]` and `[tool.pytest.ini_options]` with `pythonpath = ["."]`, `testpaths = ["tests"]`.
- `uv.lock` — four new packages, all in the dev group (`pytest`, `pluggy`, `iniconfig`, `pygments`).

**Provenance note, recorded because it matters for trust.** `tools.py` was already fully implemented and uncommitted in the working tree when this session started (`git status` showed `M tools.py`), with no Session 2 entry in this log. I did not write it in this session and cannot say what did. I read it line by line against spec sections 3, 4 and 9, kept it unchanged, and re-derived every verification result below from scratch. Nothing below is inherited from whatever produced that file.

### Decisions taken

- **[AMBIGUOUS] A category differing only by case RAISES; it does not normalise.** `"Case"`, `"CASE"`, `"Word_Order"` and `"Blocking"` are all rejected with the same `ValueError` as `"kasus"`. Alternative considered: `.lower()` before the membership test, which would silently accept the near miss. Rejected because tutorial section 8 says a counted field must be constrained at write time and cleaning it later does not work — a normaliser *is* cleaning, moved earlier. The stronger reason is that the caller is a language model: accepting near misses teaches it that the closed set is advisory, and the next near miss will be `"dative error"`, which no normaliser can rescue. Cost: a model that capitalises a category loses that log line and must retry. Verified in V3.3.
- **[AMBIGUOUS] `get_focus` window is the last 20 entries of any severity, then filtered to blocking.** Not the last 20 blocking entries. Spec section 4 says "top blocking category over last 20" and does not say last 20 of what. Consequence, and it is a real one: a week of mostly `minor` entries can leave the window holding only two or three blocking entries, so the focus is chosen from a thin sample. The alternative reading — scan back until 20 blocking entries are found — would make the window unbounded in time and could target a category last seen a month ago. Chose the bounded reading because spec 5.3 wants the focus to reflect what you are getting wrong *now*.
- **[AMBIGUOUS] Tie-break: the category whose most recent blocking occurrence is latest in the log wins.** The spec defines no tie-break. Alphabetical order is deterministic but arbitrary and would pin the agent to `adjective_endings` for as long as a tie persisted. Recency is the only signal left once frequency has tied. Tested in both directions (V3.8) precisely because an alphabetical implementation would pass a one-directional test by accident.
- **[AMBIGUOUS] `get_focus` returns `None` when the window holds no blocking entries.** The spec's return column says "top blocking category" and is silent on there being none. `None` means "no focus available". Alternatives rejected: raising (a fresh log is not an error, and it is the state on day one) and returning a default category (that is an invented focus, which is exactly the class of silent wrongness `get_focus` exists to prevent). **Session 3 must handle this: obligation 8 says call `get_focus()` before the first German output, and on an empty log it will get `None`.**
- **[AMBIGUOUS] `get_error_summary(days=7)` means today and the six days before it, inclusive, selected on the entry's `date` field.** Not a rolling 168 hours, and not selected on `id`. Calendar days match how a weekly review is read. The boundary is tested explicitly (day −6 in, day −7 out).
- **[AMBIGUOUS] `export_anki_csv` exports every entry, not blocking only.** Spec section 4 marks `get_error_summary` "blocking only" and marks `export_anki_csv` with nothing, so the asymmetry is read as deliberate: a `minor` error is still worth a flashcard even though it does not drive the weekly focus.
- **[AMBIGUOUS] Card format: two columns, no header row.** Front is the learner's own wrong sentence; back is `correction — explanation_en [category]`. No header, because Anki imports the first row as a note unless told otherwise, so a header would become a card. Acceptance criterion 4 asks only that the file import without transformation, which is untestable here without Anki.
- **[AMBIGUOUS] `mode` and `task_type` are not validated.** The spec closes exactly one field, `category`, and the session prompt added `severity`. `mode` and `task_type` are free strings. **This is the loosest thing in the file and session 3 must close it:** the fixture uses `"conversation"` and `"task"`, the spec section 3 example uses `"task"`, spec 5.2 calls the modes Aufgabe and Gespräch, and session 1's `agent.py` docstring writes "Gespraech". Four spellings for two modes is exactly the failure the closed category list exists to prevent, one field over. I did not close it on my own authority because inventing a closed set the spec does not define would be a data-contract change.
- **[AMBIGUOUS] `id` is a second-resolution ISO timestamp, so it is not unique.** Spec section 3's example is `"2026-07-29T19:03:11"`, and a model logging three errors in one turn can produce three identical ids. Kept faithful to the contract rather than adding microseconds or a counter, because nothing in the system uses `id` as a key — reads are positional and by `date`. Flagging it because the field is *named* `id` and will eventually mislead someone.
- **The malformed-line count is surfaced as a `logging.WARNING`, not in a return value.** The prompt says readers must "surface the count"; spec section 4's return column fixes the return types. Reconciled by keeping the returns spec-conformant and surfacing the count to the operator through the `tools` logger, plus the private `_read_log` returning `(entries, malformed)` so tests assert on it exactly. If you would rather the count came back in the return values, that is a spec section 4 change and I did not make it.
- **Return values richer than the spec's column.** `log_error` returns the entry it wrote (so a caller can confirm what landed) and `export_anki_csv` returns the row count (so `review.py` can report it). Neither contradicts the spec, both are additive.
- **pytest is a `dev` dependency group, not a project dependency.** `uv tree --depth 1` still prints exactly two children plus a dev-marked third, so the spec's "external dependency count: 2" stays literally true of what the agent needs to run. Installed with `uv add --dev`, per session 1's instruction never to use pip.
- **Paths are module-level constants, not function parameters.** Three of these become ADK tools in session 3, and every parameter of a registered function is published to the model in the tool schema; a `log_path` argument would be a knob the model could turn. Tests monkeypatch the module attributes instead, which is why every function reads them at call time.
- **Blank lines are skipped and not counted as damage.** A blank line destroys nothing, so counting it as a malformed line would inflate a number a human is meant to act on.
- **`_blocking` drops entries whose category is not in the closed set.** `log_error` cannot write one, so this only fires on a hand-edited log; dropping is better than letting an invented label become the focus.
- **[AMBIGUOUS] Fixture design: discrimination chosen over category breadth.** The prompt asks for "14 entries mirroring the category mix in spec section 3". Two readings compete and 14 entries cannot satisfy both. Reading A: put all 13 categories in, one each plus one repeat, so the fixture demonstrates the whole closed set. Reading B: build a mix that can *catch a wrong implementation*. Chose B. The fixture holds 8 of the 13 categories, and its most frequent category overall is `spelling` at 4 — all four `minor`. An implementation that counted every entry instead of only the blocking ones would answer `spelling` rather than `word_order`, so the fixture disagrees with the most likely wrong rule instead of merely agreeing with the right one. Reading A's fixture would have passed under both implementations, which is a fixture that proves nothing. The five categories absent from the fixture (`gender`, `verb_form`, `connectors`, `prepositions`, `relative_clauses`) are covered instead by a parametrised test that writes and reads back all 13.
- **Three private helpers exist, against the constraint "do not add functions the spec does not list".** `_validate_choice`, `_read_log` and `_blocking`. Read as compatible with the constraint, which is about the system's *capability surface* — the five things a caller or a model can invoke — not about a prohibition on internal structure. The alternative is duplicating the line-level parse across four readers and the membership test across two fields, which is the exact drift spec section 3 warns about one level down. All three are underscore-prefixed, none is exported, and none will be registered. Flagged rather than assumed, because the constraint does not say it.
- **One network use this session: `uv add --dev pytest`.** The "no network" constraint is about what `tools.py` does at runtime, and it holds absolutely — verified twice in V1.1. Installing the test runner is build tooling, and pytest is required by task 6 of the session prompt. No code in this session opened a socket, and no model was called.

### Verification results

Every row below was executed in this session and its output observed. The full harness output is in the session transcript.

- 1.1 PASS — AST import list is `['collections.Counter', 'csv', 'datetime.date', 'datetime.datetime', 'datetime.timedelta', 'json', 'logging', 'os', 'pathlib.Path']`. Banned-name hits: 0, by AST and by a second textual scan of every `import`/`from` line.
- 1.2 PASS — 408 lines. Five signatures printed from the AST, matching the spec's five names, plus three private helpers.
- 1.3 PASS — exactly one `CATEGORIES` assignment, a 13-element tuple. Each category string literal occurs once in the file, except `case`, whose second occurrence is the sentence `"Case" does not become "case"` in a docstring at line 88, not a second definition.
- 2.1 PASS — 3 entries written and read back, 10 fields × 3 entries compared, zero differences.
- 2.2 PASS — documented expected `word_order`, observed `word_order`.
- 2.3 PASS — `{'word_order': 3, 'case': 2, 'adjective_endings': 1, 'konjunktiv_ii': 1, 'passiv': 1, 'register': 1}`, sum 9, equal to the 9 blocking entries counted independently from the fixture file.
- 2.4 PASS — 14 rows written, 14 parsed back, every row exactly 2 columns. First three rows printed.
- 2.5 PASS — 100 physical lines, 100 parse, 0 unparseable, file ends with a newline, `_read_log` returns 100 entries and 0 malformed, order preserved `entry_0 … entry_99`.
- 3.1 PASS — `ValueError: Invalid category: 'kasus'. category must be exactly one of: …`. The invalid value is named and the valid set is listed. No log file was created by the rejected call.
- 3.2 PASS — `ValueError: Invalid severity: 'critical'. severity must be exactly one of: blocking, minor. …`.
- 3.3 PASS — `"Case"` raises, identically to `"kasus"`. Decision recorded as [AMBIGUOUS] above.
- 3.4 PASS — a truncated line injected at position 8 of a 14-entry copy: 14 valid entries returned, skip count 1, and the returned ids equal the original ids in order on both sides of the damage. `get_focus` on the damaged log still returns `word_order`.
- 3.5 PASS — empty file: `[]`, `None`, `{}`, `0`. No exceptions.
- 3.6 PASS — absent file: `[]`, `None`, `{}`, `0`. No exceptions, and reading did not create the file.
- 3.7 PASS — four `minor` entries and nothing else: `None`, matching the docstring.
- 3.8 PASS — two-way 2–2 tie run in both orders. `[case, word_order, case, word_order]` → `word_order`; the reverse → `case`. The reversal is the evidence that the rule is recency and not an alphabetical accident.
- 4.1 PASS — the 13 categories were parsed out of `docs/spec-v3.md` section 3 programmatically and compared with `tools.CATEGORIES`: identical in content and in order, zero positional differences.
- 4.2 PASS — `log_error` → `dict` (and appends exactly one line per call, shown by 3 calls producing 3 lines in 2.1 and 100 producing 100 in 2.5); `get_recent_errors` → `list[dict]`; `get_focus` → `str | None`; `get_error_summary` → `dict[str, int]`; `export_anki_csv` → `int` and writes the file. All match the spec section 4 column, with the two additive return values noted under decisions.
- 4.3 PASS — see the failure-mode mapping below.
- 5.1 **NOT VERIFIED, deliberately.** See the conflict note below. What was verified: `scripts/smoke_test.py` is byte-identical to HEAD; `uv lock --check` passes; `uv sync --frozen --dry-run` reports no changes, so the dev-group install did not disturb the runtime environment; `import google.adk` and `from google.adk.agents import LlmAgent` still resolve; and the script itself still runs end to end up to the model call, exiting 1 with its documented message when the key is blank. The live model call was not made.
- 5.2 PASS — `uv run pytest -v`: **73 passed, 0 failed, 0 skipped, 0.21s.**

**The V5.1 conflict, stated rather than worked around.** The session prompt's headline is "NO MODEL CALLS ANYWHERE IN THIS SESSION" and its constraints repeat "no network, no model", while V5.1 asks me to run a script whose only purpose is to call a model. I resolved it in favour of the headline constraint and stopped at the last instruction before the network call. This is the one check in the session that a human must close:

```
uv run scripts/smoke_test.py
```

Expect exit 0 and a German sentence. If it returns 404 the model name has moved again; if 429, that is free-tier quota, not a code fault.

### Failure modes this session prevents

| Spec section 9 row | Prevented by | Proved by |
|---|---|---|
| "Invented category labels — closed list not enforced at write time — validate `category` in `log_error`, reject unknowns" | `_validate_choice` against the single `CATEGORIES` constant, raising `ValueError` before the file is opened | V3.1 (`"kasus"` raises and writes nothing), V3.3 (`"Case"` raises, no normalising back door), V4.1 (the constant is the spec's list, in order) |
| "One malformed line breaks the read — no line-level error handling" | `_read_log` parses per line, skips and counts failures, and never raises | V3.4 (damage at position 8; 14 valid entries returned intact either side, skip count 1), plus V3.5/3.6 for the degenerate empty and absent cases |

### Deviations from spec-v3.md

- **`tests/` is not in spec section 2.** Four new paths: `tests/conftest.py`, `tests/test_tools.py`, `tests/fixtures/log_sample.jsonl`, and the directories. Mandated by the session prompt (task 6 and 7) and by spec section 7's P2, which asks for unit tests including a `get_focus` fixture test. Same class of deviation session 1 recorded: section 2 describes the runtime architecture, not the repository.
- **A third installed dependency.** pytest, plus its three transitive packages, in a dev group. The spec's "external dependency count: 2" is about the runtime and is still true there.
- **`get_focus` returns `str | None`, not `str`.** Spec section 4's return column does not admit the empty case. **The spec should say so**: "top blocking category over last 20, or none if the window holds no blocking entries."
- **Two additive return values** (`log_error` → the entry, `export_anki_csv` → the row count) where the spec's column describes a side effect.
- **Contradiction between the two documents, unresolved by me.** Tutorial section 2 says "`log_error` and `get_recent_errors` are registered on the agent. `get_error_summary` and `export_anki_csv` are deliberately not" — four functions, omitting `get_focus`. Spec section 4 and section 5 both say three registered, including `get_focus`. I followed the spec, which the prompt calls authoritative. **The tutorial should be corrected**, because a reader who learns the tool list from it will register the wrong set in session 3.

### Wanted but not built

- **A public reader that returns the malformed-line count.** Wanted because the count currently reaches a human only through a log warning, and `review.py` at 06:00 with nobody watching is exactly the case tutorial section 6 warns about. Not built: it is a sixth function, and the prompt says to say so rather than build it. `_read_log` already returns the count if session 4 wants it.
- **`get_focus(n=20)` with the window as a parameter.** The spec fixes 20. A parameter would also become a model-visible knob.
- **A log repair or compaction function.** No symptom: the log is 0 bytes.
- **File locking for concurrent writers.** Single-process, single-user at v1. `O_APPEND` already prevents interleaving between processes on a local filesystem; a lock would only matter over NFS.
- **A uniqueness suffix on `id`.** Would fix the second-resolution collision, and would change the data contract in spec section 3. Flagged, not built.
- **Validation of `mode` and `task_type`.** Same reason: closing a set the spec leaves open is a contract change.
- **A README in `tests/fixtures/`.** The fixture's known answers are documented in the `test_tools.py` module docstring instead, so there is no extra file to drift.

### For the next session

- **Exact signatures. Do not assume them.**
  - `log_error(learner_text: str, correction: str, category: str, detail: str, explanation_en: str, severity: str, mode: str, task_type: str | None = None) -> dict`
  - `get_recent_errors(n: int = 20) -> list[dict]`
  - `get_focus() -> str | None`
  - `get_error_summary(days: int = 7) -> dict[str, int]`
  - `export_anki_csv() -> int`
- **`get_focus()` returns `None` on a fresh log.** Obligation 8 makes the call unconditional; session 3 must decide what the agent opens with when there is no focus yet, and V5.5 of the session 3 prompt tests exactly this. Do not let the model invent a category to fill the gap.
- **`log_error` raises `ValueError` on a bad category.** In ADK the exception surfaces back into the model's context as a tool error. Session 3 has to decide deliberately what happens next — retry with a valid category, or drop the line — and obligation 3 already tells the model to fall back to `vocabulary` when nothing fits. Verify the model actually does that rather than looping.
- **The `mode` vocabulary is still undecided.** The fixture writes `"conversation"` and `"task"`. Pick the two strings in session 3 and use them everywhere, or the mode field becomes the open-set problem the category list exists to prevent.
- **Run the tests with `uv run pytest`.** 73 tests, ~0.2s. `pythonpath = ["."]` in `pyproject.toml` is what makes `import tools` work from `tests/`; without it pytest puts only `tests/` on the path.
- **`data/log.jsonl` and `data/cards.csv` are still 0 bytes.** No test writes to them: `conftest.py` monkeypatches `tools.LOG_PATH` and `tools.CARDS_PATH` into `tmp_path` for every test. Session 3's first real session will be the first thing to write to the log.
- **The atomicity claim is argued, not crash-tested.** `log_error` serialises the whole line first, writes it with a single `write()` to a handle opened `"a"` (so `O_APPEND`), then `flush()` and `os.fsync()`. What was demonstrated is 100 sequential appends producing 100 parseable lines with no truncation. What was *not* demonstrated is a process killed mid-write or two processes writing at once. The guarantee to rely on is the weaker one the code documents: damage is confined to the record being written, never to records already there.
- **Nothing in `tools.py` imports ADK, and it must stay that way.** The registration happens in `agent.py`. If session 3 finds itself editing `tools.py`, that is the signal to stop and re-read spec section 4.

---

## Session 2, addendum: the ten ambiguous decisions, ratified by the human
Date: 2026-07-31

Recorded as a separate entry per rule 1. All ten `[AMBIGUOUS]` decisions in the Session 2 entry were presented to the human with their trade-offs and **ratified as built**. No code changed. **Session 3 should treat these as settled, not open** — with the named triggers below being the only things that reopen them.

- **1, case-sensitivity.** Queried, then kept. The clarifying answer, recorded because it is the reasoning and not the rule: case-sensitivity is not itself the point. Rejection over coercion is, and `case` is the cheapest place to hold that line without carving an exception into it. `.lower()` would fix only capitalisation and leave `Kasus` and `dative error` untouched, so it adds an exception without removing the need for the raise; it would also hide the signal that obligation 3 is too loose. Acknowledged cost: a rejected call loses that log line unless the model retries, and the retry is the model's choice. **Trigger to revisit: session 3 shows Flash capitalising more than rarely — and the fix then is tightening obligation 3 in `tutor.md`, not loosening `_validate_choice`.**
- **2, `get_focus` window is the last 20 of any severity.** Ratified. **Trigger to revisit: after roughly two weeks of real logs, if blocking entries are under about half of all entries, the focus is being chosen from too thin a sample — switch to "last 20 blocking" or cap the window by days.**
- **3, tie-break is most-recent-occurrence-wins.** Ratified.
- **4, `get_focus` returns `None` when no blocking entries.** Ratified. Session 3 still has to write the branch: obligation 8 makes the call unconditional and a fresh log returns `None`.
- **5, `get_error_summary` window is calendar days, inclusive, on `date`.** Ratified.
- **6, `export_anki_csv` exports every entry including `minor`.** Ratified. The deciding argument: spec 5.3 calls `gender`, `spelling` and `vocabulary` too diffuse to elicit in conversation, so cards are the only place those get practised.
- **7, card format: two columns, no header.** Ratified. **Trigger to revisit: the first real Anki import.** Acceptance criterion 4 is untestable until then, and the category currently sits in back-text rather than as a tag, so a deck cannot be filtered by category. Regenerating the file is free.
- **8, `mode` and `task_type` left unvalidated.** Ratified *as a session 2 decision*, which is not the same as leaving the field open. **This is session 3 work, not a closed question:** pick the two mode strings, use them everywhere, and close the set. Four spellings for two modes already exist across the documents. Until that happens every log line carries whatever the model chose.
- **9, `id` is a second-resolution timestamp and not unique.** Ratified. Treat it as a timestamp, never as an identity. **Trigger to revisit: anything in session 4 that wants to dedupe or cross-reference entries.**
- **10, fixture design favours discrimination over category breadth.** Ratified.

Net effect for session 3: nine of the ten need no further thought. The one live item is **8**, which is a decision to make rather than a decision to review.
