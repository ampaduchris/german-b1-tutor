"""ADK tutor agent. The only file in this system that calls a model.

Wiring only. All behaviour lives in prompts/tutor.md, loaded verbatim as the
agent instruction. Obligation 10 is enforced in code, not prose: see gate().
Run: uv run agent.py
"""

import asyncio
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import errors, types

from tools import get_focus, get_recent_errors, log_error

PROJECT_ROOT = Path(__file__).resolve().parent
PROMPT_PATH = PROJECT_ROOT / "prompts" / "tutor.md"
LOG_PATH = PROJECT_ROOT / "data" / "log.jsonl"
MODEL = "gemini-3.6-flash"  # pinned, never a -latest alias: BUILD-LOG s1 addendum
APP_NAME = "german_agent"
USER_ID = "learner"

# The closed mode vocabulary, settled per BUILD-LOG session 2 item 8. These two
# strings are what reaches the `mode` field of every log line.
MODES = {"1": "aufgabe", "2": "gespraech"}
MINUTES = {"aufgabe": 20, "gespraech": 15}
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


async def aufgabe(runner, session_id: str) -> None:
    """Issue one task, buffer the draft locally, submit it once."""
    print(await turn(runner, session_id, "SESSION_START mode=aufgabe"))
    deadline = time.monotonic() + MINUTES["aufgabe"] * 60
    draft = []
    STATE["drafting"] = True  # nothing typed below this line reaches the model
    try:
        while True:
            left = int(deadline - time.monotonic())
            mins, secs = divmod(left if left > 0 else 0, 60)
            line = input(f"[{mins}:{secs:02d} · {SUBMIT} = abgeben] ")
            if line.strip().upper() == SUBMIT:
                break
            draft.append(line)
            if time.monotonic() >= deadline:
                print("Zeit ist um.")
                break
    except EOFError:
        pass
    finally:
        STATE["drafting"] = False
    print(await turn(runner, session_id, "SUBMISSION mode=aufgabe\n" + "\n".join(draft).strip()))


async def gespraech(runner, session_id: str) -> None:
    """Open on the focus, then correct every turn until the timer expires."""
    print(await turn(runner, session_id, "SESSION_START mode=gespraech"))
    deadline = time.monotonic() + MINUTES["gespraech"] * 60
    while time.monotonic() < deadline:
        try:
            text = input("> ").strip()
        except EOFError:
            break
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
        return 3
    finally:
        await runner.close()
    print(f"Modellaufrufe: {STATE['calls']}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
