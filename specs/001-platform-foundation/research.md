# Research: Platform Foundation

**Phase 0 output** for [plan.md](./plan.md). Ten decisions the specification deliberately left to implementation.

Nothing here needed investigating in the sense of "which framework" — the stack was settled in `lms-project-spec.md`. What needed settling is how to satisfy a handful of requirements without adding anything the constitution forbids or the project does not need.

---

## R1 — Carrying an in-progress sign-in between the two steps

**Decision**: The verify form carries the email address in a hidden field. Nothing is stored server-side beyond the two `login_code_*` columns already on the account, and no cookie is set between the steps.

**Rationale**: The pending code already lives on the account row, so step two needs only to know which account. A hidden field is the least machinery that achieves it. An earlier draft used a signed cookie to bind the attempt to the browser that started it; that was removed when the security surface was reduced, and re-adding it here would reverse a decision already taken.

**Consequence, accepted**: anyone may submit a guessed code against any email address. R2's rate limit is the only thing bounding that. Recorded in the spec's Assumptions.

**Alternatives considered**: a signed `pending_login` cookie (rejected — removed by owner decision); a short-lived server-side row (rejected — that is the challenge table already discarded in favour of two columns).

---

## R2 — Rate limiting without a fourth container

**Decision**: An in-process fixed-window counter keyed on client IP, held in a module-level dictionary in `app/security.py`. Five attempts per IP per five minutes on `POST /login` and `POST /login/verify`.

**Rationale**: The constitution forbids Redis without a measured bottleneck, and the platform is explicitly a single instance, so process-local state is not a correctness problem. A dictionary with periodic pruning is perhaps twenty lines.

**Consequence, accepted**: counters reset when the container restarts, and the window is fixed rather than sliding. Both are fine at this scale; neither is worth a dependency.

**Alternatives considered**: a `rate_limit` table in MySQL (rejected — a write on every login attempt to solve a problem a dictionary solves); `slowapi` (rejected — a dependency for one rule); Redis (rejected — forbidden, and a fourth container).

---

## R3 — CSRF protection when the login form has no session

**Decision**: Double-submit cookie. A random token is set as a cookie on any `GET` that renders a form, and the same value is placed in a hidden field. On `POST`, the two must match. Implemented as a FastAPI dependency in `app/security.py`.

**Rationale**: FastAPI ships no CSRF protection, and the constitution requires it on **every** state-changing post — including the login form, which by definition has no session behind it. Double-submit needs no server-side storage and works identically before and after sign-in, so there is one mechanism rather than two.

**Alternatives considered**: a token stored in the session (rejected — there is no session at the login form, which is the form most worth protecting); `starlette-csrf` (rejected — a dependency for something this small); skipping CSRF on login (rejected — the constitution says every form).

---

## R4 — Enforcing the forced password change

**Decision**: A FastAPI dependency, `require_password_set`, applied to every authenticated route except the choose-a-password screens and sign-out. It redirects to `/password/new` while `must_set_password` is raised.

**Rationale**: FR-011 requires that no other part of the platform be reachable until a new password is set. A dependency applied at the router level makes that structural rather than something each route has to remember. Middleware would work too but would need a path allow-list, which is easier to get subtly wrong.

**Alternatives considered**: middleware with an exempt-path list (rejected — the allow-list is the bug); a check inside each route (rejected — thirty chances to forget one).

---

## R5 — Waiting for MySQL to be ready

**Decision**: Both belt and braces. A Compose healthcheck (`mysqladmin ping`, 5-second interval, 10 retries) with `depends_on: condition: service_healthy`, **and** a retry loop around the first connection in `database.py` — ten attempts, two seconds apart.

**Rationale**: The healthcheck alone is not enough on a first run: the container reports healthy once the server accepts connections, but initialising the data directory can still be in progress. The retry loop costs a dozen lines and removes an intermittent startup failure that would otherwise be blamed on something else.

