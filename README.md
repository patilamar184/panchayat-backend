# panchayat-backend

Backend API for **Panchayat**, a civic issue reporting and resolution platform.
FastAPI + PostgreSQL + SQLAlchemy 2 + Alembic, run with Docker Compose. The frontend is a separate project.

## Layout

```
app/
  main.py            app factory, routers, CORS, error handlers
  core/              config (env settings), security (JWT, Argon2), DomainError
  db/                declarative Base + naming convention, engine/session
  models/            User, Complaint, ComplaintStatusHistory, ComplaintMedia, Notification
  schemas/           Pydantic request/response models
  services/          business rules (users, complaints workflow, notifications, media)
  api/deps.py        auth + role dependencies
  api/routes/        thin HTTP routes
  cli.py             first-administrator setup
migrations/          Alembic (single clean baseline: 0001_baseline)
tests/               pytest suite (SQLite in memory, no PostgreSQL needed)
```

## Run with Docker (recommended)

1. `cp .env.example .env`, then replace the placeholder passwords/secret
   (a ready-made `.env` with fresh random values may already exist; it is git-ignored).
   Secret key: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. `docker compose up --build -d`
   This starts two services, `db` (PostgreSQL 16) and `api`. The API container runs
   `alembic upgrade head` on start, then serves on http://localhost:8000.
3. Create the first administrator:
   `docker compose exec api python -m app.cli create-admin --email you@example.com --full-name "Your Name"`
   (you are asked for the password at a hidden prompt).
4. Open http://localhost:8000/docs (Swagger) and http://localhost:8000/health.

Data lives in the **new named volumes** `panchayat_backend_pgdata` and `panchayat_backend_media`.
PostgreSQL is published on `127.0.0.1:5433` (not 5432) so it cannot collide with an older project.
`docker compose down` keeps your data; `docker compose down -v` would delete **this project's** volumes only.
Nothing here touches any other project's database or volume.

## Run locally (without Docker for the API)

1. Start only the database: `docker compose up -d db`
2. `python -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements-dev.txt`
4. Make sure `.env` has `DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5433/DBNAME` (same values as the POSTGRES_* entries)
5. `alembic upgrade head`
6. `python -m app.cli create-admin --email you@example.com --full-name "Your Name"`
7. `uvicorn app.main:app --reload`

## Tests

```
pip install -r requirements-dev.txt
pytest
```
Tests cover authentication, roles, employee approval, complaint ownership, the status workflow and history,
notifications, and media validation/access.

## Migrations

- Apply: `alembic upgrade head`
- Render SQL without a database: `alembic upgrade head --sql`
- New change: `alembic revision --autogenerate -m "describe change"` (review the file before applying)

## Access rules

| Role | Can do |
|---|---|
| citizen | register, log in, manage profile/password, deactivate account, create complaints, see **only own** complaints and their history, upload/list/download/delete **own** complaint images, read own notifications |
| employee | register (starts `pending`); once approved: see **only assigned** complaints, move them forward, read own notifications |
| admin | approve/reject employees, list/filter all complaints, assign complaints, make admin status changes. Created only with the CLI, never through public registration |

Not-yours complaints, images and notifications return **404** (their existence is not revealed).
Deactivated accounts are refused at login and on every request with an existing token.

## Complaint workflow

Statuses: `reported, under_review, assigned, in_progress, resolved, closed`.

| From | To | Who |
|---|---|---|
| reported | under_review | admin |
| reported / under_review / assigned | assigned (assign or reassign to an approved, active employee) | admin |
| under_review | closed (notes required) | admin |
| assigned | in_progress | assigned employee |
| in_progress | resolved (resolution notes required) | assigned employee |
| resolved | in_progress (reopen) | assigned employee |
| resolved | closed | admin |

Anything else returns **409**. Every change writes a `complaint_status_history` row
(actor, action, previous/new status, notes, timestamp) and notifies the citizen (and the employee on assignment).

## Main endpoints (all under `/api/v1`, plus `GET /health`)

- Auth: `POST /auth/register/citizen`, `/auth/register/employee`, `/auth/login` (JSON), `/auth/token` (form, for Swagger "Authorize")
- Me: `GET|PATCH /users/me`, `POST /users/me/password`, `POST /users/me/deactivate`
- Citizen: `POST|GET /complaints`, `GET /complaints/{id}`, `GET /complaints/{id}/history`
- Media: `POST|GET /complaints/{id}/media`, `GET /media/{id}/file`, `DELETE /media/{id}` (JPEG/PNG/WEBP, extension + declared type + decoded format must agree, size limit `MAX_UPLOAD_BYTES`, max `MAX_IMAGES_PER_COMPLAINT` per complaint)
- Employee: `GET /employee/complaints`, `POST /employee/complaints/{id}/status`
- Admin: `GET /admin/employees`, `POST /admin/employees/{id}/approve|reject`, `GET /admin/complaints` (filters: status, category, citizen_id, assigned_employee_id, unassigned, q, created_from, created_to, page, page_size), `POST /admin/complaints/{id}/assign|status`
- Notifications: `GET /notifications`, `GET /notifications/unread`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`

Full interactive docs: `/docs` (Swagger) and `/redoc`; schema at `/openapi.json`.

## Notes

- `is_public` is stored on complaints, but no public (unauthenticated) listing endpoint exists yet.
- Files go to `MEDIA_ROOT` (a Docker volume in Compose). Swap `app/services/media.py` for object storage in production.
- Set `CORS_ORIGINS` to your frontend's address(es).
