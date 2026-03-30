/* =========================================================
   SEO Audit Tool — Frontend JS
   ========================================================= */

"use strict";

// ── State ──────────────────────────────────────────────────
let currentJobId  = null;
let evtSource     = null;
let _urlCount     = 1;    // total URLs being audited
let _currentUrlIdx = 0;   // 0-based index of URL being processed
let _totalMods    = 0;    // modules to run per URL (from [X/Y] parsing)
let _currentMod   = 0;    // last seen X from [X/Y]

// All 23 checks (mirrors ALL_CHECKS in checks/__init__.py)
const ALL_CHECKS = [
  { id: "url_structure",         label: "1. URL Structure",            scope: "page" },
  { id: "meta_tags",             label: "2. Meta Tags",                scope: "page" },
  { id: "headings",              label: "3. Headings (H1–H6)",         scope: "page" },
  { id: "content_quality",       label: "4. Content Quality",          scope: "page" },
  { id: "image_optimization",    label: "5. Image Optimization",       scope: "page" },
  { id: "internal_linking",      label: "6. Internal Linking",         scope: "page" },
  { id: "external_links",        label: "7. External Links",           scope: "page" },
  { id: "mobile_friendliness",   label: "8. Mobile Friendliness",      scope: "page" },
  { id: "page_speed",            label: "9. Page Speed & Performance", scope: "site" },
  { id: "structured_data",       label: "10. Structured Data / Schema",scope: "page" },
  { id: "xml_sitemap",           label: "11. XML Sitemap",             scope: "site" },
  { id: "robots_txt",            label: "12. Robots.txt",             scope: "site" },
  { id: "redirects",             label: "13. Redirects",               scope: "site" },
  { id: "https_security",        label: "14. HTTPS & Security",        scope: "site" },
  { id: "pagination_canonicals", label: "15. Pagination & Canonicals", scope: "page" },
  { id: "analytics_tracking",    label: "16. Analytics & Tracking",    scope: "page" },
  { id: "social_opengraph",      label: "17. Social & Open Graph",     scope: "page" },
  { id: "error_pages",           label: "18. Error Pages",             scope: "site" },
  { id: "core_web_vitals",       label: "19. Core Web Vitals",         scope: "site" },
  { id: "technical_seo",         label: "20. Technical SEO",           scope: "page" },
  { id: "content_accessibility", label: "21. Content Accessibility",   scope: "page" },
  { id: "crawl_errors",          label: "22. Crawl Errors",            scope: "site" },
  { id: "backlinks_authority",   label: "23. Backlinks & Authority",   scope: "page" },
];

// ── DOM cache ──────────────────────────────────────────────
let $ = {};

// ── Init ───────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  $ = {
    singleBtn:       document.getElementById("mode-single"),
    multiBtn:        document.getElementById("mode-multi"),
    singleWrap:      document.getElementById("single-wrap"),
    multiWrap:       document.getElementById("multi-wrap"),
    singleUrl:       document.getElementById("single-url"),
    multiUrls:       document.getElementById("multi-urls"),
    depthRange:      document.getElementById("depth-range"),
    depthVal:        document.getElementById("depth-val"),
    maxPagesRange:   document.getElementById("maxpages-range"),
    maxPagesVal:     document.getElementById("maxpages-val"),
    delayRange:      document.getElementById("delay-range"),
    delayVal:        document.getElementById("delay-val"),
    concurRange:     document.getElementById("concur-range"),
    concurVal:       document.getElementById("concur-val"),
    keyword:         document.getElementById("keyword"),
    psKey:           document.getElementById("ps-key"),
    fmtDocx:         document.getElementById("fmt-docx"),
    fmtHtml:         document.getElementById("fmt-html"),
    fmtDocxCard:     document.getElementById("fmt-docx-card"),
    fmtHtmlCard:     document.getElementById("fmt-html-card"),
    runBtn:          document.getElementById("run-btn"),
    runBtnText:      document.getElementById("run-btn-text"),
    runBtnSpinner:   document.getElementById("run-btn-spinner"),
    // Output
    emptyState:      document.getElementById("empty-state"),
    outputContent:   document.getElementById("output-content"),
    logBody:         document.getElementById("log-body"),
    logStatusPill:   document.getElementById("log-status-pill"),
    progressWrap:    document.getElementById("progress-wrap"),
    progressFill:    document.getElementById("progress-fill"),
    progressLabel:   document.getElementById("progress-label"),
    progressPct:     document.getElementById("progress-pct"),
    progressCount:   document.getElementById("progress-count"),
    // Current module display
    currentModWrap:  document.getElementById("current-mod-wrap"),
    currentModName:  document.getElementById("current-mod-name"),
    currentModNum:   document.getElementById("current-mod-num"),
    currentModScope: document.getElementById("current-mod-scope"),
    currentModResult:document.getElementById("current-mod-result"),
    // Results
    resultsWrap:     document.getElementById("results-wrap"),
    reportsPanel:    document.getElementById("reports-panel"),
    reportsList:     document.getElementById("reports-list"),
  };

  initRangeBindings();
  initModeToggle();
  initFormatCards();
  buildChecksUI();
  initChecksToolbar();
  bindRunButton();
  bindSectionToggles();
  loadReportsList();
});