**Alternatives considered**: healthcheck only (rejected — known to be flaky on first boot); a wait script in the entrypoint (rejected — moves the logic somewhere less visible).

---

## R6 — Asserting the character set rather than assuming it

**Decision**: The startup lifespan runs `SHOW VARIABLES LIKE 'character_set_%'` and raises if the connection is not `utf8mb4`, before `create_all()`.

**Rationale**: The project specification warns that fixing the charset after tables exist is painful. A wrong charset otherwise announces itself much later as mangled Arabic in a person's name. Failing loudly at boot is far cheaper than discovering it in a term's worth of data.

**Alternatives considered**: setting it in the connection URL and trusting it (rejected — the URL is one of three places it must be right; the assert catches the other two).

---

## R7 — Testing against MySQL, not SQLite

**Decision**: A session-scoped pytest fixture starts a MySQL 8 container, creates the schema with `create_all()`, and drops it afterwards. Each test runs inside a transaction that is rolled back.

**Rationale**: Constitution VI forbids SQLite outright, and for good reason here: this phase relies on a unique index on `email`, on foreign keys, and on `utf8mb4` — none of which SQLite enforces the same way. The transaction-per-test pattern keeps the suite fast without recreating the schema each time.

**Alternatives considered**: SQLite (forbidden); a shared long-lived database (rejected — tests then depend on each other's leftovers); recreating the schema per test (rejected — slow for no benefit).

---

## R8 — Sending mail without blocking the event loop

**Decision**: `smtplib` over `smtp.gmail.com:587` with STARTTLS, executed via `anyio.to_thread.run_sync` with a ten-second timeout, awaited inline within the request.

**Rationale**: `smtplib` is blocking, so calling it directly on the event loop would stall every other request for its duration. A worker thread keeps it off the loop while remaining inline, so the person sees the outcome rather than being sent to a verify page for a code that failed to send. FR-021 requires it fail within a bounded time; the timeout is what delivers that.

**Alternatives considered**: `aiosmtplib` (rejected — a dependency to avoid four lines of threadpool call); a background task (rejected — the person would reach the verify page before the platform knew whether the code was sent); a queue (rejected — forbidden by the constitution).

---

## R9 — Generating and storing the code

**Decision**: `secrets.randbelow(1_000_000)`, zero-padded to six digits. Stored as an Argon2 hash in `login_code_hash`, using the same hasher as passwords.

**Rationale**: The constitution requires codes be stored hashed. Using one hasher for both means one configuration and one thing to get right. `secrets` rather than `random` because the latter is predictable from observed output, which for a login code matters.

**Alternatives considered**: storing the code in plain text (rejected — the constitution forbids it); a separate faster hash for codes (rejected — a second configuration to justify a saving nobody would measure).

---

## R10 — Serving vendored assets and uploaded files

**Decision**: `backend/app/static/` is mounted into the Nginx container as a read-only volume and served directly at `/static/`. Bootstrap and HTMX are committed into that directory rather than loaded from a CDN. FastAPI does not serve static files.

**Rationale**: Keeping static serving out of the Python process is the reason Nginx is in the design at all. Vendoring rather than using a CDN means the platform has no runtime dependency on a third party — which matters for an organisation that may run it on a restricted network.

**Alternatives considered**: FastAPI `StaticFiles` (rejected — Nginx already exists and is better at it); CDN links (rejected — an outbound dependency for every page load, in a product whose whole subject is caution about external things).

---

## Accepted simplifications

Recorded so they read as decisions rather than oversights, consistent with the reduced security surface:

- **Session identifiers are stored as issued, not hashed.** Anyone who can read the database can use a live session. They can also read every account row, so the marginal loss is small.
- **Rate-limit counters are per-process and reset on restart.** Restarting the container clears any lockout.
- **No structured logging or log aggregation.** Whatever Uvicorn prints is what there is.
