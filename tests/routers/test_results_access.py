"""The results pages over HTTP.

Two structural facts are asserted here rather than behaviours: `GET /` is
registered exactly once, and no route in this phase names a person except the
instructor's per-person history, which is behind `module:write`.
"""

from __future__ import annotations

import pytest

from app.main import app
from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import attempt_service, question_service, test_service


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
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="instructor"))
    db.commit()
    return person


@pytest.fixture()
def trainee(db, make_user, module):
    person = make_user(email="t@example.com", full_name="Tess Trainee", role="trainee")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="trainee"))
    db.commit()
    return person


@pytest.fixture()
def live_test(db, owner, module):
    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt=f"Q{n}?", points=1, options=["right", "wrong"], correct=[0]),
        )
        for n in (1, 2)
    ]
    created = test_service.create(
        db, owner, module.id,
        TestWrite(title="Check", allowed_attempts=3, passing_score=80,
                  question_ids=[q.id for q in questions]),
    )
    test_service.set_published(db, owner, created.id, True)
    return created


# ------------------------------------------------------------------ structure


def test_the_root_is_registered_exactly_once():
    """Two registrations of `GET /` do not error: the second is shadowed, and
    the page simply never appears. This is what T011 moved to prevent."""
    roots = [route for route in app.routes if route.path == "/"]
    assert len(roots) == 1, f"GET / is registered {len(roots)} times"


def test_no_dashboard_router_remains():
    import importlib

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.routers.dashboard")


def test_no_view_spans_more_than_one_module():
    """Every results path names a module or an attempt, never a bare list
    across them (FR-021, SC-013)."""
    results_paths = {r.path for r in app.routes if "results" in r.path}
    assert results_paths == {
        "/results/modules/{module_id}",
        "/modules/{module_id}/results",
        "/modules/{module_id}/results/{user_id}",
    }


def test_this_phase_adds_no_post():
    """Nothing here enters, adjusts, or weights a score (FR-026)."""
    for route in app.routes:
        if "results" in route.path:
            assert "POST" not in getattr(route, "methods", set()), route.path


# -------------------------------------------------------------- the dashboard


def test_a_trainee_gets_the_results_dashboard(client, sign_in, trainee, module):
    sign_in(trainee)
    page = client.get("/")

    assert page.status_code == 200
    assert "Your training" in page.text
    assert "Phishing Awareness" in page.text


def test_an_administrator_keeps_the_module_dashboard(client, sign_in, make_user):
    sign_in(make_user(email="a@example.com", role="administrator"))
    page = client.get("/")

    assert page.status_code == 200
    assert "Welcome" in page.text


def test_a_trainee_with_nothing_is_told_so(client, sign_in, make_user):
    sign_in(make_user(email="lonely@example.com", role="trainee"))
    page = client.get("/")

    assert page.status_code == 200
    assert "not on any modules" in page.text.lower()


def test_the_state_word_appears_not_only_a_colour(client, sign_in, trainee, live_test):
    """Legible without colour, and without a legend (FR-023)."""
    sign_in(trainee)
    page = client.get("/")

    assert "Not started" in page.text


# ---------------------------------------------------------------- other people


def test_no_route_reaches_another_persons_dashboard(client, sign_in, trainee):
    """There is no path parameter for a person on the dashboard, so there is
    nothing to guard: the route simply does not exist (FR-013)."""
    sign_in(trainee)

    assert client.get("/results/modules/999999").status_code == 404


def test_a_trainee_cannot_open_the_cohort(client, sign_in, trainee, module):
    sign_in(trainee)
    assert client.get(f"/modules/{module.id}/results").status_code == 403


def test_a_trainee_cannot_open_another_persons_history(
    client, sign_in, trainee, module, make_user
):
    other = make_user(email="other@example.com", role="trainee")
    sign_in(trainee)

    assert client.get(f"/modules/{module.id}/results/{other.id}").status_code == 403


def test_an_instructor_elsewhere_is_refused(client, sign_in, make_user, module):
    sign_in(make_user(email="outsider@example.com", role="instructor"))
    assert client.get(f"/modules/{module.id}/results").status_code == 404


def test_the_owner_sees_the_cohort_and_reaches_a_person(
    client, db, sign_in, owner, trainee, module, live_test
):
    sign_in(owner)

    cohort = client.get(f"/modules/{module.id}/results")
    assert cohort.status_code == 200
    assert "Tess Trainee" in cohort.text

    person = client.get(f"/modules/{module.id}/results/{trainee.id}")
    assert person.status_code == 200
    assert "Tess Trainee" in person.text


def test_an_instructor_cannot_reach_somebody_not_on_the_module(
    client, sign_in, owner, module, make_user
):
    stranger = make_user(email="stranger@example.com", role="trainee")
    sign_in(owner)

    assert client.get(f"/modules/{module.id}/results/{stranger.id}").status_code == 404


# ------------------------------------------------------- picking up an attempt


def test_an_unfinished_attempt_is_reachable_from_the_dashboard(
    client, db, sign_in, trainee, live_test
):
    row = attempt_service.start(db, trainee, live_test.id)
    sign_in(trainee)

    page = client.get("/")
    assert "In progress" in page.text
    assert f"/attempts/{row.id}" in page.text
    assert "Resume" in page.text


def test_an_attempt_that_ran_out_reads_as_finished(client, db, sign_in, trainee, live_test):
    """Reading the dashboard triggers Phase 2's expire-on-read, so a lapsed
    attempt shows its outcome rather than sitting as in progress."""
    from datetime import timedelta

    from app.database import utcnow
    from app.models.attempt import Attempt

    row = attempt_service.start(db, trainee, live_test.id)
    stored = db.get(Attempt, row.id)
    stored.ends_at = utcnow() - timedelta(seconds=1)
    db.add(stored)
    db.commit()

    sign_in(trainee)
    page = client.get("/")

    assert "In progress" not in page.text
    assert "Failed" in page.text
