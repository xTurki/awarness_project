"""The assistant panel over HTTP.

The route answers with a fragment rather than a page, because htmx swaps it in
place. So these tests check a fragment: no doctype, no navigation, just the
panel with the thread in it.
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.models.module import Module
from app.models.registration import Registration
from app.schemas.module import PageWrite
from app.services import content_service, tutor_service


@pytest.fixture()
def key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")


@pytest.fixture()
def answers(monkeypatch, key):
    monkeypatch.setattr(
        tutor_service, "ask", lambda question, **kw: f"Answer about: {question}"
    )


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def owner(db, make_user, module):
    person = make_user(email="owner@example.com", role="instructor")
    db.add(Registration(user_id=person.id, module_id=module.id,
                        role_in_module="instructor"))
    db.commit()
    return person


@pytest.fixture()
def page(db, owner, module):
    made = content_service.create_page(
        db, owner, module.id,
        PageWrite(title="What phishing is", body="<p>A forged sender address.</p>"),
    )
    content_service.set_page_published(db, owner, module.id, made.id, True)
    return made


@pytest.fixture()
def trainee(db, make_user, module):
    person = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=person.id, module_id=module.id,
                        role_in_module="trainee"))
    db.commit()
    return person


def _ask(client, csrf, module, page, question, thread=()):
    data = {
        "question": question,
        "csrf_token": csrf(f"/modules/{module.id}/pages/{page.id}"),
    }
    if thread:
        data["asked"] = [q for q, _ in thread]
        data["answered"] = [a for _, a in thread]
    return client.post(f"/modules/{module.id}/pages/{page.id}/ask", data=data)


# ------------------------------------------------------------ on the page


def test_the_panel_is_under_the_page(client, sign_in, trainee, module, page, key):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/pages/{page.id}").text

    assert "Ask about this page" in text
    assert f'hx-post="/modules/{module.id}/pages/{page.id}/ask"' in text


def test_it_is_absent_with_no_key(client, monkeypatch, sign_in, trainee, module, page):
    """No key, no feature: the page renders exactly as it did before this
    existed."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    sign_in(trainee)

    text = client.get(f"/modules/{module.id}/pages/{page.id}").text

    assert "Ask about this page" not in text


def test_it_is_only_on_pages_with_material_to_ask_about(
    client, sign_in, trainee, module, page, key
):
    """Not on the module overview, and not on the test: an assistant that
    answers during a test answers the test."""
    sign_in(trainee)

    assert "Ask about this page" not in client.get(f"/modules/{module.id}").text


# ----------------------------------------------------------- asking


def test_a_question_comes_back_with_its_answer(
    client, sign_in, trainee, module, page, csrf, answers
):
    sign_in(trainee)

    response = _ask(client, csrf, module, page, "what is spoofing?")

    assert response.status_code == 200
    assert "what is spoofing?" in response.text
    assert "Answer about: what is spoofing?" in response.text


def test_the_reply_is_a_fragment_not_a_page(
    client, sign_in, trainee, module, page, csrf, answers
):
    """htmx swaps it into the panel, so a whole document would nest one page
    inside another."""
    sign_in(trainee)

    response = _ask(client, csrf, module, page, "q")

    assert "<!DOCTYPE" not in response.text
    assert "<nav" not in response.text
    assert 'id="ask-panel"' in response.text


def test_the_thread_is_carried_back_for_the_next_question(
    client, sign_in, trainee, module, page, csrf, answers
):
    sign_in(trainee)

    response = _ask(client, csrf, module, page, "first question")

    assert 'name="asked"' in response.text
    assert 'name="answered"' in response.text


def test_an_earlier_exchange_is_kept_and_shown(
    client, sign_in, trainee, module, page, csrf, answers
):
    sign_in(trainee)

    response = _ask(
        client, csrf, module, page, "second question",
        thread=[("first question", "first answer")],
    )

    assert "first question" in response.text
    assert "first answer" in response.text
    assert "second question" in response.text


def test_an_empty_question_is_not_sent_anywhere(
    client, sign_in, trainee, module, page, csrf, key, monkeypatch
):
    def explode(*a, **k):
        raise AssertionError("nothing should have been asked")

    monkeypatch.setattr(tutor_service, "ask", explode)
    sign_in(trainee)

    response = _ask(client, csrf, module, page, "   ")

    assert response.status_code == 200
    assert "Ask a question first" in response.text


# ------------------------------------------------------------ failing


def test_a_failure_keeps_the_question_in_the_box(
    client, sign_in, trainee, module, page, csrf, key, monkeypatch
):
    def fail(*a, **k):
        raise tutor_service.AssistantUnavailable(tutor_service.FAILED)

    monkeypatch.setattr(tutor_service, "ask", fail)
    sign_in(trainee)

    response = _ask(client, csrf, module, page, "a question worth keeping")

    assert response.status_code == 200
    assert "could not be reached" in response.text
    assert "a question worth keeping" in response.text


def test_too_many_questions_are_slowed_rather_than_refused_outright(
    client, sign_in, trainee, module, page, csrf, answers
):
    sign_in(trainee)

    for _ in range(settings.ask_rate_limit):
        _ask(client, csrf, module, page, "q")

    response = _ask(client, csrf, module, page, "one too many")

    assert "a lot of questions" in response.text
    assert "one too many" in response.text


# ------------------------------------------------------------ who may ask


def test_nobody_can_ask_about_a_page_they_cannot_open(
    client, sign_in, make_user, module, page, csrf, answers
):
    """The page is fetched through the same service every other reader uses,
    so the assistant cannot become a way to read somebody else's module."""
    sign_in(make_user(email="stranger@example.com", role="trainee"))

    response = _ask(client, csrf, module, page, "q")

    assert response.status_code == 404


def test_asking_without_a_csrf_token_is_refused(client, sign_in, trainee, module, page):
    sign_in(trainee)

    response = client.post(
        f"/modules/{module.id}/pages/{page.id}/ask", data={"question": "q"}
    )

    assert response.status_code == 403


def test_signing_in_is_required(client, module, page):
    response = client.post(
        f"/modules/{module.id}/pages/{page.id}/ask", data={"question": "q"}
    )

    assert response.status_code in (303, 403)
