# Contract: HTTP Routes

**Phase 1 output** for [plan.md](./plan.md). The routes this phase adds to the surface Phase 0 established.

**Conventions**, unchanged from Phase 0: every `POST` carries a CSRF token; `auth` means a valid session and a password already set. Two guards are new and specific to this phase:

- **`module:read`** — the caller may see this module. Administrator: always. Instructor: if assigned. Trainee: if published *and* registered. Anything else is 404, never 403 — a trainee should not learn that a module exists by being told they may not see it.
- **`module:write`** — the caller may change this module. Administrator, or an instructor assigned to it. Otherwise 403.

Both resolve through the single chokepoint in `module_service` (research R1).

---

## Modules

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| GET | `/modules` | auth | — | Every module the caller may see. The list differs by role, and that is the whole point (FR-006/007/008). |
| GET | `/modules/new` | admin | — | The creation form. |
| POST | `/modules` | admin | `title`, `description` | Creates it unpublished. Redirect to its home. |
| GET | `/modules/{id}` | `module:read` | — | Module home: description, published pages in order, module navigation. |
| GET | `/modules/{id}/edit` | admin | — | The edit form. |
| POST | `/modules/{id}` | admin | `title`, `description` | Updates it. |
| POST | `/modules/{id}/publish` | admin | `is_published` | Publishes or unpublishes (FR-003). |
| POST | `/modules/{id}/delete` | admin | — | Soft-delete. Reversible (FR-010). |
| POST | `/modules/{id}/restore` | admin | — | Undoes it. |

There is no route that permanently removes a module. That is a database operation, and only it deletes the image files.

---

## Instructors on a module

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| POST | `/modules/{id}/instructors` | admin | `user_id` | Registers that person with `role_in_module = instructor` (FR-004). |
| POST | `/modules/{id}/instructors/{uid}/remove` | admin | — | Removes that registration. The module keeps its pages. |

A module with no instructor is permitted. An administrator can assign a replacement at any time.

---

## Content pages

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| GET | `/modules/{id}/pages` | `module:write` | — | The instructor's page list, drafts included, in order. |
| GET | `/modules/{id}/pages/new` | `module:write` | — | The editor, empty. |
| POST | `/modules/{id}/pages` | `module:write` | `title`, `body` | **Sanitises `body`, then stores** (FR-016). Created as a draft, positioned last. |
| GET | `/modules/{id}/pages/{pid}/edit` | `module:write` | — | The editor, loaded. |
| POST | `/modules/{id}/pages/{pid}` | `module:write` | `title`, `body` | Sanitises, then stores. |
| POST | `/modules/{id}/pages/{pid}/publish` | `module:write` | `is_published` | Publishes or unpublishes that page alone. |
| POST | `/modules/{id}/pages/{pid}/delete` | `module:write` | — | Removes it. Its images stay on the volume. |
| POST | `/modules/{id}/pages/reorder` | `module:write` | `order[]` | Rewrites positions in one transaction (research R5). |
| GET | `/modules/{id}/pages/{pid}` | `module:read` | — | The reading view. Drafts are 404 for a trainee. |

**The sanitising rule is a property of these two routes and cannot be moved.** `POST /pages` and `POST /pages/{pid}` sanitise before writing. Nothing downstream re-checks, because nothing downstream needs to — the column cannot hold anything unsafe.

---

## Images

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| POST | `/modules/{id}/images` | `module:write` | multipart `file` | Validates extension and size, stores under a generated name, returns the URL for the editor to insert. Rejects with a message saying why (FR-021). |

There is **no** upload route reachable by a trainee, and none for any file type other than an image (FR-020).

Uploaded files are served by Nginx at `/uploads/{stored_name}` as static content. The application never serves them.

---

## Registration

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| GET | `/modules/{id}/roster` | `module:write` | — | Everyone registered, and in what capacity (FR-029). |
| POST | `/modules/{id}/roster` | `module:write` | `user_ids[]` | Registers all of them as trainees in one transaction. Already-registered are skipped silently (research R8). |
| POST | `/modules/{id}/roster/{uid}/remove` | `module:write` | — | Removes that registration. |

---

## What is not exposed

| Absent | Why |
|---|---|
| Any route by which a person registers themselves | FR-028 — nobody puts themselves on a module |
| Any route by which a person removes their own registration | FR-028 — removal is the instructor's decision |
| A page listing modules the caller is *not* on | There is no browsing; training is assigned |
| Any upload route for a trainee, or for a non-image | FR-020 |
| A permanent-delete route | Deliberate; permanent removal is a database operation |
| Any JSON endpoint | Server-rendered throughout |

---

## Response conventions

| Situation | Response |
|---|---|
| Module exists but the caller may not see it | **404**, not 403 — existence is not disclosed |
| Module visible but the caller may not change it | **403** |
| Upload too large or wrong extension | Back to the editor with a message naming the limit or the accepted types |
| Upload larger than Nginx allows | Should not occur — both limits derive from one setting (research R4) |
