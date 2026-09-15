# SME Cybersecurity Awareness Training Platform

A small platform for assigning cybersecurity awareness training inside one
organisation, tracking who has completed it, and chasing the people who have not.

All five phases are built: **Phase 0** identity, access and the application
shell, **Phase 1** modules, content and registration, **Phase 2** tests,
**Phase 3** results and progress, **Phase 4** scheduling and notifications. The
platform was specified before it was built, phase by phase; that history is not
part of this checkout but is in git and can be brought back with
`git restore specs/ .claude/ .specify/` if it is ever wanted again.

## What runs

Four containers. Three are the platform; the fourth publishes it.

| Container | Image | What it does | Published port |
|-----------|-------|--------------|----------------|
| `db` | `mysql:8.0` | the database | none |
| `backend` | built from `backend/` | FastAPI, uvicorn, and the daily sweep | none |
| `nginx` | built from `nginx/` | reverse proxy, and the only thing serving `/static/` and `/uploads/` | **80** |
| `tunnel` | `cloudflare/cloudflared` | publishes the site at its public name | none |

Only nginx publishes a port. The database and the application are reachable
only from inside the Docker network, which is why neither needs a password
policy at the network level: nothing outside can open a connection to them.

The tunnel is not part of the platform. The three tiers above run identically
with it absent, and the test suite never sees it.

---

# Installing on a server

## 1. What to put on the USB

The whole project folder, minus what is regenerated or private to your laptop:

```
.git/   .venv/   __pycache__/   .pytest_cache/
```

That leaves about 3 MB. Of it, this is what the platform actually needs:

| Path | Needed for |
|------|-----------|
| `docker-compose.yml` | **required**, defines all four containers |
| `backend/` | **required**, the application and its Dockerfile |
| `nginx/` | **required**, the proxy config and its Dockerfile |
| `.env` | **required**, every password and token |
| `tests/`, `pytest.ini` | only to run the test suite on the server |
| `docs/`, `README.md`, `lms-project-spec.md` | documentation |

**Do not forget `.env`.** It is git-ignored on purpose because it holds the
database passwords, the mail App Password, the Cloudflare tunnel token and the
Gemini key. A `git clone` will not contain it. Either copy it across yourself,
or build a fresh one from `.env.example`, which lists every key with a comment
explaining it.

