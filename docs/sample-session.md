# A session, verbatim

Real output, not an illustration. Every line below was recorded by
`scripts/regression.py` on 2026-08-06 against `gemini-3.6-flash`, the pinned model, and is
reproduced here unedited. The full machine record is
[`regression-2026-08-06.json`](regression-2026-08-06.json).

This is the **regression harness** driving the agent with five deliberately
planted errors, not a hand-typed study session. That is the stronger artefact:
the inputs are fixed, the expected categories are declared in advance, and
anyone can re-run it and compare. A transcript I typed myself would prove
nothing that a screenshot could not fake.

```bash
uv run scripts/regression.py --runs 1     # ~12 model calls of the free tier's 20
```

---

## Before the agent says anything

The runtime calls two tools first, in this order:

```
get_focus -> get_recent_errors
```

`get_focus()` returned `None` — the log was empty, so there was no weakness to
aim at. The prompt's elicitation table has a row for exactly that case,
`kein Fokus`, and the agent opened with its question:

> Hallo! Warum lernen Sie Deutsch? Antworten Sie bitte mit „weil“.

Nothing here is the model's choice. Which question gets asked is a table
lookup on a value that plain Python counted.

---

## The five turns

### 1. Dativ error: helfen governs the dative

**Learner writes**

```
Ich helfe meinen Bruder.
```

**Agent replies**

> Korrektur: Ich helfe mein**em** Bruder.
> *The verb „helfen“ requires the dative case (meinem).*
>
> Warum helfen Sie Ihrem Bruder? Antworten Sie bitte mit einm Satz mit „weil“.

**Written to `data/log.jsonl`**

```json
{"category": "case", "severity": "blocking", "mode": "gespraech", "detail": "dative_object_after_helfen", "learner_text": "Ich helfe meinen Bruder.", "correction": "Ich helfe meinem Bruder."}
```

Expected category `case`, observed `case` — **exact**.

### 2. Konjunktiv II: an unreal condition needs hätte, not habe

**Learner writes**

```
Wenn ich Zeit habe, würde ich mehr lesen.
```

**Agent replies**

> Korrektur: Wenn ich Zeit **hätte**, würde ich mehr lesen.
> *Hypothetical conditional sentences require Konjunktiv II in both clauses (hätte ... würde).*
>
> Warum möchten Sie mehr lesen? Antworten Sie bitte mit dem Wort „weil“.

**Written to `data/log.jsonl`**

```json
{"category": "konjunktiv_ii", "severity": "blocking", "mode": "gespraech", "detail": "konjunktiv_ii_in_if_clause", "learner_text": "Wenn ich Zeit habe, würde ich mehr lesen.", "correction": "Wenn ich Zeit hätte, würde ich mehr lesen."}
```

Expected category `konjunktiv_ii`, observed `konjunktiv_ii` — **exact**.

### 3. adjective ending: after neuter `ein` the ending is -es, not -en

**Learner writes**

```
Ich habe ein neuen Auto gekauft.
```

**Agent replies**

> Korrektur: Ich habe ein neu**es** Auto gekauft.
> *Neuter nouns with „ein“ in the accusative take the adjective ending „-es“ (ein neues Auto).*
>
> Warum haben Sie ein neues Auto gekauft? Antworten Sie bitte mit dem Wort „weil“.

**Written to `data/log.jsonl`**

```json
{"category": "adjective_endings", "severity": "blocking", "mode": "gespraech", "detail": "neuter_accusative_adjective_ending", "learner_text": "Ich habe ein neuen Auto gekauft.", "correction": "Ich habe ein neues Auto gekauft."}
```

Expected category `adjective_endings`, observed `adjective_endings` — **exact**.

### 4. word order: verb second after a subordinate clause

**Learner writes**

```
Wenn ich Zeit habe, ich gehe ins Kino.
```

**Agent replies**

> Korrektur: Wenn ich Zeit habe, **gehe ich** ins Kino.
> *When a sentence starts with a subordinate clause, the main verb must follow immediately after the comma (gehe ich).*
>
> Warum gehen Sie gerne ins Kino? Antworten Sie bitte mit dem Wort „weil“.

**Written to `data/log.jsonl`**

```json
{"category": "word_order", "severity": "blocking", "mode": "gespraech", "detail": "verb_position_after_subordinate_clause", "learner_text": "Wenn ich Zeit habe, ich gehe ins Kino.", "correction": "Wenn ich Zeit habe, gehe ich ins Kino."}
```

Expected category `word_order`, observed `word_order` — **exact**.

### 5. du/Sie slip in a formal message

**Learner writes**

```
Sehr geehrter Herr Meier, kannst du mir helfen?
```

**Agent replies**

> Korrektur: Sehr geehrter Herr Meier, **können Sie** mir helfen?
> *Use „Sie“ (können Sie) when addressing someone formally as „Herr Meier“.*
>
> Warum bitten Sie Ihren Kollegen Herr Meier um Hilfe? Antworten Sie bitte mit dem Wort „weil“.

**Written to `data/log.jsonl`**

```json
{"category": "register", "severity": "blocking", "mode": "gespraech", "detail": "inconsistent_register_formal_salutation_with_du", "learner_text": "Sehr geehrter Herr Meier, kannst du mir helfen?", "correction": "Sehr geehrter Herr Meier, können Sie mir helfen?"}
```

Expected category `register`, observed `register` — **exact**.

---

## What the harness checked

| Check | Result |
|---|---|
| Categories: expected vs observed, by set comparison | 5/5 exact |
| Obligation 8 — `get_focus()` before any output | True |
| Obligation 4 — `get_recent_errors()` at session start | True |
| Obligation 2 — `log_error` called on every correction | True |
| Obligation 9 — follow-up stays on topic (indicator only) | 5 consecutive, minimum 3 |
| Malformed log lines | 0 |
| Model calls spent | 17 |

Obligation 9 is reported as an **indicator, not a proof**. Deciding whether a
follow-up is genuinely on topic needs a model, and a model grader would share
the blind spots of the model under test, so the harness counts shared content
words instead and says plainly that this is what it is doing.

## The real log was never touched

The harness runs against a sandbox log in a temporary directory and hashes the
real one on both sides to prove it:

```
log_sha256_before  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
log_sha256_after   e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
log_untouched      True
```

Those two hashes are the SHA-256 of the empty string. A check that could
corrupt the data it measures is not a check.

## What was pinned

| Artefact | SHA-256 |
|---|---|
| `prompts/tutor.md` | `25ba237cbfa7b4c508982e00ed34261137dfd78cc9c7fe29b6fcfc0609151316` |
| `agent.py` | `25b4c7600e614ad5ddbbf799a71f2a2ccb6b3fe20c7392519ba69f1779ef954e` |
| `tools.py` | `7a748bc3af646f8e91cbc863a2fd11b6f9d75fa31f09996ae22275e771c3d78f` |

A result is only comparable to another result if the prompt that produced it
was the same prompt. Editing `tutor.md` changes the first hash, and that is the
signal that a stored baseline no longer describes the current system.

---

*One artefact of a real recording: in turn 1 the model's own follow-up reads
"mit einm Satz". That typo is the model's, and it is left in. Cleaning up the
evidence would defeat the purpose of keeping it.*
