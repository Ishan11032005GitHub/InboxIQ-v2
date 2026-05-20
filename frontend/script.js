const API = "https://inboxiq-v2.onrender.com";
const SESSION_KEY = "inboxiq_session_id";
const INBOX_CACHE_KEY = "inboxiq_cached_inbox_v1";
const INBOX_CACHE_TTL_MS = 1000 * 60 * 30;

function saveSessionId(sessionId) {
  if (sessionId) sessionStorage.setItem(SESSION_KEY, sessionId);
}

function getSessionId() {
  return sessionStorage.getItem(SESSION_KEY);
}

const sessionFromUrl = new URLSearchParams(window.location.search).get("session_id");
if (sessionFromUrl) {
  saveSessionId(sessionFromUrl);
  const cleanUrl = new URL(window.location.href);
  cleanUrl.searchParams.delete("session_id");
  window.history.replaceState({}, document.title, cleanUrl.toString());
}

const nativeFetch = window.fetch.bind(window);
window.fetch = (input, init = {}) => {
  const url = typeof input === "string" ? input : input?.url;
  if (!url?.startsWith(API)) return nativeFetch(input, init);

  const headers = new Headers(init.headers || {});
  const sessionId = getSessionId();
  if (sessionId) headers.set("X-Session-ID", sessionId);

  return nativeFetch(input, {
    ...init,
    credentials: init.credentials || "include",
    headers,
  });
};

// ----------------------
// ELEMENTS
// ----------------------
let renderedEmailIds = new Set();
let renderedThreadIds = new Map();
const loginBtn      = document.getElementById("loginBtn");
const demoBtn       = document.getElementById("demoBtn");
const logoutBtn     = document.getElementById("logoutBtn");
const demoOffer     = document.getElementById("demoOffer");
const loadEmailsBtn = document.getElementById("loadEmails");
const inbox         = document.getElementById("inbox");
const statusMessage = document.getElementById("statusMessage");
const authMessage   = document.getElementById("authMessage");
const appContent    = document.getElementById("appContent");
const approvalQueue = document.getElementById("approvalQueue");
const approvalCount = document.getElementById("approvalCount");
const taskList = document.getElementById("taskList");
const taskCount = document.getElementById("taskCount");
const workflowLogList = document.getElementById("workflowLogList");
const workflowLogCount = document.getElementById("workflowLogCount");
const contactMemoryList = document.getElementById("contactMemoryList");
const contactMemoryCount = document.getElementById("contactMemoryCount");
const observabilityGrid = document.getElementById("observabilityGrid");
const observabilityBreakdowns = document.getElementById("observabilityBreakdowns");
const observabilityStatus = document.getElementById("observabilityStatus");

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action][data-email-id]");
  if (!button) return;

  event.preventDefault();
  const id = button.dataset.emailId;
  const action = button.dataset.action;

  if (action === "generate-reply") processEmail(id);
  if (action === "schedule") scheduleEmail(id);
  if (action === "confirm-scheduled") confirmScheduled(id);
  if (action === "snooze-menu") toggleSnoozeDropdown(id);
  if (action === "snooze") snoozeEmail(id, Number(button.dataset.duration || 180));
  if (action === "adjust-reply") adjustReply(id);
  if (action === "send-reply") sendReply(id);
  if (action === "copy-reply") copyReply(id);
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-approval-action][data-action-id]");
  if (!button) return;

  event.preventDefault();
  handleApprovalAction(button.dataset.actionId, button.dataset.approvalAction);
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-task-action][data-task-id]");
  if (!button) return;

  event.preventDefault();
  handleTaskAction(button.dataset.taskId, button.dataset.taskAction);
});

document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-suggested-action][data-email-id]");
  if (!button) return;

  event.preventDefault();
  handleSuggestedAction(
    button.dataset.actionId,
    button.dataset.emailId,
    button.dataset.suggestedAction
  );
});

// ----------------------
// STATE
// ----------------------
let emailStore = {};
console.log("✅ script loaded");

// let scheduledStore = {};
const snoozedStore = new Map();
const scheduledStore = new Map();
const inboxOrder = new Map();
let nextInboxOrder = 0;

let isProcessing = false;

window.addEventListener("DOMContentLoaded", async () => {
  try {
    await checkAuthOnLoad();
  } catch (err) {
    console.error("Startup auth check failed:", err);
    updateAuthUI(false);
  } finally {
    document.body.classList.remove("auth-loading");
    connectWS();
    startAutoRefresh();
  }
});

// ----------------------
// LABEL / PRIORITY HELPERS  (unchanged)
// ----------------------
const LABEL_META = {
  newsletter:   { icon: "📰", text: "Newsletter"   },
  promotion:    { icon: "🏷️",  text: "Promotion"    },
  security:     { icon: "🔒", text: "Security"     },
  job_alert:    { icon: "💼", text: "Job Alert"    },
  event_invite: { icon: "🎟️",  text: "Event Invite" },
  notification: { icon: "🔔", text: "Notification" },
  general:      { icon: "📧", text: "General"      },
  work:         { icon: "🗂️",  text: "Work"         },
  spam:         { icon: "🚫", text: "Spam"         },
};

const PRIORITY_META = {
  high:   { color: "#ef4444", icon: "🔴" },
  medium: { color: "#f59e0b", icon: "🟡" },
  low:    { color: "#6b7280", icon: "🟢" },
};

function getLabelChip(label) {
  const m = LABEL_META[label] || { icon: "📧", text: label || "General" };
  return `<span class="label-chip">${m.icon} ${m.text}</span>`;
}

function getPriorityChip(priority) {
  const m    = PRIORITY_META[priority] || PRIORITY_META.low;
  const text = priority ? priority.charAt(0).toUpperCase() + priority.slice(1) : "Low";
  return `<span class="label-chip" style="border-color:${m.color};color:${m.color};">${m.icon} ${text}</span>`;
}

// ── Action bucket chip (Tier-1) ──────────────────────────────────────────
function getBucketChip(bucket, meta) {
  if (!bucket || !meta) return "";
  return `<span class="label-chip bucket-chip"
            style="border-color:${meta.color};color:${meta.color};"
            id="bucket-${bucket}">
            ${meta.icon} ${meta.text}
          </span>`;
}

// ----------------------
// AUTH ACTIONS  (unchanged)
// ----------------------
// ── State ─────────────────────────────────────────────────────────────────
let isCheckingAuth  = false;
let authInitialized = sessionStorage.getItem("authInitiated") === "true";
let demoLoginToken = 0;

// ── Auth button handlers ──────────────────────────────────────────────────
loginBtn?.addEventListener("click", () => {
  authInitialized = true;
  sessionStorage.setItem("authInitiated", "true");
  window.location.href = `${API}/auth/login`;
});

demoBtn?.addEventListener("click", async () => {
  const currentDemoLogin = ++demoLoginToken;
  demoBtn.disabled = true;
  demoBtn.textContent = "Opening demo...";
  showStatus("Opening demo account...");

  try {
    const res = await fetch(`${API}/demo`, {
      method: "GET",
      credentials: "include"
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "Demo login failed");
    if (currentDemoLogin !== demoLoginToken) return;

    // 🔥 THIS IS WHAT YOU WERE MISSING
    authInitialized = true;
    sessionStorage.setItem("authInitiated", "true");
    saveSessionId(data.session_id);

    updateAuthUI(true);

    showStatus("✅ Demo logged in");

    await loadEmails();

  } catch (e) {
    if (currentDemoLogin !== demoLoginToken) return;
    console.error(e);
    showStatus("Demo login failed: " + e.message);
  } finally {
    if (currentDemoLogin === demoLoginToken) {
      resetDemoButton();
    }
  }
});

document.getElementById("sendEmail")?.addEventListener("click", async () => {
  const to      = document.getElementById("to")?.value?.trim();
  const subject = document.getElementById("subject")?.value?.trim();
  const body    = document.getElementById("body")?.value?.trim();

  if (!to || !subject || !body) {
    showStatus("❌ Please fill in To, Subject, and Body.");
    return;
  }

  const btn = document.getElementById("sendEmail");
  btn.disabled    = true;
  btn.textContent = "Sending…";

  try {
    const res = await fetch(`${API}/send-email`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ to, subject, body })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Send failed");

    // Clear the form
    document.getElementById("to").value      = "";
    document.getElementById("subject").value = "";
    document.getElementById("body").value    = "";

    if (data.email) {
      appendEmails([data.email]);
    }
    if (data.simulated && data.email?.sender) {
      showStatus(`Email delivered to ${to} from ${data.email.sender}`);
      return;
    }
    if (data.message) {
      showStatus(data.message);
      return;
    }

    showStatus(`✅ Email sent to ${to}`);
  } catch (err) {
    console.error(err);
    showStatus("❌ Failed to send: " + err.message);
  } finally {
    btn.disabled    = false;
    btn.textContent = "Send Email";
  }
});

logoutBtn?.addEventListener("click", async () => {
  demoLoginToken++;
  authInitialized = false;
  resetDemoButton();
  hideStatus();
  try {
    await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
  } catch (err) {
    console.error("Logout request failed:", err);
  }
  sessionStorage.removeItem("authInitiated");
  sessionStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(INBOX_CACHE_KEY);
  resetInbox();           // ← only place resetInbox should be called
  updateAuthUI(false);
  hideStatus();
});

// ── checkAuthStatus ───────────────────────────────────────────────────────
async function checkAuthStatus() {
  if (isCheckingAuth) return;
  isCheckingAuth = true;

  try {
    const res  = await fetch(`${API}/auth/status`, { credentials: "include" });
    const data = await res.json();

    if (data.authenticated && data.user !== "demo-user") {
      // Real Google session
      authInitialized = true;
      sessionStorage.setItem("authInitiated", "true");
      updateAuthUI(true);
      const restored = restoreCachedInbox();
      await loadEmails({ background: restored });
      return;
    }

    if (data.authenticated && data.mode === "demo" && authInitialized) {
      updateAuthUI(true);
      // Don't re-fetch if cards are already rendered (survives Live Server reload)
      if (renderedEmailIds.size === 0) {
        const restored = restoreCachedInbox();
        await loadEmails({ background: restored });
      }
      return;
    }


    // No valid session — show login page
    if (!authInitialized) {
      updateAuthUI(false);
    }

  } catch (err) {
    console.error(err);
    if (!authInitialized) updateAuthUI(false);
  } finally {
    isCheckingAuth = false;
  }
}

