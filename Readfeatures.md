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
  "salary": 50000
}
```
> `salary` is optional. Used for loan eligibility calculation.

---

### Verify Email
```
POST /api/v1/auth/verify-email
```
- Validates OTP
- Activates user (`status=ACTIVE`, `kyc_status=VERIFIED`)
- Creates a SAVINGS bank account automatically
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
- Verifies identifier + password
- Sends a 6-digit LOGIN OTP to registered email
- Blocks account for **1 hour** after 3 consecutive wrong passwords

**Request body:**
```json
{ "identifier": "arjun@example.com", "password": "SecurePass123" }
```
> `identifier` can be **email**, **phone number**, or **customer_id**.

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
{ "identifier": "arjun@example.com", "otp": "654321" }
```

**Response includes:**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "session_id": "<uuid>"
}
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

All endpoints require **`Authorization: Bearer <access_token>`** header.

### Dashboard Summary
```
GET /api/v1/dashboard/summary
```
Returns account balance, recent transactions, and user profile basics.

---

### Account Details
```
GET /api/v1/account/details
```
Full account info: account number, type (SAVINGS), balance, currency (INR), status.

---

### Transaction History
```
GET /api/v1/transactions?page=1&limit=10
```
Paginated ledger entries (max 50 per page). Each entry includes:
- `entry_type` (CREDIT / DEBIT)
- `amount`, `balance_after`
- `reference_type` (TRANSFER / WALLET_TOPUP / LOAN_PAYMENT / LOAN_DISBURSEMENT / SALARY_CREDIT / JOINING_BONUS)
- `description`, `created_at`

---

### Get Profile
```
GET /api/v1/user/profile
```
Returns current user profile — use this to pre-fill the Edit Profile form.

**Response:**
```json
{
  "full_name": "Arjun Sharma",
  "email": "arjun@example.com",
  "phone": "9876543210",
  "salary": "50000.00",
  "kyc_status": "VERIFIED",
  "address": { "city": "Delhi", "state": "Delhi", "line1": null, "postal_code": null }
}
```

---

### Update Profile
```
PUT /api/v1/user/profile
```
Update phone number and/or address. `address` is an **object**, not a string.

```json
{
  "phone": "9123456789",
  "address": { "city": "Mumbai", "state": "Maharashtra" }
}
```

`AddressSchema` fields: `line1`, `line2`, `city`, `state`, `postal_code`, `country` — all optional.

---

## 3. Transfer Module

Prefix: `/api/v1/transfer` | Requires JWT

**Limits:**
- Min: ₹1 | Max per transaction: ₹5,00,000 | Daily limit: ₹10,00,000
- Intra-bank only (both accounts must be ADX Bank accounts)
- Self-transfers not allowed | Zero fees | Instant 24x7

### Initiate Transfer (Step 1)
```
POST /api/v1/transfer/initiate
```
- Validates sender/receiver accounts
- Checks sufficient balance
- Stores transfer as PENDING
- Sends a TRANSFER OTP to sender's email (valid 5 minutes)

Identify receiver by **account number** OR **phone number** (not both):
```json
{ "to_account_number": "ADX0000012", "amount": 500.00, "description": "Rent" }
```
```json
{ "to_phone": "9876543210", "amount": 500.00, "description": "Rent" }
```

**Response includes** `transfer_id`, `receiver_name`, `receiver_account` (masked), `amount`.

---

### Confirm Transfer (Step 2)
```
POST /api/v1/transfer/confirm
```
- Verifies OTP
- Atomically debits sender and credits receiver
- Creates ledger entries for both accounts

```json
{ "transfer_id": "<uuid>", "otp": "112233" }
```

---

## 4. Wallet Module

Prefix: `/api/v1/wallet` | Requires JWT

**Limits:**
- Min: ₹1 | Max per transaction: ₹50,000
- Daily limit: ₹1,00,000 | Monthly limit: ₹5,00,000

### Initiate Add Money (Step 1)
```
POST /api/v1/wallet/add-money/initiate
```
- Validates amount
- Stores top-up in Redis (TTL 5 minutes)
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
```json
{ "topup_id": "<uuid>", "otp": "445566" }
```

---

## 5. Loan Module

Prefix: `/api/v1/loan` | Requires JWT

**Key rules:**
- Interest rate: **12% p.a.** (fixed, reducing balance)
- Max loan: **salary × 12** minus existing outstanding loans
- Min loan: **₹1,000**
- Allowed tenures: **6, 12, 18, 24, 36, 48 months**
- Minimum salary for eligibility: ₹10,000/month
- EMI formula: `P × r × (1+r)^n / ((1+r)^n − 1)` where `r = 0.01` (monthly rate)

