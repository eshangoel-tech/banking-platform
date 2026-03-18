# ADX Bank

Production-style digital banking backend built as a learning project.

## Tech Stack

- **Python · FastAPI · PostgreSQL · Redis · Celery · SMTP**
- **AI:** Groq (llama-3.3-70b) · OpenAI (gpt-4o-mini) · Anthropic Claude — auto-fallback chain
- **RAG:** ChromaDB · sentence-transformers (all-MiniLM-L6-v2)
- **Auth:** bcrypt · JWT (HS256) · OTP (SHA-256, SMTP delivery)

## Project Structure

```
banking-platform/
├── app/
│   ├── main.py                         # FastAPI app factory / entry point
│   ├── api/v1/core/                    # HTTP route handlers
│   ├── schemas/                        # Pydantic request/response models
│   ├── services/core/                  # Business logic (auth, user, transfer, wallet, loan)
│   ├── services/ai/                    # AI assistant orchestration + context fetchers
│   ├── ai_agents/                      # Router · bank_manager · loan_officer · accountant · support · receptionist
│   ├── repository/                     # SQLAlchemy models + async data access (Repository pattern)
│   ├── tasks/                          # Celery tasks (loan approval, salary credit, onboarding)
│   ├── common/utils/                   # security.py · otp.py · exceptions.py (single source of truth)
│   └── config/                         # Redis · Celery · AI config · bank_rules.json · bank_policies/
├── migrations/                         # Alembic migrations
├── .env                                # Environment variables
└── requirements.txt
```

## Database (17 tables)

| Group | Tables |
|---|---|
| Banking | users, accounts, ledger_entries, loans, loan_simulations |
| Auth | sessions, otp_verifications, verified_emails |
| Observability | request_logs, audit_logs, error_logs, external_service_logs |
| AI | chat_sessions, chat_responses, llm_interactions |

## API Modules

### Auth (`/api/v1/auth`)
- Register → OTP verify → account auto-created
- Two-step login (password → OTP → JWT)
- Forgot/reset password with email link

### User & Account
- `GET /api/v1/user/profile` — fetch current profile (for pre-filling edit form)
- `PUT /api/v1/user/profile` — update phone + address (JSONB object)
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/account/details`
- `GET /api/v1/transactions` — paginated ledger entries

### Transfer (`/api/v1/transfer`)
- Two-step OTP flow: initiate → confirm
- Receiver identified by **account number OR phone number**
- Atomic debit/credit with ledger entries on both sides

### Wallet (`/api/v1/wallet`)
- Two-step OTP flow: initiate → confirm
- Credits account with `WALLET_TOPUP` ledger entry

### Loans (`/api/v1/loan`)
- Eligibility check — accounts for **existing outstanding loans**
- EMI simulator
- Book → OTP confirm → Celery auto-approves → principal credited to account
- **Pay EMI is OTP-secured**: initiate → OTP → confirm
- Loan closes when outstanding reaches zero

### AI Assistant (`/api/v1/ai/assistant`)
Three-layer multi-agent pipeline:
1. **Router** — splits message, assigns agents + context types
2. **Domain agents** (parallel) — bank_manager · loan_officer · accountant · support
3. **Receptionist** — combines responses, sees full chat history (handles "yes" confirmations)

Features:
- `/start` returns previous `chat_history` so frontend can pre-populate the chat UI
- Multi-provider AI with automatic fallback: Groq → OpenAI → Claude
- RAG pipeline over bank rules + policies (ChromaDB)
- Dev terminal pipeline trace with agent timings + token counts

## Background Tasks (Celery + Redis)

| Task | Trigger |
|---|---|
| Joining bonus ₹500 + welcome email | Email verification |
| Monthly salary credit + email | 2 min after verification |
| Loan auto-approval (PENDING → ACTIVE) + principal disbursement | Loan confirmation |

## Run Locally

```bash
# 1. Install
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure
# Fill in .env (DATABASE_URL, REDIS_URL, JWT_SECRET, SMTP_*, GROQ_API_KEY, etc.)

# 3. Migrate
alembic upgrade head

# 4. Start services (4 terminals)
redis-server
celery -A app.config.celery.celery_app worker --loglevel=info
uvicorn app.main:app --reload
# optional: cd ../banking-frontend && npm run dev
```

API docs: `http://localhost:8000/docs` | Health: `http://localhost:8000/health`

See **`Readfeatures.md`** for full API reference with request/response samples.
