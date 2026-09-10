# Data Model: Scheduling & Notifications

**Phase 1 output** for [plan.md](./plan.md). One new table and two new columns.

Conventions carry over: naive UTC `DATETIME`, `utf8mb4`, InnoDB, schema from `create_all()`.

---

## Two new columns on `test`

| Column | Type | Null | Notes |
|---|---|---|---|
| `retake_interval_days` | INT | **yes** | How often it must be retaken. Null means one-off |
| `completion_deadline_days` | INT | **yes** | How long after registration a one-off test should be passed. Null means nobody is chased |

### Rules

- **FR-003 / FR-038**, either one requires a pass mark. A cycle that restarts on passing must know what passing means, so both are refused on a test with no `passing_score`.
- **FR-004**, a retake interval shorter than `DUE_SOON_LEAD_DAYS` is refused. The warning would otherwise fire before the person had taken it.
- **FR-039**, with neither set, no due date and no reminder is ever generated for that test.
- **FR-005**, where `retake_interval_days` is set, `allowed_attempts` is ignored. A person may retake until they pass.
- If both are set, the interval wins. The form offers one or the other.

---

## `notification`

One record that one person was told one thing about one module.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `user_id` | INT, FK → `user.id`, indexed | no | |
| `module_id` | INT, FK → `module.id`, indexed | no | Every notification concerns exactly one module |
| `kind` | VARCHAR(20) | no | `registered` · `result` · `due_soon` · `overdue` |
| `due_date` | DATE | **yes** | The due date this concerns. Null for `registered` and `result` |
| `title` | VARCHAR(255) | no | Rendered as written |
| `body` | TEXT | yes | |
| `created_at` | DATETIME | no | |
| `read_at` | DATETIME | **yes** | Null means unseen, this drives the shell indicator |
| `emailed_at` | DATETIME | **yes** | Null means not yet sent, this is what the job selects on |

### The unique constraint that does the work

```
UNIQUE (user_id, kind, module_id, due_date)
```

This single constraint is what makes the daily job safe to run twice (FR-022, FR-024). A repeated run tries to insert the same row and fails at the database rather than relying on the job to remember anything.

`due_date` belongs in the key so that next cycle's `overdue` notification is a **different** row rather than a duplicate of this one. Within one cycle the date does not move, so that row is inserted once and never repeats. Two nulls do not collide in MySQL, which is why repeated `registered` events are prevented by there being only one registration rather than by this key.

### The two nullable timestamps

| Column | Null means | Set when | Read by |
|---|---|---|---|
| `read_at` | The person has not seen it | They open the list | The shell's unread indicator (FR-030, FR-031) |
| `emailed_at` | No message has gone out | A message covering it is sent | The job, which sends only unstamped rows (FR-023, FR-025) |

A send that fails leaves `emailed_at` null, so the next run retries it. Nothing else implements FR-025.

### Record and message are different things

One message may cover several records, a person overdue on three modules gets one email, and all three rows are stamped (FR-019, FR-023). The in-app list still shows three entries (FR-034).

A record always exists before any message is sent (FR-021). The record is the notification; the message is a delivery of it.

---

## The due date, derived, never stored

There is no `due_at` column anywhere. `due.py` computes it from what already exists:

| Test carries | Due date |
|---|---|
| A retake interval, most recent attempt **passed** | that attempt's `submitted_at` + interval |
| A retake interval, **never passed**, attempted or not | `registration.registered_at` + interval |
| A retake interval, most recent attempt did **not** pass, having passed earlier | that attempt's `submitted_at` |
| A completion period, never passed | `registration.registered_at` + period |
| A completion period, passed at any point | never due again (FR-037) |
| Neither | no due date (FR-039) |

Deriving is what makes FR-007 true: an instructor changing the interval re-dates everyone at once, with nothing to migrate.

**Every due date is a fixed calendar date.** No branch returns *now*, so the date an `overdue` row is keyed on does not move from one morning to the next, which is what makes that notification a single event rather than a daily one (FR-014).

**FR-008 gives a newcomer a full first cycle** measured from their registration, whether or not they have attempted and failed. **FR-009 then fixes which attempt starts every later cycle**, the most recent, and only if it passed. Someone who passed and then retook and scored below the pass mark is due immediately, which is the same rule Phases 2 and 3 already apply to what represents a person.

---

## Two states added to Phase 3

`state.py` gains `due` and `overdue`, evaluated after its existing five and only where a due date exists and the person is not currently passed.

```
Phase 3:  no test available · not started · in progress · passed · failed
Phase 4:  + due · overdue
```

They appear everywhere Phase 3's states appear, the trainee's dashboard, the instructor's cohort view, and the module home page, because all three read the same function, each passing in a due date computed at the call site (FR-010).

**FR-011**, passing clears both and sets the next due date a full interval away.
**FR-012**, removing a registration clears both, since the row the derivation reads is gone.

---

## Relationships

```
user ──< notification >── module
```

Both foreign keys enforced by InnoDB. A notification concerns exactly one module, which is what keeps the in-app list granular.

---

## What is deliberately absent

| Not modelled | Why |
|---|---|
| A `due_at` column | Derived, so changing an interval needs no backfill (FR-007) |
| A `last_run` record for the job | The job is a full sweep; a stored last-run would be wrong after a restore or a clock change (research R5, R7) |
| Per-person notification preferences | No opt-out anywhere (spec, Deliberately Excluded) |
| A separate `sent` or `delivery` table | `emailed_at` on the record is enough |
| A retention or expiry rule | Notifications are never deleted (spec, Assumptions) |
| Any notification to an instructor about someone else | Only the person concerned is notified |
