"""The study assistant, without calling Google.

Every test here stubs the call. What is worth asserting is not what a model
replies, which nobody controls, but what is sent, what is refused, and what
happens when the call does not come back.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.services import tutor_service


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")


@pytest.fixture()
def captured(monkeypatch, key):
    """Stand in for the call, and keep what was sent."""
    sent = {}

    class Reply:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "A forged sender address."}]}}
                ]
            }

    def fake_post(url, **kwargs):
        sent["url"] = url
        sent.update(kwargs)
        return Reply()

    monkeypatch.setattr(tutor_service.httpx, "post", fake_post)
    return sent


# --------------------------------------------------- absent without a key


def test_the_feature_is_absent_with_no_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")

    assert tutor_service.is_available() is False


def test_and_asking_is_refused_rather_than_attempted(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")

    with pytest.raises(tutor_service.AssistantUnavailable):
        tutor_service.ask(
            "why?", module_title="M", page_title="P", body_html="<p>text</p>"
        )


def test_present_once_a_key_is_set(key):
    assert tutor_service.is_available() is True


# ------------------------------------------------------ what gets sent


def test_the_page_is_sent_as_words_not_markup(captured):
    tutor_service.ask(
        "what is this?",
        module_title="Phishing Awareness",
        page_title="What phishing is",
        body_html="<h2>Spoofing</h2><p>A forged <strong>sender</strong> address.</p>",
    )

    system = captured["json"]["systemInstruction"]["parts"][0]["text"]
    assert "A forged sender address." in system
    assert "<strong>" not in system
    assert "<p>" not in system


def test_the_module_and_page_are_named(captured):
    tutor_service.ask(
        "what is this?",
        module_title="Phishing Awareness",
        page_title="What phishing is",
        body_html="<p>text</p>",
    )

    system = captured["json"]["systemInstruction"]["parts"][0]["text"]
    assert "Phishing Awareness" in system
    assert "What phishing is" in system


def test_the_rules_the_answer_must_follow_are_sent(captured):
    tutor_service.ask("q", module_title="M", page_title="P", body_html="<p>t</p>")

    system = captured["json"]["systemInstruction"]["parts"][0]["text"]
    assert "Never contradict the page" in system
    assert "same language the question is written in" in system


def test_a_long_page_is_cut_and_the_model_is_told_so(captured, monkeypatch):
    monkeypatch.setattr(settings, "gemini_context_chars", 100)

    tutor_service.ask(
        "q", module_title="M", page_title="P", body_html="<p>" + ("word " * 500) + "</p>"
    )

    system = captured["json"]["systemInstruction"]["parts"][0]["text"]
    assert "has been cut" in system


def test_a_short_page_is_not(captured):
    tutor_service.ask("q", module_title="M", page_title="P", body_html="<p>short</p>")

    assert "has been cut" not in captured["json"]["systemInstruction"]["parts"][0]["text"]


# ------------------------------------------------------------ the thread


def test_earlier_turns_are_sent_so_a_follow_up_makes_sense(captured):
    tutor_service.ask(
        "how do I check one?",
        module_title="M",
        page_title="P",
        body_html="<p>t</p>",
        history=[("what is a spoofed sender?", "A forged address.")],
    )

    contents = captured["json"]["contents"]
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert contents[0]["parts"][0]["text"] == "what is a spoofed sender?"
    assert contents[-1]["parts"][0]["text"] == "how do I check one?"


def test_only_the_recent_past_is_sent(captured):
    history = [(f"q{n}", f"a{n}") for n in range(20)]

    tutor_service.ask("now", module_title="M", page_title="P", body_html="<p>t</p>",
                      history=history)

    contents = captured["json"]["contents"]
    # Six pairs plus the new question. A whole afternoon would cost more each
    # time and help the answer less.
    assert len(contents) == tutor_service.HISTORY_TURNS * 2 + 1
    assert contents[0]["parts"][0]["text"] == "q14"


# ------------------------------------------------------------ refusals


def test_an_empty_question_is_refused_without_calling_anything(key, monkeypatch):
    def explode(*a, **k):
        raise AssertionError("nothing should have been sent")

    monkeypatch.setattr(tutor_service.httpx, "post", explode)

    with pytest.raises(tutor_service.AssistantUnavailable):
        tutor_service.ask("   ", module_title="M", page_title="P", body_html="<p>t</p>")


def test_a_call_that_does_not_come_back_is_reported_in_words(key, monkeypatch):
    def fail(*a, **k):
        raise OSError("no route to host")

    monkeypatch.setattr(tutor_service.httpx, "post", fail)

    with pytest.raises(tutor_service.AssistantUnavailable) as refused:
        tutor_service.ask("q", module_title="M", page_title="P", body_html="<p>t</p>")

    assert "could not be reached" in str(refused.value)
    assert "still in the box" in str(refused.value)


def test_an_empty_reply_is_treated_as_a_failure(key, monkeypatch):
    """A refused or truncated response comes back well formed and empty, which
    would otherwise render as an answer of nothing at all."""

    class Empty:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": []}}]}

    monkeypatch.setattr(tutor_service.httpx, "post", lambda *a, **k: Empty())

    with pytest.raises(tutor_service.AssistantUnavailable):
        tutor_service.ask("q", module_title="M", page_title="P", body_html="<p>t</p>")


# ------------------------------------------------------------- the answer


def test_the_answer_comes_back_as_text(captured):
    answer = tutor_service.ask(
        "q", module_title="M", page_title="P", body_html="<p>t</p>"
    )

    assert answer == "A forged sender address."


def test_the_key_travels_as_a_parameter_not_in_the_body(captured):
    tutor_service.ask("q", module_title="M", page_title="P", body_html="<p>t</p>")

    assert captured["params"]["key"] == "test-key"
    assert "test-key" not in str(captured["json"])


def test_the_configured_model_is_the_one_called(captured, monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.6-flash")

    tutor_service.ask("q", module_title="M", page_title="P", body_html="<p>t</p>")

    assert "gemini-3.6-flash:generateContent" in captured["url"]
