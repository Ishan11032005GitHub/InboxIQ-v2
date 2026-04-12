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
async function checkAuthStatus() {
  try {
    const res  = await fetch(`${API}/auth/status`, { credentials: "include" });
    const data = await res.json();
    console.log("🔐 AUTH STATUS:", data);
    if (data.authenticated) {
      updateAuthUI(true);
      await loadEmails();
      startAutoRefresh(); 
    } else {
      updateAuthUI(false);
    }
  } catch (err) {
    console.error("Auth check failed:", err);
    updateAuthUI(false);
  }
}

// ----------------------
// LOAD EMAILS  (unchanged)
// ----------------------
loadEmailsBtn?.addEventListener("click", loadEmails);

async function loadEmails() {
  showStatus("Loading emails...");
  try {
    const res  = await fetch(`${API}/emails`, { credentials: "include" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    resetInbox();
    appendEmails(data.emails || []);
    showStatus("Emails loaded");
  } catch (err) {
    console.error(err);
    showStatus(err.message);
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
    if (!res.ok) throw new Error(data.detail);

    // ── Update action-bucket chip ──────────────────────────────────────
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
  // Close the dropdown
  const dropdown = document.getElementById(`snooze-dropdown-${id}`);
  if (dropdown) dropdown.classList.add("hidden");

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

    // Format remind_at nicely
    const remindDate = data.remind_at
      ? new Date(data.remind_at).toLocaleString("en-IN", {
          dateStyle: "medium", timeStyle: "short",
        })
      : "";

    showStatus(`⏰ Snoozed! Reminder set for ${remindDate}.`);

    // Show a link to the calendar event
    if (data.event_link) {
      const actionDiv = document.getElementById(`actions-${id}`);
      if (actionDiv) {
        actionDiv.innerHTML += `
          <a href="${data.event_link}" target="_blank"
             style="display:inline-block;margin-top:8px;color:#60a5fa;font-size:0.85rem;">
            ⏰ View Snooze Reminder ↗
          </a>`;
      }
    }

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
function appendEmails(emails) {
  if (!inbox) return;

  emails.forEach(email => {
    if (renderedEmailIds.has(email.id)) return;

    renderedEmailIds.add(email.id);
    emailStore[email.id] = email;


    const label    = email.label    || "general";
    const priority = email.priority || "low";

    const card = document.createElement("div");
    card.className = "card email-card";

    card.innerHTML = `
      <div class="email-main">

        <!-- SUBJECT + CHIPS ROW -->
        <div class="email-top">
          <h3 class="email-subject">${email.subject || "(No Subject)"}</h3>
          <div style="display:flex;gap:6px;flex-wrap:wrap;flex-shrink:0;align-items:flex-start;">
            ${getLabelChip(label)}
            ${getPriorityChip(priority)}
            <!-- action-bucket chip filled in after Analyze is clicked -->
            <span id="bucket-slot-${email.id}"></span>
          </div>
        </div>

        <!-- SENDER -->
        <p class="email-meta" style="margin-bottom:0;">
          <strong>From:</strong> ${email.sender || "Unknown"}
        </p>

        <!-- BODY — collapsible -->
        <div class="email-body">
          <details>
            <summary>View message</summary>
            <p>${(email.body || "(No content)").replace(/\n/g, "<br>")}</p>
          </details>
        </div>

        <!-- ACTION BUTTONS -->
        <div id="actions-${email.id}" style="margin-top:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
          <button class="btn btn-secondary" onclick="processEmail('${email.id}')">
            Analyze
          </button>

          <!-- Snooze button + dropdown (Tier-1) -->
          <div style="position:relative;display:inline-block;">
            <button class="btn btn-secondary"
                    onclick="toggleSnoozeDropdown('${email.id}')"
                    title="Snooze this email">
              ⏰ Snooze
            </button>
            <div id="snooze-dropdown-${email.id}"
     class="hidden"
     style="
        margin-top:8px;
        background:var(--panel-2);
        border:1px solid var(--border);
        border-radius:12px;
        padding:6px;
        min-width:140px;
        box-shadow:var(--shadow);
     ">
    <button class="btn" onclick="snoozeEmail('${email.id}','3h')">⏱ In 3 hours</button>
  <button class="btn" onclick="snoozeEmail('${email.id}','tomorrow')">🌅 Tomorrow 9 AM</button>
  <button class="btn" onclick="snoozeEmail('${email.id}','next_week')">📅 Next week</button>

  <div style="height:1px;background:var(--border);margin:6px 0;"></div>

  <input type="datetime-local" id="custom-time-${email.id}" />

  <button class="btn" onclick="snoozeCustom('${email.id}')">
    ⏰ Set Custom Time
  </button>
</div>
          </div>
        </div>

        <!-- AI REPLY BOX -->
        <div class="reply-box hidden" id="reply-${email.id}">
          <textarea placeholder="AI-generated reply will appear here..."></textarea>
          <div class="reply-actions">
            <button class="btn btn-success"   onclick="sendReply('${email.id}')">Send Reply</button>
            <button class="btn btn-secondary" onclick="copyReply('${email.id}')">Copy</button>
          </div>
        </div>

      </div>
    `;

    inbox.appendChild(card);
  });
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

// async function snoozeEmail(id, duration) {
//   const dropdown = document.getElementById(`snooze-dropdown-${id}`);
//   if (dropdown) dropdown.classList.add("hidden");

//   showStatus("Snoozing...");

//   try {
//     const res = await fetch(`${API}/email/snooze`, {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       credentials: "include",
//       body: JSON.stringify({ id, duration }),
//     });

//     const data = await res.json();
//     if (!res.ok) throw new Error(data.detail);

//     const remindDate = data.remind_at
//       ? new Date(data.remind_at).toLocaleString("en-IN", {
//           dateStyle: "medium", timeStyle: "short",
//         })
//       : "";

//     showStatus(`⏰ Snoozed! Reminder set for ${remindDate}.`);

//     // ✅ FIX: REMOVE EMAIL FROM UI
//     const card = document.getElementById(`actions-${id}`)?.closest(".email-card");
//     if (card) {
//   card.remove();
//   renderedEmailIds.delete(id); // 🔥 CRITICAL FIX
// }

//   } catch (err) {
//     console.error(err);
//     showStatus("Snooze failed: " + err.message);
//   }
// }

async function snoozeCustom(id) {
  const input = document.getElementById(`custom-time-${id}`);
  const value = input?.value;

  if (!value) {
    showStatus("Please select a date and time.");
    return;
  }

  showStatus("Setting custom reminder...");

  try {
    const res = await fetch(`${API}/email/snooze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({
        id,
        custom_time: value
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    showStatus(`⏰ Snoozed until ${new Date(value).toLocaleString()}`);

    // ✅ FIX: SAME UI BEHAVIOR AS NORMAL SNOOZE
    const card = document.getElementById(`actions-${id}`)?.closest(".email-card");
    if (card) {
  card.remove();
  renderedEmailIds.delete(id); // 🔥 CRITICAL FIX
}

  } catch (err) {
    showStatus("Custom snooze failed: " + err.message);
  }
}

// ----------------------
// AUTO REFRESH (SNOOZE REAPPEAR FIX)
// ----------------------

let autoRefreshInterval = null;

function startAutoRefresh() {
  // avoid duplicate intervals
  if (autoRefreshInterval) return;

  autoRefreshInterval = setInterval(async () => {
    try {
      const res = await fetch(`${API}/emails`, { credentials: "include" });
      const data = await res.json();

      if (!res.ok) return;

      // simple strategy: reset + re-render
      const incoming = data.emails || [];
const incomingIds = new Set(incoming.map(e => e.id));

// ADD new
incoming.forEach(email => {
  if (!renderedEmailIds.has(email.id)) {
    appendEmails([email]);
  }
});

// REMOVE missing
renderedEmailIds.forEach(id => {
  if (!incomingIds.has(id)) {
    removeEmailFromUI(id);
  }
});

    } catch (err) {
      console.error("Auto refresh failed:", err);
    }
  }, 5000); // every 5 seconds
}

function removeEmailFromUI(id) {
  const card = document.getElementById(`actions-${id}`)?.closest(".email-card");

  if (card) {
    card.classList.add("fade-out");

    setTimeout(() => {
      card.remove();
      renderedEmailIds.delete(id);
    }, 300);
  }
}

// ----------------------
// INIT
// ----------------------
checkAuthStatus();