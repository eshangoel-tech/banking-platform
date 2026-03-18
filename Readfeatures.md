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
Returns account balance, recent transactions count, active loans, and user profile basics.

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

**Limits:**
- Min: ₹1 | Max per transaction: ₹50,000
- Daily limit: ₹1,00,000 | Monthly limit: ₹5,00,000
- KYC PENDING accounts: monthly limit ₹10,000
- Zero fees

### Initiate Add Money (Step 1)
```
POST /api/v1/wallet/add-money/initiate
```
- Validates amount
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

**Key rules:**
- Interest rate: **12% p.a.** (fixed, reducing balance)
- Max loan: **salary × 12** (e.g. ₹50,000 salary → max ₹6,00,000)
- Min loan: **₹1,000**
- Allowed tenures: **6, 12, 18, 24, 36, 48 months** (only these values accepted)
- Processing fee: **1%** of principal (deducted at disbursement)
- Minimum salary for eligibility: ₹10,000/month
- EMI formula: `P × r × (1+r)^n / ((1+r)^n − 1)` where `r = 0.01` (monthly rate)

### Check Eligibility
```
GET /api/v1/loan/eligibility
```
Returns all loan constraints the UI needs to render the loan form.

**Sample response (salary ₹50,000):**
```json
{
  "success": true,
  "message": "Loan eligibility fetched.",
  "data": {
    "min_loan_amount": "1000",
    "max_eligible_amount": "600000.00",
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
Calculates EMI for a given principal + tenure. Saves a simulation record.

> `tenure_months` must be one of: **6, 12, 18, 24, 36, 48**

```json
{ "amount": 100000, "tenure_months": 12 }
```

**Sample response:**
```json
{
  "success": true,
  "message": "Loan simulation completed.",
  "data": {
    "amount": "100000",
    "tenure_months": 12,
    "interest_rate": "12.00",
    "emi_amount": "8884.88",
    "total_payable": "106618.56"
  }
}
```

---

### Book Loan (Step 1)
```
POST /api/v1/loan/book
```
- Validates eligibility
- Stores booking in Redis (TTL 5 minutes)
- Sends LOAN_BOOK OTP to email

> `tenure_months` must be one of: **6, 12, 18, 24, 36, 48**

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
- Deducts `min(emi_amount, outstanding_amount)` from account balance
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
Layer 2 — Domain agents (run in parallel via asyncio.gather)
     │  bank_manager  → account balance, transactions, account queries
     │  loan_officer  → loan eligibility, EMI, loan status
     │  accountant    → spending analysis, payment issues, financial summaries
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
| Account balance, summary, blocked account | bank_manager |
| Loan eligibility, EMI calculation, rejection | loan_officer |
| Payment failed, spending analysis, where did money go | accountant |
| Interest rates, OTP not received, policy questions | support |
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
2. **After 2 minutes:** Credits user's declared monthly salary → ledger entry → sends salary email

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
> Subsequent runs use the cached model.

---

### Step 3 — Configure Environment

Edit the `.env` file in the project root and fill in:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/banking
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your-secret-key-here

# SMTP (OTP emails) — Gmail example
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your-app-password       # Gmail App Password, not normal password
SMTP_FROM_EMAIL=your@gmail.com
SMTP_FROM_NAME=ADX Bank

# Frontend URL
FRONTEND_URL=http://localhost:3000

# AI Provider Priority — left = highest, auto-fallback to next on failure
AI_PROVIDER_PRIORITY=groq,openai,claude

# Groq — FREE (console.groq.com → API Keys)
GROQ_API_KEY=gsk_your-groq-api-key
GROQ_MODEL=llama3-70b-8192

# OpenAI — paid (platform.openai.com)
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini

# Anthropic / Claude — paid (console.anthropic.com)
ANTHROPIC_API_KEY=sk-ant-your-key
CLAUDE_MODEL=claude-haiku-4-5-20251001
```

> Gmail App Password: Google Account → Security → 2-Step Verification → App Passwords

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
echo "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000" > .env.local
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

# Verify email (check inbox for OTP, then:)
curl -X POST http://localhost:8000/api/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","otp":"<otp>"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"identifier":"test@example.com","password":"Test@1234"}'

# Verify login OTP (check inbox, then:)
curl -X POST http://localhost:8000/api/v1/auth/verify-login-otp \
  -H "Content-Type: application/json" \
  -d '{"identifier":"test@example.com","otp":"<otp>"}'
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
