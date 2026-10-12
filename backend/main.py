import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.config import settings
from backend.models import (
    init_db, get_db, ScheduleConfig, ScheduledRun, CompanyLead, LeadEvidence, GmailDraft, OAuthToken
)
from backend.schemas import (
    ScheduleConfigSchema, BatchApprovalRequest, ScheduledRunSummary
)
from backend.workflow import workflow_manager
from backend.gmail_service import GmailService
from backend.report_generator import generate_research_report_html

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and tables
    init_db()
    # Start APScheduler for background job execution
    workflow_manager.start_scheduler()
    yield
    if workflow_manager.scheduler.running:
        workflow_manager.scheduler.shutdown()

app = FastAPI(
    title="StudentHub AI Outreach Agent",
    description="Minimal reliable outreach agent with grounded research, AI personalization, Gmail draft creation, and executive reports.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------
# Diagnostics & Health Check
# -----------------

@app.get("/api/health")
def get_diagnostics(db: Session = Depends(get_db)):
    """System health check and provider status."""
    search_diag = workflow_manager.search_client.check_health()
    gmail_status = workflow_manager.gmail_service.is_connected()
    db_ok = True
    try:
        db.execute("SELECT 1")
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "unhealthy",
        "database_connected": db_ok,
        "test_mode": settings.TEST_MODE,
        "search_provider": search_diag,
        "gmail": gmail_status,
        "huggingface_configured": bool(settings.HUGGINGFACE_API_KEY),
        "hf_model": settings.HF_MODEL_ID
    }

# -----------------
# Status & Settings
# -----------------

@app.get("/api/status")
def get_system_status(db: Session = Depends(get_db)):
    cfg = db.query(ScheduleConfig).first()
    latest_run = db.query(ScheduledRun).order_by(desc(ScheduledRun.id)).first()
    gmail_status = workflow_manager.gmail_service.is_connected()
    search_diag = workflow_manager.search_client.check_health()
    
    return {
        "status": "ready",
        "test_mode": settings.TEST_MODE,
        "search_provider": settings.SEARCH_PROVIDER,
        "search_status": search_diag.get("status"),
        "founder": {
            "name": settings.FOUNDER_NAME,
            "role": settings.FOUNDER_ROLE,
            "company": settings.FOUNDER_COMPANY,
            "owner_email": (cfg.owner_email if cfg else None) or settings.OWNER_EMAIL
        },
        "gmail": gmail_status,
        "is_job_running": workflow_manager._is_running,
        "schedule": {
            "is_active": cfg.is_active if cfg else False,
            "schedule_type": cfg.schedule_type if cfg else "daily",
            "run_time": cfg.run_time if cfg else "09:00",
            "timezone": cfg.timezone if cfg else "Asia/Kolkata",
            "owner_email": cfg.owner_email if cfg else settings.OWNER_EMAIL
        },
        "latest_run_id": latest_run.id if latest_run else None
    }

@app.post("/api/schedule")
def update_schedule(config: ScheduleConfigSchema, db: Session = Depends(get_db)):
    cfg = db.query(ScheduleConfig).first()
    if not cfg:
        cfg = ScheduleConfig()
        db.add(cfg)
    
    cfg.is_active = config.is_active
    cfg.schedule_type = config.schedule_type
    cfg.run_time = config.run_time
    cfg.timezone = config.timezone
    cfg.owner_email = config.owner_email
    db.commit()

    workflow_manager.sync_active_schedule()
    return {"message": "Schedule updated successfully.", "schedule": config}

# -----------------
# Google OAuth 2.0
# -----------------

@app.get("/api/auth/google/url")
def get_google_auth_url():
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        if settings.TEST_MODE:
            return {
                "auth_url": None,
                "message": "Running in TEST_MODE: Real Google OAuth is optional. Simulated draft mode is active."
            }
        raise HTTPException(status_code=400, detail="Google Client ID and Client Secret are not configured in .env.")
    
    try:
        flow = workflow_manager.gmail_service.get_authorization_url()
        return {"auth_url": flow}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate OAuth URL: {str(e)}")

@app.get("/api/auth/google/callback")
def google_auth_callback(code: Optional[str] = Query(None), error: Optional[str] = Query(None)):
    if error:
        return RedirectResponse(url=f"/?auth_error={error}")
    if not code:
        return RedirectResponse(url="/?auth_error=no_code_provided")

    try:
        workflow_manager.gmail_service.exchange_code_for_token(code)
        return RedirectResponse(url="/?auth_success=1")
    except Exception as e:
        return RedirectResponse(url=f"/?auth_error={str(e)}")

# -----------------
# Runs & Workflow
# -----------------

