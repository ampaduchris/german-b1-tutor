"""ADK tutor agent. The only file in this system that calls a model.

Wiring only. All behaviour lives in prompts/tutor.md, loaded verbatim as the
agent instruction. Obligation 10 is enforced in code, not prose: see gate().
Run: uv run agent.py
"""

import asyncio
import logging
import os
import select
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import errors, types

from tools import MODES as MODE_NAMES
from tools import get_focus, get_recent_errors, log_error

PROJECT_ROOT = Path(__file__).resolve().parent
PROMPT_PATH = PROJECT_ROOT / "prompts" / "tutor.md"
LOG_PATH = PROJECT_ROOT / "data" / "log.jsonl"
MODEL = "gemini-3.6-flash"  # pinned, never a -latest alias: BUILD-LOG s1 addendum
APP_NAME = "german_agent"
USER_ID = "learner"

# The closed mode vocabulary, settled per BUILD-LOG session 2 item 8 and now
# enforced in tools.log_error. Both dicts are derived from tools.MODES rather
# than restating the strings, so the value the runtime announces and the value
# the log validates cannot drift apart.
MODES = {"1": MODE_NAMES[0], "2": MODE_NAMES[1]}
MINUTES = {MODE_NAMES[0]: 20, MODE_NAMES[1]: 15}
SUBMIT = "FERTIG"
STATE = {"drafting": False, "calls": 0, "blocked": 0}


def gate(callback_context, llm_request):
    """Count model calls, and refuse every one while a draft is open."""
    if STATE["drafting"]:
        STATE["blocked"] += 1
        part = types.Part(text="[Aufgabe laeuft. Keine Rueckmeldung vor der Abgabe.]")
        return LlmResponse(content=types.Content(role="model", parts=[part]))
    STATE["calls"] += 1
    return None


def tool_error(tool, args, tool_context, error):
    """Hand a failed tool back to the model instead of killing the session."""
    print(f"[tool {tool.name} failed: {type(error).__name__}: {error}]", file=sys.stderr)
    return {"error": f"{type(error).__name__}: {error}"}


def build_agent() -> LlmAgent:
    """One LlmAgent, three tools, instruction read from disk at build time."""
    return LlmAgent(
        name="tutor", model=MODEL, tools=[log_error, get_recent_errors, get_focus],
        instruction=PROMPT_PATH.read_text(encoding="utf-8"),
        before_model_callback=gate, on_tool_error_callback=tool_error,
    )


async def turn(runner, session_id: str, text: str) -> str:
    """One message in, the tutor's final text out. Tool calls happen between."""
    message = types.Content(role="user", parts=[types.Part(text=text)])
    out = []
    async for ev in runner.run_async(user_id=USER_ID, session_id=session_id, new_message=message):
        if ev.is_final_response() and ev.content and ev.content.parts:
            out.extend(p.text for p in ev.content.parts if p.text)
    return "".join(out).strip()


def ask_mode() -> str:
    """Obligation 7, structurally: 1 or 2, re-asked, nothing else accepted."""
    while True:
        raw = input("Modus? 1 = Aufgabe (20 Min), 2 = Gespraech (15 Min): ").strip()
        if raw in MODES:
            return MODES[raw]
        print("Bitte 1 oder 2.")


def timed_input(prompt: str, seconds: float) -> str | None:
    """Read one line, or return None once the clock runs out.

    input() blocks forever, so before this existed a learner who typed nothing
    was never timed out and the limit spec section 8 criterion 2 calls for was
    advisory rather than enforced. select gives the read a deadline. Falls back
    to a blocking read wherever select cannot watch stdin, which is any
    non-Unix platform and some redirected streams; the prompt is printed first
    either way, so the fallback must not print it again.
    """
    print(prompt, end="", flush=True)
    try:
        ready = select.select([sys.stdin], [], [], max(seconds, 0.0))[0]
    except (OSError, ValueError):
        return input()
    if not ready:
        return None
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line.rstrip("\n")


def opener(mode: str) -> str:
    """The SESSION_START control message, carrying the limit the clock keeps.

    The duration is passed to the model rather than written in tutor.md, so the
    number the learner is told is by construction the number that is enforced.
    Before this, MINUTES here and the prose in tutor.md were two sources of
    truth for one fact.
    """
    return f"SESSION_START mode={mode} minutes={MINUTES[mode]}"


async def aufgabe(runner, session_id: str) -> None:
    """Issue one task, buffer the draft locally, submit it once."""
    mode = MODE_NAMES[0]
    print(await turn(runner, session_id, opener(mode)))
    deadline = time.monotonic() + MINUTES[mode] * 60
    draft = []
    STATE["drafting"] = True  # nothing typed below this line reaches the model
    try:
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                print("Zeit ist um.")
                break
            mins, secs = divmod(int(left), 60)
            line = timed_input(f"[{mins}:{secs:02d} · {SUBMIT} = abgeben] ", left)
            if line is None:
                print("\nZeit ist um.")
                break
            if line.strip().upper() == SUBMIT:
                break
            draft.append(line)
    except EOFError:
        pass
    finally:
        STATE["drafting"] = False
    body = "\n".join(draft).strip()
    print(await turn(runner, session_id, f"SUBMISSION mode={mode}\n{body}"))


async def gespraech(runner, session_id: str) -> None:
    """Open on the focus, then correct every turn until the timer expires."""
    mode = MODE_NAMES[1]
    print(await turn(runner, session_id, opener(mode)))
    deadline = time.monotonic() + MINUTES[mode] * 60
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            break
        try:
            text = timed_input("> ", left)
        except EOFError:
            break
        if text is None:
            print()
            break
        text = text.strip()
        if not text or text.upper() == "ENDE":
            break
        print(await turn(runner, session_id, text))
    print("Sitzung beendet.")


async def main() -> int:
    logging.getLogger("google_adk").addHandler(logging.NullHandler())
    logging.getLogger("google_adk").propagate = False  # else 120 lines per failure
    load_dotenv(PROJECT_ROOT / ".env")
    if not os.environ.get("GOOGLE_API_KEY", "").strip():
        sys.exit(f"GOOGLE_API_KEY is empty. Put a key in {PROJECT_ROOT / '.env'}")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:  # fail at launch, loudly, rather than at the first correction, silently
        open(LOG_PATH, "a", encoding="utf-8").close()
    except OSError as err:
        sys.exit(f"Cannot append to {LOG_PATH}: {err}. Corrections cannot be logged.")
    runner = InMemoryRunner(agent=build_agent(), app_name=APP_NAME)
    session = await runner.session_service.create_session(app_name=APP_NAME, user_id=USER_ID)
    try:
        mode = ask_mode()  # nothing has been printed or sent before this question
        await (aufgabe if mode == "aufgabe" else gespraech)(runner, session.id)
    except EOFError:
        sys.exit("Kein Modus gewaehlt.")
    except errors.APIError as err:
        print(f"Model call failed: HTTP {err.code}. {err.message}", file=sys.stderr)
        if err.code == 429:  # the free-tier ceiling, not a fault. Say so.
            print(
                "That is the free-tier quota, not a bug: 20 requests per day and 5 "
                f"per minute on this key. Every correction already written to {LOG_PATH} "
                "is saved. Wait for the quota to reset, or use a paid tier.",
                file=sys.stderr,
            )
        return 3
    finally:
        await runner.close()
    print(f"Modellaufrufe: {STATE['calls']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
