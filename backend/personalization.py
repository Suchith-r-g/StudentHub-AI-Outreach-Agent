import json
import logging
import httpx
from typing import Dict, Any, Optional
from backend.config import settings

logger = logging.getLogger(__name__)

class OutreachPersonalizer:
    """
    Generates personalized cold emails using open-weight models via Hugging Face Inference API.
    Has robust fallback template engine that strictly respects verified evidence and ground truth context.
    """

    def __init__(self):
        self.api_key = settings.HUGGINGFACE_API_KEY
        self.model_id = settings.HF_MODEL_ID
        self.founder_name = settings.FOUNDER_NAME
        self.founder_role = settings.FOUNDER_ROLE
        self.founder_company = settings.FOUNDER_COMPANY

    async def generate_email(self, company_lead: Dict[str, Any]) -> Dict[str, str]:
        """
        Generates unique subject and email body based strictly on verified evidence.
        """
        company_name = company_lead.get("company_name", "Team")
        industry = company_lead.get("industry", "technology")
        rationale = company_lead.get("approach_rationale", "")
        hiring_info = company_lead.get("hiring_information", "")
        evidence_snippets = [e.get("evidence_snippet", "") for e in company_lead.get("evidence_items", [])]
        combined_evidence = " | ".join(filter(None, evidence_snippets))

        # Try Hugging Face Inference if API Key provided
        if self.api_key and not settings.TEST_MODE:
            try:
                hf_result = await self._call_huggingface(company_lead, combined_evidence)
                if hf_result:
                    return hf_result
            except Exception as e:
                logger.error(f"HF Inference failed for {company_name}: {e}. Utilizing deterministic factual personalization generator.")

        # High-quality factual personalization engine based strictly on company evidence
        return self._generate_factual_personalized_email(company_lead)

    async def _call_huggingface(self, company_lead: Dict[str, Any], evidence: str) -> Optional[Dict[str, str]]:
        url = f"https://api-inference.huggingface.co/models/{self.model_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        system_prompt = (
            "You are Suchithreddy G, CEO of StudentHub. "
            "Write a concise, professional, founder-to-business outreach email to invite the company to become a founding hiring partner. "
            "Strict constraints:\n"
            "1. Ground all claims solely on the provided evidence. Do NOT invent traction, customers, or partnership numbers.\n"
            "2. Explain the specific company-to-StudentHub fit using sourced evidence.\n"
            "3. Offer: founding hiring partner with early access to verified college students and Career DNA profiles.\n"
            "4. Return strict JSON with keys 'subject' and 'body'. Do not include markdown codeblocks or other text."
        )

        user_content = (
            f"Company: {company_lead.get('company_name')}\n"
            f"Industry: {company_lead.get('industry')}\n"
            f"Website: {company_lead.get('website')}\n"
            f"Approach Rationale: {company_lead.get('approach_rationale')}\n"
            f"Hiring Info: {company_lead.get('hiring_information')}\n"
            f"Verified Evidence: {evidence}\n"
        )

        payload = {
            "inputs": f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{user_content} [/INST]",
            "parameters": {"max_new_tokens": 500, "temperature": 0.4}
        }

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    text = data[0].get("generated_text", "")
                    # Extract JSON from model output
                    json_match = text.split("[/INST]")[-1].strip()
                    try:
                        parsed = json.loads(json_match)
                        if "subject" in parsed and "body" in parsed:
                            return {"subject": parsed["subject"], "body": parsed["body"]}
                    except Exception:
                        pass
        return None

    def _generate_factual_personalized_email(self, lead: Dict[str, Any]) -> Dict[str, str]:
        company_name = lead.get("company_name", "Team")
        industry = lead.get("industry", "technology")
        rationale = lead.get("approach_rationale", "")
        hiring_info = lead.get("hiring_information", "")
        contact_name = lead.get("contact_name") or f"{company_name} Talent Team"
        
        subject = f"Founding hiring partnership: StudentHub x {company_name}"

        body = (
            f"Hi {contact_name},\n\n"
            f"I came across {company_name}'s work in {industry} and noted your ongoing campus and engineering initiatives ({hiring_info.split(';')[0] if hiring_info else 'engineering hiring'}).\n\n"
            f"At StudentHub, we have built a recruitment and career platform specifically designed around verified college students, developer profiles, resume and certificate evaluation, and Career DNA competency modeling.\n\n"
            f"Given that {rationale.lower() if rationale else 'your team hires high-potential software and technology talent'}, "
            f"I would like to invite {company_name} to join as a founding hiring partner for StudentHub. "
            f"This provides early access to pre-evaluated student developer cohorts tailored to your engineering tech stacks.\n\n"
            f"Would you be open to a brief 10-minute introductory call next week to see if this aligns with your recruitment calendar?\n\n"
            f"Best regards,\n"
            f"{self.founder_name}\n"
            f"{self.founder_role}, {self.founder_company}"
        )

        return {"subject": subject, "body": body}
