"""A live Phase 4 scenario, built through the services rather than by hand.

Run once against the seeded database so the scheduled sweep has real people to
find. Delete this file when the phase is signed off; it exists to prove the
scheduler does something, not to be part of the platform.

    docker compose exec backend python scenario_phase4.py
"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.database import engine, utcnow
from app.models.attempt import Attempt
from app.models.module import Module
from app.models.registration import Registration
from app.models.user import User
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import question_service, test_service

INTERVAL = 90


def main() -> None:
    with Session(engine) as db:
        owner = db.exec(
            select(User).where(User.email == "instructor@example.com")
        ).first()
        trainees = db.exec(
            select(User).where(User.role == "trainee").order_by(User.email)
        ).all()

        module = db.exec(
            select(Module).where(Module.title == "Annual Security Refresher")
        ).first()
        if module is None:
            module = Module(
                title="Annual Security Refresher",
                description="Repeats every 90 days.",
                is_published=True,
            )
            db.add(module)
            db.commit()
            db.refresh(module)
            db.add(
                Registration(
                    user_id=owner.id, module_id=module.id, role_in_module="instructor"
                )
            )
            db.commit()

        questions = question_service.list_bank(db, owner, module.id)
        if not questions:
            for n in (1, 2):
                question_service.create_question(
                    db, owner, module.id,
                    QuestionWrite(
                        prompt=f"Security question {n}?",
                        points=1,
                        options=["The right answer", "The wrong one"],
                        correct=[0],
                    ),
                )
            questions = question_service.list_bank(db, owner, module.id)

        tests = test_service.list_for_module(db, owner, module.id)
        if tests:
            recurring = tests[0]
        else:
            recurring = test_service.create(
                db, owner, module.id,
                TestWrite(
                    title="Annual check",
                    allowed_attempts=1,
                    passing_score=80,
                    retake_interval_days=INTERVAL,
                    question_ids=[q.id for q in questions],
                ),
            )
            test_service.set_published(db, owner, recurring.id, True)

        now = utcnow()
        # Registered long ago, so their own first cycle is not what is being
        # measured: each is placed by the attempt they last made.
        placements = [
            ("overdue", INTERVAL + 12),      # passed, and the interval has run out
            ("due soon", INTERVAL - 7),      # passed, inside the warning period
            ("current", 5),                  # passed last week
        ]

        for person, (label, days_since_pass) in zip(trainees, placements):
            if (
                db.exec(
                    select(Registration).where(
                        Registration.module_id == module.id,
                        Registration.user_id == person.id,
                    )
                ).first()
                is None
            ):
                db.add(
                    Registration(
                        user_id=person.id,
                        module_id=module.id,
                        role_in_module="trainee",
                        registered_at=now - timedelta(days=400),
                    )
                )
                db.commit()

            already = db.exec(
                select(Attempt).where(
                    Attempt.test_id == recurring.id, Attempt.user_id == person.id
                )
            ).first()
            if already is None:
                passed_at = now - timedelta(days=days_since_pass)
                db.add(
                    Attempt(
                        test_id=recurring.id,
                        user_id=person.id,
                        attempt_number=1,
                        started_at=passed_at,
                        ends_at=passed_at + timedelta(hours=1),
                        submitted_at=passed_at,
                        is_submitted=True,
                        question_order=[q.id for q in questions],
                        points_earned=2,
                        points_possible=2,
                        score_percent=90,
                        passed=True,
                    )
                )
                db.commit()

            print(f"  {person.email}: passed {days_since_pass} days ago, expect {label}")

        # And one who has never attempted, registered long enough ago that their
        # own first cycle has run out.
        newcomer = trainees[3]
        if (
            db.exec(
                select(Registration).where(
                    Registration.module_id == module.id,
                    Registration.user_id == newcomer.id,
                )
            ).first()
            is None
        ):
            db.add(
                Registration(
                    user_id=newcomer.id,
                    module_id=module.id,
                    role_in_module="trainee",
                    registered_at=now - timedelta(days=INTERVAL + 30),
                )
            )
            db.commit()
        print(f"  {newcomer.email}: never attempted, expect overdue")

        # And one registered yesterday, who has their own full ninety days.
        fresh = trainees[4]
        if (
            db.exec(
                select(Registration).where(
                    Registration.module_id == module.id,
                    Registration.user_id == fresh.id,
                )
            ).first()
            is None
        ):
            db.add(
                Registration(
                    user_id=fresh.id,
                    module_id=module.id,
                    role_in_module="trainee",
                    registered_at=now - timedelta(days=1),
                )
            )
            db.commit()
        print(f"  {fresh.email}: registered yesterday, expect nothing")

        print(f"\nModule {module.id}, test {recurring.id}, interval {INTERVAL} days.")


if __name__ == "__main__":
    main()
