from datetime import datetime
from typing import List, Dict, Any

def generate_research_report_html(
    run_date: str,
    total_researched: int,
    total_verified: int,
    total_rejected: int,
    total_drafted: int,
    qualified_leads: List[Dict[str, Any]],
    rejected_leads: List[Dict[str, Any]],
    provider_used: str = "serpapi",
    is_test_mode: bool = False
) -> str:
    """
    Generates a high-quality, executive-ready HTML report for the founder/owner.
    Clearly shows test vs live mode, research provider, and per-company rationale.
    """
    mode_badge = (
        '<span style="background-color: #fef3c7; color: #92400e; padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase;">TEST MODE (Simulated)</span>'
        if is_test_mode else
        '<span style="background-color: #d1fae5; color: #065f46; padding: 4px 10px; border-radius: 9999px; font-size: 11px; font-weight: 700; text-transform: uppercase;">LIVE PRODUCTION</span>'
    )

    company_rows = ""
    for idx, lead in enumerate(qualified_leads, 1):
        draft_status = lead.get("draft_status", "Pending Approval")
        badge_color = "#10b981" if draft_status in ("Created", "Gmail Draft Created") else "#6366f1"

        sources_html = ""
        for ev in lead.get("evidence_items", []):
            sources_html += f"""
            <li style="margin-bottom: 4px;">
                <a href="{ev.get('source_url')}" target="_blank" style="color: #2563eb; text-decoration: none; font-weight: 500;">
                    {ev.get('page_title') or ev.get('source_url')}
                </a>
                <span style="color: #6b7280; font-size: 11px;">({ev.get('source_type')})</span>
                <div style="color: #4b5563; font-size: 12px; margin-top: 2px; font-style: italic;">
                    "{ev.get('evidence_snippet')}"
                </div>
            </li>
            """

        company_rows += f"""
        <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 18px; margin-bottom: 16px; background-color: #ffffff;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #f3f4f6; padding-bottom: 10px; margin-bottom: 12px;">
                <div>
                    <h3 style="margin: 0; color: #111827; font-size: 18px; font-weight: 600;">
                        {idx}. {lead.get('company_name')}
                    </h3>
                    <a href="{lead.get('website')}" target="_blank" style="color: #2563eb; font-size: 13px; text-decoration: none;">
                        {lead.get('website')}
                    </a>
                </div>
                <div style="text-align: right;">
                    <span style="background-color: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600;">
                        {lead.get('verification_status')}
                    </span>
                    <div style="margin-top: 6px;">
                        <span style="background-color: {badge_color}15; color: {badge_color}; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                            Draft: {draft_status}
                        </span>
                    </div>
                </div>
            </div>

            <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 12px;">
                <tr>
                    <td style="width: 18%; color: #6b7280; font-weight: 500; padding: 4px 0;">Industry:</td>
                    <td style="color: #1f2937; padding: 4px 0;">{lead.get('industry')}</td>
                </tr>
                <tr>
                    <td style="color: #6b7280; font-weight: 500; padding: 4px 0;">HQ & Presence:</td>
                    <td style="color: #1f2937; padding: 4px 0;"><strong>{lead.get('headquarters')}</strong> | {lead.get('presence') or 'Not verified'}</td>
                </tr>
                <tr>
                    <td style="color: #6b7280; font-weight: 500; padding: 4px 0;">Overview:</td>
                    <td style="color: #374151; padding: 4px 0;">{lead.get('overview')}</td>
                </tr>
                <tr>
                    <td style="color: #6b7280; font-weight: 500; padding: 4px 0; vertical-align: top;">StudentHub Fit:</td>
                    <td style="color: #047857; font-weight: 500; padding: 4px 0;">{lead.get('approach_rationale')}</td>
                </tr>
                <tr>
                    <td style="color: #6b7280; font-weight: 500; padding: 4px 0;">Hiring Activity:</td>
                    <td style="color: #1f2937; padding: 4px 0;">{lead.get('hiring_information') or 'Not found'}</td>
                </tr>
                <tr>
                    <td style="color: #6b7280; font-weight: 500; padding: 4px 0;">Public Contact:</td>
                    <td style="color: #1f2937; padding: 4px 0;">
                        {f"<strong>{lead.get('contact_email')}</strong> ({lead.get('contact_name', 'Talent Team')})" if lead.get('contact_email') else '<span style="color: #dc2626; font-style: italic;">Not found in public domain — flagged for manual review</span>'}
                    </td>
                </tr>
            </table>

            <div style="background-color: #f9fafb; border-radius: 6px; padding: 10px 14px; margin-top: 8px;">
                <strong style="font-size: 12px; color: #4b5563; text-transform: uppercase; letter-spacing: 0.05em;">Evidence & Authoritative Sources:</strong>
                <ul style="margin: 6px 0 0 0; padding-left: 20px; font-size: 12px;">
                    {sources_html or '<li style=\"color:#9ca3af;\">No sources attached</li>'}
                </ul>
            </div>
        </div>
        """

    rejected_section = ""
    if rejected_leads:
        rejected_rows = ""
        for rej in rejected_leads:
            rejected_rows += f"""
            <li style="margin-bottom: 6px; font-size: 13px;">
                <strong>{rej.get('company_name', 'Unknown')}</strong> ({rej.get('website', 'No URL')}): 
                <span style="color: #dc2626;">{rej.get('disqualification_reason')}</span>
            </li>
            """
        rejected_section = f"""
        <div style="margin-top: 24px; border: 1px solid #fee2e2; border-radius: 8px; padding: 16px; background-color: #fef2f2;">
            <h4 style="margin: 0 0 10px 0; color: #991b1b; font-size: 15px;">Disqualified or Excluded Candidates ({len(rejected_leads)})</h4>
            <p style="font-size: 12px; color: #7f1d1d; margin: 0 0 10px 0;">Candidates that did not meet strict qualification filters (job aggregators, invalid URLs, duplicates):</p>
            <ul style="margin: 0; padding-left: 20px; color: #374151;">
                {rejected_rows}
            </ul>
        </div>
        """

    shortfall_notice = ""
    if len(qualified_leads) < 10:
        shortfall_notice = f"""
        <div style="margin-bottom: 20px; background-color: #fffbeb; border: 1px solid #fef3c7; border-left: 4px solid #f59e0b; padding: 14px; border-radius: 6px;">
            <strong style="color: #92400e; font-size: 14px;">Shortfall Notice:</strong>
            <p style="margin: 4px 0 0 0; color: #78350f; font-size: 13px;">
                Only {len(qualified_leads)} companies met the strict verification criteria out of 10 targeted. 
                As per policy, results were not padded with unverified or speculative companies.
            </p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>StudentHub Company Research Report</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f3f4f6; margin: 0; padding: 24px; color: #111827;">
    <div style="max-width: 850px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); overflow: hidden; border: 1px solid #e5e7eb;">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: #ffffff; padding: 28px 32px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <div style="font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: #bfdbfe;">
                    StudentHub AI Outreach Agent
                </div>
                <div>{mode_badge}</div>
            </div>
            <h1 style="margin: 0; font-size: 24px; font-weight: 700; color: #ffffff;">
                Company Research & Partnership Report
            </h1>
            <div style="font-size: 13px; color: #dbeafe; margin-top: 6px;">
                Execution Date: {run_date} | Provider: <strong>{provider_used.upper()}</strong> | Prepared for: Suchithreddy G (CEO)
            </div>
        </div>

        <!-- Metric KPI Cards -->
        <div style="padding: 24px 32px; background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; display: flex; gap: 16px;">
            <div style="flex: 1; background: #ffffff; padding: 14px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                <div style="font-size: 12px; color: #64748b; font-weight: 500; text-transform: uppercase;">Researched</div>
                <div style="font-size: 22px; font-weight: 700; color: #0f172a; margin-top: 4px;">{total_researched}</div>
            </div>
            <div style="flex: 1; background: #ffffff; padding: 14px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                <div style="font-size: 12px; color: #64748b; font-weight: 500; text-transform: uppercase;">Qualified & Verified</div>
                <div style="font-size: 22px; font-weight: 700; color: #059669; margin-top: 4px;">{total_verified}</div>
            </div>
            <div style="flex: 1; background: #ffffff; padding: 14px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                <div style="font-size: 12px; color: #64748b; font-weight: 500; text-transform: uppercase;">Drafts Created</div>
                <div style="font-size: 22px; font-weight: 700; color: #2563eb; margin-top: 4px;">{total_drafted}</div>
            </div>
            <div style="flex: 1; background: #ffffff; padding: 14px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center;">
                <div style="font-size: 12px; color: #64748b; font-weight: 500; text-transform: uppercase;">Rejected</div>
                <div style="font-size: 22px; font-weight: 700; color: #dc2626; margin-top: 4px;">{total_rejected}</div>
            </div>
        </div>

        <!-- Body Content -->
        <div style="padding: 28px 32px;">
            {shortfall_notice}

            <h2 style="font-size: 18px; font-weight: 600; color: #1e293b; margin: 0 0 16px 0;">
                Verified Partner Candidates ({len(qualified_leads)})
            </h2>

            {company_rows if qualified_leads else '<p style=\"color:#6b7280;\">No companies met the qualification criteria in this run.</p>'}

            {rejected_section}

            <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8; text-align: center;">
                Automated by StudentHub AI Outreach Agent • Strict No-Hallucination Grounded Research Policy
            </div>
        </div>
    </div>
</body>
</html>
"""
    return html

