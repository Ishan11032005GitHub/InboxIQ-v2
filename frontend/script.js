const API = "http://127.0.0.1:10000";

// ----------------------
// ELEMENTS
// ----------------------
let renderedEmailIds = new Set();
const loginBtn      = document.getElementById("loginBtn");
const demoBtn       = document.getElementById("demoBtn");
const logoutBtn     = document.getElementById("logoutBtn");
const demoOffer     = document.getElementById("demoOffer");
const loadEmailsBtn = document.getElementById("loadEmails");
const inbox         = document.getElementById("inbox");
const statusMessage = document.getElementById("statusMessage");
const authMessage   = document.getElementById("authMessage");
const appContent    = document.getElementById("appContent");

// ----------------------
// STATE
// ----------------------
let emailStore = {};
console.log("✅ script loaded");

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
loginBtn?.addEventListener("click", () => {
  window.location.href = `${API}/auth/login`;
});

demoBtn?.addEventListener("click", async () => {
  try {
    console.log("🚀 Activating demo mode...");
    await fetch(`${API}/demo`, { credentials: "include" });
    updateAuthUI(true);
    resetInbox();
    await loadEmails();
    
    showStatus("Demo mode activated");
  } catch (err) {
    console.error(err);
    showStatus("Demo failed: " + err.message);
  }
});

logoutBtn?.addEventListener("click", async () => {
  await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
  resetInbox();
  updateAuthUI(false);
  showStatus("Logged out");
});

// ----------------------
// AUTH STATUS  (unchanged)
// ----------------------
let isCheckingAuth = false;

async function checkAuthStatus() {
  if (isCheckingAuth) return;
  isCheckingAuth = true;

  try {
    const res = await fetch(`${API}/auth/status`, { credentials: "include" });
    const data = await res.json();

    if (data.authenticated) {
      updateAuthUI(true);
      await loadEmails();
      startAutoRefresh();
    } else {
      updateAuthUI(false);
    }

  } catch (err) {
    console.error(err);
  }

  isCheckingAuth = false;
}

// ----------------------
// LOAD EMAILS  (unchanged)
// ----------------------
loadEmailsBtn?.addEventListener("click", loadEmails);

async function loadEmails() {
  try {
    const res = await fetch(`${API}/emails`, { credentials: "include" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    const snoozedRes = await fetch(`${API}/emails/snoozed`, {
      credentials: "include"
    });
    const snoozedData = await snoozedRes.json();

    resetInbox();

    appendEmails(data.emails || []);
    appendSnoozedEmails(snoozedData.emails || []);

    showStatus("Emails loaded");
  } catch (err) {
    console.error(err);
    showStatus(err.message);
  }
}

async function unsnoozeEmail(id) {
  await fetch(`${API}/email/unsnooze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ id })
  });

  loadEmails();
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

// ----------------------
// PROCESS EMAIL  — now surfaces action_bucket + follow-up hint
// ----------------------
async function processEmail(id) {
  const actionDiv  = document.getElementById(`actions-${id}`);
  const replyBox   = document.getElementById(`reply-${id}`);
  const bucketSlot = document.getElementById(`bucket-slot-${id}`);

  actionDiv.innerHTML = `<button class="btn">Processing...</button>`;

  try {
    const res  = await fetch(`${API}/email/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id }),
    });

    const data = await res.json();
    if (!res.ok) {
  console.error(data);
  actionDiv.innerHTML = `<button class="btn btn-danger">⚠️ Failed</button>`;
  showStatus("AI temporarily unavailable");
  return;
}

    // ── Update action-bucket chip ──────────────────────────────────────
    if (emailStore[id]) {
      if (data.action_bucket) emailStore[id].action_bucket = data.action_bucket;
      if (data.reply) emailStore[id].reply = data.reply;
    }

    if (data.action_bucket && data.bucket_meta && bucketSlot) {
      bucketSlot.innerHTML = getBucketChip(data.action_bucket, data.bucket_meta);
    }

    // ── Calendar path ──────────────────────────────────────────────────
    if (data.type === "calendar") {
      if (data.status === "done") {
        actionDiv.innerHTML = `
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
            <button class="btn btn-primary">📅 Scheduled</button>
            ${data.event_link
              ? `<a href="${data.event_link}" target="_blank"
                   style="color:#60a5fa;font-size:0.9rem;">View Event ↗</a>`
              : ""}
          </div>`;
      } else if (data.status === "needs_input") {
        actionDiv.innerHTML = `<button class="btn btn-primary">📅 Needs Time Input</button>`;
      } else if (data.status === "requires_auth") {
        actionDiv.innerHTML = `<button class="btn btn-danger">Login Required</button>`;
      } else {
        actionDiv.innerHTML = `<button class="btn btn-danger">Failed</button>`;
      }

    // ── Reply path ─────────────────────────────────────────────────────
    } else if (data.type === "reply") {
      actionDiv.innerHTML = `<button class="btn btn-secondary">✉️ Reply Ready</button>`;
      replyBox.classList.remove("hidden");
      replyBox.querySelector("textarea").value = data.reply || "";
    }

  } catch (err) {
    console.error(err);
    actionDiv.innerHTML = `<button class="btn btn-danger">Error</button>`;
    showStatus(err.message);
  }
}