// ── needsMeeting ──────────────────────────────────────────────────────────
function needsMeeting(email) {
  return !!email.needs_meeting;
}

function moveToScheduledUI(email) {
  const container = document.getElementById("scheduledList");

  const card = document.createElement("div");
  card.className = "card email-card";
  card.setAttribute("data-id", email.id); // 🔥 FIX

  card.innerHTML = `
    <div class="email-main">
      <h3>${email.subject}</h3>
      <p><strong>From:</strong> ${email.sender}</p>

      <div style="margin-top:10px;">
        <a href="${email.event_link || "#"}" target="_blank" class="btn btn-primary">
          Open Event
        </a>

        <button class="btn btn-secondary"
          onclick="cancelSchedule('${email.id}')"
          style="cursor:pointer;">
          Cancel
        </button>
      </div>
    </div>
  `;

  container.appendChild(card);
}

function updateEmailCardToScheduled(id, eventLink) {
  const actionDiv = document.getElementById(`actions-${id}`);
  if (!actionDiv) return;

  actionDiv.innerHTML = `
    <span class="label-chip" style="border-color:#10b981;color:#10b981;">
      ✅ Scheduled
    </span>

    <a href="${eventLink}" target="_blank" class="btn btn-primary">
      Open Event
    </a>

    ${renderSnooze(id)}
  `;
}

function scheduleEmail(id) {
  const email = emailStore[id];
  if (!email) return;

  const link =
    `https://calendar.google.com/calendar/r/eventedit?text=${encodeURIComponent(email.subject)}`;
  email.event_link = link;
  email.calendar_opened = true;

  window.open(link, "_blank");
  renderActions(email);

  showStatus("📅 Calendar opened");
}

async function confirmScheduled(id) {
  try {
    const res = await fetch(`${API}/email/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id, event_link: emailStore[id]?.event_link })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    // Optional: update UI properly
    const email = emailStore[id];
    if (email) {
      email.action_bucket = "SCHEDULED";
      email.event_link = data.event_link || email.event_link || null;
      scheduledStore.set(id, email);
      snoozedStore.delete(id);
      document.querySelector(`#inbox [data-id="${id}"]`)?.remove();
      document.querySelector(`#snoozedList [data-id="${id}"]`)?.remove();
      renderedEmailIds.delete(id);
      appendScheduledEmails([email]);
      persistCurrentInboxState();
      await loadWorkflowLogs();
      await loadObservabilitySummary();
    }

    showStatus("✅ Event marked as scheduled");

  } catch (err) {
    console.error(err);
    showStatus("❌ " + err.message);
  }
}

function updateEmailCardAfterCalendar(id) {
  const actionDiv = document.getElementById(`actions-${id}`);
  if (!actionDiv) return;

  actionDiv.innerHTML = `
    <button class="btn btn-secondary" onclick="processEmail('${id}')">
      Generate Reply
    </button>

    <button class="btn btn-primary" disabled>
      📅 Calendar Opened
    </button>

    <button class="btn btn-secondary" onclick="snoozeEmail('${id}', 180)">
      Snooze
    </button>

    <button class="btn btn-success"
      onclick="confirmScheduled('${id}')">
      ✅ Event is Scheduled
    </button>
  `;
}

// setInterval(checkSnoozedReturn, 30000);

async function checkSnoozedReturn() {
  try {
    const res = await fetch(`${API}/emails/snoozed`, {
      credentials: "include"
    });

    const data = await res.json();

    const now = new Date();

    (data.emails || []).forEach(email => {
      if (new Date(email.remind_at) <= now) {

        document.querySelector(`#snoozedList [data-id="${email.id}"]`)?.remove();

        email.action_bucket = null;
        delete email.remind_at;

        appendEmails([email]);

        showStatus(`⏰ Returned: ${email.subject}`);
      }
    });

  } catch (err) {
    console.error(err);
  }
}

// ── appendEmails ──────────────────────────────────────────────────────────
function escapeHTML(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function cleanEmailBody(value = "") {
  let text = String(value || "");

  if (/<\/?[a-z][\s\S]*>/i.test(text)) {
    text = text
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/(p|div|li|tr|h[1-6])>/gi, "\n")
      .replace(/<[^>]+>/g, " ");
  }

  const parser = document.createElement("textarea");
  parser.innerHTML = text;
  text = parser.value;

  return text
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/(https?:\/\/\S{80})\S+/g, "$1...")
    .trim();
}

function renderCleanBody(body = "", { collapsed = true } = {}) {
  const clean = cleanEmailBody(body);
  if (!clean) return `<div class="message-body muted">No readable body.</div>`;

  const maxLength = 700;
  if (!collapsed || clean.length <= maxLength) {
    return `<div class="message-body">${escapeHTML(clean)}</div>`;
  }

  const preview = clean.slice(0, maxLength).trim();
  return `
    <details class="message-body-details">
      <summary>${escapeHTML(preview)}...</summary>
      <div class="message-body">${escapeHTML(clean)}</div>
    </details>
  `;
}

function renderThreadStateChip(email) {
  const state = email.thread_state;
  if (!state?.current_status) return "";

  const label = state.current_status.replaceAll("_", " ");
  const action = state.pending_action ? ` · ${state.pending_action.replaceAll("_", " ")}` : "";
  const confidence = Number.isFinite(state.confidence_score)
    ? ` · ${Math.round(state.confidence_score * 100)}%`
    : "";

  return `
    <span class="label-chip workflow-chip" title="${escapeHTML(state.summarized_context || "")}">
      ${escapeHTML(label)}${escapeHTML(action)}${confidence}
    </span>
  `;
}

function renderLegacyApprovalQueue(actions = []) {
  if (!approvalQueue || !approvalCount) return;

  approvalCount.textContent = `${actions.length} pending`;
  if (!actions.length) {
    approvalQueue.innerHTML = `<p class="muted-text">No suggested actions right now.</p>`;
    return;
  }

  approvalQueue.innerHTML = actions.map(action => `
    <div class="approval-item">
      <div>
        <div class="approval-title">${escapeHTML(action.action_type.replaceAll("_", " "))}</div>
        <div class="approval-reason">${escapeHTML(action.reasoning || "")}</div>
        <div class="approval-meta">
          ${escapeHTML(action.risk_level || "medium")} risk · ${Math.round((action.confidence_score || 0) * 100)}% confidence
        </div>
      </div>
      <div class="approval-actions">
        <button type="button" class="btn btn-secondary" data-approval-action="reject" data-action-id="${escapeHTML(action.id)}">Dismiss</button>
      </div>
    </div>
  `).join("");
}

function renderActionEntityChips(entities = {}) {
  const chips = [];
  const participants = Array.isArray(entities.participants) ? entities.participants : [];
  const emails = Array.isArray(entities.emails) ? entities.emails : [];
  const dates = Array.isArray(entities.dates) ? entities.dates : [];

  participants.slice(0, 1).forEach(value => chips.push({ label: "Person", value }));
  emails.slice(0, 1).forEach(value => chips.push({ label: "Email", value }));
  dates.slice(0, 1).forEach(value => chips.push({ label: "Date", value }));

  if (!chips.length && entities.sender) chips.push({ label: "Sender", value: entities.sender });
  if (!chips.length) return `<span class="muted-text">No entities extracted</span>`;

  return chips.map(chip => `
    <span class="approval-detail-chip">
      <span>${escapeHTML(chip.label)}</span>
      ${escapeHTML(chip.value)}
    </span>
  `).join("");
}

function renderWorkflowPlan(plan = {}) {
  if (!plan || typeof plan !== "object") return "";
  const observe = plan.observe || {};
  const reason = plan.reason || {};
  const execute = plan.execute || {};
  const verify = plan.verify || {};
  const planSteps = Array.isArray(plan.plan) ? plan.plan : [];

  return `
    <details class="workflow-plan-details">
      <summary>Workflow plan</summary>
      <div class="workflow-plan-grid">
        <div><strong>Observe</strong><span>${escapeHTML(observe.status || "active thread")} · urgency ${escapeHTML(String(Math.round(observe.urgency_score || 0)))}</span></div>
        <div><strong>Reason</strong><span>${escapeHTML((reason.intent || "workflow action").replaceAll("_", " "))} · ${escapeHTML(reason.approval_gate || "review")}</span></div>
        <div><strong>Action</strong><span>${escapeHTML((execute.action_type || "manual").replaceAll("_", " "))}</span></div>
        <div><strong>Verify</strong><span>${escapeHTML(verify.expected_outcome || "Outcome must be verified.")}</span></div>
      </div>
      ${planSteps.length ? `<ol class="workflow-plan-steps">${planSteps.map(step => `<li>${escapeHTML(step)}</li>`).join("")}</ol>` : ""}
    </details>
  `;
}

function getSuggestedActionControls(action) {
  const payload = action.payload || {};
  const emailId = payload.email_id || action.email_id;
  const actionId = action.id || "";
  const safeEmailId = escapeHTML(emailId || "");
  const safeActionId = escapeHTML(actionId);
  const disabled = !emailId ? "disabled" : "";

  const rejectButton = action.status === "pending"
    ? `<button type="button" class="btn btn-secondary" data-approval-action="reject" data-action-id="${safeActionId}">Dismiss</button>`
    : "";

  if (action.status === "failed") {
    return `<button type="button" class="btn btn-secondary" data-approval-action="retry" data-action-id="${safeActionId}">Retry</button>`;
  }

  if (action.status === "executed" || action.status === "rejected") {
    return `<span class="label-chip">${escapeHTML(action.status || "done")}</span>`;
  }

  return `
    <button type="button" class="btn btn-primary" data-suggested-action="to_email" data-action-id="${safeActionId}" data-email-id="${safeEmailId}" ${disabled}>To Email</button>
    ${rejectButton}
  `;
}

