"""The two done-gates that are mechanical, run as tests rather than by eye.

Gate 4 is a grep. Gate 5 is not: it needs a page to actually render, because
what a route hands a template is only visible when it does. Running gate 5 this
way is what found `current_test` handing a `table=True` row to two templates,
which reading the routers had not.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel

from app import rendering
from app.models.module import Module
from app.models.registration import Registration

ROUTERS = Path(rendering.__file__).parent / "routers"


# ------------------------------------------------------------------- gate 4


def test_no_router_names_session_or_select():
    """Routers hold no query and no session type. They annotate with `Db`, the
    alias `database.py` exists to provide, so this stays a grep."""
    offenders = []
    for path in sorted(ROUTERS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in ("Session", "select"):
            if token in text:
                offenders.append(f"{path.name} contains {token!r}")

    assert offenders == []


# ------------------------------------------------------------------- gate 5


@pytest.fixture()
def captured(monkeypatch):
    """Every context handed to a template while this fixture is active."""
    seen: list[tuple[str, dict]] = []
    original = rendering.templates.TemplateResponse

    def recording(*args, **kwargs):
        seen.append((kwargs.get("name", ""), dict(kwargs.get("context", {}))))
        return original(*args, **kwargs)

    monkeypatch.setattr(rendering.templates, "TemplateResponse", recording)
    return seen


def _table_models(value, path="") -> list[str]:
    """Anything reaching a template that is a row rather than a read model."""
    if isinstance(value, SQLModel) and getattr(type(value), "__table__", None) is not None:
        return [f"{path}: {type(value).__name__}"]

    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found += _table_models(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            found += _table_models(item, f"{path}[{index}]")
    return found


def test_no_template_receives_a_table_model(
    client, db, sign_in, make_user, captured
):
    """Read models at every boundary, on every page this phase can reach."""
    person = make_user(email="a@example.com", role="administrator")
    module = Module(title="Phishing Awareness", is_published=True)
    db.add(module)
    db.commit()
    db.refresh(module)
    db.add(
        Registration(user_id=person.id, module_id=module.id, role_in_module="instructor")
    )
    db.commit()
    sign_in(person)

    for path in (
        "/",
        "/modules",
        f"/modules/{module.id}",
        f"/modules/{module.id}/tests",
        f"/modules/{module.id}/tests/new",
        f"/modules/{module.id}/roster",
        f"/modules/{module.id}/results",
        f"/results/modules/{module.id}",
        "/notifications",
        "/admin/accounts",
    ):
        assert client.get(path).status_code == 200, path

    offenders: list[str] = []
    for template, context in captured:
        for found in _table_models(context):
            offenders.append(f"{template} -> {found}")

    assert offenders == [], "a table=True row reached a template"
    assert captured, "no page rendered, so nothing was checked"
