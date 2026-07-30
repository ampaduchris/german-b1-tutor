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