def generate_research_report_text(
    run_date: str,
    total_researched: int,
    total_verified: int,
    total_rejected: int,
    total_drafted: int,
    qualified_leads: List[Dict[str, Any]],
    provider_used: str = "serpapi",
    is_test_mode: bool = False
) -> str:
    """Plain-text alternative for email clients."""
    lines = [
        f"STUDENTHUB COMPANY RESEARCH REPORT — {run_date}",
        f"Mode: {'TEST (Simulated)' if is_test_mode else 'LIVE'} | Provider: {provider_used.upper()}",
        "==================================================",
        f"Researched: {total_researched} | Verified: {total_verified} | Drafts: {total_drafted} | Rejected: {total_rejected}",
        "",
        "VERIFIED PARTNER CANDIDATES:",
        "----------------------------"
    ]
    for idx, lead in enumerate(qualified_leads, 1):
        lines.append(f"{idx}. {lead.get('company_name')} ({lead.get('website')})")
        lines.append(f"   Industry: {lead.get('industry')}")
        lines.append(f"   Headquarters: {lead.get('headquarters')}")
        lines.append(f"   StudentHub Fit: {lead.get('approach_rationale')}")
        lines.append(f"   Hiring Info: {lead.get('hiring_information')}")
        lines.append(f"   Contact: {lead.get('contact_email') or 'Not verified in public domain'}")
        lines.append(f"   Draft Status: {lead.get('draft_status', 'Pending')}")
        lines.append("")
    return "\n".join(lines)
