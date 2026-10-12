from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

class EvidenceItemSchema(BaseModel):
    source_type: str
    source_url: str
    page_title: Optional[str] = None
    evidence_snippet: str
    retrieved_at: Optional[datetime] = None

class CompanyLeadSchema(BaseModel):
    id: Optional[int] = None
    company_name: str
    website: str
    industry: str
    overview: str
    headquarters: str
    presence: Optional[str] = None
    approach_rationale: str
    hiring_information: Optional[str] = None
    contact_email: Optional[str] = None
    contact_name: Optional[str] = None
    contact_role: Optional[str] = None
    contact_source_url: Optional[str] = None
    is_verified: bool = True
    verification_status: str
    disqualification_reason: Optional[str] = None
    research_timestamp: Optional[datetime] = None
    evidence_items: List[EvidenceItemSchema] = []

class PersonalizedEmailDraft(BaseModel):
    id: Optional[int] = None
    lead_id: int
    company_name: str
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None
    subject: str
    body_text: str
    is_approved: bool = False
    creation_status: str = "pending_review"  # pending_review, created, failed, needs_contact
    gmail_draft_id: Optional[str] = None
    error_message: Optional[str] = None

class ScheduleConfigSchema(BaseModel):
    is_active: bool
    schedule_type: str = "daily"
    run_time: str = "09:00"
    timezone: str = "Asia/Kolkata"
    owner_email: str

class ScheduledRunSummary(BaseModel):
    id: int
    run_identifier: str
    trigger_type: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_researched: int
    total_verified: int
    total_rejected: int
    total_drafted: int
    report_sent: bool
    report_gmail_id: Optional[str] = None
    report_error: Optional[str] = None
    error_message: Optional[str] = None

class BatchApprovalRequest(BaseModel):
    run_id: int
    approved_draft_ids: Optional[List[int]] = None  # None means all valid drafts
