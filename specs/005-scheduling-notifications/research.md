# Research: Scheduling & Notifications

**Phase 0 output** for [plan.md](./plan.md). Eight decisions.

One new dependency. Everything else arranges what exists.

---

## R1 — Due dates as a pure function

**Decision**: `due.py` holds `due_date_for(test, registration, attempts) -> date | None`. No session, no implicit clock. The rule:

```
retake_interval_days set:
    last = most recent submitted attempt
    if never passed:                 registration.registered_at + interval
    elif last passed:                last.submitted_at + interval
    else:                            last.submitted_at
completion_deadline_days set (and no interval):
    if any attempt passed:           None — never due again
    else:                            registered_at + deadline
neither set:
    None
```

**Rationale**: FR-007 requires derivation rather than storage, so changing an interval re-dates everyone with no migration and no backfill. FR-008 gives someone who has never passed a full first cycle from their registration, so a new member of staff is not overdue the morning after they are added and an early failed attempt does not shorten their time. FR-009 then fixes which attempt starts every later cycle — the most recent, and only if it passed, matching what Phases 2 and 3 already decided represents a person.

Every branch returns a fixed date and none returns *now*, which is what makes an overdue notification a single event rather than a daily one (FR-014).

Pure because this is the arithmetic with the most cases in the phase, and a function taking rows and returning a date is a table-driven test.

**Alternatives considered**: a stored `due_at` column (rejected — FR-007, and it would need rewriting for everyone whenever an interval changed); computing inside the daily job (rejected — then the results page would need its own copy of the rule).

---

## R2 — Extending Phase 3's state function rather than replacing it

**Decision**: `state.py` gains two states. The existing five are evaluated first; `due` and `overdue` are considered only where a due date exists and the person has not passed within it.

```
existing five (Phase 3)  →  then, if a due date exists and they are not currently passed:
                              due       due date within the warning period, or reached
                              overdue   due date passed
```

**Rationale**: FR-010 says these states appear "everywhere those states are shown", which is Phase 3's two pages plus the module list. Extending the one function means all of them gain the states at once, with no page needing to know.

**Alternatives considered**: a separate due-state function (rejected — two rules, and pages would have to combine them); recomputing state in each template (rejected — the rule is not a presentation concern).

---

## R3 — One record per module, one message per person

**Decision**: The job creates one `notification` row per person per module per event. It then groups a person's unsent due and overdue rows into **one** email and stamps every row it covered.

**Rationale**: FR-017 wants a record per module so the in-app list stays granular (FR-034). FR-019 wants one message so somebody overdue on three modules gets one email rather than three. Both hold at once because the record and the message are different things — the record is the notification, the message is a delivery of it (FR-021).

**Alternatives considered**: one record per message (rejected — the in-app list would then show one lumped entry, breaking FR-034); one message per record (rejected — three emails to the same person in one morning).

---

## R4 — Registration and result notifications sent inline

**Decision**: Created and emailed during the request that caused them, using Phase 0's `email_service` in a worker thread.

**Rationale**: FR-018 requires them immediate and individual. Both events already happen inside a request, so the daily job has nothing to add. A registration notification sent tomorrow morning is not a registration notification.

**Alternatives considered**: letting the daily job pick them up (rejected — up to 24 hours late); a queue (rejected — forbidden, and unnecessary).

---

## R5 — Making a second run harmless

**Decision**: Two mechanisms, neither relying on the job remembering when it last ran.

1. **A unique constraint** on `(user_id, kind, module_id, due_date)` — inserting the same notification twice fails at the database, so a repeated run creates nothing.
2. **Sending only unstamped rows** — the job selects rows where `emailed_at IS NULL`, sends, then stamps them. A repeated run finds nothing to send.

**Rationale**: FR-024 requires no duplicate record and no second message on a repeated run, and FR-025 requires an undelivered notification to be retried later — which the unstamped-row rule gives for free, since a failed send leaves the row unstamped.

Not tracking "last run date" is deliberate: a stored last-run timestamp is wrong after a restore, wrong if the clock moves, and wrong if a run half-completed. A constraint and a nullable column cannot be wrong.

`due_date` is part of the key so next cycle's notification is a different row rather than a duplicate of this one. Within a cycle the date does not move, so the overdue row is inserted once — which is the whole of FR-014.

**Alternatives considered**: a `last_run` table (rejected — the failure modes above); checking "did we already notify today" in Python (rejected — a race between two runs, and it is what the constraint does better).

---

## R6 — Scheduling in-process

**Decision**: `APScheduler`'s `AsyncIOScheduler`, started in the FastAPI lifespan, one cron job at `SCHEDULER_HOUR_UTC`. The job function takes a session and a date and is otherwise ordinary.

**Rationale**: The constitution permits scheduled work in-process and forbids a broker, a worker container, or a separate cron container. APScheduler is the smallest thing that does it, and it starts and stops with the application.

**This assumes one `backend` instance.** Two would run two schedulers. The unique constraint makes that produce duplicate work rather than duplicate emails, but the platform is single-instance by design throughout and this is one more place it matters.

**Alternatives considered**: a cron container (rejected — forbidden, and a second place to configure); Celery beat (rejected — a broker and a worker for one job a day); a `while True: sleep` thread (rejected — APScheduler already handles missed runs and shutdown, which that would have to reimplement).

---

## R7 — Missing a run costs nothing

**Decision**: The job asks "who is due or overdue **now**", never "what changed since last time". A run that never happened leaves people due; the next run finds them.

**Rationale**: FR-027. Because due dates are derived (R1) and duplicates are prevented by constraint (R5), the job is a full sweep rather than a delta. That makes a missed run, a restart, or a manual run all safe — which is what lets tests simply call it.

**Alternatives considered**: processing a window since the last run (rejected — needs a last-run record, and a missed window silently skips people).

---

## R8 — The unread indicator

**Decision**: A count of the caller's notifications with `read_at IS NULL`, rendered in the shell. Opening the list stamps `read_at` on everything shown.

**Rationale**: FR-030 and FR-031. Marking on open rather than on individual click is the simpler behaviour and matches what people expect — there is no separate dismiss action (spec, Assumptions).

**Alternatives considered**: per-notification dismiss (rejected — a control nobody asked for); never marking read (rejected — the indicator would never clear).

---

## Notes for implementation

- **`state.py` and `due.py` are both imported by the daily job and by Phase 3's pages.** Neither takes a session; both take rows.
- **The digest email lists modules, the in-app list holds one row each.** Same information, grouped differently.
- **An email failure leaves rows unstamped**, so the next run retries. Nothing else is needed for FR-025.
- **`retake_interval_days` and `completion_deadline_days` are mutually exclusive in practice** — the interval wins if both are set, and the form offers one or the other.
- **Attempt limits are ignored on a recurring test** (FR-005): `attempt_service` checks for an interval before enforcing `allowed_attempts`.