### Check Eligibility
```
GET /api/v1/loan/eligibility
```
Returns all loan constraints. **Existing active/pending loans reduce the available limit.**

**Sample response (salary ₹50,000, ₹1.5L outstanding):**
```json
{
  "data": {
    "min_loan_amount": "1000.00",
    "max_eligible_amount": "600000.00",
    "existing_loan_outstanding": "150000.00",
    "available_loan_amount": "450000.00",
    "allowed_tenures": [6, 12, 18, 24, 36, 48],
    "interest_rate": "12.00",
    "processing_fee_percent": 1
  }
}
```

---

### Simulate Loan
```
POST /api/v1/loan/simulate
```
```json
{ "amount": 100000, "tenure_months": 12 }
```

**Response:**
```json
{
  "amount": "100000",
  "tenure_months": 12,
  "interest_rate": "12.00",
  "emi_amount": "8884.88",
  "total_payable": "106618.56"
}
```

---

### Book Loan (Step 1)
```
POST /api/v1/loan/book
```
- Validates eligibility (including existing outstanding)
- Stores booking in Redis (TTL 5 minutes)
- Sends LOAN_BOOK OTP

```json
{ "amount": 100000, "tenure_months": 12 }
```
Returns `booking_id`.

---

### Confirm Loan (Step 2)
```
POST /api/v1/loan/confirm
```
- Verifies OTP → creates Loan (PENDING) → Celery auto-approves → ACTIVE + principal credited to account

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

### Pay EMI — Initiate (Step 1)
```
POST /api/v1/loan/{loan_id}/pay/initiate
```
- Validates loan is ACTIVE and balance is sufficient
- Stores pay session in Redis (TTL 5 minutes)
- Sends LOAN_PAY OTP to email

**Response:**
```json
{
  "pay_id": "<uuid>",
  "emi_amount": "8884.88",
  "outstanding_amount": "91115.12"
}
```

---

### Pay EMI — Confirm (Step 2)
```
POST /api/v1/loan/{loan_id}/pay/confirm
```
- Verifies OTP
- Atomically debits account and updates outstanding
- Closes loan when outstanding reaches zero

```json
{ "pay_id": "<uuid>", "otp": "334455" }
```

**Response:**
```json
{
  "loan_id": "<uuid>",
  "amount_paid": "8884.88",
  "outstanding_after": "82230.24",
  "loan_status": "ACTIVE"
}
```

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
Layer 2 — Domain agents (run in parallel via asyncio.gather)
     │  bank_manager  → account balance, transactions, account queries
     │  loan_officer  → loan eligibility, EMI, loan status
     │  accountant    → spending analysis, payment issues, financial summaries
     │  support       → policy/rules questions + troubleshooting (RAG)
     ▼
Layer 3 — Receptionist
     │  Combines all responses into one natural reply.
     │  Sees full chat history — understands "yes" / "sure" redirect confirmations.
     ▼
Final response  +  redirect action buttons
```

**Dev terminal trace** — each chat message prints a live pipeline log:
```
──────────── USER MESSAGE ────────────
  loan band karana hai, kitne pese dene honge?

──── ROUTER  (312ms · 420in/85out) ────
  → [LOAN_OFFICER]  context: [loan_context, bank_rules]  actions: [PAY_EMI]

── AGENT: LOAN_OFFICER  (890ms · 1200in/180out) ──
  query   : loan close karna hai, charges kya hai
  response: Your outstanding amount is ₹82,230...

──── RECEPTIONIST  (640ms · 950in/120out) ────
  response: Namaste! To close your loan the remaining...
  actions : PAY_EMI