// ── Range sliders ──────────────────────────────────────────
function initRangeBindings() {
  const pairs = [
    [$.depthRange,    $.depthVal,    v => v],
    [$.maxPagesRange, $.maxPagesVal, v => v == 0 ? "∞" : v],
    [$.delayRange,    $.delayVal,    v => parseFloat(v).toFixed(1) + "s"],
    [$.concurRange,   $.concurVal,   v => v],
  ];
  pairs.forEach(([range, val, fmt]) => {
    const update = () => { val.value = fmt(range.value); };
    range.addEventListener("input", update);
    update();
  });
}

// ── URL mode toggle ────────────────────────────────────────
function initModeToggle() {
  $.singleBtn.addEventListener("click", () => setMode("single"));
  $.multiBtn.addEventListener("click",  () => setMode("multi"));
}

function setMode(mode) {
  const isSingle = mode === "single";
  $.singleBtn.classList.toggle("active", isSingle);
  $.multiBtn.classList.toggle("active", !isSingle);
  $.singleWrap.classList.toggle("hidden", !isSingle);
  $.multiWrap.classList.toggle("hidden", isSingle);
}

// ── Format cards ───────────────────────────────────────────
function initFormatCards() {
  [[$.fmtDocxCard, $.fmtDocx], [$.fmtHtmlCard, $.fmtHtml]].forEach(([card, cb]) => {
    const sync = () => card.classList.toggle("selected", cb.checked);
    card.addEventListener("click", () => { cb.checked = !cb.checked; sync(); });
    sync();
  });
}

// ── Build check module checkboxes ─────────────────────────
function buildChecksUI() {
  const container = document.getElementById("checks-container");
  container.innerHTML = "";

  [
    { label: "Site-wide (run once per site)", items: ALL_CHECKS.filter(c => c.scope === "site") },
    { label: "Per-page (run on every crawled page)", items: ALL_CHECKS.filter(c => c.scope === "page") },
  ].forEach(({ label, items }) => {
    const lbl = document.createElement("div");
    lbl.className = "checks-group-label";
    lbl.textContent = label;
    container.appendChild(lbl);

    items.forEach(chk => {
      const el = document.createElement("label");
      el.className = "check-item";
      el.innerHTML = `
        <input type="checkbox" class="check-checkbox" data-id="${chk.id}" checked>
        <span class="check-name">${chk.label}</span>
        <span class="check-badge ${chk.scope === 'site' ? 'badge-site' : 'badge-page'}">${chk.scope}</span>`;
      container.appendChild(el);
    });
  });
}

