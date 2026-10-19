"""Loads the training modules from seed_content/training_content.json at startup.

Modules whose title already exists are skipped, so restarts don't duplicate
content or overwrite admin edits.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session, select

from app.database import engine
from app.models.module import Module
from app.models.page import Page
from app.models.question import AnswerOption, Question
from app.models.test import Test, TestQuestion
from app.sanitise import sanitise

CONTENT_FILE = Path(__file__).parent / "seed_content" / "training_content.json"

QUIZ_TITLE = "End-of-module quiz"
PASSING_SCORE = 70
ALLOWED_ATTEMPTS = 2


def seed_content(db: Session) -> list[str]:
    data = json.loads(CONTENT_FILE.read_text(encoding="utf-8"))
    created: list[str] = []
    for item in data["modules"]:
        exists = db.exec(select(Module).where(Module.title == item["title"])).first()
        if exists is None:
            _add_module(db, item)
            created.append(item["title"])
    return created


def _add_module(db: Session, item: dict) -> None:
    module = Module(title=item["title"], description=item["description"], is_published=True)
    db.add(module)
    db.flush()

    for position, page in enumerate(item["pages"], start=1):
        db.add(
            Page(
                module_id=module.id,
                title=page["title"],
                body=sanitise(page["body"]),
                position=position,
                is_published=True,
            )
        )

    quiz_ids: list[int] = []
    for position, q in enumerate(item["quiz"] + item["bank"], start=1):
        question = Question(module_id=module.id, prompt=q["prompt"], points=1, position=position)
        db.add(question)
        db.flush()
        for n, option in enumerate(q["options"], start=1):
            db.add(
                AnswerOption(
                    question_id=question.id,
                    text=option["text"],
                    is_correct=option["correct"],
                    position=n,
                )
            )
        if position <= len(item["quiz"]):
            quiz_ids.append(question.id)

    test = Test(
        module_id=module.id,
        title=QUIZ_TITLE,
        passing_score=PASSING_SCORE,
        allowed_attempts=ALLOWED_ATTEMPTS,
        is_published=True,
    )
    db.add(test)
    db.flush()
    for position, question_id in enumerate(quiz_ids, start=1):
        db.add(TestQuestion(test_id=test.id, question_id=question_id, position=position))

    db.commit()


def run() -> None:
    with Session(engine) as db:
        created = seed_content(db)
    if created:
        print(f"[content] loaded {len(created)} modules: {', '.join(created)}", flush=True)