──────── PIPELINE DONE  total=1845ms ────
```

---

### Start Session
```
POST /api/v1/ai/assistant/start
```
- Creates a `chat_sessions` row (status=ACTIVE)
- Fetches user profile + last 10 chat turns from DB
- Caches context in Redis (TTL 1 hour)

**Response — now includes previous chat history for UI pre-population:**
```json
{
  "chat_sess_id": "<uuid>",
  "chat_history": [
    {
      "user_message": "What is my balance?",
      "assistant_response": "Your current balance is ₹12,500.",
      "created_at": "2026-03-18T10:30:00"
    }
  ]
}
```
> If `chat_history` is empty → show the default greeting. Otherwise pre-populate the chat UI.

---

### Chat
```
POST /api/v1/ai/assistant/chat
```

**Request body:**
```json
{
  "chat_sess_id": "<uuid>",
  "message": "What is my balance and can I afford a ₹1L loan?"
}
```

**Response:**
```json
{
  "response": "Your balance is ₹12,500. Based on your salary you're eligible for ₹4.8L. A ₹1L loan over 12 months is ₹8,885/month.",
  "actions": [
    { "name": "GET_LOAN", "label": "Apply for Loan", "url": "/loans" }
  ],
  "chat_sess_id": "<uuid>"
}
```

**Agent routing:**

| Question type | Agent |
|---|---|
| Account balance, summary, blocked account | bank_manager |
| Financial health overview, financial summary | bank_manager |
| Loan eligibility, EMI calculation, outstanding balance | loan_officer |
| Foreclosure / pay off loan now, foreclosure charges | loan_officer |
| Payment failed, spending analysis, transaction history | accountant |
| Interest rates, fees, OTP not received, policy questions | support |
| Foreclosure policy, prepayment rules, bank charges | support |
| Greetings, "yes" to redirect, unclear text | receptionist |

**Redirect actions:**

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

**Multi-provider AI fallback:**
The system tries providers left-to-right from `AI_PROVIDER_PRIORITY`. If Groq fails (quota/network), it falls back to OpenAI, then Claude. All providers share the same `call_llm()` interface.

**Agent behaviour notes:**
- All domain agents use the customer's data from context directly — they never ask for information they already have (salary, balance, outstanding, etc.)
- Foreclosure amount = `outstanding_amount` (reducing-balance amount owed today), not `EMI × remaining months`
- Support agent has key policy facts baked in (foreclosure = zero charge, fees, limits) so it answers correctly even when RAG retrieval returns no chunks

---

### Stop Session
```
POST /api/v1/ai/assistant/stop
```
```json
{ "chat_sess_id": "<uuid>" }
```

---

## 7. Background Tasks (Celery)

Celery workers process async tasks (broker + backend = Redis):

### Account On-boarding (triggered on email verification)
1. **Immediately:** Credits ₹500 joining bonus → ledger entry + audit log → sends welcome email
2. **After 2 minutes:** Credits user's declared monthly salary → ledger entry → sends salary email

### Loan Auto-Approval (triggered after loan confirmation)
- Moves loan `PENDING → ACTIVE`
- Credits principal amount to user's account
- Creates `LOAN_DISBURSEMENT` ledger entry
- Retries up to 3× with 10s backoff on failure

---

## 8. RAG Pipeline

On every server startup:

1. **Drops** existing ChromaDB collections (`bank_rules`, `bank_policies`)
2. **Parses** JSON from `app/config/bank_rules/` and `app/config/bank_policies/`
3. **Embeds** using `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
4. **Stores** in ChromaDB at `chroma_data/` (cosine similarity)

At query time, `support` agent retrieves top-3 chunks via semantic search.
`bank_policy_document` tool fetches top-6 for broad multi-section questions.

---

## 9. Running Locally — Step by Step

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Redis 6+
- At least one AI API key: **Groq** (free), OpenAI, or Anthropic/Claude

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

---

### Step 3 — Configure Environment

Edit `.env` in the project root:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/banking
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key-here

# SMTP (OTP emails) — Gmail example
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your@gmail.com
SMTP_FROM_NAME=ADX Bank

FRONTEND_URL=http://localhost:3000

# AI Provider Priority — left = highest, auto-fallback on failure
AI_PROVIDER_PRIORITY=groq,openai,claude

# Groq — FREE (console.groq.com)
GROQ_API_KEY=gsk_your-key
GROQ_MODEL=llama-3.3-70b-versatile

# OpenAI — paid (platform.openai.com)
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-4o-mini

# Anthropic / Claude — paid (console.anthropic.com)
ANTHROPIC_API_KEY=sk-ant-your-key
CLAUDE_MODEL=claude-haiku-4-5-20251001
```

---

### Step 4 — Start PostgreSQL

**Docker:**
```bash
docker run -d --name adx-postgres \
  -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=banking \
  -p 5432:5432 postgres:14
```

---

### Step 5 — Run Database Migrations
```bash
alembic upgrade head
```

---

### Step 6 — Start Redis
```bash
docker run -d --name adx-redis -p 6379:6379 redis:alpine
```

---

### Step 7 — Start Celery Worker
```bash
celery -A app.config.celery.celery_app worker --loglevel=info
```

---

### Step 8 — Start the FastAPI Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

### Step 9 — (Optional) Frontend
```bash
cd ../banking-frontend
npm install
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local
npm run dev
```

---

### Access Points

| Service | URL |
|---|---|
| API server | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Frontend | http://localhost:3000 |
