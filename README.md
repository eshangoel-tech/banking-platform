# ADX Bank

Production-style digital banking backend (ADX Bank).

## Tech stack

- **Python** · **FastAPI** · **PostgreSQL** · **Redis** · **Celery** · **SMTP email** · **OpenAI (gpt-4o-mini)** · **ChromaDB (RAG)**
- Modular single-repo architecture

## Project structure

```
banking-platform/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory / entry
│   ├── api/                        # HTTP routes (views + URLs)
│   ├── schemas/                    # Pydantic request/response models
│   ├── services/                   # Business services
│   │   ├── core/                   # Core banking services
│   │   └── ai/                     # AI-specific services
│   ├── repository/                 # DB models + DB access
│   │   ├── base.py
│   │   ├── mixins.py
│   │   ├── session.py
│   │   └── models/                 # SQLAlchemy models (tables)
│   ├── tasks/                      # Celery tasks
│   ├── common/                     # Shared utilities, logging, constants
│   │   ├── logging.py
│   │   ├── sanitization.py         # Payload redaction + truncation for logs
│   │   ├── constants/              # enums, limits, messages
│   │   ├── responses/              # API response helpers
│   │   └── utils/                  # Cross-cutting utility functions
│   │       ├── security.py         # bcrypt password hashing + JWT (single source of truth)
│   │       ├── otp.py              # OTP generation/hashing + SMTP email delivery
│   │       └── exceptions.py       # AppException base class + all factory helpers
│   └── config/                     # Configuration (Redis, settings)
├── migrations/                     # Alembic
├── tests/
├── scripts/                        # One-off / CLI scripts
├── .env
├── requirements.txt
├── docker-compose.yml              # (optional) local Postgres/Redis
└── README.md
```

> **Rule:** anything consumed by more than one API module (or likely to be) lives in `app/common/utils/`.
> Old locations (`app/core/security.py`, `app/config/security.py`, `app/services/core/auth_service/otp_manager.py`,
> `app/services/core/auth_service/exceptions.py`) are now thin re-export shims pointing here.

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
| **verified_emails**   | Pre-verified email addresses     | id (UUID), email (unique), created_at |
| **loans**             | Loan contracts                   | id (UUID), user_id (FK), account_id (FK), principal_amount, interest_rate, tenure_months, emi_amount, outstanding_amount, status, approved_at, created_at, updated_at |
| **loan_simulations**  | Loan slider tracking             | id (UUID), user_id (FK), session_id (FK), tested_amount, tested_tenure, calculated_emi, created_at |

### Logging / observability tables

| Table                    | Purpose                          | Key columns (high level) |
|--------------------------|----------------------------------|--------------------------|
| **request_logs**         | HTTP request/response logs       | id (UUID), request_id (UUID), session_id, user_id, method, path, status_code, duration_ms, request_body (JSONB), response_body (JSONB), error_message, created_at; indexes on request_id, session_id, user_id, path, created_at, and (request_id, created_at) |
| **audit_logs**           | Business/audit events            | id (UUID), session_id, user_id, event_type, metadata (JSONB), created_at; indexes on session_id, user_id, event_type, created_at |
| **error_logs**           | Unhandled application errors     | id (UUID), request_id, session_id, user_id, path, method, error_message, stack_trace, created_at; indexed on request_id, session_id, user_id, created_at |
| **external_service_logs**| External integration calls       | id (UUID), service_name, session_id, user_id, request_payload (JSONB), response_payload (JSONB), status, created_at; indexes on service_name, status, created_at, session_id, user_id |
| **chat_sessions**        | AI chat session lifecycle        | chat_sess_id (UUID PK), session_id (FK→sessions, nullable), customer_id, started_at, last_active, status (ACTIVE/CLOSED) |
| **chat_responses**       | One row per user↔assistant turn  | response_id (UUID PK), chat_sess_id (FK→chat_sessions), user_message, assistant_response, created_at |
| **llm_interactions**     | Low-level record per LLM call    | interaction_id (UUID PK), response_id (FK→chat_responses), agent_name, request, response, status, error_msg, token_input, token_output, context_attached, latency_ms, created_at, updated_at |

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
- **Config**: `app/config/` — Redis client; logging in `app/common/logging.py`.
- **Common utils** (`app/common/utils/`):
  - `security.py` — `hash_password`, `verify_password`, `create_access_token`, `verify_token` (HS256 JWT). Single source of truth; `app/core/security.py` and `app/config/security.py` re-export from here.
  - `otp.py` — `generate_otp` (CSPRNG 6-digit), `hash_otp` / `verify_otp_hash` (SHA-256), and `send_otp_email` (async SMTP via aiosmtplib with STARTTLS, HTML + plain-text template). Old `otp_manager.py` re-exports from here.
  - `exceptions.py` — `AppException` dataclass + factory helpers for every error code (auth, OTP, token, generic). Old `auth_service/exceptions.py` re-exports from here.
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

## Auth module (v1) — implemented

Endpoints:

- `POST /api/v1/auth/register`
  - Validates email + phone uniqueness
  - Hashes password using **bcrypt**
  - Creates user with `status=INACTIVE`, `kyc_status=PENDING`
  - Generates a 6-digit OTP, stores only **SHA256 hash** in `otp_verifications`
  - OTP expires in **5 minutes**, max attempts **3**
  - **Sends OTP to the registered email via SMTP** (HTML + plain-text, STARTTLS)

