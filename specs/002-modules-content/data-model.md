# Data Model: Modules, Content & Registration

**Phase 1 output** for [plan.md](./plan.md). Four new tables. Phase 0's `user` and `session` are unchanged.

Conventions carry over from Phase 0: naive UTC `DATETIME`, `utf8mb4`, InnoDB, schema from `create_all()` with no migration tool.

---

## `module`

A subject the organisation wants covered.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `title` | VARCHAR(255) | no | Identifies the module. There is no code or reference number (FR-001) |
| `description` | TEXT | yes | A short summary, plain text |
| `is_published` | BOOL | no | Default false |
| `created_at` | DATETIME | no | |
| `deleted_at` | DATETIME | **yes** | Set to soft-delete; `NULL` means live (FR-010) |

**Two states, not three.** There is no `archived`. A module is published or it is not, and retiring one means unpublishing it. Deletion is separate and reversible.

```
unpublished ⇄ published        (administrator, FR-003)
     │
     └── soft-deleted ⇄ restored   (administrator, FR-010)
```

A soft-deleted module disappears from every list for everyone. Its pages, images, and registrations are untouched, so restoring it returns everything (SC-013). Permanent removal is a database operation, and only then are its image files deleted (FR-022).

---

## `page`

One section of a module's material.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `module_id` | INT, FK → `module.id`, indexed | no | Cascade on permanent delete |
| `title` | VARCHAR(255) | no | |
| `body` | **MEDIUMTEXT** | no | Sanitised HTML. `TEXT` would truncate at 64KB silently — research R6 |
| `position` | INT | no | Unique within `module_id`. New pages go last — research R5 |
| `is_published` | BOOL | no | Default false, so a page starts as a draft (FR-012) |
| `created_at` | DATETIME | no | |
| `updated_at` | DATETIME | no | |

### Rules

- **FR-014** — trainees see only rows where `is_published` is true, ordered by `position`.
- **FR-016** — `body` holds HTML **already sanitised**. Nothing unsafe can be in this column, because the sanitiser runs before the write. Templates render it directly.
- **FR-018** — only instructors assigned to the module, and administrators, may write here.
- Concurrent edits are last-write-wins. `updated_at` records who won, not that a conflict happened.

```
draft ⇄ published        (instructor, independently per page)
```

An instructor can publish pages one, two, and three while four is still a draft. Trainees see three pages and no sign that a fourth exists.

---

## `content_image`

A picture an instructor uploaded. The file itself lives on a volume; this is what the platform knows about it.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `module_id` | INT, FK → `module.id`, indexed | no | |
| `stored_name` | VARCHAR(64) | no | Generated — `uuid4().hex` plus extension. **Never** derived from what was uploaded (research R3) |
| `original_name` | VARCHAR(255) | no | For display only. Never used to build a path |
| `content_type` | VARCHAR(100) | no | As declared; recorded, not trusted |
| `size_bytes` | INT | no | |
| `uploaded_by` | INT, FK → `user.id` | no | |
| `uploaded_at` | DATETIME | no | |

### Rules

- **FR-019/020** — written only by an instructor assigned to the module. There is no route by which a trainee can create one.
- **FR-021** — extension must be in the allowlist and `size_bytes` under the configured cap.
- **FR-022** — permanently removing a module deletes its rows *and* its files. Soft-deleting does not.
- An image whose page was deleted stays. Nothing collects orphans (research, accepted simplifications).

---

## `registration`

The fact that a person is on a module.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | INT, PK, auto | no | |
| `user_id` | INT, FK → `user.id`, indexed | no | |
| `module_id` | INT, FK → `module.id`, indexed | no | |
| `role_in_module` | VARCHAR(20) | no | `instructor` · `trainee` |
| `registered_at` | DATETIME | no | |

**Unique constraint on `(user_id, module_id)`** — this is what makes FR-027 a database guarantee rather than a check somebody might forget.

### Rules

- **No status column.** A registration exists or the person is not on the module (FR-030). There is nothing invited and awaiting acceptance, because people are registered directly; nothing concluded, because modules do not end.
- **FR-026** — `role_in_module` is independent of `user.role`. The same person may instruct one module and be a trainee on another. Authorisation asks this column, not the platform-wide role.
- **FR-028** — no route creates or deletes a row here on the acting person's own behalf. An administrator or the module's instructor does both.
- Removing a registration removes the row. The person's attempts, once Phase 2 creates them, are not deleted — they simply stop being reachable by that person.

---

## Relationships

```
user ──< registration >── module ──< page
 │                          │
 └────< content_image ──────┘
        (uploaded_by)         (module_id)
```

Every foreign key is enforced by InnoDB, not only by the ORM.

---

## What is deliberately absent

| Not modelled | Why |
|---|---|
| A module code or reference number | The title identifies it (FR-001) |
| An `archived` state | Modules do not end; unpublishing retires one |
| A registration status | It exists or it does not (FR-030) |
| A `self_registration_open` flag | Nobody puts themselves on a module (FR-028) |
| Page view or completion tracking | No gating anywhere; reading is never a precondition (FR-035) |
| A pathway, track, or module grouping | Out of scope |
| Any audit or revision history for pages | The platform carries no audit trail |
