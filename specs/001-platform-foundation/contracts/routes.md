# Contract: HTTP Routes

**Phase 1 output** for [plan.md](./plan.md).

This is a server-rendered application. It exposes no JSON API and no machine-readable interface, so its contract is its HTTP surface: what a browser may request, what each route requires, and what comes back. That is what this file records.

**Conventions used below**

- **Guard** — the dependencies a route sits behind. `anon` = signed out, `auth` = a valid session, `pwd` = `must_set_password` cleared (research R4), `admin` = role is administrator.
- Every `POST` carries a CSRF token as a hidden field, matched against a cookie (research R3). Omitted from each row to avoid repeating it eleven times.
- Rate-limited routes are marked **RL**. Five attempts per IP per five minutes (research R2).

---

## Signing in

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| GET | `/login` | anon | — | The sign-in form. A signed-in visitor is redirected to `/`. |
| POST | `/login` | anon **RL** | `email`, `password` | On success: a code is emailed, redirect to `GET /login/verify?email=…`. On failure: the form again with a message. On mail failure: the form again saying the code could not be sent and to try again. |
| GET | `/login/verify` | anon | `email` (query) | The code-entry form, carrying `email` in a hidden field. |
| POST | `/login/verify` | anon **RL** | `email`, `code` | On success: session created, cookie set, redirect to `/` — or to `/password/new` if the account must set one. On failure: the form again, distinguishing wrong from expired. |
| POST | `/logout` | auth | — | Session row deleted, cookie cleared, redirect to `/login`. |

**Failure messages** on `POST /login` do not distinguish an unknown address, a wrong password, and a disabled account only insofar as all three simply fail — the identical-response requirement was removed with the reduced security surface, so ordinary messages are acceptable here.

**FR-018** — starting a fresh sign-in overwrites any outstanding code for that account.

---

## Choosing your own password

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| GET | `/password/new` | auth | — | The choose-a-password form. Redirects to `/` if nothing is required. |
| POST | `/password/new` | auth | `password`, `confirm` | On success: `must_set_password` cleared, redirect to `/`. On failure: the form again, saying what the password must satisfy. |

These two are the only authenticated routes **not** behind `pwd`. Everything else redirects here while the flag is raised (FR-011).

---

## The workspace

| Method | Path | Guard | Result |
|---|---|---|---|
| GET | `/` | auth + pwd | The dashboard, with navigation determined by role (FR-027). Largely empty in this phase — modules arrive in Phase 1. |

---

## Account administration

Every route here is behind `admin`. A non-administrator receives 403, not a hidden button (FR-028).

| Method | Path | Sends | Result |
|---|---|---|---|
| GET | `/admin/accounts` | — | Every account: email, name, role, active (FR-007). |
| GET | `/admin/accounts/new` | — | The creation form. |
| POST | `/admin/accounts` | `email`, `full_name`, `role`, `password` | Creates the account with `must_set_password` raised. Refuses a duplicate email. |
| GET | `/admin/accounts/{id}` | — | The edit form. |
| POST | `/admin/accounts/{id}` | `email`, `full_name`, `role` | Updates the account. Refuses an email already used by another. |
| POST | `/admin/accounts/{id}/password` | `password` | Sets a new password and raises `must_set_password`, so the owner must replace it (FR-010). |
| POST | `/admin/accounts/{id}/active` | `is_active` | Deactivates or reactivates. Deactivation takes effect on that account's very next request (FR-003). |

There is no delete route. Accounts are deactivated, never removed.

---

## Static assets

`/static/*` is served by Nginx from a volume shared with the backend (research R10). The application never serves it.

---

## What is not exposed

| Absent | Why |
|---|---|
| Any JSON or machine-readable endpoint | Server-rendered throughout; no second frontend exists to consume one |
| A registration route | No self-registration anywhere (FR-006) |
| A password-reset request route | No self-service reset; an administrator resets |
| A resend-code route | Signing in again issues a fresh code |
| A command-line entry point | The break-glass command was removed with the reduced security surface |

---

## Cookies

| Name | Set at | Attributes | Holds |
|---|---|---|---|
| `session` | successful code verification | `HttpOnly`, `Secure`, `SameSite=Lax`, expires with the session | The session identifier |
| `csrftoken` | any GET rendering a form | `Secure`, `SameSite=Lax` (readable by the template, not by script it does not need to be) | A random token, matched against the hidden field |

`Secure` is set based on `X-Forwarded-Proto` from Nginx.
