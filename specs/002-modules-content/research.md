# Research: Modules, Content & Registration

**Phase 0 output** for [plan.md](./plan.md). Nine decisions.

Two of them, R2 and R3, are the only places in this phase where getting it wrong is dangerous rather than merely wrong. The rest are ordinary.

---

## R1, One chokepoint for module authorisation

**Decision**: A single service function, `module_service.get_for(module_id, actor)`, resolves every module access. It returns the module or raises `NotFound`, never "found but forbidden", which would leak the module's existence. Every other service function in this phase takes the module from it rather than querying by id itself.

**Rationale**: FR-009 requires the caller's relationship to be verified before *any* module-scoped action, and this phase adds roughly twenty such actions. One function means one place to get the rule right and one place to test it. Twenty separate checks means twenty chances to forget one, and the one forgotten is the vulnerability.

The rule it enforces:

| Actor | Sees |
|---|---|
| Administrator | Every module, any state |
| Instructor | Modules they are assigned to, including unpublished |
| Trainee | Published modules they hold a registration on |

**Alternatives considered**: a decorator on each route (rejected, that is authorisation in the router, which Principle I forbids); checking inside each service function (rejected, the duplication is the bug).

---

## R2, Sanitising instructor HTML

**Decision**: `nh3` (Rust `ammonia` bindings), applied in `app/sanitise.py`, on an **allowlist** of tags and attributes, called by `content_service` **before the body is written**. Stored HTML is already clean; templates render it with `|safe` and nothing else.

The allowlist: `p br h2 h3 h4 strong em u ul ol li a blockquote code pre img`. Attributes: `href` on `a` (schemes `http`, `https`, `mailto` only), `src alt title width` on `img`. Everything else is stripped, including `style`, every `on*` handler, `script`, `iframe`, `object`, `embed`, `form`.

**Rationale**: FR-016 requires removal before storage and says explicitly that sanitising in the editor or at render time is not a substitute. That is not pedantry, content written once is read by every trainee on the module, so a stored payload executes in dozens of browsers. Doing it at render time means every future template that forgets `|sanitise` is a hole; doing it before storage means the database cannot hold a payload at all.

An allowlist rather than a blocklist because blocklists are a losing game, the interesting attacks are always the encoding nobody thought of.

`nh3` over `bleach` because bleach is deprecated and unmaintained, and nh3 is its recommended successor with the same allowlist model.