@app.post("/api/runs/execute")
async def trigger_run_now():
    if workflow_manager._is_running:
        raise HTTPException(status_code=409, detail="A research run is already in progress.")
    try:
        run = await workflow_manager.run_workflow(trigger_type="manual")
        return {
            "message": "Workflow completed successfully.",
            "run_id": run.id,
            "status": run.status,
            "verified_count": run.total_verified,
            "rejected_count": run.total_rejected,
            "provider_used": run.provider_used
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/runs")
def list_runs(db: Session = Depends(get_db)):
    runs = db.query(ScheduledRun).order_by(desc(ScheduledRun.id)).limit(20).all()
    results = []
    for r in runs:
        results.append({
            "id": r.id,
            "run_identifier": r.run_identifier,
            "trigger_type": r.trigger_type,
            "status": r.status,
            "started_at": r.started_at,
            "completed_at": r.completed_at,
            "provider_used": getattr(r, "provider_used", "serpapi"),
            "is_test_mode": getattr(r, "is_test_mode", False),
            "total_researched": r.total_researched,
            "total_verified": r.total_verified,
            "total_rejected": r.total_rejected,
            "total_drafted": r.total_drafted,
            "report_sent": r.report_sent,
            "report_gmail_id": r.report_gmail_id,
            "report_error": r.report_error,
            "error_message": r.error_message
        })
    return results

@app.get("/api/runs/{run_id}")
def get_run_details(run_id: int, db: Session = Depends(get_db)):
    run = db.query(ScheduledRun).filter(ScheduledRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    
    leads = []
    for lead in run.leads:
        evidence_list = [
            {
                "id": ev.id,
                "source_type": ev.source_type,
                "source_url": ev.source_url,
                "page_title": ev.page_title,
                "evidence_snippet": ev.evidence_snippet,
                "retrieved_at": ev.retrieved_at
            }
            for ev in lead.evidence_items
        ]
        
        draft_info = None
        if lead.draft:
            draft_info = {
                "id": lead.draft.id,
                "recipient_email": lead.draft.recipient_email,
                "recipient_name": lead.draft.recipient_name,
                "subject": lead.draft.subject,
                "body_text": lead.draft.body_text,
                "is_approved": lead.draft.is_approved,
                "creation_status": lead.draft.creation_status,
                "gmail_draft_id": lead.draft.gmail_draft_id,
                "error_message": lead.draft.error_message,
                "synced_at": lead.draft.synced_at
            }

        leads.append({
            "id": lead.id,
            "company_name": lead.company_name,
            "website": lead.website,
            "industry": lead.industry,
            "overview": lead.overview,
            "headquarters": lead.headquarters,
            "presence": lead.presence,
            "approach_rationale": lead.approach_rationale,
            "hiring_information": lead.hiring_information,
            "contact_email": lead.contact_email,
            "contact_name": lead.contact_name,
            "contact_role": lead.contact_role,
            "contact_source_url": lead.contact_source_url,
            "is_verified": lead.is_verified,
            "verification_status": lead.verification_status,
            "disqualification_reason": lead.disqualification_reason,
            "research_timestamp": lead.research_timestamp,
            "evidence_items": evidence_list,
            "draft": draft_info
        })

    return {
        "run": {
            "id": run.id,
            "run_identifier": run.run_identifier,
            "trigger_type": run.trigger_type,
            "status": run.status,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "provider_used": getattr(run, "provider_used", "serpapi"),
            "is_test_mode": getattr(run, "is_test_mode", False),
            "total_researched": run.total_researched,
            "total_verified": run.total_verified,
            "total_rejected": run.total_rejected,
            "total_drafted": run.total_drafted,
            "report_sent": run.report_sent,
            "report_gmail_id": run.report_gmail_id,
            "report_error": run.report_error,
            "error_message": run.error_message
        },
        "leads": leads
    }

# -----------------
# Draft Creation Approval
# -----------------

@app.post("/api/drafts/approve-batch")
async def approve_and_create_batch_drafts(payload: BatchApprovalRequest):
    """
    Explicit user approval to create genuine drafts in the connected Gmail account.
    """
    res = await workflow_manager.approve_and_create_drafts(payload.run_id, payload.approved_draft_ids)
    return res

# -----------------
# Research Report View
# -----------------

@app.get("/api/runs/{run_id}/report", response_class=HTMLResponse)
def view_run_report(run_id: int, db: Session = Depends(get_db)):
    run = db.query(ScheduledRun).filter(ScheduledRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    
    qualified_leads = []
    rejected_leads = []
    for lead in run.leads:
        evidence_items = [
            {
                "source_type": ev.source_type,
                "source_url": ev.source_url,
                "page_title": ev.page_title,
                "evidence_snippet": ev.evidence_snippet
            }
            for ev in lead.evidence_items
        ]
        if lead.is_verified:
            draft_status = lead.draft.creation_status.replace("_", " ").title() if lead.draft else "Pending"
            qualified_leads.append({
                "company_name": lead.company_name,
                "website": lead.website,
                "industry": lead.industry,
                "overview": lead.overview,
                "headquarters": lead.headquarters,
                "presence": lead.presence,
                "approach_rationale": lead.approach_rationale,
                "hiring_information": lead.hiring_information,
                "contact_email": lead.contact_email,
                "contact_name": lead.contact_name,
                "verification_status": lead.verification_status,
                "draft_status": draft_status,
                "evidence_items": evidence_items
            })
        else:
            rejected_leads.append({
                "company_name": lead.company_name,
                "website": lead.website,
                "disqualification_reason": lead.disqualification_reason or "Disqualified during review.",
                "evidence_items": evidence_items
            })

    html = generate_research_report_html(
        run_date=run.started_at.strftime("%B %d, %Y"),
        total_researched=run.total_researched,
        total_verified=run.total_verified,
        total_rejected=run.total_rejected,
        total_drafted=run.total_drafted,
        qualified_leads=qualified_leads,
        rejected_leads=rejected_leads,
        provider_used=getattr(run, "provider_used", "serpapi"),
        is_test_mode=getattr(run, "is_test_mode", False)
    )
    return html

# Mount static files directory if exists
static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
