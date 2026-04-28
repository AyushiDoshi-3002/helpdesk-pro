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
.hb-bar{display:flex;align-items:center;gap:10px;background:#f5f3ff;border:1px solid #ede9fe;border-radius:9px;paddin