function renderApprovalQueue(actions = []) {
  if (!approvalQueue || !approvalCount) return;

  const activeCount = actions.filter(action => !["executed", "rejected"].includes(action.status)).length;
  approvalCount.textContent = `${activeCount} suggestions`;
  if (!actions.length) {
    approvalQueue.innerHTML = `<p class="muted-text">No suggested actions right now.</p>`;
    return;
  }

  approvalQueue.innerHTML = actions.map(action => {
    const payload = action.payload || {};
    const approval = payload.approval || {};
    const intent = payload.extracted_intent || action.action_type;
    const entities = payload.affected_entities || {};
    const workflowPlan = payload.workflow_plan || {};
    const status = action.status || "pending";
    const displayStatus = status === "pending" ? "suggested" : status === "approved" ? "ready" : status;
    const risk = action.risk_level || "medium";
    const confidence = Math.round((action.confidence_score || 0) * 100);
    const title = String(action.action_type || "workflow action").replaceAll("_", " ");
    const controls = getSuggestedActionControls(action);

    return `
      <div class="approval-item approval-action-card">
        <div class="approval-content">
          <div class="approval-card-header">
            <div>
              <div class="approval-title">${escapeHTML(title)}</div>
              <div class="approval-subtitle">${escapeHTML(payload.topic || "Unknown thread")}</div>
            </div>
            <div class="approval-badges">
              <span class="approval-status-chip status-${escapeHTML(status)}">${escapeHTML(displayStatus)}</span>
              <span class="approval-status-chip risk-${escapeHTML(risk)}">${escapeHTML(risk)} risk</span>
              <span class="approval-status-chip">${confidence}%</span>
            </div>
          </div>
          <div class="approval-reason">${escapeHTML(action.reasoning || "")}</div>
          <div class="approval-meta">${escapeHTML(String(action.retry_count || 0))} retries</div>
          ${action.last_error ? `<div class="approval-error">${escapeHTML(action.last_error)}</div>` : ""}
          <div class="approval-insight-grid">
            <div>
              <span>Intent</span>
              <strong>${escapeHTML(String(intent).replaceAll("_", " "))}</strong>
            </div>
            <div>
              <span>Why suggested</span>
              <strong>${escapeHTML(approval.approval_reason || "Human review keeps execution safe.")}</strong>
            </div>
          </div>
          <div class="approval-entities">
            ${renderActionEntityChips(entities)}
          </div>
          ${renderWorkflowPlan(workflowPlan)}
        </div>
        <div class="approval-actions">
          ${controls}
        </div>
      </div>
    `;
  }).join("");
}

async function loadPendingActions() {
  try {
    const { res, data } = await fetchJson("/actions/pending");
    if (!res.ok) throw new Error(data.detail || "Failed to load actions");
    renderApprovalQueue(data.actions || []);
  } catch (err) {
    console.error(err);
    if (approvalQueue) approvalQueue.innerHTML = `<p class="muted-text">Suggested actions unavailable.</p>`;
  }
}

function renderObservabilitySummary(payload = {}) {
  if (!observabilityGrid || !observabilityBreakdowns || !observabilityStatus) return;

  const summary = payload.summary || {};
  const breakdowns = payload.breakdowns || {};
  const confidence = Math.round((summary.average_confidence || 0) * 100);
  const metrics = [
    ["Pending Actions", summary.pending_actions || 0],
    ["Approved Actions", summary.approved_actions || 0],
    ["Executed Actions", summary.executed_actions || 0],
    ["Open Tasks", summary.open_tasks || 0],
    ["Unresolved Threads", summary.unresolved_threads || 0],
    ["Failures", (summary.failed_actions || 0) + (summary.failed_executions || 0)],
    ["Known Contacts", summary.known_contacts || 0],
    ["Avg Confidence", `${confidence}%`],
  ];

  observabilityStatus.textContent = summary.failed_executions || summary.failed_actions
    ? "Needs attention"
    : "Healthy";

  observabilityGrid.innerHTML = metrics.map(([label, value]) => `
    <div class="metric-card">
      <div class="metric-value">${escapeHTML(String(value))}</div>
      <div class="metric-label">${escapeHTML(label)}</div>
    </div>
  `).join("");

  const sections = [
    ["Actions", breakdowns.actions || {}],
    ["Tasks", breakdowns.tasks || {}],
    ["Threads", breakdowns.threads || {}],
    ["Logs", breakdowns.logs || {}],
  ];

  observabilityBreakdowns.innerHTML = sections.map(([title, values]) => {
    const rows = Object.entries(values);
    const body = rows.length
      ? rows.map(([key, value]) => `<span>${escapeHTML(key.replaceAll("_", " "))}: ${escapeHTML(String(value))}</span>`).join("")
      : `<span>None yet</span>`;
    return `
      <div class="breakdown-card">
        <div class="breakdown-title">${escapeHTML(title)}</div>
        <div class="breakdown-items">${body}</div>
      </div>
    `;
  }).join("");
}

async function loadObservabilitySummary() {
  try {
    const { res, data } = await fetchJson("/observability/summary");
    if (!res.ok) throw new Error(data.detail || "Failed to load observability summary");
    renderObservabilitySummary(data);
  } catch (err) {
    console.error(err);
    if (observabilityStatus) observabilityStatus.textContent = "Unavailable";
    if (observabilityGrid) observabilityGrid.innerHTML = `<p class="muted-text">Observability unavailable.</p>`;
    if (observabilityBreakdowns) observabilityBreakdowns.innerHTML = "";
  }
}

