const API = "https://inboxiq-v2.onrender.com";

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

// let scheduledStore = {};

let isProcessing = false;

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

// ── Auth button handlers ──────────────────────────────────────────────────
loginBtn?.addEventListener("click", () => {
  authInitialized = true;
  sessionStorage.setItem("authInitiated", "true");
  window.location.href = `${API}/auth/login`;
});

document.getElementById("demoBtn").addEventListener("click", async () => {
  try {
    const res = await fetch(`${API}/demo`, {
      method: "GET",
      credentials: "include"
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    // 🔥 THIS IS WHAT YOU WERE MISSING
    authInitialized = true;
    sessionStorage.setItem("authInitiated", "true");

    updateAuthUI(true);

    showStatus("✅ Demo logged in");

    await loadEmails();

  } catch (e) {
    console.error(e);
    showStatus("❌ " + e.message);
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
  authInitialized = false;
  sessionStorage.removeItem("authInitiated");
  await fetch(`${API}/auth/logout`, { method: "POST", credentials: "include" });
  resetInbox();           // ← only place resetInbox should be called
  updateAuthUI(false);
  showStatus("Logged out");
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
      await loadEmails();
      return;
    }

    if (data.authenticated && data.user === "demo-user" && authInitialized) {
      updateAuthUI(true);
      // Don't re-fetch if cards are already rendered (survives Live Server reload)
      if (renderedEmailIds.size === 0) {
        await loadEmails();
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

async function scheduleEmail(id) {
  try {
    const email = emailStore[id];
    if (!email) return;

    // 🔥 ONLY OPEN CALENDAR (NO BACKEND CALL)
    const link = `https://calendar.google.com/calendar/r/eventedit?text=${encodeURIComponent(email.subject)}`;

    window.open(link, "_blank");

    // 🔥 Update UI ONLY
    updateEmailCardAfterCalendar(id);

    showStatus("📅 Calendar opened");

  } catch (err) {
    showStatus("❌ " + err.message);
  }
}

async function confirmScheduled(id) {
  try {
    const res = await fetch(`${API}/email/schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    showStatus("✅ Marked as scheduled");

  } catch (err) {
    showStatus("❌ " + err.message);
  }
}

function updateEmailCardAfterCalendar(id) {
  const actionDiv = document.getElementById(`actions-${id}`);
  if (!actionDiv) return;

  actionDiv.innerHTML = `
    <button class="btn btn-secondary" onclick="processEmail('${id}')">
      Analyze
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
function appendEmails(emails) {
  const inbox = document.getElementById("inbox");

  if (!Array.isArray(emails) || emails.length === 0) {
    inbox.innerHTML = "<p style='color:white'>No emails found</p>";
    return;
  }

  emails.forEach(email => {
    if (!email || !email.id || renderedEmailIds.has(email.id)) return;

    emailStore[email.id] = email;
    renderedEmailIds.add(email.id);

    const div = document.createElement("div");
    div.className = "card email-card";
    div.setAttribute("data-id", email.id);

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
        <div id="reply-${email.id}" class="hidden" style="margin-top:10px;">
          <textarea style="width:100%;height:80px;"></textarea>
          <div style="margin-top:6px;">
            <button onclick="sendReply('${email.id}')" class="btn btn-primary">Send</button>
            <button onclick="copyReply('${email.id}')" class="btn btn-secondary">Copy</button>
          </div>
        </div>
      </div>
    `;

    inbox.appendChild(div);

    // 🔥 CRITICAL: RENDER BUTTONS
    renderActions(email);
  });
}

function renderActions(email) {
  const actionDiv = document.getElementById(`actions-${email.id}`);
  if (!actionDiv) return;

  // 🔥 AFTER ANALYSIS STATE
  if (email.reply) {
  actionDiv.innerHTML = `
    <button class="btn btn-primary"
      onclick="toggleReply('${email.id}')">
      View Reply
    </button>
  `;
  return;
}

  // 🔥 DEFAULT STATE
  actionDiv.innerHTML = `
    <button class="btn btn-secondary"
      onclick="processEmail('${email.id}')">
      Analyze
    </button>

    <button class="btn btn-primary"
      onclick="toggleReply('${email.id}')">
      Reply
    </button>

    ${renderSnooze(email.id)}
  `;
}

function openEvent(link) {
  if (!link || !link.startsWith("http")) {
    showStatus("❌ Invalid event link");
    return;
  }
  window.open(link, "_blank");
}

function appendScheduledEmails(emails) {
  const container = document.getElementById("scheduledList");
  if (!container) return;

  emails.forEach(email => {
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

        <div class="action-row">
          <span class="chip-success">✔ Scheduled</span>

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

    // ✅ REMOVE ONLY THAT CARD
    document.querySelector(`#scheduledList [data-id="${id}"]`)?.remove();

    // ✅ restore email to inbox
    const email = emailStore[id];
    if (email) {
      email.action_bucket = null;
      appendEmails([email]);
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
}

function handleCancel(msg) {
  const email = emailStore[msg.email_id];
  if (!email) return;

  email.action_bucket = null;

  removeEmailFromUI(msg.email_id);

  appendEmails([email]);
}

function handleUnsnooze(msg) {
  const email = emailStore[msg.email_id];
  if (!email) return;

  delete email.remind_at;

  removeEmailFromUI(msg.email_id);

  appendEmails([email]);
}

function handleSnooze(msg) {
  const email = emailStore[msg.email_id];
  if (!email) return;

  email.remind_at = msg.remind_at;

  removeEmailFromUI(msg.email_id);
  appendSnoozedEmails([email]);
}

let socket;

function connectWS() {
  socket = new WebSocket("ws://127.0.0.1:10000/ws");

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

      // case "SNOOZED":
      //   handleSnooze(msg);
      //   break;

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

async function loadEmails() {
  try {
  const res = await fetch(`${API}/emails`, {
    credentials: "include"
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to load emails");

  console.log("RAW API:", data);

  const emails = Array.isArray(data) ? data : (data.emails || []);

  resetInbox();

  appendEmails(emails);
  } catch (err) {
    console.error(err);
    showStatus("Failed to load emails: " + err.message);
  }
}

async function unsnoozeEmail(id) {
  try {
    await fetch(`${API}/email/unsnooze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id })
    });

    const email = emailStore[id];

    // 🔥 REMOVE from snoozed UI
    document.querySelector(`#snoozedList [data-id="${id}"]`)?.remove();

    // 🔥 ADD BACK to inbox WITHOUT reload
    if (email) {
      delete email.remind_at;
      appendEmails([email]);
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

  if (actionDiv) {
    actionDiv.innerHTML = `
      <button class="btn btn-primary" disabled>
        ⏳ Analyzing...
      </button>
    `;
  }

  try {
    const res = await fetch(`${API}/email/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ id })
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    emailStore[id] = {
  ...data.email,
  reply: data.reply
};

    if (actionDiv) {
  actionDiv.innerHTML = `
    <button class="btn btn-primary"
      onclick="toggleReply('${id}')">
      View Reply
    </button>
  `;
}

    if (replyBox) {
      const textarea = replyBox.querySelector("textarea");
      if (textarea && !textarea.value) {
        textarea.value = data.reply || "";
      }
    }

    showStatus("✅ Email analyzed");

  } catch (err) {
    console.error(err);
    showStatus("❌ Analyze failed");
    renderActions(emailStore[id]);
  } finally {
    isProcessing = false;
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

    const email = emailStore[id];

    // 🔥 REMOVE from inbox (no full refresh)
    document.querySelector(`[data-id="${id}"]`)?.remove();

    // 🔥 ADD to snoozed list
    appendSnoozedEmails([{
      ...email,
      remind_at: data.remind_at
    }]);

    showStatus("⏰ Snoozed");

  } catch (err) {
    console.error(err);
    showStatus("❌ Snooze failed");
  }
}

// ── renderSnooze ──────────────────────────────────────────────────────────
function renderSnooze(id) {
  return `
    <div style="position:relative;">
      <button type="button" class="btn btn-secondary" onclick="toggleSnoozeDropdown('${id}')">
        Snooze
      </button>
      <div id="snooze-dropdown-${id}" class="snooze-dropdown hidden"
        style="position:absolute;background:#1f2937;padding:8px;border-radius:8px;
               top:40px;z-index:10;min-width:150px;box-shadow:0 4px 12px rgba(0,0,0,0.4);">
        <div onclick="snoozeEmail('${id}', 180)"
          style="padding:6px 10px;cursor:pointer;border-radius:4px;"
          onmouseover="this.style.background='#374151'"
          onmouseout="this.style.background='transparent'">In 3 hours</div>
        <div onclick="snoozeEmail('${id}', 1440)"
          style="padding:6px 10px;cursor:pointer;border-radius:4px;"
          onmouseover="this.style.background='#374151'"
          onmouseout="this.style.background='transparent'">Tomorrow</div>
        <div onclick="snoozeEmail('${id}', 10080)"
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

let snoozedStore = {};

// Replace appendSnoozedEmails
function appendSnoozedEmails(emails) {
  const container = document.getElementById("snoozedList");

  emails.forEach(email => {
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
  emailStore = {};
  renderedEmailIds.clear();
}

function showStatus(msg) {
  if (!statusMessage) return;
  statusMessage.textContent = msg;
  statusMessage.classList.remove("hidden");
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
        fetch(`${API}/emails`, { credentials: "include" }),
        fetch(`${API}/emails/snoozed`, { credentials: "include" }),
        fetch(`${API}/emails/scheduled`, { credentials: "include" })
      ]);

      const scheduledData = await scheduledRes.json();

      appendScheduledEmails(scheduledData.emails || []);

      const emailsData = await emailsRes.json();
      const snoozedData = await snoozedRes.json();

      if (!emailsRes.ok || !snoozedRes.ok) return;

      // 🔥 SAFE REFRESH
      // 🔥 ONLY UPDATE IF NEW EMAILS (NO RESET)
const emails = emailsData.emails || [];

emails.forEach(email => {
  if (!renderedEmailIds.has(email.id)) {
    appendEmails([email]);
  }
});

// snoozed safe update
appendSnoozedEmails(snoozedData.emails || []);

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

ws.onopen = () => {
  console.log("WS CONNECTED");

  setInterval(() => {
    ws.send("ping");
  }, 20000);
};

ws.onmessage = (event) => {
  console.log("WS EVENT:", event.data);
};

// ----------------------
// INIT
// ----------------------
window.addEventListener("DOMContentLoaded", () => {
  connectWS();
  checkAuthStatus();
  startAutoRefresh();
});

window.processEmail = processEmail;
window.snoozeEmail = snoozeEmail;
window.toggleReply = toggleReply;