**Alternatives considered**: `bleach` (rejected, deprecated); sanitising in a Jinja filter (rejected, FR-017 forbids it, and one forgotten filter is a hole); trusting the editor's output (rejected, the editor runs in the browser, which is the attacker's machine); escaping rather than sanitising (rejected, it would show the instructor's markup as literal text instead of formatting).

---

## R3, Accepting an upload safely enough

**Decision**: Extension allowlist (`.png .jpg .jpeg .gif .webp`), a size cap read from one setting, a **generated** stored filename (`uuid4().hex` plus the normalised extension), written into a named volume that Nginx serves as static files. The original filename is kept in the database for display only and never used to build a path.

**Rationale**: FR-021 requires images only, by extension, with a size cap. Generating the stored name is not extra hardening, it is what stops a filename like `../../app/main.py` from deciding where the file lands, which is a path-traversal bug rather than a security nicety.

**What is deliberately absent**: no content sniffing, no magic-byte check, no virus scanning, no image re-encoding. All were removed when the security surface was reduced, on the grounds that uploads are instructor-only and instructors are trusted staff. A renamed executable will be accepted; it will sit in a directory Nginx serves as static content and will not run.

**Alternatives considered**: sniffing the content type (rejected, removed by owner decision); re-encoding through Pillow (rejected, a dependency and CPU cost for a threat model that does not include instructors); storing files in MySQL (rejected, bloats backups, and Nginx already serves files better).

---

## R4, Making two upload limits agree

**Decision**: One number in `.env` (`UPLOAD_MAX_MB`). The application reads it directly. `nginx.conf` is generated from a template at container start with `client_max_body_size` set from the same variable, plus a small margin for multipart overhead.

**Rationale**: The project specification warns about exactly this: when Nginx's limit is lower than the application's, an oversized upload dies in Nginx with a generic 413 that the application never sees and therefore cannot explain. The instructor gets a blank error page instead of "that file is too large". Deriving both from one variable removes the possibility of them drifting apart.

**Alternatives considered**: hardcoding both and documenting that they must match (rejected, a comment is not a mechanism); setting Nginx generously and letting the application reject (rejected, the upload still travels the whole way before being refused, which on a phone connection is the slow failure).

---

## R5, Ordering pages

**Decision**: An integer `position` per page, unique within its module. Reordering rewrites the affected positions in one transaction. New pages go to the end.

**Rationale**: Tens of pages per module at most. A fractional-position or linked-list scheme solves a contention problem this project does not have, at the cost of code nobody will remember how to debug.

**Alternatives considered**: fractional positions (rejected, solves concurrent reordering, which will not happen here); a linked list (rejected, a reorder becomes several writes and a broken chain is unrecoverable by hand).

---

## R6, Page bodies large enough

**Decision**: `MEDIUMTEXT` for `page.body`.

**Rationale**: FR-017 says a page must hold a complete training topic without silent truncation, and silent is the operative word, MySQL will quietly cut a `TEXT` column at 64KB in a non-strict configuration, and formatted HTML reaches 64KB sooner than prose does. `MEDIUMTEXT` gives 16MB, which nobody will approach. The cost is nothing.

**Alternatives considered**: `TEXT` (rejected, 64KB is reachable with markup, and the failure is silent); `LONGTEXT` (rejected, no benefit over 16MB).

---

## R7, Vendoring the editor

**Decision**: Quill, downloaded once and committed under `app/static/vendor/quill/`. Never loaded from a CDN.

**Rationale**: The project specification requires vendoring. It matters more here than for Bootstrap: a CDN-loaded editor is third-party JavaScript running on the page where an instructor authors content that every trainee will read. For a product about cybersecurity awareness, taking that dependency would be difficult to defend.

Quill because it emits a small, predictable set of tags that maps cleanly onto the R2 allowlist.

**Alternatives considered**: TinyMCE (rejected, larger, and its useful features need a licence key); a plain textarea with Markdown (rejected, the owner asked for a rich-text editor); CKEditor (rejected, heavier than the need).

---

## R8, Bulk registration without an import

**Decision**: A multi-select of existing accounts on the roster screen, submitted as one form. Registrations are inserted in one transaction; anyone already registered is skipped silently.

**Rationale**: FR-025 requires several people registered in one action, and FR-027 requires no duplicate. "Skipped silently" rather than an error because the person doing it selected fifteen names and does not care that two were already there, telling them so is noise, not information. Importing a file remains out of scope.

**Alternatives considered**: one request per person (rejected, fifteen round trips and a partial failure to reason about); CSV upload (rejected, out of scope).

---

## R9, Where the module navigation lives

**Decision**: One Jinja include, `components/module_nav.html`, rendered by every module-scoped template. Bootstrap's offcanvas below 992px, a persistent column above it, one markup block, two behaviours from CSS.

**Rationale**: FR-033 requires both behaviours and FR-034 requires no sideways scrolling. Two separate markup blocks would mean two things to keep in step, and the phone one is the one that gets forgotten. Phases 2, 3, and 4 all render inside this shell, so it is worth getting right once here.

**Alternatives considered**: separate mobile and desktop markup (rejected, divergence is guaranteed); a JavaScript drawer of our own (rejected, Bootstrap is already vendored and does it).

---

## Accepted simplifications

Consistent with the reduced security surface, recorded so they read as decisions:

- **Uploads are checked by extension only.** A renamed file of another type will be accepted and stored.
- **Images are never scanned.** No virus checking of any kind.
- **Orphaned images are not collected.** An image whose page is deleted stays on the volume until its module is permanently removed.
- **Concurrent edits are last-write-wins.** Two instructors on one page at the same moment lose the earlier edit, with no warning.
