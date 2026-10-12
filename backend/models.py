from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from backend.config import settings

Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class ScheduleConfig(Base):
    __tablename__ = "schedule_config"

    id = Column(Integer, primary_key=True, index=True)
    is_active = Column(Boolean, default=False)
    schedule_type = Column(String, default="daily")  # "daily", "interval", "once"
    run_time = Column(String, default="09:00")       # "HH:MM"
    timezone = Column(String, default="Asia/Kolkata")
    owner_email = Column(String, default="suchith2435@gmail.com")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScheduledRun(Base):
    __tablename__ = "scheduled_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_identifier = Column(String, unique=True, index=True)  # idempotency key e.g. "manual-20261012-113000"
    trigger_type = Column(String, default="manual")           # "manual" or "scheduled"
    status = Column(String, default="running")               # "running", "completed", "failed", "shortfall"
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Provider & Mode Metadata
    provider_used = Column(String, default="serpapi")         # "serpapi", "tavily", "mock"
    is_test_mode = Column(Boolean, default=False)

    # Metrics
    total_researched = Column(Integer, default=0)
    total_verified = Column(Integer, default=0)
    total_rejected = Column(Integer, default=0)
    total_drafted = Column(Integer, default=0)
    
    # Research report status
    report_sent = Column(Boolean, default=False)
    report_gmail_id = Column(String, nullable=True)
    report_error = Column(Text, nullable=True)
    
    error_message = Column(Text, nullable=True)

    # Relationships
    leads = relationship("CompanyLead", back_populates="run", cascade="all, delete-orphan")

class CompanyLead(Base):
    __tablename__ = "company_leads"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("scheduled_runs.id"), index=True)
    
    # 1. Company details
    company_name = Column(String, index=True, nullable=False)
    website = Column(String, nullable=False)
    industry = Column(String, default="Technology / Engineering")
    overview = Column(Text, nullable=False)
    headquarters = Column(String, default="India")
    presence = Column(Text, nullable=True)              # Regional / office locations verified
    
    # 2. Strategic Fit & Hiring Opportunity (strictly factual evidence)
    approach_rationale = Column(Text, nullable=False)   # Why StudentHub should approach it
    hiring_information = Column(Text, nullable=True)    # Careers link, job openings, tech stacks
    
    # 3. Contact & Verification
    contact_email = Column(String, nullable=True)       # Sourced contact email (never fabricated)
    contact_name = Column(String, nullable=True)
    contact_role = Column(String, nullable=True)
    contact_source_url = Column(String, nullable=True)  # Where the contact was sourced
    
    is_verified = Column(Boolean, default=True)
    verification_status = Column(String, default="Officially Verified")  # "Officially Verified", "Third-Party Source", "Partially Verified", "Disqualified"
    disqualification_reason = Column(Text, nullable=True)
    research_timestamp = Column(DateTime, default=datetime.utcnow)

    # Relationships
    evidence_items = relationship("LeadEvidence", back_populates="lead", cascade="all, delete-orphan")
    draft = relationship("GmailDraft", back_populates="lead", uselist=False, cascade="all, delete-orphan")
    run = relationship("ScheduledRun", back_populates="leads")

class LeadEvidence(Base):
    __tablename__ = "lead_evidence"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("company_leads.id"), index=True)
    
    source_type = Column(String, default="official_website")  # "official_website", "careers_page", "news", "job_board"
    source_url = Column(String, nullable=False)
    page_title = Column(String, nullable=True)
    evidence_snippet = Column(Text, nullable=False)
    retrieved_at = Column(DateTime, default=datetime.utcnow)

    lead = relationship("CompanyLead", back_populates="evidence_items")

class GmailDraft(Base):
    __tablename__ = "gmail_drafts"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("company_leads.id"), index=True)
    
    # Idempotency uniqueness: lead_id per run
    recipient_email = Column(String, nullable=True)
    recipient_name = Column(String, nullable=True)
    subject = Column(String, nullable=False)
    body_text = Column(Text, nullable=False)
    
    # State tracking
    is_approved = Column(Boolean, default=False)
    creation_status = Column(String, default="pending_review")  # "pending_review", "created", "failed", "needs_contact", "simulated_test"
    gmail_draft_id = Column(String, nullable=True, unique=True)
    gmail_message_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    synced_at = Column(DateTime, nullable=True)

    lead = relationship("CompanyLead", back_populates="draft")

class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True)
    provider = Column(String, default="google", unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_uri = Column(String, default="https://oauth2.googleapis.com/token")
    client_id = Column(String, nullable=True)
    client_secret = Column(String, nullable=True)
    scopes = Column(Text, nullable=True)
    expiry = Column(DateTime, nullable=True)
    connected_email = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OAuthState(Base):
    __tablename__ = "oauth_states"

    state = Column(String, primary_key=True)
    code_verifier = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check and add columns if upgrading existing sqlite table
        import sqlite3
        if "sqlite" in settings.DATABASE_URL:
            conn = engine.raw_connection()
            cursor = conn.cursor()
            # check scheduled_runs columns
            cursor.execute("PRAGMA table_info(scheduled_runs)")
            cols = [col[1] for col in cursor.fetchall()]
            if "provider_used" not in cols:
                cursor.execute("ALTER TABLE scheduled_runs ADD COLUMN provider_used VARCHAR DEFAULT 'serpapi'")
            if "is_test_mode" not in cols:
                cursor.execute("ALTER TABLE scheduled_runs ADD COLUMN is_test_mode BOOLEAN DEFAULT 0")
            conn.commit()
            conn.close()

        cfg = db.query(ScheduleConfig).first()
        if not cfg:
            cfg = ScheduleConfig(
                is_active=False,
                schedule_type="daily",
                run_time="09:00",
                timezone="Asia/Kolkata",
                owner_email=settings.OWNER_EMAIL
            )
            db.add(cfg)
            db.commit()
    finally:
        db.close()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
