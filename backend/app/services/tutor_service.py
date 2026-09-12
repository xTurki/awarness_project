"""The study assistant: a question about the page in front of somebody.

Nothing here is stored. The page already exists, the question arrives in the
request, and the answer is rendered and forgotten. The thread a trainee builds
while reading lives in their own browser and comes back with each question, so
this phase added no table, no column, and no migration.

Two facts shape the rest of this module:

1. **The page text and the question leave the server**, to Google. That is what
   the feature is. It is named here rather than buried, because it is the first
   thing anybody reviewing this platform will ask about.
2. **With no API key the feature is simply absent.** `is_available()` is false,
   no panel renders, and the route answers as though it were not there. The
   platform runs unchanged without one, which is how it ran before this existed.

This module knows nothing about HTTP requests or templates (Principle II): it
takes strings and returns a string.
"""

from __future__ import annotations

import httpx
import nh3

from app.config import settings

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

#: Kept to the recent past. A whole afternoon of questions would be sent with
#: every new one, which costs more each time and helps the answer less.
HISTORY_TURNS = 6

#: Generous, because a model that thinks spends this budget before it writes a
#: word. The default model does not think, but the setting may name one that
#: does, and a truncated answer is worse than a slow one.
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
    """No key configured, or the call did not come back."""


def is_available() -> bool:
    """Whether the feature exists at all on this deployment."""
    return bool(settings.gemini_api_key)


def page_text(body_html: str) -> str:
    """The page as words, with its markup removed.

    Sent as text rather than HTML: the tags are how the page looks, which has
    nothing to do with the question, and they would be most of what is sent.
    """
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
    """Answer one question about one page, or raise.

    `history` is the exchange so far, oldest first, as (question, answer) pairs.
    It arrives from the browser rather than from storage, so it is trimmed and
    treated as what it is: input.
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
            # Low, because this explains material somebody is about to be tested
            # on. Invention is the failure mode that matters here.
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
    except Exception as exc:  # noqa: BLE001 - every failure is the same failure here
        print(f"[assistant] call failed: {type(exc).__name__}: {exc}", flush=True)
        raise AssistantUnavailable(FAILED) from exc

    answer = _text_of(data)
    if not answer:
        raise AssistantUnavailable(FAILED)
    return answer


def _text_of(data: dict) -> str:
    """The reply, out of a shape that is not guaranteed to hold one.

    A refused or truncated response comes back well formed and empty, so every
    step here is tried rather than assumed.
    """
    for candidate in data.get("candidates") or []:
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(part.get("text", "") for part in parts).strip()
        if text:
            return text
    return ""
