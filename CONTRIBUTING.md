# Contributing

This is a personal study tool and a worked example of spec-driven agent design.
Changes are welcome. The bar is the one the project holds itself to: a change
has to be justified by something observed, and the evidence goes in writing.

## Before proposing a feature

Nothing gets built ahead of the symptom that demands it. Six extensions are
already recorded as [`deferred` issues](https://github.com/ampaduchris/german-b1-tutor/issues?q=label%3Adeferred),
each naming the trigger that would justify it.

- **If your idea is one of them,** comment on that issue with evidence that its
  trigger has happened. That is what reopens the decision, not enthusiasm.
- **If it is new,** open it with the
  [Deferred extension form](https://github.com/ampaduchris/german-b1-tutor/issues/new?template=deferred.yml).
  It asks for the trigger, the file or number that makes it unnecessary today,
  and what done would look like.

## Setup

```bash
uv sync                  # Python 3.10+, exact pins from uv.lock
uv run pytest            # 168 tests, no API key, no model call
```

A key is only needed for `agent.py`, `scripts/smoke_test.py` and
`scripts/regression.py`. See `.env.example`, and budget the free tier first: 20
requests a day, and a full regression run spends about 17 of them.

## Rules a change has to keep

- **`tools.py` and `review.py` never call a model.** CI fails the build if either
  imports a model client.
- **Tests never need a key.** CI runs with no secret configured, on Python 3.10
  through 3.13. A test that needs a key has stopped testing the deterministic
  layer.
- **The four closed vocabularies stay closed.** `category`, `severity`, `mode`
  and `task_type` are validated at write time in `log_error`. Adding a member is
  a data-contract change: amend `docs/spec-v3.md` first.
- **`prompts/tutor.md` changes one obligation at a time,** measured with the
  regression harness rather than judged by reading. See
  [Editing the prompt](README.md#editing-the-prompt).
- **`docs/BUILD-LOG.md` is append-only.** Record decisions and what you could not
  verify, following the rules at the top of the file.
- **`.env` and `data/` are never committed.**

## Pull requests

Open one against `main`, link the issue it closes, and let CI pass on all four
Python versions before asking for review. Changes are merged with a merge
commit, so each commit should be one logical change that makes sense alone.
