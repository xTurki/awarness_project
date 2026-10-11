"""The four training modules loaded at startup from the Word document's content."""

from __future__ import annotations

from sqlmodel import select

from app.content_seed import seed_content
from app.models.module import Module
from app.models.page import Page
from app.models.question import AnswerOption, Question
from app.models.test import Test
from app.models.test import TestQuestion as QuizQuestion


def test_loads_four_published_modules_with_pages_bank_and_quiz(db):
    created = seed_content(db)

    assert len(created) == 4
    modules = db.exec(select(Module)).all()
    assert all(m.is_published for m in modules)
    for module in modules:
        pages = db.exec(select(Page).where(Page.module_id == module.id)).all()
        questions = db.exec(select(Question).where(Question.module_id == module.id)).all()
        tests = db.exec(select(Test).where(Test.module_id == module.id)).all()

        assert len(pages) == 6 and all(p.is_published for p in pages)
        assert len(questions) == 20
        assert len(tests) == 1
        quiz = tests[0]
        assert quiz.is_published and quiz.passing_score == 70 and quiz.allowed_attempts == 2
        assert len(db.exec(select(QuizQuestion).where(QuizQuestion.test_id == quiz.id)).all()) == 10


def test_every_question_has_four_options_and_one_correct(db):
    seed_content(db)
    for question in db.exec(select(Question)).all():
        options = db.exec(select(AnswerOption).where(AnswerOption.question_id == question.id)).all()
        assert len(options) == 4
        assert sum(o.is_correct for o in options) == 1


def test_running_twice_creates_nothing_the_second_time(db):
    seed_content(db)
    assert seed_content(db) == []
    assert len(db.exec(select(Module)).all()) == 4
