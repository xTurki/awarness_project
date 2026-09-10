# Quickstart: Modules, Content & Registration

**Phase 1 output** for [plan.md](./plan.md). How to prove this phase works.

Every scenario maps to a user story in [spec.md](./spec.md). Walking all six is what "Phase 1 is done" means.

---

## Prerequisites

Phase 0 built and working, accounts, sign-in, the application shell. If `docker compose up` does not already give you a sign-in page, finish that first.

New in this phase:

```bash
# .env gains one setting
UPLOAD_MAX_MB=5
```

Both the application limit and Nginx's `client_max_body_size` derive from it (research R4), so there is one number to change and no way for them to disagree.

```bash
docker compose down && docker compose up -d --build   # rebuild: new volume, new nginx config
docker compose exec backend python seed.py
```

> Adding tables means recreating the database. There are no migrations: `docker compose down -v && docker compose up -d`, then seed again.

---

## Scenario 1, Set up a module *(US1, P1)*

As the seeded **administrator**:

1. Create a module, a title and a description. It exists, unpublished.
2. Assign the seeded **instructor** to it.
3. Sign in as that instructor: the module appears in their list, though it is unpublished.
4. Sign in as a **trainee**: it does not appear. Request `/modules/{id}` directly, expect **404**, not 403.

> 404 rather than 403 is deliberate. A trainee should not be able to learn that a module exists by being refused it.

5. As the administrator, try to create a module while signed in as the instructor. Expect refusal (FR-005).

---

## Scenario 2, Write the material *(US2, P1)*

As the **instructor** on that module:

1. Create three pages. Use the editor's headings, bold, a list, and a link, without typing any markup.
2. Reorder them. Confirm the new order sticks.
3. Publish the first two. Leave the third a draft.
4. Upload an image into page two and confirm it displays.
5. Sign in as a registered trainee (after Scenario 3), expect **exactly two pages**, in your order, with the image visible and **no sign the third exists**.

**Then the one that matters:**

6. As the instructor, put this into a page body and save it:

   ```html
   <p>Hello</p><script>alert(1)</script><a href="javascript:alert(2)">click</a>
   ```

7. Check what was **stored**, not what is displayed:

   ```bash
   docker compose exec db mysql -uroot -p -e \
     "SELECT body FROM lms.page WHERE id = <page id>\G"
   ```

   Expect `<p>Hello</p>` and a stripped link. The `<script>` must be **absent from the column**, not escaped, not hidden by the template. If it is in the database, the sanitiser is in the wrong place (research R2).

8. As an instructor on a *different* module, try to edit this one's pages. Expect **403**.

---

## Scenario 3, Put people on it *(US3, P2)*

As the module's **instructor**:

1. Open the roster. Select five trainees and register them in one action.
2. Confirm all five now see the module.
3. Register one of them again. Expect no duplicate and no error shown (research R8).
4. Remove one. That person no longer sees the module; requesting it directly gives 404. The other four are unaffected.
5. As an instructor on a different module, request this roster. Expect **403**.
6. Signed in as a trainee, look for any way to add or remove yourself. **There is none** (FR-028).

---

## Scenario 4, Read your training *(US4, P2)*

As a registered **trainee**:

1. The dashboard lists the modules you are on, and no others.
2. Open one. Move between its published pages in the instructor's order.
3. The image in page two loads.
4. Request a draft page's address directly. Expect **404**.

---

## Scenario 5, Uploads behave *(FR-019 to FR-022)*

As the **instructor**:

| Try | Expect |
|---|---|
| A 12MB image, with `UPLOAD_MAX_MB=5` | Refused, with a message naming the limit, *not* a blank Nginx error page |
| `notes.pdf` | Refused as not an accepted type |
| `payload.exe` renamed to `payload.png` | **Accepted.** Extension-only checking is the recorded decision; it lands in a directory Nginx serves as static content and does not run |

Then confirm the stored filename is generated, not the uploaded one:

```bash
docker compose exec backend ls /data/uploads
# expect names like 9f3a1c8e4b7d.png, never the original filename
```

---

## Scenario 6, Every width *(FR-033, FR-034, done-gate 3)*

Walk the module list, module home, a content page, the editor, and the roster at each width:

| Width | Expect |
|---|---|
| 360px | Module navigation as a drawer; no sideways page scrolling anywhere |
| 768px | Usable |
| 1280px | Navigation persistent alongside the content, not behind a button |

The editor is the one to check carefully on a phone, its toolbar is the thing most likely to force horizontal scroll.

---

## Running the tests

```bash
docker compose exec backend pytest
```

Against a MySQL container, never SQLite. `tests/services/test_sanitise.py` deserves particular attention: it is the only test in this phase whose failure would be silent in production.

---

## Done when

- [ ] All six scenarios pass
- [ ] A `<script>` in a submitted page body is **absent from the stored column**
- [ ] A trainee can reach no part of a module they are not registered on
- [ ] An instructor can reach no part of a module they are not assigned to
- [ ] No route lets anyone register or deregister themselves
- [ ] No module under `app/routers/` imports `Session` or `select`
- [ ] No `table=True` model reaches a template
- [ ] Every module-scoped service function resolves through `module_service.get_for`
- [ ] Layout verified at all three widths
