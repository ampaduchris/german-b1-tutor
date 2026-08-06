# Tutorial: What You Are Actually Building

Companion to Implementation Spec v3. Purpose: convert the build into transferable understanding of agent architecture. Read once before P1, then again after P5.

Framing: you are not learning to code. You are learning to specify, review and reject. Every concept below is paired with the review question that catches the corresponding failure.

---

## The one-sentence thesis

An agent is a loop that lets a language model call functions and see the results, repeating until it stops asking. Everything else in this build is plumbing around that loop, and most of the plumbing should never touch a model.

---

## 1. The loop, not the model

A model call is a single request and response. An agent adds a controller that inspects the response, executes any requested tool call, appends the result, and calls again. The loop terminates when the model returns text with no tool request.

| In your build | The loop lives in ADK's runner. You never write it. |
|---|---|
| Failure mode | Unbounded looping when a tool errors and the model retries indefinitely. |
| Review question | "Show me the termination condition and the maximum iteration count." |

Consequence worth internalising: an agent's cost and latency are non-deterministic because the number of iterations is decided at runtime by the model.

---

## 2. Tools, and who executes them

The model does not run code. It emits a structured request naming a tool and its arguments. Your runtime executes the function and feeds the return value back as a new message. The model then decides what to do with it.

| In your build | `log_error`, `get_recent_errors` and `get_focus` are registered on the agent — three, matching spec sections 4 and 5. `get_error_summary` and `export_anki_csv` are deliberately not, because nothing about them requires a model's judgment. |
|---|---|
| Failure mode | Registering every function you have. Each registered tool consumes context and adds a wrong-choice opportunity. |
| Review question | "Which tools are registered, and what would break if I removed each one?" |

Rule of thumb: register a function only when the decision to call it, or the arguments to call it with, genuinely require language understanding.

---

## 3. The deterministic boundary

The most consequential architectural line in any agent build: which work is done by code and which by a model.

| Property | Plain function | Model call |
|---|---|---|
| Cost | 0 | Tokens |
| Latency | Microseconds | Seconds |
| Reproducibility | Exact | Approximate |
| Testable | Yes, unit tests | Only statistically |
| Failure style | Raises an error | Produces confident nonsense |

Counting your weekly error categories is arithmetic. Deciding that "Wenn ich Zeit habe, ich gehe ins Kino" contains a word-order error is language understanding. The first is a function. The second is a model call. **H**

| In your build | Roughly two thirds of behaviour is deterministic at v1. |
|---|---|
| Failure mode | Asking the model to do arithmetic, then trusting the number. |
| Review question | "List every operation that calls the model. Justify each one." |

---

## 4. Context as a budget

The model sees exactly one thing: the assembled context for that call. It has no other access to your project. Context is finite, is re-sent on every call, and is billed every time.

Your per-call context: system prompt, plus recent errors retrieved from the log, plus the current message, plus any tool results appended so far this turn.

| In your build | `get_recent_errors(20)` is a deliberate budget decision, not a default. |
|---|---|
| Failure mode | Growing context silently until quality degrades and cost rises with no error raised. |
| Review question | "What exactly is in the context on call two of a turn, and how large is it?" |

This is why retrieval exists as a later extension. Retrieval is what you do when selecting the right slice of state beats sending all of it.

---

## 5. State is the architecture

The model is stateless between calls. Any continuity you want must be written down and re-read. In this build that is `log.jsonl`, and nothing else.

| In your build | The log is not a feature. It is the only thing that makes the agent different tomorrow than it was today. |
|---|---|
| Failure mode | Continuity that lives in conversation history only, and evaporates when the process restarts. |
| Review question | "If I delete the session and restart, what does the agent still know?" |

Design test: anything you would be annoyed to lose belongs in a file, not in a conversation.

---

## 6. Statelessness under scheduling

This is the load-bearing lesson of the whole build, and the reason the scheduled review job is worth building even though it is small.

An interactive session accumulates history as you talk. A scheduled invocation does not. Cron starts a fresh process with an empty context every time. There is no "last week" unless last week was written to disk.

