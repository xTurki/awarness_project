# Contract: HTTP Routes

**Phase 1 output** for [plan.md](./plan.md). The routes this phase adds.

**Guards** carry over from Phase 1: `module:read` (may see this module) and `module:write` (may change it), both resolved through `module_service.get_for`. Two are new:

- **`attempt:own`** — the attempt belongs to the caller
- **`attempt:view`** — the caller owns it, or is an instructor on its module

Every `POST` carries a CSRF token.

---

## Question bank

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| GET | `/modules/{id}/questions` | `module:write` | — | The bank, in order. |
| GET | `/modules/{id}/questions/new` | `module:write` | — | The question form. |
| POST | `/modules/{id}/questions` | `module:write` | `prompt`, `points`, `options[]`, `correct[]` | Validates two options and one correct (FR-003), then saves. |
| GET | `/modules/{id}/questions/{qid}/edit` | `module:write` | — | The form, loaded. |
| POST | `/modules/{id}/questions/{qid}` | `module:write` | same | Updates it. Refused if the question is in an attempted test (FR-013). |
| POST | `/modules/{id}/questions/{qid}/delete` | `module:write` | — | Removes it. Refused if it is in an attempted test. |

---

## Building a test

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| GET | `/modules/{id}/tests` | `module:read` | — | Instructors see all; trainees see published ones inside their window. |
| GET | `/modules/{id}/tests/new` | `module:write` | — | The test form. |
| POST | `/modules/{id}/tests` | `module:write` | `title`, `instructions`, `opens_at`, `closes_at`, `time_limit_minutes`, `allowed_attempts`, `shuffle_questions`, `passing_score`, `question_ids[]` | Creates it unpublished. Refuses an unreachable pass mark (FR-012). |
| GET | `/modules/{id}/tests/{tid}/edit` | `module:write` | — | The form. Shows why it is read-only if attempted (FR-014). |
| POST | `/modules/{id}/tests/{tid}` | `module:write` | same | Updates it. **Refused once any attempt exists** (FR-013). |
| POST | `/modules/{id}/tests/{tid}/publish` | `module:write` | `is_published` | Publishes or unpublishes. Refuses to publish with no questions (FR-011). Permitted even when frozen (FR-014). |
| GET | `/modules/{id}/tests/{tid}` | `module:read` | — | Test detail. A trainee sees the time limit, attempts allowed, and pass mark before starting (FR-009). |

---

## Taking a test

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| POST | `/tests/{tid}/attempts` | `module:read` | — | Starts an attempt, or resumes the one in progress. Fixes `ends_at` and `question_order`. Refuses outside the window or beyond the attempt limit (FR-015, FR-025). |
| GET | `/attempts/{aid}` | `attempt:own` | — | The attempt: questions in the fixed order, answers already given, `ends_at` for the countdown. |
| POST | `/attempts/{aid}/answer` | `attempt:own` | `question_id`, `option_ids[]` | Upserts one answer. Refused after `ends_at` (FR-021). Returns a small fragment — this is the HTMX route hit on every click. |
| POST | `/attempts/{aid}/submit` | `attempt:own` | — | Submits and scores. A second submit returns the same result (FR-024). |

`POST /attempts/{aid}/answer` is the only high-traffic route in the platform. It does one upsert and returns a fragment; anything more belongs elsewhere.

---

## Reviewing

| Method | Path | Guard | Sends | Result |
|---|---|---|---|---|
| GET | `/tests/{tid}/attempts/mine` | auth | — | The caller's own attempts at that test, each with its date, score, and outcome (FR-030). No path parameter names a person, so there is no route to anyone else's. **Superseded in Phase 3** by `/results/modules/{id}`, which covers every test on the module; it exists so this phase ships complete on its own. |
| GET | `/attempts/{aid}/review` | `attempt:view` | — | Each question with the answer given, whether it was right, and the correct answer (FR-031). Redirects into the attempt if it is still in progress. |
| GET | `/tests/{tid}/attempts` | `module:write` | — | Every attempt on the test, with who, when, score, outcome (FR-033). |
| POST | `/attempts/{aid}/score` | `module:write` | `score_percent` | Replaces the score; pass or fail follows it (FR-035). Refused on an unsubmitted attempt (FR-036). |

---

## What is not exposed

| Absent | Why |
|---|---|
| Any route reaching another person's attempt as a trainee | FR-032 |
| Any route reaching attempts on a module the instructor is not assigned to | FR-034 |
| A route to edit a test that has been attempted | FR-013 — refused, not hidden |
| A route to change a submitted attempt's answers | Only the score can be overridden |
| Any JSON endpoint | Server-rendered throughout |

---

## Response conventions

| Situation | Response |
|---|---|
| Attempt does not belong to the caller | 404 |
| Instructor requesting another module's attempts | 403 |
| Answer submitted after `ends_at` | The attempt is submitted and scored; the trainee lands on the result |
| Starting an attempt with none remaining | Back to the test with a message saying how many were allowed |
| Editing a frozen test | Back to the form, read-only, explaining why (FR-014) |
