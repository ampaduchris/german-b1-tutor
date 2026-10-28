<!-- What changes and why, in a few lines. Link the issue this closes. -->

Closes #

## Checklist

See [CONTRIBUTING.md](../blob/main/CONTRIBUTING.md) for the reasoning behind each item.

- [ ] CI is green on Python 3.10 to 3.13, with no warnings.
- [ ] No test needs an API key or calls a model.
- [ ] `tools.py` and `review.py` still never import a model client.
- [ ] A `google-adk` or `google-genai` update has been through the request
      capture and the one-call smoke test, not just green CI.
- [ ] A change to `prompts/tutor.md` touches one obligation and is measured
      with `scripts/regression.py`.
- [ ] Decisions and anything unverified are recorded in `docs/BUILD-LOG.md`.
- [ ] Nothing from `.env` or `data/` is included.