// ── Check toolbar buttons ──────────────────────────────────
function initChecksToolbar() {
  const all = () => document.querySelectorAll(".check-checkbox");

  document.getElementById("btn-select-all").addEventListener("click", () => {
    all().forEach(cb => cb.checked = true);
  });
  document.getElementById("btn-deselect-all").addEventListener("click", () => {
    all().forEach(cb => cb.checked = false);
  });
  document.getElementById("btn-site-only").addEventListener("click", () => {
    all().forEach(cb => {
      const c = ALL_CHECKS.find(x => x.id === cb.dataset.id);
      cb.checked = !!c && c.scope === "site";
    });
  });
  document.getElementById("btn-page-only").addEventListener("click", () => {
    all().forEach(cb => {
      const c = ALL_CHECKS.find(x => x.id === cb.dataset.id);
      cb.checked = !!c && c.scope === "page";
    });
  });
}

// ── Section collapse / expand ─────────────────────────────
function bindSectionToggles() {
  document.querySelectorAll(".section-header").forEach(hdr => {
    hdr.addEventListener("click", e => {
      // Don't collapse when clicking toolbar buttons inside body
      const body = hdr.nextElementSibling;
      hdr.classList.toggle("collapsed");
      body.classList.toggle("hidden");
    });
  });
}

// ── Run button ─────────────────────────────────────────────
function bindRunButton() {
  $.runBtn.addEventListener("click", startAudit);
}

function startAudit() {
  // Collect URLs
  const isSingle = $.singleBtn.classList.contains("active");
  let urls = [];
  if (isSingle) {
    const u = $.singleUrl.value.trim();
    if (!u) { toast("Enter a URL first", "error"); return; }
    urls = [u];
  } else {
    urls = $.multiUrls.value.split("\n")
      .map(s => s.trim())
      .filter(s => s && !s.startsWith("#"));
    if (!urls.length) { toast("Enter at least one URL", "error"); return; }
  }

  // Collect selected checks
  const selected = [];
  document.querySelectorAll(".check-checkbox").forEach(cb => {
    if (cb.checked) selected.push(cb.dataset.id);
  });
  if (!selected.length) { toast("Select at least one check module", "error"); return; }
  const selectedChecks = selected.length === ALL_CHECKS.length ? null : selected;

  // Collect formats
  const formats = [];
  if ($.fmtDocx.checked) formats.push("docx");
  if ($.fmtHtml.checked) formats.push("html");
  if (!formats.length) { toast("Select at least one report format", "error"); return; }

  // Reset progress state
  _urlCount      = urls.length;
  _currentUrlIdx = 0;
  _totalMods     = selected.length;
  _currentMod    = 0;

  const payload = {
    urls,
    depth:           Number($.depthRange.value),
    max_pages:       Number($.maxPagesRange.value),
    delay:           Number($.delayRange.value),
    concurrency:     Number($.concurRange.value),
    keyword:         $.keyword.value.trim(),
    pagespeed_key:   $.psKey.value.trim(),
    selected_checks: selectedChecks,
    report_formats:  formats,
  };

  setRunning(true);
  showOutputPanel();
  clearLog();
  setLogStatus("running");
  $.resultsWrap.innerHTML = "";
  updateProgress(0, _totalMods * _urlCount);
  hideCurrentModule();

  fetch("/start", {
    method:  "POST",
    headers: { "Content-Type": "application/json" },
    body:    JSON.stringify(payload),
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) {
      toast(data.error, "error");
      setRunning(false);
      setLogStatus("error");
      return;
    }
    currentJobId = data.job_id;
    openStream(currentJobId);
  })
  .catch(err => {
    toast("Failed to start: " + err.message, "error");
    setRunning(false);
    setLogStatus("error");
  });
}

// ── SSE stream ─────────────────────────────────────────────
function openStream(jobId) {
  if (evtSource) evtSource.close();
  evtSource = new EventSource(`/stream/${jobId}`);

  evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.heartbeat) return;

    if (typeof data.log === "string") {
      processLogLine(data.log);
    }

    if (data.done) {
      evtSource.close();
      evtSource = null;
      setRunning(false);
      hideCurrentModule();

      if (data.status === "error") {
        setLogStatus("error");
        updateProgress(_totalMods * _urlCount, _totalMods * _urlCount, true);
        toast("Audit failed — see log for details", "error");
      } else {
        setLogStatus("done");
        updateProgress(_totalMods * _urlCount, _totalMods * _urlCount);
        renderResults(data.result || [], jobId);
        toast("Audit complete!", "success");
        loadReportsList();
      }
    }
  };

  evtSource.onerror = () => {
    evtSource.close();
    evtSource = null;
    setRunning(false);
    setLogStatus("error");
    hideCurrentModule();
    toast("Connection lost — check server", "error");
  };
}

