# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/). The reasoning behind each change
lives in [`docs/BUILD-LOG.md`](docs/BUILD-LOG.md).

## [1.0.0] - 2026-10-25

First release. A Goethe-Zertifikat B1 *Schreiben* trainer: one ADK agent over an
append-only error log, built from a written specification.

### The system
- One `LlmAgent` on the pinned model `gemini-3.6-flash`, with two session
  shapes: Gespräch, corrected every turn, and Aufgabe, a timed task during which
  the tutor stays silent. That silence is enforced in code, not asked for in the
  prompt.
- A deterministic layer (`tools.py`, `review.py`) that never calls a model:
  logging, focus selection, the weekly review and the Anki CSV export.
- Four closed vocabularies, validated at write time: 13 error categories,
  severity, mode and task type.
- The system prompt as a contract: `prompts/tutor.md`, eleven numbered
  obligations.

### Evidence
- 172 tests that need no API key, run in CI on Python 3.10 to 3.13.
- Regression baseline of 2026-10-25 on google-adk 2.11.0 and google-genai
  2.31.0: 5/5 planted errors caught with the exact category; obligations 2, 4, 8
  and 10 honoured; the obligation-9 indicator not met (2 consecutive, minimum
  3); 17 model calls plus one retried 503.
- The harness retries a transient 503 once and records it; a 429 still stops
  the run (#23).

### Engineering
- CI actions pinned by commit SHA, and the runner pinned to `ubuntu-26.04`; a
  weekly scheduled run; superseded PR runs cancelled; a 10-minute job timeout;
  `uv run --locked` (#8, #18, #20, #21).
- Dependabot for uv and GitHub Actions. Model-client updates are merged only
  after a request capture and a smoke test (#12, #13, #14, #15, #19).
- An interactive architecture walkthrough on GitHub Pages, with a link preview
  (#17).
- CONTRIBUTING.md, an issue form for deferred extensions, and a roadmap of six
  extensions deliberately not built yet (#1 to #6, #10).

### Known gaps
- Acceptance criteria 3 and 4 remain NOT VERIFIED in the build log: whether the
  weekly review changes a real week's plan, and importing `cards.csv` into Anki.

[1.0.0]: https://github.com/ampaduchris/german-b1-tutor/releases/tag/v1.0.0
