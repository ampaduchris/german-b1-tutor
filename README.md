# german-agent

Goethe-Zertifikat B1 Schreiben trainer. Built entirely through Claude Code, with no hand-written code.

## What is here

Only `docs/`. The project tree itself is created by build Session 1, which is deliberate: the spec defines the tree, and Session 1 proves it can follow the spec.

| File | Role |
|---|---|
| `docs/spec-v3.md` | The technical implementation spec. Authoritative. Every build prompt reads it and every conflict resolves in its favour. |
| `docs/build-sessions.md` | The five build prompts, one per session, each self-verifying. |
| `docs/tutorial.md` | The agent-architecture concepts the build teaches. Read before Session 1 and again after Session 5. |
| `docs/BUILD-LOG.md` | Append-only cross-session state. Each session reads it first and writes to it last. |
| `docs/explainer.html` | Interactive walkthrough of the architecture. Open in a browser. |

## How to build

1. Open `docs/explainer.html` and read `docs/tutorial.md`.
2. Launch Claude Code from this directory. Not from `docs/`, not from a parent.
3. Paste Session 1 from `docs/build-sessions.md`. One session per fresh Claude Code session.
4. Read the verification table before starting the next session. A `NOT VERIFIED` row is information, not a failure.
5. After Session 5, read the completed `docs/BUILD-LOG.md` end to end.

## Prerequisites

- Python 3.10 or later
- A Google AI Studio key in `GOOGLE_API_KEY`, free tier is sufficient
- Claude Code with a Pro or Max subscription

## The rule that matters

Nothing gets built ahead of the symptom that demands it. Spec section 10 lists the deferred extensions and the trigger for each. If a build session proposes one, the correct response is to record it in the build log and not build it.