async function handleApprovalAction(actionId, action) {
  if (!actionId || !["reject", "retry"].includes(action)) return;

  try {
    const { res, data } = await fetchJson(`/actions/${encodeURIComponent(actionId)}/${action}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(data.detail || "Action update failed");
    const messages = {
      reject: "Suggestion dismissed",
      retry: "Action ready to retry",
    };
    showStatus(messages[action]);
    await loadPendingActions();
    await loadObservabilitySummary();
    await loadTasks();
    await loadWorkflowLogs();
    await loadObservabilitySummary();
  } catch (err) {
    console.error(err);
    showStatus(err.message);
  }
}

async function approveAndExecuteAction(actionId) {
  if (!actionId) throw new Error("Missing action id");

  const approve = await fetchJson(`/actions/${encodeURIComponent(actionId)}/approve`, {
    method: "POST",
  });
  if (!approve.res.ok) throw new Error(approve.data.detail || "Action approval failed");

  const execute = await fetchJson(`/actions/${encodeURIComponent(actionId)}/execute`, {
    method: "POST",
  });
  if (!execute.res.ok) throw new Error(execute.data.detail || "Action execution failed");

  await Promise.allSettled([
    loadPendingActions(),
    loadTasks(),
    loadWorkflowLogs(),
    loadObservabilitySummary(),
  ]);

  return execute.data;
}

async function completeSuggestedAction(actionId) {
  if (!actionId) return;
  const { res, data } = await fetchJson(`/actions/${encodeURIComponent(actionId)}/complete`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(data.detail || "Could not complete suggestion");
  await Promise.allSettled([
    loadPendingActions(),
    loadWorkflowLogs(),
    loadObservabilitySummary(),
  ]);
}

async function handleSuggestedAction(actionId, emailId, suggestedAction) {
  if (!emailId || !suggestedAction) return;

  const card = document.querySelector(`#inbox [data-id="${CSS.escape(emailId)}"]`);
  if (card) card.scrollIntoView({ behavior: "smooth", block: "center" });

  try {
    if (suggestedAction === "to_email") {
      if (card) {
        card.classList.add("email-card-highlight");
        setTimeout(() => card.classList.remove("email-card-highlight"), 1800);
        showStatus("Opened the email. Use the email buttons to take action.");
      } else {
        showStatus("Email is not currently visible. Load emails or check Scheduled/Snoozed.");
      }
    }
  } catch (err) {
    console.error(err);
    showStatus(err.message || "Suggested action failed");
  }
}

function renderTaskList(tasks = []) {
  if (!taskList || !taskCount) return;

  const openCount = tasks.filter(task => task.status !== "completed").length;
  taskCount.textContent = `${openCount} open`;

  if (!tasks.length) {
    taskList.innerHTML = `<p class="muted-text">No workflow tasks yet.</p>`;
    return;
  }

  taskList.innerHTML = tasks.map(task => {
    const isCompleted = task.status === "completed";
    const dueText = task.due_at ? `Due ${formatWorkflowTime(task.due_at)}` : "";
    const controls = isCompleted
      ? `<button type="button" class="btn btn-secondary" data-task-action="reopen" data-task-id="${escapeHTML(task.id)}">Reopen</button>`
      : `<button type="button" class="btn btn-success" data-task-action="complete" data-task-id="${escapeHTML(task.id)}">Complete</button>`;

    return `
      <div class="approval-item">
        <div>
          <div class="approval-title">${escapeHTML(task.title || "Workflow task")}</div>
          <div class="approval-reason">${escapeHTML(task.description || "")}</div>
          <div class="approval-meta">
            ${escapeHTML(task.status || "open")} - ${escapeHTML(task.source_action_id || "workflow")}${dueText ? ` - ${escapeHTML(dueText)}` : ""}
          </div>
        </div>
        <div class="approval-actions">
          ${controls}
        </div>
      </div>
    `;
  }).join("");
}

async function loadTasks() {
  try {
    const { res, data } = await fetchJson("/tasks");
    if (!res.ok) throw new Error(data.detail || "Failed to load tasks");
    renderTaskList(data.tasks || []);
  } catch (err) {
    console.error(err);
    if (taskList) taskList.innerHTML = `<p class="muted-text">Workflow tasks unavailable.</p>`;
  }
}

async function handleTaskAction(taskId, action) {
  if (!taskId || !["complete", "reopen"].includes(action)) return;

  try {
    const { res, data } = await fetchJson(`/tasks/${encodeURIComponent(taskId)}/${action}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(data.detail || "Task update failed");
    showStatus(action === "complete" ? "Task completed" : "Task reopened");
    await loadTasks();
    await loadWorkflowLogs();
    await loadObservabilitySummary();
  } catch (err) {
    console.error(err);
    showStatus(err.message);
  }
}

function formatWorkflowTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderWorkflowLogs(logs = []) {
  if (!workflowLogList || !workflowLogCount) return;

  workflowLogCount.textContent = `${logs.length} events`;

  if (!logs.length) {
    workflowLogList.innerHTML = `<p class="muted-text">No workflow history yet.</p>`;
    return;
  }

  workflowLogList.innerHTML = logs.map(log => `
    <div class="approval-item history-item">
      <div>
        <div class="approval-title">${escapeHTML((log.action_type || "workflow").replaceAll("_", " "))}</div>
        <div class="approval-reason">${escapeHTML(log.message || "")}</div>
        <div class="approval-meta">
          ${escapeHTML(log.status || "recorded")} - ${escapeHTML(formatWorkflowTime(log.created_at))}
        </div>
      </div>
      <span class="label-chip">${escapeHTML(log.status || "event")}</span>
    </div>
  `).join("");
}

async function loadWorkflowLogs() {
  try {
    const { res, data } = await fetchJson("/actions/logs?limit=50");
    if (!res.ok) throw new Error(data.detail || "Failed to load workflow history");
    renderWorkflowLogs(data.logs || []);
  } catch (err) {
    console.error(err);
    if (workflowLogList) workflowLogList.innerHTML = `<p class="muted-text">Workflow history unavailable.</p>`;
  }
}

function renderContactMemories(contacts = []) {
  if (!contactMemoryList || !contactMemoryCount) return;

  contactMemoryCount.textContent = `${contacts.length} contacts`;

  if (!contacts.length) {
    contactMemoryList.innerHTML = `<p class="muted-text">No contact memory yet.</p>`;
    return;
  }

  contactMemoryList.innerHTML = contacts.map(contact => {
    const topics = Array.isArray(contact.recurring_topics)
      ? contact.recurring_topics.slice(-2).join(", ")
      : "";
    return `
      <div class="approval-item memory-item">
        <div>
          <div class="approval-title">${escapeHTML(contact.display_name || contact.sender_email || "Unknown contact")}</div>
          <div class="approval-reason">${escapeHTML(contact.summary || "")}</div>
          <div class="approval-meta">
            ${escapeHTML(contact.thread_count || 0)} thread(s) - ${Math.round(contact.importance_score || 0)} importance${topics ? ` - ${escapeHTML(topics)}` : ""}
          </div>
        </div>
        <span class="label-chip">${escapeHTML(contact.preferred_tone || "remembered")}</span>
      </div>
    `;
  }).join("");
}

async function loadContactMemories() {
  try {
    const { res, data } = await fetchJson("/contacts/memory?limit=20");
    if (!res.ok) throw new Error(data.detail || "Failed to load contact memory");
    renderContactMemories(data.contacts || []);
  } catch (err) {
    console.error(err);
    if (contactMemoryList) contactMemoryList.innerHTML = `<p class="muted-text">Contact memory unavailable.</p>`;
  }
}

function getConversationThread(email) {
  if (Array.isArray(email.conversation_thread) && email.conversation_thread.length) {
    return email.conversation_thread;
  }

  const thread = [{
    role: "received",
    sender: email.sender || "Unknown",
    subject: email.subject || "",
    body: email.body || "",
  }];

  if (email.reply_sent && email.reply) {
    thread.push({
      role: "sent",
      sender: "You",
      subject: `Re: ${email.subject || ""}`,
      body: email.reply,
      sent_at: email.reply_sent_at,
    });
  }

  return thread;
}

function getThreadKey(email) {
  return email?.thread_id || email?.threadId || email?.id;
}

function renderConversationThread(email) {
  const messages = getConversationThread(email);
  return `
    <div class="conversation-thread" style="display:grid;gap:10px;margin-bottom:10px;">
      ${messages.map(message => `
        <div style="border:1px solid #334155;border-radius:8px;padding:10px;background:#0f172a;">
          <div style="font-weight:700;margin-bottom:4px;">
            ${message.role === "sent" ? "You" : escapeHTML(message.sender || "Unknown")}
            ${message.role === "sent" ? `<span class="label-chip" style="margin-left:8px;border-color:#10b981;color:#10b981;">Reply Sent</span>` : ""}
          </div>
          ${renderCleanBody(message.body || "", { collapsed: false })}
        </div>
      `).join("")}
    </div>
  `;
}

function renderInboxThread(email) {
  const messages = getConversationThread(email);
  return `
    <div class="conversation-thread" style="display:grid;gap:10px;margin-top:12px;">
      ${messages.map((message, index) => `
        <div style="border:1px solid #334155;border-radius:12px;padding:12px;background:#0f172a;">
          <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-weight:700;margin-bottom:6px;">
            <span>${message.role === "sent" ? "You" : escapeHTML(message.sender || "Unknown")}</span>
            <span style="color:#94a3b8;font-size:0.78rem;">${index + 1} of ${messages.length}</span>
          </div>
          ${message.subject ? `<div style="color:#cbd5e1;font-size:0.85rem;margin-bottom:6px;">${escapeHTML(message.subject)}</div>` : ""}
          ${renderCleanBody(message.body || "")}
        </div>
      `).join("")}
    </div>
  `;
}

function renderEmailCardContent(email) {
  const emailId = escapeHTML(email.id || "");
  return `
    <div class="email-main">
      <h3>${escapeHTML(email.subject || "No Subject")}</h3>
      <p><strong>From:</strong> ${escapeHTML(email.sender || "Unknown")}</p>

      <div style="margin-top:8px;">
        ${getLabelChip(email.label)}
        ${getPriorityChip(email.priority)}
        ${renderThreadStateChip(email)}
      </div>

      ${renderInboxThread(email)}

      <div id="actions-${emailId}" class="action-row" style="margin-top:10px;"></div>

      ${renderReplyBox(email)}
    </div>
  `;
}

function refreshEmailCard(email) {
  const threadKey = getThreadKey(email);
  const existingId = renderedThreadIds.get(threadKey);
  const card = existingId ? document.querySelector(`#inbox [data-id="${existingId}"]`) : null;
  if (!card) return false;

  renderedEmailIds.delete(existingId);
  renderedEmailIds.add(email.id);
  renderedThreadIds.set(threadKey, email.id);
  card.setAttribute("data-id", email.id);
  card.innerHTML = renderEmailCardContent(email);
  emailStore[email.id] = email;
  renderActions(email, card);
  return true;
}

function renderReplyBox(email) {
  const isSent = !!email.reply_sent;
  const emailId = escapeHTML(email.id || "");

  return `
    <div id="reply-${emailId}" class="hidden reply-box" style="margin-top:10px;">
      ${renderConversationThread(email)}
      ${isSent ? "" : `
        <textarea id="prompt-${emailId}" class="reply-prompt"
          placeholder="Optional: add instructions for this reply, e.g. keep it short, politely decline, ask for another slot..."></textarea>
      `}
      <textarea class="reply-body" style="width:100%;height:100px;" ${isSent ? "readonly" : ""}>${escapeHTML(email.reply || "")}</textarea>
      <div class="reply-actions" style="margin-top:6px;">
        ${isSent ? `<span class="label-chip" style="border-color:#10b981;color:#10b981;">Reply Sent</span>` : `<button id="send-${emailId}" type="button" data-action="send-reply" data-email-id="${emailId}" class="btn btn-primary">Send</button>`}
        ${isSent ? "" : `<button id="adjust-${emailId}" type="button" data-action="adjust-reply" data-email-id="${emailId}" class="btn btn-secondary">Adjust Reply</button>`}
        <button id="copy-${emailId}" type="button" data-action="copy-reply" data-email-id="${emailId}" class="btn btn-secondary">Copy</button>
      </div>
    </div>
  `;
}

function appendEmails(emails) {
  const inbox = document.getElementById("inbox");

  if (!Array.isArray(emails) || emails.length === 0) {
    if (!renderedEmailIds.size) {
      inbox.innerHTML = "<p style='color:white'>No emails found</p>";
    }
    return;
  }

  if (inbox.textContent.trim() === "No emails found") {
    inbox.innerHTML = "";
  }

  let failed = 0;
  emails.forEach(email => {
    try {
    if (!email || !email.id || snoozedStore.has(email.id) || scheduledStore.has(email.id)) return;
    rememberInboxOrder([email]);
    const threadKey = getThreadKey(email);
    if (renderedEmailIds.has(email.id)) return;
    if (renderedThreadIds.has(threadKey)) {
      refreshEmailCard(email);
      return;
    }

    emailStore[email.id] = email;
    renderedEmailIds.add(email.id);
    renderedThreadIds.set(threadKey, email.id);

    const div = document.createElement("div");
    div.className = "card email-card";
    div.setAttribute("data-id", email.id);

    div.innerHTML = renderEmailCardContent(email);
    /*
    div.innerHTML = `
      <div class="email-main">
        <h3>${email.subject || "No Subject"}</h3>
        <p><strong>From:</strong> ${email.sender || "Unknown"}</p>

        <div style="margin-top:8px;">
          ${getLabelChip(email.label)}
          ${getPriorityChip(email.priority)}
        </div>

        <p style="margin-top:10px;">
          ${(email.body || "").slice(0, 150)}
        </p>

        <!-- 🔥 ACTIONS CONTAINER -->
        <div id="actions-${email.id}" class="action-row" style="margin-top:10px;"></div>

        <!-- 🔥 REPLY BOX -->
        ${renderReplyBox(email)}
      </div>
    `;
    */

    insertEmailCardInInboxOrder(inbox, div, email);

    // 🔥 CRITICAL: RENDER BUTTONS
    renderActions(email, div);
    } catch (err) {
      failed += 1;
      if (email?.id) {
        renderedEmailIds.delete(email.id);
        renderedThreadIds.delete(getThreadKey(email));
      }
      console.error("Failed to render email", email, err);
    }
  });

  if (!renderedEmailIds.size) {
    inbox.innerHTML = `<p style='color:white'>No inbox emails to show${failed ? ` (${failed} failed to render)` : ""}</p>`;
  } else if (failed) {
    showStatus(`Loaded emails, but ${failed} could not be rendered.`);
  }
}

function renderActions(email, root = document) {
  const actionId = `actions-${email.id}`;
  const actionDiv = root === document
    ? document.getElementById(actionId)
    : root.querySelector(".action-row");
  if (!actionDiv) return;

  // 🔥 1. AFTER REPLY → ONLY VIEW REPLY (NO SNOOZE)
  if (email.reply) {
    actionDiv.innerHTML = `
      <button class="btn btn-primary"
        onclick="toggleReply('${email.id}')">
        View Reply
      </button>
    `;
    return;
  }

  if (email.calendar_opened || localStorage.getItem(`calendar_opened_${email.id}`) === "true") {
  actionDiv.innerHTML = `
    <button class="btn btn-secondary" onclick="processEmail('${email.id}')">
      Generate Reply
    </button>

    <button class="btn btn-primary" disabled>
      📅 Calendar Opened
    </button>

    ${renderSnooze(email.id)}

    <button class="btn btn-success" onclick="confirmScheduled('${email.id}')">
      ✅ Event is Scheduled
    </button>
  `;
  return;
}
  // 🔥 2. MEETING EMAIL → SHOW SCHEDULE BUTTON
  if (email.needs_meeting) {
    actionDiv.innerHTML = `
      <button class="btn btn-primary"
        onclick="scheduleEmail('${email.id}')">
        📅 Schedule
      </button>

      ${renderSnooze(email.id)}
    `;
    return;
  }

  // 🔥 3. DEFAULT EMAIL
  actionDiv.innerHTML = `
    <button class="btn btn-secondary"
      onclick="processEmail('${email.id}')">
      Generate Reply
    </button>

    <button class="btn btn-primary"
      onclick="toggleReply('${email.id}')">
      Reply
    </button>

    ${renderSnooze(email.id)}
  `;
}

function renderActions(email, root = document) {
  const actionId = `actions-${email.id}`;
  const actionDiv = root === document
    ? document.getElementById(actionId)
    : root.querySelector(".action-row");
  if (!actionDiv) return;

  const emailId = escapeHTML(email.id || "");
  const controls = [];

  if (email.reply_sent) {
    controls.push(`
      <span class="label-chip" style="border-color:#10b981;color:#10b981;">
        Reply Sent
      </span>
      <button class="btn btn-primary" onclick="toggleReply('${email.id}')">
        View Thread
      </button>
    `);
  } else if (email.reply) {
    controls.push(`
      <button class="btn btn-primary" onclick="toggleReply('${email.id}')">
        View Reply
      </button>
    `);
  } else {
    controls.push(`
      <button type="button" class="btn btn-secondary" data-action="generate-reply" data-email-id="${emailId}">
        Generate Reply
      </button>
    `);

    if (!email.needs_meeting) {
      controls.push(`
        <button class="btn btn-primary" onclick="toggleReply('${email.id}')">
          Reply
        </button>
      `);
    }
  }

  if (email.needs_meeting) {
    controls.push(`
      <button type="button" class="btn btn-primary" data-action="schedule" data-email-id="${emailId}">
        Schedule
      </button>
    `);

    controls.push(`
      <button type="button" class="btn btn-success" data-action="confirm-scheduled" data-email-id="${emailId}">
        Event is Scheduled
      </button>
    `);
  }

  controls.push(renderSnooze(email.id));
  actionDiv.innerHTML = controls.join("");
}

function openEvent(link) {
  if (!link || !link.startsWith("http")) {
    showStatus("❌ Invalid event link");
    return;
  }
  window.open(link, "_blank");
}

function normalizeEmailList(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.emails)) return payload.emails;
  if (Array.isArray(payload?.emails?.emails)) return payload.emails.emails;
  return [];
}

function trimForCache(value, max = 4000) {
  if (typeof value !== "string") return value;
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

function compactEmailForCache(email) {
  if (!email || !email.id) return null;
  const thread = Array.isArray(email.conversation_thread)
    ? email.conversation_thread.slice(0, 12).map(message => ({
        ...message,
        body: trimForCache(message.body || "", 3000),
      }))
    : email.conversation_thread;

  return {
    ...email,
    inbox_order: inboxOrder.get(email.id) ?? email.inbox_order ?? null,
    body: trimForCache(email.body || "", 4000),
    reply: trimForCache(email.reply || "", 4000),
    conversation_thread: thread,
  };
}

function rememberInboxOrder(emails = []) {
  (emails || []).forEach(email => {
    if (!email || !email.id) return;
    if (Number.isFinite(email.inbox_order)) {
      inboxOrder.set(email.id, email.inbox_order);
      nextInboxOrder = Math.max(nextInboxOrder, email.inbox_order + 1);
      return;
    }
    if (!inboxOrder.has(email.id)) {
      inboxOrder.set(email.id, nextInboxOrder++);
    }
    email.inbox_order = inboxOrder.get(email.id);
  });
}

function insertEmailCardInInboxOrder(inbox, card, email) {
  const order = inboxOrder.get(email.id);
  if (!Number.isFinite(order)) {
    inbox.appendChild(card);
    return;
  }

  const nextCard = Array.from(inbox.querySelectorAll(".email-card[data-id]")).find(existingCard => {
    const existingId = existingCard.getAttribute("data-id");
    const existingOrder = inboxOrder.get(existingId);
    return Number.isFinite(existingOrder) && existingOrder > order;
  });

  inbox.insertBefore(card, nextCard || null);
}

function saveInboxCache({ emails = [], snoozed = [], scheduled = [] } = {}) {
  try {
    const payload = {
      saved_at: Date.now(),
      emails: emails.map(compactEmailForCache).filter(Boolean).slice(0, 150),
      snoozed: snoozed.map(compactEmailForCache).filter(Boolean).slice(0, 80),
      scheduled: scheduled.map(compactEmailForCache).filter(Boolean).slice(0, 80),
    };
    localStorage.setItem(INBOX_CACHE_KEY, JSON.stringify(payload));
  } catch (err) {
    console.warn("Could not save inbox cache", err);
  }
}

function getCurrentInboxEmails() {
  return Array.from(document.querySelectorAll("#inbox .email-card[data-id]"))
    .map(card => emailStore[card.getAttribute("data-id")])
    .filter(Boolean);
}

function persistCurrentInboxState() {
  saveInboxCache({
    emails: getCurrentInboxEmails(),
    snoozed: Array.from(snoozedStore.values()),
    scheduled: Array.from(scheduledStore.values()),
  });
}

function restoreCachedInbox() {
  try {
    const raw = localStorage.getItem(INBOX_CACHE_KEY);
    if (!raw) return false;
    const cached = JSON.parse(raw);
    if (!cached?.saved_at || Date.now() - cached.saved_at > INBOX_CACHE_TTL_MS) return false;

    resetInbox();
    rememberInboxOrder([...(cached.emails || []), ...(cached.snoozed || []), ...(cached.scheduled || [])]);
    setSnoozedEmails(cached.snoozed || []);
    setScheduledEmails(cached.scheduled || []);
    appendEmails(cached.emails || []);
    showStatus("Restored last inbox. Refreshing quietly...");
    return true;
  } catch (err) {
    console.warn("Could not restore inbox cache", err);
    return false;
  }
}

async function fetchJson(path, options = {}) {
  const url = `${API}${path}`;

  try {
    const res = await fetch(url, {
      credentials: "include",
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    return { res, data };
  } catch (err) {
    throw new Error(`${path} failed to reach ${API}: ${err.message}`);
  }
}

function setScheduledEmails(emails) {
  scheduledStore.clear();

  (emails || []).forEach(email => {
    if (!email || !email.id) return;
    rememberInboxOrder([email]);
    scheduledStore.set(email.id, email);
    snoozedStore.delete(email.id);
    emailStore[email.id] = email;
    document.querySelector(`#inbox [data-id="${email.id}"]`)?.remove();
    renderedEmailIds.delete(email.id);
    renderedThreadIds.delete(getThreadKey(email));
  });

  renderScheduledEmails();
}

function appendScheduledEmails(emails) {
  (emails || []).forEach(email => {
    if (!email || !email.id) return;
    rememberInboxOrder([email]);
    scheduledStore.set(email.id, email);
    snoozedStore.delete(email.id);
    emailStore[email.id] = email;
    document.querySelector(`#inbox [data-id="${email.id}"]`)?.remove();
    renderedEmailIds.delete(email.id);
    renderedThreadIds.delete(getThreadKey(email));
  });

  renderScheduledEmails();
}

function renderScheduledEmails() {
  const container = document.getElementById("scheduledList");
  if (!container) return;

  container.innerHTML = "";

  scheduledStore.forEach(email => {
    if (!email || !email.id) return;

    // ❌ DO NOT DUPLICATE
    if (container.querySelector(`[data-id="${email.id}"]`)) return;

    const card = document.createElement("div");
    card.className = "card email-card";
    card.setAttribute("data-id", email.id);

    card.innerHTML = `
      <div class="email-main">
        <h3>${email.subject}</h3>
        <p><strong>From:</strong> ${email.sender}</p>

        <div id="actions-${email.id}" class="action-row">
          <span class="chip-success">✔ Scheduled</span>

          ${email.reply_sent ? `
            <span class="label-chip" style="border-color:#10b981;color:#10b981;">Reply Sent</span>
            <button class="btn btn-primary" onclick="toggleReply('${email.id}')">
              View Thread
            </button>
          ` : email.reply ? `
            <button class="btn btn-primary" onclick="toggleReply('${email.id}')">
              View Reply
            </button>
          ` : `
            <button type="button" class="btn btn-secondary" data-action="generate-reply" data-email-id="${escapeHTML(email.id || "")}">
              Generate Reply
            </button>
          `}

          ${email.event_link ? `
            <button class="btn btn-primary"
              onclick="openEvent('${email.event_link}')">
              Open
            </button>
          ` : ""}

          <button class="btn btn-secondary"
            onclick="cancelSchedule('${email.id}')">
            Cancel
          </button>
        </div>

        ${renderReplyBox(email)}
      </div>
    `;

    container.appendChild(card);
  });
}

async function cancelSchedule(id) {
  try {
    const res = await fetch(`${API}/email/cancel-schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id })
    });

    if (!res.ok) throw new Error("Cancel failed");
    scheduledStore.delete(id);

    // ✅ REMOVE ONLY THAT CARD
    document.querySelector(`#scheduledList [data-id="${id}"]`)?.remove();

    // ✅ restore email to inbox
    const email = emailStore[id] || snoozedStore.get(id);
    if (!email) throw new Error("Email not found");
    if (email) {
      email.action_bucket = null;
      appendEmails([email]);
      persistCurrentInboxState();
    }

    showStatus("❌ Schedule cancelled");

  } catch (err) {
    console.error(err);
    showStatus("❌ Cancel failed");
  }
}

function handleScheduled(msg) {
  const email = emailStore[msg.email_id];
  if (!email) return;

  email.action_bucket = "SCHEDULED";
  email.event_link = msg.event_link;

  removeEmailFromUI(msg.email_id);

  appendScheduledEmails([email]);
  persistCurrentInboxState();
}

function handleCancel(msg) {
  const email = emailStore[msg.email_id];
  if (!email) return;

  email.action_bucket = null;

  removeEmailFromUI(msg.email_id);

  appendEmails([email]);
  persistCurrentInboxState();
}

function handleUnsnooze(msg) {
  const email = snoozedStore.get(msg.email_id) || emailStore[msg.email_id];
  if (!email) return;

  delete email.remind_at;
  snoozedStore.delete(msg.email_id);

  removeEmailFromUI(msg.email_id);
  renderSnoozedEmails();

  appendEmails([email]);
  persistCurrentInboxState();
}

function handleSnooze(msg) {
  const email = emailStore[msg.email_id];
  if (!email) return;

  email.remind_at = msg.remind_at;

  removeEmailFromUI(msg.email_id);
  appendSnoozedEmails([email]);
  persistCurrentInboxState();
}

let socket;

const WS_URL = API.replace("https://", "wss://").replace("http://", "ws://");

function connectWS() {
  socket = new WebSocket(`${WS_URL}/ws`);

  socket.onmessage = (event) => {
    const msg = JSON.parse(event.data);

    console.log("WS:", msg); // DEBUG

    switch (msg.type) {
      case "SCHEDULED":
        handleScheduled(msg);
        break;

      case "CANCEL_SCHEDULED":
        handleCancel(msg);
        break;

      case "SNOOZED":
        handleSnooze(msg);
        break;

      case "UNSNOOZED":
        handleUnsnooze(msg);
        break;
    }
  };

  socket.onerror = (err) => {
    console.error("WS error:", err);
  };

  socket.onclose = () => {
    console.warn("WS disconnected. Reconnecting...");
    setTimeout(connectWS, 2000);
  };
}

// function markAsScheduled(id) {
//   const email = emailStore[id];
//   if (!email) return;

//   // 🔥 REMOVE ANY EXISTING SCHEDULED EMAIL
//   // Object.values(emailStore).forEach(e => {
//   //   if (e.action_bucket === "SCHEDULED") {
//   //     e.action_bucket = null;
//   //   }
//   // });

//   email.action_bucket = "SCHEDULED";

//   removeEmailFromUI(id);

//   appendScheduledEmails([email]);

//   showStatus("📅 Email scheduled");
// }

// ----------------------
// LOAD EMAILS  (unchanged)
// ----------------------
loadEmailsBtn?.addEventListener("click", loadEmails);

async function loadEmails(options = {}) {
  const background = !!options.background;
  try {
    if (!background) showStatus("Loading emails...");

    const { res: emailsRes, data } = await fetchJson("/emails?limit=500");
    if (!emailsRes.ok) throw new Error(data.detail || "Failed to load emails");

    console.log("RAW API:", data);

    if (!background || !renderedEmailIds.size) {
      resetInbox();
    }

    let snoozedData = { emails: [] };
    let scheduledData = { emails: [] };
    const [snoozedResult, scheduledResult] = await Promise.allSettled([
      fetchJson("/emails/snoozed"),
      fetchJson("/emails/scheduled"),
    ]);

    if (snoozedResult.status === "fulfilled" && snoozedResult.value.res.ok) {
      snoozedData = snoozedResult.value.data || { emails: [] };
    } else {
      console.warn("Snoozed emails unavailable during inbox load", snoozedResult);
    }

    if (scheduledResult.status === "fulfilled" && scheduledResult.value.res.ok) {
      scheduledData = scheduledResult.value.data || { emails: [] };
    } else {
      console.warn("Scheduled emails unavailable during inbox load", scheduledResult);
    }

    const allEmails = normalizeEmailList(data);
    rememberInboxOrder([
      ...allEmails,
      ...(snoozedData.emails || []),
      ...(scheduledData.emails || []),
    ]);

    setSnoozedEmails(snoozedData.emails || []);
    setScheduledEmails(scheduledData.emails || []);

    const snoozedIds = new Set((snoozedData.emails || []).map(email => email.id));
    const scheduledIds = new Set((scheduledData.emails || []).map(email => email.id));
    const emails = allEmails
      .filter(email => !snoozedIds.has(email.id) && !scheduledIds.has(email.id));

    appendEmails(emails);
    saveInboxCache({
      emails,
      snoozed: snoozedData.emails || [],
      scheduled: scheduledData.emails || [],
    });
    Promise.allSettled([
      loadPendingActions(),
      loadObservabilitySummary(),
      loadTasks(),
      loadWorkflowLogs(),
      loadContactMemories(),
    ]);
    showStatus(background ? `Inbox updated quietly (${emails.length} emails)` : `Loaded ${emails.length} emails`);
  } catch (err) {
    console.error(err);
    if (!background) {
      const restored = renderedEmailIds.size || restoreCachedInbox();
      showStatus(restored
        ? "Backend is unreachable. Showing the last saved inbox."
        : "Failed to load emails: " + err.message);
    } else {
      console.warn("Background inbox refresh failed:", err);
    }
  }
}

async function unsnoozeEmail(id) {
  try {
    const res = await fetch(`${API}/email/unsnooze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id })
    });

    if (!res.ok) throw new Error("Unsnooze failed");

    const email = snoozedStore.get(id) || emailStore[id];

    // 🔥 REMOVE from snoozed UI
    snoozedStore.delete(id);
    renderSnoozedEmails();
    document.querySelectorAll(`#inbox [data-id="${id}"], #snoozedList [data-id="${id}"]`)
      .forEach(card => card.remove());
    renderedEmailIds.delete(id);

    // 🔥 ADD BACK to inbox WITHOUT reload
    if (email) {
      delete email.remind_at;
      appendEmails([email]);
      persistCurrentInboxState();
    }

    showStatus("✅ Email unsnoozed");

  } catch (err) {
    console.error(err);
    showStatus("❌ Unsnooze failed");
  }
}

// async function snoozeCustom(id) {
//   const input = document.getElementById(`custom-time-${id}`);
//   const value = input?.value;

//   if (!value) {
//     showStatus("Please select a date and time.");
//     return;
//   }

//   showStatus("Setting custom reminder...");

//   try {
//     const res = await fetch(`${API}/email/snooze`, {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       credentials: "include",
//       body: JSON.stringify({
//         id,
//         custom_time: value
//       }),
//     });

//     const data = await res.json();
//     if (!res.ok) throw new Error(data.detail);

//     showStatus(`⏰ Snoozed until ${new Date(value).toLocaleString()}`);

//   } catch (err) {
//     showStatus("Custom snooze failed: " + err.message);
//   }
// }

// ── Meeting detection — uses LLM flag from backend ───────────────────────
// function needsMeeting(email) {
//   return !!email.needs_meeting;
// }

// ── processEmail ─────────────────────────────────────────────────────────
async function processEmail(id) {
  if (isProcessing) return; // 🔥 BLOCK REFRESH INTERFERENCE
  isProcessing = true;

  const actionDiv = document.getElementById(`actions-${id}`);
  const replyBox = document.getElementById(`reply-${id}`);
  const instructions = document.getElementById(`prompt-${id}`)?.value?.trim() || "";

  if (actionDiv) {
    actionDiv.innerHTML = `
      <button class="btn btn-primary" disabled>
        Generating...
      </button>
    `;
  }

  try {
    const res = await fetch(`${API}/email/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id, instructions })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    emailStore[id] = {
  ...data.email,
  reply: data.reply
};

    if (scheduledStore.has(id)) {
      scheduledStore.set(id, emailStore[id]);
      renderScheduledEmails();
    } else {
      renderActions(emailStore[id]);
    }

    const activeReplyBox = document.getElementById(`reply-${id}`);
    if (activeReplyBox) {
      const textarea = activeReplyBox.querySelector(".reply-body");
      if (textarea) textarea.value = data.reply || "";
      activeReplyBox.classList.remove("hidden");
    }

    showStatus("Reply generated");

  } catch (err) {
    console.error(err);
    showStatus("Reply generation failed");
    renderActions(emailStore[id]);
  } finally {
    isProcessing = false;
  }
}

async function adjustReply(id) {
  if (isProcessing) return;
  isProcessing = true;

  const instructions = document.getElementById(`prompt-${id}`)?.value?.trim() || "";
  const adjustBtn = document.getElementById(`adjust-${id}`);
  const previousText = adjustBtn?.textContent || "Adjust Reply";

  if (adjustBtn) {
    adjustBtn.disabled = true;
    adjustBtn.textContent = "Adjusting...";
  }

  try {
    const res = await fetch(`${API}/email/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id, instructions })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    emailStore[id] = {
      ...data.email,
      reply: data.reply
    };

    if (scheduledStore.has(id)) {
      scheduledStore.set(id, emailStore[id]);
      renderScheduledEmails();
    } else {
      renderActions(emailStore[id]);
    }

    const activeReplyBox = document.getElementById(`reply-${id}`);
    if (activeReplyBox) {
      const textarea = activeReplyBox.querySelector(".reply-body");
      if (textarea) textarea.value = data.reply || "";
      activeReplyBox.classList.remove("hidden");
    }

    showStatus("Reply adjusted");
  } catch (err) {
    console.error(err);
    showStatus("Reply adjustment failed");
  } finally {
    if (adjustBtn) {
      adjustBtn.disabled = false;
      adjustBtn.textContent = previousText;
    }
    isProcessing = false;
  }
}

async function checkAuthOnLoad() {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);

  try {
    const res = await fetch(`${API}/auth/status`, {
      method: "GET",
      credentials: "include",
      signal: controller.signal
    });

    const data = await res.json();

    if (data.authenticated) {
      authInitialized = true;
      sessionStorage.setItem("authInitiated", "true");

      updateAuthUI(true);
      const restored = restoreCachedInbox();
      await loadEmails({ background: restored });
      return;
    }

    authInitialized = false;
    sessionStorage.removeItem("authInitiated");
    updateAuthUI(false);

  } catch (err) {
    console.error("Auth check failed:", err);
    updateAuthUI(false);
  } finally {
    clearTimeout(timeoutId);
    document.body.classList.remove("auth-loading");
  }
}

// ── snoozeEmail ───────────────────────────────────────────────────────────
async function snoozeEmail(id, duration) {
  showStatus("⏳ Snoozing...");

  try {
    const res = await fetch(`${API}/email/snooze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id, duration })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    const email = emailStore[id] || snoozedStore.get(id);

    // 🔥 REMOVE from inbox (no full refresh)
    if (!email) throw new Error("Email not found");
    removeEmailFromUI(id);
    scheduledStore.delete(id);

    // 🔥 ADD to snoozed list
    appendSnoozedEmails([{
      ...email,
      remind_at: data.remind_at
    }]);
    persistCurrentInboxState();
    await loadWorkflowLogs();

    showStatus("⏰ Snoozed");

  } catch (err) {
    console.error(err);
    showStatus("❌ Snooze failed");
  }
}

// ── renderSnooze ──────────────────────────────────────────────────────────
function renderSnooze(id) {
  const emailId = escapeHTML(id || "");
  return `
    <div style="position:relative;">
      <button type="button" class="btn btn-secondary" data-action="snooze-menu" data-email-id="${emailId}">
        Snooze
      </button>
      <div id="snooze-dropdown-${emailId}" class="snooze-dropdown hidden"
        style="position:absolute;background:#1f2937;padding:8px;border-radius:8px;
               top:40px;z-index:10;min-width:150px;box-shadow:0 4px 12px rgba(0,0,0,0.4);">
        <div data-action="snooze" data-email-id="${emailId}" data-duration="180"
          style="padding:6px 10px;cursor:pointer;border-radius:4px;"
          onmouseover="this.style.background='#374151'"
          onmouseout="this.style.background='transparent'">In 3 hours</div>
        <div data-action="snooze" data-email-id="${emailId}" data-duration="1440"
          style="padding:6px 10px;cursor:pointer;border-radius:4px;"
          onmouseover="this.style.background='#374151'"
          onmouseout="this.style.background='transparent'">Tomorrow</div>
        <div data-action="snooze" data-email-id="${emailId}" data-duration="10080"
          style="padding:6px 10px;cursor:pointer;border-radius:4px;"
          onmouseover="this.style.background='#374151'"
          onmouseout="this.style.background='transparent'">Next week</div>
      </div>
    </div>`;
}

// ----------------------
// SEND REPLY  — shows follow-up confirmation (Tier-1)
// ----------------------
async function sendReply(id) {
  const email    = emailStore[id];
  const replyBox = document.getElementById(`reply-${id}`);
  const body     = replyBox?.querySelector(".reply-body")?.value?.trim();

  if (!email) { showStatus("Email not found. Reload and try again."); return; }
  if (email.reply_sent) { showStatus("Reply already sent."); return; }
  if (!body) { showStatus("Reply is empty."); return; }

  const sendBtn = document.getElementById(`send-${id}`);
  if (sendBtn) {
    sendBtn.disabled = true;
    sendBtn.textContent = "Sending...";
  }

  try {
    const res = await fetch(`${API}/send-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        id,
        to:      email.sender,
        subject: `Re: ${email.subject}`,
        body,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    email.reply = body;
    email.reply_sent = true;
    email.reply_sent_at = new Date().toISOString();
    email.action_bucket = "WAITING";
    email.conversation_thread = [
      ...(getConversationThread(email).filter(message => message.role !== "sent")),
      {
        role: "sent",
        sender: "You",
        subject: `Re: ${email.subject}`,
        body,
        sent_at: email.reply_sent_at,
      },
    ];

    if (scheduledStore.has(id)) {
      scheduledStore.set(id, email);
      renderScheduledEmails();
    } else {
      const card = document.querySelector(`[data-id="${id}"]`);
      const replyContainer = document.getElementById(`reply-${id}`);
      if (replyContainer) replyContainer.outerHTML = renderReplyBox(email);
      renderActions(email, card || document);
    }

    // Mark email as WAITING in the bucket chip
    const bucketSlot = document.getElementById(`bucket-slot-${id}`);
    if (bucketSlot) {
      bucketSlot.innerHTML = `<span class="label-chip" style="border-color:#f59e0b;color:#f59e0b;">⏳ Waiting</span>`;
    }

    // Show follow-up confirmation
    const followupMsg = data.followup_scheduled
      ? ` A follow-up reminder has been set for 48 hours from now.`
      : "";

    if (sendBtn) {
      sendBtn.textContent = "Sent";
      sendBtn.disabled = true;
    }
    showStatus(`Reply sent to ${email.sender}.${followupMsg}`);

    // Optionally surface a View Reminder link
    if (data.followup_link) {
      const actionDiv = document.getElementById(`actions-${id}`);
      if (actionDiv) {
        actionDiv.innerHTML += `
          <a href="${data.followup_link}" target="_blank"
             style="display:inline-block;margin-top:8px;color:#60a5fa;font-size:0.85rem;">
            ⏰ View Follow-up Reminder ↗
          </a>`;
      }
    }

  } catch (err) {
    console.error(err);
    if (sendBtn) {
      sendBtn.disabled = false;
      sendBtn.textContent = "Send";
    }
    showStatus("Failed to send: " + err.message);
  }
}

// ----------------------
// COPY REPLY  (unchanged)
// ----------------------
function copyReply(id) {
  const text = document.getElementById(`reply-${id}`)?.querySelector(".reply-body")?.value || "";
  if (!text.trim()) {
    showStatus("Nothing to copy.");
    return;
  }

  if (navigator.clipboard?.writeText) {
    navigator.clipboard
      .writeText(text)
      .then(() => showCopied(id))
      .catch(() => fallbackCopy(text));
    return;
  }

  fallbackCopy(text);
}

function showCopied(id) {
  const copyBtn = document.getElementById(`copy-${id}`);
  if (copyBtn) {
    const previousText = copyBtn.textContent;
    copyBtn.textContent = "Copied";
    setTimeout(() => {
      copyBtn.textContent = previousText || "Copy";
    }, 1600);
  }
  showStatus("Copied");
}

function fallbackCopy(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();

  try {
    document.execCommand("copy");
    showStatus("Reply copied to clipboard.");
  } catch (err) {
    console.error(err);
    showStatus("Copy failed. Select the reply text and copy manually.");
  } finally {
    textarea.remove();
  }
}

// ----------------------
// SNOOZE  (Tier-1)
// ----------------------


function toggleSnoozeDropdown(id) {
    const dropdown = document.getElementById(`snooze-dropdown-${id}`);
    if (!dropdown) return;

    const emailCard = dropdown.closest('.email-card');
    const isOpening = dropdown.classList.contains('hidden');

    // Helper: reset any other open snooze dropdowns & restore their cards
    if (isOpening) {
      document.querySelectorAll('.snooze-dropdown:not(.hidden)').forEach(dd => {
        if (dd.id !== dropdown.id) {
          dd.classList.add('hidden');
          const otherCard = dd.closest('.email-card');
          if (otherCard) {
            // restore original card styles
            if (otherCard.dataset.origPaddingBottom !== undefined) {
              otherCard.style.paddingBottom = otherCard.dataset.origPaddingBottom;
              otherCard.style.overflow = otherCard.dataset.origOverflow || '';
              delete otherCard.dataset.origPaddingBottom;
              delete otherCard.dataset.origOverflow;
            } else {
              otherCard.style.paddingBottom = '';
              otherCard.style.overflow = '';
            }
          }
        }
      });
    }

    if (isOpening) {
      // Show dropdown
      dropdown.classList.remove('hidden');
      if (emailCard) {
        // Store original styles before modification
        if (emailCard.dataset.origPaddingBottom === undefined) {
          emailCard.dataset.origPaddingBottom = emailCard.style.paddingBottom || '';
          emailCard.dataset.origOverflow = emailCard.style.overflow || '';
        }
        // STRETCH vertically: add extra bottom padding and ensure overflow visible
        emailCard.style.paddingBottom = "130px";
        emailCard.style.overflow = "visible";
        // Also ensure the card itself does not clip absolute dropdowns
        emailCard.style.position = "relative";
        // Smooth scroll to bring dropdown into view (prevents cutoff at bottom of viewport)
        dropdown.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    } else {
      // Hide dropdown and restore original card dimensions
      dropdown.classList.add('hidden');
      if (emailCard) {
        if (emailCard.dataset.origPaddingBottom !== undefined) {
          emailCard.style.paddingBottom = emailCard.dataset.origPaddingBottom;
          emailCard.style.overflow = emailCard.dataset.origOverflow;
          delete emailCard.dataset.origPaddingBottom;
          delete emailCard.dataset.origOverflow;
        } else {
          emailCard.style.paddingBottom = '';
          emailCard.style.overflow = '';
        }
      }
    }
  }

// ----------------------
// RENDER EMAILS
// ----------------------
// ONLY CHANGE: restore persisted state

// FIND appendEmails() and replace ONLY that function






function toggleReply(id) {
  const box = document.getElementById(`reply-${id}`);
  if (!box) return;

  const textarea = box.querySelector(".reply-body");
  const email = emailStore[id];

  if (textarea && email?.reply && !textarea.value.trim()) {
    textarea.value = email.reply;
  }

  box.classList.toggle("hidden");
}

// function appendEmails(emails) {
//   // ... existing loop ...
  
//   // Restore State Logic
//   if (email.action_bucket) {
//     const bucketSlot = document.getElementById(`bucket-slot-${email.id}`);
//     if (bucketSlot) {
//       bucketSlot.innerHTML = getBucketChip(email.action_bucket, BUCKET_META[email.action_bucket]);
//     }
//   }

//   // Restore Reply Box if already WAITING or REPLY_READY
//   if (email.action_bucket === "WAITING" || email.action_bucket === "NEEDS_REPLY" || email.action_bucket === "NEEDS_ACTION") {
//      // ... logic to show reply box if content exists ...
//   }
  
//   // Restore Scheduled UI
//   if (email.action_bucket === "SCHEDULED") {
//      const actionDiv = document.getElementById(`actions-${email.id}`);
//      if (actionDiv) {
//         actionDiv.innerHTML = `<button type="button" class="btn btn-primary">Scheduled</button>`;
//         if (email.event_link) {
//            actionDiv.innerHTML += `<a href="${email.event_link}" target="_blank">View Event ↗</a>`;
//         }
//      }
//   }
  
//   // Restore Waiting UI
//   if (email.action_bucket === "WAITING") {
//      const actionDiv = document.getElementById(`actions-${email.id}`);
//      if (actionDiv) {
//         actionDiv.innerHTML = `<button type="button" class="btn btn-secondary">Waiting...</button>`;
//      }
//      const bucketSlot = document.getElementById(`bucket-slot-${email.id}`);
//      if (bucketSlot) {
//         bucketSlot.innerHTML = `<span class="label-chip" style="border-color:#f59e0b;color:#f59e0b;">⏳ Waiting</span>`;
//      }
//   }
// }

function setSnoozedEmails(emails) {
  snoozedStore.clear();

  (emails || []).forEach(email => {
    if (!email || !email.id) return;
    rememberInboxOrder([email]);
    snoozedStore.set(email.id, email);
    scheduledStore.delete(email.id);
    emailStore[email.id] = email;
    document.querySelector(`#inbox [data-id="${email.id}"]`)?.remove();
    renderedEmailIds.delete(email.id);
  });

  renderSnoozedEmails();
}

function appendSnoozedEmails(emails) {
  (emails || []).forEach(email => {
    if (!email || !email.id) return;
    rememberInboxOrder([email]);
    snoozedStore.set(email.id, email);
    scheduledStore.delete(email.id);
    emailStore[email.id] = email;
    document.querySelector(`#inbox [data-id="${email.id}"]`)?.remove();
    renderedEmailIds.delete(email.id);
  });

  renderSnoozedEmails();
}

function renderSnoozedEmails() {
  const container = document.getElementById("snoozedList");
  if (!container) return;

  container.innerHTML = "";

  snoozedStore.forEach(email => {
    const div = document.createElement("div");
    div.className = "card email-card";
    div.setAttribute("data-id", email.id);

    div.innerHTML = `
      <h3>${email.subject}</h3>
      <p><strong>From:</strong> ${email.sender}</p>

      <p style="margin-top:8px;">
        ⏰ Snoozed until: ${new Date(email.remind_at).toLocaleString()}
      </p>

      <button class="btn btn-secondary"
        onclick="unsnoozeEmail('${email.id}')">
        Unsnooze
      </button>
    `;

    container.appendChild(div);
  });
}

function removeEmailFromUI(id) {
  const email = emailStore[id];
  if (email) renderedThreadIds.delete(getThreadKey(email));
  const selectors = [
    `#inbox [data-id="${id}"]`,
    `#scheduledList [data-id="${id}"]`,
    `#snoozedList [data-id="${id}"]`
  ];

  selectors.forEach(sel => {
    const el = document.querySelector(sel);
    if (el) {
      el.classList.add("fade-out");
      setTimeout(() => el.remove(), 200);
    }
  });

  renderedEmailIds.delete(id);
}

function injectScrollButton() {
  if (document.getElementById("scrollToSnoozed")) return; // already injected

  const btn = document.createElement("button");
  btn.id        = "scrollToSnoozed";
  btn.type      = "button";
  btn.className = "btn btn-secondary";
  btn.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    opacity: 0.9;
  `;
  btn.innerHTML = "⏰ Snoozed";
  btn.addEventListener("click", () => {
    document.getElementById("snoozedList")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  document.body.appendChild(btn);
}

// ----------------------
// UI STATE  (unchanged)
// ----------------------
function updateAuthUI(isLoggedIn) {
  document.body.classList.remove("auth-loading");

  if (isLoggedIn) {
    loginBtn?.classList.add("hidden");
    demoOffer?.classList.add("hidden");

    logoutBtn?.classList.remove("hidden");

    authMessage?.classList.add("hidden");
    appContent?.classList.remove("hidden");

  } else {
    loginBtn?.classList.remove("hidden");
    demoOffer?.classList.remove("hidden");

    logoutBtn?.classList.add("hidden");

    authMessage?.classList.remove("hidden");
    appContent?.classList.add("hidden");
  }
}


// ----------------------
// RESET / UTIL  (unchanged)
// ----------------------
function resetInbox() {
  inbox.innerHTML = "";
  document.getElementById("scheduledList").innerHTML = "";
  snoozedStore.clear();
  scheduledStore.clear();
  renderSnoozedEmails();
  emailStore = {};
  renderedEmailIds.clear();
  renderedThreadIds.clear();
  inboxOrder.clear();
  nextInboxOrder = 0;
}

function resetDemoButton() {
  if (!demoBtn) return;
  demoBtn.disabled = false;
  demoBtn.textContent = "Use Demo Account";
}

function hideStatus() {
  statusMessage?.classList.add("hidden");
  if (statusMessage) statusMessage.textContent = "";

  const authStatus = document.getElementById("authStatus");
  if (authStatus) {
    authStatus.textContent = "";
    authStatus.classList.add("hidden");
  }
}

function showStatus(msg) {
  if (statusMessage) {
    statusMessage.textContent = msg;
    statusMessage.classList.remove("hidden");
  }

  if (appContent?.classList.contains("hidden") && authMessage) {
    let authStatus = document.getElementById("authStatus");
    if (!authStatus) {
      authStatus = document.createElement("p");
      authStatus.id = "authStatus";
      authStatus.className = "status";
      authMessage.appendChild(authStatus);
    }
    authStatus.textContent = msg;
    authStatus.classList.remove("hidden");
  }
}

function scrollToScheduled() {
  document.getElementById("scheduledList")?.scrollIntoView({ behavior: "smooth" });
}

function scrollToSnoozed() {
  document.getElementById("snoozedList")?.scrollIntoView({ behavior: "smooth" });
}

// async function snoozeEmail(emailId, duration) {
//     const response = await fetch(`${API_BASE}/email/snooze`, {
//         method: 'POST',
//         credentials: 'include',                // ← THE CRITICAL FIX
//         headers: { 'Content-Type': 'application/json' },
//         body: JSON.stringify({ email_id: emailId, duration_minutes: duration })
//     });
//     if (!response.ok) {
//         const err = await response.json().catch(() => ({}));
//         console.error('Snooze failed:', response.status, err);
//         alert('Failed to snooze email. Please try again.');
//         return;
//       }
//       // remove from UI immediately
//       document.getElementById(`email-${emailId}`)?.remove();
//   }

async function snoozeCustom(emailId) {
    const remindAt = document.getElementById('custom-snooze-time').value;
    const response = await fetch(`${API}/email/snooze`, {
        method: 'POST',
        credentials: 'include',                // ← THE CRITICAL FIX
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_id: emailId, remind_at: remindAt })
    });
    if (!response.ok) {
        console.error('Custom snooze failed:', response.status);
        return;
    }
    document.getElementById(`email-${emailId}`)?.remove();
    document.getElementById('snooze-modal')?.classList.add('hidden');
}

// function appendSnoozedEmails(emails) {
//   const snoozedList = document.getElementById("snoozedList");
//   if (!snoozedList) return;

//   snoozedList.innerHTML = "";

//   emails.forEach(email => {
//     const card = document.createElement("div");
//     card.className = "card email-card";

//     card.innerHTML = `
//       <div class="email-main">
//         <h3>${email.subject}</h3>
//         <p><strong>From:</strong> ${email.sender}</p>
//         <p>⏰ Snoozed until: ${new Date(email.remind_at).toLocaleString()}</p>

//         <button type="button" class="btn btn-secondary"
//                 onclick="unsnoozeEmail('${email.id}')">
//           🔄 Unsnooze
//         </button>
//       </div>
//     `;

//     snoozedList.appendChild(card);
//   });
// }

// ----------------------
// AUTO REFRESH (SNOOZE REAPPEAR FIX)
// ----------------------

let autoRefreshInterval = null;

function startAutoRefresh() {
  if (autoRefreshInterval) {
    clearInterval(autoRefreshInterval);
  }

  autoRefreshInterval = setInterval(async () => {
    try {
      // 🚫 DO NOT refresh if user not in app view
      if (appContent.classList.contains("hidden")) return;
      if (isProcessing) return;

      const [emailsRes, snoozedRes, scheduledRes] = await Promise.all([
        fetch(`${API}/emails?limit=500`, { credentials: "include" }),
        fetch(`${API}/emails/snoozed`, { credentials: "include" }),
        fetch(`${API}/emails/scheduled`, { credentials: "include" })
      ]);

      const scheduledData = await scheduledRes.json();

      const emailsData = await emailsRes.json();
      const snoozedData = await snoozedRes.json();

      if (!emailsRes.ok || !snoozedRes.ok || !scheduledRes.ok) return;

      // 🔥 SAFE REFRESH
      // 🔥 ONLY UPDATE IF NEW EMAILS (NO RESET)
      const allEmails = normalizeEmailList(emailsData);
      rememberInboxOrder([
        ...allEmails,
        ...(snoozedData.emails || []),
        ...(scheduledData.emails || []),
      ]);

      setSnoozedEmails(snoozedData.emails || []);
      appendScheduledEmails(scheduledData.emails || []);

      const snoozedIds = new Set((snoozedData.emails || []).map(email => email.id));
      const scheduledIds = new Set((scheduledData.emails || []).map(email => email.id));
      const emails = allEmails
        .filter(email => !snoozedIds.has(email.id) && !scheduledIds.has(email.id));

      emails.forEach(email => {
        if (!renderedEmailIds.has(email.id)) {
          appendEmails([email]);
        }
      });
      await loadPendingActions();
      await loadObservabilitySummary();
      await loadTasks();
      await loadWorkflowLogs();
      await loadContactMemories();
      persistCurrentInboxState();

    } catch (err) {
      console.error("Auto refresh failed:", err);
    }
  }, 15000); // slower = stable
}

// function removeEmailFromUI(id) {
//   const card = document.getElementById(`actions-${id}`)?.closest(".email-card");

//   if (card) {
//     card.classList.add("fade-out");

//     setTimeout(() => {
//       card.remove();
//       renderedEmailIds.delete(id);
//     }, 300);
//   }
// }

// const ws = new WebSocket("ws://127.0.0.1:10000/ws");

// ws.onopen = () => {
//   console.log("WS CONNECTED");

//   setInterval(() => {
//     ws.send("ping");
//   }, 20000);
// };

// ws.onmessage = (event) => {
//   console.log("WS EVENT:", event.data);
// };

window.processEmail = processEmail;
window.scheduleEmail = scheduleEmail;
window.confirmScheduled = confirmScheduled;
window.cancelSchedule = cancelSchedule;
window.openEvent = openEvent;
window.snoozeEmail = snoozeEmail;
window.unsnoozeEmail = unsnoozeEmail;
window.toggleSnoozeDropdown = toggleSnoozeDropdown;
window.toggleReply = toggleReply;
window.sendReply = sendReply;
window.adjustReply = adjustReply;
window.copyReply = copyReply;
