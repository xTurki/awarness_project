# Quickstart: Scheduling & Notifications

**Phase 1 output** for [plan.md](./plan.md). How to prove this phase works.

The daily job takes a date as an argument, so none of this requires waiting a day or changing a clock.

---

## Prerequisites

Phases 0–3 working. You need a module with a published test carrying a pass mark, an instructor, and several registered trainees.

```bash
# .env gains two settings
DUE_SOON_LEAD_DAYS=14
SCHEDULER_HOUR_UTC=6

docker compose down -v && docker compose up -d --build   # new table, new columns
docker compose exec backend python seed.py
```

**Running the job by hand**, used throughout:

```bash
docker compose exec backend python -c \
 "from datetime import date; from app.database import get_session; \
  from app.services.daily_job import run_daily; \
  print(run_daily(next(get_session()), date(2027,3,15)))"
```

---

## Scenario 1, Set a schedule *(US1, P1)*

As the **instructor**:

1. Set a 90-day retake interval on the test. It saves, and trainees see it on the test page.
2. Try setting one on a test with **no pass mark**, refused, saying a pass mark is needed first (FR-003).
3. Try an interval of **7 days** while the warning period is 14, refused (FR-004).
4. On a different, one-off test, set a **30-day completion period**. Each registered person becomes due 30 days after their own registration.
5. Try setting an interval on a module you do not run, refused.
6. Confirm a recurring test ignores the attempt limit: exhaust the allowed attempts without passing, then start another. It is allowed (FR-005).

---

## Scenario 2, Who is due *(FR-007 to FR-012)*

Arrange several trainees on the 90-day module and run the job for a date you choose:

| Trainee | Last attempt | Run for | Expect |
|---|---|---|---|
| A | Passed 100 days ago | today | **Overdue** |
| B | Passed 80 days ago | today | **Due**, inside the 14-day warning |
| C | Passed 5 days ago | today | Neither |
| D | Never attempted, registered 100 days ago | today | **Overdue**, registration + 90 days has passed (FR-008) |
| F | Registered yesterday, never attempted | today | Neither, they have their own 90 days (FR-008) |
| G | Registered yesterday, attempted once and **failed** | today | Neither, a failed attempt does not shorten a first cycle (FR-008) |
| E | Passed 5 days ago, then retook and **failed** today | today | **Due**, their due date is that failing attempt, so overdue from tomorrow (FR-009) |

Trainee E is the case worth checking carefully. If E shows as passed, the clock is running from the wrong attempt.

Then:

- Have A retake and pass. Run the job again, A is no longer due, and their next due date is 90 days out (FR-011).
- Remove B's registration. Run again, B is not due and gets nothing (FR-012).
- Change the interval to 365 days. Every trainee's due date moves **at once**, with no migration (FR-007).

---

## Scenario 3, Being told *(US2, P1)*

1. With A and D overdue, run the job.
2. Both receive an email. Both see an entry in `/notifications`.
3. Run the job **again for the same date**. Expect: **no second email and no second record** (FR-024). Check:

   ```bash
   docker compose exec db mysql -uroot -p -e \
     "SELECT user_id, kind, module_id, due_date, emailed_at FROM lms.notification\G"
   ```

4. Put one trainee overdue on **three** modules. Run the job. Expect **one email** listing all three (FR-019), and **three entries** in their notification list (FR-034).
5. Run the job seven days later. The still-overdue trainee receives **nothing further**, no second email, no second entry, and the module still shows as overdue (FR-014).
6. Skip several days entirely, then run. Everyone who became due meanwhile is caught (FR-027).

---

## Scenario 4, The notification list *(US3, P2)*

As a trainee with unread notifications:

1. The shell shows something is waiting (FR-030).
2. Open `/notifications`, entries newest first, each saying what it concerns and when.
3. Follow one, you arrive at that module (FR-032).
4. Sign in again, nothing shows as waiting unless something new arrived (FR-031).
5. Request another person's notifications. There is no route that takes a person, so there is nothing to try (FR-033).
6. A trainee with none sees a clear statement, not an empty list.

---

## Scenario 5, Immediate notifications *(US4, P3)*

1. As the instructor, register a new trainee. They are notified **at once**, not on the next run (FR-015).
2. Register five in one action, each gets their own, about their own registration.
3. Have a trainee submit a test. They are notified of the result immediately (FR-016).

---

## Scenario 6, When a mail send fails *(FR-025)*

1. Break outbound mail, a wrong `SMTP_APP_PASSWORD`, then restart the backend.
2. Run the job with someone overdue.
3. The **in-app notification exists**; no email arrived.
4. Check the record: `emailed_at` is **null**.
5. Fix the credential, restart, run the job again for the same date. The email now goes, and `emailed_at` is stamped. **No duplicate record was created.**

---

## Scenario 7, A replacement test *(FR-020)*

1. With several trainees passed on a module, publish a **replacement** test (Phase 3 warns you first, with the count).
2. Run the job.
3. **Everyone** who had passed is now notified, no grace period, no suppression.

---

## Scenario 8, The scheduler actually runs *(FR-026, FR-028)*

Everything above calls the job by hand. Confirm it also runs on its own:

1. Set `SCHEDULER_HOUR_UTC` to a few minutes ahead. Restart the backend.
2. Watch the logs at that time, the job runs with nobody signed in.
3. Confirm no extra container, service, or process was added: `docker compose ps` shows the same three.

---

## Scenario 9, Presentation *(FR-040)*

| Width | Expect |
|---|---|
| 360px | Notification list readable, no sideways scrolling; the shell indicator visible without scrolling |
| 768px / 1280px | Usable |

Also confirm **due** and **overdue** appear on Phase 3's results page and the instructor's cohort view (FR-010), and remain legible in greyscale.

---

## Running the tests

```bash
docker compose exec backend pytest
```

Two modules carry this phase:

- `test_due.py`, a table of due-date cases, including trainee E from Scenario 2
- `test_daily_job.py`, **runs the job twice and asserts nothing changed the second time**

---

## Done when

- [ ] All nine scenarios pass
- [ ] Someone who passed then failed on retake is **overdue**
- [ ] Running the job twice produces no second record and no second email
- [ ] An overdue person is told once, and not again on any later run
- [ ] A newly registered person is not overdue until their first full interval has passed
- [ ] Three overdue modules produce one email and three list entries
- [ ] A failed send leaves the record unstamped and is retried next run
- [ ] A missed run catches everyone up
- [ ] Changing an interval re-dates everyone with no migration
- [ ] The scheduler runs unattended, with no fourth container
- [ ] Due and overdue appear everywhere Phase 3's states appear