- `POST /api/v1/auth/verify-email`
  - Validates OTP, expiry, and attempts
  - Marks OTP as VERIFIED
  - Activates user (`status=ACTIVE`, `kyc_status=VERIFIED`)
  - Creates an account automatically (`account_type=CURRENT`, `balance=0`)

Clean architecture locations:

- **Routes (view layer)**: `app/api/v1/core/auth/routes.py`
- **Schemas**: `app/schemas/auth.py`
- **Service layer**: `app/services/core/auth_service/service.py`
- **Repository layer**: `app/repository/core/auth_repository/repository.py`
- **OTP utils + SMTP delivery**: `app/common/utils/otp.py`
- **Password hashing + JWT**: `app/common/utils/security.py`
- **Exceptions**: `app/common/utils/exceptions.py`

## AI assistant (v1)

A three-layer multi-agent AI assistant powered by OpenAI **gpt-4o-mini** and a
ChromaDB RAG pipeline over bank policies and rules.

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/ai/assistant/start` | JWT | Open a session; pre-loads user context + chat history into Redis |
| POST | `/api/v1/ai/assistant/chat` | JWT | Send a message; runs multi-agent pipeline; returns response + redirect actions |
| POST | `/api/v1/ai/assistant/stop` | JWT | Close session; clears Redis cache |

### Architecture

```
User message
     │
     ▼
Layer 1 ─ Router (assistant agent)
     │  Splits message into sub-queries.
     │  Assigns each to: bank_manager | loan_officer | accountant | support | receptionist
     │  Specifies required context types per sub-query.
     │
     ▼
Layer 2 ─ Domain agents (run concurrently via asyncio.gather)
     │  bank_manager  — account balance, transactions
     │  loan_officer  — loans, EMI, eligibility
     │  accountant    — financial summaries, spending analysis
     │  support       — policy/rules questions (uses RAG context)
     │
     ▼
Layer 3 ─ Receptionist
     │  Combines all domain-agent responses into one coherent reply.
     │  Handles greetings, unclear queries, redirect confirmations.
     │  Collects and deduplicates redirect actions.
     │
     ▼
Final response  +  redirect actions (e.g. PAY_EMI → /loans)
```

### Context types

The router can request any combination:

| Name | Source |
|------|--------|
| `user_context` | Redis (cached at session start) |
| `chat_history` | Redis (updated after each turn) |
| `account_context` | DB — `accounts` table |
| `transaction_context` | DB — `ledger_entries` table (last 10) |
| `loan_context` | DB — `loans` table |
| `bank_policy` | RAG — ChromaDB `bank_policies` collection |
| `bank_rules` | RAG — ChromaDB `bank_rules` collection |

### Redirect actions (tools)

Agents can suggest page navigations.  The API returns them as:

```json
{
  "name" : "PAY_EMI",
  "label": "Pay EMI",
  "url"  : "/loans"
}
```

Available tools: `PAY_EMI`, `GET_LOAN`, `ADD_MONEY`, `TRANSFER_MONEY`,
`EDIT_PROFILE`, `VIEW_TRANSACTIONS`, `VIEW_LOANS`, `VIEW_ACCOUNT`, `CONTACT_SUPPORT`.

Defined in **`app/common/tools.py`**.

### RAG pipeline

On server startup `initialize_vector_store()` (called via `asyncio.run_in_executor`):
1. Drops and recreates two ChromaDB collections (`bank_rules`, `bank_policies`).
2. Parses JSON files from `app/config/bank_rules/` and `app/config/bank_policies/`.
3. Embeds all chunks using `sentence-transformers/all-MiniLM-L6-v2`.
4. Upserts into ChromaDB (cosine similarity, persistent at `chroma_data/`).

Retrieval returns top-k annotated chunks: `[source | section | similarity]\ntext`.

### Key files

| File | Role |
|------|------|
| `app/config/ai_config.py` | OPENAI_API_KEY, model, session TTL |
| `app/common/tools.py` | Redirect tool definitions |
| `app/services/ai/llm_utils.py` | Shared `call_llm()` + `LLMCallResult` |
| `app/ai_agents/assistant/agent.py` | Layer 1 — router |
| `app/ai_agents/bank_manager/agent.py` | Layer 2 — bank manager |
| `app/ai_agents/loan_officer/agent.py` | Layer 2 — loan officer |
| `app/ai_agents/accountant/agent.py` | Layer 2 — accountant |
| `app/ai_agents/support_staff/agent.py` | Layer 2 — support (RAG) |
| `app/ai_agents/receptionist/agent.py` | Layer 3 — receptionist / combiner |
| `app/services/ai/assistant_service.py` | Orchestration service |
| `app/services/ai/context_fetch.py` | DB + RAG context fetchers |
| `app/services/ai/rag/` | Embedder, ingester, vector store, retriever |
| `app/repository/core/chat_repository/` | ChatSession, ChatResponse, LLMInteraction data access |

### Environment variables

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini   # optional, defaults to gpt-4o-mini
```

## Run locally

```bash
# Copy and fill in .env
cp .env.example .env

# Install dependencies
pip install -r requirements.txt

# Apply DB migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

Health: `GET /health`. Docs: `GET /docs`.

## SMTP configuration

Set the following in `.env` to enable OTP email delivery:

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@adxbank.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=noreply@adxbank.com
SMTP_FROM_NAME=ADX Bank
```

If SMTP is not configured, registration still succeeds but an error is logged and the OTP is not delivered.
