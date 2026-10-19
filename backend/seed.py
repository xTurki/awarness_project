"""Create demo accounts: one admin, one instructor and five trainees.

Demo accounts skip the first-login password change. Safe to run more than once.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.database import engine
from app.models.user import User
from app.security import hash_secret

SEED_PASSWORD = "password"

ACCOUNTS = [
    # The admin uses a real address so the login code can be received.
    ("computingproject6@gmail.com", "admin", "administrator"),
    ("ins@e.com", "Instructor", "instructor"),
    ("1@e.com", "Trainee One", "trainee"),
    ("2@e.com", "Trainee Two", "trainee"),
    ("3@e.com", "Trainee Three", "trainee"),
    ("4@e.com", "Trainee Four", "trainee"),
    ("5@e.com", "Trainee Five", "trainee"),
]


def seed(session: Session) -> list[str]:
    created: list[str] = []
    for email, full_name, role in ACCOUNTS:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing is not None:
            continue
        session.add(
            User(
                email=email,
                full_name=full_name,
                role=role,
                password_hash=hash_secret(SEED_PASSWORD),
                is_active=True,
                must_set_password=False,
            )
        )
        created.append(email)
    session.commit()
    return created


def main() -> None:
    with Session(engine) as session:
        created = seed(session)

    if created:
        print(f"Created {len(created)} accounts. The password for all of them is:")
        print(f"  {SEED_PASSWORD}")
        print()
        for email, full_name, role in ACCOUNTS:
            print(f"  {role:<14} {email:<26} {full_name}")
        print()
        print("Sign-in still needs the emailed code. These accounts are exempt from")
        print("the first-sign-in password change, not from the second factor.")
    else:
        print("Nothing to do: the accounts already exist.")


if __name__ == "__main__":
    main()
