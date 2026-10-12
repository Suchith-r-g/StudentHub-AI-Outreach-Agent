// StudentHub AI Outreach Agent Frontend Logic

let currentRunId = null;
let currentRunData = null;
let activeModalLead = null;

document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    setupEventListeners();
    await fetchStatus();
    await fetchRunsHistory();
}

function setupEventListeners() {
    // Schedule Save
    document.getElementById("btn-save-schedule").addEventListener("click", saveSchedule);
    document.getElementById("schedule-active").addEventListener("change", (e) => {
        document.getElementById("schedule-status-label").innerText = e.target.checked ? "Schedule Active" : "Schedule Inactive";
    });

    // Run Now Button
    document.getElementById("btn-run-now").addEventListener("click", executeRunNow);

    // Batch Draft Approval
    document.getElementById("btn-approve-batch").addEventListener("click", approveBatchDrafts);

    // Google Connect
    document.getElementById("btn-connect-gmail").addEventListener("click", handleConnectGmail);

    // Test Draft Action
    document.getElementById("btn-test-draft").addEventListener("click", handleCreateTestDraft);

    // Modal Close
    document.getElementById("modal-close-btn").addEventListener("click", closeModal);
    document.getElementById("modal-close-backdrop").addEventListener("click", closeModal);
    document.getElementById("modal-btn-cancel").addEventListener("click", closeModal);
    document.getElementById("modal-btn-approve-single").addEventListener("click", approveSingleDraft);
}

// ---------------------------
// API Interactions
// ---------------------------

async function handleCreateTestDraft() {
    const btn = document.getElementById("btn-test-draft");
    btn.disabled = true;
    btn.innerText = "Creating...";

    try {
        const res = await fetch("/api/drafts/test-probe", { method: "POST" });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to create test draft");
        }
        const data = await res.json();
        const modeLabel = data.simulated ? "Simulated Draft" : "Genuine Draft";
        showToast(`✅ ${modeLabel} created in Gmail! ID: ${data.draft_id}`, "success");
    } catch (err) {
        showToast("Error creating test draft: " + err.message, "danger");
    } finally {
        btn.disabled = false;
        btn.innerText = "Create 1 Test Draft";
    }
}

async function fetchStatus() {
    try {
        const res = await fetch("/api/status");
        if (!res.ok) throw new Error("Failed to load status");
        const data = await res.json();

        // Update Test Mode Badge
        const testBadge = document.getElementById("test-mode-badge");
        if (data.test_mode) {
            testBadge.innerText = "TEST MODE (Simulated)";
            testBadge.className = "badge badge-warning";
        } else {
            testBadge.innerText = `LIVE MODE (${(data.search_provider || "SerpAPI").toUpperCase()})`;
            testBadge.className = "badge badge-success";
        }

        // Update Gmail pill
        const pill = document.getElementById("gmail-status-pill");
        const statusText = document.getElementById("gmail-status-text");
        const connectBtn = document.getElementById("btn-connect-gmail");

        if (data.gmail.connected) {
            pill.className = "status-pill status-connected";
            statusText.innerText = `Connected: ${data.gmail.email || "Active"}`;
            connectBtn.innerText = "Reconnect Gmail";
        } else {
            pill.className = "status-pill status-disconnected";
            statusText.innerText = data.test_mode ? "Gmail: Test Simulation Ready" : "Gmail: Disconnected";
            connectBtn.innerText = "Connect Gmail";
        }

        // Schedule Form
        if (data.schedule) {
            const toggle = document.getElementById("schedule-active");
            toggle.checked = data.schedule.is_active;
            document.getElementById("schedule-status-label").innerText = data.schedule.is_active ? "Schedule Active" : "Schedule Inactive";
            document.getElementById("schedule-time").value = data.schedule.run_time || "09:00";
            document.getElementById("schedule-tz").value = data.schedule.timezone || "Asia/Kolkata";
            document.getElementById("owner-email").value = data.schedule.owner_email || data.founder.owner_email;
        }

        // Latest Run
        if (data.latest_run_id) {
            loadRunDetails(data.latest_run_id);
        }
    } catch (err) {
        showToast("Error loading system status: " + err.message, "danger");
    }
}

