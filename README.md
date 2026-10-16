# SME Cybersecurity Awareness Training Platform

## Requirements

- Docker with Docker Compose
- Port 80 free
- A filled-in `.env` file in the project folder (database passwords, Brevo SMTP login, optional Gemini key)

## Run

```bash
# 1. Build and start the three containers (db, backend, nginx)
docker compose up -d --build

# 2. Create the demo accounts (prints the emails and shared password)
docker compose exec backend python seed.py

# 3. Check that everything is up
docker compose ps
```

Open <http://localhost>.

Signing in needs a six-digit code sent by email. If email isn't working, the code
also appears in `docker compose logs backend`.

## Stop

```bash
docker compose down      # stop (data is kept)
docker compose down -v   # stop and DELETE the database
```
