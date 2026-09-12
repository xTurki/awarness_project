"""Create the demonstration accounts for a fresh installation.

Seven accounts: one administrator, one instructor, five trainees. All are created
with `must_set_password` **false**, demonstration accounts are exempt so the
platform can be shown working without a detour. Accounts an administrator creates
are never exempt (spec Assumptions).

Running this twice creates nothing the second time.
"""

from __future__ import annotations

from sqlmodel import Session, select

from app.database import engine
from app.models.user import User
from app.security import hash_secret

SEED_PASSWORD = "password"

ACCOUNTS = [
    # The administrator uses the real sending address, so a fresh installation can
    # be signed into with a code that actually arrives. Everyone else is a placeholder.
    ("computingproject6@gmail.com", "admin", "administrator"),
    ("ins@e.com", "Iris Instructor", "instructor"),
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