// ── Log line processing (parse progress + display) ────────
function processLogLine(text) {
  appendLog(text);

  // ── "AUDIT [U/N]: URL" — new URL starting ──────────────
  const auditM = text.match(/^AUDIT \[(\d+)\/(\d+)\]/);
  if (auditM) {
    _currentUrlIdx = parseInt(auditM[1]) - 1;
    _urlCount      = parseInt(auditM[2]);
    return;
  }

  // ── "[X/Y] Module Title  (scope)" — check starting ─────
  // Log format: "[ 1/23] 1. URL Structure  (1 page(s))"
  const checkM = text.match(/^\[\s*(\d+)\/(\d+)\]\s+(.+?)\s{2,}\((.+?)\)/);
  if (checkM) {
    const x     = parseInt(checkM[1]);
    const y     = parseInt(checkM[2]);
    const title = checkM[3].trim();
    const scope = checkM[4].trim();

    _currentMod = x;
    _totalMods  = y;

    // Absolute progress: modules done = (urlIdx * y) + (x - 1)
    const done  = (_currentUrlIdx * y) + (x - 1);
    const total = _urlCount * y;
    updateProgress(done, total);
    showCurrentModule(title, scope, x, y);
    return;
  }

  // ── "       ✓ N checks | P pass | F fail | W warn | Xs" — check done ─
  const doneM = text.match(/✓\s+(\d+)\s+checks\s+\|\s+(\d+)\s+pass\s+\|\s+(\d+)\s+fail\s+\|\s+(\d+)\s+warn\s+\|\s+([\d.]+)s/);
  if (doneM) {
    const total_c = parseInt(doneM[1]);
    const pass    = parseInt(doneM[2]);
    const fail    = parseInt(doneM[3]);
    const warn    = parseInt(doneM[4]);
    const elapsed = doneM[5];

    // Update the current module indicator with result
    showCurrentModuleResult(pass, fail, warn, elapsed);

    // Advance progress by 1 (this module is now done)
    const done  = (_currentUrlIdx * _totalMods) + _currentMod;
    const total = _urlCount * _totalMods;
    updateProgress(done, total);
    return;
  }

  // ── "[CRAWL] Done — X page(s) collected" ───────────────
  const crawlDoneM = text.match(/\[CRAWL\] Done — (\d+) page\(s\) collected/);
  if (crawlDoneM) {
    // Crawl finished — still at 0 progress for this URL
    return;
  }
}

// ── Progress bar ───────────────────────────────────────────
function updateProgress(done, total, isError) {
  if (total <= 0) total = 1;
  const pct = Math.min(100, Math.round((done / total) * 100));

  $.progressFill.style.width       = pct + "%";
  $.progressFill.style.background  = isError
    ? "linear-gradient(135deg,#ef4444,#dc2626)"
    : "linear-gradient(135deg,#6366f1,#4f46e5)";
  $.progressPct.textContent        = pct + "%";
  $.progressCount.textContent      = `${done} / ${total} modules`;
  $.progressLabel.textContent      = done >= total
    ? "All checks complete"
    : "Running checks...";
}

// ── Current module display ─────────────────────────────────
function showCurrentModule(title, scope, x, y) {
  $.currentModWrap.classList.remove("hidden");
  $.currentModName.textContent  = title;
  $.currentModNum.textContent   = `${x} / ${y}`;
  $.currentModScope.textContent = scope;
  $.currentModResult.className  = "mod-result-badge hidden";
  $.currentModResult.textContent = "";
}

