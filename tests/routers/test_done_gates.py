"""Architecture checks.

- Routers don't run queries or import Session/select.
- Templates only receive read models, never table rows.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import SQLModel

from app import rendering
from app.models.module import Module
from app.models.registration import Registration

ROUTERS = Path(rendering.__file__).parent / "routers"


# ------------------------------------------------------------- no queries


def test_no_router_names_session_or_select():
    """Routers don't contain `Session` or `select` (they use the `Db` alias)."""
    offenders = []
    for path in sorted(ROUTERS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in ("Session", "select"):
            if token in text:
                offenders.append(f"{path.name} contains {token!r}")

    assert offenders == []


# ----------------------------------------------------- read models only


@pytest.fixture()
def captured(monkeypatch):
    """Record every template context while active."""
    seen: list[tuple[str, dict]] = []
    original = rendering.templates.TemplateResponse

    def recording(*args, **kwargs):
        seen.append((kwargs.get("name", ""), dict(kwargs.get("context", {}))))
        return original(*args, **kwargs)

    monkeypatch.setattr(rendering.templates, "TemplateResponse", recording)
    return seen


def _table_models(value, path="") -> list[str]:
    """Find table rows in a template context."""
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
    """No page passes a table row to a template."""
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