What is **not** on the USB, and cannot be: the data. The database and the
uploaded images live in Docker volumes on the old machine, not in this folder.
A fresh install starts empty. To carry the data across, see
[Carrying existing data across](#carrying-existing-data-across).

## 2. What the server needs

- **Docker and Docker Compose.** The current server runs Docker 29.2.1 and
  Compose v5.1.0. Anything recent enough to understand `docker compose` works.
- **Internet access during the build.** Four images are pulled:
  `python:3.12-slim`, `nginx:1.27-alpine`, `mysql:8.0`, and
  `cloudflare/cloudflared:2026.9.1`. See
  [Installing without internet](#installing-without-internet) if the server has
  none.
- **Outbound access to `smtp.gmail.com:587`. Verify this first.** Every sign-in
  needs an emailed code and there is no bypass. If mail is blocked, nobody signs
  in until it is unblocked.
- **No inbound port.** Do not forward anything on the router and do not open 443.
  The tunnel makes an outbound connection and serves through it.
- **A correct clock.** Every time is stored in UTC and converted in the browser.
  A server clock that is wrong shifts every due date and every test window.
- A machine that does not sleep. The daily sweep runs at a fixed hour and a
  sleeping machine simply misses it.

## 3. Copy and configure

```bash
# From the USB to the server, whatever name you give the folder.
cp -r /Volumes/USB/canvas-project ~/canvas-project
cd ~/canvas-project

# If you did not bring .env, build one:
cp .env.example .env
```

Then fill in `.env`. Every key is required; the file explains each one. The four
that decide whether the platform works at all:

| Key | What it is |
|-----|-----------|
| `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD` | any two long strings you choose |
| `SESSION_SECRET` | any long random string; changing it signs everyone out |
| `SMTP_USER`, `SMTP_APP_PASSWORD`, `SMTP_FROM` | a Google **App Password**, not an account password |
| `CLOUDFLARE_TUNNEL_TOKEN` | the connector token, from the Cloudflare dashboard |

Two more matter at production time:

```bash
SHOW_LOGIN_CODE=false     # true prints the sign-in code on the page itself
GEMINI_API_KEY=           # empty means the study assistant is simply absent
```

`SHOW_LOGIN_CODE=true` is a development convenience for when the mail provider
refuses to send. It shows anyone the code on the page that asks for it, so it
must be `false` anywhere real. [`backend/app/development.py`](backend/app/development.py)
explains how to delete the feature for good.

## 4. Start it

```bash
docker compose up -d --build
```

The first run takes a few minutes: it pulls four images, installs the Python
dependencies, and initialises MySQL. Afterwards a restart takes seconds.

To run the platform **without** publishing it, name the three services and the
tunnel is never created:

```bash
docker compose up -d --build db backend nginx
```

## 5. Create the accounts

```bash
docker compose exec backend python seed.py
```

This prints seven demonstration accounts and the one password they share: an
administrator, an instructor, and five trainees. They are exempt from the
first-sign-in password change, **not** from the emailed code. Run it twice and
it does nothing the second time.

Change that administrator's password before anyone else uses the machine.

## 6. Check it worked

```bash
docker compose ps                    # four containers, db healthy

curl -s -o /dev/null -w '%{http_code}\n' http://localhost      # 200
curl -s http://localhost | grep -o '<title>[^<]*</title>'       # the landing page

docker compose logs --tail 20 backend
docker compose logs --tail 20 tunnel # "Registered tunnel connection" x4
```

Use `GET`, not `curl -I`. The landing route answers `HEAD` with 405, which
proves nginx and the application are both alive but reads like a fault.

Then open it in a browser:

- on the server itself, <http://localhost>
- from another machine on the same network, `http://<the server's IP>`
- from anywhere, the public address the tunnel serves

If a browser shows **"The platform is restarting"**, nginx is up and the
application is not. That page refreshes itself every ten seconds, so a slow
start resolves on its own. If it persists, read `docker compose logs backend`.

---

# Publishing it at a public address

The tunnel container connects outward to Cloudflare and serves the site through
that connection. Nothing dials in, so the server needs no public address, no
forwarded port and no TLS certificate of its own. Cloudflare holds the
certificate; the hop from the connector to nginx is plain HTTP inside the
Docker network and never leaves the machine.

The origin is named `http://nginx:80` in the Cloudflare dashboard, and
`docker-compose.yml` gives the connector a hosts entry for that name so it
resolves without a name server.

**One rule, and it is the only one that has ever broken this site:**

> Every connector running on a tunnel must be able to reach every origin that
> tunnel serves.

Cloudflare spreads requests across all registered connectors. A second connector
that cannot reach nginx does not fail over, it answers **502 Bad Gateway** for
whatever share of requests lands on it, and it leaves no trace in this stack's
logs because those requests never arrive here. That produced days of
intermittent failures that looked like a network problem. If you run more than
one stack behind Cloudflare, give each stack its own tunnel, or put one
connector on every network.

To check what is registered:

```bash
docker ps --format '{{.Names}}\t{{.Image}}' | grep cloudflare
docker compose logs tunnel | grep -c 'Unable to reach'   # must be 0
```

---

# Carrying existing data across

The database and the uploaded images are in Docker volumes named after the
project folder: `canvas-project_db_data` and `canvas-project_uploads`. They are
not in the project folder and not on the USB.

**On the old machine:**

```bash
cd ~/canvas-project

docker compose exec -T db sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction lms' > lms-backup.sql

docker run --rm -v canvas-project_uploads:/data -v "$PWD":/out \
  alpine tar czf /out/uploads.tgz -C /data .
```

Copy `lms-backup.sql` and `uploads.tgz` to the USB alongside the project.

**On the new machine**, after step 4 above has the containers running:

```bash
cd ~/canvas-project

docker compose exec -T db sh -c \
  'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" lms' < lms-backup.sql

docker run --rm -v canvas-project_uploads:/data -v "$PWD":/in \
  alpine tar xzf /in/uploads.tgz -C /data

docker compose restart backend
```

Restore the images as well as the database. The database records which file
belongs to which page, and a page whose file is missing shows a broken image
with nothing to explain why.

Skip `seed.py` when you have restored real data; the accounts are already in the
dump.

# Backing up

There is no automatic backup. The same two commands are the whole of it:

```bash
docker compose exec -T db sh -c \
  'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction lms' > backup-$(date +%F).sql

docker run --rm -v canvas-project_uploads:/data -v "$PWD":/out \
  alpine tar czf /out/uploads-$(date +%F).tgz -C /data .
```

If the volume is lost and there is no dump, the data is gone.

# Installing without internet

The build pulls four images. On a machine that has internet, save them:

```bash
docker pull python:3.12-slim nginx:1.27-alpine mysql:8.0 cloudflare/cloudflared:2026.9.1
docker save python:3.12-slim nginx:1.27-alpine mysql:8.0 cloudflare/cloudflared:2026.9.1 \
  | gzip > images.tgz
```

Carry `images.tgz` on the USB, and on the server:

```bash
gunzip -c images.tgz | docker load
docker compose up -d --build
```

The Python dependencies in `backend/requirements.txt` are installed during the
build and still need PyPI. To avoid that too, build the `backend` image on the
machine that has internet and save it the same way.

---

# Day to day

## Watching who is using it

nginx logs every request. The first address in each line is always the tunnel
container, because the tunnel is what connects to nginx. The real visitor
address is the **last quoted field**, forwarded by Cloudflare:

```bash
docker compose logs -f nginx                       # live

docker compose logs --no-log-prefix nginx \
  | awk -F'"' '{print $8}' | sort | uniq -c | sort -rn    # visitors by volume
```

The log lives inside the container and is lost on `docker compose down`.

## Running the tests

```bash
docker compose exec backend pytest
```

That single command is the whole suite. Tests run against a disposable schema on
the same MySQL server, never SQLite: this project depends on foreign keys, a
unique index and `utf8mb4`, and SQLite enforces none of them the same way.

## Changing a model

There are no migrations. `create_all()` creates missing tables and never alters
an existing one, so a changed model against a stale schema fails at runtime:

```bash
docker compose down -v && docker compose up -d --build
docker compose exec backend python seed.py
```

`down -v` **deletes the database**. Take a dump first if the data matters.

### The one change that was made by hand

`module.art` was widened from 32 to 64 characters so it could hold the name of
an uploaded cover picture as well as a pattern name. `create_all()` never
alters an existing column, so a database created before that change needs one
statement:

```bash
docker compose exec db sh -c \
  'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" lms -e \
   "ALTER TABLE module MODIFY art VARCHAR(64) NULL;"'
```

Widening a column keeps every value in it. A database created fresh after the
change already has the right width and needs nothing.

## Removing a module permanently

Removing a module from the platform is reversible: it disappears from every
list while its pages, images and registrations stay exactly where they are, and
restoring it brings all of them back. There is no route that removes one for
good, and that is deliberate.

Permanent removal is a database operation, and **whoever performs it must also
delete that module's image files**. Nothing in the application does this, and an
image whose page was deleted is never collected on its own:

```bash
# 1. See what will go.
docker compose exec db mysql -uroot -p -e \
  "SELECT stored_name FROM lms.content_image WHERE module_id = <id>;"

# 2. Delete those files from the volume.
docker compose exec backend sh -c 'rm -f /data/uploads/<stored_name> ...'

# 3. Then the rows, children first.
docker compose exec db mysql -uroot -p -e "
  DELETE FROM lms.content_image WHERE module_id = <id>;
  DELETE FROM lms.page          WHERE module_id = <id>;
  DELETE FROM lms.registration  WHERE module_id = <id>;
  DELETE FROM lms.module        WHERE id        = <id>;"
```

Do step 2 before step 3. Once the rows are gone, nothing records which files
belonged to that module, and they stay on the volume forever.

---

# Signing in

Email and password, then a six-digit code sent to that address. Every sign-in,
for everyone, every time. There is no trusted device and no remembered browser.

An account an administrator created or reset must choose its own password before
anything else is reachable.

An administrator does not appear in their own account list and cannot edit their
own row. Another administrator resets their password. With one administrator and
a forgotten password there is no route back, so keep two.

# What this deliberately does not do

- **No self-registration.** Accounts come from an administrator or from the seed.
- **No self-service password reset.** An administrator resets it; the person then
  chooses their own.
- **No audit trail.** Nothing records who did what.
- **No automatic backup.** The database lives in one Docker volume on one
  machine. The dump above is the whole of it.
- **No application logging** beyond whatever the server prints.
- **English, left to right, only.**

Each of these is a recorded decision, not an oversight. The reasoning was
written down phase by phase during the spec-driven build; that record is not in
this checkout, but git still has it under `specs/` and it comes back with
`git restore specs/`.

# Layout

```text
docker-compose.yml     four services; only nginx publishes a port
nginx/                 reverse proxy, the maintenance page, and /static/
backend/app/
├── models/            the schema, SQLModel table classes
├── schemas/           non-table models at every boundary, in and out
├── services/          business logic, authorisation, and every query
├── routers/           thin: parse, call one service, render or redirect
├── templates/         Jinja2, with Bootstrap and HTMX vendored under static/
└── development.py     the sign-in code display; meant to be deleted
tests/                 pytest, against MySQL
docs/                  the design system, the analysis report, the testing guide
```
