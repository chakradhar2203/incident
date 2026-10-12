# RCA Assistant – AI Incident Triage & Root Cause Analysis

A Python/FastAPI application that helps IT operations teams investigate incidents faster using Claude AI and Firebase for knowledge storage.

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure
```bash
copy .env.example .env
# Edit .env with your credentials
```

### 3. Run
```bash
python run.py
```

Open **http://localhost:8000** in your browser.

---

## Project Structure

```
RCA-Assistant/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings (pydantic-settings)
│   ├── models.py            # Pydantic data models
│   ├── rca_engine.py        # Local + AI-assisted RCA analysis
│   ├── knowledge_base.py    # Firebase Firestore KB (with in-memory fallback)
│   ├── servicenow.py        # ServiceNow REST API client
│   ├── scheduler.py         # Background recurring incident scheduler
│   ├── incident_generator.py# Synthetic incident templates
│   ├── routers/
│   │   ├── config.py        # GET/POST /api/config
│   │   ├── incidents.py     # /api/incidents
│   │   ├── knowledge.py     # /api/knowledge
│   │   ├── servicenow.py    # /api/servicenow
│   │   ├── scheduler.py     # /api/scheduler
│   │   └── copilot.py       # /api/copilot
│   └── static/
│       ├── index.html       # Dashboard UI
│       ├── styles.css       # Dark-theme CSS
│       └── app.js           # Dashboard JavaScript
├── servicenow/
│   ├── ui_action_run_rca.js   # SN button: Run RCA Analysis
│   └── ui_action_write_rca.js # SN button: Write RCA Notes
├── requirements.txt
├── .env.example
├── run.py
└── README.md
```

---

## Configuration

All settings can be provided via `.env` or through the Settings tab in the dashboard.

| Variable | Description |
|----------|-------------|
| `SERVICENOW_INSTANCE_URL` | Your SN instance URL |
| `SERVICENOW_USERNAME` | Integration user |
| `SERVICENOW_PASSWORD` | Password or token |
| `SERVICENOW_WRITEBACK_ENABLED` | `false` by default |
| `CLAUDE_API_KEY` | Anthropic Claude API key |
| `CLAUDE_MODEL` | Default: `claude-3-5-sonnet-20241022` |
| `FIREBASE_SERVICE_ACCOUNT_PATH` | Path to Firebase JSON key |
| `FIREBASE_PROJECT_ID` | Your Firebase project ID |
| `ANALYSIS_MODE` | `local` or `ai` |

---

## Analysis Modes

### Local Mode (default)
- No external AI required
- Uses keyword/pattern matching on logs
- Compares with bundled historical cases
- Works offline

### AI-Assisted Mode
- Requires `CLAUDE_API_KEY`
- Uses Claude to generate grounded RCA from evidence + KB cases
- Output is still based on incident evidence (not hallucinated)

---

## Firebase Setup

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create a project → Enable Firestore
3. Project Settings → Service Accounts → Generate New Private Key
4. Save the JSON file as `firebase-service-account.json` in the project root
5. Set `FIREBASE_SERVICE_ACCOUNT_PATH=firebase-service-account.json`

**Without Firebase**: The app uses an in-memory knowledge base with 8 seed cases.

---

## ServiceNow Integration

### API Integration
Set your ServiceNow credentials in Settings. The app can:
- Fetch incidents via the Table API
- Write RCA results to work notes
- Mark incidents as In Progress

### UI Action Buttons (PDI)
Install buttons directly on the incident form — see [ServiceNow Setup Guide](servicenow/SERVICENOW_SETUP.md).

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/config` | Get current config (sanitised) |
| `POST` | `/api/config` | Update runtime config |
| `POST` | `/api/incidents/analyze` | Analyze an incident |
| `GET` | `/api/incidents` | List all analyzed incidents |
| `GET` | `/api/incidents/{number}` | Get a stored RCA result |
| `POST` | `/api/incidents/feedback` | Submit verified resolution |
| `POST` | `/api/incidents/generate` | Generate & analyze a demo incident |
| `GET` | `/api/knowledge` | List KB cases |
| `GET` | `/api/knowledge/stats` | KB statistics |
| `POST` | `/api/knowledge` | Add a KB case |
| `GET` | `/api/servicenow/test` | Test SN connection |
| `GET` | `/api/servicenow/{number}` | Fetch & analyze SN incident |
| `POST` | `/api/servicenow/{number}/writeback` | Write RCA to SN incident |
| `POST` | `/api/scheduler/start` | Start recurring scheduler |
| `POST` | `/api/scheduler/stop` | Stop scheduler |
| `GET` | `/api/scheduler/status` | Scheduler status |
| `POST` | `/api/copilot/ask` | Ask a question about an incident |
| `GET` | `/health` | Health check |

Full interactive docs: **http://localhost:8000/docs**

---

## Safety & Security

- Write-back is **disabled by default**
- Credentials are never returned in API responses
- All credentials are memory-only when set via dashboard
- AI-generated results are clearly marked as requiring engineer review
- Potentially destructive commands are flagged with `requires_approval: true`
- Commands are suggested only — never auto-executed

---

## ServiceNow Custom Fields

The app reads two optional custom fields from ServiceNow incidents:
- `u_application_logs` — application/infrastructure logs
- `u_recent_changes` — recent system changes

Create these fields in your ServiceNow PDI for best results.

