import pytest
from backend.research import CompanyQualifier, WebSearchClient
from backend.personalization import OutreachPersonalizer
from backend.models import init_db, SessionLocal, ScheduledRun, CompanyLead, GmailDraft
from backend.workflow import OutreachWorkflowManager
from backend.gmail_service import GmailService
from backend.config import settings

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

def test_qualification_rules():
    qualifier = CompanyQualifier()
    
    # 1. Test missing name
    candidates = [{"company_name": "", "website": "https://example.com", "evidence_items": [{"evidence_snippet": "test"}]}]
    qualified, rejected = qualifier.qualify_candidates(candidates)
    assert len(qualified) == 0
    assert len(rejected) == 1
    assert "Missing company name" in rejected[0]["disqualification_reason"]

    # 2. Test missing evidence
    candidates = [{"company_name": "Test Co", "website": "https://test.com", "evidence_items": []}]
    qualified, rejected = qualifier.qualify_candidates(candidates)
    assert len(qualified) == 0
    assert "No supporting evidence" in rejected[0]["disqualification_reason"]

    # 3. Test invalid website
    candidates = [{
        "company_name": "Test Co",
        "website": "not-a-valid-url",
        "evidence_items": [{"source_type": "site", "source_url": "url", "evidence_snippet": "data"}],
        "approach_rationale": "Great fit"
    }]
    qualified, rejected = qualifier.qualify_candidates(candidates)
    assert len(qualified) == 0
    assert "Invalid or suspicious website" in rejected[0]["disqualification_reason"]

def test_job_board_filtering():
    qualifier = CompanyQualifier()
    candidates = [{
        "company_name": "LinkedIn Job Posting",
        "website": "https://in.linkedin.com/jobs/view/12345",
        "evidence_items": [{"source_type": "job_board", "source_url": "url", "evidence_snippet": "Software Engineer job"}],
        "approach_rationale": "Recruiting talent"
    }]
    qualified, rejected = qualifier.qualify_candidates(candidates)
    assert len(qualified) == 0
    assert len(rejected) == 1
    assert "Job aggregator/directory" in rejected[0]["disqualification_reason"]

def test_duplicate_prevention():
    qualifier = CompanyQualifier()
    existing_companies = ["Kellton Tech", "Persistent Systems"]

    candidates = [
        {
            "company_name": "kellton tech", # case-insensitive duplicate
            "website": "https://kellton.com",
            "evidence_items": [{"source_url": "url", "evidence_snippet": "data"}],
            "approach_rationale": "Fit"
        },
        {
            "company_name": "Happiest Minds",
            "website": "https://happiestminds.com",
            "evidence_items": [{"source_url": "url", "evidence_snippet": "data"}],
            "approach_rationale": "Fit"
        }
    ]
    qualified, rejected = qualifier.qualify_candidates(candidates, existing_companies)
    assert len(qualified) == 1
    assert qualified[0]["company_name"] == "Happiest Minds"
    assert len(rejected) == 1
    assert "already qualified in a previous run" in rejected[0]["disqualification_reason"]

def test_missing_optional_contact_does_not_reject():
    qualifier = CompanyQualifier()
    candidates = [{
        "company_name": "New Tech Ltd",
        "website": "https://newtech.com",
        "evidence_items": [{"source_type": "official_website", "source_url": "https://newtech.com", "evidence_snippet": "Digital platform"}],
        "approach_rationale": "Strong campus recruitment program for backend developers",
        "contact_email": None  # Optional field!
    }]
    qualified, rejected = qualifier.qualify_candidates(candidates)
    assert len(qualified) == 1
    assert qualified[0]["company_name"] == "New Tech Ltd"
    assert qualified[0]["contact_email"] is None

def test_email_personalization_grounding():
    personalizer = OutreachPersonalizer()
    lead = {
        "company_name": "Sasken Technologies",
        "industry": "IoT Embedded Systems",
        "approach_rationale": "Focus on embedded C/C++ fits verified student profiles",
        "hiring_information": "Recruiting GETs for embedded software",
        "contact_name": "Campus Hiring Desk",
        "evidence_items": [{"evidence_snippet": "Embedded systems leader"}]
    }
    email = personalizer._generate_factual_personalized_email(lead)
    assert "Sasken Technologies" in email["subject"]
    assert "Suchithreddy G" in email["body"]
    assert "StudentHub" in email["body"]
    assert "IoT Embedded Systems" in email["body"]
    assert "embedded c/c++" in email["body"].lower()

def test_draft_creation_safety_and_idempotency():
    gmail_service = GmailService()
    # Test rejection of missing/invalid recipient
    with pytest.raises(ValueError):
        gmail_service.create_draft(recipient_email="", subject="Sub", body_text="Body")

    with pytest.raises(ValueError):
        gmail_service.create_draft(recipient_email="invalid_address", subject="Sub", body_text="Body")

    # In test mode, creating draft returns simulated draft without network errors
    draft = gmail_service.create_draft(recipient_email="test@example.com", subject="Test", body_text="Body")
    assert "id" in draft
    assert draft.get("simulated") is True
    assert "simulated" in draft["id"]

def test_serpapi_health_check():
    client = WebSearchClient()
    health = client.check_health()
    assert "status" in health
    assert "provider" in health
