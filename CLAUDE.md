# Rules for an agent working in this repository

- Read `docs/BUILD-LOG.md` first. Append one entry last. Never edit an earlier entry.
- `docs/spec-v3.md` is the sole authority. `prompts/tutor.md` never overrides it.
- The deterministic layer (`tools.py`, `review.py`) never imports a model client. No test needs an API (application programming interface) key or calls a model.
- A change to `prompts/tutor.md` touches one obligation and is measured with `scripts/regression.py`. That script runs on the owner's key, never in CI.
- Never commit `.env` or anything under `data/`.
- Open a pull request from a branch. Never push to `main`. Never approve or merge: the owner approves and merges every pull request.
- Every commit carries a `Co-Authored-By` line naming the model.
- Run `uv run --locked pytest -q` before opening a pull request. It must pass on Python 3.11, 3.12 and 3.13.
- Public writing: British English, short declarative sentences, no em dashes, abbreviations written out at first use.
- Record any departure from the spec and any hand edit by the owner in `docs/DEVIATIONS.md`.