// ----------------------
// SEND REPLY  — shows follow-up confirmation (Tier-1)
// ----------------------
async function sendReply(id) {
  const email    = emailStore[id];
  const replyBox = document.getElementById(`reply-${id}`);
  const body     = replyBox?.querySelector("textarea")?.value?.trim();

  if (!body) { showStatus("Reply is empty."); return; }

  try {
    const res = await fetch(`${API}/send-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        to:      email.sender,
        subject: `Re: ${email.subject}`,
        body,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    // Mark email as WAITING in the bucket chip
    const bucketSlot = document.getElementById(`bucket-slot-${id}`);
    if (bucketSlot) {
      bucketSlot.innerHTML = `<span class="label-chip" style="border-color:#f59e0b;color:#f59e0b;">⏳ Waiting</span>`;
    }

    // Show follow-up confirmation
    const followupMsg = data.followup_scheduled
      ? ` A follow-up reminder has been set for 48 hours from now.`
      : "";

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
    showStatus("Failed to send: " + err.message);
  }
}

// ----------------------
// COPY REPLY  (unchanged)
// ----------------------
function copyReply(id) {
  const text = document.getElementById(`reply-${id}`)?.querySelector("textarea")?.value || "";
  navigator.clipboard.writeText(text).then(() => showStatus("Reply copied to clipboard."));
}

// ----------------------
// SNOOZE  (Tier-1)
// ----------------------
async function snoozeEmail(id, duration) {
  showStatus("Snoozing...");

  try {
    const res = await fetch(`${API}/email/snooze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id, duration }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    removeEmailFromUI(id);

    // 🔥 instant reload to move it to snoozed section
    setTimeout(loadEmails, 300);

  } catch (err) {
    console.error(err);
    showStatus("Snooze failed: " + err.message);
  }
}

function toggleSnoozeDropdown(id) {
  const dropdown = document.getElementById(`snooze-dropdown-${id}`);
  if (dropdown) dropdown.classList.toggle("hidden");
}

// ----------------------
// RENDER EMAILS
// ----------------------
// ONLY CHANGE: restore persisted state

// FIND appendEmails() and replace ONLY that function

/*
function appendEmails(emails) {
  if (!inbox) return;

  emails.forEach(email => {
    if (renderedEmailIds.has(email.id)) return;

    renderedEmailIds.add(email.id);
    emailStore[email.id] = email;

    const label = email.label || "general";
    const priority = email.priority || "low";

    const card = document.createElement("div");
    card.className = "card email-card";
    card.setAttribute("data-id", email.id);

    card.innerHTML = `
      <div class="email-main">

        <div class="email-top">
          <h3>${email.subject}</h3>
          ${getLabelChip(label)}
          ${getPriorityChip(priority)}
          <span id="bucket-slot-${email.id}"></span>
        </div>

        <p><strong>From:</strong> ${email.sender}</p>

        <div id="actions-${email.id}">
          <button onclick="processEmail('${email.id}')">Analyze</button>
        </div>

        <div class="reply-box hidden" id="reply-${email.id}">
          <textarea></textarea>
          <button onclick="sendReply('${email.id}')">Send</button>
        </div>

      </div>
    `;

    inbox.appendChild(card);

    // ✅ RESTORE STATE

    // restore reply
    if (email.reply) {
      const replyBox = document.getElementById(`reply-${email.id}`);
      replyBox.classList.remove("hidden");
      replyBox.querySelector("textarea").value = email.reply;
    }

    // restore scheduled
    if (email.action_bucket === "SCHEDULED") {
      const actionDiv = document.getElementById(`actions-${email.id}`);
      actionDiv.innerHTML = `<button>📅 Scheduled</button>`;
    }
  });
}
*/

