(function () {
  const data = window.DASHBOARD_DATA;
  const byId = (id) => document.getElementById(id);

  function text(node, value) {
    node.textContent = value;
    return node;
  }

  function el(tag, className, value) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = value;
    return node;
  }

  function emptyState(message) {
    return el("div", "empty-state", message);
  }

  const helpCopy = {
    connectWorkspace: {
      title: "Connect Workspace",
      body: "Connects the browser dashboard to the root workspace folder, not to one project file. Choose your local repo root (the directory containing projects/, papers/, sources/, and wiki/) so the dashboard can scan it directly.",
    },
    refreshScan: {
      title: "Refresh Scan",
      body: "Runs a fresh browser-side scan of the connected workspace folder. Use this after changing project files when you want the command launcher to reflect live folder state without rebuilding dashboard.json.",
    },
    rebuildCommand: {
      title: "Copy Rebuild Command",
      body: "Copies the command that regenerates dashboard.json and data.js from the repository. Run it after edits, ingest, triage, or project tracking changes, then reload the dashboard.",
    },
    reloadView: {
      title: "Reload View",
      body: "Reloads this local dashboard page. Use it after rebuilding the dashboard data so the browser reads the newest generated files.",
    },
    projectSelect: {
      title: "Project",
      body: "Chooses which project folder the command launcher should target. Active projects come from projects/_active.md; untracked projects still appear, but the dashboard marks them separately.",
    },
    actionSelect: {
      title: "Action",
      body: "Chooses the workflow command to prepare. Most actions target the selected project; Global Wiki Ingest ignores the project and uses papers/inbox/ directly.",
    },
    copyCommand: {
      title: "Copy Command",
      body: "Copies the displayed command exactly as shown. Use this as a fallback when a direct Run action is not available.",
    },
    runCommand: {
      title: "Run Button",
      body: "Runs allowlisted local actions through scripts/dashboard_server.py. Local LLM roles open in a separate Terminal session connected to LM Studio.",
    },
    explorationSection: {
      title: "Idea / Exploration Flow",
      body: "Use Idea Notes for lightweight evolving summaries, Exploration Briefs for focused questions worth review, and Active Explorations only after Skeptic Review says scouting is worthwhile. PDFs kept inside explorations are temporary and do not enter papers/, wiki/, or Mendeley until promoted.",
    },
    obsidianSection: {
      title: "Obsidian Wiki Viewer",
      body: "Obsidian is the recommended reader for the LLM-Wiki. Open this repository as one vault, start at index.md or wiki/overviews/, then use Graph View or Local Graph to explore [[wikilink]] connections. The graph gets richer as Synthesizer adds overview pages and cross-links.",
    },
  };

  const actionHelpCopy = {
    brief: {
      title: "Open Project Brief",
      body: "Project_Brief.md is the project contract. Use this before project-specific scouting, triage, synthesis, or drafting. It does not add papers to the wiki by itself.",
    },
    queries: {
      title: "Edit Scout Queries",
      body: "Optional. Use this when you want to add extra search campaigns without rewriting Project_Brief.md. Checked queries are treated as already run, so you can keep a running query log.",
    },
    scout: {
      title: "Scout Papers",
      body: "Build-phase discovery step. It searches external academic sources using the project brief and unchecked query items, then saves candidate metadata only. It does not download PDFs or update the wiki.",
    },
    "scout-campaign": {
      title: "Scout Query Campaign Only",
      body: "Advanced optional scouting. It runs only unchecked items in scout-queries.md, useful for a follow-up topic like computational modeling after your main scout batch already exists.",
    },
    triage: {
      title: "Triage Candidates",
      body: "Build-phase sorting step. Codex reads candidate titles/abstracts and sorts them into in-scope, borderline, or out-of-scope against Project_Brief.md. It still does not download PDFs.",
    },
    "approval-board": {
      title: "Build Triage Approval Board",
      body: "Creates the local checklist page where you decide which triaged papers should be downloaded, skipped, or ingested as wiki-only knowledge.",
    },
    "open-approval-board": {
      title: "Open Latest Approval Board",
      body: "Opens the newest generated approval-board HTML for this project. This is for human decision-making before PDFs enter papers/inbox/.",
    },
    "open-selected-paper-links": {
      title: "Open Selected Paper Links",
      body: "After exporting decisions from the approval board, this opens selected paper URLs so you can manually download PDFs when auto-download is blocked.",
    },
    "scopus-csv": {
      title: "Import Scopus CSV",
      body: "Imports a CSV file exported from Scopus into a scout candidate batch for triage.\n\n"
        + "Required columns (must be selected in Scopus export):\n"
        + "• Title\n"
        + "• Authors\n"
        + "• Year\n"
        + "• DOI  (EID is used as fallback if DOI is missing)\n"
        + "• Abstract\n\n"
        + "Recommended additional columns:\n"
        + "• Source title  (journal name)\n"
        + "• Author Keywords\n"
        + "• PubMed ID\n"
        + "• Link\n\n"
        + "How to export from Scopus:\n"
        + "Search → select results → Export → CSV → tick the fields above → Export.\n\n"
        + "The import creates a scout folder under scouts/{slug}/ and adds the papers as a candidate batch, ready for triage.",
    },
    ingest: {
      title: "Ingest Approved PDFs",
      body: "This is where approved PDFs become part of the LLM-Wiki. Codex copies/renames PDFs into papers/, creates sources/ and wiki/ pages, and updates index.md.",
    },
    "global-wiki-ingest": {
      title: "Global Wiki Ingest From Inbox",
      body: "Project-independent LLM-Wiki path. Use this when you already selected PDFs from Mendeley or your library and want them wiki-ized without Scout, Triage, or Project_Brief.",
    },
    synthesize: {
      title: "Synthesize Overview",
      body: "Use-phase knowledge compounding over cloud-safe library files. Reads existing sources/wiki pages and writes a reusable wiki/overviews/ page.",
    },
    draft: {
      title: "Draft A Section",
      body: "Project writing layer. Confidential drafting runs through the local LLM only after relevant wiki pages or overviews exist.",
    },
    verify: {
      title: "Verify A Draft",
      body: "Safety check for drafted prose. Codex runs scripts/verify_citations.py to confirm wikilinks, source frontmatter, and claim-log coverage before a draft is treated as usable.",
    },
    "prep-files": {
      title: "Create Optional Paper-In-Prep Files",
      body: "Optional writing/project-management layer for your own manuscript projects. It creates figure-plan, experiment-roadmap, and critique-log files. Skip this for normal literature wiki work.",
    },
    "data-update": {
      title: "Add Data Update",
      body: "Optional paper-in-prep tracking. Use this when you have a new panel, completed figure, or experimental result to record against the figure/experiment plan.",
    },
    critic: {
      title: "Run Project Critic",
      body: "Optional project-writing pressure test. Confidential critique runs through the local LLM; cloud-safe critique is limited to public wiki/exploration material.",
    },
    "pre-drafter": {
      title: "Analyze Wiki Relevance",
      body: "Scans all public wiki/sources pages for relevance to your project. Enter keywords below, then click Run. Writes wiki_context.md to the project folder — automatically loaded by the planner and drafter.",
    },
    "local-planner": {
      title: "Run Local Planner (Discussion)",
      body: "Opens a Terminal session for interactive pre-drafting discussion. Refine your central question, figure sequence, experiment list, and aims. Loads wiki_context.md automatically. Run Analyze Wiki Relevance first.",
    },
    "local-drafter": {
      title: "Run Local Drafter",
      body: "Opens a Terminal session for scripts/local_agent.py in drafter mode. LM Studio must be running with Local Server enabled at localhost:1234.",
    },
    "local-argue": {
      title: "Run Local Argue",
      body: "Opens a Terminal session for reviewer-style critique through the local LM Studio server.",
    },
    "local-demon": {
      title: "Run Local Demon",
      body: "Opens a Terminal session for devil's-advocate critique through the local LM Studio server.",
    },
    "local-rejection-sim": {
      title: "Run Local Rejection Simulator",
      body: "Opens a Terminal session for a local pre-submission rejection simulation.",
    },
    create: {
      title: "Create First Project Workspace",
      body: "Creates a new project folder and copies the Project_Brief template. Use this only when starting a new project deliverable.",
    },
    "idea-note": {
      title: "Summarize Discussion Into Idea Note",
      body: "Use after brainstorming. It saves only an evolving summary and dated updates, not the full conversation transcript. This is the lightest exploration layer.",
    },
    "promote-idea": {
      title: "Promote Idea Note To Exploration Brief",
      body: "Use when an idea has a focused question, searchable terms, and possible wiki or project value. This creates a one-file Exploration_Brief but does not scout yet.",
    },
    "exploration-skeptic": {
      title: "Run Exploration Skeptic Review",
      body: "Use before scouting. The Skeptic decides whether the brief is not-ready, brief-ready, scout-ready, or project-ready, and writes the review into the brief.",
    },
    "active-exploration": {
      title: "Promote To Active Exploration",
      body: "Use only after Skeptic Review says the idea is scout-ready. It creates an active exploration folder for candidates, paper briefs, and temporary PDFs.",
    },
    "exploration-synthesis": {
      title: "Write Exploration-Local Synthesis",
      body: "Use inside an active exploration when you want a provisional synthesis without promoting material into the permanent wiki. It writes explorations/active/IDEA_SLUG/synthesis.md and should clearly separate ingested wiki evidence from candidate-paper leads.",
    },
  };

  function ensureHelpDialog() {
    let dialog = byId("help-popover");
    if (dialog) return dialog;

    dialog = el("div", "help-popover");
    dialog.id = "help-popover";
    dialog.setAttribute("role", "dialog");
    dialog.setAttribute("aria-modal", "true");
    dialog.setAttribute("hidden", "");

    const panel = el("div", "help-panel");
    const closeButton = text(el("button", "help-close"), "x");
    closeButton.type = "button";
    closeButton.setAttribute("aria-label", "Close help");
    const title = el("h3", "help-title");
    const body = el("p", "help-body");

    closeButton.addEventListener("click", closeHelpDialog);
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeHelpDialog();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !dialog.hasAttribute("hidden")) closeHelpDialog();
    });

    panel.append(closeButton, title, body);
    dialog.append(panel);
    document.body.append(dialog);
    return dialog;
  }

  function closeHelpDialog() {
    const dialog = byId("help-popover");
    if (dialog) dialog.setAttribute("hidden", "");
  }

  function showHelp(copy) {
    const dialog = ensureHelpDialog();
    dialog.querySelector(".help-title").textContent = copy.title;
    dialog.querySelector(".help-body").textContent = copy.body;
    dialog.removeAttribute("hidden");
    dialog.querySelector(".help-close").focus();
  }

  function helpButton(copy) {
    const button = text(el("button", "help-button"), "?");
    button.type = "button";
    button.setAttribute("aria-label", `${copy.title} help`);
    button.addEventListener("click", () => showHelp(copy));
    return button;
  }

  function labelWithHelp(label, copy) {
    const wrapper = el("span", "label-with-help");
    wrapper.append(text(el("span"), label), helpButton(copy));
    return wrapper;
  }

  const statusScores = {
    not_needed: null,
    dropped: null,
    planned: 0,
    in_progress: 25,
    data_collected: 50,
    analyzed: 70,
    drafted: 85,
    complete: 100,
  };

  const runnableActions = new Set([
    "brief",
    "queries",
    "scout",
    "scout-campaign",
    "scout-exploration",
    "create-project",
    "pre-drafter",
    "fetch-external-info",
    "copy-info-to-project",
    "export-docx",
    "open-user-drafts",
    "open-figure-flow",
    "open-data-needed",
    "local-planner",
    "local-drafter",
    "local-argue",
    "local-demon",
    "local-rejection-sim",
    "approval-board",
    "open-approval-board",
    "prep-files",
    "data-update",
    "promote-exploration-to-project",
    "local-exploration-synthesis",
    "local-scout-brief",
    "export-scout-brief",
  ]);

  let serverState = {
    checked: false,
    online: false,
    allowed: new Set(),
  };
  let serverBase = "";           // "" = same-origin (http://); "http://localhost:8765" = file:// fallback
  function apiUrl(path) { return serverBase + path; }
  const dashboardStartCommand = "python3 scripts/dashboard_server.py --port 8765";

  function updateServerToggle() {
    const button = byId("server-toggle");
    if (!button) return;
    button.disabled = false;
    button.dataset.state = serverState.online ? "online" : "offline";
    button.textContent = serverState.online ? "Stop" : "Copy cmd";
    button.title = serverState.online
      ? "Stop the local dashboard server. Start it again from Terminal with the copied command."
      : "A browser page cannot start a stopped local server by itself; click to copy the Terminal command.";
  }

  async function stopDashboardServer(button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Stopping...";
    try {
      const response = await fetch(apiUrl("/api/run"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action_id: "stop-dashboard-server" }),
      });
      await response.json();
      serverState = { checked: true, online: false, allowed: new Set() };
      const status = byId("server-status");
      if (status) {
        status.innerHTML = '<span class="server-dot server-dot--off"></span>Server stopping';
        status.title = `Run: ${dashboardStartCommand}`;
        status.className = "server-status-offline";
      }
      updateServerToggle();
    } catch (_error) {
      serverState = { checked: true, online: false, allowed: new Set() };
      updateServerToggle();
    } finally {
      button.disabled = false;
      if (serverState.online) button.textContent = original;
    }
  }

  function setupServerToggle() {
    const button = byId("server-toggle");
    if (!button) return;
    button.addEventListener("click", async () => {
      if (serverState.online && serverState.allowed.has("stop-dashboard-server")) {
        await stopDashboardServer(button);
        return;
      }
      copyText(dashboardStartCommand, button);
    });
    updateServerToggle();
  }

  async function checkServer() {
    function applyServerState(payload, base) {
      serverBase = base;
      serverState = {
        checked: true,
        online: Boolean(payload.interactive),
        allowed: new Set(payload.allowed_actions || []),
      };
      const status = byId("server-status");
      if (status) {
        status.innerHTML = serverState.online
          ? '<span class="server-dot server-dot--on"></span>Server online'
          : '<span class="server-dot server-dot--off"></span>Server offline';
        status.title = serverState.online ? "" : `Run: ${dashboardStartCommand}`;
        status.className = serverState.online ? "server-status-online" : "server-status-offline";
      }
      updateServerToggle();
    }

    // file:// protocol — try 127.0.0.1 first (avoids IPv6 localhost resolution), then localhost
    if (location.protocol === "file:") {
      for (const base of ["http://127.0.0.1:8765", "http://localhost:8765"]) {
        try {
          const res = await fetch(`${base}/api/health`, { cache: "no-store" });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          applyServerState(await res.json(), base);
          return serverState;
        } catch (_) { /* try next */ }
      }
      // Both failed — server not running
      serverBase = "";
      serverState = { checked: true, online: false, allowed: new Set() };
      const status = byId("server-status");
      if (status) {
        status.innerHTML = '<span class="server-dot server-dot--off"></span>Server offline';
        status.title = "Start: python3 scripts/dashboard_server.py --port 8765";
        status.className = "server-status-offline";
      }
      updateServerToggle();
      if (!document.querySelector(".file-protocol-banner")) {
        const banner = document.createElement("div");
        banner.className = "file-protocol-banner";
        banner.innerHTML =
          '<strong>버튼을 사용하려면 서버를 켜고 서버 주소로 열어야 해요.</strong><br>' +
          '터미널: <code>python3 scripts/dashboard_server.py --port 8765</code><br>' +
          '접속: <a href="http://127.0.0.1:8765/_system/dashboard/index.html" target="_blank">http://127.0.0.1:8765/_system/dashboard/index.html</a>';
        document.body.prepend(banner);
      }
      return serverState;
    }

    // Same-origin (already served by dashboard_server.py at http://127.0.0.1:8765)
    try {
      const res = await fetch(apiUrl("/api/health"), { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      applyServerState(await res.json(), "");
    } catch (_) {
      serverState = { checked: true, online: false, allowed: new Set() };
      const status = byId("server-status");
      if (status) {
        status.innerHTML = '<span class="server-dot server-dot--off"></span>Server offline';
        status.title = `Run: ${dashboardStartCommand}`;
        status.className = "server-status-offline";
      }
      updateServerToggle();
    }
    return serverState;
  }

  function renderFocusPanel() {
    const title = byId("focus-title");
    const context = byId("focus-context");
    const command = byId("focus-command");
    const badges = byId("focus-badges");
    const copyButton = byId("focus-copy");
    if (!title || !context || !command || !badges || !copyButton || !data) return;

    const confidentialCount = (data.projects || []).filter((project) => project.confidential).length;
    const publicProjectCount = (data.projects || []).filter((project) => !project.confidential).length;
    const topItem = data.today && data.today.length ? data.today[0] : null;
    const fallbackProject = (data.projects || []).find((project) => project.confidential) || (data.projects || [])[0];
    const fallbackCommand = fallbackProject
      ? fallbackProject.recommended_command
      : "python3 scripts/build_dashboard.py";

    const focus = topItem
      ? {
          title: topItem.title,
          context: topItem.context,
          command: topItem.command,
        }
      : {
          title: confidentialCount ? "Open the local confidential lane" : "Keep building the public wiki",
          context: confidentialCount
            ? "Confidential project work should stay in LM Studio through scripts/local_agent.py. Public scout, ingest, and wiki work can continue here."
            : "No urgent action is detected. Add a topic through Quick Scout, ingest PDFs from the inbox, or browse the wiki in Obsidian.",
          command: fallbackCommand,
        };

    title.textContent = focus.title;
    context.textContent = focus.context;
    command.textContent = focus.command;
    copyButton.onclick = () => copyText(focus.command, copyButton);
    badges.replaceChildren();

    const badgeRows = [
      [`${data.totals.source_pages} sources`, "ready"],
      [`${data.totals.inbox_pdfs} inbox PDFs`, data.totals.inbox_pdfs ? "attention" : "ready"],
      [`${confidentialCount} local-only project${confidentialCount === 1 ? "" : "s"}`, confidentialCount ? "private" : "ready"],
      [`${publicProjectCount} public ingest workspace${publicProjectCount === 1 ? "" : "s"}`, "ready"],
    ];
    badgeRows.forEach(([label, state]) => {
      const badge = text(el("span", "focus-badge"), label);
      badge.dataset.state = state;
      badges.append(badge);
    });
  }

  function canRunTemplate(template) {
    return serverState.online && runnableActions.has(template.id) && serverState.allowed.has(template.id);
  }

  async function runServerAction(template, project, button, output, extraParams) {
    if (!canRunTemplate(template)) {
      output.textContent = "This action is copy-only, or the dashboard server is not running.";
      return;
    }
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Running...";
    output.dataset.state = "running";
    output.textContent = "Running allowlisted local action...";
    try {
      const ptype = project && project.project_type ? project.project_type : "paper_in_prep";
      const params = Object.assign({ project_type: ptype }, extraParams || {});
      const response = await fetch(apiUrl("/api/run"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_id: template.id,
          project_slug: project ? project.slug : null,
          params,
        }),
      });
      const result = await response.json();
      output.dataset.state = result.ok ? "ok" : "error";
      const chunks = [
        result.ok ? "Done." : "Failed.",
        result.command ? `Command: ${result.command}` : "",
        result.stdout ? `Output:\n${result.stdout}` : "",
        result.stderr ? `Errors:\n${result.stderr}` : "",
        result.log ? `Log: ${result.log}` : "",
      ].filter(Boolean);
      output.textContent = chunks.join("\n\n");
      if (result.reload_suggested) window.setTimeout(() => window.location.reload(), 1200);
    } catch (error) {
      output.dataset.state = "error";
      output.textContent = `Run failed: ${error.message}`;
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function serverRequiredMessage() {
    return [
      "This action needs the interactive dashboard server.",
      "",
      "Open this URL instead:",
      "http://127.0.0.1:8765/_system/dashboard/index.html",
      "",
      "If the server is not running, start it from the repo root:",
      "python3 scripts/dashboard_server.py --port 8765",
    ].join("\n");
  }

  function dashboardScoutSlug(value) {
    return String(value || "")
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9 _/-]/g, "")
      .replace(/[ _/]+/g, "-")
      .replace(/-{2,}/g, "-")
      .replace(/^-+|-+$/g, "") || "topic";
  }

  function quickScoutSlug(topic, yearStart, yearEnd) {
    const base = dashboardScoutSlug(topic);
    const years = [yearStart, yearEnd].map((value) => String(value || "").trim()).filter(Boolean).join("-");
    return years ? `${base}-${dashboardScoutSlug(years)}` : base;
  }

  function triagePromptForExploration(slug) {
    return `Read subagents/02-triage.md and act as the Triage agent for exploration ${slug}.

Use:
- explorations/idea-notes/${slug}.md
- the newest candidates folder under explorations/active/${slug}/candidates/

Write:
- explorations/active/${slug}/triage-reports/{YYYY-MM-DD}.md
- explorations/active/${slug}/triage-reports/{YYYY-MM-DD}.json

Use candidate metadata only. Do not download PDFs. Sort candidates into In-scope, Borderline, Out-of-scope, and already-in-corpus when applicable. Keep reasons short and tied to the exploration scope.`;
  }

  function triagePromptForPaperScout(slug) {
    return `Read subagents/02-triage.md and act as the Triage agent for paper scout ${slug}.

Use:
- scouts/${slug}/Scout_Brief.md
- the newest candidates folder under scouts/${slug}/candidates/

Write:
- scouts/${slug}/triage-reports/{YYYY-MM-DD}.md
- scouts/${slug}/triage-reports/{YYYY-MM-DD}.json

Use candidate metadata only. Do not download PDFs. This is a paper scout request, not an idea note or active exploration. Keep reasons short and sort candidates into useful, borderline, out-of-scope, and already-in-corpus when applicable.`;
  }

  function ingestPrompt() {
    return `Read subagents/03-ingester.md and act as the Ingester for the global LLM-Wiki.

Input:
- PDFs currently in papers/inbox/

Task:
- Ingest each PDF into the permanent library.
- Move each canonical PDF into papers/ using the repository naming convention.
- Create or update sources/{stem}.md.
- Create or update the appropriate wiki/{category}/{stem}.md page.
- Update index.md.
- Keep all wiki content in English.
- Do not use web search.
- Do not read papers/under-review/ or any confidential project folder.

After successful ingest:
- Run python3 scripts/cleanup_ingested_inbox_pdfs.py so papers/inbox/ returns to temporary-intake state.
- Run python3 scripts/build_dashboard.py so the dashboard counts refresh.

If a PDF cannot be ingested cleanly, leave it in papers/inbox/ and report the filename plus the blocker.`;
  }

  function synthesizePrompt({ slug, keywords, outputPath, outputType }) {
    const mode = outputType === "exploration"
      ? `Exploration-Local Mode for explorations/active/${slug}`
      : "Library Synthesis Mode";
    return `Read subagents/04-synthesizer.md and act as the Synthesizer agent in ${mode}.

Topic / keywords:
${keywords}

Output path: ${outputPath}

Use only ingested sources/ and wiki/ pages. Do not use web search.
Write or update ${outputPath} with cross-paper synthesis grounded only in papers already in the wiki.
At the end, list: (1) key claims and their supporting wiki pages, (2) knowledge gaps, (3) papers that should be ingested next.
After writing, run: python3 scripts/build_dashboard.py`;
  }

  async function runDashboardAction(actionId, params, output) {
    const response = await fetch(apiUrl("/api/run"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, params: params || {} }),
    });
    const result = await response.json();
    output.dataset.state = result.ok ? "ok" : "error";
    const chunks = [
      result.ok ? "Done." : "Failed.",
      result.command ? `Command: ${result.command}` : "",
      result.stdout ? `Output:\n${result.stdout}` : "",
      result.stderr ? `Errors:\n${result.stderr}` : "",
      result.log ? `Log: ${result.log}` : "",
    ].filter(Boolean);
    output.textContent = chunks.join("\n\n");
    return result;
  }

  function copyPlainText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(value);
      return;
    }
    const scratch = document.createElement("textarea");
    scratch.value = value;
    scratch.setAttribute("readonly", "");
    scratch.style.position = "fixed";
    scratch.style.left = "-9999px";
    document.body.append(scratch);
    scratch.select();
    document.execCommand("copy");
    scratch.remove();
  }

  function offerTriagePrompt(slug, output) {
    const prompt = triagePromptForExploration(slug);
    const wantsTriage = window.confirm("Scout finished. Copy the Codex triage prompt for these candidates?");
    if (!wantsTriage) return;
    copyPlainText(prompt);
    output.textContent += "\n\nTriage prompt copied. Paste it into Codex to start the triage step.";
  }

  function offerPaperScoutTriagePrompt(slug, output) {
    if (!window.confirm("Scout finished. Copy the triage prompt for this paper scout?")) return;
    copyPlainText(triagePromptForPaperScout(slug));
    output.textContent += "\n\nCopied paper-scout triage prompt to clipboard.";
  }

  function projectCommandTemplates(project) {
    const slug = project.slug;
    const localFlags = `--project ${slug}`;
    if (project.confidential) {
      const ptype = project.project_type || "paper_in_prep";
      // Section lists by project type
      const sectionsByType = {
        paper_in_prep: ["introduction", "results", "discussion", "figure-legends", "methods"],
        review_article: ["introduction", "review-body", "discussion"],
        grant: ["specific-aims", "significance", "innovation", "approach"],
        job_application: ["research-statement", "teaching-statement"],
      };
      const sections = sectionsByType[ptype] || sectionsByType.paper_in_prep;
      // External info types by project type
      const infoTypesByProject = {
        grant: ["grant_info"],
        job_application: ["job_description", "dept_faculty"],
        paper_in_prep: ["general"],
        review_article: ["general"],
      };
      const infoTypes = infoTypesByProject[ptype] || ["general"];

      const templates = [
        {
          id: "pre-drafter",
          group: "0. Pre-drafting Prep",
          tool: "cloud-safe",
          title: "Analyze wiki relevance",
          detail: "Scan wiki/sources for relevant pages. Enter topic keywords and click Run. Writes wiki_context.md.",
          command: `python3 scripts/pre_drafter.py --project ${slug} --type ${ptype} --keywords "KEYWORD1, KEYWORD2, KEYWORD3"`,
          hasKeywordInput: true,
        },
        {
          id: "open-user-drafts",
          group: "0. Pre-drafting Prep",
          tool: "Finder",
          title: "Open user-drafts folder",
          detail: `Write your section skeleton in user-drafts/{section}.md BEFORE running the drafter. Sections: ${sections.join(", ")}`,
          command: `open projects/${slug}/user-drafts/`,
        },
        {
          id: "local-planner",
          group: "0. Pre-drafting Prep",
          tool: "Local LLM",
          title: "Run local Planner (discussion)",
          detail: "Interactive discussion: refine questions, figure plan, aims. Run Analyze Wiki Relevance first.",
          command: `python3 scripts/local_agent.py --role planner ${localFlags}`,
        },
      ];

      // Scout brief — always available for confidential projects
      templates.push(
        {
          id: "local-scout-brief",
          group: "0c. Scout Brief",
          tool: "Local LLM",
          title: "Generate scout brief",
          detail: "Local LLM reads Project_Brief and writes a sanitized search brief — zero project identity leakage. Run /save inside the session, then export.",
          command: `python3 scripts/local_agent.py --role scout-brief --project ${slug}`,
        },
        {
          id: "export-scout-brief",
          group: "0c. Scout Brief",
          tool: "Local Agent",
          title: "Export scout brief → scouts/",
          detail: `Validates simulation_passed:true and no slug leakage, then copies to scouts/project-${slug}/Scout_Brief.md for cloud scouting.`,
          command: `# Click Run — server validates and copies to scouts/project-${slug}/Scout_Brief.md`,
        },
      );

      // Figure flow + data planning (paper_in_prep only — before drafter)
      if (ptype === "paper_in_prep") {
        templates.push(
          {
            id: "open-figure-flow",
            group: "0b. Figure Flow & Data Planning",
            tool: "Editor",
            title: "Open figure-flow.md",
            detail: "Narrative story arc: what each figure proves and why in that order. Creates from template if missing.",
            command: `open projects/${slug}/figure-flow.md`,
          },
          {
            id: "open-data-needed",
            group: "0b. Figure Flow & Data Planning",
            tool: "Editor",
            title: "Open data-needed.md",
            detail: "Track what data/experiments are needed, in progress, or done per figure panel.",
            command: `open projects/${slug}/data-needed.md`,
          },
          {
            id: "local-planner",
            group: "0b. Figure Flow & Data Planning",
            tool: "Local LLM",
            title: "Discuss figure flow & data needs (Planner)",
            detail: "Run Planner to discuss figure narrative sequence and data gaps. Use /save figure-flow or /save data-needed, then /export-docx-no-tc for Word output.",
            command: `python3 scripts/local_agent.py --role planner ${localFlags}`,
          }
        );
      }

      // Consolidated drafter entry — section chosen via sub-select in the launcher UI
      templates.push({
        id: "local-drafter",
        group: "1. Write",
        tool: "Local LLM",
        title: "Draft — choose section below",
        detail: `AI writes a section draft. Choose a section (or 'etc' for custom). If user-drafts/{section}.md exists, use /compare for side-by-side. Use /save then /export-docx for Word output.`,
        command: `python3 scripts/local_agent.py --role drafter ${localFlags} --section SECTION`,
        hasSectionInput: true,
        sectionOptions: [...sections, "etc"],
      });

      // External info fetcher (grant / job application)
      if (ptype === "grant" || ptype === "job_application") {
        templates.push({
          id: "fetch-external-info",
          group: "3. External Info",
          tool: "Cloud fetch (public URLs only)",
          title: ptype === "grant" ? "Fetch grant guidelines" : "Fetch job description",
          detail: "Enter the grant program URL or job posting URL. Saves to _system/docs/external-info/ for review.",
          command: `python3 scripts/fetch_external_info.py --url "URL_HERE" --type ${infoTypes[0]} --slug ${slug}`,
          hasFetchInput: true,
          fetchType: infoTypes[0],
        });
        if (ptype === "job_application") {
          templates.push({
            id: "fetch-external-info",
            group: "3. External Info",
            tool: "Cloud fetch (public URLs only)",
            title: "Fetch department faculty research",
            detail: "Enter the department faculty page URL. Extracts research interests for collaboration section.",
            command: `python3 scripts/fetch_external_info.py --url "URL_HERE" --type dept_faculty --slug ${slug}`,
            hasFetchInput: true,
            fetchType: "dept_faculty",
          });
        }
      }

      // Critique stages: always include brief; add figure-flow/data-needed for paper_in_prep
      const critiqueStages = [
        {
          stage: "brief",
          label: "Project Brief",
          argueDetail: "Critique project conception: aims coherence, testability, novelty claims, scope.",
          demonDetail: "Attack the project conception: is this novel, fundable, publishable at all?",
        },
      ];
      if (ptype === "paper_in_prep") {
        critiqueStages.push(
          {
            stage: "figure-flow",
            label: "Figure Flow",
            argueDetail: "Critique the narrative arc: is the figure sequence logically necessary? Do transitions hold?",
            demonDetail: "Attack the story: is this narrative coherent and sufficient, or does it have fatal gaps?",
          },
          {
            stage: "data-needed",
            label: "Data Needed",
            argueDetail: "Critique the experimental plan: sufficient? Scope creep? Feasibility?",
            demonDetail: "Attack the data strategy: will this experimental plan hold under hostile scrutiny?",
          }
        );
      }
      // Per-section critique entries (for sections that have been drafted)
      const draftSections = ptype === "paper_in_prep"
        ? ["introduction", "results", "discussion"]
        : ptype === "grant"
        ? ["specific-aims", "approach"]
        : ptype === "review_article"
        ? ["introduction", "review-body"]
        : [];

      // --- Group 2a: Stage-based critique (pre-draft artifacts) ---
      critiqueStages.forEach(({ stage, label, argueDetail, demonDetail }) => {
        templates.push(
          {
            id: "local-argue",
            group: "2a. Critique — Stage",
            tool: "Local LLM",
            title: `Argue: ${label}`,
            detail: argueDetail + " Logs versioned to critiques/argue/.",
            command: `python3 scripts/local_agent.py --role argue ${localFlags} --section ${stage}`,
            sectionValue: stage,
          },
          {
            id: "local-demon",
            group: "2a. Critique — Stage",
            tool: "Local LLM",
            title: `Demon: ${label}`,
            detail: demonDetail + " Logs versioned to critiques/demon/.",
            command: `python3 scripts/local_agent.py --role demon ${localFlags} --section ${stage}`,
            sectionValue: stage,
          }
        );
      });

      // --- Group 2b: Section-based critique (draft sections) ---
      draftSections.forEach((sec) => {
        templates.push(
          {
            id: "local-argue",
            group: `2b. Critique — ${sec} draft`,
            tool: "Local LLM",
            title: `Argue: ${sec}`,
            detail: `Reviewer-#2 pressure test on the ${sec} draft. Logs versioned to critiques/argue/.`,
            command: `python3 scripts/local_agent.py --role argue ${localFlags} --section ${sec}`,
            sectionValue: sec,
          },
          {
            id: "local-demon",
            group: `2b. Critique — ${sec} draft`,
            tool: "Local LLM",
            title: `Demon: ${sec}`,
            detail: `Devil's-advocate attack on the ${sec} draft. Logs versioned to critiques/demon/.`,
            command: `python3 scripts/local_agent.py --role demon ${localFlags} --section ${sec}`,
            sectionValue: sec,
          }
        );
      });

      // --- Group 2c: Full review + rejection sim ---
      templates.push(
        {
          id: "local-argue",
          group: "2c. Full Review",
          tool: "Local LLM",
          title: "Argue: full project",
          detail: "Comprehensive reviewer-#2 pass across all loaded drafts, brief, and planning files.",
          command: `python3 scripts/local_agent.py --role argue ${localFlags}`,
        },
        {
          id: "local-demon",
          group: "2c. Full Review",
          tool: "Local LLM",
          title: "Demon: full project",
          detail: "Full devil's-advocate attack — everything that could kill this project.",
          command: `python3 scripts/local_agent.py --role demon ${localFlags}`,
        },
        {
          id: "local-rejection-sim",
          group: "2c. Full Review",
          tool: "Local LLM",
          title: "Rejection Simulator",
          detail: "Pre-mortem: simulate funder/journal rejection scenarios.",
          command: `python3 scripts/local_agent.py --role rejection-sim ${localFlags}`,
        },
      );

      return templates;
    }
    return [
      {
        id: "idea-note",
        group: "0. Idea / Exploration",
        tool: "cloud-safe",
        title: "Summarize discussion into idea note",
        detail: "Saves a lightweight evolving summary without storing the full conversation.",
        command: "Summarize our latest discussion as an evolving idea note. Do not save the full transcript. Create or update explorations/idea-notes/IDEA_SLUG.md using explorations/_template/Idea_Note_TEMPLATE.md. Add only the new or changed ideas under today's date, keep a short Current Summary, and list open questions plus candidate papers to check if any.",
      },
      {
        id: "promote-idea",
        group: "0. Idea / Exploration",
        tool: "cloud-safe",
        title: "Promote idea note to Exploration Brief",
        detail: "Use when an idea is focused enough to review but not yet a project.",
        command: "Promote explorations/idea-notes/IDEA_SLUG.md to explorations/ideas/Exploration_Brief_IDEA_SLUG.md using explorations/_template/Exploration_Brief_TEMPLATE.md. Preserve the evolving summary, convert it into a focused starting question, search scope, seed ideas, candidate paper criteria, related wiki anchors, and stop/promote criteria. Do not scout yet.",
      },
      {
        id: "exploration-skeptic",
        group: "0. Idea / Exploration",
        tool: "cloud-safe",
        title: "Run Exploration Skeptic Review",
        detail: "Decides whether an Exploration Brief is actually scout-ready.",
        command: "Read subagents/07-exploration-skeptic.md and act as the Exploration Skeptic for explorations/ideas/Exploration_Brief_IDEA_SLUG.md. Do not search the web and do not scout. Fill or update the Skeptic Review section with whether this is not-ready, brief-ready, scout-ready, or project-ready, plus why, risks, evidence that would change the decision, and a minimal scout plan only if scout-ready.",
      },
      {
        id: "active-exploration",
        group: "0. Idea / Exploration",
        tool: "Codex CLI",
        title: "Promote to active exploration",
        detail: "Creates the active exploration folder after Skeptic Review approves scouting.",
        command: "mkdir -p explorations/active/IDEA_SLUG/{candidates,paper-briefs,_pdfs} && cp explorations/ideas/Exploration_Brief_IDEA_SLUG.md explorations/active/IDEA_SLUG/Exploration_Brief.md && cp explorations/_template/Active_Exploration_README_TEMPLATE.md explorations/active/IDEA_SLUG/README.md && touch explorations/active/IDEA_SLUG/scout-queries.md explorations/active/IDEA_SLUG/notes.md explorations/active/IDEA_SLUG/questions.md explorations/active/IDEA_SLUG/synthesis.md explorations/active/IDEA_SLUG/promote-to-wiki.md explorations/active/IDEA_SLUG/promote-to-project.md",
      },
      {
        id: "exploration-synthesis",
        group: "0. Idea / Exploration",
        tool: "cloud-safe",
        title: "Write exploration-local synthesis",
        detail: "Provisional synthesis inside explorations/active/IDEA_SLUG, not a wiki overview.",
        command: "Read subagents/04-synthesizer.md and act in Exploration-Local Mode for explorations/active/IDEA_SLUG. Use Exploration_Brief.md, notes.md, questions.md, paper-briefs/, candidate metadata, and any relevant already-ingested sources/wiki pages. Write explorations/active/IDEA_SLUG/synthesis.md. Clearly separate ingested wiki evidence from non-ingested candidate leads, and list any items that should be promoted in promote-to-wiki.md.",
      },
      {
        id: "brief",
        group: "1. Project Discovery",
        tool: "Terminal",
        title: "Open project brief",
        detail: "Edit the project contract before scouting or drafting.",
        command: `nano projects/${slug}/Project_Brief.md`,
      },
      {
        id: "queries",
        group: "1. Project Discovery",
        tool: "Terminal",
        title: "Edit scout queries",
        detail: "Add follow-up search campaigns without changing Project_Brief.md.",
        command: `nano projects/${slug}/scout-queries.md`,
      },
      {
        id: "scout",
        group: "1. Project Discovery",
        tool: "Codex CLI",
        title: "Scout papers",
        detail: "Runs Project_Brief terms plus unchecked scout-queries.md items. Completed query items are checked off.",
        command: `python3 scripts/scout_all.py --brief projects/${slug}/Project_Brief.md --out projects/${slug}/candidates/$(date +%F)`,
      },
      {
        id: "scout-campaign",
        group: "1. Project Discovery",
        tool: "Codex CLI",
        title: "Scout query campaign only",
        detail: "Runs only unchecked scout-queries.md items. Useful when triage is already using another candidate batch.",
        command: `python3 scripts/scout_all.py --brief projects/${slug}/Project_Brief.md --out projects/${slug}/candidates/$(date +%F)-campaign --queries-only`,
      },
      {
        id: "triage",
        group: "1. Project Discovery",
        tool: "Codex CLI",
        title: "Triage candidates",
        detail: "Paste into Codex after a candidate batch exists.",
        command: `Read subagents/02-triage.md and act as the Triage agent for project ${slug}. Use projects/${slug}/Project_Brief.md and the newest candidates folder. Write the triage report to projects/${slug}/triage-reports/.`,
      },
      {
        id: "approval-board",
        group: "1. Project Discovery",
        tool: "Terminal",
        title: "Build triage approval board",
        detail: "Creates a local checklist page where you choose Download PDF, Wiki-only ingest, or Skip.",
        command: `python3 scripts/build_triage_approval_board.py --project projects/${slug}`,
      },
      {
        id: "open-approval-board",
        group: "1. Project Discovery",
        tool: "Terminal",
        title: "Open latest approval board",
        detail: project.latest_approval_board ? "Opens the newest generated approval board HTML." : "Build an approval board first if this file does not exist yet.",
        command: project.latest_approval_board ? `open ${project.latest_approval_board}` : `python3 scripts/build_triage_approval_board.py --project projects/${slug}`,
      },
      {
        id: "open-selected-paper-links",
        group: "1. Project Discovery",
        tool: "Terminal",
        title: "Open selected paper links",
        detail: "After approval board Download JSON, replace PATH_TO_DECISIONS_JSON with that file path.",
        command: "python3 scripts/open_pdf_decision_urls.py PATH_TO_DECISIONS_JSON --action both --open",
      },
      {
        id: "ingest",
        group: "2. LLM-Wiki Core",
        tool: "Codex CLI",
        title: "Ingest approved PDFs",
        detail: "Use after you manually place approved PDFs in papers/inbox/.",
        command: `Read subagents/03-ingester.md and act as the Ingester agent for project ${slug}. Ingest approved PDFs from papers/inbox/ into papers/, sources/, wiki/, and index.md. Treat source frontmatter as citation truth and fail loudly if authors, year, or DOI cannot be resolved.`,
      },
      {
        id: "global-wiki-ingest",
        group: "2. LLM-Wiki Core",
        tool: "Codex CLI",
        title: "Global wiki ingest from inbox",
        detail: "Project-independent. Use when you already have PDFs and want them in the wiki without Scout, Triage, or Project_Brief.",
        command: "Read subagents/03-ingester.md and act as the Ingester agent in direct wiki ingest mode.\n\nDo not use any Project_Brief. Do not use Scout or Triage. Ingest only the PDFs currently placed in papers/inbox/ into the global LLM-Wiki.\n\nFor each PDF:\n- copy/rename it into papers/\n- create sources/{stem}.md with citation-truth frontmatter\n- create wiki/{category}/{stem}.md\n- choose the best category from AGENTS.md\n- update index.md\n\nUse only the PDF content. Do not use web search. If author, year, or DOI cannot be resolved, stop and list the unresolved papers instead of guessing.",
      },
      {
        id: "synthesize",
        group: "2. LLM-Wiki Core",
        tool: "cloud-safe",
        title: "Synthesize overview",
        detail: "Use after at least 3 related papers are ingested.",
        command: project.confidential
          ? `This path is confidential_tier: local-only. Run python3 scripts/local_agent.py --role drafter --project ${slug} to handle locally. For public synthesis, create a redacted exploration idea-note first.`
          : `Read subagents/04-synthesizer.md and act as the Synthesizer agent for the public library-ingest topic ${slug}. Use relevant sources/ and wiki/ pages only. Write or update the appropriate wiki/overviews/ page.`,
      },
      {
        id: "prep-files",
        group: "3. Project Writing Layer",
        tool: "Terminal",
        title: "Create optional paper-in-prep files",
        detail: "Use only when the project is ready for figure/data/critique tracking. Existing files are not overwritten.",
        command: `mkdir -p projects/${slug}/data-updates projects/${slug}/critiques && cp -n projects/_template/figure-plan_TEMPLATE.md projects/${slug}/figure-plan.md && cp -n projects/_template/experiment-roadmap_TEMPLATE.md projects/${slug}/experiment-roadmap.md && cp -n projects/_template/critique-log_TEMPLATE.md projects/${slug}/critiques/critique-log.md`,
      },
      {
        id: "data-update",
        group: "3. Project Writing Layer",
        tool: "Terminal",
        title: "Add data update",
        detail: "Creates one editable panel/figure update file from the template.",
        command: `mkdir -p projects/${slug}/data-updates && cp -n projects/_template/data-updates_TEMPLATE.md projects/${slug}/data-updates/$(date +%F)-fig-panel.md`,
      },
      {
        id: "draft",
        group: "3. Project Writing Layer",
        tool: project.confidential ? "Local LLM" : "Codex CLI",
        title: "Draft a section",
        detail: project.confidential ? "Confidential drafting runs through LM Studio only." : "Library-ingest projects do not use the confidential drafting lane.",
        command: project.confidential
          ? `python3 scripts/local_agent.py --role drafter --project ${slug}`
          : "No project draft is needed for a library_ingest project.",
      },
      {
        id: "verify",
        group: "3. Project Writing Layer",
        tool: "Codex CLI",
        title: "Verify a draft",
        detail: "Replace X with the draft basename before running.",
        command: `python3 scripts/verify_citations.py projects/${slug}/drafts/X.draft.md projects/${slug}/drafts/X.draft_claim_log.md`,
      },
      {
        id: "critic",
        group: "3. Project Writing Layer",
        tool: project.confidential ? "Local LLM" : "Codex CLI",
        title: "Run project Critic",
        detail: project.confidential ? "Confidential critique runs through the local Argue role." : "Library-ingest projects do not use the confidential critique lane.",
        command: project.confidential
          ? `python3 scripts/local_agent.py --role argue --project ${slug}`
          : "No project critique is needed for a library_ingest project.",
      },
    ];
  }

  function defaultCreateProjectCommand() {
    return "mkdir -p projects/YOUR_PROJECT_SLUG/{candidates,triage-reports,drafts,notes} && cp projects/_template/Project_Brief_TEMPLATE.md projects/YOUR_PROJECT_SLUG/Project_Brief.md";
  }

  function copyText(value, button) {
    const markCopied = () => {
      const original = button.textContent;
      button.textContent = "Copied";
      window.setTimeout(() => {
        button.textContent = original;
      }, 1400);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(value).then(markCopied);
      return;
    }
    const scratch = document.createElement("textarea");
    scratch.value = value;
    scratch.setAttribute("readonly", "");
    scratch.style.position = "fixed";
    scratch.style.left = "-9999px";
    document.body.append(scratch);
    scratch.select();
    document.execCommand("copy");
    scratch.remove();
    markCopied();
  }

  async function getDirectoryIfExists(parentHandle, name) {
    try {
      return await parentHandle.getDirectoryHandle(name);
    } catch (error) {
      if (error && error.name === "NotFoundError") return null;
      throw error;
    }
  }

  async function getFileIfExists(parentHandle, name) {
    try {
      return await parentHandle.getFileHandle(name);
    } catch (error) {
      if (error && error.name === "NotFoundError") return null;
      throw error;
    }
  }

  async function readFileText(fileHandle) {
    if (!fileHandle) return "";
    const file = await fileHandle.getFile();
    return file.text();
  }

  function parseMarkdownTable(textValue) {
    const rows = [];
    let header = null;
    textValue.split(/\r?\n/).forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed.startsWith("|") || !trimmed.endsWith("|")) return;
      const cells = trimmed.slice(1, -1).split("|").map((cell) => cell.trim());
      if (!header) {
        header = cells.map((cell) => cell.toLowerCase().replace(/[ /\-]+/g, "_"));
        return;
      }
      if (cells.every((cell) => /^:?-{3,}:?$/.test(cell))) return;
      const row = {};
      header.forEach((key, index) => {
        row[key] = cells[index] || "";
      });
      rows.push(row);
    });
    return rows;
  }

  function parseFrontmatter(textValue) {
    const match = /^---\n([\s\S]*?)\n---/.exec(textValue);
    const meta = {};
    if (!match) return meta;
    match[1].split(/\r?\n/).forEach((line) => {
      const separator = line.indexOf(":");
      if (separator === -1) return;
      const key = line.slice(0, separator).trim();
      let value = line.slice(separator + 1).trim();
      value = value.replace(/^["']|["']$/g, "");
      if (key) meta[key] = value;
    });
    return meta;
  }

  function progressFromRows(rows) {
    const scores = [];
    const statusCounts = {};
    rows.forEach((row) => {
      const status = String(row.status || "").trim().toLowerCase().replace(/\s+/g, "_");
      if (!status) return;
      statusCounts[status] = (statusCounts[status] || 0) + 1;
      const score = Object.prototype.hasOwnProperty.call(statusScores, status) ? statusScores[status] : 0;
      if (score !== null) scores.push(score);
    });
    return {
      percent: scores.length ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length) : 0,
      tracked_items: scores.length,
      status_counts: statusCounts,
    };
  }

  async function countFiles(handle, suffix, options = {}) {
    let count = 0;
    const exclude = options.exclude || new Set();
    for await (const [name, child] of handle.entries()) {
      if (exclude.has(name)) continue;
      if (child.kind === "file" && name.endsWith(suffix)) count += 1;
      if (child.kind === "directory" && options.recursive) {
        count += await countFiles(child, suffix, options);
      }
    }
    return count;
  }

  async function directoryMtimeLabel(handle) {
    let newest = 0;
    for await (const [, child] of handle.entries()) {
      if (child.kind !== "file") continue;
      const file = await child.getFile();
      newest = Math.max(newest, file.lastModified || 0);
    }
    if (!newest) return "Live scan";
    return new Date(newest).toLocaleString();
  }

  async function scanWorkspace(rootHandle) {
    const projectsHandle = await getDirectoryIfExists(rootHandle, "projects");
    if (!projectsHandle) {
      throw new Error("Selected folder does not contain projects/.");
    }
    const projects = [];
    for await (const [name, handle] of projectsHandle.entries()) {
      if (handle.kind !== "directory" || name.startsWith(".") || name === "_template") continue;
      const brief = await getFileIfExists(handle, "Project_Brief.md");
      const scoutQueries = await getFileIfExists(handle, "scout-queries.md");
      const candidates = await getDirectoryIfExists(handle, "candidates");
      const triage = await getDirectoryIfExists(handle, "triage-reports");
      const drafts = await getDirectoryIfExists(handle, "drafts");
      const notes = await getDirectoryIfExists(handle, "notes");
      const figurePlan = await getFileIfExists(handle, "figure-plan.md");
      const experimentRoadmap = await getFileIfExists(handle, "experiment-roadmap.md");
      const dataUpdates = await getDirectoryIfExists(handle, "data-updates");
      const critiques = await getDirectoryIfExists(handle, "critiques");
      const candidateJsons = candidates ? await countFiles(candidates, ".json", { recursive: true }) : 0;
      const triageReports = triage ? await countFiles(triage, ".md") : 0;
      const stagedDrafts = drafts ? await countFiles(drafts, ".draft.md") : 0;
      const claimLogs = drafts ? await countFiles(drafts, ".draft_claim_log.md") : 0;
      const allDraftMarkdown = drafts ? await countFiles(drafts, ".md") : 0;
      const finalDrafts = Math.max(allDraftMarkdown - stagedDrafts - claimLogs, 0);
      const noteCount = notes ? await countFiles(notes, ".md") : 0;
      const dataUpdateCount = dataUpdates ? await countFiles(dataUpdates, ".md") : 0;
      const critiqueCount = critiques ? await countFiles(critiques, ".md") : 0;
      const briefMeta = parseFrontmatter(await readFileText(brief));
      const projectType = briefMeta.project_type || "live-scan";
      const confidential = projectType !== "library_ingest" || briefMeta.confidential_tier === "local-only";
      const figureRows = parseMarkdownTable(await readFileText(figurePlan));
      const experimentRows = parseMarkdownTable(await readFileText(experimentRoadmap));
      projects.push({
        slug: name,
        title: briefMeta.title || name,
        project_type: projectType,
        confidential,
        status: confidential ? "local-only" : "live",
        deadline: briefMeta.deadline || "",
        tracked: Boolean(brief),
        last_touched: await directoryMtimeLabel(handle),
        progress: {
          percent: Math.round([
            Boolean(brief),
            Boolean(scoutQueries),
            candidateJsons > 0,
            triageReports > 0,
            stagedDrafts + finalDrafts > 0,
          ].filter(Boolean).length / 5 * 100),
        },
        counts: {
          candidate_jsons: Math.max(candidateJsons - (candidates ? 1 : 0), 0),
          triage_reports: triageReports,
          approval_boards: 0,
          staged_drafts: stagedDrafts,
          final_drafts: finalDrafts,
          claim_logs: claimLogs,
          candidate_batches: 0,
          notes: noteCount,
          data_updates: dataUpdateCount,
          critique_reports: critiqueCount,
          planned_figures: figureRows.length,
          planned_experiments: experimentRows.length,
        },
        paper_in_prep: {
          figure_plan_exists: Boolean(figurePlan),
          experiment_roadmap_exists: Boolean(experimentRoadmap),
          data_updates_dir_exists: Boolean(dataUpdates),
          critiques_dir_exists: Boolean(critiques),
          figure_progress: progressFromRows(figureRows),
          experiment_progress: progressFromRows(experimentRows),
        },
        next_step: brief ? "Use command launcher" : "Create Project_Brief.md",
        recommended_command: confidential
          ? `python3 scripts/local_agent.py --role drafter --project ${name}`
          : (brief ? `nano projects/${name}/Project_Brief.md` : `cp projects/_template/Project_Brief_TEMPLATE.md projects/${name}/Project_Brief.md`),
      });
    }
    return projects.sort((a, b) => a.slug.localeCompare(b.slug));
  }

  function renderCommandLauncher(projects, sourceLabel) {
    const commandRoot = byId("command-center");
    commandRoot.replaceChildren();

    const card = el("article", "launcher-card");
    const controls = el("div", "launcher-controls");
    const projectLabel = el("label");
    projectLabel.append(labelWithHelp("Project", helpCopy.projectSelect));
    const projectSelect = el("select", "select-input");
    const actionLabel = el("label");
    actionLabel.append(labelWithHelp("Action", helpCopy.actionSelect));
    const actionSelect = el("select", "select-input");
    const projectField = el("div", "launcher-field");
    const actionField = el("div", "launcher-field");
    const actionSelectRow = el("div", "select-help-row");
    const actionHelpButton = text(el("button", "help-button"), "?");
    actionHelpButton.type = "button";
    actionHelpButton.setAttribute("aria-label", "Selected action help");
    actionSelectRow.append(actionSelect, actionHelpButton);
    projectField.append(projectLabel, projectSelect);
    actionField.append(actionLabel, actionSelectRow);
    // Keyword input (shown only for pre-drafter action)
    const keywordRow = el("div", "launcher-field keyword-input-row");
    keywordRow.style.display = "none";
    const keywordLabel = el("label");
    keywordLabel.textContent = "Topic keywords (comma-separated)";
    const keywordInput = el("input", "select-input");
    keywordInput.type = "text";
    keywordInput.placeholder = "e.g. cerebellum, LTD, timing, mGluR1, PKC";
    keywordLabel.append(keywordInput);
    keywordRow.append(keywordLabel);

    // URL input (shown for fetch-external-info action)
    const urlRow = el("div", "launcher-field url-input-row");
    urlRow.style.display = "none";
    const urlLabel = el("label");
    urlLabel.textContent = "URL to fetch (public page)";
    const urlInput = el("input", "select-input");
    urlInput.type = "url";
    urlInput.placeholder = "https://grants.nih.gov/... or https://department.edu/faculty";
    urlLabel.append(urlInput);
    urlRow.append(urlLabel);

    // Section sub-select (shown for consolidated drafter action)
    const sectionRow = el("div", "launcher-field section-input-row");
    sectionRow.style.display = "none";
    const sectionLabel = el("label");
    sectionLabel.textContent = "Section";
    const sectionSelect = el("select", "select-input");
    sectionLabel.append(sectionSelect);
    sectionRow.append(sectionLabel);
    // Custom section — stored here after user answers the prompt popup
    let customSectionValue = "";
    // (no inline row needed — we use window.prompt instead)
    const sectionCustomRow = el("div", "launcher-field section-custom-row");
    sectionCustomRow.style.display = "none";   // always hidden; kept for backward compat
    sectionSelect.addEventListener("change", () => {
      if (sectionSelect.value === "etc") {
        const entered = window.prompt("Enter custom section name (e.g. acknowledgements, cover-letter):", customSectionValue || "");
        if (entered !== null && entered.trim()) {
          customSectionValue = entered.trim();
        } else if (entered === null) {
          // User cancelled — revert to first option
          sectionSelect.value = sectionSelect.options[0] ? sectionSelect.options[0].value : "etc";
          customSectionValue = "";
        } else {
          customSectionValue = "";
        }
      } else {
        customSectionValue = "";
      }
      updateCommand();
    });

    const copyGroup = el("div", "copy-command-group");
    const runButton = text(el("button", "copy-button primary run-button"), "Run");
    const copyButton = text(el("button", "copy-button"), "Copy command");
    copyButton.type = "button";
    runButton.type = "button";
    copyGroup.append(runButton, copyButton, helpButton(helpCopy.runCommand), helpButton(helpCopy.copyCommand));

    if (!projects.length) {
      projectSelect.append(text(el("option"), "No projects found"));
      actionSelect.append(text(el("option"), "Create first project"));
    } else {
      projects.forEach((project) => {
        const option = text(el("option"), `${project.slug}${project.status ? ` (${project.status})` : ""}`);
        option.value = project.slug;
        projectSelect.append(option);
      });
    }

    const commandText = text(el("code", "command-text launcher-command"), "");
    const runOutput = text(el("pre", "run-output"), "");

    function selectedProject() {
      return projects.find((project) => project.slug === projectSelect.value);
    }

    function fillActions() {
      actionSelect.replaceChildren();
      const project = selectedProject();
      const templates = project ? projectCommandTemplates(project) : [{
        id: "create",
        tool: "Terminal",
        title: "Create first project workspace",
        detail: "Replace YOUR_PROJECT_SLUG before running.",
        command: defaultCreateProjectCommand(),
      }];
      let activeGroup = "";
      let groupNode = actionSelect;
      templates.forEach((template) => {
        if (template.group && template.group !== activeGroup) {
          activeGroup = template.group;
          groupNode = document.createElement("optgroup");
          groupNode.label = activeGroup;
          actionSelect.append(groupNode);
        }
        const option = text(el("option"), `${template.title} · ${template.tool}`);
        option.value = template.id;
        groupNode.append(option);
      });
      updateCommand();
    }

    function currentTemplate() {
      const project = selectedProject();
      const templates = project ? projectCommandTemplates(project) : [{
        id: "create",
        tool: "Terminal",
        title: "Create first project workspace",
        detail: "Replace YOUR_PROJECT_SLUG before running.",
        command: defaultCreateProjectCommand(),
      }];
      return templates.find((template) => template.id === actionSelect.value) || templates[0];
    }

    function resolvedDraftCommand(template) {
      if (!template.hasSectionInput) return template.command;
      const chosenSection = sectionSelect.value === "etc"
        ? (customSectionValue || "custom")
        : sectionSelect.value;
      return template.command.replace("SECTION", chosenSection || "introduction");
    }

    function updateCommand() {
      const template = currentTemplate();
      // Show keyword input only for pre-drafter
      keywordRow.style.display = template.hasKeywordInput ? "" : "none";
      // Show URL input only for fetch-external-info
      urlRow.style.display = template.hasFetchInput ? "" : "none";
      if (template.hasFetchInput) {
        urlInput.placeholder = template.fetchType === "dept_faculty"
          ? "https://neuroscience.stanford.edu/people/faculty"
          : "https://grants.nih.gov/grants/guide/rfa-files/RFA-NS-XX-XXX.html";
      }
      // Show section sub-select for consolidated drafter
      if (template.hasSectionInput) {
        sectionRow.style.display = "";
        // Repopulate section options if needed
        const opts = template.sectionOptions || [];
        if (sectionSelect.dataset.forTemplate !== template.id + (selectedProject() ? selectedProject().slug : "")) {
          sectionSelect.replaceChildren();
          opts.forEach((sec) => {
            const opt = text(el("option"), sec === "etc" ? "etc (custom)" : sec);
            opt.value = sec;
            sectionSelect.append(opt);
          });
          sectionSelect.dataset.forTemplate = template.id + (selectedProject() ? selectedProject().slug : "");
        }
        // Show chosen custom value as a hint in the "etc" option label
        if (sectionSelect.value === "etc" && customSectionValue) {
          const etcOpt = Array.from(sectionSelect.options).find((o) => o.value === "etc");
          if (etcOpt) etcOpt.textContent = `etc → ${customSectionValue}`;
        }
        sectionCustomRow.style.display = "none";  // always hidden — popup used instead
      } else {
        sectionRow.style.display = "none";
        sectionCustomRow.style.display = "none";
      }
      const cmd = resolvedDraftCommand(template);
      commandText.textContent = cmd;
      const runnable = canRunTemplate(template);
      runButton.disabled = !runnable;
      runButton.textContent = runnable ? "Run" : "Copy-only";
    }

    function showCurrentActionHelp() {
      const template = currentTemplate();
      const copy = actionHelpCopy[template.id] || {
        title: template.title,
        body: template.detail,
      };
      showHelp(copy);
    }

    projectSelect.addEventListener("change", fillActions);
    actionSelect.addEventListener("change", updateCommand);
    actionHelpButton.addEventListener("click", showCurrentActionHelp);
    copyButton.addEventListener("click", () => {
      const tmpl = currentTemplate();
      // For pre-drafter, update command with actual keywords before copying
      if (tmpl.id === "pre-drafter" && keywordInput.value.trim()) {
        const kw = keywordInput.value.trim();
        const project = selectedProject();
        const slug = project ? project.slug : "YOUR_PROJECT";
        const ptype = project && project.project_type ? project.project_type : "paper_in_prep";
        copyText(
          `python3 scripts/pre_drafter.py --project ${slug} --type ${ptype} --keywords "${kw}"`,
          copyButton,
        );
      } else {
        copyText(resolvedDraftCommand(tmpl), copyButton);
      }
    });
    runButton.addEventListener("click", () => {
      const tmpl = currentTemplate();
      let extraParams = {};
      if (tmpl.hasKeywordInput) {
        extraParams = { keywords: keywordInput.value.trim() };
      } else if (tmpl.hasFetchInput) {
        extraParams = {
          url: urlInput.value.trim(),
          info_type: tmpl.fetchType || "general",
          slug: selectedProject() ? selectedProject().slug : "",
        };
      } else if (tmpl.hasSectionInput) {
        // Consolidated drafter: get section from sub-select (or prompt result for "etc")
        const chosenSection = sectionSelect.value === "etc"
          ? (customSectionValue || "custom")
          : sectionSelect.value;
        extraParams = { section: chosenSection };
      } else if (tmpl.sectionValue) {
        extraParams = { section: tmpl.sectionValue };
      }
      runServerAction(tmpl, selectedProject(), runButton, runOutput, extraParams);
    });

    controls.append(projectField, actionField, keywordRow, urlRow, sectionRow, sectionCustomRow, copyGroup, commandText);
    card.append(controls, runOutput);

    // ---- New Project creator ----
    const newProjectCard = el("article", "launcher-card new-project-card");
    newProjectCard.innerHTML = `
      <div class="launcher-controls">
        <div class="launcher-field">
          <label><span>New confidential project</span>
            <input id="new-project-slug" class="select-input" type="text" placeholder="slug-kebab-case (e.g. 2026-my-grant)" />
          </label>
        </div>
        <div class="launcher-field">
          <label><span>Project type</span>
            <select id="new-project-type" class="select-input">
              <option value="paper_in_prep">Research article (paper_in_prep)</option>
              <option value="review_article">Review article</option>
              <option value="grant">Grant application</option>
              <option value="job_application">Job application (research statement)</option>
            </select>
          </label>
        </div>
        <div class="launcher-field">
          <label><span>Working title</span>
            <input id="new-project-title" class="select-input" type="text" placeholder="Working title for this project" />
          </label>
        </div>
        <div class="copy-command-group">
          <button id="new-project-create" class="copy-button primary run-button" type="button">Create Project</button>
          <button id="new-project-copy" class="copy-button" type="button">Copy mkdir command</button>
        </div>
      </div>
      <pre id="new-project-output" class="run-output" data-state="">Enter a slug and type, then click Create Project. (ex., cerebellar-tbi-review)</pre>
    `;
    commandRoot.append(newProjectCard);
    commandRoot.append(card);

    const npSlug = newProjectCard.querySelector("#new-project-slug");
    const npType = newProjectCard.querySelector("#new-project-type");
    const npTitle = newProjectCard.querySelector("#new-project-title");
    const npCreate = newProjectCard.querySelector("#new-project-create");
    const npCopy = newProjectCard.querySelector("#new-project-copy");
    const npOutput = newProjectCard.querySelector("#new-project-output");

    npCopy.addEventListener("click", () => {
      const s = (npSlug.value || "YOUR_SLUG").trim().replace(/[^a-z0-9_-]/g, "-");
      copyText(
        `mkdir -p projects/${s}/{Drafts,critiques/argue,critiques/demon,rejection-sims,notes,data-updates} && cp projects/_template/Project_Brief.md projects/${s}/Project_Brief.md`,
        npCopy,
      );
    });

    npCreate.addEventListener("click", async () => {
      const s = (npSlug.value || "").trim();
      if (!s) { npOutput.textContent = "Enter a slug first."; return; }
      const ptype = npType.value;
      const title = (npTitle.value || "Working title").trim();
      if (!serverState.online || !serverState.allowed.has("create-project")) {
        npOutput.textContent = "Dashboard server not running. Use the Copy command instead.";
        return;
      }
      npCreate.disabled = true;
      npCreate.textContent = "Creating...";
      npOutput.dataset.state = "running";
      npOutput.textContent = "Creating project...";
      try {
        const resp = await fetch(apiUrl("/api/run"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action_id: "create-project",
            params: { slug: s, project_type: ptype, title },
          }),
        });
        const result = await resp.json();
        npOutput.dataset.state = result.ok ? "ok" : "error";
        npOutput.textContent = result.ok
          ? `Created!\n\n${result.stdout}`
          : `Failed:\n${result.stderr || result.stdout}`;
        if (result.ok && result.reload_suggested) {
          window.setTimeout(() => window.location.reload(), 1400);
        }
      } catch (e) {
        npOutput.dataset.state = "error";
        npOutput.textContent = `Error: ${e.message}`;
      } finally {
        npCreate.disabled = false;
        npCreate.textContent = "Create Project";
      }
    });

    fillActions();
  }

  function renderWorkspaceTools(projects) {
    const root = byId("workspace-tools");
    root.replaceChildren();
    const status = text(el("span", "workspace-status"), "Static data loaded");
    const rebuildButton = text(el("button", "copy-button"), "Rebuild data");
    const reloadButton  = text(el("button", "copy-button"), "Reload view");
    rebuildButton.type = "button";
    reloadButton.type  = "button";

    rebuildButton.addEventListener("click", async () => {
      if (!serverState.online || !serverState.allowed.has("rebuild-dashboard")) {
        copyText("python3 scripts/build_dashboard.py", rebuildButton);
        return;
      }
      const original = rebuildButton.textContent;
      rebuildButton.disabled = true;
      rebuildButton.textContent = "Rebuilding...";
      status.textContent = "Rebuilding dashboard data...";
      try {
        const response = await fetch(apiUrl("/api/run"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: "rebuild-dashboard" }),
        });
        const result = await response.json();
        status.textContent = result.ok ? "Rebuilt. Reloading..." : `Rebuild failed: ${result.stderr || result.stdout}`;
        if (result.ok) window.setTimeout(() => window.location.reload(), 800);
      } catch (error) {
        status.textContent = `Rebuild failed: ${error.message}`;
      } finally {
        rebuildButton.disabled = false;
        rebuildButton.textContent = original;
      }
    });
    reloadButton.addEventListener("click", () => window.location.reload());

    const rebuildGroup = el("div", "toolbar-help-group");
    const reloadGroup  = el("div", "toolbar-help-group");
    rebuildGroup.append(rebuildButton, helpButton(helpCopy.rebuildCommand));
    reloadGroup.append(reloadButton,  helpButton(helpCopy.reloadView));
    root.append(rebuildGroup, reloadGroup, status);
    renderCommandLauncher(projects, "static dashboard data");
    setupPublishRevisionUI(projects);
  }

  // ── Publish / Revision lifecycle UI ──────────────────────────────────────
  function setupPublishRevisionUI(projects) {
    const publishBtn = byId("publish-project-btn");
    const revisionBtn = byId("start-revision-btn");
    const projectSel = document.querySelector("#command-center select[data-role='project']");
    // Fall back: command launcher first select element
    const findProjectSelect = () => document.querySelectorAll("#command-center select")[0];

    function refreshLifecycleButtons() {
      const sel = projectSel || findProjectSelect();
      if (!sel || !publishBtn || !revisionBtn) return;
      const slug = sel.value;
      const project = projects.find(p => p.slug === slug);
      if (!project) {
        publishBtn.hidden = true;
        revisionBtn.hidden = true;
        return;
      }
      // Show Publish only for paper_in_prep that is NOT already published
      const eligibleForPublish = project.project_type === "paper_in_prep" && !project.is_published;
      publishBtn.hidden = !eligibleForPublish;
      // Show Revision only for projects that ARE published
      revisionBtn.hidden = !project.is_published;
    }

    refreshLifecycleButtons();
    const liveSel = findProjectSelect();
    if (liveSel) liveSel.addEventListener("change", refreshLifecycleButtons);

    // ── Publish modal ─────────────────────────────────────────────────────
    const modal = byId("publish-modal");
    const closeBtn = byId("publish-modal-close");
    const cancelBtn = byId("publish-cancel-btn");
    const verifyBtn = byId("publish-verify-btn");
    const executeBtn = byId("publish-execute-btn");
    const urlInput = byId("publish-preprint-url");
    const pathInput = byId("publish-acceptance-path");
    const fileInput = byId("publish-acceptance-file");
    const browseBtn = byId("publish-browse-btn");
    const fileHint = byId("publish-file-hint");
    const journalInput = byId("publish-journal");
    const notesInput = byId("publish-notes");
    const verifyOut = byId("publish-verify-output");

    function closePublishModal() {
      if (modal) modal.hidden = true;
      if (executeBtn) executeBtn.disabled = true;
      if (verifyOut) { verifyOut.style.display = "none"; verifyOut.textContent = ""; }
      if (urlInput) urlInput.value = "";
      if (pathInput) pathInput.value = "";
      if (journalInput) journalInput.value = "";
      if (notesInput) notesInput.value = "";
      if (fileHint) fileHint.textContent = "";
    }

    if (publishBtn) {
      publishBtn.addEventListener("click", () => {
        const sel = projectSel || findProjectSelect();
        if (!sel || !sel.value) { alert("Select a project first."); return; }
        if (!serverState.online) { alert("Dashboard server required for publish action."); return; }
        if (modal) modal.hidden = false;
      });
    }
    if (closeBtn) closeBtn.addEventListener("click", closePublishModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closePublishModal);
    if (modal) {
      modal.addEventListener("click", (e) => { if (e.target === modal) closePublishModal(); });
    }
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal && !modal.hidden) closePublishModal();
    });

    // File picker — drops the file to a temp path so the server can read it
    if (browseBtn && fileInput) {
      browseBtn.addEventListener("click", () => fileInput.click());
      fileInput.addEventListener("change", async () => {
        const f = fileInput.files && fileInput.files[0];
        if (!f) return;
        if (fileHint) fileHint.textContent = `선택됨: ${f.name} (${(f.size/1024).toFixed(1)} KB) — Drag & drop on the path field, or paste the full path manually.`;
        // Browser security restricts auto-getting the full path of a file. Ask user to type/paste it.
      });
    }

    // Drag-drop support on path input
    if (pathInput) {
      pathInput.addEventListener("dragover", (e) => { e.preventDefault(); pathInput.classList.add("modal-input--drop"); });
      pathInput.addEventListener("dragleave", () => pathInput.classList.remove("modal-input--drop"));
      pathInput.addEventListener("drop", (e) => {
        e.preventDefault();
        pathInput.classList.remove("modal-input--drop");
        const files = e.dataTransfer && e.dataTransfer.files;
        if (files && files[0]) {
          // Browsers expose .path on Electron/Chrome with dnd; fall back to name
          const p = files[0].path || files[0].name;
          pathInput.value = p;
          if (fileHint) fileHint.textContent = `Dropped: ${files[0].name}`;
        }
      });
    }

    if (verifyBtn) {
      verifyBtn.addEventListener("click", async () => {
        const sel = projectSel || findProjectSelect();
        const slug = sel ? sel.value : "";
        if (!slug) { alert("Select a project first."); return; }
        const params = {
          project_slug: slug,
          preprint_url: urlInput ? urlInput.value.trim() : "",
          acceptance_letter_path: pathInput ? pathInput.value.trim() : "",
        };
        if (!params.preprint_url && !params.acceptance_letter_path) {
          alert("Provide a preprint URL or an acceptance-letter PDF path.");
          return;
        }
        verifyBtn.disabled = true;
        const orig = verifyBtn.textContent; verifyBtn.textContent = "Verifying...";
        if (verifyOut) { verifyOut.style.display = "block"; verifyOut.dataset.state = "running"; verifyOut.textContent = "Verifying proof..."; }
        try {
          const resp = await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "verify-publish", params }) });
          const result = await resp.json();
          if (verifyOut) {
            verifyOut.dataset.state = result.ok ? "ok" : "error";
            if (result.ok && result.verification) {
              const v = result.verification;
              const lines = ["✓ Verification passed."];
              if (v.preprint_url_ok) lines.push(`  ✓ Preprint URL reachable: ${v.preprint_url}`);
              if (v.acceptance_letter_ok) lines.push(`  ✓ Acceptance letter found: ${v.acceptance_letter_resolved}`);
              lines.push("\nClick 'Move to published/' to complete the publication.");
              verifyOut.textContent = lines.join("\n");
            } else {
              verifyOut.textContent = result.stderr || result.error || "Verification failed.";
            }
          }
          if (result.ok && executeBtn) executeBtn.disabled = false;
        } catch (e) {
          if (verifyOut) { verifyOut.dataset.state = "error"; verifyOut.textContent = `Error: ${e.message}`; }
        } finally { verifyBtn.disabled = false; verifyBtn.textContent = orig; }
      });
    }

    if (executeBtn) {
      executeBtn.addEventListener("click", async () => {
        const sel = projectSel || findProjectSelect();
        const slug = sel ? sel.value : "";
        if (!slug) return;
        if (!confirm(`정말로 projects/${slug}/ 를 projects/published/${slug}/ 로 이동할까요?\n이 작업 후 클라우드 LLM이 이 폴더를 읽을 수 있게 됩니다.`)) return;
        const params = {
          project_slug: slug,
          preprint_url: urlInput ? urlInput.value.trim() : "",
          acceptance_letter_path: pathInput ? pathInput.value.trim() : "",
          journal: journalInput ? journalInput.value.trim() : "",
          notes: notesInput ? notesInput.value.trim() : "",
        };
        executeBtn.disabled = true;
        const orig = executeBtn.textContent; executeBtn.textContent = "Publishing...";
        try {
          const resp = await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "publish-project", params }) });
          const result = await resp.json();
          if (verifyOut) {
            verifyOut.style.display = "block";
            verifyOut.dataset.state = result.ok ? "ok" : "error";
            verifyOut.textContent = [result.stdout, result.stderr].filter(Boolean).join("\n\n");
          }
          if (result.ok) {
            setTimeout(() => { closePublishModal(); location.reload(); }, 1500);
          }
        } catch (e) {
          if (verifyOut) { verifyOut.style.display = "block"; verifyOut.dataset.state = "error"; verifyOut.textContent = `Error: ${e.message}`; }
        } finally { executeBtn.disabled = false; executeBtn.textContent = orig; }
      });
    }

    // ── Revision modal ────────────────────────────────────────────────────
    const revModal = byId("revision-modal");
    const revClose = byId("revision-modal-close");
    const revCancel = byId("revision-cancel-btn");
    const revExecute = byId("revision-execute-btn");
    const revTag = byId("revision-tag");
    const revOut = byId("revision-output");

    function closeRevisionModal() {
      if (revModal) revModal.hidden = true;
      if (revOut) { revOut.style.display = "none"; revOut.textContent = ""; }
      if (revTag) revTag.value = "r1";
    }

    if (revisionBtn) {
      revisionBtn.addEventListener("click", () => {
        const sel = projectSel || findProjectSelect();
        if (!sel || !sel.value) { alert("Select a published project first."); return; }
        if (!serverState.online) { alert("Dashboard server required."); return; }
        if (revModal) revModal.hidden = false;
      });
    }
    if (revClose) revClose.addEventListener("click", closeRevisionModal);
    if (revCancel) revCancel.addEventListener("click", closeRevisionModal);
    if (revModal) revModal.addEventListener("click", (e) => { if (e.target === revModal) closeRevisionModal(); });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && revModal && !revModal.hidden) closeRevisionModal();
    });

    if (revExecute) {
      revExecute.addEventListener("click", async () => {
        const sel = projectSel || findProjectSelect();
        const slug = sel ? sel.value : "";
        if (!slug) return;
        const tag = revTag ? revTag.value.trim() || "r1" : "r1";
        revExecute.disabled = true;
        const orig = revExecute.textContent; revExecute.textContent = "Creating...";
        if (revOut) { revOut.style.display = "block"; revOut.dataset.state = "running"; revOut.textContent = "Creating revision project..."; }
        try {
          const resp = await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "start-revision", params: { project_slug: slug, revision_tag: tag } }) });
          const result = await resp.json();
          if (revOut) {
            revOut.dataset.state = result.ok ? "ok" : "error";
            revOut.textContent = [result.stdout, result.stderr].filter(Boolean).join("\n\n");
          }
          if (result.ok) setTimeout(() => { closeRevisionModal(); location.reload(); }, 1500);
        } catch (e) {
          if (revOut) { revOut.dataset.state = "error"; revOut.textContent = `Error: ${e.message}`; }
        } finally { revExecute.disabled = false; revExecute.textContent = orig; }
      });
    }
  }

  function renderExplorations(explorations) {
    const root = byId("exploration-overview");
    if (!root) return;
    root.replaceChildren();
    if (!explorations) {
      root.append(emptyState("Exploration data is missing. Rebuild after creating explorations/."));
      return;
    }

    const stats = el("div", "exploration-stats");
    [
      ["Idea notes", explorations.idea_notes || 0],
      ["Briefs", explorations.briefs || 0],
      ["Active", explorations.active || 0],
      ["Archived", explorations.archived || 0],
    ].forEach(([label, value]) => {
      const chip = el("div", "exploration-chip");
      chip.append(text(el("span"), label));
      chip.append(text(el("strong"), String(value)));
      stats.append(chip);
    });

    const recent = el("div", "exploration-list");
    if (!explorations.recent || !explorations.recent.length) {
      recent.append(emptyState("No idea notes yet. Use the command launcher to summarize a discussion into an idea note."));
    } else {
      explorations.recent.forEach((item) => {
        const card = el("article", "exploration-item");
        card.append(text(el("h3"), item.title));
        card.append(text(el("p"), `${item.level} · ${item.status} · ${item.updated}`));
        card.append(text(el("code", "project-command"), item.path));
        recent.append(card);
      });
    }

    const commands = el("div", "exploration-commands");
    if (explorations.commands && explorations.commands.length) {
      explorations.commands.forEach((command) => {
        const card = el("article", "exploration-command");
        const title = el("div", "exploration-command-main");
        title.append(text(el("span", "command-tool"), command.tool));
        title.append(text(el("h3"), command.title));
        title.append(text(el("p"), command.detail));

        // Helper: replace IDEA_SLUG with the slug input value
        function resolvedCommand() {
          const slugEl = byId("idea-capture-slug");
          const slug = slugEl && slugEl.value.trim() ? slugEl.value.trim() : "IDEA_SLUG";
          return command.command.replaceAll("IDEA_SLUG", slug);
        }

        // Ensure slug is set (prompt if missing) — returns false if user cancelled
        function ensureSlug() {
          const slugEl = byId("idea-capture-slug");
          if (!slugEl || !slugEl.value.trim()) {
            const entered = window.prompt("Enter the idea slug:", "");
            if (entered && entered.trim()) {
              if (slugEl) slugEl.value = entered.trim();
            } else {
              return false;
            }
          }
          return true;
        }

        const runOutput = command.runnable ? el("pre", "run-output") : null;
        if (runOutput) {
          runOutput.dataset.state = "";
          runOutput.style.display = "none";
        }

        const actions = el("div", "exploration-command-actions");
        const detailButton = text(el("button", "copy-button"), "Details");
        detailButton.type = "button";
        detailButton.addEventListener("click", () => showHelp({
          title: command.title,
          body: `${command.detail}\n\n${resolvedCommand()}`,
        }));

        if (command.runnable && command.action_id) {
          // Local LLM runnable — show Run + Copy buttons
          const runButton = text(el("button", "copy-button primary run-button"), "Run");
          runButton.type = "button";
          const copyFallback = text(el("button", "copy-button"), "Copy command");
          copyFallback.type = "button";

          runButton.addEventListener("click", async () => {
            if (!ensureSlug()) return;
            const slug = (byId("idea-capture-slug") || {}).value.trim();

            // Promote action needs the full project modal
            if (command.action_id === "promote-exploration-to-project") {
              openPromoteModal(slug, (byId("idea-capture-keywords") || {}).value || "");
              return;
            }

            // local-exploration-synthesis: just needs project slug confirmation
            if (command.action_id === "local-exploration-synthesis") {
              const pslug = window.prompt("Project slug to open local agent on:", slug);
              if (!pslug || !pslug.trim()) return;
              if (!serverState.online) {
                if (runOutput) { runOutput.style.display = ""; runOutput.dataset.state = "error"; runOutput.textContent = "Server offline. Start: python3 scripts/dashboard_server.py --port 8765"; }
                return;
              }
              runButton.disabled = true;
              runButton.textContent = "Opening...";
              if (runOutput) { runOutput.style.display = ""; runOutput.dataset.state = "running"; runOutput.textContent = "Opening Terminal..."; }
              try {
                const resp = await fetch(apiUrl("/api/run"), {
                  method: "POST", headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ action_id: command.action_id, project_slug: pslug.trim(), params: { project_slug: pslug.trim() } }),
                });
                const result = await resp.json();
                if (runOutput) { runOutput.dataset.state = result.ok ? "ok" : "error"; runOutput.textContent = result.stdout || result.stderr || (result.ok ? "Done." : "Failed."); }
              } catch (e) {
                if (runOutput) { runOutput.dataset.state = "error"; runOutput.textContent = `Error: ${e.message}`; }
              } finally {
                runButton.disabled = false; runButton.textContent = "Run";
              }
              return;
            }
          });

          copyFallback.addEventListener("click", () => {
            ensureSlug();
            copyText(resolvedCommand(), copyFallback);
          });

          actions.append(detailButton, runButton, copyFallback);
        } else {
          // Cloud-safe copy-only
          const copyButton = text(el("button", "copy-button primary"), command.button_label || "Copy command");
          copyButton.type = "button";
          copyButton.addEventListener("click", () => {
            ensureSlug();
            copyText(resolvedCommand(), copyButton);
          });
          actions.append(detailButton, copyButton);
        }

        card.append(title, actions);
        if (runOutput) card.append(runOutput);
        commands.append(card);
      });
    }

    root.append(stats, recent, commands);
  }

  function renderObsidianViewer() {
    const root = byId("obsidian-viewer");
    if (!root || !data) return;
    root.replaceChildren();

    const repoPath = data.meta.repo_path;
    const openUri = `obsidian://open?path=${encodeURIComponent(`${repoPath}/index.md`)}`;
    const setupCommand = `open -a Obsidian "${repoPath}"`;
    const graphFilter = "path:wiki";

    const primary = el("article", "obsidian-card obsidian-primary");
    const primaryBody = el("div");
    primaryBody.append(text(el("h3"), "Open Wiki in Obsidian"));
    primaryBody.append(text(el("p"), "Use this when you want to read, search, and follow links across the saved paper wiki. The dashboard is for workflow; Obsidian is for reading."));
    const buttonRow = el("div", "obsidian-actions");
    const openLink = text(el("a", "copy-button primary obsidian-link"), "Open vault");
    openLink.href = openUri;
    const copySetup = text(el("button", "copy-button"), "Copy setup");
    copySetup.type = "button";
    copySetup.addEventListener("click", () => copyText(setupCommand, copySetup));
    const serverOpen = text(el("button", "copy-button"), "Open via server");
    serverOpen.type = "button";
    serverOpen.disabled = !serverState.online || !serverState.allowed.has("open-obsidian");
    serverOpen.addEventListener("click", async () => {
      const original = serverOpen.textContent;
      serverOpen.disabled = true;
      serverOpen.textContent = "Opening...";
      try {
        await fetch(apiUrl("/api/run"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: "open-obsidian" }),
        });
        serverOpen.textContent = "Opened";
        window.setTimeout(() => {
          serverOpen.textContent = original;
          serverOpen.disabled = !serverState.online;
        }, 1200);
      } catch (_error) {
        serverOpen.textContent = "Failed";
      }
    });
    buttonRow.append(openLink, serverOpen, copySetup);
    primary.append(primaryBody, buttonRow);

    const reading = el("article", "obsidian-card");
    reading.append(text(el("h3"), "How to read"));
    reading.append(text(el("p"), "Start broad, then drill down only when you need source-level detail."));
    const list = el("ol", "obsidian-list");
    ["index.md", "wiki/overviews/", "wiki/{category}/", "sources/ for citation-truth detail"].forEach((item) => {
      list.append(text(el("li"), item));
    });
    const guideRow = el("div", "obsidian-inline-actions");
    guideRow.append(text(el("code", "command-text"), "_system/docs/WIKI_VIEWING.md"));
    const copyGuide = text(el("button", "copy-button"), "Copy guide path");
    copyGuide.type = "button";
    copyGuide.addEventListener("click", () => copyText("_system/docs/WIKI_VIEWING.md", copyGuide));
    guideRow.append(copyGuide);
    reading.append(list, guideRow);

    const graph = el("article", "obsidian-card");
    graph.append(text(el("h3"), "Graph View"));
    graph.append(text(el("p"), "Use this optional filter when the graph gets too crowded."));
    const graphCode = text(el("code", "command-text"), graphFilter);
    const copyFilter = text(el("button", "copy-button"), "Copy graph filter");
    copyFilter.type = "button";
    copyFilter.addEventListener("click", () => copyText(graphFilter, copyFilter));
    graph.append(graphCode, copyFilter);

    root.append(primary, reading, graph);
  }

  function renderWikiSearch() {
    const input = byId("wiki-search-input");
    const count = byId("wiki-search-count");
    const results = byId("wiki-search-results");
    if (!input || !count || !results) return;
    const index = data.wiki_search || [];

    function resultScore(item, terms) {
      const title = String(item.title || "").toLowerCase();
      const path = String(item.path || "").toLowerCase();
      const haystack = String(item.search_text || "");
      let score = 0;
      terms.forEach((term) => {
        if (title.includes(term)) score += 8;
        if (path.includes(term)) score += 4;
        if (haystack.includes(term)) score += 1;
      });
      if (item.kind === "overview") score += 2;
      if (item.kind === "wiki") score += 1;
      return score;
    }

    function render(query) {
      results.replaceChildren();
      const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
      if (!terms.length) {
        count.textContent = `${index.length} searchable page(s)`;
        results.append(emptyState("Search the saved wiki. Try VOR, Purkinje, CGRP, plasticity, vestibular, or TBI."));
        return;
      }
      const matches = index
        .map((item) => ({ item, score: resultScore(item, terms) }))
        .filter((row) => row.score > 0 && terms.every((term) => String(row.item.search_text || "").includes(term)))
        .sort((a, b) => b.score - a.score || a.item.path.localeCompare(b.item.path))
        .slice(0, 8)
        .map((row) => row.item);
      count.textContent = `${matches.length} result(s)`;
      if (!matches.length) {
        results.append(emptyState("No dashboard-indexed wiki result. Try fewer words, or use Obsidian full-text search for deeper lookup."));
        return;
      }
      matches.forEach((item) => {
        const card = el("article", "wiki-result");
        const body = el("div");
        body.append(text(el("h3"), item.title));
        const meta = el("div", "wiki-result-meta");
        [item.kind, item.year, item.category].filter(Boolean).forEach((value) => {
          meta.append(text(el("span", "pill type"), value));
        });
        body.append(meta);
        body.append(text(el("p"), item.snippet || item.path));
        body.append(text(el("code", "project-command"), item.path));
        const link = text(el("a", "copy-button wiki-result-link"), "Open");
        link.href = `../../${item.path}`;
        link.target = "_blank";
        link.rel = "noopener";
        card.append(body, link);
        results.append(card);
      });
    }

    input.addEventListener("input", () => render(input.value));
    render("");
  }

  function slugifyIdea(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .replace(/-{2,}/g, "-")
      .slice(0, 60) || "idea-slug";
  }

  function ideaCapturePrompt() {
    const rough = byId("idea-capture-text") ? byId("idea-capture-text").value.trim() : "";
    const slugInput = byId("idea-capture-slug") ? byId("idea-capture-slug").value.trim() : "";
    const keywords = byId("idea-capture-keywords") ? byId("idea-capture-keywords").value.trim() : "";
    const exclude = byId("idea-capture-exclude") ? byId("idea-capture-exclude").value.trim() : "";
    const slug = slugifyIdea(slugInput || keywords || rough);
    return `Create or update explorations/idea-notes/${slug}.md using explorations/_template/Idea_Note_TEMPLATE.md.

Do not save the full conversation transcript. Save only a compact evolving idea note.

Rough idea / question:
${rough || "[write the idea here]"}

Search keywords:
${keywords || "[add 3-8 searchable terms]"}

Must-exclude terms:
${exclude || "[optional]"}

Write the note with:
- frontmatter including slug: ${slug}, status: idea-note, confidential_tier: external-ok
- a short Current Summary
- Why this might matter
- Searchable terms
- Must-include keywords
- Must-exclude keywords
- Open questions
- Candidate papers or wiki anchors to check, if any
- A dated update for today

Keep it public-facing. Do not include unpublished data, grant aims, project strategy, or confidential project text.`;
  }

  function setupIdeaCapture() {
    const rough = byId("idea-capture-text");
    const slug = byId("idea-capture-slug");
    const copyButton = byId("idea-capture-copy");
    const detailsButton = byId("idea-capture-details");
    if (!rough || !slug || !copyButton || !detailsButton) return;

    rough.addEventListener("input", () => {
      if (!slug.value.trim()) slug.value = slugifyIdea(rough.value);
    });
    detailsButton.addEventListener("click", () => showHelp({
      title: "Idea note structure",
      body: ideaCapturePrompt(),
    }));
    copyButton.addEventListener("click", () => copyText(ideaCapturePrompt(), copyButton));
  }

  // ── Promote-exploration modal ────────────────────────────────────────────────
  function openPromoteModal(explorationSlug, keywords) {
    const modal   = byId("promote-exploration-modal");
    const eSlug   = byId("promote-exploration-slug");
    const pSlug   = byId("promote-project-slug");
    const pTitle  = byId("promote-project-title");
    const pType   = byId("promote-project-type");
    const pKw     = byId("promote-keywords");
    const output  = byId("promote-modal-output");
    const confirm = byId("promote-modal-confirm");
    const cancel  = byId("promote-modal-cancel");
    const closeBtn = byId("promote-modal-close");
    if (!modal) return;

    // Pre-fill from slug input and keywords
    if (eSlug) eSlug.value = explorationSlug || "";
    if (pSlug) pSlug.value = explorationSlug || "";
    if (pKw)   pKw.value   = keywords || "";
    if (output) { output.hidden = true; output.textContent = ""; output.dataset.state = ""; }

    // Auto-sync exploration slug → project slug while user edits
    if (eSlug && pSlug) {
      eSlug.addEventListener("input", () => {
        if (!pSlug.dataset.edited) pSlug.value = eSlug.value;
      }, { once: false });
      pSlug.addEventListener("input", () => { pSlug.dataset.edited = "1"; });
    }

    modal.hidden = false;

    function closeModal() {
      modal.hidden = true;
      if (pSlug) delete pSlug.dataset.edited;
    }
    if (closeBtn) closeBtn.onclick = closeModal;
    if (cancel)   cancel.onclick   = closeModal;
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); }, { once: true });

    if (confirm) {
      confirm.onclick = async () => {
        const exploSlug  = (eSlug && eSlug.value.trim()) || "";
        const projSlug   = (pSlug && pSlug.value.trim()) || exploSlug;
        const projTitle  = (pTitle && pTitle.value.trim()) || "Working title";
        const projType   = (pType && pType.value) || "paper_in_prep";
        const kw         = (pKw && pKw.value.trim()) || "";

        if (!exploSlug) { alert("Enter the exploration slug."); return; }
        if (!serverState.online) {
          if (output) { output.hidden = false; output.dataset.state = "error"; output.textContent = "Server offline. Start: python3 scripts/dashboard_server.py --port 8765"; }
          return;
        }

        confirm.disabled = true;
        confirm.textContent = "Creating...";
        if (output) { output.hidden = false; output.dataset.state = "running"; output.textContent = "Creating folders and project..."; }

        try {
          const resp = await fetch(apiUrl("/api/run"), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action_id: "promote-exploration-to-project",
              project_slug: projSlug,
              params: {
                exploration_slug: exploSlug,
                project_slug:     projSlug,
                project_type:     projType,
                project_title:    projTitle,
                keywords:         kw,
              },
            }),
          });
          const result = await resp.json();
          if (output) {
            output.dataset.state = result.ok ? "ok" : "error";
            output.textContent = [result.stdout, result.stderr].filter(Boolean).join("\n\n") || (result.ok ? "Done." : "Failed.");
          }
          if (result.ok) {
            confirm.textContent = "Done ✓";
            window.setTimeout(() => {
              closeModal();
              window.location.reload();
            }, 1800);
          }
        } catch (e) {
          if (output) { output.dataset.state = "error"; output.textContent = `Error: ${e.message}`; }
        } finally {
          confirm.disabled = false;
          if (confirm.textContent === "Creating...") confirm.textContent = "Promote + Create Project";
        }
      };
    }
  }

  function setupIngestMenu() {
    const select = byId("ingest-exploration-select");
    const openBoard = byId("ingest-open-board");
    const importLocal = byId("ingest-import-local");
    const openInbox = byId("ingest-open-inbox");
    const copyPrompt = byId("ingest-copy-prompt");
    const output = byId("ingest-output");
    if (!select || !openBoard || !importLocal || !openInbox || !copyPrompt || !output) return;

    const targets = ((data.explorations && data.explorations.approval_targets) || [])
      .slice()
      .sort((a, b) => String(b.updated || "").localeCompare(String(a.updated || "")));
    select.textContent = "";
    if (!targets.length) {
      select.append(text(el("option"), "No active explorations with candidates yet"));
      select.disabled = true;
      openBoard.disabled = true;
    } else {
      targets.forEach((target) => {
        const bits = [
          target.latest_candidate_batch ? `batch ${target.latest_candidate_batch}` : "",
          target.triage_report_count ? `${target.triage_report_count} triage report(s)` : "no triage yet",
        ].filter(Boolean);
        const prefix = target.kind === "paper-scout" ? "scout" : "exploration";
        const option = text(el("option"), `${prefix}: ${target.slug} - ${bits.join(", ")}`);
        option.value = target.slug;
        option.dataset.kind = target.kind || "exploration";
        select.append(option);
      });
    }

    openBoard.addEventListener("click", async () => {
      const slug = select.value;
      if (!slug) return;
      const kind = select.selectedOptions[0] ? select.selectedOptions[0].dataset.kind : "exploration";
      const actionId = kind === "paper-scout" ? "open-approval-board-scout" : "open-approval-board-exploration";
      const params = kind === "paper-scout" ? { scout_slug: slug } : { exploration_slug: slug };
      if (!serverState.online || !serverState.allowed.has(actionId)) {
        output.dataset.state = "error";
        output.textContent = serverRequiredMessage();
        return;
      }
      openBoard.disabled = true;
      output.dataset.state = "running";
      output.textContent = `Opening triage/download board for ${slug}...`;
      try {
        await runDashboardAction(actionId, params, output);
      } catch (error) {
        output.dataset.state = "error";
        output.textContent = error.message === "Failed to fetch" ? serverRequiredMessage() : `Run failed: ${error.message}`;
      } finally {
        openBoard.disabled = !targets.length;
      }
    });

    importLocal.addEventListener("click", async () => {
      if (!serverState.online || !serverState.allowed.has("import-local-pdfs")) {
        output.dataset.state = "error";
        output.textContent = serverRequiredMessage();
        return;
      }
      const rawMode = window.prompt("Type copy or move for selected PDFs.", "copy");
      if (rawMode === null) return;
      const mode = rawMode.trim().toLowerCase();
      if (!["copy", "move"].includes(mode)) {
        output.dataset.state = "error";
        output.textContent = "Import cancelled. Mode must be copy or move.";
        return;
      }
      importLocal.disabled = true;
      output.dataset.state = "running";
      output.textContent = `Opening file picker for local PDF ${mode}...`;
      try {
        await runDashboardAction("import-local-pdfs", { mode }, output);
      } catch (error) {
        output.dataset.state = "error";
        output.textContent = error.message === "Failed to fetch" ? serverRequiredMessage() : `Run failed: ${error.message}`;
      } finally {
        importLocal.disabled = false;
      }
    });

    openInbox.addEventListener("click", async () => {
      if (!serverState.online || !serverState.allowed.has("open-inbox")) {
        output.dataset.state = "error";
        output.textContent = serverRequiredMessage();
        return;
      }
      openInbox.disabled = true;
      output.dataset.state = "running";
      output.textContent = "Opening papers/inbox...";
      try {
        await runDashboardAction("open-inbox", {}, output);
      } catch (error) {
        output.dataset.state = "error";
        output.textContent = error.message === "Failed to fetch" ? serverRequiredMessage() : `Run failed: ${error.message}`;
      } finally {
        openInbox.disabled = false;
      }
    });

    copyPrompt.addEventListener("click", () => copyText(ingestPrompt(), copyPrompt));

    // ── Triage Criteria panel ──────────────────────────────────────────────
    const triageBtn = byId("ingest-triage-criteria");
    const triagePanel = byId("triage-criteria-panel");
    const triagePanelClose = byId("triage-panel-close");
    const triageCriteriaText = byId("triage-criteria-text");
    const triageSaveCopy = byId("triage-save-copy");
    const triageCopyOnly = byId("triage-copy-only");
    const triageSavedBadge = byId("triage-saved-badge");

    function buildTriageCriteriaExample(topic, keywords, yearRange) {
      const topicLine  = topic    ? `Papers on ${topic}` : "Papers directly relevant to your research question";
      const kwLine     = keywords ? keywords.split(/[,;\n]+/).map(k => k.trim()).filter(Boolean).map(k => `- ${k}`).join("\n")
                                  : "- (add your key terms here)";
      const yearLine   = yearRange ? `- Prefer ${yearRange} unless a classic paper establishes a key concept`
                                   : "- Prefer the last 10 years unless a classic paper establishes a key concept";
      return `# Triage Criteria

## Include — in-scope (high confidence)
- ${topicLine} with primary experimental data
- Mechanistic studies directly testing the keywords above
- Papers using relevant model systems, tools, or assays for this topic

## Borderline — review carefully
- Papers where the topic is secondary to a broader claim (check for relevant data sections)
- Review articles or meta-analyses that cite primary data useful to this wiki
- Computational or theoretical papers grounded in relevant experimental observations

## Exclude — out-of-scope
- Pure clinical case reports without mechanistic data
- Papers where the topic appears only incidentally (e.g., one sentence in introduction)
- Methods papers unrelated to this scout's core question

## Keywords to prioritize
${kwLine}

## Year range preference
${yearLine}`.trim();
    }

    function getTargetMeta(slug) {
      return ((data.explorations && data.explorations.approval_targets) || [])
        .find(t => t.slug === slug) || {};
    }

    function buildTriagePrompt() {
      const sel = select;
      const slug = sel.value;
      if (!slug) return "";
      const kind = sel.selectedOptions[0] ? sel.selectedOptions[0].dataset.kind : "exploration";
      const prefix = kind === "paper-scout" ? `scouts/${slug}` : `explorations/active/${slug}`;
      return (
        `Read ${prefix}/Triage_Criteria.md for inclusion/exclusion scope.\n` +
        `Triage all candidates in ${prefix}/candidates/ (latest batch) against those criteria.\n` +
        `Assign each paper to in-scope, borderline, or out-of-scope with a one-line reason.\n` +
        `Write the triage report to ${prefix}/triage-reports/ as both .md and .json.\n` +
        `Follow the format in subagents/02-triage.md exactly.`
      );
    }

    if (triageBtn && triagePanel) {
      triageBtn.addEventListener("click", () => {
        const isHidden = triagePanel.hidden;
        triagePanel.hidden = !isHidden;
        if (isHidden && !triageCriteriaText.value.trim()) {
          const meta = getTargetMeta(select.value);
          triageCriteriaText.value = buildTriageCriteriaExample(
            meta.topic || "",
            meta.keywords || "",
            meta.year_range || ""
          );
        }
        if (!triagePanel.hidden) triageCriteriaText.focus();
      });
    }

    // Re-generate example when dropdown selection changes (only if textarea is still the auto-generated default)
    select.addEventListener("change", () => {
      if (triageCriteriaText && triagePanel && !triagePanel.hidden) {
        const meta = getTargetMeta(select.value);
        triageCriteriaText.value = buildTriageCriteriaExample(
          meta.topic || "",
          meta.keywords || "",
          meta.year_range || ""
        );
      }
    });

    if (triagePanelClose) {
      triagePanelClose.addEventListener("click", () => { triagePanel.hidden = true; });
    }

    if (triageSaveCopy) {
      triageSaveCopy.addEventListener("click", async () => {
        const criteria = triageCriteriaText ? triageCriteriaText.value.trim() : "";
        const slug = select.value;
        if (!slug) { alert("Select a scout or exploration first."); return; }
        if (!criteria) { alert("Write some triage criteria first."); return; }
        const kind = select.selectedOptions[0] ? select.selectedOptions[0].dataset.kind : "exploration";
        const targetType = kind === "paper-scout" ? "scout" : "exploration";

        // Save criteria file (server mode)
        if (serverState.online && serverState.allowed.has("save-triage-criteria")) {
          triageSaveCopy.disabled = true;
          triageSaveCopy.textContent = "Saving...";
          try {
            const resp = await fetch(apiUrl("/api/run"), {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action_id: "save-triage-criteria", params: { criteria, target_type: targetType, target_slug: slug } }),
            });
            const result = await resp.json();
            if (result.ok) {
              if (triageSavedBadge) { triageSavedBadge.hidden = false; setTimeout(() => { triageSavedBadge.hidden = true; }, 2500); }
            } else {
              alert(`Save failed: ${result.stderr || result.error || "Unknown error"}`);
            }
          } catch (e) { alert(`Error: ${e.message}`); }
          finally { triageSaveCopy.disabled = false; triageSaveCopy.textContent = "Save & Copy triage prompt"; }
        }

        // Copy triage prompt
        const prompt = buildTriagePrompt();
        if (prompt) {
          navigator.clipboard.writeText(prompt);
          output.dataset.state = "ok";
          output.textContent = `Triage criteria saved. Prompt copied!\n\nPaste into Codex CLI to run triage:\n\n${prompt}`;
        }
      });
    }

    if (triageCopyOnly) {
      triageCopyOnly.addEventListener("click", () => {
        const slug = select.value;
        if (!slug) { alert("Select a scout or exploration first."); return; }
        const prompt = buildTriagePrompt();
        if (prompt) {
          navigator.clipboard.writeText(prompt);
          triageCopyOnly.textContent = "Copied!";
          setTimeout(() => { triageCopyOnly.textContent = "Copy prompt only"; }, 1500);
        }
      });
    }
  }

  function setupScopusImport() {
    const modal       = byId("scopus-modal");
    const closeBtn    = byId("scopus-modal-close");
    const cancelBtn   = byId("scopus-modal-cancel");
    const confirmBtn  = byId("scopus-modal-confirm");
    const openBtn     = byId("scopus-import-open");
    const helpBtn     = byId("scopus-import-help");
    const fileInput   = byId("scopus-file-input");
    const fileNameEl  = byId("scopus-file-name");
    const outputEl    = byId("scopus-modal-output");
    const modeExisting = byId("scopus-mode-existing");
    const modeNew      = byId("scopus-mode-new");
    const existingSection = byId("scopus-existing-section");
    const newSection      = byId("scopus-new-section");
    const existingSelect  = byId("scopus-existing-select");

    if (!modal || !openBtn) return;

    let csvContent = null;

    function closeModal() {
      modal.hidden = true;
      csvContent = null;
      if (fileInput) fileInput.value = "";
      if (fileNameEl) fileNameEl.textContent = "No file chosen";
      if (outputEl) { outputEl.hidden = true; outputEl.dataset.state = "idle"; }
    }

    function updateSections() {
      const mode = document.querySelector('input[name="scopus-target-mode"]:checked');
      if (!mode) return;
      existingSection.style.display = mode.value === "existing" ? "" : "none";
      newSection.style.display      = mode.value === "new"      ? "" : "none";
    }

    // Populate existing scouts dropdown
    function populateExistingSelect() {
      if (!existingSelect) return;
      existingSelect.textContent = "";
      const targets = ((data.explorations && data.explorations.approval_targets) || [])
        .filter(t => t.kind === "paper-scout");
      if (!targets.length) {
        const opt = document.createElement("option");
        opt.textContent = "No existing scouts yet";
        opt.disabled = true;
        existingSelect.append(opt);
      } else {
        targets.forEach(t => {
          const opt = document.createElement("option");
          opt.value = t.slug;
          opt.textContent = t.slug;
          existingSelect.append(opt);
        });
      }
    }

    openBtn.addEventListener("click", () => {
      populateExistingSelect();
      updateSections();
      modal.hidden = false;
    });

    if (helpBtn) {
      helpBtn.addEventListener("click", () => showHelp(helpCopy["scopus-csv"]));
    }

    [modeExisting, modeNew].forEach(r => r && r.addEventListener("change", updateSections));

    if (fileInput) {
      fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];
        if (!file) return;
        fileNameEl.textContent = file.name;
        const reader = new FileReader();
        reader.onload = e => { csvContent = e.target.result; };
        reader.readAsText(file, "utf-8");
      });
    }

    confirmBtn.addEventListener("click", async () => {
      if (!csvContent) { alert("Choose a Scopus CSV file first."); return; }

      const mode = document.querySelector('input[name="scopus-target-mode"]:checked');
      const isExisting = mode && mode.value === "existing";

      const targetSlug  = isExisting ? (existingSelect && existingSelect.value) : "";
      const topic       = isExisting ? "" : (byId("scopus-topic").value.trim());
      const keywords    = isExisting ? "" : (byId("scopus-keywords").value.trim());
      const yearStart   = isExisting ? "" : (byId("scopus-year-start").value.trim());
      const yearEnd     = isExisting ? "" : (byId("scopus-year-end").value.trim());

      if (!isExisting && !topic) { alert("Enter a topic for the new scout."); return; }
      if (isExisting && !targetSlug) { alert("Select an existing scout."); return; }

      if (!serverState.online || !serverState.allowed || !serverState.allowed.has("import-scopus-csv")) {
        if (outputEl) {
          outputEl.hidden = false;
          outputEl.dataset.state = "error";
          outputEl.textContent = "Dashboard server must be running to import CSV. Start it and try again.";
        }
        return;
      }

      confirmBtn.disabled = true;
      if (outputEl) { outputEl.hidden = false; outputEl.dataset.state = "running"; outputEl.textContent = "Importing…"; }

      try {
        const resp = await fetch(apiUrl("/api/run"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: "import-scopus-csv", params: {
            csv_content: csvContent,
            target_slug: targetSlug,
            topic, keywords,
            year_start: yearStart,
            year_end: yearEnd,
          }}),
        });
        const result = await resp.json();
        if (outputEl) {
          outputEl.dataset.state = result.ok ? "success" : "error";
          outputEl.textContent = result.ok
            ? (result.stdout || "Import complete.") + "\n\nRebuild the dashboard to see the new scout in the dropdown."
            : result.error || result.stderr || "Import failed.";
        }
        if (result.ok) {
          confirmBtn.textContent = "Done ✓";
          setTimeout(() => { confirmBtn.textContent = "Import"; confirmBtn.disabled = false; }, 2500);
        } else {
          confirmBtn.disabled = false;
        }
      } catch (e) {
        if (outputEl) { outputEl.dataset.state = "error"; outputEl.textContent = `Error: ${e.message}`; }
        confirmBtn.disabled = false;
      }
    });

    closeBtn.addEventListener("click", closeModal);
    cancelBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", e => { if (e.target === modal) closeModal(); });
    document.addEventListener("keydown", e => {
      if (e.key === "Escape" && modal && !modal.hidden) closeModal();
    });
  }

  function setupSynthesizeModal() {
    const modal       = byId("synthesize-modal");
    const closeBtn    = byId("synthesize-modal-close");
    const cancelBtn   = byId("synthesize-modal-cancel");
    const confirmBtn  = byId("synthesize-modal-confirm");
    const copyOnlyBtn = byId("synthesize-modal-copy-only");
    const keywordsEl  = byId("synth-keywords");
    const slugEl      = byId("synth-slug");
    const outputEl    = byId("synth-output");
    const outputMsg   = byId("synthesize-modal-output");
    const openBtn     = byId("ingest-synthesize");
    const explorationSelect = byId("ingest-exploration-select");

    if (!modal || !openBtn) return;

    function closeModal() {
      modal.hidden = true;
      if (outputMsg) { outputMsg.hidden = true; outputMsg.dataset.state = "idle"; }
    }

    function resolvedOutputPath() {
      const slug = (slugEl.value || "synthesis").trim().replace(/\s+/g, "-");
      const type = outputEl ? outputEl.value : "overview";
      return type === "exploration"
        ? `explorations/active/${slug}/synthesis.md`
        : `wiki/overviews/${slug}.md`;
    }

    function buildPrompt() {
      return synthesizePrompt({
        slug: (slugEl.value || "synthesis").trim().replace(/\s+/g, "-"),
        keywords: (keywordsEl.value || "").trim(),
        outputPath: resolvedOutputPath(),
        outputType: outputEl ? outputEl.value : "overview",
      });
    }

    function populateFromSelection() {
      const slug = explorationSelect && explorationSelect.value ? explorationSelect.value : "";
      const target = ((data.explorations && data.explorations.approval_targets) || [])
        .find(t => t.slug === slug);
      const kw = (target && target.keywords) ? target.keywords : "";
      slugEl.value = slug;
      keywordsEl.value = kw || (slug ? `Scout / exploration: ${slug}\n(Add specific keywords here)` : "");
    }

    openBtn.addEventListener("click", () => {
      const mode = document.querySelector('input[name="synth-mode"]:checked');
      if (!mode || mode.value === "recent") {
        document.getElementById("synth-mode-recent").checked = true;
        populateFromSelection();
      }
      if (outputMsg) outputMsg.hidden = true;
      modal.hidden = false;
      keywordsEl.focus();
    });

    document.querySelectorAll('input[name="synth-mode"]').forEach(radio => {
      radio.addEventListener("change", () => {
        if (radio.value === "custom") {
          keywordsEl.value = "";
          slugEl.value = "";
          keywordsEl.placeholder = "Describe the synthesis topic or paste key concepts…";
        } else {
          keywordsEl.placeholder = "Enter keywords or a topic description…";
          populateFromSelection();
        }
      });
    });

    copyOnlyBtn.addEventListener("click", () => {
      copyText(buildPrompt(), copyOnlyBtn);
    });

    confirmBtn.addEventListener("click", async () => {
      const keywords = keywordsEl.value.trim();
      const slug = (slugEl.value || "synthesis").trim().replace(/\s+/g, "-");
      if (!keywords) { alert("Enter keywords or a topic first."); return; }

      const outputPath = resolvedOutputPath();
      const outputType = outputEl ? outputEl.value : "overview";
      const prompt = buildPrompt();

      if (serverState.online && serverState.allowed && serverState.allowed.has("save-synthesis-brief")) {
        confirmBtn.disabled = true;
        if (outputMsg) { outputMsg.hidden = false; outputMsg.dataset.state = "running"; outputMsg.textContent = "Saving brief…"; }
        try {
          const resp = await fetch(apiUrl("/api/run"), {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "save-synthesis-brief",
              params: { slug, keywords, output_path: outputPath, output_type: outputType } }),
          });
          const result = await resp.json();
          if (result.ok) {
            if (outputMsg) { outputMsg.dataset.state = "success"; outputMsg.textContent = `Brief saved → ${outputPath}`; }
          } else {
            if (outputMsg) { outputMsg.dataset.state = "error"; outputMsg.textContent = result.error || result.stderr || "Save failed."; }
          }
        } catch (e) {
          if (outputMsg) { outputMsg.dataset.state = "error"; outputMsg.textContent = `Error: ${e.message}`; }
        } finally {
          confirmBtn.disabled = false;
        }
      } else {
        if (outputMsg) { outputMsg.hidden = false; outputMsg.dataset.state = "idle"; outputMsg.textContent = "Server offline — prompt copied only."; }
      }

      copyText(prompt, confirmBtn);
    });

    closeBtn.addEventListener("click", closeModal);
    cancelBtn.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => { if (e.target === modal) closeModal(); });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal && !modal.hidden) closeModal();
    });
  }

  function setupScoutHistory() {
    const input = byId("scout-history-search");
    const results = byId("scout-history-results");
    if (!input || !results) return;
    const history = data.scout_history || [];

    function matchScore(item, terms) {
      const title = String(item.title || "").toLowerCase();
      const years = String(item.year_range || "").toLowerCase();
      const haystack = String(item.search_text || "");
      let score = 0;
      terms.forEach((term) => {
        if (title.includes(term)) score += 8;
        if (years.includes(term)) score += 6;
        if (haystack.includes(term)) score += 2;
      });
      return score;
    }

    function render(query) {
      results.replaceChildren();
      const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
      if (!history.length) {
        results.append(emptyState("No previous paper scouts yet."));
        return;
      }
      if (!terms.length) {
        results.append(text(el("p", "scout-history-hint"), `${history.length} previous scout(s). Type a topic, keyword, or year to check overlap.`));
        return;
      }
      const matches = terms.length
        ? history
            .map((item) => ({ item, score: matchScore(item, terms) }))
            .filter((row) => row.score > 0 && terms.every((term) => String(row.item.search_text || "").includes(term)))
            .sort((a, b) => b.score - a.score || String(b.item.updated || "").localeCompare(String(a.item.updated || "")))
            .slice(0, 6)
            .map((row) => row.item)
        : history.slice(0, 4);
      if (!matches.length) {
        results.append(emptyState("No matching scout history. This looks like a new paper scout."));
        return;
      }
      matches.forEach((item) => {
        const card = el("article", "scout-history-item");
        const body = el("div", "scout-history-main");
        body.append(text(el("h3"), item.title || item.slug));
        const meta = [
          item.year_range || "years not specified",
          item.candidate_batch_count ? `${item.candidate_batch_count} batch` : "no batch",
          item.latest_candidate_batch ? `latest: ${item.latest_candidate_batch}` : "",
        ].filter(Boolean).join(" · ");
        body.append(text(el("p"), meta));
        card.append(body);
        card.title = item.brief_path || item.path;
        results.append(card);
      });
    }

    input.addEventListener("input", () => render(input.value));
    render("");
  }

  if (!data) {
    byId("summary-cards").append(emptyState("Dashboard data is missing. Run python3 scripts/build_dashboard.py first."));
    return;
  }

  text(byId("generated-at"), data.meta.generated_at);
  text(byId("repo-path"), data.meta.repo_path);
  renderFocusPanel();
  renderWikiSearch();
  setupIdeaCapture();
  setupIngestMenu();
  setupScopusImport();
  setupSynthesizeModal();
  setupScoutHistory();
  setupServerToggle();
  checkServer().then(() => {
    renderWorkspaceTools(data.projects);
    renderObsidianViewer();
  });
  const explorationHelp = byId("exploration-help");
  if (explorationHelp) {
    explorationHelp.addEventListener("click", () => showHelp(helpCopy.explorationSection));
  }
  const obsidianHelp = byId("obsidian-help");
  if (obsidianHelp) {
    obsidianHelp.addEventListener("click", () => showHelp(helpCopy.obsidianSection));
  }

  const summaryCards = [
    ["Source Pages", data.totals.source_pages, "Structured paper summaries"],
    ["Overviews", data.totals.overview_pages, "Reusable synthesis pages"],
    ["Inbox PDFs", data.totals.inbox_pdfs, "Approved files waiting for ingest"],
    ["Idea Notes", data.totals.idea_notes || 0, "Lightweight brainstorming summaries"],
    ["Projects", data.totals.project_folders, `${data.totals.tracked_projects} tracked, ${data.totals.untracked_projects} untracked`],
    ["Local Draft Checks", data.totals.drafts_ready_for_verification, `${data.totals.drafts_missing_claim_logs} missing claim logs`],
  ];
  const summaryRoot = byId("summary-cards");
  summaryCards.forEach(([label, value, note]) => {
    const card = el("article", "stat-card");
    card.append(text(el("span", "stat-label"), label));
    card.append(text(el("strong", "stat-value"), String(value)));
    card.append(text(el("span", "stat-note"), note));
    summaryRoot.append(card);
  });

  const todayRoot = byId("today-list");
  if (!data.today.length) {
    todayRoot.append(emptyState("No priority items detected. Rebuild after the next ingest, triage, or draft."));
  } else {
    data.today.forEach((item) => {
      const row = el("article", "today-item");
      row.append(text(el("span", `priority priority-${item.priority.toLowerCase()}`), item.priority));
      const body = el("div", "today-body");
      body.append(text(el("h3"), item.title));
      body.append(text(el("p"), item.context));
      body.append(text(el("code", "today-command"), item.command));
      row.append(body);
      todayRoot.append(row);
    });
  }

  const actionRoot = byId("actions");
  if (!data.actions.length) {
    actionRoot.append(emptyState("No urgent actions detected. Keep building the corpus and drafts."));
  } else {
    data.actions.forEach((action) => {
      const card = el("article", "action-card");
      card.dataset.severity = action.severity;
      card.append(text(el("h3"), action.title));
      card.append(text(el("p"), action.detail));
      card.append(text(el("code", "action-command"), action.command));
      actionRoot.append(card);
    });
  }

  renderWorkspaceTools(data.projects);
  renderExplorations(data.explorations);
  renderObsidianViewer();

  const mendeleyRoot = byId("mendeley-bridge");
  if (!data.mendeley || !data.mendeley.commands || !data.mendeley.commands.length) {
    mendeleyRoot.append(emptyState("No Mendeley bridge commands found. Rebuild after creating _system/mendeley/export/library.bib."));
  } else {
    const details = el("details", "mendeley-details");
    const summary = el("summary", "mendeley-summary");
    const summaryText = el("div");
    summaryText.append(text(el("strong"), "Mendeley bridge commands"));
    summaryText.append(text(el("span"), `${data.mendeley.entry_count} exported reference(s), ${data.mendeley.pdf_count} internal PDF(s), ${data.mendeley.duplicate_count} duplicate candidate(s).`));
    summary.append(summaryText);
    summary.append(text(el("span", "mendeley-toggle"), "Show commands"));
    details.append(summary);

    const note = text(el("p", "mendeley-note compact"), "Optional. Use only when auditing Mendeley exports or copying selected canonical PDFs into the watched folder.");
    details.append(note);

    const commandGrid = el("div", "mendeley-grid compact-grid");
    data.mendeley.commands.forEach((command) => {
      const card = el("article", "mendeley-card");
      const head = el("div", "command-head");
      const title = el("div");
      title.append(text(el("span", "command-tool"), command.tool));
      title.append(text(el("h3"), command.title));
      head.append(title);
      const copyButton = text(el("button", "copy-button primary"), command.button_label || "Copy command");
      copyButton.type = "button";
      copyButton.addEventListener("click", () => copyText(command.command, copyButton));
      head.append(copyButton);
      card.append(head);
      card.append(text(el("p"), command.detail));
      card.append(text(el("code", "command-text"), command.command));
      commandGrid.append(card);
    });
    details.append(commandGrid);
    mendeleyRoot.append(details);
  }

  // Warnings — populate hidden list + modal list, then wire popup button
  const warningRoot = byId("warnings");
  const warningModalList = byId("warnings-modal-list");
  data.warnings.forEach((warning) => {
    if (warningRoot) warningRoot.append(text(el("li"), warning));
    if (warningModalList) warningModalList.append(text(el("li"), warning));
  });
  const warningsBtn = byId("warnings-btn");
  const warningsModal = byId("warnings-modal");
  const warningsModalClose = byId("warnings-modal-close");
  if (warningsBtn && warningsModal) {
    const warningCount = data.warnings ? data.warnings.length : 0;
    warningsBtn.textContent = warningCount > 0 ? `⚠️ Notes (${warningCount})` : "⚠️ Notes";
    warningsBtn.addEventListener("click", () => { warningsModal.hidden = false; });
    if (warningsModalClose) {
      warningsModalClose.addEventListener("click", () => { warningsModal.hidden = true; });
    }
    warningsModal.addEventListener("click", (e) => { if (e.target === warningsModal) warningsModal.hidden = true; });
    if (!warningCount && warningModalList) {
      warningModalList.append(text(el("li", "empty-state"), "No warnings — system looks healthy."));
    }
  }

  const draftRoot = byId("draft-checks");
  if (!data.projects.length) {
    draftRoot.append(emptyState("No projects to check yet."));
  } else {
    data.projects.forEach((project) => {
      const row = el("article", "draft-status");
      row.dataset.state = project.draft_verification.state;
      row.append(text(el("strong"), project.slug));
      row.append(text(el("span"), project.draft_verification.label));
      draftRoot.append(row);
    });
  }

  const projectRoot = byId("project-cards");
  if (!data.projects.length) {
    projectRoot.append(emptyState("No project folders found yet."));
  } else {
    data.projects.forEach((project) => {
      const card = el("article", "project-card");
      const topline = el("div", "project-topline");
      const left = el("div");
      left.append(text(el("h3"), project.title));
      left.append(text(el("p"), project.slug));
      topline.append(left);
      topline.append(text(el("span", `pill status-${project.status.toLowerCase()}`), project.status));
      card.append(topline);

      const meta = el("div", "project-meta");
      meta.append(text(el("span", "pill type"), project.project_type));
      meta.append(text(el("span", "pill type"), project.deadline || "No deadline"));
      meta.append(text(el("span", "pill type"), project.tracked ? "Tracked" : "Untracked"));
      card.append(meta);

      const progress = el("div", "progress-block");
      const progressTop = el("div", "progress-topline");
      progressTop.append(text(el("span"), `Progress: ${project.progress.percent}%`));
      progressTop.append(text(el("span"), `Next: ${project.progress.next_stage}`));
      progress.append(progressTop);
      const progressTrack = el("div", "progress-track");
      const progressFill = el("div", "progress-fill");
      progressFill.style.width = `${project.progress.percent}%`;
      progressTrack.append(progressFill);
      progress.append(progressTrack);
      const stageRow = el("div", "stage-row");
      project.progress.stages.forEach((stage) => {
        stageRow.append(text(el("span", stage.complete ? "stage complete" : "stage"), stage.name));
      });
      progress.append(stageRow);
      card.append(progress);

      const prep = project.paper_in_prep || {};
      const isPaperPrep = String(project.project_type || "").toLowerCase() === "paper_in_prep";
      const hasPrepLayer = prep.figure_plan_exists || prep.experiment_roadmap_exists || prep.data_updates_dir_exists || prep.critiques_dir_exists;
      const figureProgress = prep.figure_progress || { percent: 0 };
      if (isPaperPrep || hasPrepLayer) {
        const prepBlock = el("div", "prep-block");
        const prepTitle = text(el("strong"), "Paper-in-prep optional layer");
        const prepNote = text(
          el("span"),
          prep.figure_plan_exists
            ? `Figure progress: ${figureProgress.percent}%`
            : "No figure plan yet; Project_Brief.md remains enough to proceed"
        );
        prepBlock.append(prepTitle, prepNote);
        const miniTrack = el("div", "mini-progress-track");
        const miniFill = el("div", "mini-progress-fill");
        miniFill.style.width = `${figureProgress.percent}%`;
        miniTrack.append(miniFill);
        prepBlock.append(miniTrack);
        card.append(prepBlock);
      }

      const counts = el("div", "counts-grid");
      [
        ["candidate jsons", project.counts.candidate_jsons, "candidate_jsons"],
        ["triage reports", project.counts.triage_reports, "triage_reports"],
        ["approval boards", project.counts.approval_boards || 0, "approval_boards"],
        ["draft files", project.counts.staged_drafts + project.counts.final_drafts, "draft_files"],
        ["claim logs", project.counts.claim_logs, "claim_logs"],
        ["candidate batches", project.counts.candidate_batches, "candidate_batches"],
        ["notes", project.counts.notes, "notes"],
        ["figure rows", project.counts.planned_figures || 0, "figure_rows"],
        ["data updates", project.counts.data_updates || 0, "data_updates"],
        ["critique/logs", project.counts.critique_reports || 0, "critique_reports"],
      ].forEach(([label, value, bucketKey]) => {
        const chip = el("button", "count-chip count-chip--button");
        chip.type = "button";
        chip.dataset.bucket = bucketKey;
        chip.append(text(el("strong"), String(value)));
        chip.append(text(el("span"), label));
        chip.addEventListener("click", () => openBucketFiles(project, bucketKey, label));
        counts.append(chip);
      });
      card.append(counts);

      card.append(text(el("p"), `Last touched: ${project.last_touched}`));
      card.append(text(el("p"), `Next step: ${project.next_step}`));
      if (project.latest_approval_board) {
        const approvalLink = text(el("a", "project-link"), "Open latest triage approval board");
        approvalLink.href = `../../${project.latest_approval_board}`;
        approvalLink.target = "_blank";
        approvalLink.rel = "noopener";
        card.append(approvalLink);
      }
      card.append(text(el("code", "project-command"), project.recommended_command));
      projectRoot.append(card);
    });
  }

  const categoryRoot = byId("category-grid");
  if (categoryRoot) {
    const maxPages = Math.max(...data.categories.map((category) => category.page_count), 1);
    data.categories.forEach((category) => {
      const card = el("article", "category-card");
      card.dataset.legacy = String(category.legacy);
      card.append(text(el("h3", "category-name"), category.name));
      const bar = el("div", "category-bar");
      const fill = el("div", "category-fill");
      fill.style.width = `${(category.page_count / maxPages) * 100}%`;
      bar.append(fill);
      card.append(bar);
      const count = el("div", "category-count");
      count.append(text(el("span"), `${category.page_count} page(s)`));
      count.append(text(el("span"), category.legacy ? "legacy" : "current"));
      card.append(count);
      categoryRoot.append(card);
    });
  }

  // recent-files section removed — replaced by workflow chart + local LLM workflow

  // Existing Exploration Scout — runs scripts/scout_all.py --exploration against an existing idea-note.
  const existingExplorationForm = byId("existing-exploration-form");
  if (existingExplorationForm) {
    const select = byId("existing-exploration-select");
    const runButton = byId("existing-exploration-run");
    const output = byId("quick-scout-output");
    const ideaNotes = ((data.explorations && data.explorations.recent) || [])
      .filter((item) => item.level === "idea-note")
      .sort((a, b) => a.slug.localeCompare(b.slug));
    select.textContent = "";
    if (!ideaNotes.length) {
      select.append(text(el("option"), "No idea notes found"));
      select.disabled = true;
      runButton.disabled = true;
    } else {
      ideaNotes.forEach((item) => {
        const option = text(el("option"), `${item.slug} - ${item.title}`);
        option.value = item.slug;
        select.append(option);
      });
    }
    existingExplorationForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const slug = select.value;
      if (!slug) return;
      if (!serverState.online || !serverState.allowed.has("scout-exploration")) {
        output.dataset.state = "error";
        output.textContent = serverRequiredMessage();
        return;
      }
      const originalLabel = runButton.textContent;
      runButton.disabled = true;
      runButton.textContent = "Running...";
      output.dataset.state = "running";
      output.textContent = `Running scout against existing exploration: ${slug}`;
      try {
        const response = await fetch(apiUrl("/api/run"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action_id: "scout-exploration",
            params: { exploration_slug: slug },
          }),
        });
        const result = await response.json();
        output.dataset.state = result.ok ? "ok" : "error";
        const chunks = [
          result.ok ? "Done." : "Failed.",
          result.command ? `Command: ${result.command}` : "",
          result.stdout ? `Output:\n${result.stdout}` : "",
          result.stderr ? `Errors:\n${result.stderr}` : "",
          result.log ? `Log: ${result.log}` : "",
        ].filter(Boolean);
        output.textContent = chunks.join("\n\n");
        if (result.ok) offerTriagePrompt(slug, output);
      } catch (error) {
        output.dataset.state = "error";
        output.textContent = error.message === "Failed to fetch" ? serverRequiredMessage() : `Run failed: ${error.message}`;
      } finally {
        runButton.disabled = false;
        runButton.textContent = originalLabel;
      }
    });
  }

  // ── Active workspaces bar ────────────────────────────────────────────────
  (function renderActiveWorkspacesBar() {
    const el = byId("awb-chips");
    if (!el) return;
    const projects = (data.projects || []).filter(p => p.status !== "closed");
    if (!projects.length) {
      el.innerHTML = '<span class="awb-empty">No active projects</span>';
      return;
    }
    const typeMap = { paper_in_prep: "paper", grant: "grant", review_article: "review", library_ingest: "ingest" };
    el.replaceChildren();
    projects.forEach(p => {
      const chip = document.createElement("a");
      chip.href = "#commands";
      chip.className = "awb-chip";
      const typeLabel = typeMap[p.project_type] || p.project_type || "?";
      const isConf = p.confidential && p.project_type !== "library_ingest";
      chip.innerHTML = `<span>${p.slug}</span>`
        + `<span class="awb-badge ${isConf ? "awb-badge--conf" : "awb-badge--open"}">${typeLabel}</span>`
        + (p.is_published ? '<span class="awb-badge awb-badge--pub">pub</span>' : "");
      el.append(chip);
    });
  })();

  // ── Wiki coverage button ──────────────────────────────────────────────────
  const wcBtn = byId("wiki-coverage-btn");
  if (wcBtn) {
    wcBtn.addEventListener("click", () => {
      // Works both from file:// and http://localhost
      const base = location.href.replace(/[^/]*$/, "");
      const url = location.protocol === "file:"
        ? base + "wiki-coverage.html"
        : "/_system/dashboard/wiki-coverage.html";
      window.open(url, "_blank");
    });
  }

  // ── Homework section ─────────────────────────────────────────────────────
  renderHomework(data.homework);

  // ── Duplicate check button (in PDF/Ingest section) ───────────────────────
  const dupBtn = byId("ingest-check-duplicates");
  const dupOut = byId("duplicate-check-output");
  if (dupBtn && dupOut) {
    dupBtn.addEventListener("click", async () => {
      // Find the currently selected exploration/scout candidates dir
      const sel = byId("ingest-exploration-select");
      const slug = sel ? sel.value : "";
      if (!slug) { dupOut.style.display = "block"; dupOut.dataset.state = "error"; dupOut.textContent = "Select a scout/exploration first."; return; }
      if (!serverState.online) { dupOut.style.display = "block"; dupOut.dataset.state = "error"; dupOut.textContent = serverRequiredMessage(); return; }
      // Find latest candidates dir for this slug
      dupOut.style.display = "block";
      dupOut.dataset.state = "running";
      dupOut.textContent = "Checking for duplicates...";
      const candidatesDir = `scouts/${slug}/candidates`;
      try {
        const response = await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: "check-duplicates", params: { candidates_dir: candidatesDir } }) });
        const result = await response.json();
        dupOut.dataset.state = result.ok ? "ok" : "error";
        dupOut.textContent = [result.stdout, result.stderr].filter(Boolean).join("\n\n") || (result.ok ? "No duplicates found." : "Check failed.");
      } catch (e) { dupOut.dataset.state = "error"; dupOut.textContent = `Error: ${e.message}`; }
    });
  }

  // ── Local LLM workflow panel ──────────────────────────────────────────────
  // renderLocalLLMWorkflow removed — panel deleted in v2.1 (merged into Projects — Local LLM)

  // ── Backup panel ──────────────────────────────────────────────────────────
  renderBackup(data.backup);

  // ── renderHomework ────────────────────────────────────────────────────────
  function renderHomework(hw) {
    const body = byId("homework-body");
    const periodSel = byId("homework-period-select");
    if (!body) return;

    // Sync period selector
    if (periodSel && hw && hw.frequency_days) {
      periodSel.value = String(hw.frequency_days);
      periodSel.addEventListener("change", async () => {
        if (!serverState.online) { alert("Dashboard server required to change period."); return; }
        const days = parseInt(periodSel.value, 10);
        try {
          await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "homework-set-period", params: { days } }) });
          location.reload();
        } catch (e) { alert(`Failed: ${e.message}`); }
      });
    }

    body.textContent = "";

    if (!hw || !hw.current) {
      const empty = el("div", "hw-empty");
      empty.append(text(el("p"), `No paper assigned yet. You have ${hw ? hw.total_wiki_papers : 0} papers in the wiki.`));
      if (serverState.online) {
        const assignBtn = el("button", "primary-button hw-btn", "Assign a paper now");
        assignBtn.addEventListener("click", async () => {
          assignBtn.disabled = true; assignBtn.textContent = "Assigning...";
          try {
            await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action_id: "homework-assign" }) });
            location.reload();
          } catch (e) { assignBtn.disabled = false; assignBtn.textContent = "Assign a paper now"; alert(`Failed: ${e.message}`); }
        });
        empty.append(assignBtn);
      }
      body.append(empty);
      return;
    }

    const cur = hw.current;
    const card = el("div", "hw-card");

    // Status badge
    const overdue = hw.overdue;
    const daysLeft = hw.days_remaining;
    let badge, badgeClass;
    if (overdue) { badge = `${Math.abs(daysLeft)} day${Math.abs(daysLeft) !== 1 ? "s" : ""} overdue`; badgeClass = "hw-badge hw-badge--overdue"; }
    else if (daysLeft <= 3) { badge = `Due in ${daysLeft} day${daysLeft !== 1 ? "s" : ""}`; badgeClass = "hw-badge hw-badge--soon"; }
    else { badge = `${daysLeft} days left`; badgeClass = "hw-badge hw-badge--ok"; }

    const badgeEl = el("span", badgeClass, badge);
    const catEl = el("span", "hw-cat", cur.category);
    const meta = el("div", "hw-meta"); meta.append(badgeEl, catEl);
    card.append(meta);

    const titleEl = el("h3", "hw-title", cur.title || cur.stem);
    card.append(titleEl);

    const stemEl = el("p", "hw-stem", cur.stem);
    card.append(stemEl);

    const dueEl = el("p", "hw-due", `Assigned: ${cur.assigned_date} · Due: ${cur.due_date} · Completed: ${hw.completed_count}`);
    card.append(dueEl);

    const actions = el("div", "hw-actions");
    // Open in Obsidian (copy path)
    const openBtn = el("button", "copy-button", "📖 Open wiki page");
    openBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(`wiki/${cur.category}/${cur.stem}.md`);
      openBtn.textContent = "Path copied!";
      setTimeout(() => { openBtn.textContent = "📖 Open wiki page"; }, 1500);
    });
    actions.append(openBtn);

    if (serverState.online) {
      const doneBtn = el("button", "primary-button hw-btn", "✓ Mark complete");
      doneBtn.addEventListener("click", async () => {
        doneBtn.disabled = true; doneBtn.textContent = "Saving...";
        try {
          await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "homework-complete" }) });
          location.reload();
        } catch (e) { doneBtn.disabled = false; doneBtn.textContent = "✓ Mark complete"; alert(`Failed: ${e.message}`); }
      });
      actions.append(doneBtn);

      const skipBtn = el("button", "copy-button", "Skip");
      skipBtn.addEventListener("click", async () => {
        if (!confirm("Skip this paper and get a new one?")) return;
        skipBtn.disabled = true;
        try {
          await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "homework-skip" }) });
          location.reload();
        } catch (e) { skipBtn.disabled = false; alert(`Failed: ${e.message}`); }
      });
      actions.append(skipBtn);
    }
    card.append(actions);
    body.append(card);

    // ── Start Session button ───────────────────────────────────────────────
    if (serverState.online) {
      const sessionRow = el("div", "hw-session-row");
      const startBtn = el("button", "primary-button", "📂 Start reading session");
      startBtn.title = "Creates homework/" + cur.assigned_date + "-" + cur.stem + "/ with notes, discussion log, and ideas templates";
      startBtn.addEventListener("click", async () => {
        startBtn.disabled = true; startBtn.textContent = "Creating...";
        try {
          const resp = await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "homework-start-session" }) });
          const res = await resp.json();
          if (res.ok) {
            startBtn.textContent = "✓ Session ready — opening folder";
            // Open folder
            await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action_id: "homework-open-session", params: { session_dir: res.session_dir } }) });
            setTimeout(() => location.reload(), 800);
          } else {
            startBtn.disabled = false; startBtn.textContent = "📂 Start reading session";
            alert(res.stderr || "Failed to create session folder");
          }
        } catch (e) { startBtn.disabled = false; startBtn.textContent = "📂 Start reading session"; alert(e.message); }
      });
      sessionRow.append(startBtn);

      const openIdeaBtn = el("button", "copy-button", "💡 Open idea-wiki");
      openIdeaBtn.addEventListener("click", async () => {
        await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: "homework-open-idea-wiki" }) });
      });
      sessionRow.append(openIdeaBtn);
      body.append(sessionRow);
    }

    // ── Format note ─────────────────────────────────────────────────────────
    const fmtNote = el("p", "hw-format-note",
      "💡 파일 형식: notes.md / discussion-log.md / ideas.md (markdown) — 그림은 images/ 폴더에 저장 후 ![label](images/file.png)로 참조. Obsidian에서 인라인 이미지 표시 가능. Word 내보내기: 로컬 LLM에서 /export-docx-no-tc");
    body.append(fmtNote);

    // ── Past sessions list ───────────────────────────────────────────────────
    const sessions = hw.sessions || [];
    if (sessions.length > 0) {
      const sessSection = el("div", "hw-sessions-section");
      sessSection.append(el("h4", "hw-section-title", `Reading Sessions (${sessions.length})`));

      const sessGrid = el("div", "hw-sessions-grid");
      sessions.forEach(sess => {
        const scard = el("div", "hw-session-card");

        const sTitle = el("p", "hw-session-title", sess.title || sess.dir_name);
        const sMeta = el("p", "hw-session-meta", `${sess.session_date}${sess.idea_count > 0 ? ` · ${sess.idea_count} idea${sess.idea_count !== 1 ? "s" : ""}` : ""}`);
        const sBadges = el("div", "hw-session-badges");
        if (sess.has_notes) sBadges.append(el("span", "hw-session-badge", "notes"));
        if (sess.has_discussion) sBadges.append(el("span", "hw-session-badge", "discussion"));
        if (sess.has_ideas) sBadges.append(el("span", "hw-session-badge hw-session-badge--idea", "ideas"));

        scard.append(sTitle, sMeta, sBadges);

        if (serverState.online) {
          const openSBtn = el("button", "copy-button hw-session-open", "Open folder");
          openSBtn.addEventListener("click", async () => {
            await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action_id: "homework-open-session", params: { session_dir: sess.dir } }) });
          });
          scard.append(openSBtn);
        } else {
          const pathBtn = el("button", "copy-button hw-session-open", "Copy path");
          pathBtn.addEventListener("click", () => { navigator.clipboard.writeText(sess.dir); pathBtn.textContent = "Copied!"; setTimeout(() => { pathBtn.textContent = "Copy path"; }, 1500); });
          scard.append(pathBtn);
        }
        sessGrid.append(scard);
      });
      sessSection.append(sessGrid);
      body.append(sessSection);
    }

    // ── Idea-wiki panel ──────────────────────────────────────────────────────
    const ideaWiki = hw.idea_wiki || [];
    if (ideaWiki.length > 0) {
      const ideaSection = el("div", "hw-idea-wiki-section");
      const ideaHeader = el("div", "hw-section-header");
      ideaHeader.append(el("h4", "hw-section-title", `Idea Wiki (${ideaWiki.length})`));
      if (serverState.online) {
        const openIdxBtn = el("button", "copy-button", "Open folder");
        openIdxBtn.addEventListener("click", async () => {
          await fetch(apiUrl("/api/run"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action_id: "homework-open-idea-wiki" }) });
        });
        ideaHeader.append(openIdxBtn);
      }
      ideaSection.append(ideaHeader);

      ideaWiki.slice(0, 8).forEach(idea => {
        const irow = el("div", "hw-idea-row");
        const statusClass = {seed: "hw-idea-badge--seed", developing: "hw-idea-badge--developing",
          promoted: "hw-idea-badge--promoted", archived: "hw-idea-badge--archived"}[idea.status] || "hw-idea-badge--seed";
        irow.append(el("span", `hw-idea-badge ${statusClass}`, idea.status || "seed"));
        const iTitle = el("span", "hw-idea-title", idea.title || idea.filename);
        irow.append(iTitle);
        if (idea.date) irow.append(el("span", "hw-idea-date", idea.date));
        if (idea.source_paper_stem) {
          const srcBtn = el("button", "hw-idea-src", idea.source_paper_stem.split("-").slice(0, 2).join("-") + "…");
          srcBtn.title = idea.source_paper_stem;
          srcBtn.addEventListener("click", () => { navigator.clipboard.writeText(idea.source_paper_stem); srcBtn.textContent = "Copied!"; setTimeout(() => srcBtn.textContent = idea.source_paper_stem.split("-").slice(0, 2).join("-") + "…", 1500); });
          irow.append(srcBtn);
        }
        ideaSection.append(irow);
      });
      if (ideaWiki.length > 8) ideaSection.append(el("p", "hw-idea-more", `+ ${ideaWiki.length - 8} more in homework/idea-wiki/`));
      body.append(ideaSection);
    }
  }



  // ── Project scout brief loader ─────────────────────────────────────────────
  // Reads scouts/project-*/ entries from data.scouts, shows selector + Run button.
  (function setupProjectScoutBriefs() {
    const section = byId("project-scout-brief-section");
    const divider = byId("project-scout-divider");
    const select  = byId("project-scout-brief-select");
    const meta    = byId("project-scout-brief-meta");
    const runBtn  = byId("project-scout-brief-run");
    const output  = byId("project-scout-brief-output");
    if (!section || !select || !runBtn) return;

    // Filter scouts that came from a confidential project (slug starts with "project-")
    const projectBriefs = (data.scout_history || [])
      .filter(s => s.slug && s.slug.startsWith("project-"));

    if (!projectBriefs.length) return;  // hide if none exist yet

    section.hidden = false;
    if (divider) divider.hidden = false;

    projectBriefs.forEach(b => {
      const opt = text(el("option"), b.title || b.slug);
      opt.value = b.slug;
      select.append(opt);
    });

    function showMeta() {
      const brief = projectBriefs.find(b => b.slug === select.value);
      if (!brief || !meta) return;
      const parts = [];
      if (brief.keywords) parts.push(`Keywords: ${brief.keywords}`);
      if (brief.year_range) parts.push(`Year range: ${brief.year_range}`);
      if (brief.exclude) parts.push(`Exclude: ${brief.exclude}`);
      meta.textContent = parts.join(" · ");
      meta.hidden = !parts.length;
    }
    select.addEventListener("change", showMeta);
    showMeta();

    runBtn.addEventListener("click", async () => {
      const slug = select.value;
      if (!slug) return;
      if (!serverState.online || !serverState.allowed.has("scout-quick")) {
        if (output) { output.hidden = false; output.dataset.state = "error"; output.textContent = serverRequiredMessage(); }
        return;
      }
      runBtn.disabled = true; runBtn.textContent = "Running...";
      if (output) { output.hidden = false; output.dataset.state = "running"; output.textContent = `Running scout against ${slug}...`; }
      try {
        // Scout using the exported brief path as the topic source
        const brief = projectBriefs.find(b => b.slug === slug);
        const resp = await fetch(apiUrl("/api/run"), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action_id: "project-scout",
            project_slug: slug,
            params: { scout_slug: slug, brief_path: brief ? brief.brief_path : `scouts/${slug}/Scout_Brief.md` },
          }),
        });
        const result = await resp.json();
        if (result.ok) {
          // Delete the brief file after successful scout — keywords preserved in candidates/
          try {
            await fetch(apiUrl("/api/run"), {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ action_id: "delete-scout-brief", project_slug: slug }),
            });
          } catch (_) { /* non-fatal */ }
          if (output) {
            output.dataset.state = "ok";
            output.textContent = ["Scout done. Brief deleted — keywords preserved in candidates/.", result.stdout].filter(Boolean).join("\n\n");
          }
          // Reload after short delay so the selector updates
          setTimeout(() => window.location.reload(), 2000);
        } else {
          if (output) {
            output.dataset.state = "error";
            output.textContent = ["Failed.", result.stdout, result.stderr].filter(Boolean).join("\n\n");
          }
        }
      } catch (e) {
        if (output) { output.dataset.state = "error"; output.textContent = `Error: ${e.message}`; }
      } finally { runBtn.disabled = false; runBtn.textContent = "Run Scout"; }
    });
  })();

  // Quick Scout — runs scripts/scout_all.py against a freshly created paper scout request.
  const quickScoutForm = byId("quick-scout-form");
  if (quickScoutForm) {
    const quickScoutOutput = byId("quick-scout-output");
    const quickScoutButton = byId("quick-scout-run");
    quickScoutForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const topic = byId("quick-scout-topic").value.trim();
      if (!topic) {
        quickScoutOutput.dataset.state = "error";
        quickScoutOutput.textContent = "Topic is required.";
        return;
      }
      const params = {
        topic,
        keywords: byId("quick-scout-keywords").value.trim(),
        year_start: byId("quick-scout-year-start").value.trim(),
        year_end: byId("quick-scout-year-end").value.trim(),
      };
      if (!serverState.online || !serverState.allowed.has("scout-quick")) {
        quickScoutOutput.dataset.state = "error";
        quickScoutOutput.textContent = serverRequiredMessage();
        return;
      }
      const originalLabel = quickScoutButton.textContent;
      quickScoutButton.disabled = true;
      quickScoutButton.textContent = "Running...";
      quickScoutOutput.dataset.state = "running";
      quickScoutOutput.textContent = "Running scout against new exploration idea-note...";
      try {
        const response = await fetch(apiUrl("/api/run"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: "scout-quick", params }),
        });
        const result = await response.json();
        quickScoutOutput.dataset.state = result.ok ? "ok" : "error";
        const chunks = [
          result.ok ? "Done." : "Failed.",
          result.command ? `Command: ${result.command}` : "",
          result.stdout ? `Output:\n${result.stdout}` : "",
          result.stderr ? `Errors:\n${result.stderr}` : "",
        ].filter(Boolean);
        quickScoutOutput.textContent = chunks.join("\n\n");
        if (result.ok) offerPaperScoutTriagePrompt(quickScoutSlug(topic, params.year_start, params.year_end), quickScoutOutput);
      } catch (error) {
        quickScoutOutput.dataset.state = "error";
        quickScoutOutput.textContent = error.message === "Failed to fetch" ? serverRequiredMessage() : `Run failed: ${error.message}`;
      } finally {
        quickScoutButton.disabled = false;
        quickScoutButton.textContent = originalLabel;
      }
    });
  }

  // ── renderBackup ──────────────────────────────────────────────────────────
  function renderBackup(backup) {
    const body = byId("backup-body");
    if (!body) return;
    body.textContent = "";

    const b = backup || {};
    const gdrivePath     = b.gdrive_path || "";
    const repoInit       = !!b.repo_initialized;
    const lastBackup     = b.last_backup || null;
    const daysSince      = typeof b.days_since_backup === "number" ? b.days_since_backup : null;
    const overdue        = b.overdue !== false;
    const autoInstalled  = b.plist_installed || b.auto_backup_installed || false;
    const intervalHours  = b.auto_backup_interval_hours || 24;
    const snapshotId     = b.last_snapshot_id || null;
    const dataMb         = b.data_added_mb || null;

    const output = el("pre", "action-output");
    output.id = "backup-output";
    output.dataset.state = "idle";
    output.textContent = "Idle.";

    async function serverCall(actionId, params, btnEl, busyLabel) {
      if (!serverState.online || !serverState.allowed.has(actionId)) {
        output.dataset.state = "error";
        output.textContent = serverRequiredMessage();
        return null;
      }
      const origLabel = btnEl ? btnEl.textContent : "";
      if (btnEl) { btnEl.disabled = true; btnEl.textContent = busyLabel || "Running..."; }
      output.dataset.state = "running";
      output.textContent = "Running…";
      try {
        const resp = await fetch(apiUrl("/api/run"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action_id: actionId, params: params || {} }),
        });
        const result = await resp.json();
        output.dataset.state = result.ok ? "ok" : "error";
        const chunks = [
          result.ok ? "✓ Done." : "✗ Failed.",
          result.error  ? `Error: ${result.error}` : "",
          result.stderr ? `Stderr:\n${result.stderr}` : "",
          result.stdout ? result.stdout : "",
        ].filter(Boolean);
        output.textContent = chunks.join("\n\n");
        return result;
      } catch (err) {
        output.dataset.state = "error";
        output.textContent = err.message === "Failed to fetch" ? serverRequiredMessage() : `Error: ${err.message}`;
        return null;
      } finally {
        if (btnEl) { btnEl.disabled = false; btnEl.textContent = origLabel; }
      }
    }

    // ── Status badges ─────────────────────────────────────────────────────
    const statusRow = el("div", "backup-status-row");

    // Restic status pill
    const repoEl = el("span",
      repoInit ? "backup-badge backup-badge--ok" : "backup-badge backup-badge--error",
      repoInit ? "restic repo ✓" : "restic repo: not initialised");
    statusRow.append(repoEl);

    // Last backup pill
    let badgeText, badgeClass;
    if (!lastBackup) {
      badgeText = "Never backed up"; badgeClass = "backup-badge backup-badge--error";
    } else if (overdue) {
      badgeText = `Last: ${lastBackup.slice(0,10)} (${daysSince}d ago) — overdue!`;
      badgeClass = "backup-badge backup-badge--warn";
    } else {
      badgeText = `Last: ${lastBackup.slice(0,10)} (${daysSince}d ago)`;
      badgeClass = "backup-badge backup-badge--ok";
    }
    const badgeEl = el("span", badgeClass, badgeText);
    badgeEl.style.marginLeft = "6px";
    statusRow.append(badgeEl);

    if (snapshotId) {
      const snapEl = el("span", "backup-badge backup-badge--ok", `snapshot ${snapshotId}`);
      snapEl.style.marginLeft = "6px";
      statusRow.append(snapEl);
    }
    if (dataMb !== null) {
      const sizeEl = el("span", "backup-badge backup-badge--ok", `+${dataMb} MB last run`);
      sizeEl.style.marginLeft = "6px";
      statusRow.append(sizeEl);
    }
    body.append(statusRow);

    // ── Google Drive path ─────────────────────────────────────────────────
    const pathRow = el("div", "backup-path-row");
    const pathLabel = el("label", "backup-path-label");
    pathLabel.textContent = "Google Drive path: ";
    const pathInput = el("input", "backup-path-input");
    pathInput.type = "text";
    pathInput.value = gdrivePath;
    pathInput.placeholder = "/Users/…/Google Drive/My Drive";
    pathLabel.append(pathInput);
    pathRow.append(pathLabel);

    const detectBtn = el("button", "copy-button", "Auto-detect");
    detectBtn.type = "button";
    detectBtn.addEventListener("click", async () => {
      const result = await serverCall("backup-detect-gdrive", {}, detectBtn, "Detecting…");
      if (!result || !result.ok) return;
      const parsed = result.data || (() => { try { return JSON.parse(result.stdout); } catch(_){return null;} })();
      if (!parsed || !parsed.found) {
        output.textContent = "Google Drive not found. Make sure Google Drive for Desktop is running.";
        return;
      }
      if (parsed.candidates.length === 1) {
        pathInput.value = parsed.candidates[0];
        output.textContent = `Found: ${parsed.candidates[0]}`;
      } else {
        const oldPicker = pathRow.querySelector(".backup-gdrive-picker");
        if (oldPicker) oldPicker.remove();
        const picker = el("select", "backup-gdrive-picker");
        picker.append(el("option", "", "— choose account —"));
        parsed.candidates.forEach(c => {
          const opt = document.createElement("option");
          opt.value = c;
          opt.textContent = c.split("GoogleDrive-")[1]?.replace("/My Drive","") || c;
          picker.append(opt);
        });
        picker.addEventListener("change", () => { if (picker.value) pathInput.value = picker.value; });
        pathRow.insertBefore(picker, detectBtn);
        output.textContent = `Found ${parsed.candidates.length} accounts — select one above.`;
      }
    });
    pathRow.append(detectBtn);

    const savePathBtn = el("button", "copy-button", "Save path");
    savePathBtn.type = "button";
    savePathBtn.addEventListener("click", async () => {
      const path = pathInput.value.trim();
      if (!path) { output.dataset.state = "error"; output.textContent = "Enter a path first."; return; }
      const result = await serverCall("backup-set-path", { path }, savePathBtn, "Saving…");
      if (result && result.ok) setTimeout(() => location.reload(), 1200);
    });
    pathRow.append(savePathBtn);
    body.append(pathRow);

    // ── Step 1: Initialise repo (shown only when not yet done) ────────────
    if (!repoInit) {
      const initNote = el("p", "backup-init-note",
        "⚠️  First-time setup: initialise the restic repository on Google Drive.");
      initNote.style.cssText = "margin:8px 0 4px;font-size:0.85rem;color:#b45309;";

      const initBtn = el("button", "run-button", "🗄 Initialise restic repo");
      initBtn.type = "button";
      initBtn.style.marginBottom = "10px";
      initBtn.addEventListener("click", async () => {
        const path = pathInput.value.trim();
        if (path) await serverCall("backup-set-path", { path }, null, "");
        const result = await serverCall("backup-init-repo", {}, initBtn, "Initialising…");
        if (result && result.ok) setTimeout(() => location.reload(), 1500);
      });
      body.append(initNote, initBtn);
    }

    // ── Backup action buttons ─────────────────────────────────────────────
    const btnRow = el("div", "backup-btn-row");

    const backupBtn = el("button", "run-button", "⬆ Backup now (incremental)");
    backupBtn.type = "button";
    backupBtn.title = "Restic snapshot — only changed chunks are uploaded. PDFs included; deduplication keeps size small.";
    backupBtn.disabled = !repoInit;
    backupBtn.addEventListener("click", async () => {
      const result = await serverCall("backup-run", {}, backupBtn, "Backing up…");
      if (result && result.ok) {
        const s = result.summary || {};
        const added = s.data_added ? `+${(s.data_added/1048576).toFixed(2)} MB` : "";
        output.textContent = [
          "✓ Snapshot created.",
          s.snapshot_id ? `ID: ${s.snapshot_id}` : "",
          s.files_new   ? `New files: ${s.files_new}` : "",
          s.files_changed ? `Changed: ${s.files_changed}` : "",
          added,
        ].filter(Boolean).join("  •  ");
        setTimeout(() => location.reload(), 2000);
      }
    });
    btnRow.append(backupBtn);

    const dryRunBtn = el("button", "copy-button", "Dry run");
    dryRunBtn.type = "button";
    dryRunBtn.title = "Show what would be backed up, without writing anything.";
    dryRunBtn.disabled = !repoInit;
    dryRunBtn.addEventListener("click", () =>
      serverCall("backup-run", { dry_run: true }, dryRunBtn, "Scanning…"));
    btnRow.append(dryRunBtn);

    const snapshotsBtn = el("button", "copy-button", "📋 Snapshots");
    snapshotsBtn.type = "button";
    snapshotsBtn.disabled = !repoInit;
    snapshotsBtn.addEventListener("click", async () => {
      const result = await serverCall("backup-snapshots", { limit: 30 }, snapshotsBtn, "Loading…");
      if (!result || !result.ok) return;
      const parsed = result.data || (() => { try { return JSON.parse(result.stdout); } catch(_){return null;} })();
      if (!parsed || !parsed.snapshots) return;
      const lines = parsed.snapshots.map(s => {
        const t = (s.time||"").slice(0,16).replace("T"," ");
        return `${t}  [${s.id}]`;
      });
      output.textContent = lines.length
        ? `Snapshots (newest first):\n${lines.join("\n")}`
        : "No snapshots found.";
    });
    btnRow.append(snapshotsBtn);

    const pruneBtn = el("button", "copy-button", "🗑 Prune >6 months");
    pruneBtn.type = "button";
    pruneBtn.disabled = !repoInit;
    pruneBtn.title = "Remove snapshots older than 6 months and reclaim space.";
    pruneBtn.addEventListener("click", async () => {
      if (!confirm("Prune snapshots older than 6 months?")) return;
      await serverCall("backup-prune", {}, pruneBtn, "Pruning…");
    });
    btnRow.append(pruneBtn);

    const openFolderBtn = el("button", "copy-button", "Open folder");
    openFolderBtn.type = "button";
    openFolderBtn.addEventListener("click", () =>
      serverCall("backup-open-folder", {}, openFolderBtn, "Opening…"));
    btnRow.append(openFolderBtn);

    body.append(btnRow);

    // ── Auto-backup (LaunchAgent) ─────────────────────────────────────────
    const autoRow = el("div", "backup-auto-row");
    const autoStatus = el("span", "backup-auto-status",
      autoInstalled ? `Auto-backup: every ${intervalHours}h ✓` : "Auto-backup: not installed");
    autoRow.append(autoStatus);

    if (!autoInstalled) {
      const installBtn = el("button", "copy-button", "Install daily auto-backup");
      installBtn.type = "button";
      installBtn.disabled = !repoInit;
      installBtn.addEventListener("click", async () => {
        const result = await serverCall("backup-install-schedule", {}, installBtn, "Installing…");
        if (result && result.ok) setTimeout(() => location.reload(), 1200);
      });
      autoRow.append(installBtn);
    } else {
      const uninstallBtn = el("button", "copy-button", "Uninstall");
      uninstallBtn.type = "button";
      uninstallBtn.addEventListener("click", async () => {
        if (!confirm("Remove auto-backup LaunchAgent?")) return;
        const result = await serverCall("backup-uninstall-schedule", {}, uninstallBtn, "Removing…");
        if (result && result.ok) setTimeout(() => location.reload(), 1200);
      });
      autoRow.append(uninstallBtn);
    }
    body.append(autoRow);

    // ── restic install hint ───────────────────────────────────────────────
    const hint = el("p", "backup-hint",
      "Requires restic: brew install restic  (one-time setup, ~10 MB)");
    hint.style.cssText = "margin-top:8px;font-size:0.78rem;color:#6b7280;";
    body.append(hint);

    body.append(output);
  }

  /* ──────────────────────────────────────────────────────────────────
     ADMIN MODE (PIN-protected) + PROJECT MANAGERS
     ────────────────────────────────────────────────────────────────── */

  // Admin session state lives in sessionStorage so it ends when the tab closes.
  const ADMIN_PIN_KEY = "dashboard.adminPin";       // PIN cached for this tab session only
  const ADMIN_UNLOCKED_KEY = "dashboard.adminOn";   // "1" while unlocked in this tab

  function adminPin() {
    return sessionStorage.getItem(ADMIN_PIN_KEY) || "";
  }
  function isAdminUnlocked() {
    return sessionStorage.getItem(ADMIN_UNLOCKED_KEY) === "1" && !!adminPin();
  }
  function lockAdmin() {
    sessionStorage.removeItem(ADMIN_PIN_KEY);
    sessionStorage.removeItem(ADMIN_UNLOCKED_KEY);
    applyAdminMode();
  }
  function unlockAdmin(pin) {
    sessionStorage.setItem(ADMIN_PIN_KEY, pin);
    sessionStorage.setItem(ADMIN_UNLOCKED_KEY, "1");
    applyAdminMode();
  }
  function applyAdminMode() {
    const on = isAdminUnlocked();
    document.body.classList.toggle("admin-mode", on);
    const btn = byId("admin-toggle");
    if (btn) {
      btn.textContent = on ? "🔓 Admin: On" : "🔒 Admin: Off";
      btn.classList.toggle("admin-on", on);
    }
  }

  async function callApi(action_id, params, project_slug) {
    const resp = await fetch(apiUrl("/api/run"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id, project_slug: project_slug || null, params: params || {} }),
    });
    let out;
    try { out = await resp.json(); }
    catch (err) { throw new Error("Server returned non-JSON response"); }
    if (!out.ok) throw new Error(out.stderr || "Request failed");
    return out;
  }

  async function getAdminStatus() {
    const out = await callApi("admin-status", {});
    try { return JSON.parse(out.stdout); }
    catch (e) { return { configured: false, recovery_email_masked: "", smtp_configured: false }; }
  }

  (function wireAdminToggle() {
    const btn = byId("admin-toggle");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      if (isAdminUnlocked()) {
        lockAdmin();
        return;
      }
      let status;
      try { status = await getAdminStatus(); }
      catch (err) {
        alert("Cannot reach the dashboard server. Start it with:\n  python3 scripts/dashboard_server.py --port 8765");
        return;
      }
      if (status.configured) {
        openAdminUnlockModal(status);
      } else {
        openAdminSetupModal();
      }
    });
    applyAdminMode();
  })();

  function makeOverlay(id, className) {
    const old = byId(id);
    if (old) old.remove();
    const overlay = el("div", className + " admin-modal-overlay");
    overlay.id = id;
    overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
    return overlay;
  }

  function openAdminSetupModal() {
    const overlay = makeOverlay("admin-setup", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), "Set up admin PIN"));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    modal.append(text(el("p", "admin-help"),
      "Choose a 4–8 digit PIN to unlock admin mode (required to edit project managers). " +
      "Provide a recovery email so you can reset the PIN later."));

    const pinIn = document.createElement("input");
    pinIn.type = "password";
    pinIn.inputMode = "numeric";
    pinIn.placeholder = "PIN (4–8 digits)";
    pinIn.maxLength = 8;
    const pinIn2 = document.createElement("input");
    pinIn2.type = "password";
    pinIn2.inputMode = "numeric";
    pinIn2.placeholder = "Confirm PIN";
    pinIn2.maxLength = 8;
    const emailIn = document.createElement("input");
    emailIn.type = "email";
    emailIn.placeholder = "Recovery email";

    const fieldWrap = el("div", "admin-field-wrap");
    [pinIn, pinIn2, emailIn].forEach((inp) => fieldWrap.append(inp));
    modal.append(fieldWrap);

    const status = el("p", "manager-editor-status");
    modal.append(status);

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const save = text(el("button", "manager-editor-save"), "Save & Unlock");
    save.type = "button";
    save.addEventListener("click", async () => {
      const pin = pinIn.value.trim();
      if (!/^\d{4,8}$/.test(pin)) { status.textContent = "PIN must be 4–8 digits."; return; }
      if (pin !== pinIn2.value.trim()) { status.textContent = "PIN confirmation does not match."; return; }
      const email = emailIn.value.trim();
      if (!/^\S+@\S+\.\S+$/.test(email)) { status.textContent = "Invalid recovery email."; return; }
      save.disabled = true;
      status.textContent = "Saving...";
      try {
        await callApi("admin-setup", { pin, recovery_email: email });
        unlockAdmin(pin);
        overlay.remove();
      } catch (err) {
        status.textContent = "Setup failed: " + err.message;
        save.disabled = false;
      }
    });
    actions.append(cancel, save);
    modal.append(actions);
    document.body.append(overlay);
    pinIn.focus();
  }

  function openAdminUnlockModal(status) {
    const overlay = makeOverlay("admin-unlock", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), "Enter admin PIN"));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    const pinIn = document.createElement("input");
    pinIn.type = "password";
    pinIn.inputMode = "numeric";
    pinIn.placeholder = "PIN";
    pinIn.maxLength = 8;
    modal.append(pinIn);

    const statusLine = el("p", "manager-editor-status");
    modal.append(statusLine);

    const forgot = el("p", "admin-forgot-line");
    const forgotLink = text(el("a", "admin-forgot-link"), "Forgot PIN?");
    forgotLink.href = "#";
    forgotLink.addEventListener("click", (e) => {
      e.preventDefault();
      overlay.remove();
      openForgotPinModal(status);
    });
    forgot.append(forgotLink);
    modal.append(forgot);

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const ok = text(el("button", "manager-editor-save"), "Unlock");
    ok.type = "button";
    async function tryUnlock() {
      const pin = pinIn.value.trim();
      if (!/^\d{4,8}$/.test(pin)) { statusLine.textContent = "PIN must be 4–8 digits."; return; }
      ok.disabled = true;
      statusLine.textContent = "Verifying...";
      try {
        await callApi("admin-verify", { pin });
        unlockAdmin(pin);
        overlay.remove();
      } catch (err) {
        statusLine.textContent = err.message;
        ok.disabled = false;
      }
    }
    ok.addEventListener("click", tryUnlock);
    pinIn.addEventListener("keydown", (e) => { if (e.key === "Enter") tryUnlock(); });
    actions.append(cancel, ok);
    modal.append(actions);
    document.body.append(overlay);
    pinIn.focus();
  }

  function openForgotPinModal(status) {
    const overlay = makeOverlay("admin-forgot", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), "Reset admin PIN"));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    const helpText = `A 6-digit code will be sent to your recovery email (${status.recovery_email_masked || "configured address"}). ` +
      (status.smtp_configured
        ? "Email delivery is configured."
        : "SMTP is not configured: the code will also be printed to the dashboard-server terminal as a fallback.");
    modal.append(text(el("p", "admin-help"), helpText));

    const emailIn = document.createElement("input");
    emailIn.type = "email";
    emailIn.placeholder = "Confirm your recovery email";
    modal.append(emailIn);

    const sendBtn = text(el("button", "manager-editor-add"), "Send reset code");
    sendBtn.type = "button";
    modal.append(sendBtn);

    const codeWrap = el("div", "admin-reset-stage");
    codeWrap.style.display = "none";
    const codeIn = document.createElement("input");
    codeIn.type = "text";
    codeIn.inputMode = "numeric";
    codeIn.placeholder = "6-digit code";
    codeIn.maxLength = 6;
    const newPin = document.createElement("input");
    newPin.type = "password";
    newPin.inputMode = "numeric";
    newPin.placeholder = "New PIN (4–8 digits)";
    newPin.maxLength = 8;
    const newPin2 = document.createElement("input");
    newPin2.type = "password";
    newPin2.inputMode = "numeric";
    newPin2.placeholder = "Confirm new PIN";
    newPin2.maxLength = 8;
    [codeIn, newPin, newPin2].forEach((i) => codeWrap.append(i));
    modal.append(codeWrap);

    const statusLine = el("p", "manager-editor-status");
    modal.append(statusLine);

    sendBtn.addEventListener("click", async () => {
      const email = emailIn.value.trim();
      if (!/^\S+@\S+\.\S+$/.test(email)) { statusLine.textContent = "Enter a valid email."; return; }
      sendBtn.disabled = true;
      statusLine.textContent = "Sending...";
      try {
        const out = await callApi("admin-request-reset", { recovery_email: email });
        let info = {};
        try { info = JSON.parse(out.stdout); } catch {}
        statusLine.textContent = info.message || "Reset code sent.";
        codeWrap.style.display = "flex";
        codeIn.focus();
      } catch (err) {
        statusLine.textContent = err.message;
        sendBtn.disabled = false;
      }
    });

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const apply = text(el("button", "manager-editor-save"), "Reset PIN");
    apply.type = "button";
    apply.addEventListener("click", async () => {
      const code = codeIn.value.trim();
      const pin = newPin.value.trim();
      if (!/^\d{6}$/.test(code)) { statusLine.textContent = "Code must be 6 digits."; return; }
      if (!/^\d{4,8}$/.test(pin)) { statusLine.textContent = "New PIN must be 4–8 digits."; return; }
      if (pin !== newPin2.value.trim()) { statusLine.textContent = "PIN confirmation does not match."; return; }
      apply.disabled = true;
      statusLine.textContent = "Resetting...";
      try {
        await callApi("admin-reset-pin", { code, new_pin: pin });
        unlockAdmin(pin);
        statusLine.textContent = "PIN reset. Admin mode unlocked.";
        setTimeout(() => overlay.remove(), 600);
      } catch (err) {
        statusLine.textContent = err.message;
        apply.disabled = false;
      }
    });
    actions.append(cancel, apply);
    modal.append(actions);
    document.body.append(overlay);
    emailIn.focus();
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function closeManagerPopover() {
    const existing = byId("manager-popover");
    if (existing) existing.remove();
    document.removeEventListener("mousedown", onPopoverOutside, true);
    document.removeEventListener("keydown", onPopoverEsc, true);
  }
  function onPopoverOutside(e) {
    const pop = byId("manager-popover");
    if (pop && !pop.contains(e.target)) closeManagerPopover();
  }
  function onPopoverEsc(e) {
    if (e.key === "Escape") closeManagerPopover();
  }

  function openManagerPopover(anchor, managers) {
    closeManagerPopover();
    const list = (managers || []).filter((m) => m && (m.name || m.email));
    if (!list.length) return;
    const pop = el("div", "manager-popover");
    pop.id = "manager-popover";
    pop.setAttribute("role", "dialog");

    const header = el("div", "manager-pop-header");
    header.append(text(el("strong"), `Managers (${list.length})`));
    const closeBtn = text(el("button", "manager-pop-close", "×"), "×");
    closeBtn.type = "button";
    closeBtn.addEventListener("click", closeManagerPopover);
    header.append(closeBtn);
    pop.append(header);

    const multi = list.length > 1;
    let selectAllBox = null;
    if (multi) {
      const selRow = el("label", "manager-pop-row manager-pop-selectall");
      selectAllBox = document.createElement("input");
      selectAllBox.type = "checkbox";
      selectAllBox.checked = true;
      selRow.append(selectAllBox, text(el("span", "manager-pop-name"), "Select all"));
      pop.append(selRow);
    }

    const checkboxes = [];
    list.forEach((m, idx) => {
      const row = el("label", "manager-pop-row");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = true;
      cb.dataset.email = m.email || "";
      cb.dataset.name = m.name || "";
      checkboxes.push(cb);
      const name = el("span", "manager-pop-name");
      name.textContent = m.name || m.email || `Manager ${idx + 1}`;
      const mail = el("a", "manager-pop-email");
      if (m.email) {
        mail.href = `mailto:${encodeURIComponent(m.email)}`;
        mail.textContent = m.email;
      } else {
        mail.textContent = "(no email on file)";
        mail.classList.add("no-email");
      }
      mail.addEventListener("click", (e) => e.stopPropagation());
      row.append(cb, name, mail);
      pop.append(row);
    });

    if (selectAllBox) {
      selectAllBox.addEventListener("change", () => {
        checkboxes.forEach((cb) => { cb.checked = selectAllBox.checked; });
      });
      checkboxes.forEach((cb) => {
        cb.addEventListener("change", () => {
          selectAllBox.checked = checkboxes.every((c) => c.checked);
        });
      });
    }

    const actions = el("div", "manager-pop-actions");
    const sendBtn = text(el("button", "manager-pop-send"),
      multi ? "📧 Email selected managers" : "📧 Email this manager");
    sendBtn.type = "button";
    sendBtn.addEventListener("click", () => {
      const picked = checkboxes
        .filter((cb) => cb.checked && cb.dataset.email)
        .map((cb) => cb.dataset.email);
      if (!picked.length) {
        alert("No managers with an email address are selected.");
        return;
      }
      window.location.href = `mailto:${picked.join(",")}`;
    });
    actions.append(sendBtn);
    pop.append(actions);

    document.body.append(pop);
    const rect = anchor.getBoundingClientRect();
    const top = window.scrollY + rect.bottom + 6;
    let left = window.scrollX + rect.right - pop.offsetWidth;
    if (left < 8) left = 8;
    pop.style.top = `${top}px`;
    pop.style.left = `${left}px`;

    setTimeout(() => {
      document.addEventListener("mousedown", onPopoverOutside, true);
      document.addEventListener("keydown", onPopoverEsc, true);
    }, 0);
  }

  function buildManagerBadge(project) {
    const wrap = el("div", "manager-badge-wrap");
    const managers = Array.isArray(project.managers) ? project.managers : [];
    if (managers.length === 0) {
      const empty = el("span", "manager-empty", "No manager assigned");
      wrap.append(empty);
    } else {
      const trigger = el("button", "manager-trigger");
      trigger.type = "button";
      trigger.title = "Click to view email addresses";
      const labelNames = managers
        .map((m) => m.name || m.email)
        .filter(Boolean);
      const label = labelNames.length <= 2
        ? labelNames.join(", ")
        : `${labelNames.slice(0, 2).join(", ")} +${labelNames.length - 2} more`;
      trigger.append(text(el("span", "manager-icon"), "👤"));
      trigger.append(text(el("span", "manager-names"), label));
      trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        openManagerPopover(trigger, managers);
      });
      wrap.append(trigger);
    }
    const editBtn = el("button", "manager-edit-btn");
    editBtn.type = "button";
    editBtn.title = "Edit managers (admin mode)";
    editBtn.textContent = "✎";
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (!isAdminUnlocked()) {
        alert("Admin mode is locked. Unlock it from the top bar first.");
        return;
      }
      openManagerEditor(project);
    });
    wrap.append(editBtn);
    return wrap;
  }

  function openManagerEditor(project) {
    closeManagerPopover();
    const existing = byId("manager-editor");
    if (existing) existing.remove();

    const overlay = el("div", "manager-editor-overlay");
    overlay.id = "manager-editor";
    const modal = el("div", "manager-editor-modal");
    overlay.append(modal);

    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `Edit managers — ${project.title || project.slug}`));
    const closeBtn = text(el("button", "manager-editor-close"), "×");
    closeBtn.type = "button";
    closeBtn.addEventListener("click", () => overlay.remove());
    head.append(closeBtn);
    modal.append(head);

    const listWrap = el("div", "manager-editor-list");
    modal.append(listWrap);

    const rows = (Array.isArray(project.managers) ? project.managers : []).map((m) => ({
      name: m.name || "",
      email: m.email || "",
    }));

    function renderRows() {
      listWrap.innerHTML = "";
      rows.forEach((row, idx) => {
        const r = el("div", "manager-editor-row");
        const nameIn = document.createElement("input");
        nameIn.type = "text";
        nameIn.placeholder = "Name";
        nameIn.value = row.name;
        nameIn.addEventListener("input", () => { row.name = nameIn.value; });
        const emailIn = document.createElement("input");
        emailIn.type = "email";
        emailIn.placeholder = "email@example.com";
        emailIn.value = row.email;
        emailIn.addEventListener("input", () => { row.email = emailIn.value; });
        const del = text(el("button", "manager-editor-del"), "🗑");
        del.type = "button";
        del.title = "Remove";
        del.addEventListener("click", () => {
          rows.splice(idx, 1);
          renderRows();
        });
        r.append(nameIn, emailIn, del);
        listWrap.append(r);
      });
      if (rows.length === 0) {
        listWrap.append(text(el("p", "manager-editor-empty"), "No managers assigned. Add one below."));
      }
    }
    renderRows();

    const addBtn = text(el("button", "manager-editor-add"), "+ Add manager");
    addBtn.type = "button";
    addBtn.addEventListener("click", () => {
      rows.push({ name: "", email: "" });
      renderRows();
    });
    modal.append(addBtn);

    const status = el("p", "manager-editor-status");
    modal.append(status);

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const save = text(el("button", "manager-editor-save"), "Save");
    save.type = "button";
    save.addEventListener("click", async () => {
      if (!isAdminUnlocked()) {
        status.textContent = "Admin mode is locked. Unlock from the top bar.";
        return;
      }
      const cleaned = rows
        .map((r) => ({ name: (r.name || "").trim(), email: (r.email || "").trim() }))
        .filter((r) => r.name || r.email);
      for (const r of cleaned) {
        if (r.email && !/^\S+@\S+\.\S+$/.test(r.email)) {
          status.textContent = `Invalid email: ${r.email}`;
          return;
        }
      }
      save.disabled = true;
      status.textContent = "Saving...";
      try {
        await callApi("update-managers", { managers: cleaned, admin_pin: adminPin() }, project.slug);
        status.textContent = "Saved. Reloading...";
        setTimeout(() => window.location.reload(), 400);
      } catch (err) {
        status.textContent = "Save failed: " + err.message;
        save.disabled = false;
      }
    });
    actions.append(cancel, save);
    modal.append(actions);

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.remove();
    });
    document.body.append(overlay);
  }

  // Inject manager badges + "Add data update" button into project cards.
  (function decorateProjectCards() {
    if (!data || !Array.isArray(data.projects)) return;
    const projectRoot = byId("project-cards");
    if (!projectRoot) return;
    const cards = projectRoot.querySelectorAll(".project-card");
    cards.forEach((card, idx) => {
      const project = data.projects[idx];
      if (!project) return;

      const dataBtnRow = el("div", "card-actions-row");
      const addData = text(el("button", "card-action-btn add-data-btn"), "+ Data update");
      addData.type = "button";
      addData.title = "Record a new data update for this project";
      addData.addEventListener("click", () => openDataUpdateModal(project));
      dataBtnRow.append(addData);

      const renumberBtn = text(el("button", "card-action-btn"), "Renumber figures");
      renumberBtn.type = "button";
      renumberBtn.title = "Swap or shift figure numbers across all data-updates";
      renumberBtn.addEventListener("click", () => openRenumberModal(project));
      dataBtnRow.append(renumberBtn);

      const archiveBtn = text(el("button", "card-action-btn"), "📦 Archive");
      archiveBtn.type = "button";
      archiveBtn.title = "View archived data files (restore-able)";
      archiveBtn.addEventListener("click", () => openArchiveModal(project));
      dataBtnRow.append(archiveBtn);

      const meetingBtn = text(el("button", "card-action-btn add-meeting-btn"), "+ Meeting");
      meetingBtn.type = "button";
      meetingBtn.title = "Schedule a new meeting (ICS + macOS Calendar)";
      meetingBtn.addEventListener("click", () => openMeetingModal(project));
      dataBtnRow.append(meetingBtn);

      const meetingsListBtn = text(el("button", "card-action-btn"), "Meetings");
      meetingsListBtn.type = "button";
      meetingsListBtn.title = "View all meetings for this project";
      meetingsListBtn.addEventListener("click", () => openMeetingsListModal(project));
      dataBtnRow.append(meetingsListBtn);

      const syncDataBtn = text(el("button", "card-action-btn sync-btn"), "🤖 Sync data");
      syncDataBtn.type = "button";
      syncDataBtn.title = "Launch local LLM to propose figure-plan / Decision_Log updates from recent data-updates";
      syncDataBtn.addEventListener("click", () => launchLocalSync(project, "local-data-sync"));
      dataBtnRow.append(syncDataBtn);

      const syncMeetBtn = text(el("button", "card-action-btn sync-btn"), "🤖 Sync meetings");
      syncMeetBtn.type = "button";
      syncMeetBtn.title = "Launch local LLM to propose updates from recent meeting notes";
      syncMeetBtn.addEventListener("click", () => launchLocalSync(project, "local-meeting-sync"));
      dataBtnRow.append(syncMeetBtn);

      const proposalsBtn = text(el("button", "card-action-btn"), "Proposals");
      proposalsBtn.type = "button";
      proposalsBtn.title = "Review and apply LLM sync proposals";
      proposalsBtn.addEventListener("click", () => openProposalsModal(project));
      dataBtnRow.append(proposalsBtn);

      card.append(dataBtnRow);

      const badge = buildManagerBadge(project);
      card.classList.add("project-card--with-manager");
      card.append(badge);
    });
  })();

  /* ──────────────────────────────────────────────────────────────────
     COUNT-CHIP FILE LIST POPUP
     ────────────────────────────────────────────────────────────────── */

  async function openBucketFiles(project, bucketKey, label) {
    const overlay = makeOverlay("bucket-files", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal bucket-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `${label} — ${project.title || project.slug}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    const status = el("p", "manager-editor-status", "Loading...");
    modal.append(status);
    const listWrap = el("div", "bucket-file-list");
    modal.append(listWrap);

    document.body.append(overlay);
    try {
      const out = await callApi("list-bucket-files", { bucket: bucketKey }, project.slug);
      const result = JSON.parse(out.stdout);
      status.textContent = result.items.length
        ? `${result.items.length} item${result.items.length === 1 ? "" : "s"}`
        : "No files yet for this bucket.";
      result.items.forEach((it) => {
        const row = el("div", "bucket-file-row");
        const icon = el("span", "bucket-file-icon", it.kind === "dir" ? "📁" : "📄");
        const main = el("button", "bucket-file-main bucket-file-open");
        main.type = "button";
        main.append(text(el("strong"), it.name));
        const metaLine = it.kind === "dir"
          ? `${it.file_count} files · ${it.mtime}`
          : (it.mtime || "");
        main.append(text(el("span", "bucket-file-meta"), metaLine));
        main.addEventListener("click", async () => {
          main.disabled = true;
          try { await callApi("open-relative-path", { rel_path: it.rel_path }); }
          catch (err) { alert("Open failed: " + err.message); main.disabled = false; }
        });
        const right = el("div", "bucket-file-right");
        const path = el("code", "bucket-file-path", it.rel_path);
        right.append(path);
        if (bucketKey === "data_updates") {
          const reassignBtn = text(el("button", "bucket-file-reassign"), "Reassign…");
          reassignBtn.type = "button";
          reassignBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            openReassignModal(project, it.rel_path, it.name);
          });
          right.append(reassignBtn);
        }
        row.append(icon, main, right);
        listWrap.append(row);
      });
    } catch (err) {
      status.textContent = "Failed to load: " + err.message;
    }
  }

  function openReassignModal(project, updateRelPath, updateName) {
    const overlay = makeOverlay("reassign-modal", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `Reassign — ${updateName}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    modal.append(text(el("p", "admin-help"),
      "Change the figure/panel assignment for this data update. The actual data file in LLM_project_manager/ will be renamed to match the new tag, and the change will be appended to CHANGELOG.md."));

    const fields = el("div", "du-fields-wrap");
    function fld(label, ph) {
      const w = el("label", "du-field");
      w.append(text(el("span", "du-field-label"), label));
      const i = document.createElement("input");
      i.type = "text"; i.placeholder = ph || "";
      w.append(i);
      return { wrap: w, input: i };
    }
    const figF = fld("New figure (blank = unspecified)", "Fig 2");
    const panelF = fld("New panel (optional)", "A");
    const reasonF = fld("Reason (recorded in CHANGELOG)", "merged with new control panel");
    [figF, panelF, reasonF].forEach(({ wrap }) => fields.append(wrap));
    modal.append(fields);

    const statusLine = el("p", "manager-editor-status");
    modal.append(statusLine);

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const apply = text(el("button", "manager-editor-save"), "Reassign");
    apply.type = "button";
    apply.addEventListener("click", async () => {
      const newFig = figF.input.value.trim();
      if (!newFig && !confirm("No figure specified — will tag as 'unspecified'. Continue?")) return;
      apply.disabled = true;
      statusLine.textContent = "Reassigning...";
      try {
        const out = await callApi("reassign-data-update", {
          update_rel_path: updateRelPath,
          new_figure: newFig,
          new_panel: panelF.input.value.trim(),
          reason: reasonF.input.value.trim(),
        }, project.slug);
        let info = {};
        try { info = JSON.parse(out.stdout); } catch {}
        statusLine.textContent = "Reassigned." + (info.renamed ? " File renamed." : "");
        setTimeout(() => { overlay.remove(); window.location.reload(); }, 600);
      } catch (err) {
        statusLine.textContent = "Reassign failed: " + err.message;
        apply.disabled = false;
      }
    });
    actions.append(cancel, apply);
    modal.append(actions);
    document.body.append(overlay);
    figF.input.focus();
  }

  /* ──────────────────────────────────────────────────────────────────
     ADD DATA UPDATE MODAL
     ────────────────────────────────────────────────────────────────── */

  const STATUS_OPTIONS = [
    "planned", "in_progress", "data_collected", "analyzed",
    "drafted", "complete", "dropped",
  ];

  async function openDataUpdateModal(project) {
    const overlay = makeOverlay("data-update-modal", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal data-update-modal");
    overlay.append(modal);

    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `+ Data update — ${project.title || project.slug}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    // Mode selector
    const modeRow = el("div", "du-mode-row");
    const modeNew = el("label", "du-mode-opt");
    const modeNewIn = document.createElement("input");
    modeNewIn.type = "radio"; modeNewIn.name = "du-mode"; modeNewIn.value = "new"; modeNewIn.checked = true;
    modeNew.append(modeNewIn, text(el("span"), "New data (new figure/panel)"));
    const modeExisting = el("label", "du-mode-opt");
    const modeExistingIn = document.createElement("input");
    modeExistingIn.type = "radio"; modeExistingIn.name = "du-mode"; modeExistingIn.value = "existing";
    modeExisting.append(modeExistingIn, text(el("span"), "Adding to existing data"));
    modeRow.append(modeNew, modeExisting);
    modal.append(modeRow);

    // Figure picker (existing) — hidden by default
    const pickerWrap = el("div", "du-picker-wrap");
    pickerWrap.style.display = "none";
    const pickerLabel = text(el("label", "du-field-label"), "Pick a figure/panel:");
    const pickerSelect = document.createElement("select");
    pickerSelect.className = "du-picker-select";
    pickerWrap.append(pickerLabel, pickerSelect);
    modal.append(pickerWrap);

    // Form fields
    const fieldsWrap = el("div", "du-fields-wrap");
    function field(label, placeholder, multiline) {
      const wrap = el("label", "du-field");
      wrap.append(text(el("span", "du-field-label"), label));
      const input = multiline ? document.createElement("textarea") : document.createElement("input");
      input.placeholder = placeholder || "";
      if (multiline) input.rows = 3;
      else input.type = "text";
      wrap.append(input);
      return { wrap, input };
    }
    const figureF = field("Figure (e.g., Fig 2)", "Fig 2");
    const panelF = field("Panel (optional, e.g., A)", "A");
    const statusF = (function () {
      const wrap = el("label", "du-field");
      wrap.append(text(el("span", "du-field-label"), "Status update"));
      const sel = document.createElement("select");
      const blank = document.createElement("option");
      blank.value = ""; blank.textContent = "(no change)";
      sel.append(blank);
      STATUS_OPTIONS.forEach((s) => {
        const o = document.createElement("option");
        o.value = s; o.textContent = s;
        sel.append(o);
      });
      wrap.append(sel);
      return { wrap, input: sel };
    })();
    // Brief description (required — drives the canonical filename)
    const briefF = field("Brief description (3–6 words — used in the filename)", "e.g., wt-vs-ko-baseline");
    // Source file picker (replaces text path input)
    const pathWrap = el("div", "du-field");
    pathWrap.append(text(el("span", "du-field-label"), "Data file (moved into LLM_project_manager/)"));
    const pathRow = el("div", "du-path-row");
    const pathField = document.createElement("input");
    pathField.type = "text";
    pathField.placeholder = project.gdrive_path
      ? `${project.gdrive_path.replace(/\/$/, "")}/LLM_project_manager/...`
      : "(Set Google Drive path first — see notice below)";
    pathField.readOnly = true;
    const browseBtn = text(el("button", "du-browse-btn"), "📂 Browse…");
    browseBtn.type = "button";
    const clearBtn = text(el("button", "du-clear-btn"), "Clear");
    clearBtn.type = "button";
    clearBtn.addEventListener("click", () => { pathField.value = ""; });
    pathRow.append(pathField, browseBtn, clearBtn);
    pathWrap.append(pathRow);
    const pathF = { wrap: pathWrap, input: pathField };
    // Inline gdrive_path setup (shown only when missing)
    if (!project.gdrive_path) {
      const setupNotice = el("div", "du-gdrive-notice");
      setupNotice.append(text(el("span"), "⚠️ No Google Drive path configured for this project. "));
      const setupBtn = text(el("button", "du-setup-btn"), "Set Google Drive path…");
      setupBtn.type = "button";
      setupBtn.addEventListener("click", async () => {
        setupBtn.disabled = true;
        try {
          const out = await callApi("pick-data-path", { kind: "folder" });
          const info = JSON.parse(out.stdout);
          if (info.cancelled) { setupBtn.disabled = false; return; }
          await callApi("set-project-gdrive-path", { gdrive_path: info.path }, project.slug);
          setupNotice.remove();
          project.gdrive_path = info.path;
          pathField.placeholder = `${info.path.replace(/\/$/, "")}/LLM_project_manager/...`;
        } catch (err) {
          alert("Setup failed: " + err.message);
          setupBtn.disabled = false;
        }
      });
      setupNotice.append(setupBtn);
      pathWrap.append(setupNotice);
    }
    browseBtn.addEventListener("click", async () => {
      browseBtn.disabled = true;
      try {
        const out = await callApi("pick-data-path", { kind: "file" }, project.slug);
        const info = JSON.parse(out.stdout);
        if (!info.cancelled) pathField.value = info.path;
      } catch (err) {
        alert("Picker failed: " + err.message);
      } finally {
        browseBtn.disabled = false;
      }
    });

    const legendF = field("Brief legend (1–3 sentences)", "What this panel shows", true);
    const changedF = field("What changed in this update", "New data / analysis / interpretation", true);
    const interpF = field("Current interpretation", "What the data support / do not support", true);
    const concernsF = field("Concerns or failure modes", "Technical issues, alt explanations, reviewer concerns", true);
    const nextF = field("Next step", "Concrete next action, or 'None'", true);

    [figureF, panelF, briefF, pathF, statusF, legendF, changedF, interpF, concernsF, nextF]
      .forEach(({ wrap }) => fieldsWrap.append(wrap));
    modal.append(fieldsWrap);

    const statusLine = el("p", "manager-editor-status");
    modal.append(statusLine);

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const save = text(el("button", "manager-editor-save"), "Save data update");
    save.type = "button";
    actions.append(cancel, save);
    modal.append(actions);

    // Fetch figures / existing updates for "existing" mode
    let figuresCache = null;
    let selectedExistingUpdateRel = "";
    async function ensureFigures() {
      if (figuresCache) return figuresCache;
      const out = await callApi("list-project-figures", {}, project.slug);
      figuresCache = JSON.parse(out.stdout);
      return figuresCache;
    }

    async function populatePicker() {
      pickerSelect.innerHTML = "";
      const blank = document.createElement("option");
      blank.value = ""; blank.textContent = "— select an existing data update to add n+ data —";
      pickerSelect.append(blank);
      try {
        const info = await ensureFigures();
        if (info.gdrive_path && !pathF.input.placeholder.includes(info.gdrive_path)) {
          pathF.input.placeholder = `${info.gdrive_path.replace(/\/$/, "")}/LLM_project_manager/...`;
        }
        const updates = info.updates || [];
        if (updates.length === 0) {
          const opt = document.createElement("option");
          opt.value = ""; opt.disabled = true;
          opt.textContent = "(no existing data-updates yet — switch to 'New data')";
          pickerSelect.append(opt);
          return;
        }
        updates.forEach((u, i) => {
          const fp = (u.figure || "") + (u.panel ? " " + u.panel : "") || "(unspecified)";
          const opt = document.createElement("option");
          opt.value = String(i);
          opt.dataset.rel = u.rel_path;
          opt.dataset.figure = u.figure || "";
          opt.dataset.panel = u.panel || "";
          opt.textContent = `${u.name}  —  ${fp}${u.status ? " [" + u.status + "]" : ""}`;
          pickerSelect.append(opt);
        });
      } catch (err) {
        const opt = document.createElement("option");
        opt.disabled = true; opt.textContent = "Failed to load: " + err.message;
        pickerSelect.append(opt);
      }
    }

    pickerSelect.addEventListener("change", () => {
      const opt = pickerSelect.selectedOptions[0];
      if (!opt) { selectedExistingUpdateRel = ""; return; }
      selectedExistingUpdateRel = opt.dataset.rel || "";
      figureF.input.value = opt.dataset.figure || "";
      panelF.input.value = opt.dataset.panel || "";
    });

    modeNewIn.addEventListener("change", () => {
      pickerWrap.style.display = "none";
    });
    modeExistingIn.addEventListener("change", async () => {
      pickerWrap.style.display = "block";
      await populatePicker();
    });

    save.addEventListener("click", async () => {
      const figure = figureF.input.value.trim();
      const brief = briefF.input.value.trim();
      const isExisting = modeExistingIn.checked;
      if (!brief) { statusLine.textContent = "Brief description is required."; return; }
      if (!figure && !isExisting) {
        // figure can be empty → tagged unspecified; warn but allow
        if (!confirm("No figure assigned — file will be tagged 'unspecified'. Continue?")) return;
      }
      if (isExisting && !selectedExistingUpdateRel) {
        statusLine.textContent = "Pick an existing data-update from the dropdown.";
        return;
      }
      save.disabled = true;
      statusLine.textContent = "Saving...";
      try {
        const out = await callApi("add-data-update", {
          mode: isExisting ? "existing" : "new",
          existing_update_rel_path: selectedExistingUpdateRel,
          figure,
          panel: panelF.input.value.trim(),
          status: statusF.input.value,
          brief_description: brief,
          source_file: pathF.input.value.trim(),
          legend: legendF.input.value.trim(),
          what_changed: changedF.input.value.trim(),
          interpretation: interpF.input.value.trim(),
          concerns: concernsF.input.value.trim(),
          next_step: nextF.input.value.trim(),
        }, project.slug);
        let info = {};
        try { info = JSON.parse(out.stdout); } catch {}
        statusLine.textContent = "Saved → " + (info.rel_path || "data-updates/")
          + (info.archived_zip ? " (previous data archived)" : "")
          + (info.figure_plan_status_updated ? " (figure-plan.md row updated)" : "");
        setTimeout(() => { overlay.remove(); window.location.reload(); }, 700);
      } catch (err) {
        statusLine.textContent = "Save failed: " + err.message;
        save.disabled = false;
      }
    });

    document.body.append(overlay);
    figureF.input.focus();
  }

  /* ──────────────────────────────────────────────────────────────────
     RENUMBER FIGURES MODAL
     ────────────────────────────────────────────────────────────────── */

  function openRenumberModal(project) {
    const overlay = makeOverlay("renumber-modal", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `Renumber figures — ${project.title || project.slug}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    modal.append(text(el("p", "admin-help"),
      "Map old figure labels to new labels. Every data-update with a matching `figure` will be updated, " +
      "its data file renamed, figure-plan.md row(s) replaced, and the change logged in CHANGELOG.md."));

    const rowsWrap = el("div", "renumber-rows-wrap");
    modal.append(rowsWrap);
    const rows = [{ from: "", to: "" }];
    function renderRows() {
      rowsWrap.innerHTML = "";
      rows.forEach((r, i) => {
        const row = el("div", "renumber-row");
        const fromIn = document.createElement("input");
        fromIn.type = "text"; fromIn.placeholder = "Fig 1"; fromIn.value = r.from;
        fromIn.addEventListener("input", () => { r.from = fromIn.value; });
        const arrow = el("span", "renumber-arrow", "→");
        const toIn = document.createElement("input");
        toIn.type = "text"; toIn.placeholder = "Fig 2"; toIn.value = r.to;
        toIn.addEventListener("input", () => { r.to = toIn.value; });
        const del = text(el("button", "manager-editor-del"), "×");
        del.type = "button";
        del.addEventListener("click", () => {
          rows.splice(i, 1);
          if (rows.length === 0) rows.push({ from: "", to: "" });
          renderRows();
        });
        row.append(fromIn, arrow, toIn, del);
        rowsWrap.append(row);
      });
    }
    renderRows();
    const addRow = text(el("button", "manager-editor-add"), "+ Add mapping");
    addRow.type = "button";
    addRow.addEventListener("click", () => { rows.push({ from: "", to: "" }); renderRows(); });
    modal.append(addRow);

    const reasonWrap = el("label", "du-field");
    reasonWrap.append(text(el("span", "du-field-label"), "Reason (CHANGELOG)"));
    const reasonIn = document.createElement("input");
    reasonIn.type = "text";
    reasonIn.placeholder = "e.g., reordered figures for clarity";
    reasonWrap.append(reasonIn);
    modal.append(reasonWrap);

    const statusLine = el("p", "manager-editor-status");
    modal.append(statusLine);

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const apply = text(el("button", "manager-editor-save"), "Apply renumber");
    apply.type = "button";
    apply.addEventListener("click", async () => {
      const mapping = {};
      for (const r of rows) {
        const from = (r.from || "").trim();
        const to = (r.to || "").trim();
        if (!from && !to) continue;
        if (!from || !to) { statusLine.textContent = "Each row needs both from and to."; return; }
        if (from === to) { statusLine.textContent = "Skipping self-mapping is fine; remove it."; return; }
        mapping[from] = to;
      }
      if (Object.keys(mapping).length === 0) { statusLine.textContent = "Add at least one mapping."; return; }
      apply.disabled = true;
      statusLine.textContent = "Applying...";
      try {
        const out = await callApi("renumber-figures", {
          mapping, reason: reasonIn.value.trim(),
        }, project.slug);
        const info = JSON.parse(out.stdout);
        statusLine.textContent = `Updated ${info.data_updates_changed} data-update(s) + ${info.figure_plan_rows_changed} figure-plan row(s).`;
        setTimeout(() => { overlay.remove(); window.location.reload(); }, 800);
      } catch (err) {
        statusLine.textContent = "Renumber failed: " + err.message;
        apply.disabled = false;
      }
    });
    actions.append(cancel, apply);
    modal.append(actions);
    document.body.append(overlay);
  }

  /* ──────────────────────────────────────────────────────────────────
     ARCHIVE VIEWER
     ────────────────────────────────────────────────────────────────── */

  async function openArchiveModal(project) {
    const overlay = makeOverlay("archive-modal", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal bucket-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `Archive — ${project.title || project.slug}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    const status = el("p", "manager-editor-status", "Loading...");
    modal.append(status);
    const listWrap = el("div", "bucket-file-list");
    modal.append(listWrap);
    document.body.append(overlay);

    try {
      const out = await callApi("list-archive", {}, project.slug);
      const info = JSON.parse(out.stdout);
      if (!info.configured) {
        status.textContent = "Set Google Drive path first (use + Data update modal).";
        return;
      }
      const items = info.items || [];
      status.textContent = items.length
        ? `${items.length} archived zip${items.length === 1 ? "" : "s"}`
        : "No archives yet.";
      items.forEach((it) => {
        const row = el("div", "bucket-file-row");
        const icon = el("span", "bucket-file-icon", "🗜");
        const main = el("div", "bucket-file-open archive-main");
        main.append(text(el("strong"), it.name));
        main.append(text(el("span", "bucket-file-meta"),
          `${(it.size / 1024).toFixed(1)} KB · ${it.mtime}`));
        const right = el("div", "bucket-file-right");
        right.append(text(el("code", "bucket-file-path"), it.abs_path));
        const restoreBtn = text(el("button", "bucket-file-reassign"), "Restore");
        restoreBtn.type = "button";
        restoreBtn.addEventListener("click", async () => {
          restoreBtn.disabled = true;
          try {
            const r = await callApi("restore-archive", { zip_path: it.abs_path }, project.slug);
            const ri = JSON.parse(r.stdout);
            alert(`Restored as: ${ri.name}`);
          } catch (err) {
            alert("Restore failed: " + err.message);
            restoreBtn.disabled = false;
          }
        });
        right.append(restoreBtn);
        row.append(icon, main, right);
        listWrap.append(row);
      });
    } catch (err) {
      status.textContent = "Failed to load: " + err.message;
    }
  }

  /* ──────────────────────────────────────────────────────────────────
     MEETING MODALS
     ────────────────────────────────────────────────────────────────── */

  async function fetchMeetingTypes() {
    const out = await callApi("list-meeting-types", {});
    return JSON.parse(out.stdout).types || [];
  }

  async function openMeetingModal(project) {
    const overlay = makeOverlay("meeting-modal", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal data-update-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `+ Meeting — ${project.title || project.slug}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    const fields = el("div", "du-fields-wrap");
    function fld(label, ph, multiline) {
      const w = el("label", "du-field");
      w.append(text(el("span", "du-field-label"), label));
      const i = multiline ? document.createElement("textarea") : document.createElement("input");
      if (multiline) i.rows = 3;
      else i.type = "text";
      i.placeholder = ph || "";
      w.append(i);
      return { wrap: w, input: i };
    }

    // Type dropdown + add new
    const typeWrap = el("label", "du-field");
    typeWrap.append(text(el("span", "du-field-label"), "Meeting type"));
    const typeRow = el("div", "du-path-row");
    const typeSel = document.createElement("select");
    typeSel.className = "du-picker-select";
    const addTypeBtn = text(el("button", "du-browse-btn"), "+ New type");
    addTypeBtn.type = "button";
    typeRow.style.gridTemplateColumns = "1fr auto";
    typeRow.append(typeSel, addTypeBtn);
    typeWrap.append(typeRow);
    fields.append(typeWrap);

    async function reloadTypes(selectName) {
      typeSel.innerHTML = "";
      const types = await fetchMeetingTypes();
      types.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t; opt.textContent = t;
        if (t === selectName) opt.selected = true;
        typeSel.append(opt);
      });
    }
    reloadTypes();
    addTypeBtn.addEventListener("click", async () => {
      const name = prompt("New meeting type (letters/digits/_-, 2–32 chars):", "");
      if (!name) return;
      try {
        await callApi("add-meeting-type", { name: name.trim() });
        await reloadTypes(name.trim());
      } catch (err) { alert("Failed: " + err.message); }
    });

    const titleF = fld("Title", "e.g., Cerebellar circuit progress review");
    const whenF = (function () {
      const w = el("label", "du-field");
      w.append(text(el("span", "du-field-label"), "When (local time)"));
      const i = document.createElement("input");
      i.type = "datetime-local";
      const def = new Date();
      def.setMinutes(0, 0, 0);
      def.setHours(def.getHours() + 1);
      i.value = def.toISOString().slice(0, 16);
      w.append(i);
      return { wrap: w, input: i };
    })();
    const durF = (function () {
      const w = el("label", "du-field");
      w.append(text(el("span", "du-field-label"), "Duration (minutes)"));
      const i = document.createElement("input");
      i.type = "number"; i.min = "5"; i.max = "480"; i.step = "5"; i.value = "60";
      w.append(i);
      return { wrap: w, input: i };
    })();
    const locF = fld("Location / Zoom link (optional)", "https://zoom.us/j/...");
    const agendaF = fld("Agenda", "What this meeting needs to cover", true);
    [titleF, whenF, durF, locF, agendaF].forEach(({ wrap }) => fields.append(wrap));

    // Attendees from project managers
    const attWrap = el("div", "du-field");
    attWrap.append(text(el("span", "du-field-label"), "Attendees"));
    const attList = el("div", "meeting-attendee-list");
    (project.managers || []).forEach((m) => {
      const row = el("label", "manager-pop-row");
      const cb = document.createElement("input");
      cb.type = "checkbox"; cb.checked = true;
      cb.dataset.name = m.name || ""; cb.dataset.email = m.email || "";
      row.append(cb, text(el("span", "manager-pop-name"), m.name || m.email || "?"));
      row.append(text(el("span", "manager-pop-email"), m.email || "(no email)"));
      attList.append(row);
    });
    attWrap.append(attList);
    // Extra attendee inputs
    const extras = [];
    const extraWrap = el("div", "meeting-extra-attendees");
    function renderExtras() {
      extraWrap.innerHTML = "";
      extras.forEach((e, i) => {
        const row = el("div", "renumber-row");
        const n = document.createElement("input");
        n.type = "text"; n.placeholder = "Name"; n.value = e.name;
        n.addEventListener("input", () => { e.name = n.value; });
        const em = document.createElement("input");
        em.type = "email"; em.placeholder = "email@example.com"; em.value = e.email;
        em.addEventListener("input", () => { e.email = em.value; });
        const del = text(el("button", "manager-editor-del"), "×");
        del.type = "button";
        del.addEventListener("click", () => { extras.splice(i, 1); renderExtras(); });
        row.append(n, em, del);
        extraWrap.append(row);
      });
    }
    const addExtra = text(el("button", "manager-editor-add"), "+ Add attendee");
    addExtra.type = "button";
    addExtra.addEventListener("click", () => { extras.push({ name: "", email: "" }); renderExtras(); });
    attWrap.append(extraWrap, addExtra);
    fields.append(attWrap);

    // Options row
    const optsWrap = el("div", "du-mode-row");
    const calOpt = el("label", "du-mode-opt");
    const calIn = document.createElement("input");
    calIn.type = "checkbox"; calIn.checked = true;
    calOpt.append(calIn, text(el("span"), "Add to macOS Calendar"));
    const mailOpt = el("label", "du-mode-opt");
    const mailIn = document.createElement("input");
    mailIn.type = "checkbox"; mailIn.checked = true;
    mailOpt.append(mailIn, text(el("span"), "Open mail app with invite info"));
    optsWrap.append(calOpt, mailOpt);
    fields.append(optsWrap);

    modal.append(fields);

    const statusLine = el("p", "manager-editor-status");
    modal.append(statusLine);

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const save = text(el("button", "manager-editor-save"), "Create meeting");
    save.type = "button";
    save.addEventListener("click", async () => {
      const title = titleF.input.value.trim();
      const when = whenF.input.value;
      if (!when) { statusLine.textContent = "Pick a date/time."; return; }
      const attendees = [];
      attList.querySelectorAll("input[type=checkbox]").forEach((cb) => {
        if (cb.checked) attendees.push({ name: cb.dataset.name, email: cb.dataset.email });
      });
      extras.forEach((e) => {
        if ((e.name || "").trim() || (e.email || "").trim()) attendees.push(e);
      });
      save.disabled = true;
      statusLine.textContent = "Creating...";
      try {
        const out = await callApi("create-meeting", {
          type: typeSel.value,
          title,
          datetime: when,
          duration_minutes: parseInt(durF.input.value || "60", 10),
          location: locF.input.value.trim(),
          agenda: agendaF.input.value.trim(),
          attendees,
          add_to_calendar: calIn.checked,
        }, project.slug);
        const info = JSON.parse(out.stdout);
        let note = `Saved: ${info.rel_path}`;
        if (info.calendar_added) note += "  ·  Calendar.app updated";
        else if (calIn.checked) note += `  ·  Calendar: ${info.calendar_message}`;
        statusLine.textContent = note;
        if (mailIn.checked && info.mailto_url) {
          window.location.href = info.mailto_url;
        }
        // Also reveal the .ics so user can drag it into mail app for attachment
        try { await callApi("open-relative-path", { rel_path: info.ics_rel_path }); } catch {}
        setTimeout(() => { overlay.remove(); window.location.reload(); }, 1000);
      } catch (err) {
        statusLine.textContent = "Create failed: " + err.message;
        save.disabled = false;
      }
    });
    actions.append(cancel, save);
    modal.append(actions);
    document.body.append(overlay);
    titleF.input.focus();
  }

  async function openMeetingsListModal(project) {
    const overlay = makeOverlay("meetings-list", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal bucket-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `Meetings — ${project.title || project.slug}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    const status = el("p", "manager-editor-status", "Loading...");
    modal.append(status);
    const listWrap = el("div", "bucket-file-list");
    modal.append(listWrap);
    document.body.append(overlay);

    try {
      const out = await callApi("list-meetings", {}, project.slug);
      const info = JSON.parse(out.stdout);
      const items = info.items || [];
      status.textContent = items.length
        ? `${items.length} meeting${items.length === 1 ? "" : "s"}`
        : "No meetings yet.";
      items.forEach((it) => {
        const row = el("div", "bucket-file-row meeting-row");
        const icon = el("span", "bucket-file-icon", "🗓");
        const main = el("button", "bucket-file-open");
        main.type = "button";
        main.append(text(el("strong"), `[${it.type}] ${it.title}`));
        const when = it.datetime ? it.datetime.replace("T", " ").slice(0, 16) : "";
        const attCount = (it.attendees || []).length;
        main.append(text(el("span", "bucket-file-meta"),
          `${when} · ${it.duration_minutes} min · ${attCount} attendee${attCount === 1 ? "" : "s"}${it.location ? " · " + it.location : ""}`));
        main.addEventListener("click", async () => {
          main.disabled = true;
          try { await callApi("open-relative-path", { rel_path: it.rel_path }); }
          catch (err) { alert("Open failed: " + err.message); main.disabled = false; }
        });
        const right = el("div", "bucket-file-right");
        const noteBtn = text(el("button", "bucket-file-reassign"), "+ Note");
        noteBtn.type = "button";
        noteBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          openMeetingNoteModal(project, it);
        });
        right.append(noteBtn);
        if (it.ics_rel_path) {
          const icsBtn = text(el("button", "bucket-file-reassign"), ".ics");
          icsBtn.type = "button";
          icsBtn.title = "Open ICS (adds to Calendar.app)";
          icsBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            try { await callApi("open-relative-path", { rel_path: it.ics_rel_path }); }
            catch (err) { alert("Open failed: " + err.message); }
          });
          right.append(icsBtn);
        }
        row.append(icon, main, right);
        listWrap.append(row);
      });
    } catch (err) {
      status.textContent = "Failed: " + err.message;
    }
  }

  /* ──────────────────────────────────────────────────────────────────
     PHASE 3: LLM SYNC LAUNCH + PROPOSAL REVIEW
     ────────────────────────────────────────────────────────────────── */

  async function launchLocalSync(project, actionId) {
    try {
      const out = await callApi(actionId, {}, project.slug);
      alert((out.stdout || "").trim() + "\n\nAfter the local agent finishes, click 'Proposals' to review and apply.");
    } catch (err) {
      alert("Launch failed: " + err.message);
    }
  }

  async function openProposalsModal(project) {
    const overlay = makeOverlay("proposals-modal", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal bucket-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `Sync proposals — ${project.title || project.slug}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    const status = el("p", "manager-editor-status", "Loading...");
    modal.append(status);
    const listWrap = el("div", "bucket-file-list");
    modal.append(listWrap);
    document.body.append(overlay);

    try {
      const out = await callApi("list-sync-proposals", {}, project.slug);
      const info = JSON.parse(out.stdout);
      const items = info.items || [];
      status.textContent = items.length
        ? `${items.length} proposal${items.length === 1 ? "" : "s"}`
        : "No proposals yet — run a 🤖 Sync first.";
      items.forEach((it) => {
        const card = el("div", "proposal-card");
        const ph = el("div", "proposal-head");
        ph.append(text(el("strong"), `${it.kind}  ·  ${it.name}`));
        ph.append(text(el("span", "bucket-file-meta"),
          `${it.action_count} action${it.action_count === 1 ? "" : "s"} · ${it.mtime}`));
        const openBtn = text(el("button", "bucket-file-reassign"), "Open file");
        openBtn.type = "button";
        openBtn.addEventListener("click", async () => {
          try { await callApi("open-relative-path", { rel_path: it.rel_path }); }
          catch (err) { alert("Open failed: " + err.message); }
        });
        ph.append(openBtn);
        card.append(ph);

        const actions = it.actions || [];
        if (!actions.length) {
          card.append(text(el("p", "admin-help"), "No JSON action items parsed. Open the file to inspect."));
        } else {
          const list = el("div", "proposal-items");
          const checks = [];
          actions.forEach((a) => {
            const row = el("label", "proposal-item");
            const cb = document.createElement("input");
            cb.type = "checkbox"; cb.checked = true;
            cb.dataset.id = a.id || "";
            checks.push(cb);
            const summary = el("div", "proposal-item-body");
            summary.append(text(el("strong"), `[${a.action || "?"}] ${a.id || ""}`));
            const detail = summarizeAction(a);
            summary.append(text(el("span", "bucket-file-meta"), detail));
            if (a.source_files && a.source_files.length) {
              const src = el("span", "proposal-sources",
                "source: " + a.source_files.join(", "));
              summary.append(src);
            }
            row.append(cb, summary);
            list.append(row);
          });
          card.append(list);
          const applyRow = el("div", "manager-editor-actions");
          const allBtn = text(el("button", "manager-editor-cancel"), "Toggle all");
          allBtn.type = "button";
          allBtn.addEventListener("click", () => {
            const anyOff = checks.some((c) => !c.checked);
            checks.forEach((c) => { c.checked = anyOff; });
          });
          const applyBtn = text(el("button", "manager-editor-save"), "Apply selected");
          applyBtn.type = "button";
          applyBtn.addEventListener("click", async () => {
            const ids = checks.filter((c) => c.checked).map((c) => c.dataset.id).filter(Boolean);
            if (!ids.length) { alert("Select at least one item."); return; }
            applyBtn.disabled = true;
            try {
              const r = await callApi("apply-sync-proposal", {
                proposal_rel_path: it.rel_path,
                selected_ids: ids,
              }, project.slug);
              const ri = JSON.parse(r.stdout);
              alert(`Applied:\n${(ri.applied || []).join("\n") || "(none)"}\n\nSkipped:\n${(ri.skipped || []).join("\n") || "(none)"}`);
              overlay.remove();
              window.location.reload();
            } catch (err) {
              alert("Apply failed: " + err.message);
              applyBtn.disabled = false;
            }
          });
          applyRow.append(allBtn, applyBtn);
          card.append(applyRow);
        }
        listWrap.append(card);
      });
    } catch (err) {
      status.textContent = "Failed: " + err.message;
    }
  }

  function summarizeAction(a) {
    const k = a.action;
    if (k === "figure_plan_status_update")
      return `${a.figure || ""}${a.panel ? " " + a.panel : ""}  status → ${a.new_status}.  ${a.reason || ""}`;
    if (k === "experiment_roadmap_status_update")
      return `experiment "${a.experiment || ""}" → ${a.new_status}.  ${a.reason || ""}`;
    if (k === "decision_log_append")
      return `Decision_Log: ${a.entry || ""}`;
    if (k === "figure_plan_add_row")
      return `add figure ${a.figure || ""}${a.panel ? " " + a.panel : ""}: ${a.claim || ""}`;
    if (k === "experiment_roadmap_add_row")
      return `add experiment: ${a.experiment || ""} — ${a.purpose || ""}`;
    if (k === "note")
      return `(note) ${a.text || ""}`;
    return JSON.stringify(a);
  }

  function openMeetingNoteModal(project, meeting) {
    const overlay = makeOverlay("meeting-note", "manager-editor-overlay");
    const modal = el("div", "manager-editor-modal");
    overlay.append(modal);
    const head = el("div", "manager-editor-head");
    head.append(text(el("h3"), `+ Note — ${meeting.title || meeting.name}`));
    const close = text(el("button", "manager-editor-close"), "×");
    close.type = "button";
    close.addEventListener("click", () => overlay.remove());
    head.append(close);
    modal.append(head);

    modal.append(text(el("p", "admin-help"),
      "Notes are appended to the meeting file as a new section (append-only history). " +
      "Use this to log discussion points; later you can run an LLM-driven sync (Phase 3) to propose updates to figure-plan and Decision_Log."));

    const noteWrap = el("label", "du-field");
    noteWrap.append(text(el("span", "du-field-label"), "Note (markdown ok)"));
    const noteIn = document.createElement("textarea");
    noteIn.rows = 8;
    noteIn.placeholder = "- Decision: drop Fig 3B (insufficient n)\n- Action: rerun control with new mouse line\n- ...";
    noteWrap.append(noteIn);
    modal.append(noteWrap);

    const authorWrap = el("label", "du-field");
    authorWrap.append(text(el("span", "du-field-label"), "Author (optional)"));
    const authorIn = document.createElement("input");
    authorIn.type = "text"; authorIn.placeholder = "Your name";
    authorWrap.append(authorIn);
    modal.append(authorWrap);

    const statusLine = el("p", "manager-editor-status");
    modal.append(statusLine);

    const actions = el("div", "manager-editor-actions");
    const cancel = text(el("button", "manager-editor-cancel"), "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", () => overlay.remove());
    const save = text(el("button", "manager-editor-save"), "Append note");
    save.type = "button";
    save.addEventListener("click", async () => {
      const note = noteIn.value.trim();
      if (!note) { statusLine.textContent = "Note is empty."; return; }
      save.disabled = true;
      statusLine.textContent = "Saving...";
      try {
        await callApi("add-meeting-note", {
          meeting_rel_path: meeting.rel_path,
          note,
          author: authorIn.value.trim(),
        }, project.slug);
        statusLine.textContent = "Saved.";
        setTimeout(() => overlay.remove(), 500);
      } catch (err) {
        statusLine.textContent = "Save failed: " + err.message;
        save.disabled = false;
      }
    });
    actions.append(cancel, save);
    modal.append(actions);
    document.body.append(overlay);
    noteIn.focus();
  }
})();