function showCurrentModuleResult(pass, fail, warn, elapsed) {
  const badge = $.currentModResult;
  badge.classList.remove("hidden");

  if (fail > 0) {
    badge.className = "mod-result-badge result-fail";
    badge.textContent = `✗ ${fail} fail`;
  } else if (warn > 0) {
    badge.className = "mod-result-badge result-warn";
    badge.textContent = `⚠ ${warn} warn`;
  } else {
    badge.className = "mod-result-badge result-pass";
    badge.textContent = `✓ ${pass} pass`;
  }
}

function hideCurrentModule() {
  $.currentModWrap.classList.add("hidden");
}

// ── Log rendering ──────────────────────────────────────────
function appendLog(text) {
  const div = document.createElement("div");
  div.className = "log-line " + classifyLog(text);

  // Syntax-highlight key parts inline
  div.innerHTML = formatLogLine(text);

  $.logBody.appendChild(div);
  // Auto-scroll to bottom
  $.logBody.scrollTop = $.logBody.scrollHeight;
}

function classifyLog(text) {
  const t = text.trim();
  if (/^\[CRAWL\]/.test(t))        return "ll-crawl";
  if (/^\[CHECKS?\]/.test(t))      return "ll-check";
  if (/^\[REPORT\]/.test(t))       return "ll-report";
  if (/^\[SCORE\]/.test(t))        return "ll-score";
  if (/^\[ERROR\]/.test(t))        return "ll-error";
  if (/^\[SKIP\]/.test(t))         return "ll-error";
  if (/^\[WARN\]/.test(t))         return "ll-warn";
  if (/^AUDIT \[/.test(t))         return "ll-audit";
  if (/^All done/.test(t))         return "ll-done";
  if (/^✓/.test(t.trimStart()))    return "ll-done";
  if (/^\[[\s\d]+\/\d+\]/.test(t)) return "ll-check-start";
  if (/✓\s+\d+ checks/.test(t))   return "ll-check-done";
  if (/^[═─]+$/.test(t))           return "ll-sep";
  return "ll-dim";
}

function formatLogLine(text) {
  // escape HTML first
  let s = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Highlight [X/Y] progress counter
  s = s.replace(/(\[\s*\d+\/\d+\])/g,
    '<span class="hl-counter">$1</span>');

  // Highlight ✓ pass markers
  s = s.replace(/(✓)/g,
    '<span class="hl-pass">$1</span>');

  // Highlight fail count
  s = s.replace(/(\d+)\s+fail/g,
    (m, n) => n > 0 ? `<span class="hl-fail">${n} fail</span>` : m);

  // Highlight warn count
  s = s.replace(/(\d+)\s+warn/g,
    (m, n) => n > 0 ? `<span class="hl-warn">${n} warn</span>` : m);

  // Highlight elapsed time (e.g. 1.5s)
  s = s.replace(/(\d+\.\d+s)/g,
    '<span class="hl-time">$1</span>');

  // Highlight URLs
  s = s.replace(/(https?:\/\/[^\s<>"]+)/g,
    '<span class="hl-url">$1</span>');

  // Highlight score percentage
  s = s.replace(/(\d+\.?\d*)\/100/g,
    '<span class="hl-score">$1/100</span>');

  return s;
}

function clearLog() {
  $.logBody.innerHTML = "";
}

// ── UI state helpers ───────────────────────────────────────
function setRunning(on) {
  $.runBtn.disabled = on;
  $.runBtn.classList.toggle("running", on);
  $.runBtnText.textContent = on ? "Running..." : "Run Audit";
  $.runBtnSpinner.classList.toggle("hidden", !on);
  // Show progress bar while running, keep it visible after finish
  if (on) $.progressWrap.classList.remove("hidden");
}

function showOutputPanel() {
  $.emptyState.classList.add("hidden");
  $.outputContent.classList.remove("hidden");   // CSS handles display:flex
}

function setLogStatus(s) {
  const labels = { running: "Running", done: "Done", error: "Error", idle: "Idle" };
  $.logStatusPill.className   = "log-status-pill pill-" + s;
  $.logStatusPill.textContent = labels[s] || s;
}

// ── Results rendering ──────────────────────────────────────
function renderResults(reports, jobId) {
  const wrap = $.resultsWrap;
  wrap.innerHTML = "";

  if (!reports || !reports.length) {
    wrap.innerHTML = `<p class="text-secondary" style="padding:1rem;text-align:center">No results — check the log for errors.</p>`;
    return;
  }

  reports.forEach((report, idx) => {
    wrap.appendChild(buildScoreCard(report, idx));

    if (report.modules && Object.keys(report.modules).length) {
      const heading = document.createElement("div");
      heading.className = "modules-heading";
      heading.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <rect x="3" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
        Module Results — click any card for details`;
      wrap.appendChild(heading);

      const grid = document.createElement("div");
      grid.className = "modules-grid";
      Object.entries(report.modules).forEach(([id, mod]) => {
        grid.appendChild(buildModuleCard(id, mod));
      });
      wrap.appendChild(grid);
    }

    if (report.files && Object.keys(report.files).length) {
      wrap.appendChild(buildDownloads(report, idx, jobId));
    }

    if (idx < reports.length - 1) {
      const hr = document.createElement("hr");
      hr.style.cssText = "border:none;border-top:1px solid var(--border);margin:1.5rem 0";
      wrap.appendChild(hr);
    }
  });
}

function buildScoreCard(report, idx) {
  const s     = report.score || {};
  const pct   = s.score_pct || 0;
  const R     = 45;
  const circ  = +(2 * Math.PI * R).toFixed(2);  // 282.74
  const offset = +(circ - (pct / 100) * circ).toFixed(2);
  const color = pct >= 80 ? "var(--success)" : pct >= 60 ? "var(--warning)" : "var(--danger)";

  const el = document.createElement("div");
  el.className = "score-section";
  el.innerHTML = `
    <div class="score-ring-wrap">
      <svg class="score-ring" viewBox="0 0 110 110">
        <circle class="ring-bg"   cx="55" cy="55" r="${R}"/>
        <circle class="ring-fill" cx="55" cy="55" r="${R}"
          stroke="${color}"
          stroke-dasharray="${circ}"
          stroke-dashoffset="${circ}"
          id="score-ring-${idx}"/>
      </svg>
      <div class="score-number">
        <span class="score-pct" style="color:${color}">${pct}</span>
        <span class="score-of-100">/100</span>
      </div>
    </div>
    <div class="score-meta">
      <div class="score-title">SEO Score</div>
      <div class="score-url">${escHtml(report.url || "")}</div>
      <div class="score-pills">
        <span class="score-pill pill-pass">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
            <polyline points="20 6 9 17 4 12"/></svg>
          ${s.passed || 0} passed
        </span>
        <span class="score-pill pill-fail">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          ${s.failed || 0} failed
        </span>
        <span class="score-pill pill-warn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="12" height="12">
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          ${s.warnings || 0} warnings
        </span>
      </div>
    </div>`;

  // Animate ring after DOM insertion
  setTimeout(() => {
    const ring = document.getElementById(`score-ring-${idx}`);
    if (ring) ring.style.strokeDashoffset = offset;
  }, 120);

  return el;
}

function buildModuleCard(modId, mod) {
  const { title, pass, fail, warn, total, summary, top_issues } = mod;
  const tot     = total || (pass + fail + warn) || 1;
  const pctPass = Math.round((pass / tot) * 100);

  let stClass  = "status-pass";
  let barColor = "var(--success)";
  if (fail > 0)      { stClass = "status-fail"; barColor = "var(--danger)";  }
  else if (warn > 0) { stClass = "status-warn"; barColor = "var(--warning)"; }

  const card = document.createElement("div");
  card.className = `module-card ${stClass}`;
  card.title = "Click to see details";
  card.innerHTML = `
    <div class="module-card-title">${escHtml(title)}</div>
    <div class="module-stats">
      ${pass > 0 ? `<span class="stat-chip stat-pass">✓ ${pass}</span>` : ""}
      ${fail > 0 ? `<span class="stat-chip stat-fail">✗ ${fail}</span>` : ""}
      ${warn > 0 ? `<span class="stat-chip stat-warn">⚠ ${warn}</span>` : ""}
    </div>
    <div class="module-bar-wrap">
      <div class="module-bar" style="width:${pctPass}%;background:${barColor}"></div>
    </div>`;

  card.addEventListener("click", () =>
    openModal(title, summary, top_issues || []));
  return card;
}

function openModal(title, summary, issues) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";

  const rows = issues.map(issue => `
    <div class="issue-row">
      <div class="issue-row-top">
        <span class="issue-dot status-${issue.status}-dot"></span>
        <span class="issue-name">${escHtml(issue.name)}</span>
        <span class="stat-chip stat-${issue.status}">${issue.status}</span>
      </div>
      ${issue.detail ? `<div class="issue-detail">${escHtml(issue.detail)}</div>` : ""}
      ${issue.page   ? `<div class="issue-page">${escHtml(issue.page)}</div>`   : ""}
    </div>`).join("");

  overlay.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">${escHtml(title)}</span>
        <button class="modal-close" id="mclose">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" width="16" height="16">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
      <div class="modal-body">
        ${summary ? `<div class="modal-summary">${escHtml(summary)}</div>` : ""}
        ${rows    || `<p style="text-align:center;color:var(--success);padding:1rem">
                        All checks passed for this module!</p>`}
      </div>
    </div>`;

  document.body.appendChild(overlay);
  const close = () => overlay.remove();
  overlay.querySelector("#mclose").addEventListener("click", close);
  overlay.addEventListener("click", e => { if (e.target === overlay) close(); });
  document.addEventListener("keydown", function esc(e) {
    if (e.key === "Escape") { close(); document.removeEventListener("keydown", esc); }
  });
}

function buildDownloads(report, idx, jobId) {
  const section = document.createElement("div");
  section.className = "downloads-section";

  const btns = Object.keys(report.files).map(fmt => {
    const icons  = { docx: "📄", html: "🌐" };
    const labels = { docx: "Download DOCX", html: "Download HTML" };
    return `
      <a class="download-btn ${fmt}" href="/download/${jobId}/${idx}/${fmt}" download>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" y1="15" x2="12" y2="3"/>
        </svg>
        ${icons[fmt] || ""} ${labels[fmt] || fmt.toUpperCase()}
      </a>`;
  }).join("");

  section.innerHTML = `
    <div class="downloads-heading">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
        <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
        <polyline points="7 10 12 15 17 10"/>
        <line x1="12" y1="15" x2="12" y2="3"/>
      </svg>
      Download Reports
    </div>
    <div class="download-group-url">${escHtml(report.url)}</div>
    <div class="download-btns">${btns}</div>`;

  return section;
}

// ── Reports history ────────────────────────────────────────
function loadReportsList() {
  fetch("/reports-list")
    .then(r => r.json())
    .then(files => {
      if (!files.length) { $.reportsPanel.classList.add("hidden"); return; }
      $.reportsPanel.classList.remove("hidden");
      $.reportsList.innerHTML = "";
      files.slice(0, 30).forEach(f => {
        const ext  = f.name.split(".").pop().toLowerCase();
        const icon = ext === "docx" ? "📄" : ext === "html" ? "🌐" : "📁";
        const div  = document.createElement("div");
        div.className = "report-item";
        div.innerHTML = `
          <span class="report-item-icon">${icon}</span>
          <span class="report-item-name">${escHtml(f.name)}</span>
          <span class="report-item-size">${formatBytes(f.size)}</span>
          <a class="report-item-dl" href="/reports-download/${encodeURIComponent(f.name)}"
             download title="Download ${escHtml(f.name)}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
          </a>`;
        $.reportsList.appendChild(div);
      });
    })
    .catch(() => {});
}

// ── Toast ──────────────────────────────────────────────────
function toast(msg, type = "info") {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  const dotColor = type === "success" ? "var(--success)" :
                   type === "error"   ? "var(--danger)"  : "var(--accent)";
  el.innerHTML = `<span class="toast-dot" style="background:${dotColor}"></span>${escHtml(msg)}`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

// ── Utilities ──────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatBytes(b) {
  if (b < 1024)         return b + " B";
  if (b < 1048576)      return (b / 1024).toFixed(1) + " KB";
  return (b / 1048576).toFixed(1) + " MB";
}
