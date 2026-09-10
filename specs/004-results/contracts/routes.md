# Contract: HTTP Routes

**Phase 1 output** for [plan.md](./plan.md). Three routes, all `GET`. This phase writes nothing.

**Guards** carry over: `auth` (signed in, password set), `module:write` (administrator, or an instructor assigned to the module).

---

## A person's own results

| Method | Path | Guard | Result |
|---|---|---|---|
| GET | `/` | auth | **Moved here from `dashboard.py`; the application registers `GET /` exactly once.** **A trainee's dashboard, which is their results page.** Every module they are registered on as a trainee, with state and score. Outstanding first. A person with none sees a statement saying so. Instructors and administrators see their own dashboards here instead. |
| GET | `/results/modules/{id}` | auth | That person's attempt history for that module — every attempt including at replaced tests, each linking to its Phase 2 review. An attempt in progress links back into the attempt. |

The dashboard shows the caller's own results and nobody else's. There is no path parameter for a person, so there is no route by which one trainee reaches another's (FR-013).

`/results/modules/{id}` refuses with 404 if the caller holds no registration on that module.

---

## An instructor's cohort

| Method | Path | Guard | Result |
|---|---|---|---|
| GET | `/modules/{id}/results` | `module:write` | Everyone registered on the module as a trainee, with state and score. Those who have not passed first. Each links to that person's attempts. |

| GET | `/modules/{id}/results/{uid}` | `module:write` | **One person's attempt history for that module** — every attempt with its date, score, and outcome, each linking to its Phase 2 review. This is what a cohort row links to (FR-018). |

Phase 2's `/tests/{tid}/attempts` remains: it lists every attempt on one test by everyone. The route above is one person across that module's tests, which is what FR-018 asks for and what the cohort row needs.

There is **no** route listing results across modules (FR-021).

---

## Where a state is also shown

These are Phase 1 and 2 pages that gain a state badge rather than new routes:

| Page | Addition |
|---|---|
| `/modules/{id}` — module home | The caller's state for this module |

The badge always carries its word, never colour alone (FR-023).

---

## One thing Phase 2 gains

`POST /modules/{id}/tests/{tid}/publish` — already defined in Phase 2 — now shows a confirmation first when the module already has a published test, naming how many people will revert to "not started" (FR-027). The count comes from `results_service`.

---

## What is not exposed

| Absent | Why |
|---|---|
| Any route reaching another person's results by id | FR-013 — there is no such parameter |
| Any route spanning more than one module | FR-021 |
| Any `POST` in this phase | FR-025 and FR-026 — nothing is stored and no score is entered here |
| An export | Out of scope |
| A certificate or printable record | Out of scope |

---

## Response conventions

| Situation | Response |
|---|---|
| Requesting a module you hold no registration on | 404 |
| Instructor requesting another module's cohort | 403 |
| A module in progress, opened from results | Redirect into the attempt, not the review |
| No registrations at all | 200 with a clear statement, not an empty table |
