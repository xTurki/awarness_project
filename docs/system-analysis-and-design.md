# System Analysis and Design

**SME Cybersecurity Awareness Training Platform**

| | |
|---|---|
| Course | COMP6900 Major Project, University of Newcastle |
| Group | 5 |
| Date | 20 October 2026 |
| Status | Under development and testing |

---

## Contents

1. [Introduction](#1-introduction)
2. [Requirements](#2-requirements)
3. [Architecture](#3-architecture)
4. [Data design](#4-data-design)
5. [Process design](#5-process-design)
6. [Interface design](#6-interface-design)
7. [Implementation](#7-implementation)
8. [Testing](#8-testing)

---

## 1. Introduction

### 1.1 Problem

Small and medium enterprises need to train staff in cybersecurity awareness and
keep a record of who has completed the training and who needs to retake it.

### 1.2 What the system does

- An **administrator** creates accounts and modules and assigns instructors.
- An **instructor** writes module pages, builds a question bank and creates a
  test by choosing how many questions it has; the questions are drawn at random
  from the bank.
- A **trainee** reads the pages, takes the test and sees their results.
- A **daily job** works out who is due for retraining and notifies them.

### 1.3 Out of scope

- Self-registration
- Assignments, forums, messaging and calendars
- SCORM / xAPI import
- Notification preferences
- Multiple organisations in one installation
- Certificates and badges

### 1.4 Development model

The project follows the **waterfall model**:

```mermaid
flowchart LR
    R["1. Requirements"] --> D["2. Design"] --> I["3. Implementation"] --> T["4. Testing"]
```

| Stage | Output | Section |
|---|---|---|
| 1. Requirements | Actors, use cases, functional and non-functional requirements | §2 |
| 2. Design | Architecture, data, processes, interface | §3 to §6 |
| 3. Implementation | The application | §7 |
| 4. Testing | Automated test suite | §8 |

Requirements are grouped and built in this order:

| Group | Covers |
|---|---|
| P0 Foundation | Accounts, two-step login, sessions, roles |
| P1 Modules and content | Modules, pages, images, registration |
| P2 Tests | Question bank, tests, attempts, scoring |
| P3 Results | Progress state, dashboards, cohort view |
| P4 Scheduling | Retake intervals, daily job, notifications |

---

## 2. Requirements

### 2.1 Actors

| Actor | Description |
|---|---|
| Administrator | Creates accounts and modules, publishes modules, assigns instructors |
| Instructor | Manages the modules they are assigned to |
| Trainee | Reads content and takes tests |
| Scheduler | Automatic daily process that sends due and overdue notices |

A user's role on a module (`registration.role_in_module`) is separate from their
platform role, so one person can be an instructor on one module and a trainee on
another.

### 2.2 Use case diagram

```mermaid
flowchart LR
    ADMIN([Administrator])
    INST([Instructor])
    TRAIN([Trainee])
    SCHED([Scheduler])

    subgraph Identity
        UC1(Sign in with password and code)
        UC2(Set own password)
    end

    subgraph Administration
        UC3(Manage accounts)
        UC4(Reset a password)
        UC5(Deactivate an account)
        UC6(Create and publish a module)
        UC7(Assign an instructor)
    end

    subgraph Authoring
        UC8(Write and order pages)
        UC9(Upload images)
        UC10(Build the question bank)
        UC11(Create and publish a test)
        UC12(Set a retake schedule)
    end

    subgraph Participation
        UC13(Register trainees)
        UC14(Read module pages)
        UC15(Ask the study assistant)
        UC16(Take a test)
        UC17(Review an attempt)
    end

    subgraph Results
        UC18(View own progress)
        UC19(View the cohort)
        UC20(Override a score)
        UC21(Read notifications)
    end

    subgraph Automatic
        UC22(Find who is due)
        UC23(Send email digest)
    end

    ADMIN --> UC1 & UC3 & UC4 & UC5 & UC6 & UC7 & UC13
    INST --> UC1 & UC8 & UC9 & UC10 & UC11 & UC12 & UC13 & UC19 & UC20
    TRAIN --> UC1 & UC2 & UC14 & UC15 & UC16 & UC17 & UC18 & UC21
    SCHED --> UC22 --> UC23
```

### 2.3 Key functional requirements

**Access**
- Accounts are created only by an administrator.
- Login needs a password and a 6-digit code sent by email.
- A new account must set its own password before using the platform.
- Deactivating an account takes effect on the next request.

**Content and tests**
- Only assigned instructors can edit a module's content.
- A test cannot be edited once it has attempts.
- The time limit is enforced on the server.
- An expired attempt is submitted automatically the next time it is loaded.

**Results and scheduling**
- The most recent attempt decides a trainee's result.
- Results and due dates are calculated, not stored.
- A new trainee gets a full interval from their registration date.
- An overdue notice is sent once.
- Running the daily job twice on the same day creates no duplicates.

### 2.4 Non-functional requirements

| Attribute | Requirement |
|---|---|
| Deployment | Runs with `docker compose up` (three containers) |
| Offline assets | Bootstrap, icons, fonts, htmx and Quill are served locally |
| Accessibility | WCAG AA text contrast |
| Responsive | Works on phone, tablet and desktop |
| Data integrity | Unique constraints enforced by the database |

---

## 3. Architecture

### 3.1 Layers

A server-rendered web application in three tiers (browser, application,
database). The application is split into layers:

| Layer | Responsibility |
|---|---|
| Routers | Read the request, call a service, render a template |
| Services | Business logic and access checks |
| Models | Database tables (SQLModel) |
| Schemas | Read models for templates and input validation |

Modules a user cannot access return **404**.

### 3.2 Deployment diagram

```mermaid
flowchart TB
    USER(["Browser"])

    subgraph Internet
        GEM[Google Gemini API]
        SMTP["Brevo SMTP"]
    end

    subgraph HOST["Docker host"]
        NG["nginx<br/>port 80"]
        BE["backend<br/>FastAPI + APScheduler"]
        DB[("MySQL 8")]
        VOL[("volumes<br/>db_data, uploads")]
    end

    USER --> NG
    NG -->|"static files, uploads"| VOL
    NG -->|"proxy"| BE
    BE --> DB
    BE --> VOL
    BE -->|"page text + question"| GEM
    BE -->|"login codes, notices"| SMTP
```

Only nginx exposes a port. The backend and database are reachable only inside
the Docker network. The daily scheduler runs inside the backend process.

### 3.3 Class diagram

```mermaid
classDiagram
    direction LR

    class User {
        +int id
        +str email
        +str full_name
        +str role
        +bool is_active
        +bool must_set_password
    }
    class Module {
        +int id
        +str title
        +str description
        +bool is_published
        +str art
        +datetime deleted_at
    }
    class Registration {
        +int user_id
        +int module_id
        +str role_in_module
        +datetime registered_at
    }
    class Page {
        +int module_id
        +str title
        +str body
        +int position
        +bool is_published
    }
    class Test {
        +int module_id
        +str title
        +int time_limit_minutes
        +int allowed_attempts
        +int passing_score
        +int retake_interval_days
        +int completion_deadline_days
    }
    class Question {
        +int module_id
        +str prompt
        +int points
    }
    class Attempt {
        +int test_id
        +int user_id
        +datetime ends_at
        +list question_order
        +int score_percent
        +bool passed
    }
    class Notification {
        +int user_id
        +int module_id
        +str kind
        +date due_date
        +datetime read_at
        +datetime emailed_at
    }

    User "1" --> "0..*" Registration
    Module "1" --> "0..*" Registration
    Module "1" --> "0..*" Page
    Module "1" --> "0..*" Test
    Module "1" --> "0..*" Question
    Test "1" --> "0..*" Attempt
    User "1" --> "0..*" Attempt
    Test "0..*" -- "0..*" Question : test_question
    User "1" --> "0..*" Notification
```

### 3.4 Services

| Service | Responsibility |
|---|---|
| `auth_service` | Login, codes, sessions |
| `admin_service` | Accounts |
| `module_service` | Modules and module access checks |
| `content_service` | Pages, ordering, images |
| `registration_service` | Adding and removing users on modules |
| `question_service` | Question bank |
| `test_service` | Tests and random question selection |
| `attempt_service` | Taking, submitting and reviewing attempts |
| `scoring` | Score, percentage, pass/fail |
| `state` | A trainee's state on a module |
| `due` | Due date calculation |
| `results_service` | Dashboards and cohort views |
| `notification_service` | Creating and sending notifications |
| `email_service` | Sending email |
| `daily_job` | The daily scheduled run |
| `tutor_service` | Study assistant (Gemini) |

---

## 4. Data design

### 4.1 Entity relationship diagram

```mermaid
erDiagram
    USER ||--o{ SESSION : has
    USER ||--o{ REGISTRATION : has
    MODULE ||--o{ REGISTRATION : has
    MODULE ||--o{ PAGE : contains
    MODULE ||--o{ TEST : has
    MODULE ||--o{ QUESTION : has
    MODULE ||--o{ CONTENT_IMAGE : has
    QUESTION ||--o{ ANSWER_OPTION : has
    TEST ||--o{ TEST_QUESTION : includes
    QUESTION ||--o{ TEST_QUESTION : "used in"
    TEST ||--o{ ATTEMPT : has
    USER ||--o{ ATTEMPT : makes
    ATTEMPT ||--o{ ATTEMPT_ANSWER : contains
    QUESTION ||--o{ ATTEMPT_ANSWER : "answered in"
    USER ||--o{ NOTIFICATION : receives
    MODULE ||--o{ NOTIFICATION : about

    USER {
        int id PK
        string email UK
        string full_name
        string role
        string password_hash
        boolean is_active
        boolean must_set_password
        string login_code_hash
        datetime login_code_expires_at
        datetime created_at
    }
    MODULE {
        int id PK
        string title
        text description
        boolean is_published
        string art
        datetime created_at
        datetime deleted_at
    }
    REGISTRATION {
        int id PK
        int user_id FK
        int module_id FK
        string role_in_module
        datetime registered_at
    }
    PAGE {
        int id PK
        int module_id FK
        string title
        text body
        int position
        boolean is_published
        datetime created_at
        datetime updated_at
    }
    TEST {
        int id PK
        int module_id FK
        string title
        text instructions
        boolean is_published
        datetime opens_at
        datetime closes_at
        int time_limit_minutes
        int allowed_attempts
        boolean shuffle_questions
        int passing_score
        int retake_interval_days
        int completion_deadline_days
        datetime created_at
    }
    ATTEMPT {
        int id PK
        int test_id FK
        int user_id FK
        int attempt_number
        datetime started_at
        datetime ends_at
        datetime submitted_at
        boolean is_submitted
        json question_order
        int points_earned
        int points_possible
        int score_percent
        boolean passed
        boolean score_overridden
    }
    NOTIFICATION {
        int id PK
        int user_id FK
        int module_id FK
        string kind
        date due_date
        string title
        text body
        datetime created_at
        datetime read_at
        datetime emailed_at
    }
    SESSION {
        string id PK
        int user_id FK
        datetime created_at
        datetime expires_at
    }
    CONTENT_IMAGE {
        int id PK
        int module_id FK
        string stored_name
        string original_name
    }
    QUESTION {
        int id PK
        int module_id FK
        text prompt
        int points
        int position
        datetime created_at
    }
    ANSWER_OPTION {
        int id PK
        int question_id FK
        string text
        boolean is_correct
        int position
    }
    TEST_QUESTION {
        int test_id PK, FK
        int question_id PK, FK
        int position
    }
    ATTEMPT_ANSWER {
        int id PK
        int attempt_id FK
        int question_id FK
        json selected_option_ids
        boolean is_correct
        int points_awarded
    }
```

### 4.2 Tables

13 tables. Unique constraints:

| Table | Unique constraint |
|---|---|
| `user` | `email` |
| `registration` | `(user_id, module_id)` |
| `page` | `(module_id, position)` |
| `test_question` | `(test_id, question_id)` (primary key) |
| `attempt_answer` | `(attempt_id, question_id)` |
| `notification` | `(user_id, kind, module_id, due_date)` |

### 4.3 Calculated values

These are calculated when needed and not stored:

| Value | Calculated from |
|---|---|
| Trainee state on a module | Registration, current test, attempts |
| Due date | Retake interval and latest attempt |
| Test locked | Whether any attempt exists |
| Results | Attempts |

Tables are created at startup with `create_all()`.

### 4.4 Initial content

Four training modules are loaded at startup from
`backend/app/seed_content/training_content.json`. Each module has 6 pages, a
20-question bank and an end-of-module quiz (10 questions, 70% pass mark, 2
attempts). Modules that already exist are skipped. Demo accounts are created
separately with `seed.py`.

---

## 5. Process design

### 5.1 Trainee state

Each trainee has one state per module, calculated by `state.py`:

```mermaid
stateDiagram-v2
    [*] --> NoTest : registered
    NoTest --> NotStarted : test published
    NotStarted --> InProgress : attempt started
    InProgress --> Passed : score >= pass mark
    InProgress --> Failed : score < pass mark
    Passed --> InProgress : retake
    Failed --> InProgress : retake
    Passed --> Due : due within 14 days
    Failed --> Due : due within 14 days
    NotStarted --> Due : due within 14 days
    Due --> Overdue : due date passed
    Due --> InProgress : attempt started
    Overdue --> InProgress : attempt started
    Passed --> NotStarted : replacement test published
    Failed --> NotStarted : replacement test published
    Overdue --> NotStarted : replacement test published
```

- The **latest** attempt decides the state. Example with an 80% pass mark:
  40%, 90%, then 70% = Failed.
- Publishing a replacement test resets everyone to Not started. The instructor
  sees how many people will be affected before publishing.

### 5.2 Two-step login

```mermaid
sequenceDiagram
    actor P as User
    participant R as auth router
    participant S as auth_service
    participant D as Database
    participant M as SMTP

    P->>R: POST /login (email, password)
    R->>S: start_login
    S->>D: find user, check password
    alt invalid or inactive
        S-->>R: error
        R-->>P: login form with message
    else valid
        S->>D: save code hash + expiry
        S->>M: email the code
        R-->>P: redirect to /login/verify
    end

    P->>R: POST /login/verify (code)
    R->>S: verify_code
    S->>D: check hash and expiry
    alt expired or wrong
        R-->>P: error message
    else correct
        S->>D: clear code, create session
        R-->>P: redirect to /, set session cookie
    end
```

Codes expire after 10 minutes and a new login replaces any previous code.
Sessions last 12 hours.

### 5.3 Daily job

```mermaid
sequenceDiagram
    participant SCH as APScheduler
    participant J as daily_job
    participant DU as due.py
    participant N as notification_service
    participant D as Database
    participant M as SMTP

    SCH->>J: run_daily(today) at 06:00 UTC
    J->>D: trainee registrations and current tests
    loop each trainee on a scheduled test
        J->>DU: due_date_for(test, registration, attempts)
        alt overdue
            J->>N: create overdue notice
        else due within 14 days
            J->>N: create due-soon notice
        end
        N->>D: insert (skipped if it already exists)
    end
    J->>D: notices not yet emailed
    loop each user
        J->>M: one email listing all modules
        J->>D: mark as emailed
    end
```

Failed emails are retried on the next run.

### 5.4 Taking a test

```mermaid
flowchart TD
    A(["Open test page"]) --> B{"Can start?"}
    B -->|no| B1["Show reason"]
    B -->|yes| C["Start / resume attempt"]
    C --> D["Set ends_at and question order"]
    D --> E["All questions on one page"]
    E --> F["Answer changed: saved immediately (htmx)"]
    F --> G{"Time up?"}
    G -->|yes| H["Auto-submit"]
    G -->|no| E
    E --> I["Submit"]
    I --> J["Score, pass/fail"]
    H --> J
    J --> K["Notify result"]
    K --> L(["Review answers"])
```

- A test's questions are picked at random from the bank when the test is saved.
  Saving again with the same count keeps the same questions.
- `shuffle_questions` changes the question order for each attempt.
- `allowed_attempts` of 0 means unlimited; on recurring tests the limit resets
  after a pass.

### 5.5 Study assistant

```mermaid
flowchart LR
    Q["Question + previous messages"] --> RT["tutor router"]
    RT --> CS["content_service.get_page"]
    CS --> TS["tutor_service"]
    TS -->|"page text (max 6000 chars) + question"| G["Google Gemini"]
    G --> TS --> RT -->|"HTML fragment"| Q
```

- The page text and the question are sent to Google.
- Nothing is stored; the conversation is kept in the page (last 6 exchanges).
- Only pages the user can access can be used.
- The feature is hidden when no API key is set.

---

## 6. Interface design

- Server-rendered Jinja2 templates with Bootstrap 5.3.
- htmx is used for saving test answers and for the study assistant.
- Quill is used as the page editor.
- One stylesheet with design tokens (colours, type scale, spacing); see
  `docs/design-system.md`.
- Light and dark theme, following the OS setting.
- Dashboards show summary figures (modules, published, drafts for staff; to do,
  completed, overdue for trainees).
- Module cards show a coloured cover or an uploaded image, and the trainee's
  state.
- Times are stored in UTC and shown in the user's local time zone.

**Accessibility**

| Item | Implementation |
|---|---|
| Text contrast | At least 4.5:1 |
| Focus | Visible focus outline |
| Touch targets | 44px minimum |
| State badges | Always show a text label |
| Reduced motion | Transitions disabled when requested |
| Text size | All sizes in rem |

---

## 7. Implementation

### 7.1 Technology

| Component | Choice |
|---|---|
| Language | Python 3.12 |
| Web framework | FastAPI, Jinja2 |
| ORM | SQLModel |
| Database | MySQL 8 (utf8mb4) |
| Web server | nginx 1.27 |
| Front end | Bootstrap 5.3, Bootstrap Icons, Inter, htmx, Quill |
| HTML sanitising | nh3 |
| Password hashing | Argon2 |
| Scheduling | APScheduler |
| Email | Brevo SMTP |
| Study assistant | Google Gemini (optional) |

### 7.2 Code structure

| Folder | Contents |
|---|---|
| `backend/app/models/` | 13 tables |
| `backend/app/schemas/` | Read and input models |
| `backend/app/services/` | 16 services |
| `backend/app/routers/` | 12 routers, 65 routes |
| `backend/app/templates/` | 35 templates, 4 email templates |

Shared modules: `config.py` (settings from `.env`), `security.py` (hashing, CSRF,
rate limiting), `dependencies.py` (login and role checks), `rendering.py`,
`sanitise.py`, `art.py`, `content_seed.py`.

### 7.3 Routes

| Area | Router | Routes |
|---|---|---|
| Login and password | `auth`, `password` | 7 |
| Accounts | `admin` | 7 |
| Modules | `modules` | 11 |
| Content | `content` | 10 |
| Registration | `registrations` | 3 |
| Questions | `questions` | 6 |
| Tests | `tests` | 7 |
| Attempts | `attempts` | 7 |
| Results | `results` | 4 |
| Notifications | `notifications` | 2 |
| Study assistant | `tutor` | 1 |
| **Total** | | **65** |

---

## 8. Testing

**659 automated tests** in 57 files, run with pytest against MySQL 8 in a
separate test database. Each test runs in a transaction that is rolled back.

| Type | Covers |
|---|---|
| Unit tests | `scoring`, `state`, `due`, `art` |
| Service tests | Access checks, test locking, daily job, notifications |
| Route tests | Status codes, role access, CSRF, page content |
| Structure tests | Routers contain no queries; templates receive only read models |

Run the tests with:

```bash
docker compose exec backend pytest
```
