# Data Model: Platform Foundation

**Phase 1 output** for [plan.md](./plan.md). Two tables. Everything in this phase is one of them.

All timestamps are **naive UTC** `DATETIME`. All string columns are `utf8mb4`. Engine is InnoDB throughout. The schema is produced by `SQLModel.metadata.create_all()` at startup; there is no migration tool, so changing anything here before real data exists means `docker compose down -v && docker compose up`.

---

## `user`

A person who can sign in.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `email` | VARCHAR(255), **unique index** | no | 255 is the practical ceiling for a `utf8mb4` unique index. Stored lowercased. |
| `full_name` | VARCHAR(255) | no | |
| `password_hash` | VARCHAR(255) | no | Argon2. Never rendered, never returned. |
| `role` | VARCHAR(20) | no | `administrator` · `instructor` · `trainee` |
| `is_active` | BOOL | no | Default true |
| `must_set_password` | BOOL | no | Default false; true whenever an administrator creates the account or resets its password |
| `login_code_hash` | VARCHAR(255) | **yes** | Argon2 hash of the pending six-digit code |
| `login_code_expires_at` | DATETIME | **yes** | When that code stops working |
| `created_at` | DATETIME | no | |

### Rules

- **FR-001** — `email` is unique platform-wide; comparison and storage are lowercase, so `Ahmad@x.com` and `ahmad@x.com` are one account.
- **FR-002** — `password_hash` holds an Argon2 digest and nothing else.
- **FR-005** — a password of fewer than eight characters is refused wherever one is set: seeding, administrator creation, administrator reset, and the person's own choice.
- **FR-010/011** — `must_set_password` is raised by administrator creation and administrator reset, and cleared only when the person sets their own.
- **FR-016/017/018** — the two `login_code_*` columns are written together and cleared together. Both `NULL` means no sign-in is in progress.
- **Never rendered.** This is a `table=True` model carrying two secrets; done-gate 5 forbids passing it to a template or returning it from an endpoint. Templates receive a `UserRead` built in the service layer.

### Login-code lifecycle

```
both NULL ──── password accepted ────▶ hash + expiry set, code emailed
    ▲                                              │
    │                                     correct code, in time
    │                                              │
    └────────────── cleared ◀──────────────────────┘
                       ▲
                       └── overwritten by any fresh sign-in for the same account
```

There is no attempt counter and no lock. A code stops working when it expires, when it is used, or when a newer one replaces it — and nothing else.

### Account state

```
                 ┌── administrator deactivates ──▶ inactive
   active ───────┤                                    │
      ▲          └── (never deleted)                  │
      └──── administrator reactivates ────────────────┘
```

An inactive account is refused at sign-in and on every subsequent request from an existing session. Accounts are never removed.

---

## `session`

Evidence that an account signed in successfully. Held here rather than in the browser, so access can be withdrawn at any moment.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | VARCHAR(64), PK | no | `secrets.token_urlsafe(32)`. Stored as issued — see research, accepted simplifications |
| `user_id` | INT, FK → `user.id`, indexed | no | |
| `created_at` | DATETIME | no | |
| `expires_at` | DATETIME | no | `created_at` + 12 hours |
| `ip` | VARCHAR(45) | yes | IPv6-sized |
| `user_agent` | VARCHAR(255) | yes | Truncated |

### Rules

- **FR-022** — a request is authenticated by looking this row up, so deleting it withdraws access immediately.
- **FR-023** — sign-out deletes the row.
- **FR-024** — a row past `expires_at` is refused and deleted on sight.
- Expired rows for all accounts are swept opportunistically on each successful sign-in. There is no scheduled cleanup in this phase.
- The foreign key is enforced by InnoDB, not only by the ORM.

---

## What is deliberately absent

| Not modelled | Why |
|---|---|
| Any audit or history table | The platform carries no audit trail (spec, Deliberately Excluded) |
| A login-attempt or lockout table | Rate limiting is in-process (research R2) |
| A pending-login or challenge table | The code lives in two columns on `user`; the verify form carries the email (research R1) |
| A password-reset token table | There is no self-service reset; an administrator resets and the owner then chooses their own |
| Any module, test, or result table | Phases 1–4 |

---

## Seed data

`seed.py` creates seven accounts: one administrator, one instructor, five trainees. All are created with `must_set_password` **false** — demonstration accounts are exempt so the platform can be shown working without a detour (spec, Assumptions). Real accounts an administrator creates are never exempt.
