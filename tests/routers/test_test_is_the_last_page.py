"""The test closes the module rather than sitting somewhere else.

Somebody reads the pages in order and arrives at it: it is the last entry in the
module sidebar, the last page reaches it by reading forward, and it renders with
the same sidebar so that arriving there does not feel like leaving the module.
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.module import PageWrite
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import content_service, question_service, test_service


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
def pages(db, owner, module):
    made = []
    for title in ("What phishing is", "How to spot it", "What to do"):
        page = content_service.create_page(
            db, owner, module.id, PageWrite(title=title, body="<p>Words.</p>")
        )
        content_service.set_page_published(db, owner, module.id, page.id, True)
        made.append(page)
    return made


@pytest.fixture()
def live_test(db, owner, module):
    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt="Q?", points=1, options=["a", "b"], correct=[0]),
        )
    ]
    created = test_service.create(
        db, owner, module.id,
        TestWrite(title="Phishing check", allowed_attempts=1, passing_score=80,
                  instructions="Answer every question. You need 80% to pass.",
                  question_ids=[q.id for q in questions]),
    )
    test_service.set_published(db, owner, created.id, True)
    return created


@pytest.fixture()
def trainee(db, make_user, module):
    person = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=person.id, module_id=module.id,
                        role_in_module="trainee"))
    db.commit()
    return person


# ------------------------------------------------------------- in the sidebar


def test_the_test_is_the_last_entry_in_the_module_sidebar(
    client, sign_in, trainee, module, pages, live_test
):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}").text

    assert f"/modules/{module.id}/tests/{live_test.id}" in text
    # After every page, because it is what the reading order ends with.
    assert text.index(f"/pages/{pages[-1].id}") < text.index(f"/tests/{live_test.id}")


def test_it_is_marked_as_the_test_rather_than_another_page(
    client, sign_in, trainee, module, pages, live_test
):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}").text

    assert "Phishing check" in text
    assert ">Test</span>" in text


def test_a_module_with_no_published_test_shows_no_such_entry(
    client, sign_in, trainee, module, pages
):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}").text

    assert ">Test</span>" not in text


def test_the_sidebar_is_there_on_the_test_page_too(
    client, sign_in, trainee, module, pages, live_test
):
    """Arriving at the test must not feel like leaving the module."""
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/tests/{live_test.id}").text

    for page in pages:
        assert page.title in text


# --------------------------------------------------------- reading forward


def test_a_middle_page_leads_to_the_next_page(
    client, sign_in, trainee, module, pages, live_test
):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/pages/{pages[0].id}").text

    assert f'href="/modules/{module.id}/pages/{pages[1].id}">Next' in text.replace("\n", " ")


def test_the_last_page_leads_to_the_test(
    client, sign_in, trainee, module, pages, live_test
):
    """The whole point: reading forward ends at the test."""
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/pages/{pages[-1].id}").text

    assert "Finish with the test" in text
    assert f"/modules/{module.id}/tests/{live_test.id}" in text


def test_the_last_page_offers_nothing_when_there_is_no_test(
    client, sign_in, trainee, module, pages
):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/pages/{pages[-1].id}").text

    assert "Finish with the test" not in text


def test_the_first_page_has_no_previous(client, sign_in, trainee, module, pages):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/pages/{pages[0].id}").text

    assert ">Previous<" not in text.replace("\n", "").replace(" ", "")


def test_a_later_page_has_one(client, sign_in, trainee, module, pages):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/pages/{pages[1].id}").text

    assert f'href="/modules/{module.id}/pages/{pages[0].id}">Previous' in text.replace("\n", " ")


# ------------------------------------------------- what the last page says


def test_the_instructions_are_shown_before_the_button(
    client, sign_in, trainee, module, pages, live_test
):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/tests/{live_test.id}").text

    assert "Answer every question. You need 80% to pass." in text
    assert text.index("Answer every question") < text.index("Start the test")


def test_the_terms_are_shown_with_them(client, sign_in, trainee, module, pages, live_test):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/tests/{live_test.id}").text

    assert "Before you start" in text
    assert "Questions:" in text
    assert "Pass mark:" in text


def test_and_the_button_starts_it(client, sign_in, trainee, module, pages, live_test):
    sign_in(trainee)
    text = client.get(f"/modules/{module.id}/tests/{live_test.id}").text

    assert "Start the test" in text
    assert f'action="/tests/{live_test.id}/attempts"' in text