async function saveSchedule() {
    const isActive = document.getElementById("schedule-active").checked;
    const runTime = document.getElementById("schedule-time").value;
    const timezone = document.getElementById("schedule-tz").value;
    const ownerEmail = document.getElementById("owner-email").value.trim();

    try {
        const res = await fetch("/api/schedule", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                is_active: isActive,
                schedule_type: "daily",
                run_time: runTime,
                timezone: timezone,
                owner_email: ownerEmail
            })
        });
        if (!res.ok) throw new Error("Failed to save schedule");
        showToast("Schedule updated successfully", "success");
    } catch (err) {
        showToast(err.message, "danger");
    }
}

async function handleConnectGmail() {
    try {
        const res = await fetch("/api/auth/google/url");
        const data = await res.json();
        if (data.auth_url) {
            window.location.href = data.auth_url;
        } else {
            showToast(data.message || "Running in test mode. Gmail draft creation is simulated safely.", "info");
        }
    } catch (err) {
        showToast(err.message, "danger");
    }
}

async function executeRunNow() {
    const progressBox = document.getElementById("run-progress-box");
    const runBtn = document.getElementById("btn-run-now");
    
    progressBox.classList.remove("hidden");
    runBtn.disabled = true;

    try {
        const res = await fetch("/api/runs/execute", { method: "POST" });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Workflow execution failed");
        }
        const data = await res.json();
        showToast(`Workflow completed! ${data.verified_count} verified, ${data.rejected_count} rejected.`, "success");
        await loadRunDetails(data.run_id);
        await fetchRunsHistory();
    } catch (err) {
        showToast(err.message, "danger");
    } finally {
        progressBox.classList.add("hidden");
        runBtn.disabled = false;
    }
}

async function loadRunDetails(runId) {
    try {
        const res = await fetch(`/api/runs/${runId}`);
        if (!res.ok) throw new Error("Failed to load run details");
        const data = await res.json();

        currentRunId = runId;
        currentRunData = data;

        // Render Summary Banner
        document.getElementById("run-summary-section").classList.remove("hidden");
        document.getElementById("leads-section").classList.remove("hidden");

        const providerLabel = (data.run.provider_used || "serpapi").toUpperCase();
        const modeLabel = data.run.is_test_mode ? "TEST" : "LIVE";
        document.getElementById("run-id-tag").innerText = `RUN #${data.run.id} (${modeLabel} • ${providerLabel})`;
        document.getElementById("run-timestamp").innerText = new Date(data.run.started_at).toLocaleString();

        document.getElementById("kpi-researched").innerText = data.run.total_researched;
        document.getElementById("kpi-verified").innerText = data.run.total_verified;
        document.getElementById("kpi-drafted").innerText = data.run.total_drafted;
        
        const reportStatusElem = document.getElementById("kpi-report-status");
        if (data.run.report_sent) {
            reportStatusElem.innerText = "Delivered to Owner";
            reportStatusElem.style.color = "var(--success)";
        } else if (data.run.report_error) {
            reportStatusElem.innerText = "Delivery Error";
            reportStatusElem.style.color = "var(--danger)";
        } else {
            reportStatusElem.innerText = "Pending";
            reportStatusElem.style.color = "var(--warning)";
        }

        // View Report link
        const reportBtn = document.getElementById("btn-view-report");
        reportBtn.href = `/api/runs/${runId}/report`;

        // Render Leads
        renderLeads(data.leads);
    } catch (err) {
        showToast(err.message, "danger");
    }
}

