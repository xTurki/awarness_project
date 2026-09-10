# Data Model: Quizzes

**Phase 1 output** for [plan.md](./plan.md). Five new tables. Everything from Phases 0 and 1 is unchanged.

Conventions carry over: naive UTC `DATETIME`, `utf8mb4`, InnoDB, schema from `create_all()`.

---

## `question`

One question in a module's bank.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `module_id` | INT, FK → `module.id`, indexed | no | The bank belongs to the module, not to a test |
| `prompt` | TEXT | no | Plain text |
| `points` | INT | no | Default 1 |
| `position` | INT | no | Order within the bank |
| `created_at` | DATETIME | no | |

There is no `type` column. Multiple choice is the only kind (spec, Deliberately Excluded).

---

## `answer_option`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `question_id` | INT, FK → `question.id`, indexed | no | Cascade delete |
| `text` | VARCHAR(500) | no | |
| `is_correct` | BOOL | no | |
| `position` | INT | no | |

**Validated on save (FR-003)**: at least two options, at least one correct. Both are checked in `question_service`, not left to the database.

How many are correct also decides presentation — one means radio buttons, several means checkboxes (FR-005, research R7).

---

## `test`

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `module_id` | INT, FK → `module.id`, indexed | no | |
| `title` | VARCHAR(255) | no | |
| `instructions` | TEXT | yes | Plain text |
| `is_published` | BOOL | no | Default false |
| `opens_at` | DATETIME | yes | Null means open from the start |
| `closes_at` | DATETIME | yes | Null means never closes |
| `time_limit_minutes` | INT | yes | Null means untimed |
| `allowed_attempts` | INT | no | Default 1 |
| `shuffle_questions` | BOOL | no | Default false |
| `passing_score` | INT | yes | A percentage |
| `created_at` | DATETIME | no | |

**Frozen once attempted (FR-013).** No column records this — the check is whether any attempt row exists (research R6). A boolean would be a second source of truth able to disagree with reality.

**FR-011** — publishing is refused with no questions. **FR-012** — a pass mark unreachable with the points available is refused on save.

Phase 4 adds `retake_interval_days` and `completion_deadline_days` here.

```
unpublished ⇄ published        (instructor, while no attempts exist)
     │
     └── first attempt made ──▶ frozen: publish/unpublish still allowed,
                                everything else refused
```

---

## `test_question`

Which questions make up a test, and in what order.

| Column | Type | Null | Notes |
|---|---|---|---|
| `test_id` | INT, FK → `test.id` | no | Composite PK with `question_id` |
| `question_id` | INT, FK → `question.id` | no | |
| `position` | INT | no | The order the instructor chose |

A join table because a bank question may appear in more than one test, and a test is an ordered selection rather than everything in the bank (FR-007).

---

## `attempt`

One person's sitting of one test. The centre of this phase.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `test_id` | INT, FK → `test.id`, indexed | no | |
| `user_id` | INT, FK → `user.id`, indexed | no | |
| `attempt_number` | INT | no | Derived on creation, never supplied by the request |
| `started_at` | DATETIME | no | |
| `ends_at` | DATETIME | no | **Fixed at creation** — `min(started_at + limit, closes_at)`. Never recomputed (FR-016, FR-023) |
| `submitted_at` | DATETIME | yes | Null while in progress |
| `is_submitted` | BOOL | no | Default false |
| `question_order` | JSON | no | **Fixed at creation** — ordered question ids (FR-017) |
| `points_earned` | INT | yes | Set on scoring |
| `points_possible` | INT | yes | Set on scoring |
| `score_percent` | INT | yes | Set on scoring; replaced by an instructor override (FR-035) |
| `passed` | BOOL | yes | Follows `score_percent` against the test's pass mark |
| `score_overridden` | BOOL | no | Default false; true once an instructor sets a score by hand |

**Index on `(test_id, user_id)`** — every attempt-count and most-recent-attempt query uses it.

### The two fixed columns

`ends_at` and `question_order` are written once and never changed. They are what make an interrupted attempt resumable and an instructor's later edit harmless to a running attempt. Nothing in the codebase should recompute either.

### Lifecycle

```
in progress ──── submitted by the trainee ────▶ submitted, scored
     │
     └──── ends_at passes, seen on next read ──▶ submitted, scored
                                                 (research R8)
```

There is no scheduled sweep. An expired attempt becomes submitted the next time anyone looks at it.

**FR-024** — submitting an already-submitted attempt does nothing and returns the same result.

**FR-029** — a person's *most recent submitted* attempt is the one that represents them. Everything downstream reads that, not the best one.

---

## `attempt_answer`

What one person chose for one question in one attempt.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `attempt_id` | INT, FK → `attempt.id`, indexed | no | |
| `question_id` | INT, FK → `question.id` | no | |
| `selected_option_ids` | JSON | no | A list, because a question may have several correct answers |
| `is_correct` | BOOL | yes | Set at scoring |
| `points_awarded` | INT | yes | Set at scoring |
| `answered_at` | DATETIME | no | Updated on each change |

**Unique constraint on `(attempt_id, question_id)`** — this is what makes each save an upsert and guarantees one row per question however many times the trainee changes their mind.

A question with no row is unanswered, and scores zero.

---

## Relationships

```
module ──< question ──< answer_option
   │           │
   │           └──< test_question >── test ──< attempt ──< attempt_answer
   └──────────────────────────────────┘              │
                                              user ──┘
```

Every foreign key is enforced by InnoDB.

---

## What is deliberately absent

| Not modelled | Why |
|---|---|
| A question `type` column | Multiple choice is the only kind |
| Partial credit | Exact match only (FR-027) |
| A `is_frozen` flag on `test` | Derived from whether attempts exist (research R6) |
| A per-attempt time-remaining column | Derived from `ends_at` and the server clock |
| Question categories, tags, or difficulty | Out of scope |
| A random draw from the bank | A test is a fixed set of questions |
| Any history of edits or overrides | The platform carries no audit trail |
