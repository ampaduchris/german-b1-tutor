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
