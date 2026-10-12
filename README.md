# StudentHub AI Outreach Agent

A minimal, reliable, production-ready AI Outreach Agent that automates targeted company research, qualification, factual AI personalization, Google Gmail draft creation, and executive research report delivery.

---

## 🎯 Objective & Overview

At a user-configured scheduled time (or triggered on-demand via the interface):
1. **Researches exactly 10 legitimate Indian technology companies** matching StudentHub's partner profile (software engineering, digital engineering, IoT, HR-tech).
2. **Strictly validates web presence and hiring/partnership evidence** from authoritative public sources with timestamps and source URLs (zero hallucinations, zero fabricated contacts).
3. **Generates individually personalized outreach emails** using Hugging Face open-weight models (`meta-llama/Meta-Llama-3-8B-Instruct` or factual evidence fallback) signed by Suchithreddy G, CEO.
4. **Delivers an Executive Company Research Report via Gmail** to the owner email address (`suchithreddy@studenthub.co`) detailing company overviews, locations, rationale, hiring signals, and draft statuses.
5. **Awaits explicit user approval** to create 10 authentic, unsent drafts in the connected Gmail account via Google OAuth 2.0 (using the minimal `gmail.compose` permission).
6. **Guarantees idempotency**: Prevents duplicate runs, overlapping executions, and recreating existing drafts on retries.

---

## 🛠️ Architecture & Tech Stack

- **Backend**: FastAPI (Python 3.14 / 3.13)
- **Background Scheduler**: APScheduler (`AsyncIOScheduler`) with persistent database cron configuration and overlap prevention
- **Database**: SQLite with SQLAlchemy 2.0 ORM
- **Validation**: Pydantic v2
- **Search Provider**: Modular search interface supporting:
  - `mock`: Ground-truth reproducible dataset for test/evaluation mode
  - `tavily`: Real-time web search via Tavily API
  - `serpapi`: Google Search via SerpAPI
- **AI Personalization**: Hugging Face Inference Providers with open-weight models (`meta-llama/Meta-Llama-3-8B-Instruct`)
- **Email & Drafts**: Google Gmail API (`google-api-python-client`, `google-auth-oauthlib`)
- **Frontend**: Lightweight, responsive Vanilla CSS / JS dashboard with preview modal and batch approval controls

---

## 📁 Repository Structure

```
├── backend/
│   ├── config.py             # Application settings & environment loader
│   ├── models.py             # SQLAlchemy models (ScheduledRun, CompanyLead, LeadEvidence, GmailDraft, OAuthToken)
│   ├── schemas.py            # Pydantic schemas
│   ├── research.py           # Web search client & qualification engine (duplicate/evidence filters)
│   ├── personalization.py    # HF Inference client & factual email template engine
│   ├── gmail_service.py      # Google OAuth 2.0 & Gmail API draft creation / report delivery
│   ├── report_generator.py   # Executive HTML & plain-text research report generator
│   ├── workflow.py           # Single end-to-end workflow manager & APScheduler coordination
│   └── main.py               # FastAPI application & API endpoints
├── static/
│   ├── index.html            # Minimal management dashboard
│   ├── style.css             # Vanilla CSS styling & responsive layout
│   └── app.js                # Frontend state, API integration & modal logic
├── tests/
│   └── test_outreach.py      # Pytest suite covering qualification, deduplication, personalization, idempotency
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
└── README.md                 # Project documentation
```

---

## 🚀 Quickstart & Setup

### 1. Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- Git

### 2. Environment Setup
Clone the repository and create a virtual environment:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:

```powershell
copy .env.example .env
```

Review the settings in `.env`:
- `TEST_MODE=true`: **Recommended for initial evaluation**. Enables deterministic ground-truth candidate research and safe Gmail simulation without requiring external API keys.
- `SEARCH_PROVIDER=mock`: Set to `tavily` or `serpapi` if using live web search APIs.
- `HUGGINGFACE_API_KEY`: (Optional) Add your Hugging Face User Access Token for live model inference.
- `GOOGLE_CLIENT_ID` & `GOOGLE_CLIENT_SECRET`: Add for live Gmail OAuth 2.0 integration.

### 4. Run the Application
Start the FastAPI server:

```powershell
$env:PYTHONPATH="."
.\venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser to: **`http://localhost:8000`**

---

## 🔑 Google Cloud OAuth 2.0 Setup (For Live Gmail Drafts)

To connect a real Gmail account:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g., `StudentHub-Outreach`).
3. Enable the **Gmail API**:
   - Navigate to **APIs & Services > Library**.
   - Search for **Gmail API** and click **Enable**.
4. Configure the **OAuth Consent Screen**:
   - Select **External** (or Internal for Google Workspace).
   - Add App Name (`StudentHub Outreach Agent`) and User Support Email.
   - Under **Scopes**, add `https://www.googleapis.com/auth/gmail.compose`.
   - Under **Test Users**, add your Gmail account address.
5. Create OAuth 2.0 Credentials:
   - Navigate to **APIs & Services > Credentials > Create Credentials > OAuth Client ID**.
   - Select Application Type: **Web application**.
   - Add Authorized Redirect URI:
     ```
     http://localhost:8000/api/auth/google/callback
     ```
6. Copy your **Client ID** and **Client Secret** into your `.env` file:
   ```env
   GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your_client_secret_here
   ```
7. In the UI, click **Connect Gmail** to authorize.

---

## 🧪 Testing & Verification

Run the automated test suite with pytest:

```powershell
$env:PYTHONPATH="."
.\venv\Scripts\pytest -v tests/test_outreach.py
```

The test suite validates:
- **`test_qualification_rules`**: Filters invalid URLs, missing names, missing evidence, and unverified hiring claims.
- **`test_duplicate_prevention`**: Prevents intra-batch and cross-run duplicate companies.
- **`test_email_personalization_grounding`**: Ensures email copy is grounded strictly on sourced evidence and founder context.
- **`test_draft_creation_safety_and_idempotency`**: Enforces strict recipient validation, prevents fabricated emails, and checks retry safety.

---

## 📋 What Works & System State

| Feature | State | Notes |
| :--- | :--- | :--- |
| **Scheduler** | ✅ **Working** | APScheduler cron running in background; persistent DB settings; overlap protection. |
| **Research & Qualification** | ✅ **Working** | Real Indian tech firms (Kellton, Happiest Minds, Persistent, Sasken, Zensar, LatentView, Cyient, Birlasoft, Tata Elxsi, Darwinbox) with verified websites, evidence snippets, and careers pages. |
| **AI Personalization** | ✅ **Working** | Sourced evidence fit for StudentHub; supports Hugging Face Inference API with grounded fallback. |
| **Executive Research Report** | ✅ **Working** | Beautiful HTML executive email report sent to owner (`suchithreddy@studenthub.co`) and viewable via `/api/runs/{id}/report`. |
| **Gmail Drafts (Test Mode)** | ✅ **Working** | Simulated safe draft generation with unique IDs; zero outgoing emails. |
| **Gmail Drafts (Live Mode)** | 🔑 **Ready** | Full OAuth 2.0 flow implemented using minimal `gmail.compose` scope. Requires Google Cloud Client ID/Secret. |
| **Idempotency & Auditing** | ✅ **Working** | Retry-safe; duplicate runs prevented; draft creation tracking in SQLite. |
