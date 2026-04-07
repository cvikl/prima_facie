# Prima Facie — AI Legal Intake System

AI-powered legal intake system for **Jadek & Pensa d.o.o.**, a Slovenian law firm. Transforms incoming client emails into structured legal tickets with automated classification, compliance assessment, and draft response generation.

## Project Goal

### The Problem

When a client email arrives at a law firm, a lawyer must manually:
1. Read and understand the inquiry
2. Classify which legal field it belongs to
3. Identify the right team members to handle it
4. Check for conflicts of interest against existing clients
5. Assess AML/KYC risk under Slovenian ZPPDFT-2 regulations
6. Research relevant legislation and past similar cases
7. Estimate costs
8. Draft a professional response

This process is time-consuming, error-prone (especially for compliance steps), and creates a bottleneck at intake — the very moment when responsiveness matters most to the client.

### The Solution

Prima Facie automates the entire intake pipeline. A client email enters the system (via Gmail/n8n webhook or direct API) and exits as a fully analyzed legal ticket containing:

- **Result A: Draft response email** — a professional, ready-to-review reply for the client, written in their language, referencing the firm's relevant experience and proposed team
- **Result B: Internal compliance dashboard** — a structured assessment including conflict of interest status, AML/KYC risk score with required documents, expense estimates, extracted deadlines, similar past cases, and applicable legal references

The lawyer's role shifts from manual triage to review and approval — they verify the AI's work rather than doing it from scratch.

### Key Constraints

The system is designed around the specific requirements of a Slovenian law firm:

- **Zero external data exposure** — all processing (LLM inference, embeddings, legal references) runs on the firm's own infrastructure. No client data is sent to third-party APIs. This is a hard requirement for attorney-client privilege.
- **Auditable compliance** — conflict detection and AML scoring are deterministic (rule-based, not LLM), producing reproducible results that can be explained in regulatory audits.
- **Slovenian legal framework** — prompts, legal fields, AML rules (ZPPDFT-2), rejection emails, and the embedded Mini-TFL legal database are all grounded in Slovenian and EU law.
- **Bilingual operation** — the system detects whether the client writes in Slovenian or English and responds in the same language.

### What It Is Not

- Not a case management system — it handles intake only (email → ticket). Case tracking, billing, and document management are out of scope.
- Not a legal advice engine — the LLM drafts responses and extracts information, but a lawyer must always review and approve before anything is sent.
- Not a general-purpose tool — it is purpose-built for Jadek & Pensa's 18 legal fields, 20 lawyers, and specific compliance requirements.

## Table of Contents

