# Contract: HTTP Routes

**Phase 1 output** for [plan.md](./plan.md).

This phase adds **two routes** and one field to an existing form. Most of its behaviour is not reachable by HTTP at all — it happens in the daily job, which is documented below as a contract of its own because it is the interface that matters.

**Guards** carry over: `auth`, `module:write`.

---

## Notifications

| Method | Path | Guard | Result |
|---|---|---|---|
| GET | `/notifications` | auth | The caller's notifications, newest first. Each says what it concerns and when it arrived, and links to its module. Opening the list stamps everything shown as seen (FR-031). |
| POST | `/notifications/read` | auth | Marks the caller's notifications seen. Used where the list is opened without a full page load. |

`/notifications` shows the caller's own and nobody else's. There is no path parameter for a person, so no route reaches another's (FR-033).

### The shell indicator

Every authenticated page renders an unread count from `notification` where `read_at IS NULL` for the caller (FR-030). It is a component, not a route.

---

## Setting a schedule

No new route. The **Phase 2 test form** gains two fields:

| Field | Applies when | Refused if |
|---|---|---|
| `retake_interval_days` | The test should recur | No pass mark (FR-003), or shorter than the warning period (FR-004) |
| `completion_deadline_days` | The test is one-off but should be chased | No pass mark (FR-038) |

Both are optional. Neither set means nobody is ever chased about that test (FR-039).

Trainees see the retake interval on the test detail page from Phase 2 (FR-006).

---

## The daily job

Not an HTTP route. It is the contract that matters most in this phase, so it is specified here.

**Signature**: `run_daily(session, today: date) -> RunSummary`

The date is a parameter rather than read from the clock, so a test can run it for any day.

**What it does, in order:**

1. For every active registration on a module whose test carries an interval or a completion period, compute the due date (`due.py`).
2. Where the due date is within `DUE_SOON_LEAD_DAYS`, insert a `due_soon` notification for that person and module. Where it has passed, insert `overdue`.
3. Insertions that violate the unique constraint are skipped — that is what makes a second run create nothing (FR-024).
4. Group each person's unsent `due_soon` and `overdue` rows into **one** email.
5. Send. Stamp `emailed_at` on every row that message covered.
6. A send that fails leaves its rows unstamped, so a later run retries (FR-025).

**Guarantees**

| Property | How |
|---|---|
| Running twice changes nothing | Unique constraint, plus sending only unstamped rows |
| A missed run costs nobody | The job asks who is due *now*, not what changed (FR-027) |
| No message without a record | Records are inserted before any send (FR-021) |
| One message, several records | Grouped at step 4, all stamped at step 5 (FR-019) |

**Schedule**: once a day at `SCHEDULER_HOUR_UTC`, started in the application lifespan. No second machine, no worker, no broker (FR-028).

---

## Immediate notifications

No routes of their own. Two existing actions gain a notification, created and emailed inline (FR-018):

| Existing action | Notification |
|---|---|
| `POST /modules/{id}/roster` (Phase 1) | `registered`, one per person registered |
| `POST /attempts/{aid}/submit` (Phase 2) | `result`, to the person who submitted |

---

## What is not exposed

| Absent | Why |
|---|---|
| Any route reaching another person's notifications | FR-033 |
| A route to turn notifications off, or choose which arrive | No preferences anywhere |
| An unsubscribe link in any email | Same |
| A route to trigger the daily job | It runs on a schedule; tests call the function directly |
| A route showing who was notified | Out of scope |
| Any channel beyond in-app and email | Out of scope |

---

## Response conventions

| Situation | Response |
|---|---|
| No notifications at all | 200 with a clear statement, not an empty list |
| Following a notification whose module you left | 404 — the registration is gone |
| Setting an interval on a module you do not run | 403 |
| Setting an interval with no pass mark | Back to the form, explaining that a pass mark is needed first |