| Interactive | Scheduled |
|---|---|
| History accumulates in-session | Every run starts blank |
| You supply missing context by talking | Nothing supplies it but the log |
| Failures are visible immediately | Failures are silent until you check |

| In your build | `review.py` must reconstruct everything it needs from `log.jsonl` alone. |
|---|---|
| Review question | "Assume this runs at 06:00 with no human present. What does it read, and what happens if the file is missing or malformed?" |

Once you have internalised this, most agent architecture decisions become obvious.

---

## 7. The system prompt is a contract, not a personality

Treat `prompts/tutor.md` as an interface specification. It defines obligations the model must satisfy on every turn: correct every error, log once per error, choose from the closed list, never lecture.

| In your build | Kept in a separate file precisely so you can iterate on it without a code change. Expect ten revisions. |
|---|---|
| Failure mode | Prompt drift. You edit it repeatedly, quality changes, and you cannot tell which edit did it. |
| Review question | "What is the smallest test that tells me whether this prompt edit helped?" |

Practical discipline: change one obligation at a time, and keep the five planted-error sentences from section 10 of the spec as a fixed regression check.

---

## 8. Closed vocabularies

If the model may invent category names, you will get `case`, `Kasus`, `dative`, and `case error` as four distinct labels for one phenomenon. Aggregation then silently under-reports your worst weakness.

| In your build | 13 fixed categories. Free text is confined to the `detail` field, where it cannot corrupt counts. |
|---|---|
| Failure mode | Aggregation that looks fine and is wrong. |
| Review question | "What happens when the model wants a category that does not exist?" |

Generalisation: any field you intend to count must be constrained at write time. Cleaning it later does not work.

---

## 9. Evaluation

An agent you cannot measure is one you cannot improve. Most of what matters here needs no model to check.

| Check | Method | Model needed |
|---|---|---|
| Did it catch the five planted errors | Set comparison, `scripts/regression.py` | No |
| Did it use only valid categories | Set membership | No |
| Is the correction actually correct German | Your judgment, or a second model | Sometimes |
| Is the explanation useful | Your judgment | No |

| Failure mode | Evaluating by vibe, then attributing improvement to whichever change you made last. |
|---|---|
| Review question | "Give me a script that runs my five planted sentences and reports pass or fail per error." Built: `scripts/regression.py`. |

Confidence: this is the single most transferable habit in the build. **H**

---

## 10. Earned complexity

Every extension in the spec has a trigger symptom. The discipline is refusing to build ahead of the symptom.

The reason is not purity. It is that each unbuilt component is a concept you will learn properly later, when you have a concrete problem it solves, rather than abstractly now. Retrieval learned because your log outgrew the context window sticks. Retrieval learned because it was on a roadmap does not.

| Failure mode | A system elaborate enough to be impressive and too heavy to run daily. |
|---|---|
| Review question | "Which symptom made me build this?" If there is no answer, remove it. |

---

## Glossary

| Term | Working definition |
|---|---|
| Agent | Model plus loop plus tools plus state |
| Tool | A function the model can request by name |
| Tool call | The model's structured request; your runtime executes it |
| Context window | Everything the model sees on a single call |
| System prompt | Standing obligations prepended to every call |
| State | Anything persisted outside the conversation |
| Stateless | No memory between invocations unless re-read from storage |
| Subagent | A separate agent with its own isolated context, invoked by another |
| Retrieval | Selecting a relevant slice of state instead of sending all of it |
| Orchestration | Deciding what runs next; deterministic when the sequence is known |
| Eval | A repeatable test of agent behaviour against known-correct cases |

---

## Ten questions to put to Claude Code

Ask these after P5. The answers are the tutorial.

1. Show me the exact bytes sent on the second model call of a turn.
2. Where does the loop terminate, and what caps it?
3. Which registered tool would the model most plausibly call wrongly, and why?
4. What happens if `log.jsonl` has one malformed line?
5. If I ran this on a schedule with no human, what breaks first?
6. Which operation here is arithmetic dressed up as intelligence?
7. What is the cheapest correctness check I am not currently running?
8. If my log reaches 5,000 lines, what degrades and in what order?
9. Which part of this would you delete?
10. What did you build that I did not ask for?

Question 10 catches the most defects, in both directions.