- [Project Goal](#project-goal)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Setup & Installation](#setup--installation)
- [Project Structure](#project-structure)
- [Pipeline: How an Email Becomes a Ticket](#pipeline-how-an-email-becomes-a-ticket)
  - [Step 1: Classification](#step-1-classification)
  - [Team Assignment](#team-assignment)
  - [Step 2: Deep Analysis](#step-2-deep-analysis)
  - [Compliance Checks](#compliance-checks)
  - [Similarity Search](#similarity-search)
  - [Legal References (Mini-TFL)](#legal-references-mini-tfl)
  - [Step 3: Draft Email Generation](#step-3-draft-email-generation)
- [API Reference](#api-reference)
  - [Email Ingestion](#email-ingestion)
  - [n8n Webhook Integration](#n8n-webhook-integration)
  - [Ticket Endpoints](#ticket-endpoints)
  - [User Endpoints](#user-endpoints)
- [Data Models](#data-models)
  - [Ticket](#ticket)
  - [User (Lawyer)](#user-lawyer)
  - [Customer](#customer)
- [Ticket Lifecycle](#ticket-lifecycle)
- [Compliance Engine](#compliance-engine)
  - [Conflict of Interest Detection](#conflict-of-interest-detection)
  - [AML/KYC Risk Scoring](#amlkyc-risk-scoring)
  - [Expense Estimation](#expense-estimation)
- [Legal Fields](#legal-fields)
- [Seed Data](#seed-data)
- [Configuration](#configuration)

---

## Architecture Overview

```
                          ┌─────────────────────────────────────────────────────┐
                          │              Prima Facie Orchestrator               │
                          │                                                     │
  Client Email ──────────►│  Step 1 (LLM)  →  DB Lookups  →  Step 2 (LLM)     │
  (via n8n or API)        │       │                                │            │
                          │       ▼                                ▼            │
                          │  Classification      Compliance Engine (rules)      │
                          │  + Team Assignment    ├─ Conflict Check             │
                          │                       ├─ AML Scoring (ZPPDFT-2)    │
                          │                       └─ Expense Estimation         │
                          │                                │                    │
                          │       ┌────────────────────────┘                    │
                          │       ▼                                             │
                          │  Vector DB (ChromaDB) → Similar Tickets             │
                          │  Mini-TFL             → Legal References            │
                          │       │                                             │
                          │       ▼                                             │
                          │  Step 3 (LLM)  →  Draft Email  →  Ticket Created   │
                          └─────────────────────────────────────────────────────┘
                                        │
                                        ▼
                               React SPA Dashboard
```

| Component | Technology | Location |
|-----------|-----------|----------|
| Orchestrator + API | FastAPI, SQLAlchemy, SQLite | This repo |
| LLM Server (GaMS-9B) | Self-hosted, remote | Set via `LLM_BASE_URL` env var |
| Vector Store | ChromaDB (persistent) + `paraphrase-multilingual-MiniLM-L12-v2` | `./chroma_data/` |
| Frontend | React 18 + Tailwind CSS (CDN) | `static/index.html` |
| Email Trigger | n8n Gmail webhook | External |

**Design principles:**
- **Local-first** — no client data leaves firm infrastructure. LLM, embeddings, and legal references all run on-premise.
- **Deterministic compliance** — conflict detection and AML scoring use rule-based logic (not LLM), ensuring auditability.
- **Multilingual** — detects client language (Slovenian/English) and responds in kind.

---

## Prerequisites

- Python 3.11+
- LLM server running (set `LLM_BASE_URL` environment variable, defaults to `http://localhost:8000`)

---

## Setup & Installation

```bash
# Clone and enter the repo
git clone <repo-url>
cd prima_facie

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app (auto-creates DB and seeds data on first run)
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

The dashboard is available at **http://localhost:8080**.

---

## Project Structure

```
prima_facie/
├── app/
│   ├── main.py              # FastAPI app — all API endpoints, static file serving
│   ├── database.py          # SQLite engine + session factory
│   ├── models.py            # SQLAlchemy models: Ticket, User, UserField, Customer
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── orchestrator.py      # 3-step LLM pipeline: classify → analyze → draft
│   ├── prompts.py           # System prompts for each LLM step (Slovenian)
│   ├── compliance.py        # AML scoring, conflict detection, expense estimation
│   ├── llm_client.py        # HTTP client for the remote GaMS-9B server
│   ├── vector_store.py      # ChromaDB wrapper for ticket similarity search
│   ├── legal_references.py  # Mini-TFL: embedded legal article/ruling database
│   └── seed.py              # Database initialization with lawyer and field data
├── static/
│   └── index.html           # Single-page React dashboard
├── prima_facie.db           # SQLite database (auto-created)
├── chroma_data/             # Persistent vector store (auto-created)
├── requirements.txt         # Python dependencies
└── README.md
```

---

## Pipeline: How an Email Becomes a Ticket

The full pipeline is orchestrated in `app/orchestrator.py:process_email()`. Each step is described below in execution order.

### Step 1: Classification

**LLM endpoint:** `POST /parse_intent` (temperature: 0.0)
**Prompt:** `STEP1_SYSTEM_PROMPT` in `app/prompts.py`

The email (with subject prepended as `Zadeva: {subject}`) is sent to GaMS-9B, which returns:

| Field | Type | Description |
|-------|------|-------------|
| `field` | `string` | One of 18 legal fields (exact Slovenian name) |
| `summary` | `string` | 3–5 sentence summary with legal terminology, in the email's language |
| `urgency` | `"high" \| "medium" \| "low"` | Based on deadlines, penalties, or time pressure |
| `deadlines` | `list[{description, hours_remaining}]` | Extracted deadlines (e.g., 72h GDPR notification) |
| `language` | `"sl" \| "en" \| "mixed"` | Language of the client's email |

### Team Assignment

After classification, the system queries the database for lawyers assigned to the detected `field`, ordered by:
1. **Priority** — primary specialists first (priority 0), then secondary (priority 1+)
2. **Workload** — lower workload preferred (scale: 1.0 = free, 3.0 = overloaded)

The top 3 candidates are selected as the proposed team.

### Step 2: Deep Analysis

**LLM endpoint:** `POST /parse_intent` (temperature: 0.0)
**Prompt:** `STEP2_SYSTEM_PROMPT` in `app/prompts.py`
**Input:** Original email + Step 1 classification results

Returns:

| Field | Type | Description |
|-------|------|-------------|
| `customer_name` | `string` | Client's full name |
| `customer_firm` | `string \| null` | Client's company name |
| `opposing_parties` | `list[string]` | All other parties mentioned (for conflict checks) |
| `aml_indicators` | `object` | 7 boolean flags for AML risk factors (see below) |
| `complexity` | `1 \| 2 \| 3` | Case complexity rating |
| `unanswered_questions` | `list[string]` | 4–5 specific questions the lawyer should ask the client |
| `key_facts` | `list[string]` | 3–7 key facts extracted from the email |

**AML indicator flags:**

| Indicator | Trigger |
|-----------|---------|
| `high_risk_jurisdiction` | Non-EU country, offshore jurisdictions (Cayman, BVI, Panama, UAE, etc.) |
| `complex_ownership` | Multi-layered or opaque ownership structures |
| `cash_intensive` | Cash deposits, payments, or large transactions without clear business reason |
| `pep_involved` | Politically exposed person or their family |
| `sanctioned_country` | Countries under EU/UN/OFAC sanctions (Russia, Iran, North Korea, Syria, Belarus) |
| `opaque_fund_source` | Unclear source of funds or explicit confidentiality requests |
| `novel_structure` | Unusual legal structure with no clear business purpose |

### Compliance Checks

All compliance checks are **deterministic** (no LLM). See [Compliance Engine](#compliance-engine) for full details.

Run between Step 2 and Step 3:
1. **Conflict of interest** — matches opposing parties against the customer database
2. **AML/KYC scoring** — calculates risk score from the 7 indicator flags
3. **Expense estimation** — estimates hours and cost based on complexity

### Similarity Search

**Module:** `app/vector_store.py`
**Embedding model:** `paraphrase-multilingual-MiniLM-L12-v2` (local, no API calls)
**Database:** ChromaDB with cosine similarity, persistent in `./chroma_data/`

The system builds a text representation of the ticket (field + summary + key facts) and queries for the 3 most similar past tickets. Results include:
- Ticket ID, summary, field
- Cosine similarity score
- Customer name/firm (enriched from DB)

Similar tickets are used in Step 3 to mention relevant firm experience and are displayed in the dashboard.

### Legal References (Mini-TFL)

**Module:** `app/legal_references.py`

A self-contained legal intelligence engine that replicates key features of the TFL (Tax-Fin-Lex) API without external calls:

1. **Citation extraction** — regex patterns match law citations in the raw email text (e.g., "33. člen GDPR")
2. **Article content** — embedded summaries of key articles from GDPR, ZVOP-2, ZDR-1, ZGD-1, ZPPDFT-2, OZ, ZJN-3, ZPOmK-2, ZTuj-2, and EU directives
3. **Court decisions** — landmark rulings indexed per legal field and keyword
4. **Keyword-to-article mapping** — maps extracted `key_facts` to specific law articles
5. **Cross-references** — inter-law links (e.g., GDPR ↔ ZVOP-2)

All data is internal — no client information leaves the system.

### Step 3: Draft Email Generation

**LLM endpoint:** `POST /summarize` (temperature: 0.3)
**Prompt:** Built dynamically by `build_step3_prompt()` in `app/prompts.py`

If a **conflict of interest** is detected, the system skips the LLM and generates a deterministic rejection email (in Slovenian or English, based on the detected language).

Otherwise, the LLM generates a professional response with this structure:

1. **Subject line** — e.g., "Re: Zaščita intelektualne lastnine — DeepAlgo d.o.o."
2. **Greeting** — formal, using client surname
3. **Introduction** — demonstrates understanding of the client's issue
4. **Firm experience & reference** — mentions similar past cases if available (from vector search)
5. **Proposed team** — introduces assigned lawyers by name and specialization
6. **Questions** — the unanswered questions from Step 2
7. **Next steps** — proposes a call or meeting with a specific timeframe
8. **Offer note** — states that a detailed cost proposal will follow within 2 business days
9. **Closing** — signed by the lead attorney, "Odvetniška pisarna Jadek & Pensa d.o.o."

---

## API Reference

### Email Ingestion

#### `POST /tickets/ingest`

Direct email ingestion. Runs the full pipeline synchronously and returns the completed ticket.

**Request body:**
```json
{
  "sender_email": "client@example.com",
  "subject": "Kršitev varstva osebnih podatkov",
  "body": "Spoštovani, v našem podjetju smo zaznali kršitev..."
}
```

**Response:** `TicketDetailOut` (see [Data Models](#data-models))

### n8n Webhook Integration

#### `POST /webhook/n8n` (async, recommended)

Returns immediately and processes the email in the background. Ideal for production use with n8n Gmail triggers.

**Request body:**
```json
{
  "name": "Janez Novak <janez@example.com>",
  "subject": "Email subject",
  "body": "Email content"
}
```

The `name` field is parsed to extract the email address (handles both `Name <email>` format and plain email).

**Response:**
```json
{
  "status": "queued",
  "message": "Email received and queued for processing",
  "sender_email": "janez@example.com",
  "subject": "Email subject"
}
```

#### `POST /webhook/n8n/sync`

Same input format as above, but waits for full pipeline completion. Returns `TicketDetailOut`. Useful for testing — may timeout for complex emails (LLM timeout is 300s).

#### `GET /webhook/n8n`

Info endpoint. Returns usage instructions and example payload.

### Ticket Endpoints

#### `GET /tickets`

List all tickets, ordered by creation date (newest first).

**Query parameters (all optional):**
| Parameter | Type | Example |
|-----------|------|---------|
| `status` | string | `NEW`, `BLOCKED`, `IN_REVIEW`, `APPROVED`, `SENT`, `CLOSED` |
| `field` | string | `VARSTVO OSEBNIH PODATKOV` |
| `urgency` | string | `high`, `medium`, `low` |

**Response:** `list[TicketListOut]`

#### `GET /tickets/{ticket_id}`

Get full ticket details including compliance data, draft email, similar tickets, legal references, and assigned team.

**Response:** `TicketDetailOut`

#### `PATCH /tickets/{ticket_id}`

Update ticket status, draft email, or reviewer.

**Request body (all fields optional):**
```json
{
  "status": "IN_REVIEW",
  "draft_email": "Updated draft text...",
  "reviewed_by": "SAJE"
}
```

**Business rules:**
- Cannot set status to `APPROVED` if `conflict_status` is `"conflict"` (returns 400)
- Setting status to `SENT` automatically records `sent_at` timestamp

#### `POST /tickets/{ticket_id}/send`

Mark a ticket as sent.

**Business rules:**
- Blocked if `conflict_status` is `"conflict"` (returns 400)
- Ticket must be `APPROVED` or `IN_REVIEW` (returns 400 otherwise)
- Records `sent_at` timestamp

### User Endpoints

#### `GET /users`

List all lawyers, ordered by name.

**Response:** `list[UserOut]` — each entry includes:
```json
{
  "id": 1,
  "acronym": "SAJE",
  "name": "Lawyer F",
  "workload": 2.0,
  "fields": ["INTELEKTUALNA LASTNINA", "KOMERCIALNE POGODBE", "KORPORACIJSKO PRAVO", "REGULACIJA S PODROČJA ZDRAVIL"]
}
```

---

## Data Models

### Ticket

The central entity. Stores all pipeline outputs.

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `status` | string | `NEW`, `BLOCKED`, `IN_REVIEW`, `APPROVED`, `SENT`, `CLOSED` |
| `raw_email` | text | Original email body |
| `sender_email` | string | Sender's email address |
| `language` | string | Detected language (`sl`, `en`, `mixed`) |
| **Classification (Step 1)** | | |
| `field` | string | Legal field (one of 18) |
| `summary` | text | LLM-generated summary |
| `urgency` | string | `low`, `medium`, `high` |
| `deadlines` | JSON | `[{"description": "...", "hours_remaining": 48}]` |
| **Analysis (Step 2)** | | |
| `customer_name` | string | Client's full name |
| `customer_firm` | string | Client's company (nullable) |
| `opposing_parties` | JSON | `["Company X", "Person Y"]` |
| `aml_indicators` | JSON | `{"high_risk_jurisdiction": false, ...}` (7 boolean flags) |
| `complexity` | int | 1 (simple), 2 (moderate), 3 (complex) |
| `unanswered_questions` | JSON | `["question1", "question2", ...]` |
| `key_facts` | JSON | `["fact1", "fact2", ...]` |
| **Compliance** | | |
| `conflict_status` | string | `none`, `warning`, `conflict` |
| `conflict_details` | text | Human-readable conflict explanation |
| `aml_risk` | string | `GREEN`, `ORANGE`, `RED` |
| `aml_score` | int | Numeric risk score (0–15+) |
| `aml_required_documents` | JSON | List of required KYC documents |
| **Expense Estimation** | | |
| `estimated_hours_min` | float | Minimum estimated hours |
| `estimated_hours_max` | float | Maximum estimated hours |
| `estimated_cost_min` | float | Minimum estimated cost (EUR) |
| `estimated_cost_max` | float | Maximum estimated cost (EUR) |
| **Output (Step 3)** | | |
| `draft_email` | text | Generated response email (or rejection email) |
| `similar_tickets` | JSON | `[{"id": 1, "summary": "...", "similarity": 0.85}]` |
| `legal_references` | JSON | Mini-TFL output (laws, articles, court decisions) |
| **Relations** | | |
| `customer_id` | FK → Customer | Linked customer record |
| `assigned_team` | M2M → User | Assigned lawyers (via `ticket_assigned_users`) |
| **Metadata** | | |
| `created_at` | datetime | Ticket creation timestamp (UTC) |
| `reviewed_by` | string | Reviewer's acronym |
| `sent_at` | datetime | When the email was sent (UTC) |

### User (Lawyer)

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `acronym` | string(4) | Unique identifier (e.g., `SAJE`) |
| `name` | string | Full name |
| `workload` | float | 1.0 = free, 2.0 = normal, 3.0 = overloaded |

Related via `UserField` (priority-ordered field assignments).

### Customer

| Column | Type | Description |
|--------|------|-------------|
| `id` | int | Primary key |
| `name` | string | Full name |
| `firm_name` | string | Company name (nullable) |
| `email` | string | Email address (nullable) |
| `created_at` | datetime | Record creation timestamp |

Customers are auto-created during email processing when a new client is detected. Used for conflict-of-interest checks.

---

## Ticket Lifecycle

```
          ┌──────────────────────────────────────────────────────────┐
          │                                                          │
  Email ──► NEW ──► IN_REVIEW ──► APPROVED ──► SENT ──► CLOSED     │
  Ingested  │                                                        │
            │   (if conflict detected)                               │
            └──► BLOCKED ─── resolve conflict ──► IN_REVIEW ──► ... │
                                                                     │
          └──────────────────────────────────────────────────────────┘
```

| Status | Meaning |
|--------|---------|
| `NEW` | Just processed, awaiting lawyer review |
| `BLOCKED` | Conflict of interest detected — cannot approve or send until resolved |
| `IN_REVIEW` | Lawyer is reviewing and editing the draft email |
| `APPROVED` | Draft approved, ready to send |
| `SENT` | Email sent to client (timestamp recorded) |
| `CLOSED` | Case completed |

---

## Compliance Engine

All compliance logic lives in `app/compliance.py`. It is entirely rule-based — no LLM involved.

### Conflict of Interest Detection

Two-level check (`check_conflicts()`):

**Level 1 — RED (conflict, ticket blocked):**
Opposing party name matches an existing customer in the database (exact or partial match with >3 character threshold to avoid trivial matches). The ticket is automatically set to `BLOCKED` and a rejection email is generated instead of a draft response.

**Level 2 — YELLOW (warning, flagged for review):**
The legal field is one of the 10 "critical industries" where representing multiple clients creates conflict risk, AND another client already exists in that field:

- Banking & Finance
- M&A
- Real Estate, Construction & Infrastructure
- Energy
- Public Procurement
- Competition Law
- Pharmaceutical Regulation
- Investment Funds
- Insolvency & Restructuring
- Technology, Media & Telecom

The ticket proceeds normally but is flagged with a warning and explanation.

### AML/KYC Risk Scoring

Based on Slovenian ZPPDFT-2 (Prevention of Money Laundering and Terrorist Financing Act).

**Scoring (`calculate_aml_score()`):**

| Indicator | Weight |
|-----------|--------|
| `sanctioned_country` | +5 |
| `high_risk_jurisdiction` | +3 |
| `complex_ownership` | +2 |
| `cash_intensive` | +2 |
| `pep_involved` | +2 |
| `opaque_fund_source` | +2 |
| `novel_structure` | +1 |

**Risk levels:**

| Score | Level | Color |
|-------|-------|-------|
| 0–2 | Low risk | GREEN |
| 3–5 | Medium risk | ORANGE |
| 6+ | High risk | RED |

**Required documents by risk level:**

| Level | Documents |
|-------|-----------|
| All | Personal ID, proof of address, UBO declaration |
| ORANGE + RED | Source of funds documentation, business purpose statement, company registration certificate |
| RED only | Enhanced Due Diligence (EDD), senior management approval, ongoing monitoring plan, EU/UN sanctions list check |

### Expense Estimation

`estimate_expenses()` uses complexity and a base hourly rate of **200 EUR**.

| Complexity | Hours Range | Cost Range (EUR) |
|------------|-------------|-------------------|
| 1 (simple) | 5–15 | 1,000–3,000 |
| 2 (moderate) | 15–40 | 3,000–8,000 |
| 3 (complex) | 40–100 | 8,000–20,000 |

---

## Legal Fields

The system classifies emails into exactly one of 18 legal fields:

| # | Field (Slovenian) | Domain |
|---|-------------------|--------|
| 1 | DELOVNO PRAVO | Labor law, employment disputes, terminations |
| 2 | BANČNIŠTVO IN FINANCE | Banking, financial instruments, credit agreements |
| 3 | DAVČNO PRAVO | Tax law, VAT, income tax |
| 4 | ENERGETIKA | Energy projects, renewables, energy regulation |
| 5 | TEHNOLOGIJA, MEDIJI IN ELEKTRONSKE KOMUNIKACIJE | IT contracts, telecoms, media law |
| 6 | INSOLVENČNO PRAVO IN PRESTRUKTURIRANJA | Bankruptcy, compulsory settlements, debt restructuring |
| 7 | INTELEKTUALNA LASTNINA | Patents, trademarks, copyrights, software IP |
| 8 | JAVNO NAROČANJE | Public procurement, tenders |
| 9 | KOMERCIALNE POGODBE | Commercial contracts, distribution, franchises |
| 10 | KONKURENČNO PRAVO | Antitrust, abuse of dominance, cartels |
| 11 | KORPORACIJSKO PRAVO | Company formation, corporate governance |
| 12 | MIGRACIJSKO PRAVO | Work permits, visas, residence permits |
| 13 | NALOŽBENI SKLADI | Investment funds, asset management |
| 14 | NEPREMIČNINE, GRADBENIŠTVO IN INFRASTRUKTURA | Real estate, construction permits, infrastructure |
| 15 | PREPREČEVANJE IN REŠEVANJE SPOROV | Arbitration, mediation, litigation, enforcement |
| 16 | PREVZEMI IN ZDRUŽITVE | M&A transactions, due diligence |
| 17 | REGULACIJA S PODROČJA ZDRAVIL | Pharmaceutical regulation, clinical trials |
| 18 | VARSTVO OSEBNIH PODATKOV | GDPR, data breaches, data processing |

---

## Seed Data

On first run (`app/seed.py`), the database is populated with:

**20 lawyers** with acronyms, anonymized names, and workload levels. Names are placeholders (`Lawyer A` through `Lawyer T`) — replace with real names in private deployment. Each lawyer has a workload rating (1.0 = free, 3.0 = overloaded).

**18 legal fields** with priority-ordered lawyer assignments (see `FIELD_ASSIGNMENTS` in `app/seed.py`).

**3 demo customers** for conflict-of-interest testing (anonymized):
- Acme Corp (`info@acme-example.com`)
- Jane Doe / FlowData d.o.o. (`jane@flowdata-example.com`)
- Target Company d.o.o. (`info@target-example.com`)

---

## Configuration

### LLM Server

Set the `LLM_BASE_URL` environment variable (defaults to `http://localhost:8000`). Timeout is configured in `app/llm_client.py`:

```bash
export LLM_BASE_URL="http://your-llm-server:8000"
```

```python
TIMEOUT = 300.0  # seconds
```

The LLM server exposes two endpoints consumed by this app:
- `POST /parse_intent` — JSON extraction (Steps 1 & 2, temp=0.0)
- `POST /summarize` — text generation (Step 3, temp=0.3)

Both accept `{"system_prompt": "...", "user_message": "..."}`.

### Database

SQLite, stored at `./prima_facie.db`. Configured in `app/database.py`:

```python
DATABASE_URL = "sqlite:///./prima_facie.db"
```

### Vector Store

ChromaDB with persistent storage at `./chroma_data/`. Embedding model is `paraphrase-multilingual-MiniLM-L12-v2` (downloaded automatically on first run). Configured in `app/vector_store.py`.

### Expense Rate

Base hourly rate is set in `app/compliance.py`:

```python
HOURLY_RATE = 200  # EUR
```