function renderLeads(leads) {
    const container = document.getElementById("leads-list");
    container.innerHTML = "";

    const qualifiedLeads = leads.filter(l => l.is_verified);
    const rejectedLeads = leads.filter(l => !l.is_verified);

    document.getElementById("batch-stats-badge").innerText = `${qualifiedLeads.length} Qualified / ${rejectedLeads.length} Rejected`;

    if (qualifiedLeads.length === 0) {
        container.innerHTML = `
            <div style="padding: 24px; text-align: center; color: #64748b; background: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1;">
                <strong>No qualified companies in this run.</strong>
                <p style="margin-top: 6px; font-size: 13px;">All ${rejectedLeads.length} candidate(s) were disqualified during the qualification & duplicate filter stage.</p>
            </div>
        `;
    } else {
        qualifiedLeads.forEach((lead, idx) => {
            const card = document.createElement("div");
            card.className = "lead-card";

            const draft = lead.draft || {};
            let draftBadge = '<span class="badge badge-warning">Draft Pending Approval</span>';
            if (draft.creation_status === "created") {
                draftBadge = `<span class="badge badge-success">Gmail Draft Created (${draft.gmail_draft_id || "Synced"})</span>`;
            } else if (draft.creation_status === "simulated_test") {
                draftBadge = `<span class="badge badge-warning">Simulated Draft (${draft.gmail_draft_id})</span>`;
            } else if (draft.creation_status === "needs_contact") {
                draftBadge = '<span class="badge badge-danger">Needs Public Contact (Review)</span>';
            }

            const evidenceChips = (lead.evidence_items || []).map(ev => 
                `<a href="${ev.source_url}" target="_blank" class="source-chip" title="${ev.evidence_snippet}">🔗 ${ev.page_title || ev.source_type}</a>`
            ).join("");

            card.innerHTML = `
                <div class="lead-header">
                    <div>
                        <span class="lead-company-name">${idx + 1}. ${lead.company_name}</span>
                        <a href="${lead.website}" target="_blank" class="lead-website-link">${lead.website}</a>
                    </div>
                    <div>${draftBadge}</div>
                </div>
                <div class="lead-meta-row">
                    <strong>Industry & HQ:</strong> ${lead.industry} • ${lead.headquarters}
                </div>
                <div class="lead-meta-row">
                    <strong>Hiring Signals:</strong> ${lead.hiring_information || "Not found"}
                </div>
                <div class="lead-fit-box">
                    <strong>StudentHub Partnership Rationale:</strong> ${lead.approach_rationale}
                </div>
                <div class="lead-actions-row">
                    <div class="lead-sources">
                        <span>Sources:</span>
                        ${evidenceChips || '<span style="color:#94a3b8;">None</span>'}
                    </div>
                    <button class="btn btn-secondary btn-preview" data-lead-idx="${idx}">
                        🔍 Preview Email & Draft
                    </button>
                </div>
            `;

            card.querySelector(".btn-preview").addEventListener("click", () => openEmailModal(lead));
            container.appendChild(card);
        });
    }

    // Render Rejected Leads Section if any
    if (rejectedLeads.length > 0) {
        const rejHeader = document.createElement("div");
        rejHeader.style.marginTop = "24px";
        rejHeader.style.padding = "16px";
        rejHeader.style.background = "#fef2f2";
        rejHeader.style.border = "1px solid #fee2e2";
        rejHeader.style.borderRadius = "8px";

        let rejItems = "";
        rejectedLeads.forEach(r => {
            rejItems += `<li style="font-size: 13px; margin-bottom: 6px;"><strong>${r.company_name}</strong>: <span style="color: #dc2626;">${r.disqualification_reason}</span></li>`;
        });

        rejHeader.innerHTML = `
            <h4 style="margin: 0 0 8px 0; color: #991b1b; font-size: 14px;">Excluded Candidates (${rejectedLeads.length})</h4>
            <p style="font-size: 12px; color: #7f1d1d; margin-bottom: 8px;">These entries were disqualified according to strict evidence and duplicate guidelines:</p>
            <ul style="padding-left: 20px; color: #374151; margin: 0;">${rejItems}</ul>
        `;
        container.appendChild(rejHeader);
    }
}

