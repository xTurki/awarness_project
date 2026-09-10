# Quickstart: Platform Foundation

**Phase 1 output** for [plan.md](./plan.md). How to bring the platform up from nothing and prove this phase actually works.

Every scenario below maps to a user story in [spec.md](./spec.md). Walking all seven is what "Phase 0 is done" means.

---

## Prerequisites

- Docker and Docker Compose
- A Gmail or Google Workspace account with an **App Password**, an ordinary account password will not work for SMTP
- Outbound access to `smtp.gmail.com:587`. **Verify this first.** Without it nobody can sign in, and there is no bypass.

---

## Setup

```bash
cp .env.example .env
# edit .env: MYSQL_* credentials, SESSION_SECRET, SMTP_USER, SMTP_APP_PASSWORD, SMTP_FROM
docker compose up -d
docker compose exec backend python seed.py
```

Open `http://localhost`. You should see the sign-in form.

The seed creates seven accounts: one administrator, one instructor, five trainees. Their addresses and passwords are printed by `seed.py`. **They are exempt from the first-sign-in password change**, so they can be used immediately.

> **Changing a model?** There are no migrations. Run `docker compose down -v && docker compose up -d` and seed again. This is expected and costs nothing while there is no real data.

---

## Scenario 1, Sign in with a second factor *(US1, P1)*

1. Open `http://localhost`, enter the seeded administrator's email and password.
2. You are taken to the code-entry page. A six-digit code arrives by email.
3. Enter it. You reach the dashboard.

**Then check the failures:**

| Try | Expect |
|---|---|
| A wrong code | Refused, still on the page, able to retry |
| A code older than ten minutes | Refused as expired |
| The same code twice | Refused the second time |
| Start a fresh sign-in, then submit the first code | Refused, the newer code replaced it |

---

## Scenario 2, Role-shaped workspace *(US2, P2)*

Sign in as the administrator, the instructor, and a trainee in turn.

- Each sees different navigation; only the administrator sees account administration.
- Signed in as a trainee, request `/admin/accounts` directly. Expect **403**, not a page with the buttons hidden.

---

## Scenario 3, Ending access *(US3, P2)*

1. Sign in as a trainee in one browser. In another, sign in as the administrator.
2. Administrator: deactivate the trainee's account.
3. Trainee: load any page. Expect to be refused and returned to sign-in, **on the very next request**, not at session expiry.
4. Sign in again as anyone, then sign out. Expect protected pages to be unreachable with that session.

---

## Scenario 4, Create a real account *(US4, P2)*

1. As the administrator, create an account with a chosen role and an initial password.
2. Sign in as that new person: password → code → **you are asked to choose a new password before anything else**.
3. Try to reach `/` before setting one. Expect to be returned to the choose-a-password screen.
4. Set one. You reach the dashboard. Sign in again later, you are not asked again.
5. As the administrator, reset that account's password. Sign in as them again: **they are asked to choose one again.**

Also confirm: creating a second account with an email already in use is refused, and no signed-out visitor is offered any way to create an account.

---

## Scenario 5, From nothing *(US5, P3)*

On a machine that has never run this:

```bash
git clone <repo> && cd <repo>
cp .env.example .env && $EDITOR .env
docker compose up -d
docker compose exec backend python seed.py
```

Expect a working sign-in page inside ten minutes, including image pulls.

**Then check the boundaries:**

```bash
curl http://localhost:3306      # expect refused, MySQL is not published
curl http://localhost:8000      # expect refused, the application is not published
docker compose restart          # accounts still there afterwards
```

---

## Scenario 6, When email fails *(US6, P4)*

Break mail deliberately, put a wrong `SMTP_APP_PASSWORD` in `.env` and restart the backend.

Attempt to sign in. Expect to be told plainly, **within about fifteen seconds**, that the code could not be sent and that signing in again is how to retry. You should *not* be left on a code-entry page waiting.

> There is no way in while mail is down. The break-glass command was removed when the security surface was reduced; recovery means editing the database directly.

---

## Scenario 7, Every width *(FR-029, done-gate 3)*

Walk sign-in, code entry, choose-a-password, dashboard, and account administration at each width:

| Width | Expect |
|---|---|
| 360px | Usable, no sideways page scrolling, navigation as a drawer |
| 768px | Usable |
| 1280px | Full layout |

On a phone, the code field should offer the code from the mail notification automatically.

---

## Running the tests

```bash
docker compose exec backend pytest
```

Tests run against a disposable MySQL container, never SQLite (research R7). Running them automatically on every change is deferred to a later phase; this command is the whole of it for now.

---

## Done when

- [ ] All seven scenarios pass
- [ ] `docker compose up` works on a clean machine
- [ ] Test suite green against MySQL
- [ ] No module under `app/routers/` imports `Session` or `select`
- [ ] No `table=True` model reaches a template or an endpoint response
- [ ] Every account-administration service function checks the caller's role
