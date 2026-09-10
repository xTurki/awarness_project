"""Nobody puts themselves on the platform (FR-006, SC-011).

Another absence test. Accounts come from an administrator or from the seed, and
there is no third way.
"""

from __future__ import annotations

from app.main import app

FORBIDDEN_WORDS = ("register", "signup", "sign-up", "join")


def test_no_route_looks_like_self_registration():
    paths = {route.path for route in app.routes}
    offending = {
        path
        for path in paths
        if any(word in path.lower() for word in FORBIDDEN_WORDS)
    }
    assert offending == set(), f"unexpected self-registration routes: {offending}"


def test_account_creation_is_unreachable_while_signed_out(client, csrf):
    token = csrf("/login")

    assert client.get("/admin/accounts/new").status_code == 303
    created = client.post(
        "/admin/accounts",
        data={
            "email": "intruder@example.com",
            "full_name": "Intruder",
            "role": "administrator",
            "password": "demo-password",
            "csrf_token": token,
        },
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/login"


def test_account_creation_is_refused_for_a_signed_in_trainee(client, make_user, sign_in, csrf):
    sign_in(make_user(email="t@example.com", role="trainee"))
    token = csrf("/")

    created = client.post(
        "/admin/accounts",
        data={
            "email": "self@example.com",
            "full_name": "Self",
            "role": "administrator",
            "password": "demo-password",
            "csrf_token": token,
        },
    )
    assert created.status_code == 403


def test_the_sign_in_page_offers_no_way_to_create_an_account(client):
    page = client.get("/login")
    assert page.status_code == 200
    lowered = page.text.lower()
    for word in FORBIDDEN_WORDS:
        assert word not in lowered, f"the sign-in page mentions {word!r}"
