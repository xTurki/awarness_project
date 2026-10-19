"""Study assistant using the Gemini API.

Note: the page text and the question are sent to Google. Nothing is stored.
Without an API key the feature is disabled.
"""

from __future__ import annotations

import httpx
import nh3

from app.config import settings

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Only the most recent exchanges are sent.
HISTORY_TURNS = 6

# Large enough for models that use "thinking" tokens.
MAX_OUTPUT_TOKENS = 1200

UNAVAILABLE = (
    "The study assistant is not switched on for this platform."
)

FAILED = (
    "The study assistant could not be reached just now. Your question is still "
    "in the box, so try again in a moment."
)

INSTRUCTIONS = """\
You are a study assistant inside a workplace cybersecurity awareness training \
platform. A trainee is reading one page of a training module and has asked you \
about it.

How to answer:

- Answer from the page below wherever the page covers the question.
- Where the page does not cover it, say so plainly in one short sentence, then \
answer briefly from general knowledge so they are not left with nothing.
- Never contradict the page. It is the material they will be tested on.
- Reply in the same language the question is written in.
- Be brief: a few sentences, plain text, no headings, no preamble, no sign-off.
- If the question is not about the training at all, say so in one line.

Module: {module}
Page: {page}
{truncation}
--- the page they are reading ---
{body}
--- end of the page ---
"""


class AssistantUnavailable(Exception):
    """No API key, or the request failed."""


def is_available() -> bool:
    """True if an API key is configured."""
    return bool(settings.gemini_api_key)


def page_text(body_html: str) -> str:
    """Page body as plain text (HTML tags removed)."""
    stripped = nh3.clean(body_html or "", tags=set(), attributes={})
    return " ".join(stripped.split())


def ask(
    question: str,
    *,
    module_title: str,
    page_title: str,
    body_html: str,
    history: list[tuple[str, str]] | None = None,
) -> str:
    """Answer a question about a page. Raises AssistantUnavailable on failure.

    `history` is a list of (question, answer) pairs from the browser, oldest first.
    """
    if not is_available():
        raise AssistantUnavailable(UNAVAILABLE)

    asked = (question or "").strip()
    if not asked:
        raise AssistantUnavailable("Ask a question first.")

    text = page_text(body_html)
    cut = len(text) > settings.gemini_context_chars
    if cut:
        text = text[: settings.gemini_context_chars]

    system = INSTRUCTIONS.format(
        module=module_title,
        page=page_title,
        truncation=(
            "\nThis page is long and has been cut: answer from what follows, and "
            "say so if the question is clearly about a later part.\n"
            if cut
            else ""
        ),
        body=text or "(this page has no text yet)",
    )

    contents = []
    for previous_question, previous_answer in (history or [])[-HISTORY_TURNS:]:
        contents.append({"role": "user", "parts": [{"text": previous_question}]})
        contents.append({"role": "model", "parts": [{"text": previous_answer}]})
    contents.append({"role": "user", "parts": [{"text": asked}]})

    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            # Low temperature to keep answers factual.
            "temperature": 0.2,
        },
    }

    try:
        response = httpx.post(
            ENDPOINT.format(model=settings.gemini_model),
            params={"key": settings.gemini_api_key},
            json=payload,
            timeout=settings.gemini_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[assistant] call failed: {type(exc).__name__}: {exc}", flush=True)
        raise AssistantUnavailable(FAILED) from exc

    answer = _text_of(data)
    if not answer:
        raise AssistantUnavailable(FAILED)
    return answer


def _text_of(data: dict) -> str:
    """Extract the reply text from the API response (may be empty)."""
    for candidate in data.get("candidates") or []:
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts).strip()
        if text:
            return text
    return ""
