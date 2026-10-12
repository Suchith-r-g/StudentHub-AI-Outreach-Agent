import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone as pytz_timezone

from backend.config import settings
from backend.models import (
    SessionLocal, ScheduledRun, CompanyLead, LeadEvidence, GmailDraft, ScheduleConfig
)
from backend.research import WebSearchClient, CompanyQualifier
from backend.personalization import OutreachPersonalizer
from backend.gmail_service import GmailService
from backend.report_generator import generate_research_report_html, generate_research_report_text

logger = logging.getLogger(__name__)

class OutreachWorkflowManager:
    """
    Coordinates the single end-to-end workflow:
    1. Research & Evidence gathering (10 verified target companies)
    2. Qualification & strict ground-truth verification
    3. AI Personalization using open-weight model / grounded factual generation
    4. Gmail draft creation (upon approval or batch trigger)
    5. Owner Research Report email delivery
    6. Complete idempotency & retry safety
    """

    def __init__(self):
        self.search_client = WebSearchClient()
        self.qualifier = CompanyQualifier()
        self.personalizer = OutreachPersonalizer()
        self.gmail_service = GmailService()
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    def start_scheduler(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Outreach background scheduler started.")
            self.sync_active_schedule()

    def sync_active_schedule(self):
        """Syncs database schedule configuration into APScheduler."""
        db = SessionLocal()
        try:
            cfg = db.query(ScheduleConfig).first()
            job_id = "scheduled_studenthub_outreach_run"

            # Remove existing job if present
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)

            if cfg and cfg.is_active:
                tz = pytz_timezone(cfg.timezone or "Asia/Kolkata")
                parts = (cfg.run_time or "09:00").split(":")
                hour = int(parts[0]) if len(parts) > 0 else 9
                minute = int(parts[1]) if len(parts) > 1 else 0

                trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
                self.scheduler.add_job(
                    self.execute_scheduled_job,
                    trigger=trigger,
                    id=job_id,
                    replace_existing=True,
                    name="Daily StudentHub AI Outreach & Research Run"
                )
                logger.info(f"Registered scheduled job at {cfg.run_time} {cfg.timezone}")
            else:
                logger.info("Schedule is currently inactive.")
        except Exception as e:
            logger.error(f"Error syncing scheduler: {e}")
        finally:
            db.close()

    async def execute_scheduled_job(self):
        """Entry point for automated scheduler trigger."""
        run_identifier = f"sched-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        logger.info(f"Triggering scheduled run {run_identifier}")
        await self.run_workflow(trigger_type="scheduled", run_identifier=run_identifier)

    async def run_workflow(self, trigger_type: str = "manual", run_identifier: Optional[str] = None) -> ScheduledRun:
        """
        Executes the research & lead generation run idempotently.
        """
        if self._is_running:
            raise RuntimeError("An outreach research run is already in progress. Overlapping runs are prevented.")

        self._is_running = True
        if not run_identifier:
            run_identifier = f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        db = SessionLocal()
        try:
            # Idempotency check: Ensure unique run_identifier
            existing_run = db.query(ScheduledRun).filter(ScheduledRun.run_identifier == run_identifier).first()
            if existing_run:
                logger.warning(f"Run {run_identifier} already exists. Returning existing run.")
                return existing_run

            provider = settings.SEARCH_PROVIDER
            is_test = settings.TEST_MODE

            scheduled_run = ScheduledRun(
                run_identifier=run_identifier,
                trigger_type=trigger_type,
                status="running",
                started_at=datetime.now(timezone.utc),
                provider_used=provider,
                is_test_mode=is_test
            )
            db.add(scheduled_run)
            db.commit()
            db.refresh(scheduled_run)

            # Step 1: Research Candidate Companies
            # Compute cohort index based on total previous runs for search diversity
            total_prior_runs = db.query(ScheduledRun).count()
            
            # Fetch historically qualified domains and names
            if not is_test:
                existing_companies = [
                    row[0] for row in db.query(CompanyLead.company_name).filter(
                        CompanyLead.is_verified == True,
                        CompanyLead.run_id != scheduled_run.id
                    ).all() if row[0]
                ]
                existing_domains = [
                    row[0] for row in db.query(CompanyLead.normalized_domain).filter(
                        CompanyLead.is_verified == True,
                        CompanyLead.run_id != scheduled_run.id
                    ).all() if row[0]
                ]
            else:
                existing_companies = []
                existing_domains = []

            logger.info(
                f"Step 1: Searching for qualified partner companies using provider '{provider}' "
                f"(TEST_MODE={is_test}, cohort_index={total_prior_runs}, exclude_domains={len(existing_domains)})..."
            )
            raw_candidates = await self.search_client.search_studenthub_partners(
                target_count=15,
                cohort_index=total_prior_runs,
                exclude_domains=set(existing_domains)
            )
            scheduled_run.total_researched = len(raw_candidates)

            # Step 2: Qualification & Deduplication against existing database leads
            logger.info("Step 2: Qualifying candidates and checking evidence against historical records...")
            qualified, rejected = self.qualifier.qualify_candidates(
                candidates=raw_candidates,
                existing_company_names=existing_companies,
                existing_domains=existing_domains,
                allow_reconsideration=False
            )

            scheduled_run.total_verified = len(qualified)
            scheduled_run.total_rejected = len(rejected)

            # Step 3: Persist Qualified Leads and Generate AI Personalized Emails
            logger.info(f"Step 3: Persisting {len(qualified)} qualified leads and {len(rejected)} rejected candidates...")
            
            now_utc = datetime.now(timezone.utc)

            # Persist Qualified Leads
            for cand in qualified:
                norm_dom = cand.get("normalized_domain") or cand.get("website", "")
                lead = CompanyLead(
                    run_id=scheduled_run.id,
                    company_name=cand["company_name"],
                    normalized_domain=norm_dom,
                    website=cand["website"],
                    industry=cand.get("industry", "Technology"),
                    overview=cand.get("overview", ""),
                    headquarters=cand.get("headquarters", "India"),
                    presence=cand.get("presence"),
                    approach_rationale=cand.get("approach_rationale", ""),
                    hiring_information=cand.get("hiring_information"),
                    search_query=cand.get("search_query"),
                    contact_email=cand.get("contact_email"),
                    contact_name=cand.get("contact_name"),
                    contact_role=cand.get("contact_role"),
                    contact_source_url=cand.get("contact_source_url"),
                    is_verified=True,
                    verification_status=cand.get("verification_status", "Officially Verified"),
                    disqualification_reason=None,
                    research_timestamp=cand.get("research_timestamp", now_utc),
                    first_seen_at=now_utc,
                    last_seen_at=now_utc
                )
                db.add(lead)
                db.flush()

                # Save Evidence Items
                for ev in cand.get("evidence_items", []):
                    evidence_record = LeadEvidence(
                        lead_id=lead.id,
                        source_type=ev.get("source_type", "official_website"),
                        source_url=ev.get("source_url", cand["website"]),
                        page_title=ev.get("page_title"),
                        evidence_snippet=ev.get("evidence_snippet", ""),
                        retrieved_at=now_utc
                    )
                    db.add(evidence_record)

                # Generate AI Personalized Draft Content
                email_content = await self.personalizer.generate_email(cand)
                
                # Check recipient validity: flag for review if contact email is missing
                creation_status = "pending_review" if cand.get("contact_email") else "needs_contact"

                draft_record = GmailDraft(
                    lead_id=lead.id,
                    recipient_email=cand.get("contact_email"),
                    recipient_name=cand.get("contact_name"),
                    subject=email_content["subject"],
                    body_text=email_content["body"],
                    is_approved=False,
                    creation_status=creation_status
                )
                db.add(draft_record)

            # Persist Rejected Leads (for transparency, audit history, and deduplication)
            for rej in rejected:
                rej_lead = CompanyLead(
                    run_id=scheduled_run.id,
                    company_name=rej.get("company_name", "Unknown"),
                    normalized_domain=rej.get("normalized_domain"),
                    website=rej.get("website", ""),
                    industry=rej.get("industry", "Technology"),
                    overview=rej.get("overview", "Disqualified during qualification review."),
                    headquarters=rej.get("headquarters", "India"),
                    presence=rej.get("presence"),
                    approach_rationale=rej.get("approach_rationale", "N/A"),
                    hiring_information=rej.get("hiring_information"),
                    search_query=rej.get("search_query"),
                    contact_email=rej.get("contact_email"),
                    is_verified=False,
                    verification_status="Disqualified",
                    disqualification_reason=rej.get("disqualification_reason", "Failed qualification criteria."),
                    research_timestamp=now_utc,
                    first_seen_at=now_utc,
                    last_seen_at=now_utc
                )
                db.add(rej_lead)
                db.flush()
                for ev in rej.get("evidence_items", []):
                    evidence_record = LeadEvidence(
                        lead_id=rej_lead.id,
                        source_type=ev.get("source_type", "source_url"),
                        source_url=ev.get("source_url", rej.get("website", "")),
                        page_title=ev.get("page_title"),
                        evidence_snippet=ev.get("evidence_snippet", ""),
                        retrieved_at=now_utc
                    )
                    db.add(evidence_record)

            db.commit()

            # Step 4: Dispatch Owner Company Research Report via Gmail
            await self._dispatch_research_report(db, scheduled_run, qualified, rejected)

            scheduled_run.status = "completed" if len(qualified) >= 10 else "shortfall"
            scheduled_run.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(scheduled_run)

            return scheduled_run

        except Exception as e:
            logger.exception(f"Outreach workflow run failed: {e}")
            if 'scheduled_run' in locals() and scheduled_run:
                scheduled_run.status = "failed"
                scheduled_run.error_message = str(e)
                scheduled_run.completed_at = datetime.now(timezone.utc)
                db.commit()
            raise e
        finally:
            self._is_running = False
            db.close()

    async def approve_and_create_drafts(self, run_id: int, draft_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Explicit User Approval Step: Creates real unsent drafts in the connected Gmail account.
        Checks for existing drafts to ensure idempotency.
        """
        db = SessionLocal()
        created_count = 0
        failed_count = 0
        results = []

        try:
            query = db.query(GmailDraft).join(CompanyLead).filter(
                CompanyLead.run_id == run_id,
                CompanyLead.is_verified == True
            )
            if draft_ids:
                query = query.filter(GmailDraft.id.in_(draft_ids))

            drafts = query.all()
            for draft in drafts:
                # Idempotency check: do not recreate if already created
                if draft.creation_status in ("created", "simulated_test") and draft.gmail_draft_id:
                    results.append({
                        "id": draft.id,
                        "company": draft.lead.company_name,
                        "status": "already_created",
                        "gmail_draft_id": draft.gmail_draft_id
                    })
                    continue

                if not draft.recipient_email:
                    draft.creation_status = "needs_contact"
                    draft.error_message = "No verified business email address found. Flagged for manual review."
                    failed_count += 1
                    results.append({
                        "id": draft.id,
                        "company": draft.lead.company_name,
                        "status": "failed",
                        "reason": draft.error_message
                    })
                    continue

                try:
                    gmail_resp = self.gmail_service.create_draft(
                        recipient_email=draft.recipient_email,
                        subject=draft.subject,
                        body_text=draft.body_text
                    )
                    draft.gmail_draft_id = gmail_resp.get("id")
                    draft.gmail_message_id = gmail_resp.get("message", {}).get("id")
                    draft.connected_account = gmail_resp.get("connected_account")
                    draft.is_approved = True
                    draft.creation_status = "created" if not gmail_resp.get("simulated") else "simulated_test"
                    draft.error_message = None
                    draft.synced_at = datetime.now(timezone.utc)
                    created_count += 1
                    results.append({
                        "id": draft.id,
                        "company": draft.lead.company_name,
                        "status": "created",
                        "gmail_draft_id": draft.gmail_draft_id,
                        "connected_account": draft.connected_account,
                        "simulated": bool(gmail_resp.get("simulated"))
                    })
                except Exception as e:
                    logger.error(f"Failed to create draft for {draft.lead.company_name}: {e}")
                    draft.creation_status = "failed"
                    draft.error_message = str(e)
                    failed_count += 1
                    results.append({
                        "id": draft.id,
                        "company": draft.lead.company_name,
                        "status": "failed",
                        "reason": str(e)
                    })

            # Update ScheduledRun metric
            run = db.query(ScheduledRun).filter(ScheduledRun.id == run_id).first()
            if run:
                run.total_drafted = db.query(GmailDraft).join(CompanyLead).filter(
                    CompanyLead.run_id == run_id,
                    GmailDraft.creation_status.in_(["created", "simulated_test"])
                ).count()

            db.commit()
            return {
                "run_id": run_id,
                "total_processed": len(drafts),
                "created_count": created_count,
                "failed_count": failed_count,
                "results": results
            }
        finally:
            db.close()

    async def _dispatch_research_report(self, db, run: ScheduledRun, qualified: List[Dict[str, Any]], rejected: List[Dict[str, Any]]):
        """Dispatches the executive research report to the owner email."""
        cfg = db.query(ScheduleConfig).first()
        owner_email = (cfg.owner_email if cfg else None) or settings.OWNER_EMAIL
        run_date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        subject = f"StudentHub Company Research Report — {run_date_str}"

        # Fetch lead draft statuses
        leads_with_draft_info = []
        for q in qualified:
            lead_record = db.query(CompanyLead).filter(
                CompanyLead.run_id == run.id,
                CompanyLead.company_name == q["company_name"]
            ).first()
            draft_status = "Pending Review"
            if lead_record and lead_record.draft:
                draft_status = lead_record.draft.creation_status.replace("_", " ").title()
            
            lead_dict = dict(q)
            lead_dict["draft_status"] = draft_status
            leads_with_draft_info.append(lead_dict)

        html_body = generate_research_report_html(
            run_date=run_date_str,
            total_researched=run.total_researched,
            total_verified=run.total_verified,
            total_rejected=run.total_rejected,
            total_drafted=run.total_drafted,
            qualified_leads=leads_with_draft_info,
            rejected_leads=rejected,
            provider_used=run.provider_used or settings.SEARCH_PROVIDER,
            is_test_mode=run.is_test_mode
        )
        text_body = generate_research_report_text(
            run_date=run_date_str,
            total_researched=run.total_researched,
            total_verified=run.total_verified,
            total_rejected=run.total_rejected,
            total_drafted=run.total_drafted,
            qualified_leads=leads_with_draft_info,
            provider_used=run.provider_used or settings.SEARCH_PROVIDER,
            is_test_mode=run.is_test_mode
        )

        try:
            logger.info(f"Sending Research Report to owner: {owner_email}")
            res = self.gmail_service.send_research_report(
                to_email=owner_email,
                subject=subject,
                html_content=html_body,
                text_content=text_body
            )
            run.report_sent = True
            run.report_gmail_id = res.get("id")
            run.report_error = None
        except Exception as e:
            logger.warning(f"Failed to deliver research report to {owner_email}: {e}")
            run.report_sent = False
            run.report_error = str(e)

workflow_manager = OutreachWorkflowManager()
