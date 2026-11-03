# SME Cybersecurity Awareness Training Platform

## Requirements

- Docker with Docker Compose
- Port 80 free
- A filled-in `.env` file in the project folder (database passwords, Brevo SMTP login, optional Gemini key)

## Run

```bash
# 1. Build and start the containers (db, backend, nginx, tunnel)
docker compose up -d --build

# 2. Create the demo accounts (prints the emails and shared password)
docker compose exec backend python seed.py

# 3. Check that everything is up
docker compose ps
```

Open <http://localhost> (or `http://<server-ip>` from another machine).

## Access online

The platform is also published at **<https://project.mylocaldomainserver.online>**,
reachable from any device with internet access — no need to be on the same network.

This goes through a Cloudflare tunnel, so it needs `CLOUDFLARE_TUNNEL_TOKEN` set in
`.env` (the `tunnel` container starts with the others).

Signing in needs a six-digit code sent by email. If email isn't working, the code
also appears in `docker compose logs backend`.

## Stop

```bash
docker compose down      # stop (data is kept)
docker compose down -v   # stop and DELETE the database
```
