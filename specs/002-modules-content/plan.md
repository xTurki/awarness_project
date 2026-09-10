# Implementation Plan: Modules, Content & Registration

**Branch**: `002-modules-content` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-modules-content/spec.md`

## Summary

Introduce the module, the thing the platform exists to deliver, and everything that hangs off it: an administrator creating modules and assigning instructors, an instructor writing ordered content pages with a rich-text editor and uploading images into them, people being registered onto modules, and trainees finding and reading what they have been assigned.

Two pieces of this phase carry all its risk, and the plan is shaped around them. **Instructor-authored HTML is read back by every trainee who opens that page**, so it must be sanitised on the server before storage, not on render, not in the editor. And **this is the first phase to accept a file**, which brings a storage volume, an upload limit that has to agree in two places, and a serving path that must not execute anything.

Everything else is CRUD with an authorisation rule in front of it.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Everything from Phase 0, plus `nh3` (HTML sanitising) and a vendored rich-text editor (Quill). No other additions.

**Storage**: MySQL 8 for modules, pages, registrations, and image metadata. A second named Docker volume for the image files themselves, the first file storage in the project.

**Testing**: pytest against a disposable MySQL 8 container, as Phase 0 established

**Target Platform**: Unchanged, Linux server under Docker Compose, browsers from 360px up

**Project Type**: Server-rendered web application, three containers

**Performance Goals**: None beyond the spec's user-facing criteria. One organisation, tens of modules, tens of people per module.

**Constraints**: Everything from Phase 0, plus: uploads are instructor-only and image-only · the Nginx body-size limit and the application limit must agree · a page body must hold a full training topic without silent truncation · sanitising happens before storage

**Scale/Scope**: Four user stories, 35 functional requirements, 14 success criteria. Three new tables and one new volume.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against `.specify/memory/constitution.md` v4.0.0.

### Principles

| # | Principle | Status | How this phase satisfies it |
|---|---|---|---|
| I | Routers Are Thin | ✅ | `Session` and `select` stay under `app/services/`. The upload route is the one to watch, it is tempting to put file handling in the router; it goes in `content_service`. |
| II | Services Are HTTP-Agnostic | ✅ | `content_service` receives file **bytes and a filename**, not `UploadFile`. Reading the upload off the request is the router's job; everything after is plain arguments. |
| III | Authorisation in the Service Layer | ✅ | This is the first phase with module-scoped data, so the principle finally has teeth. Every service function takes the acting account and resolves the module through one chokepoint (research R1). |
| IV | The Models Are the Schema | ✅ | Three new tables from `create_all()`. Still no migration tool; still `down -v` to change anything. |
| V | Every Phase Ships Running Software | ✅ | Ends with an instructor able to write and publish a real module that real trainees can read. |
| VI | Tests Accompany the Feature | ✅ | Against MySQL. The sanitiser gets its own tests, it is the one thing here that fails silently and dangerously. |
| VII | Non-Goals Are Defended | ✅ | No self-registration of any kind, no prerequisites or gating, no pathways, no trainee uploads, no roster import, no module copying. All recorded in the spec. |
| VIII | Simplicity Is a Requirement | ✅ | Two dependencies added, both load-bearing. Research records what was rejected. |

### Constraints

| Constraint | Status | Note |
|---|---|---|
| Instructor HTML sanitised server-side before storage | ✅ | `nh3`, allowlist, in `content_service`, never in a template filter |
| Uploads image-only by extension, with a size cap | ✅ | Extension allowlist and size check; no content sniffing (removed with the security reduction) |
| Nginx `client_max_body_size` agrees with the application limit | ✅ | Both read from one number, research R4 |
| No `table=True` model rendered or returned | ✅ | Done-gate 5, and now four models rather than two |
| Naive UTC everywhere | ✅ | |
| Authorisation in the service layer | ✅ | Done-gate 6 |
| Three tiers, only Nginx published | ✅ | Second volume shared between `backend` and `nginx` |
| No queue, no worker, no second machine | ✅ | Nothing scheduled in this phase |

### Done gates for this phase

1. `docker compose up` on a clean checkout brings all three tiers to a working state
2. The test suite passes against a MySQL container
3. Layout verified below 576px, 576–992px, and above 992px
4. No module under `app/routers/` imports `Session` or `select`
5. No endpoint or template receives a `table=True` model instance
6. Every module-scoped service function performs its own authorisation check

**Result: PASS.** No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-modules-content/
├── plan.md              # This file
├── research.md          # Phase 0 output, implementation decisions
├── data-model.md        # Phase 1 output, three new tables
├── quickstart.md        # Phase 1 output, bring it up and prove it works
├── contracts/
│   └── routes.md        # Phase 1 output, the HTTP surface added
├── checklists/
│   └── requirements.md  # From /speckit-specify
└── tasks.md             # Phase 2 output (/speckit-tasks, not created here)
```

### Source Code (repository root)

Additions to what Phase 0 built. Unchanged files are omitted.

```text
docker-compose.yml               # + uploads volume, client_max_body_size
nginx/nginx.conf                 # + /uploads/ location, body size limit
backend/
├── requirements.txt             # + nh3
└── app/
    ├── config.py                # + UPLOAD_MAX_BYTES, UPLOAD_DIR, ALLOWED_IMAGE_EXTENSIONS
    ├── models/
    │   ├── module.py            # new
    │   ├── page.py              # new
    │   ├── content_image.py     # new
    │   └── registration.py      # new
    ├── services/
    │   ├── module_service.py    # new, modules, instructor assignment, the authorisation chokepoint
    │   ├── content_service.py   # new, pages, ordering, sanitising, uploads
    │   └── registration_service.py  # new
    ├── routers/
    │   ├── modules.py           # new
    │   ├── content.py           # new
    │   └── registrations.py     # new
    ├── sanitise.py              # new, the allowlist and one function, kept apart deliberately
    ├── templates/
    │   ├── modules/{list,form,home,page,roster}.html
    │   └── components/module_nav.html
    └── static/vendor/quill/     # vendored editor
tests/
├── services/{test_module,test_content,test_sanitise,test_registration}.py
└── routers/
```

**Structure Decision**: Phase 0's layout continues unchanged. One file is added outside the pattern: `app/sanitise.py`. It holds the allowlist and the single function that applies it, kept out of `content_service` so that the thing every trainee's browser depends on is one small file with its own test module, rather than a helper buried among page CRUD.

## Complexity Tracking

No constitution violations. Nothing to justify.
