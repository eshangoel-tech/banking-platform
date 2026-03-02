# ADX Bank

Production-style digital banking backend (ADX Bank).

## Tech stack

- **Python** · **FastAPI** · **PostgreSQL** · **Redis** · **Celery** · **SMTP email**
- Modular single-repo architecture

## Project structure

```
banking-platform/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory / entry
│   ├── api/                    # HTTP routes (views + URLs)
│   ├── schemas/                # Pydantic request/response models
│   ├── services/               # Business services
│   │   ├── core/               # Core banking services
│   │   └── ai/                 # AI-specific services
│   ├── repository/             # DB models + DB access
│   │   ├── base.py
│   │   ├── mixins.py
│   │   ├── session.py
│   │   └── models/             # SQLAlchemy models (tables)
│   ├── tasks/                  # Celery tasks
│   ├── common/                 # Shared utilities, logging, constants
│   │   ├── logging.py
│   │   ├── constants/          # enums, limits, messages
│   │   └── responses/          # API response helpers
│   └── config/                 # Configuration (security, Redis, settings)
├── migrations/                 # Alembic
├── tests/
├── scripts/                    # One-off / CLI scripts
├── .env
├── requirements.txt
├── docker-compose.yml          # (optional) local Postgres/Redis
└── README.md
```

## Database structure (current)

Defined in **`app/repository/models/`** and applied via **Alembic** in `migrations/`.

### Core banking tables

| Table                 | Purpose                          | Key columns (high level) |
|-----------------------|----------------------------------|--------------------------|
| **users**             | Bank customers                   | id (UUID), customer_id, full_name, email, phone, password_hash, address (JSONB), salary, kyc_status, status, failed_login_attempts, blocked_until, last_login_at, created_at, updated_at |
| **accounts**          | Bank accounts (1:1 with user)    | id (UUID), user_id (FK), account_number, account_type, balance, currency, status, created_at, updated_at |
| **ledger_entries**    | Financial source of truth        | id (UUID), account_id (FK), entry_type, amount, balance_after, reference_type, reference_id, description, created_at (indexed) |
| **sessions**          | User sessions                    | id (UUID), user_id (FK), session_meta (JSONB), ip_address, user_agent, is_active, expires_at (indexed), created_at |
| **otp_verifications** | OTP lifecycle                    | id (UUID), user_id (FK, nullable), otp_hash, otp_type, attempts, max_attempts, expires_at (indexed), status, created_at |
| **loans**             | Loan contracts                   | id (UUID), user_id (FK), account_id (FK), principal_amount, interest_rate, tenure_months, emi_amount, outstanding_amount, status, approved_at, created_at, updated_at |
| **loan_simulations**  | Loan slider tracking             | id (UUID), user_id (FK), session_id (FK), tested_amount, tested_tenure, calculated_emi, created_at |

### Logging / observability tables

| Table                    | Purpose                          | Key columns (high level) |
|--------------------------|----------------------------------|--------------------------|
| **request_logs**         | HTTP request/response logs       | id (UUID), request_id (UUID), session_id, user_id, method, path, status_code, duration_ms, request_body (JSONB), response_body (JSONB), error_message, created_at; indexes on request_id, session_id, user_id, path, created_at, and (request_id, created_at) |
| **audit_logs**           | Business/audit events            | id (UUID), session_id, user_id, event_type, metadata (JSONB), created_at; indexes on session_id, user_id, event_type, created_at |
| **error_logs**           | Unhandled application errors     | id (UUID), request_id, session_id, user_id, path, method, error_message, stack_trace, created_at; indexed on request_id, session_id, user_id, created_at |
| **external_service_logs**| External integration calls       | id (UUID), service_name, session_id, user_id, request_payload (JSONB), response_payload (JSONB), status, created_at; indexes on service_name, status, created_at, session_id, user_id |
| **ai_interactions**      | AI model usage                   | id (UUID), session_id, user_id, model_name, prompt, response, tokens_used, latency_ms, created_at; indexes on session_id, user_id, created_at |

### Where to change the DB

1. **Add/change tables or columns (application layer)**  
   Edit the SQLAlchemy models in **`app/repository/models/`** (e.g. `user.py`, `account.py`, `request_log.py`). Each file corresponds to one table.

2. **Apply changes to the database**  
   Create and run Alembic migrations:
   ```bash
   alembic revision --autogenerate -m "description"
   alembic upgrade head
   ```
   Migration scripts live in **`migrations/versions/`**. The DB URL is taken from `DATABASE_URL` in `.env` (and from `alembic.ini` for CLI).

3. **Change migration behaviour / env**  
   Edit **`migrations/env.py`** (e.g. how `target_metadata` is built, multi-DB). Model imports there must match **`app.repository.models`** so autogenerate sees all tables.

## What’s built so far

- **FastAPI app** in `app/main.py`: health check at `/health`, OpenAPI at `/docs` and `/redoc`.
- **Config**: `app/config/` — JWT security helpers, Redis client; logging in `app/common/logging.py`.
- **Database / repository**: SQLAlchemy in `app/repository/` — base, session (`get_db`), and the banking + logging schema described above.
- **Alembic**: Migration environment configured to use `app.repository.Base` and import all models from `app.repository.models`.
- **Logging architecture**:
  - JSON structured logs to stdout (`app/common/logging.py`)
  - HTTP logging middleware (`app/api/middleware.py`) that:
    - Generates a `request_id` per request
    - Measures `duration_ms`
    - Extracts `session_id` / `user_id` from headers (best-effort)
    - Sanitizes and truncates request/response bodies before inserting into `request_logs`
  - Global exception handler (`app/main.py`) that:
    - Captures `request_id` / `session_id` / `user_id`
    - Persists stack traces into `error_logs`
    - Returns a generic 500 JSON error without leaking internals
  - Audit logging service (`app/services/core/audit.py`) that writes domain events into `audit_logs`
- **Sanitization utilities** in `app/common/sanitization.py`:
  - `sanitize_payload(payload)` removes sensitive keys (password, otp, token, card_number, cvv, etc.) recursively
  - `truncate_payload(payload, max_bytes)` ensures large payloads aren’t stored in full
- **Placeholders**: `app/api/`, `app/schemas/`, `app/services/core/`, `app/services/ai/`, `app/tasks/` are present for future use.

## Run locally

```bash
# Set .env (e.g. DATABASE_URL, REDIS_URL, JWT_SECRET)
uvicorn app.main:app --reload
```

Health: `GET /health`. Docs: `GET /docs`.