function openEmailModal(lead) {
    activeModalLead = lead;
    const modal = document.getElementById("preview-modal");
    const draft = lead.draft || {};

    document.getElementById("modal-company-title").innerText = lead.company_name;
    document.getElementById("modal-recipient").innerText = lead.contact_email 
        ? `${lead.contact_email} (${lead.contact_name || "Talent Acquisition"})` 
        : "Not found in public domain (Flagged for Review)";
    document.getElementById("modal-subject").innerText = draft.subject || "Founding hiring partnership";
    document.getElementById("modal-draft-id").innerText = draft.gmail_draft_id 
        ? `Created in Gmail: ${draft.gmail_draft_id}` 
        : "Pending Explicit Approval";
    document.getElementById("modal-body-text").innerText = draft.body_text || "No email content generated.";

    const sourcesList = document.getElementById("modal-sources-list");
    sourcesList.innerHTML = "";
    (lead.evidence_items || []).forEach(ev => {
        const li = document.createElement("li");
        li.innerHTML = `<a href="${ev.source_url}" target="_blank">${ev.page_title || ev.source_url}</a>: <em>"${ev.evidence_snippet}"</em>`;
        sourcesList.appendChild(li);
    });

    const approveBtn = document.getElementById("modal-btn-approve-single");
    if (draft.creation_status === "created" || draft.creation_status === "simulated_test") {
        approveBtn.disabled = true;
        approveBtn.innerText = "Draft Already Created";
    } else {
        approveBtn.disabled = false;
        approveBtn.innerText = "Approve & Create Draft in Gmail";
    }

    modal.classList.remove("hidden");
}

function closeModal() {
    document.getElementById("preview-modal").classList.add("hidden");
    activeModalLead = null;
}

async function approveSingleDraft() {
    if (!activeModalLead || !activeModalLead.draft) return;
    try {
        const res = await fetch("/api/drafts/approve-batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                run_id: currentRunId,
                approved_draft_ids: [activeModalLead.draft.id]
            })
        });
        const result = await res.json();
        showToast(`Draft processed: ${result.created_count} created`, "success");
        closeModal();
        await loadRunDetails(currentRunId);
    } catch (err) {
        showToast(err.message, "danger");
    }
}

async function approveBatchDrafts() {
    if (!currentRunId) return;
    if (!confirm("Confirm creating Gmail drafts for all qualified companies in this batch? (Emails will be created as unsent drafts).")) {
        return;
    }

    try {
        const res = await fetch("/api/drafts/approve-batch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ run_id: currentRunId })
        });
        const result = await res.json();
        showToast(`Batch approved: ${result.created_count} drafts created!`, "success");
        await loadRunDetails(currentRunId);
        await fetchRunsHistory();
    } catch (err) {
        showToast(err.message, "danger");
    }
}

async function fetchRunsHistory() {
    try {
        const res = await fetch("/api/runs");
        if (!res.ok) return;
        const runs = await res.json();
        const tbody = document.getElementById("history-table-body");
        tbody.innerHTML = "";

        if (runs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No runs executed yet.</td></tr>';
            return;
        }

        runs.forEach(r => {
            const tr = document.createElement("tr");
            const mode = r.is_test_mode ? "TEST" : "LIVE";
            tr.innerHTML = `
                <td><strong>#${r.id}</strong> <small style="color:#64748b;">(${mode})</small></td>
                <td><span class="badge ${r.trigger_type === 'scheduled' ? 'badge-info' : 'badge-warning'}">${r.trigger_type}</span></td>
                <td><span class="badge ${r.status === 'completed' ? 'badge-success' : 'badge-warning'}">${r.status}</span></td>
                <td>${r.total_researched}</td>
                <td>${r.total_verified}</td>
                <td><strong>${r.total_drafted}</strong></td>
                <td>${r.report_sent ? '✅ Sent' : (r.report_error ? '❌ Error' : '⏳ Pending')}</td>
                <td>${new Date(r.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                <td>
                    <button class="btn btn-outline btn-sm btn-view-history-run" data-run-id="${r.id}">View</button>
                    <a href="/api/runs/${r.id}/report" target="_blank" class="btn btn-outline btn-sm">Report</a>
                </td>
            `;
            tr.querySelector(".btn-view-history-run").addEventListener("click", () => loadRunDetails(r.id));
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
    }
}

function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    toast.innerText = message;
    toast.className = `toast ${type === 'danger' ? 'badge-danger' : (type === 'success' ? 'badge-success' : '')}`;
    toast.classList.remove("hidden");
    setTimeout(() => {
        toast.classList.add("hidden");
    }, 4000);
}