function appendEmails(emails) {
  if (!inbox) return;

  emails.forEach(email => {
    if (renderedEmailIds.has(email.id)) return;

    renderedEmailIds.add(email.id);
    emailStore[email.id] = email;

    const label = email.label || "general";
    const priority = email.priority || "low";

    const card = document.createElement("div");
    card.className = "card email-card";
    card.setAttribute("data-id", email.id);

    card.innerHTML = `
      <div class="email-main">

        <div class="email-top">
          <h3 class="email-subject">${email.subject || "(No Subject)"}</h3>
          <div style="display:flex;gap:6px;flex-wrap:wrap;">
            ${getLabelChip(label)}
            ${getPriorityChip(priority)}
            <span id="bucket-slot-${email.id}"></span>
          </div>
        </div>

        <p class="email-meta">
          <strong>From:</strong> ${email.sender || "Unknown"}
        </p>

        <div class="email-body">
          <details>
            <summary>View message</summary>
            <p>${(email.body || "").replace(/\n/g, "<br>")}</p>
          </details>
        </div>

        <!-- 🔥 ALWAYS START WITH ANALYZE -->
        <div id="actions-${email.id}" style="margin-top:14px;display:flex;gap:8px;">
          <button class="btn btn-secondary" onclick="processEmail('${email.id}')">
            Analyze
          </button>

          <button class="btn btn-secondary"
              onclick="toggleSnoozeDropdown('${email.id}')"
              title="Snooze this email">
              ⏰ Snooze
          </button>
        </div>

        <!-- 🔥 ALWAYS HIDDEN INITIALLY -->
        <div class="reply-box hidden" id="reply-${email.id}">
          <textarea placeholder="AI-generated reply will appear here..."></textarea>
          <div class="reply-actions">
            <button class="btn btn-success" onclick="sendReply('${email.id}')">Send Reply</button>
            <button class="btn btn-secondary" onclick="copyReply('${email.id}')">Copy</button>
          </div>
        </div>

      </div>
    `;

    inbox.appendChild(card);
    // ✅ RESTORE STATE (CRITICAL FIX)

// restore reply
if (email.reply) {
  const replyBox = document.getElementById(`reply-${email.id}`);
  replyBox.classList.remove("hidden");
  replyBox.querySelector("textarea").value = email.reply;

  const actionDiv = document.getElementById(`actions-${email.id}`);
  actionDiv.innerHTML = `<button class="btn btn-secondary">Reply Ready</button>`;
}

// restore scheduled
if (email.action_bucket === "SCHEDULED") {
  const actionDiv = document.getElementById(`actions-${email.id}`);
  actionDiv.innerHTML = `<button class="btn btn-primary">Scheduled</button>`;
}
  });
}

function appendSnoozedEmails(emails) {
  const snoozedList = document.getElementById("snoozedList");
  if (!snoozedList) return;

  snoozedList.innerHTML = "";

  emails.forEach(email => {
    const card = document.createElement("div");
    card.className = "card email-card";

    card.innerHTML = `
      <div class="email-main">
        <h3>${email.subject}</h3>
        <p><strong>From:</strong> ${email.sender}</p>
        <button class="btn btn-secondary"
          onclick="unsnoozeEmail('${email.id}')">
          Unsnooze
        </button>
      </div>
    `;

    snoozedList.appendChild(card);
  });
}

function removeEmailFromUI(id) {
  const card = document.querySelector(`[data-id="${id}"]`);
  if (!card) return;

  card.style.opacity = "0.3";

  setTimeout(() => {
    card.remove();
    renderedEmailIds.delete(id);
  }, 200);
}

// ----------------------
// UI STATE  (unchanged)
// ----------------------
function updateAuthUI(isAuthenticated) {
  if (isAuthenticated) {
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
  emailStore = {};
  renderedEmailIds.clear();
}

function showStatus(msg) {
  if (!statusMessage) return;
  statusMessage.textContent = msg;
  statusMessage.classList.remove("hidden");
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
    const response = await fetch(`${API_BASE}/email/snooze`, {
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

//         <button class="btn btn-secondary"
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
  if (autoRefreshInterval) return;

  autoRefreshInterval = setInterval(async () => {
    try {
      const res = await fetch(`${API}/emails`, { credentials: "include" });

      if (res.status === 401) return; // ❌ DO NOT flip UI

      const data = await res.json();
      if (!res.ok) return;

      const snoozedRes = await fetch(`${API}/emails/snoozed`, {
        credentials: "include"
      });
      const snoozedData = await snoozedRes.json();

      if (!document.hidden) {
  resetInbox();
}
      appendEmails(data.emails || []);
      appendSnoozedEmails(snoozedData.emails || []);

    } catch (err) {
      console.error(err);
    }
  }, 900000);
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

// ----------------------
// INIT
// ----------------------
checkAuthStatus();
