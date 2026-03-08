# ADX Bank — Features & API Reference

> **Demo disclaimer:** ADX Bank is NOT a real bank. This is a production-style
> learning project for educational purposes.

---

## Table of Contents

1. [Auth Module](#1-auth-module)
2. [User & Account Module](#2-user--account-module)
3. [Transfer Module](#3-transfer-module)
4. [Wallet Module](#4-wallet-module)
5. [Loan Module](#5-loan-module)
6. [AI Assistant Module](#6-ai-assistant-module)
7. [Background Tasks (Celery)](#7-background-tasks-celery)
8. [RAG Pipeline](#8-rag-pipeline)
9. [Running Locally — Step by Step](#9-running-locally--step-by-step)

---

## 1. Auth Module

Prefix: `/api/v1/auth`

### Register
```
POST /api/v1/auth/register
```
- Creates an **INACTIVE** user account
- Hashes password with bcrypt
- Generates a 6-digit OTP (SHA-256 stored, never plaintext), valid **5 minutes**, max **3 attempts**
- Sends OTP to the registered email via SMTP

**Request body:**
```json
{
  "full_name": "Arjun Sharma",
  "email": "arjun@example.com",
  "phone": "9876543210",
  "password": "SecurePass123",
  "address": { "city": "Mumbai", "state": "Maharashtra" },
  "salary": 50000
}
```

---

### Verify Email
```
POST /api/v1/auth/verify-email
```
- Validates OTP
- Activates user (`status=ACTIVE`, `kyc_status=VERIFIED`)
- Creates a bank account automatically
- Fires Celery task → credits ₹500 joining bonus + sends welcome email

**Request body:**
```json
{ "email": "arjun@example.com", "otp": "123456" }
```

---

### Login (Step 1)
```
POST /api/v1/auth/login
```
- Verifies email + password
- Sends a 6-digit LOGIN OTP to email
- Blocks account for **1 hour** after 3 consecutive wrong passwords

**Request body:**
```json
{ "email": "arjun@example.com", "password": "SecurePass123" }
```

---

### Verify Login OTP (Step 2)
```
POST /api/v1/auth/verify-login-otp
```
- Verifies OTP
- Creates a DB session
- Returns a **JWT token** (HS256, 30-minute expiry)

**Request body:**
```json
{ "email": "arjun@example.com", "otp": "654321" }
```

**Response includes:**
```json
{ "token": "<jwt>", "session_id": "<uuid>" }
```

---

### Forgot Password
```
POST /api/v1/auth/forgot-password
```
- Always returns a generic success message (no enumeration)
- Sends a password reset link to the email (15-minute expiry)

```json
{ "email": "arjun@example.com" }
```

---

### Reset Password
```
POST /api/v1/auth/reset-password
```
- Validates reset token
- Updates password hash
- Invalidates all active sessions

```json
{ "token": "<reset_token>", "new_password": "NewPass456" }
```

---

## 2. User & Account Module

All endpoints require **`Authorization: Bearer <jwt>`** header.

### Dashboard Summary
```
GET /api/v1/dashboard/summary
```
Returns account balance, recent transactions count, active loans, and user profile basics.

---

### Account Details
```
GET /api/v1/account/details
```
Full account info: account number, type, balance, currency, status.

---

### Transaction History
```
GET /api/v1/transactions?page=1&limit=10
```
Paginated ledger entries (max 50 per page). Each entry includes:
- `entry_type` (CREDIT / DEBIT)
- `amount`, `balance_after`
- `reference_type` (TRANSFER / WALLET_TOPUP / LOAN_EMI / SALARY_CREDIT / JOINING_BONUS)
- `description`, `created_at`

---

### Update Profile
```
PUT /api/v1/user/profile
```
Update phone number and/or address.
```json
{ "phone": "9123456789", "address": { "city": "Delhi" } }
```

---

## 3. Transfer Module

Prefix: `/api/v1/transfer` | Requires JWT

### Initiate Transfer (Step 1)
```
POST /api/v1/transfer/initiate
```
- Validates sender/receiver accounts
- Checks sufficient balance
- Stores transfer as PENDING
- Sends a TRANSFER OTP to sender's email

```json
{
  "to_account_number": "ADX0000012",
  "amount": 500.00,
  "description": "Rent payment"
}
```

Returns `transfer_id`.

---

### Confirm Transfer (Step 2)
```
POST /api/v1/transfer/confirm
```
- Verifies OTP
- Atomically debits sender and credits receiver
- Creates ledger entries for both accounts
- Marks transfer as COMPLETED

```json
{ "transfer_id": "<uuid>", "otp": "112233" }
```

---

## 4. Wallet Module

Prefix: `/api/v1/wallet` | Requires JWT

> Razorpay has been removed. All top-ups are OTP-verified.

### Initiate Add Money (Step 1)
```
POST /api/v1/wallet/add-money/initiate
```
- Validates amount (max ₹50,000 per transaction)
- Stores top-up request in Redis (key: `wallet_topup:{topup_id}`, TTL 5 minutes)
- Sends ADD_MONEY OTP to email

```json
{ "amount": 5000.00 }
```

Returns `topup_id`.

---

### Confirm Add Money (Step 2)
```
POST /api/v1/wallet/add-money/confirm
```
- Verifies OTP
- Credits account balance
- Creates ledger entry (CREDIT, reference_type=WALLET_TOPUP)

```json
{ "topup_id": "<uuid>", "otp": "445566" }
```

---

## 5. Loan Module

Prefix: `/api/v1/loan` | Requires JWT

### Check Eligibility
```
GET /api/v1/loan/eligibility
```
Returns max eligible loan amount (`salary × 12`) and whether the customer qualifies.

---

### Simulate Loan
```
POST /api/v1/loan/simulate
```
Calculates EMI for a given principal + tenure. Saves a simulation record.

```json
{ "amount": 100000, "tenure_months": 12 }
```

Returns `emi_amount`, `total_payable`, `interest_amount`.

---

### Book Loan (Step 1)
```
POST /api/v1/loan/book
```
- Validates eligibility
- Stores booking in Redis (TTL 5 minutes)
- Sends LOAN_BOOK OTP to email

```json
{ "amount": 100000, "tenure_months": 12 }
```

Returns `booking_id`.

---

### Confirm Loan (Step 2)
```
POST /api/v1/loan/confirm
```
- Verifies OTP
- Creates Loan record (status=PENDING)
- Dispatches Celery task → auto-approves to ACTIVE within seconds

```json
{ "booking_id": "<uuid>", "otp": "778899" }
```

---

### List Loans
```
GET /api/v1/loan/list
```
Returns all loans (PENDING / ACTIVE / CLOSED) newest first.

---

### Pay EMI
```
POST /api/v1/loan/{loan_id}/pay
```
- Deducts `min(emi_amount, outstanding_amount)` from wallet
- Creates DEBIT ledger entry (reference_type=LOAN_EMI)
- Closes loan when `outstanding_amount` reaches zero

---

## 6. AI Assistant Module

Prefix: `/api/v1/ai/assistant` | Requires JWT

### Architecture

```
User message
     │
     ▼
Layer 1 — Router (assistant agent)
     │  Splits into sub-queries. Assigns each to the right agent + context.
     ▼
Layer 2 — Domain agents (run in parallel)
     │  bank_manager  → account queries + financial advice
     │  loan_officer  → loan eligibility, EMI, comparison
     │  accountant    → payment issues, transaction analysis
     │  support       → policy/rules questions + troubleshooting (uses RAG)
     ▼
Layer 3 — Receptionist
     │  Combines all responses into one natural reply.
     │  Handles greetings, redirects, unclear queries.
     ▼
Final response  +  redirect action buttons
```

---

### Start Session
```
POST /api/v1/ai/assistant/start
```
- Creates a `chat_sessions` row (status=ACTIVE)
- Fetches user profile + last 10 chat turns
- Caches context in Redis (`ai_context:{chat_sess_id}`, TTL 1 hour)

**Response:**
```json
{ "chat_sess_id": "<uuid>" }
```

---

### Chat
```
POST /api/v1/ai/assistant/chat
```
Runs the full multi-agent pipeline.

**Request body:**
```json
{
  "chat_sess_id": "<uuid>",
  "message": "What is my current balance and can I afford a ₹1L loan?"
}
```

**Response:**
```json
{
  "response": "Your current balance is ₹12,500. Based on your salary of ₹40,000, you're eligible for up to ₹4,80,000. A ₹1L loan over 12 months would cost ₹8,885/month — well within reach!",
  "actions": [
    { "name": "GET_LOAN", "label": "Apply for Loan", "url": "/loans" }
  ],
  "chat_sess_id": "<uuid>"
}
```

**What agents handle:**

| Question type | Agent |
|---|---|
| Account blocked, summary, charges | bank_manager |
| Loan eligibility, EMI, rejection | loan_officer |
| Payment failed, where did money go | accountant |
| Interest calculation, foreclosure, OTP not received | support |
| Greetings, "yes" to redirect, unclear text | receptionist |

**Redirect action buttons:**

| Tool name | Label | URL |
|---|---|---|
| PAY_EMI | Pay EMI | /loans |
| GET_LOAN | Apply for Loan | /loans |
| ADD_MONEY | Add Money | /wallet |
| TRANSFER_MONEY | Transfer Money | /transfer |
| EDIT_PROFILE | Edit Profile | /profile |
| VIEW_TRANSACTIONS | View Transactions | /transactions |
| VIEW_LOANS | View Loans | /loans |
| VIEW_ACCOUNT | View Account | /dashboard |
| CONTACT_SUPPORT | Contact Support | /support |

---

### Stop Session
```
POST /api/v1/ai/assistant/stop
```
Closes the session and clears Redis cache.

```json
{ "chat_sess_id": "<uuid>" }
```

---

## 7. Background Tasks (Celery)

Celery workers process two types of async tasks:

### Account On-boarding (triggered on email verification)
1. **Immediately:** Credits ₹500 joining bonus → ledger entry + audit log → sends welcome email
2. **After 2 minutes:** Credits user's monthly salary → ledger entry → sends salary email

### Loan Auto-Approval
- Triggered after loan confirmation
- Moves loan from `PENDING → ACTIVE`
- Retries up to 3× with 10s backoff on failure

---

## 8. RAG Pipeline

On every server startup, ADX Bank automatically:

1. **Drops** existing ChromaDB collections (`bank_rules`, `bank_policies`)
2. **Parses** JSON files from:
   - `app/config/bank_rules/bank_rules.json` → `bank_rules` collection
   - `app/config/bank_policies/*.json` → `bank_policies` collection
3. **Embeds** all chunks using `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
4. **Stores** in ChromaDB at `chroma_data/` (cosine similarity)

At query time, the `support` agent retrieves the top-3 most relevant chunks
using semantic search and injects them as context into its LLM prompt.

---

## 9. Running Locally — Step by Step

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Redis 6+
- An OpenAI API key (for the AI assistant)

---

### Step 1 — Clone & Create Virtual Environment
```bash
git clone <your-repo-url>
cd banking-platform

python -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows
```

---

### Step 2 — Install Dependencies
```bash
pip install -r requirements.txt
```
> First run downloads `sentence-transformers/all-MiniLM-L6-v2` (~90 MB).
> Subsequent runs use the cached model.

---

### Step 3 — Configure Environment
```bash
cp .env.example .env
```

Edit `.env` and fill in:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/banking
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key-here

# SMTP (OTP emails)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your@gmail.com
SMTP_FROM_NAME=ADX Bank

# Frontend URL
FRONTEND_URL=http://localhost:3000

# OpenAI (AI assistant)
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
```

---

### Step 4 — Start PostgreSQL

**Option A — Docker (recommended for local dev):**
```bash
docker run -d \
  --name adx-postgres \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=banking \
  -p 5432:5432 \
  postgres:14
```

**Option B — Native PostgreSQL:**
```bash
# Create the database
createdb banking
```

---

### Step 5 — Run Database Migrations
```bash
alembic upgrade head
```
This creates all 17 tables in your PostgreSQL database.

---

### Step 6 — Start Redis

**Option A — Docker:**
```bash
docker run -d --name adx-redis -p 6379:6379 redis:alpine
```

**Option B — Native:**
```bash
redis-server
```

---

### Step 7 — Start Celery Worker
Open a **new terminal** (with the virtual env activated):
```bash
celery -A app.config.celery.celery_app worker --loglevel=info
```
> Required for: joining bonus credits, salary credits, loan auto-approval.

---

### Step 8 — Start the FastAPI Server
Open another **new terminal**:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On startup the server will:
- Load the sentence-transformers embedding model (15–30s first time)
- Drop and recreate ChromaDB collections
- Embed all bank rules + policy documents

> **Expected startup log:**
> ```
> INFO  Loading embedding model: sentence-transformers/all-MiniLM-L6-v2
> INFO  Embedding model loaded.
> INFO  Ingested N documents into collection 'bank_rules'.
> INFO  Ingested N documents into collection 'bank_policies'.
> INFO  Vector store ready: ['bank_rules', 'bank_policies']
> INFO  Application startup complete.
> ```

---

### Step 9 — (Optional) Start the Frontend
```bash
cd ../banking-frontend
npm install
npm run dev
```
Frontend runs at **http://localhost:3000**

---

### Access Points
| Service | URL |
|---|---|
| API server | http://localhost:8000 |
| Interactive API docs (Swagger) | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health check | http://localhost:8000/health |
| Frontend | http://localhost:3000 |

---

### Quick Test (with curl)
```bash
# Health check
curl http://localhost:8000/health

# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name":"Test User","email":"test@example.com","phone":"9999999999","password":"Test@1234","salary":50000}'

# (Check email for OTP, then:)
curl -X POST http://localhost:8000/api/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","otp":"<otp>"}'
```

---

### Running All Services Together (tmux / split terminals)

```
Terminal 1: PostgreSQL (or docker)
Terminal 2: Redis (or docker)
Terminal 3: celery -A app.config.celery.celery_app worker --loglevel=info
Terminal 4: uvicorn app.main:app --reload
Terminal 5: (optional) cd ../banking-frontend && npm run dev
```
