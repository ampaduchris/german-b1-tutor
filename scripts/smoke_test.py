"""Smoke test: prove the model is reachable and GOOGLE_API_KEY resolves.

This file is scaffolding, not part of the agent. Its only job is to answer one
question: can this machine reach free-tier Gemini Flash with the key on disk?

It deliberately has no tools, no log, and no session shapes. Per spec-v3.md
section 2, agent.py is the only file permitted to call a model in the finished
system; this script is a temporary exception that exists so session 1 can be
verified before agent.py has any content.

Run:  uv run scripts/smoke_test.py

Exit codes, so the verification checks can tell failures apart:
  0  reply received
  1  GOOGLE_API_KEY missing or empty
  2  the API rejected the key (authentication)
  3  any other API failure (quota, network, bad model name)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import errors as genai_errors
from google.genai import types

# The single model string for this script. Printed by verification check 2.2,
# so it is read from here rather than recalled from memory.
#
# Chosen by probing this key against every Flash model, not from documentation:
#   gemini-2.5-flash    404, "no longer available to new users"
#   gemini-2.0-flash    429, free-tier quota exhausted for this key
#   gemini-3.5-flash    503, high demand
#   gemini-3.6-flash    replied
#   gemini-flash-latest replied, but it is a moving alias
# The alias is rejected on purpose. Spec section 11 keeps five planted-error
# sentences as a fixed regression check, and a model that changes under the
# alias would invalidate that check with no visible cause.
#
# Note for whoever revisits this: models.list() reports gemini-2.5-flash as
# available. Only an actual generateContent call reveals that it is not.
MODEL = "gemini-3.6-flash"

# The one German instruction sent to the model. A German reply proves both
# reachability and that the model will answer in German at all.
GERMAN_INSTRUCTION = (
    "Antworte auf Deutsch in genau einem Satz: "
    "Warum ist die deutsche Wortstellung für Lernende schwierig?"
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def silence_adk_logging() -> None:
    """Stop ADK printing its own traceback for an error we already report.

    On a failed model call ADK logs two full tracebacks to stderr, from
    workflow/_node_runner.py and runners.py, under the 'google_adk' logger
    hierarchy. This script catches that same exception and prints a one
    paragraph explanation instead, so the library's version is pure noise and
    buries the readable message.

    Delete these three lines to get ADK's raw tracebacks back when diagnosing
    something this script's own error handling does not explain.
    """
    adk_logger = logging.getLogger("google_adk")
    adk_logger.addHandler(logging.NullHandler())
    adk_logger.propagate = False


def load_key() -> str:
    """Load GOOGLE_API_KEY from .env, or exit with a readable message.

    A missing key is the most likely first-run failure, so it is reported as a
    sentence and an exit code rather than as a traceback.
    """
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        print(
            "GOOGLE_API_KEY is not set.\n"
            "\n"
            f"Expected a non-empty value in {PROJECT_ROOT / '.env'} or in the\n"
            "shell environment, in the form:\n"
            "\n"
            "    GOOGLE_API_KEY=your-key-here\n"
            "\n"
            "Get a free-tier key from https://aistudio.google.com/apikey\n"
            "The .env file is listed in .gitignore and is never committed.",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def is_auth_failure(err: genai_errors.APIError) -> bool:
    """True when the API rejected the credential rather than the request.

    Checked explicitly so that check 3.2 gets a message naming authentication
    instead of a generic 'the request failed'.
    """
    if err.code in (401, 403):
        return True
    # Gemini returns 400 INVALID_ARGUMENT with an API_KEY_INVALID reason for a
    # malformed key, which is an auth failure wearing a validation error's code.
    haystack = f"{err.code} {err.message} {getattr(err, 'details', '')}".upper()
    return "API_KEY" in haystack or "API KEY" in haystack


async def main() -> int:
    silence_adk_logging()
    load_key()

    # No tools, no instruction contract. Session 3 builds the real agent.
    agent = LlmAgent(
        name="smoke_test_agent",
        model=MODEL,
        instruction="Du bist ein Deutschlehrer. Antworte immer auf Deutsch.",
    )

    runner = InMemoryRunner(agent=agent, app_name="smoke_test")
    session = await runner.session_service.create_session(
        app_name="smoke_test", user_id="smoke_test_user"
    )

    message = types.Content(
        role="user", parts=[types.Part(text=GERMAN_INSTRUCTION)]
    )

    # flush=True so these stay above any error text, which goes to unbuffered
    # stderr and would otherwise overtake them.
    print(f"model:  {MODEL}", flush=True)
    print(f"sent:   {GERMAN_INSTRUCTION}", flush=True)

    reply_parts: list[str] = []
    try:
        # run_async yields every event in the turn. With no tools registered
        # there is exactly one model call and one final-response event.
        async for event in runner.run_async(
            user_id="smoke_test_user",
            session_id=session.id,
            new_message=message,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        reply_parts.append(part.text)
    except genai_errors.APIError as err:
        if is_auth_failure(err):
            print(
                "Authentication failed: the API rejected GOOGLE_API_KEY.\n"
                f"  HTTP status: {err.code}\n"
                f"  API message: {err.message}\n"
                "\n"
                "The key was present but not accepted. Check the value in .env\n"
                "against https://aistudio.google.com/apikey",
                file=sys.stderr,
            )
            return 2
        print(
            "The model call failed, but not because of the key.\n"
            f"  HTTP status: {err.code}\n"
            f"  API message: {err.message}\n"
            "\n"
            "Likely causes: free-tier quota exhausted, no network, or the model\n"
            f"name '{MODEL}' is not available to this key.",
            file=sys.stderr,
        )
        return 3
    finally:
        await runner.close()

    reply = "".join(reply_parts).strip()
    if not reply:
        print(
            "The call succeeded but the model returned no text.",
            file=sys.stderr,
        )
        return 3

    print(f"reply:  {reply}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
