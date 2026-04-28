<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Smart Approval Pipeline</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0eff4;color:#0f172a;min-height:100vh}

/* Layout */
.shell{display:grid;grid-template-columns:260px 1fr;min-height:100vh}
.sidebar{background:#1e1b4b;padding:0;display:flex;flex-direction:column;position:sticky;top:0;height:100vh;overflow-y:auto}
.sb-logo{padding:24px 20px 16px;border-bottom:1px solid #312e81}
.sb-logo h1{font-size:15px;font-weight:700;color:#fff;letter-spacing:-.3px}
.sb-logo p{font-size:11px;color:#818cf8;margin-top:3px}
.sb-nav{padding:16px 12px;flex:1}
.sb-label{font-size:9px;font-weight:700;letter-spacing:.1em;color:#6366f1;text-transform:uppercase;padding:0 8px;margin:16px 0 6px}
.sb-item{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;font-size:13px;font-weight:500;color:#a5b4fc;cursor:pointer;transition:all .15s;margin-bottom:2px}
.sb-item:hover{background:#312e81;color:#e0e7ff}
.sb-item.active{background:#4338ca;color:#fff}
.sb-item .si{width:18px;text-align:center;font-size:14px}
.sb-stats{padding:16px;border-top:1px solid #312e81;margin-top:auto}
.sb-stat{display:flex;justify-content:space-between;font-size:12px;color:#a5b4fc;padding:4px 0}
.sb-stat strong{color:#fff}

/* Main */
.main{padding:28px 32px;overflow-y:auto}
.page-header{margin-bottom:24px}
.page-header h2{font-size:22px;font-weight:700;color:#0f172a}
.page-header p{font-size:13px;color:#64748b;margin-top:4px}

/* Tabs */
.tab-bar{display:flex;gap:4px;margin-bottom:24px;background:#e2e8f0;padding:4px;border-radius:10px;width:fit-content}
.tab-btn{padding:8px 20px;border-radius:7px;font-size:13px;font-weight:500;cursor:pointer;border:none;background:transparent;color:#64748b;transition:all .15s}
.tab-btn.active{background:#fff;color:#0f172a;box-shadow:0 1px 4px rgba(0,0,0,.12)}

/* Cards */
.card{background:#fff;border-radius:12px;border:1px solid #e2e8f0;padding:20px;margin-bottom:16px}
.card-title{font-size:14px;font-weight:600;color:#0f172a;margin-bottom:16px;display:flex;align-items:center;gap:8px}

/* Metric row */
.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}
.metric{background:#fff;border-radius:10px;padding:14px;text-align:center;border:1px solid #e2e8f0}
.metric-n{font-size:24px;font-weight:700;color:#4338ca}
.metric-l{font-size:11px;color:#94a3b8;margin-top:2px}

/* Form */
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.fg{display:flex;flex-direction:column;gap:5px}
.fg.full{grid-column:1/-1}
.fg label{font-size:11px;font-weight:600;color:#374151;text-transform:uppercase;letter-spacing:.05em}
.fg input,.fg select,.fg textarea{font-size:13px;padding:9px 12px;border:1px solid #d1d5db;border-radius:8px;background:#fff;color:#0f172a;font-family:inherit;outline:none;transition:border .15s}
.fg input:focus,.fg select:focus,.fg textarea:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.1)}
.fg textarea{resize:none;height:80px}

/* Route preview */
.route-preview{border-radius:9px;padding:11px 14px;margin-bottom:16px;font-size:12px;display:flex;align-items:center;gap:8px;border:1px solid transparent}
.rp-low{background:#f0fdf4;border-color:#bbf7d0;color:#166534}
.rp-med{background:#fffbeb;border-color:#fde68a;color:#92400e}
.rp-high{background:#fef2f2;border-color:#fecaca;color:#991b1b}

/* Submit btn */
.btn-submit{background:#4338ca;color:#fff;border:none;padding:11px 24px;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer;transition:background .15s}
.btn-submit:hover{background:#3730a3}
.btn-submit:disabled{background:#94a3b8;cursor:not-allowed}

/* Pipeline list */
.pipeline-filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}
.pf-btn{font-size:11px;padding:4px 12px;border-radius:20px;border:1px solid #d1d5db;background:#fff;cursor:pointer;color:#64748b;font-weight:500;transition:all .15s}
.pf-btn.active{background:#4338ca;color:#fff;border-color:#4338ca}

/* Task card */
.task-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;margin-bottom:12px;overflow:hidden;transition:box-shadow .15s}
.task-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.06)}
.task-header{padding:14px 16px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:12px}
.task-meta{flex:1;min-width:0}
.task-id{font-size:10px;font-family:monospace;color:#94a3b8;margin-bottom:3px}
.task-title{font-size:13px;font-weight:600;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.task-sub{font-size:11px;color:#64748b;margin-top:2px}
.task-chevron{font-size:12px;color:#94a3b8;flex-shrink:0;transition:transform .2s}
.task-chevron.open{transform:rotate(180deg)}
.task-body{padding:0 16px 16px;border-top:1px solid #f1f5f9;display:none}
.task-body.open{display:block}
.task-desc{background:#f8fafc;border-left:3px solid #6366f1;border-radius:0 8px 8px 0;padding:10px 12px;font-size:12px;color:#374151;margin:12px 0;line-height:1.6}

/* Status pills */
.spill{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:600;white-space:nowrap}
.s-class{background:#ede9fe;color:#5b21b6}
.s-senior{background:#dbeafe;color:#1e40af}
.s-tech{background:#ede9fe;color:#5b21b6}
.s-cto{background:#fef3c7;color:#92400e}
.s-ceo{background:#fce7f3;color:#9d174d}
.s-await{background:#fef3c7;color:#92400e}
.s-approved{background:#d1fae5;color:#065f46}
.s-rejected{background:#fee2e2;color:#991b1b}
.s-done{background:#d1fae5;color:#065f46}
.s-risk-low{background:#dcfce7;color:#166534}
.s-risk-med{background:#fef3c7;color:#92400e}
.s-risk-high{background:#fee2e2;color:#991b1b}
.s-risk-pending{background:#f1f5f9;color:#475569}

/* Agent hierarchy */
.hier{position:relative;padding-left:0;margin:14px 0 4px}
.hier-line{position:absolute;left:19px;top:40px;bottom:10px;width:1px;background:linear-gradient(180deg,#94a3b844,#94a3b811)}
.hnode{display:flex;gap:0;margin-bottom:14px;position:relative}
.hdot{width:38px;height:38px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:16px;border:2px solid #e2e8f0;background:#f8fafc;z-index:1;transition:all .3s;margin-top:2px}
.hdot.idle{filter:grayscale(.5);opacity:.6}
.hdot.active{border-color:#6366f1;box-shadow:0 0 0 4px rgba(99,102,241,.15);animation:aglow 1.4s ease-in-out infinite}
.hdot.done{border-color:#22c55e;background:#f0fdf4}
.hdot.fail{border-color:#ef4444;background:#fef2f2}
.hdot.skip{border-color:#3b82f6;background:#eff6ff}
@keyframes aglow{0%,100%{box-shadow:0 0 0 0 rgba(99,102,241,.4)}50%{box-shadow:0 0 0 8px rgba(99,102,241,0)}}
.hbody{flex:1;padding-left:12px;padding-top:4px}
.ht{font-size:13px;font-weight:600;color:#0f172a;display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.hd{font-size:11px;color:#94a3b8;margin-top:1px}
.hresult{font-size:12px;margin-top:7px;padding:8px 11px;border-radius:8px;line-height:1.6}
.hr-done{background:#f0fdf4;color:#166534;border-left:3px solid #22c55e}
.hr-fail{background:#fef2f2;color:#991b1b;border-left:3px solid #ef4444}
.hr-active{background:#f5f3ff;color:#4c1d95;border-left:3px solid #7c3aed}
.hr-skip{background:#eff6ff;color:#1e40af;border-left:3px solid #3b82f6}

/* Badges */
.badge-auto{font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:#ede9fe;color:#7c3aed}
.badge-manual{font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:#fef3c7;color:#92400e}
.badge-active{font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:#dcfce7;color:#166534;animation:pulse 1.5s infinite}
.badge-skip{font-size:9px;font-weight:700;padding:2px 7px;border-radius:20px;background:#dbeafe;color:#1e40af}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}

/* Email card */
.email-card{background:#fafaf9;border:1px solid #e5e7eb;border-radius:10px;padding:13px;margin-top:9px;font-size:12px}
.email-meta{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;font-size:10px;font-family:monospace;color:#6b7280;padding-bottom:8px;border-bottom:1px solid #e5e7eb;margin-bottom:8px}
.email-meta span:nth-child(odd){font-weight:700;color:#374151}
.email-body{line-height:1.7;color:#374151;font-style:italic}

/* Cls tags */
.cls-block{background:#f8fafc;border:1px solid #e2e8f0;border-radius:9px;padding:10px 12px;margin:8px 0}
.cls-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.cls-tag{font-size:10px;font-family:monospace;padding:2px 8px;border-radius:12px}
.tag-low{background:#dcfce7;color:#166534}
.tag-med{background:#fef3c7;color:#92400e}
.tag-high{background:#fee2e2;color:#991b1b}
.tag-sec{background:#fce7f3;color:#9d174d}
.tag-info{background:#dbeafe;color:#1e40af}
.tag-gray{background:#f1f5f9;color:#475569}

/* Heartbeat bar */
.hb-bar{display:flex;align-items:center;gap:10px;background:#f5f3ff;border:1px solid #ede9fe;border-radius:9px;padding:8px 14px;font-size:12px;color:#4c1d95;margin-bottom:18px}
.hb-dot{width:8px;height:8px;border-radius:50%;background:#7c3aed;animation:hbp 1.4s ease-in-out infinite}
@keyframes hbp{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.3;transform:scale(.6)}}

/* Action buttons */
.act-btn{padding:8px 16px;border-radius:8px;font-size:12px;font-weight:600;cursor:pointer;border:1px solid transparent;transition:all .15s}
.act-btn:active{transform:scale(.97)}
.ab-green{background:#059669;color:#fff;border-color:#059669}
.ab-green:hover{background:#047857}
.ab-red{background:#dc2626;color:#fff;border-color:#dc2626}
.ab-red:hover{background:#b91c1c}
.ab-gray{background:#f1f5f9;color:#475569;border-color:#e2e8f0}
.ab-gray:hover{background:#e2e8f0}
.act-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}

/* Login */
.login-box{max-width:360px;margin:60px auto}
.pwd-input{width:100%;font-size:14px;padding:11px 14px;border:1px solid #d1d5db;border-radius:9px;font-family:inherit;outline:none;margin-bottom:12px}
.pwd-input:focus{border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.1)}
.login-btn{width:100%;background:#4338ca;color:#fff;border:none;padding:11px;border-radius:9px;font-size:14px;font-weight:600;cursor:pointer}
.login-btn:hover{background:#3730a3}

/* Note textarea */
.note-ta{width:100%;font-size:12px;padding:9px 12px;border:1px solid #d1d5db;border-radius:8px;font-family:inherit;outline:none;resize:none;height:60px;margin-top:12px}
.note-ta:focus{border-color:#6366f1}

/* Decision history */
.hist-card{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:14px;margin-bottom:10px}
.hist-header{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap}
.hist-note{background:#f0fdf4;border-left:3px solid #22c55e;border-radius:0 8px 8px 0;padding:8px 12px;font-size:12px;color:#166534;margin-top:10px}

/* Toast */
.toast{position:fixed;bottom:24px;right:24px;background:#1e1b4b;color:#fff;padding:12px 18px;border-radius:10px;font-size:13px;z-index:9999;display:none;animation:toastIn .2s ease}
@keyframes toastIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* Spinner */
.spinner{width:14px;height:14px;border:2px solid #6366f1;border-top-color:transparent;border-radius:50%;display:inline-block;animation:spin .7s linear infinite;vertical-align:middle}
@keyframes spin{to{transform:rotate(360deg)}}

.delete-btn{font-size:11px;padding:4px 10px;border-radius:6px;border:1px solid #e2e8f0;background:#fff;cursor:pointer;color:#94a3b8;transition:all .15s}
.delete-btn:hover{background:#fef2f2;color:#dc2626;border-color:#fecaca}

.sep{border:none;border-top:1px solid #e2e8f0;margin:16px 0}
</style>
</head>
<body>

<div class="shell">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sb-logo">
      <h1>🧠 Smart Pipeline</h1>
      <p>Agentic Approval System</p>
    </div>
    <nav class="sb-nav">
      <div class="sb-label">Navigation</div>
      <div class="sb-item active" onclick="showPage('submit')" id="nav-submit">
        <span class="si">📋</span> Submit Request
      </div>
      <div class="sb-item" onclick="showPage('pipeline')" id="nav-pipeline">
        <span class="si">⚙️</span> Live Pipeline
      </div>
      <div class="sb-item" onclick="showPage('approval')" id="nav-approval">
        <span class="si">✅</span> Your Approval
      </div>
      <div class="sb-item" onclick="showPage('history')" id="nav-history">
        <span class="si">📚</span> History
      </div>

      <div class="sb-label" style="margin-top:24px">Agent Chain</div>
      <div style="padding:0 8px">
        <div style="font-size:11px;color:#818cf8;line-height:1.8">
          🔍 System Classifier<br>
          👨‍💼 Senior Agent<br>
          🧑‍🔧 Tech Lead Agent<br>
          🏛️ CTO / CEO Agent<br>
          <span style="color:#4ade80">✅ Your Approval ← YOU</span><br>
          📚 KB Sync
        </div>
      </div>
    </nav>
    <div class="sb-stats">
      <div class="sb-stat"><span>Total requests</span><strong id="sb-total">0</strong></div>
      <div class="sb-stat"><span>In pipeline</span><strong id="sb-progress">0</strong></div>
      <div class="sb-stat"><span>Awaiting you</span><strong id="sb-awaiting" style="color:#fbbf24">0</strong></div>
      <div class="sb-stat"><span>Approved</span><strong id="sb-approved" style="color:#4ade80">0</strong></div>
    </div>
  </aside>

  <!-- Main content -->
  <main class="main">
    <!-- Heartbeat bar -->
    <div class="hb-bar">
      <div class="hb-dot"></div>
      <span>Agent heartbeat active — <strong id="hb-next">8s</strong> to next tick</span>
      <span style="margin-left:auto;font-size:11px;color:#7c3aed" id="hb-status"></span>
    </div>

    <!-- Pages -->
    <div id="page-submit">
      <div class="page-header">
        <h2>Submit Change Request</h2>
        <p>Fill in the form — agents will classify, review, and route automatically.</p>
      </div>
      <div class="card">
        <div class="card-title">📝 Request Details</div>
        <div class="form-grid">
          <div class="fg">
            <label>Your Name / ID *</label>
            <input type="text" id="f-requester" placeholder="e.g. Priya K · ENG-042"/>
          </div>
          <div class="fg">
            <label>Change Title *</label>
            <input type="text" id="f-title" placeholder="e.g. Update API login documentation"/>
          </div>
          <div class="fg">
            <label>Department *</label>
            <select id="f-dept">
              <option value="">Select…</option>
              <option>Engineering</option><option>Finance</option><option>HR</option>
              <option>Legal</option><option>Operations</option><option>Security</option>
              <option>Executive</option><option>Product</option><option>Other</option>
            </select>
          </div>
          <div class="fg">
            <label>Change Type *</label>
            <select id="f-type" onchange="updateRoutePreview()">
              <option value="">Select…</option>
              <option>Documentation Update</option>
              <option>Code Change</option>
              <option>Security Patch</option>
              <option>API Change</option>
              <option>Financial Report</option>
              <option>Policy Document</option>
              <option>Employee Data</option>
              <option>Vendor Contract</option>
              <option>System Architecture</option>
            </select>
          </div>
          <div class="fg">
            <label>Priority</label>
            <select id="f-priority">
              <option>Medium</option><option>High</option><option>Low</option>
            </select>
          </div>
          <div class="fg full">
            <label>Describe the change *</label>
            <textarea id="f-desc" placeholder="What are you changing, why, and what are the risks? The classifier reads this to determine routing."></textarea>
          </div>
        </div>
        <div id="route-preview" style="display:none" class="route-preview"></div>
        <button class="btn-submit" id="submit-btn" onclick="submitRequest()">🚀 Submit to Pipeline</button>
        <div id="submit-msg" style="margin-top:10px;font-size:13px"></div>
      </div>
    </div>

    <div id="page-pipeline" style="display:none">
      <div class="page-header">
        <h2>Live Pipeline</h2>
        <p>All requests and their current agent stage. Auto-refreshes every heartbeat.</p>
      </div>
      <div class="metrics" id="metrics-row"></div>
      <div class="pipeline-filters" id="pipeline-filters"></div>
      <div id="pipeline-list"></div>
    </div>

    <div id="page-approval" style="display:none">
      <div class="page-header">
        <h2>Your Approval</h2>
        <p>The only manual step — every task here has been reviewed by the full agent chain.</p>
      </div>
      <div id="approval-login">
        <div class="login-box">
          <div class="card">
            <div class="card-title">🔐 Admin Login</div>
            <input type="password" class="pwd-input" id="admin-pwd" placeholder="Enter password" onkeydown="if(event.key==='Enter')doLogin()"/>
            <button class="login-btn" onclick="doLogin()">Login →</button>
            <div id="login-err" style="color:#dc2626;font-size:12px;margin-top:8px"></div>
          </div>
        </div>
      </div>
      <div id="approval-content" style="display:none">
        <div id="awaiting-list"></div>
      </div>
    </div>

    <div id="page-history" style="display:none">
      <div class="page-header">
        <h2>Decision History</h2>
        <p>All approved, rejected, and completed requests.</p>
      </div>
      <div id="history-list"></div>
    </div>
  </main>
</div>

<div class="toast" id="toast"></div>

<script>
// ── Config ──────────────────────────────────────────────────────────────────
const ADMIN_PASSWORD = "admin123";
const HEARTBEAT_SEC  = 8;
const MODEL          = "claude-sonnet-4-20250514";

// ── Change type routing rules ────────────────────────────────────────────────
const CHANGE_TYPES = {
  "Documentation Update": {risk:"Low",    needs_ceo:false, auto_senior:true,  category:"docs"},
  "Code Change":          {risk:"Medium", needs_ceo:false, auto_senior:false, category:"tech"},
  "Security Patch":       {risk:"High",   needs_ceo:true,  auto_senior:false, category:"security"},
  "API Change":           {risk:"High",   needs_ceo:true,  auto_senior:false, category:"api"},
  "Financial Report":     {risk:"High",   needs_ceo:true,  auto_senior:false, category:"finance"},
  "Policy Document":      {risk:"Medium", needs_ceo:false, auto_senior:false, category:"policy"},
  "Employee Data":        {risk:"High",   needs_ceo:true,  auto_senior:false, category:"hr"},
  "Vendor Contract":      {risk:"Medium", needs_ceo:false, auto_senior:false, category:"legal"},
  "System Architecture":  {risk:"High",   needs_ceo:false, auto_senior:false, category:"tech"},
};
const CAT_LABELS = {
  docs:"Internal Documentation", tech:"Technical Change", security:"Security-Critical",
  api:"External API / Integration", finance:"Financial Data", policy:"Policy / Compliance",
  hr:"People & HR", legal:"Legal / Vendor"
};
const AGENTS = [
  {id:"classifier", label:"System Classifier", icon:"🔍", desc:"Reads change type, assigns risk, determines routing"},
  {id:"senior",     label:"Senior Agent",       icon:"👨‍💼", desc:"Reviews edit quality — may auto-pass low-risk"},
  {id:"techlead",   label:"Tech Lead Agent",    icon:"🧑‍🔧", desc:"Validates technical safety, writes CTO/CEO briefing"},
  {id:"cto",        label:"CTO / CEO Agent",    icon:"🏛️",  desc:"Reads briefing, decides to approve or escalate"},
  {id:"human",      label:"Your Approval",      icon:"✅",  desc:"THE ONLY MANUAL STEP — approve or reject here", manual:true},
  {id:"kb",         label:"KB Sync",            icon:"📚",  desc:"Auto-triggered on approval → writes to knowledge base"},
];

// ── In-memory store ──────────────────────────────────────────────────────────
let DB = JSON.parse(localStorage.getItem("pipeline_db") || "[]");
let nextId = DB.length ? Math.max(...DB.map(t=>t.id)) + 1 : 1;

function saveDB() { localStorage.setItem("pipeline_db", JSON.stringify(DB)); }

function createTask(data) {
  const t = {
    id: nextId++,
    ...data,
    stage: "classifier",
    status: "Classifying",
    risk_level: "Pending",
    stage_results: { junior: { agent:"Junior Agent", decision:"Approved", reason:`Submitted by ${data.requester}` } },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    reviewer_note: "",
  };
  DB.push(t);
  saveDB();
  return t;
}

function updateTask(id, patch) {
  const i = DB.findIndex(t=>t.id===id);
  if(i===-1) return;
  Object.assign(DB[i], patch, {updated_at: new Date().toISOString()});
  saveDB();
}

function deleteTask(id) {
  DB = DB.filter(t=>t.id!==id);
  saveDB();
}

function getByStatus(status) { return DB.filter(t=>t.status===status); }
function getAll(filter) { return filter && filter!=="All" ? DB.filter(t=>t.status===filter) : [...DB].reverse(); }
function getStats() {
  const progress = new Set(["Classifying","Senior Review","TechLead Review","CTO Review","CEO Review"]);
  return {
    total: DB.length,
    progress: DB.filter(t=>progress.has(t.status)).length,
    awaiting: DB.filter(t=>t.status==="Awaiting Approval").length,
    approved: DB.filter(t=>["Approved","Done"].includes(t.status)).length,
    rejected: DB.filter(t=>t.status==="Rejected").length,
  };
}

// ── Claude API ───────────────────────────────────────────────────────────────
async function claude(system, user, max_tokens=500) {
  try {
    const resp = await fetch("https://api.anthropic.com/v1/messages", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({model:MODEL, max_tokens, system, messages:[{role:"user",content:user}]})
    });
    const data = await resp.json();
    let raw = (data.content||[]).filter(b=>b.type==="text").map(b=>b.text).join("");
    raw = raw.trim().replace(/^```json?/,"").replace(/```$/,"").trim();
    return JSON.parse(raw);
  } catch(e) {
    return {decision:"Escalate_Human", reason:`Agent error: ${e.message}`, risk:"Medium"};
  }
}

// ── Agents ───────────────────────────────────────────────────────────────────
async function runClassifier(task) {
  const typeInfo = CHANGE_TYPES[task.request_type] || {};
  const result = await claude(
    `You are a change management classifier. Analyze and return ONLY raw JSON (no markdown):
{
  "category": one of [docs,tech,security,api,finance,policy,hr,legal],
  "risk": one of [Low,Medium,High,Critical],
  "involves_security": boolean,
  "involves_external": boolean,
  "summary": "one-sentence plain English summary max 20 words",
  "routing_note": "one sentence explaining routing decision",
  "auto_pass_senior": boolean (true only if Low risk and purely internal documentation)
}`,
    `Title: ${task.title}\nType: ${task.request_type}\nDept: ${task.department}\nDesc: ${task.description}`,
    300
  );
  const needs_ceo = result.involves_security || result.involves_external
    || typeInfo.needs_ceo || ["High","Critical"].includes(result.risk);
  const sr = {...task.stage_results};
  sr.classifier = {
    agent:"System Classifier", action:"Classified and routed", decision:"Routed",
    category: result.category||"tech",
    risk: result.risk||"Medium",
    involves_security: result.involves_security||false,
    involves_external: result.involves_external||false,
    summary: result.summary||"",
    routing_note: result.routing_note||"",
    auto_pass_senior: result.auto_pass_senior||false,
    needs_ceo,
  };
  updateTask(task.id, {status:"Senior Review", stage:"senior", risk_level:result.risk||"Medium", stage_results:sr});
}

async function runSenior(task) {
  const cls = task.stage_results.classifier || {};
  const sr  = {...task.stage_results};
  if(cls.auto_pass_senior) {
    sr.senior = {agent:"Senior Agent", action:"Auto-passed (low risk)", decision:"Approve",
      reason:"Low-risk internal documentation — auto-approved at senior level.", risk:cls.risk||"Low", skipped:true};
    updateTask(task.id, {status:"TechLead Review", stage:"techlead", stage_results:sr});
    return;
  }
  const result = await claude(
    `You are a Senior Engineer reviewing a change request. Return ONLY raw JSON:
{"decision":"Approve or Reject","reason":"1-2 sentences","notes":"brief technical note for Tech Lead"}`,
    `Title: ${task.title}\nType: ${task.request_type}\nDept: ${task.department}\nClassifier summary: ${cls.summary||""}\nRisk: ${cls.risk||"Medium"}\nDesc: ${task.description}`
  );
  sr.senior = {agent:"Senior Agent", action:"Reviewed change quality",
    decision:result.decision||"Approve", reason:result.reason||"", notes:result.notes||"", risk:cls.risk||"Medium"};
  if(result.decision==="Reject") {
    updateTask(task.id, {status:"Rejected", stage:"senior", stage_results:sr});
  } else {
    updateTask(task.id, {status:"TechLead Review", stage:"techlead", stage_results:sr});
  }
}

async function runTechLead(task) {
  const cls  = task.stage_results.classifier || {};
  const snr  = task.stage_results.senior || {};
  const sr   = {...task.stage_results};
  const needs_ceo = cls.needs_ceo || false;
  const result = await claude(
    `You are a Tech Lead in a change management pipeline. Return ONLY raw JSON:
{"decision":"Approve or Reject","reason":"1-2 sentences","cto_email_body":"2-3 sentence email to CTO/CEO explaining the change and what they need to decide. Write as if emailing a busy executive — clear, direct, no jargon.","technical_note":"one line technical context"}`,
    `Title: ${task.title}\nType: ${task.request_type}\nDept: ${task.department}\nRisk: ${cls.risk||"Medium"}\nSecurity: ${cls.involves_security}\nExternal: ${cls.involves_external}\nNeeds CEO: ${needs_ceo}\nSenior notes: ${snr.notes||""}\nDesc: ${task.description}`,
    500
  );
  sr.techlead = {agent:"Tech Lead Agent", action:"Validated technical safety",
    decision:result.decision||"Approve", reason:result.reason||"",
    cto_email_body:result.cto_email_body||"", technical_note:result.technical_note||"", needs_ceo};
  if(result.decision==="Reject") {
    updateTask(task.id, {status:"Rejected", stage:"techlead", stage_results:sr});
    return;
  }
  const nextStatus = needs_ceo ? "CEO Review" : "CTO Review";
  updateTask(task.id, {status:nextStatus, stage:"cto", stage_results:sr});
}

async function runCTO(task) {
  const cls  = task.stage_results.classifier || {};
  const tl   = task.stage_results.techlead   || {};
  const sr   = {...task.stage_results};
  const needs_ceo = cls.needs_ceo || false;
  const role = needs_ceo ? "CEO" : "CTO";
  const result = await claude(
    `You are the ${role} reviewing an escalated change. Return ONLY raw JSON:
{"decision":"Approve or Reject or Escalate_Human","reason":"1-2 sentences","risk_assessment":"Low or Medium or High","requires_human_approval":boolean}
Auto-approve ONLY if risk is genuinely Low and routine internal change.`,
    `Briefing from Tech Lead:\n${tl.cto_email_body||""}\nTechnical note: ${tl.technical_note||""}\nTitle: ${task.title}\nType: ${task.request_type}\nRisk: ${cls.risk||"Medium"}\nSecurity: ${cls.involves_security}\nExternal: ${cls.involves_external}\nDesc: ${task.description}`
  );
  sr.cto = {agent:`${role} Agent`, action:`Final review as ${role}`, decision:result.decision||"Escalate_Human",
    reason:result.reason||"", risk:result.risk_assessment||"Medium", role};
  const decision = result.decision || "Escalate_Human";
  if(decision==="Reject") {
    updateTask(task.id, {status:"Rejected", stage:"cto", stage_results:sr});
    return;
  }
  if(decision==="Approve" && !result.requires_human_approval) {
    sr.human = {agent:"Auto", decision:"Approved", reason:`Auto-approved by ${role} agent (low risk).`};
    updateTask(task.id, {status:"Approved", stage:"kb", stage_results:sr});
    runKB({...task, stage_results:sr});
    return;
  }
  updateTask(task.id, {status:"Awaiting Approval", stage:"human", stage_results:sr});
}

function runKB(task) {
  const sr = task.stage_results || {};
  const reason = sr.cto?.reason || sr.techlead?.reason || "Approved via pipeline.";
  const solution = `[Pipeline Approved] ${reason}`;
  // In a real app, write to KB here. We just log it.
  console.log("KB updated:", task.title, "→", solution);
  const newSR = {...sr, kb:{status:"updated", written_at:new Date().toISOString()}};
  updateTask(task.id, {status:"Done", stage_results:newSR});
}

// ── Heartbeat ─────────────────────────────────────────────────────────────────
let hbInterval, hbCountdown = HEARTBEAT_SEC;
let agentRunning = false;

async function heartbeatTick() {
  if(agentRunning) return;
  agentRunning = true;
  setHbStatus("⚙️ Agents running…");
  let processed = 0;
  const queue = [
    ["Classifying",     runClassifier],
    ["Senior Review",   runSenior],
    ["TechLead Review", runTechLead],
    ["CTO Review",      runCTO],
    ["CEO Review",      runCTO],
  ];
  for(const [status, runner] of queue) {
    const tasks = getByStatus(status).slice(0,2);
    for(const t of tasks) {
      try { await runner(t); processed++; } catch(e) { console.error(e); }
    }
  }
  agentRunning = false;
  if(processed > 0) {
    toast(`⚙️ ${processed} task(s) advanced by agents`);
    renderCurrentPage();
  }
  setHbStatus(processed > 0 ? `✓ Processed ${processed}` : "");
  updateSidebarStats();
}

function setHbStatus(msg) {
  document.getElementById("hb-status").textContent = msg;
  if(msg) setTimeout(()=>document.getElementById("hb-status").textContent="", 3000);
}

function startHeartbeat() {
  hbCountdown = HEARTBEAT_SEC;
  hbInterval = setInterval(async ()=>{
    hbCountdown--;
    document.getElementById("hb-next").textContent = hbCountdown + "s";
    if(hbCountdown <= 0) {
      hbCountdown = HEARTBEAT_SEC;
      await heartbeatTick();
      renderCurrentPage();
    }
  }, 1000);
}

// ── UI Helpers ────────────────────────────────────────────────────────────────
function toast(msg, ms=3000) {
  const el = document.getElementById("toast");
  el.textContent = msg; el.style.display = "block";
  clearTimeout(el._t);
  el._t = setTimeout(()=>el.style.display="none", ms);
}

function statusPill(status) {
  const map = {
    "Classifying":"s-class","Senior Review":"s-senior","TechLead Review":"s-tech",
    "CTO Review":"s-cto","CEO Review":"s-ceo","Awaiting Approval":"s-await",
    "Approved":"s-approved","Rejected":"s-rejected","Done":"s-done"
  };
  return `<span class="spill ${map[status]||"tag-gray"}">${status}</span>`;
}

function riskPill(risk) {
  const map = {Low:"s-risk-low", Medium:"s-risk-med", High:"s-risk-high", Critical:"s-risk-high"};
  return `<span class="spill ${map[risk]||"s-risk-pending"}">${risk||"Pending"} risk</span>`;
}

function fmtDate(iso) {
  try { return new Date(iso).toLocaleString("en-IN",{dateStyle:"medium",timeStyle:"short"}); }
  catch(e) { return iso||"—"; }
}

function updateRoutePreview() {
  const t = document.getElementById("f-type").value;
  const rp = document.getElementById("route-preview");
  if(!t) { rp.style.display="none"; return; }
  const info = CHANGE_TYPES[t];
  if(!info) { rp.style.display="none"; return; }
  const cls = {Low:"rp-low",Medium:"rp-med",High:"rp-high"}[info.risk]||"rp-med";
  rp.className = `route-preview ${cls}`;
  const ceoNote = info.needs_ceo ? " → <strong>CEO routing</strong>" : " → <strong>CTO routing</strong>";
  const autoNote = info.auto_senior ? " → <strong>Senior auto-pass eligible</strong>" : "";
  rp.innerHTML = `⚡ Routing preview: <strong>${info.risk} risk</strong>${ceoNote}${autoNote}`;
  rp.style.display = "flex";
}

function renderClsTags(cls) {
  if(!cls) return "";
  const riskTag = {Low:"tag-low",Medium:"tag-med",High:"tag-high",Critical:"tag-high"}[cls.risk]||"tag-gray";
  const cat = CAT_LABELS[cls.category]||cls.category||"";
  let tags = `<span class="cls-tag tag-gray">${cat}</span>`;
  tags += `<span class="cls-tag ${riskTag}">${cls.risk} risk</span>`;
  if(cls.involves_security) tags += `<span class="cls-tag tag-sec">security-critical</span>`;
  if(cls.involves_external) tags += `<span class="cls-tag tag-info">external integration</span>`;
  if(cls.needs_ceo)         tags += `<span class="cls-tag tag-sec">CEO-level routing</span>`;
  if(cls.auto_pass_senior)  tags += `<span class="cls-tag tag-low">senior auto-pass</span>`;
  const summary = cls.summary ? `<div style="font-size:11px;color:#64748b;margin-top:6px;font-style:italic">❝${cls.summary}❞</div>` : "";
  return `<div class="cls-block">
    <div style="font-size:10px;font-family:monospace;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:5px">System classification</div>
    <div class="cls-tags">${tags}</div>${summary}
  </div>`;
}

function renderEmailCard(tl, task) {
  if(!tl?.cto_email_body) return "";
  const role = tl.needs_ceo ? "CEO" : "CTO";
  const note = tl.technical_note ? `<div style="font-size:10px;font-family:monospace;opacity:.65;margin-top:8px">Technical note: ${tl.technical_note}</div>` : "";
  return `<div class="email-card">
    <div class="email-meta">
      <span>From</span><span>Tech Lead · System Notification</span>
      <span>To</span><span>${role} · Approval Required</span>
      <span>Re</span><span>${task.title||""}</span>
    </div>
    <div class="email-body">${tl.cto_email_body}${note}</div>
  </div>`;
}

function renderHierarchy(sr, currentStage, task, expandEmail=false) {
  let html = `<div class="hier"><div class="hier-line"></div>`;
  for(let i=0; i<AGENTS.length; i++) {
    const agent = AGENTS[i];
    const aid = agent.id;
    const res = sr[aid];
    let dotCls="idle", resCls="", tick="", resText="", badge="";

    if(res) {
      const dec = res.decision||"";
      if(dec==="Reject") { dotCls="fail"; resCls="hr-fail"; tick="❌"; resText=res.reason||""; }
      else if(res.skipped) { dotCls="skip"; resCls="hr-skip"; tick="⏭️"; resText=res.reason||""; }
      else if(["Approve","Approved","Routed","updated"].includes(dec)) { dotCls="done"; resCls="hr-done"; tick="✅"; resText=res.reason||res.routing_note||res.status||""; }
      else if(dec==="Escalate_Human") { dotCls="done"; resCls="hr-done"; tick="⬆️"; resText=res.reason||""; }
      else { dotCls="done"; resCls="hr-done"; tick="✅"; resText=res.reason||res.routing_note||""; }
    } else if(aid===currentStage) {
      dotCls="active"; resCls="hr-active"; tick="<span class='spinner'></span>"; resText="Agent working…";
    }

    if(agent.manual) badge = "<span class='badge-manual'>MANUAL</span>";
    else if(res?.skipped) badge = "<span class='badge-skip'>AUTO-PASS</span>";
    else if(aid===currentStage && !res) badge = "<span class='badge-active'>● ACTIVE</span>";
    else badge = "<span class='badge-auto'>AUTO</span>";

    const resultHtml = resText ? `<div class="hresult ${resCls}">${tick} ${resText}</div>` : "";
    const clsHtml = (aid==="classifier" && res) ? renderClsTags(res) : "";
    const emailHtml = (aid==="techlead" && res?.cto_email_body)
      ? (expandEmail
          ? renderEmailCard(res, task)
          : `<details><summary style="font-size:11px;color:#94a3b8;cursor:pointer;margin-top:6px">View briefing email →</summary>${renderEmailCard(res,task)}</details>`)
      : "";
    const roleNote = (aid==="cto" && res?.role) ? `<span style="font-size:10px;color:#b45309"> (acting as ${res.role})</span>` : "";

    html += `<div class="hnode">
      <div class="hdot ${dotCls}">${agent.icon}</div>
      <div class="hbody">
        <div class="ht">${agent.label}${roleNote}${badge}</div>
        <div class="hd">${agent.desc}</div>
        ${resultHtml}${clsHtml}${emailHtml}
      </div>
    </div>`;
  }
  html += "</div>";
  return html;
}

function renderTaskCard(t, opts={}) {
  const {expanded=false, showApproveButtons=false} = opts;
  const sr = t.stage_results || {};
  const cls = sr.classifier || {};
  const id = `task-${t.id}`;
  const bodyId = `body-${t.id}`;
  return `<div class="task-card" id="${id}">
    <div class="task-header" onclick="toggleTask(${t.id})">
      <div class="task-meta">
        <div class="task-id">#${t.id} · ${fmtDate(t.created_at)}</div>
        <div class="task-title">${t.title}</div>
        <div class="task-sub">${t.requester} · ${t.department} · ${t.request_type}</div>
      </div>
      <div style="display:flex;gap:8px;align-items:center;flex-shrink:0">
        ${statusPill(t.status)}
        ${riskPill(t.risk_level)}
        <span class="task-chevron ${expanded?'open':''}" id="chev-${t.id}">▾</span>
      </div>
    </div>
    <div class="task-body ${expanded?'open':''}" id="${bodyId}">
      <div class="task-desc">${t.description}</div>
      ${renderHierarchy(sr, t.stage, t)}
      ${showApproveButtons ? renderApproveButtons(t) : ""}
      <div class="act-row">
        <button class="delete-btn" onclick="doDelete(${t.id})">🗑️ Delete</button>
        <button class="act-btn ab-gray" onclick="renderCurrentPage()">🔄 Refresh</button>
      </div>
    </div>
  </div>`;
}

function renderApproveButtons(t) {
  return `<hr class="sep">
    <div style="font-size:12px;color:#64748b;margin-bottom:4px">Your decision note (optional):</div>
    <textarea class="note-ta" id="note-${t.id}" placeholder="Add context for the record…"></textarea>
    <div class="act-row">
      <button class="act-btn ab-green" onclick="doApprove(${t.id})">✅ Approve → KB</button>
      <button class="act-btn ab-red"   onclick="doReject(${t.id})">❌ Reject</button>
    </div>`;
}

// ── Page renders ──────────────────────────────────────────────────────────────
let currentPage = "submit";
let pipelineFilter = "All";
let loggedIn = false;
let openTasks = {};

function showPage(page) {
  ["submit","pipeline","approval","history"].forEach(p=>{
    document.getElementById(`page-${p}`).style.display = p===page ? "block" : "none";
    document.getElementById(`nav-${p}`)?.classList.toggle("active", p===page);
  });
  currentPage = page;
  renderCurrentPage();
}

function renderCurrentPage() {
  if(currentPage==="submit") renderSubmitPage();
  else if(currentPage==="pipeline") renderPipelinePage();
  else if(currentPage==="approval") renderApprovalPage();
  else if(currentPage==="history") renderHistoryPage();
  updateSidebarStats();
}

function renderSubmitPage() { /* form is static, nothing to re-render */ }

function renderPipelinePage() {
  const s = getStats();
  document.getElementById("metrics-row").innerHTML = [
    [s.total,"📋","Total"],
    [s.progress,"⚙️","In Pipeline"],
    [s.awaiting,"🔔","Needs Your OK"],
    [s.approved,"🟢","Approved"],
    [s.rejected,"🔴","Rejected"],
  ].map(([n,i,l])=>`<div class="metric"><div style="font-size:20px">${i}</div><div class="metric-n">${n}</div><div class="metric-l">${l}</div></div>`).join("");

  const FILTERS = ["All","Classifying","Senior Review","TechLead Review","CTO Review","CEO Review","Awaiting Approval","Approved","Rejected","Done"];
  document.getElementById("pipeline-filters").innerHTML = FILTERS.map(f=>
    `<button class="pf-btn ${pipelineFilter===f?'active':''}" onclick="setPipelineFilter('${f}')">${f}</button>`
  ).join("");

  const tasks = getAll(pipelineFilter);
  document.getElementById("pipeline-list").innerHTML = tasks.length
    ? tasks.map(t=>renderTaskCard(t,{expanded:!!openTasks[t.id]})).join("")
    : `<div style="text-align:center;padding:40px;color:#94a3b8">No tasks yet.</div>`;
}

function renderApprovalPage() {
  if(!loggedIn) {
    document.getElementById("approval-login").style.display="block";
    document.getElementById("approval-content").style.display="none";
    return;
  }
  document.getElementById("approval-login").style.display="none";
  document.getElementById("approval-content").style.display="block";
  const awaiting = getByStatus("Awaiting Approval");
  let html = "";
  if(!awaiting.length) {
    html = `<div class="card" style="text-align:center;padding:40px">
      <div style="font-size:32px;margin-bottom:12px">🎉</div>
      <div style="font-weight:600;color:#166534">Nothing waiting for your approval right now.</div>
    </div>`;
  } else {
    html = `<div style="background:#fef3c7;border:1px solid #fde68a;border-radius:9px;padding:11px 14px;font-size:13px;color:#92400e;margin-bottom:16px">
      🔔 <strong>${awaiting.length} task(s)</strong> need your approval.
    </div>`;
    html += awaiting.map(t=>renderTaskCard(t,{expanded:true,showApproveButtons:true})).join("");
  }
  document.getElementById("awaiting-list").innerHTML = html;
}

function renderHistoryPage() {
  const hist = DB.filter(t=>["Approved","Rejected","Done"].includes(t.status)).reverse();
  if(!hist.length) {
    document.getElementById("history-list").innerHTML = `<div style="text-align:center;padding:40px;color:#94a3b8">No decisions yet.</div>`;
    return;
  }
  document.getElementById("history-list").innerHTML = hist.map(t=>{
    const isDone = ["Approved","Done"].includes(t.status);
    const noteHtml = t.reviewer_note ? `<div class="hist-note">💬 ${t.reviewer_note}</div>` : "";
    return `<div class="hist-card">
      <div class="hist-header">
        <div>
          <div style="font-size:11px;font-family:monospace;color:#94a3b8">#${t.id} · ${fmtDate(t.created_at)}</div>
          <div style="font-size:14px;font-weight:600;margin-top:2px">${t.title}</div>
          <div style="font-size:12px;color:#64748b;margin-top:2px">${t.requester} · ${t.department}</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          ${statusPill(t.status)}
          <button class="delete-btn" onclick="doDelete(${t.id})">🗑️</button>
        </div>
      </div>
      ${noteHtml}
    </div>`;
  }).join("");
}

function updateSidebarStats() {
  const s = getStats();
  document.getElementById("sb-total").textContent    = s.total;
  document.getElementById("sb-progress").textContent = s.progress;
  document.getElementById("sb-awaiting").textContent = s.awaiting;
  document.getElementById("sb-approved").textContent = s.approved;
}

// ── Interactions ──────────────────────────────────────────────────────────────
function setPipelineFilter(f) { pipelineFilter=f; renderPipelinePage(); }

function toggleTask(id) {
  openTasks[id] = !openTasks[id];
  const body = document.getElementById(`body-${id}`);
  const chev = document.getElementById(`chev-${id}`);
  if(body) body.classList.toggle("open", openTasks[id]);
  if(chev) chev.classList.toggle("open", openTasks[id]);
}

async function submitRequest() {
  const requester = document.getElementById("f-requester").value.trim();
  const title     = document.getElementById("f-title").value.trim();
  const dept      = document.getElementById("f-dept").value;
  const type      = document.getElementById("f-type").value;
  const desc      = document.getElementById("f-desc").value.trim();
  const priority  = document.getElementById("f-priority").value;
  const msg       = document.getElementById("submit-msg");
  const errors    = [];
  if(!requester) errors.push("Name / ID required.");
  if(!title)     errors.push("Title required.");
  if(!dept)      errors.push("Select department.");
  if(!type)      errors.push("Select change type.");
  if(!desc)      errors.push("Description required.");
  if(errors.length) { msg.innerHTML=`<span style="color:#dc2626">${errors.join(" ")}</span>`; return; }
  const btn = document.getElementById("submit-btn");
  btn.disabled = true; btn.textContent = "Submitting…";
  const t = createTask({title, requester, department:dept, request_type:type, description:desc, priority});
  msg.innerHTML = `<span style="color:#059669">✅ Task #${t.id} created! Agents will pick it up on the next heartbeat.</span>`;
  btn.disabled = false; btn.textContent = "🚀 Submit to Pipeline";
  updateSidebarStats();
  toast(`Task #${t.id} submitted!`);
  // Clear form
  ["f-requester","f-title","f-desc"].forEach(id=>document.getElementById(id).value="");
  document.getElementById("f-dept").value="";
  document.getElementById("f-type").value="";
  document.getElementById("route-preview").style.display="none";
}

function doLogin() {
  const pwd = document.getElementById("admin-pwd").value;
  if(pwd===ADMIN_PASSWORD) {
    loggedIn=true;
    renderApprovalPage();
  } else {
    document.getElementById("login-err").textContent="Incorrect password.";
  }
}

function doApprove(id) {
  const t = DB.find(x=>x.id===id);
  if(!t) return;
  const note = document.getElementById(`note-${id}`)?.value||"";
  const sr = {...t.stage_results};
  sr.human = {agent:"You", decision:"Approved", reason:note||"Approved by authority."};
  updateTask(id, {status:"Approved", stage:"kb", stage_results:sr, reviewer_note:note});
  runKB({...t, stage_results:sr});
  toast("✅ Approved! KB updated.");
  renderApprovalPage();
  updateSidebarStats();
}

function doReject(id) {
  const t = DB.find(x=>x.id===id);
  if(!t) return;
  const note = document.getElementById(`note-${id}`)?.value||"";
  const sr = {...t.stage_results};
  sr.human = {agent:"You", decision:"Rejected", reason:note||"Rejected by authority."};
  updateTask(id, {status:"Rejected", stage:"human", stage_results:sr, reviewer_note:note});
  toast("❌ Rejected.");
  renderApprovalPage();
  updateSidebarStats();
}

function doDelete(id) {
  if(!confirm(`Delete task #${id}?`)) return;
  deleteTask(id);
  renderCurrentPage();
  updateSidebarStats();
  toast("🗑️ Deleted.");
}

// ── Init ──────────────────────────────────────────────────────────────────────
renderCurrentPage();
startHeartbeat();
// Trigger immediate first tick after 2s
setTimeout(()=>heartbeatTick(), 2000);
</script>
</body>
</html>
