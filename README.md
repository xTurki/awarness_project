# SME Cybersecurity Awareness Training Platform

A small platform for assigning cybersecurity awareness training inside one
organisation, tracking who has completed it, and chasing the people who have not.

Built in five phases. **Phase 0 — identity, access, and the application shell —
is the part that exists today.** Modules and content arrive in Phase 1, tests in
Phase 2, results in Phase 3, and scheduling and notifications in Phase 4. The
specifications for all five live under [`specs/`](specs/).

## Before you start

- Docker and Docker Compose.
- A Gmail or Google Workspace account with an **App Password**. An ordinary
  account password will not work for SMTP.
- Outbound access to `smtp.gmail.com:587`. **Verify this first.** Every sign-in
  needs an emailed code and there is no bypass: if mail is down, nobody can sign
  in until it is back.

## Setup

```bash
cp .env.example .env
# edit .env: MYSQL_* credentials, SESSION_SECRET, SMTP_USER, SMTP_APP_PASSWORD, SMTP_FROM
docker compose up -d --build
docker compose exec backend python seed.py
```

Open <http://localhost>. You should see the sign-in page.

`seed.py` prints the seven demonstration accounts it created and their shared
password: one administrator, one instructor, five trainees. They are exempt from
the first-sign-in password change — **not** from the emailed code.

## Signing in

Email and password, then a six-digit code sent to that address. Every sign-in,
for everyone, every time. There is no trusted device and no remembered browser.

An account an administrator created or reset must choose its own password before
anything else is reachable.

## Running the tests

```bash
docker compose exec backend pytest
```

That single command is the whole suite. Tests run against a disposable schema on
the same MySQL server, never SQLite — this project depends on foreign keys, a
unique index, and `utf8mb4`, and SQLite enforces none of them the same way.

## Changing a model

There are no migrations. `create_all()` creates missing tables and never alters
an existing one, so a changed model against a stale schema fails at runtime:

```bash
docker compose down -v && docker compose up -d --build
docker compose exec backend python seed.py
```

This is free while there is no real data, and it is expected to stay that way
until the end of Phase 3.

## What this deliberately does not do

- **No self-registration.** Accounts come from an administrator or from the seed.
- **No self-service password reset.** An administrator resets it; the person then
  chooses their own. Someone who forgets their password and cannot reach an
  administrator has no route back.
- **No audit trail.** Nothing records who did what.
- **No backup.** The database lives in one Docker volume on one machine. If that
  volume is lost, the data is gone.
- **No application logging** beyond whatever the server prints.
- **English, left to right, only.**

Each of these is a recorded decision, not an oversight. The reasoning is in
[`specs/001-platform-foundation/spec.md`](specs/001-platform-foundation/spec.md).

## Layout

```text
docker-compose.yml     three services; only nginx publishes a port
nginx/                 reverse proxy, and the only thing serving /static/
backend/app/
├── models/            the schema — SQLModel table classes
├── schemas/           non-table models at every boundary, in and out
├── services/          business logic, authorisation, and every query
├── routers/           thin: parse, call one service, render or redirect
└── templates/         Jinja2, with Bootstrap and HTMX vendored under static/
tests/                 pytest, against MySQL
specs/                 the specification, plan, and tasks for all five phases
```
