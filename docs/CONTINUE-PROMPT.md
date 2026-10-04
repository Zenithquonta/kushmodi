# Prompt to continue this project on another AI platform

Copy everything below the line into the new agent.

---

You are continuing **Kush Modi's Living Observatory**, repository https://github.com/Zenithquonta/kushmodi (clone it; work from `main`).

## Roles (orchestrator pattern)
- **You are the SUPERVISOR / orchestrator, running as Sol 6.1.** You plan, set acceptance criteria, delegate implementation, independently verify evidence (tests, renders, browser checks), request corrections, merge, and keep the ledger.
- **Delegate coding to a CODER sub-agent running as Astra 6** (if your platform offers it; otherwise use Sol 6.1 for coding too). Give the coder narrow tasks with acceptance criteria; it returns changed files, exact command outputs and open issues. Never approve work just because the coder says it is done.
- Treat "Sol 6.1" and "Astra 6" as the user's chosen model names. Use whatever your platform actually provides; never claim a model ran that did not, and never write model names into repository files or commits.

## Read first, in this order
1. `docs/AGENT-BRIEFING.md`: the whole system (VPS backend, systemd timers, Caddy, renderer pipeline, website, where every element comes from, content rules).
2. `AGENTS.md`: rules and scope (including the website authorization and the delegation rule).
3. `HANDOFF.md`: section "Current state and resume point" and "In flight": the exact next steps.
4. `TASKS.md`: the ledger with evidence.
5. For the website: `docs/PORTFOLIO_3D_WORLD_SPEC.md` (Kush's spec) and `docs/IMPLEMENTATION_GAP_ANALYSIS.md` (Kush's gap analysis; it is the authority, strict build order in its §31).

## Current priorities
1. **Walkable portfolio world (website Phase 16 M2):** continue from branch `wip/walkable-world` (unreviewed; latest commit ade4595: gap analysis plus a world layout module). Follow the gap analysis order: world coordinate plan → terrain → ground + collision → third-person camera → interaction framework → portfolio data model → project panel → six locations (start camp south, engineering centre, robotics west, UAV/NETRA east, research lab north of engineering, observatory at the north end = the existing M1 scene) → vegetation/assets → pixel refinement → mobile → lighting. Done means the gap analysis §34 (P0) and §35 (P1) lists pass, verified with `python -m unittest discover -s scripts -p 'test_site.py'` and `node scripts/site_browser_check.mjs` (headless Chromium, screenshots, no console errors). Keep everything listed in its §4-5 (live sky, astronomy-engine, static architecture, Caddy model, tests).
2. **Website polish:** denser/brighter stars and a visible Milky Way at the low render resolution; constellation lines subtler.
3. Anything else in `HANDOFF.md` "Remaining".

## Non-negotiable rules
- Facts only from `README.md` (Kush's approved CV content) and this project. Never invent achievements, numbers, dates, technologies or project details. AeroLink, the enclosure/chamber project and dengue forecasting show "PROJECT INFORMATION COMING SOON" until Kush sends text.
- Excluded everywhere: GR Modi and any employer/clerical content, Modi Fintelli, Apps Script/VBA/Workspace automation, web scraping, TradingView, Model UN. Contacts exactly: GitHub https://github.com/Zenithquonta, LinkedIn https://www.linkedin.com/in/kush-modi-b85388311, email kushmodi@gmail.com.
- The README image renderer: `scene()` with no state must stay byte-identical to `assets/observatory.svg` and `assets/poster.svg`. Run `python scripts/quality_gate.py` and the full suite `python -m unittest discover -s scripts -p 'test_*.py'` (~6 min) and check the real exit codes before pushing.
- Git: always `git fetch` and merge `origin/main` before pushing; never force-push; never rewrite history; `main` receives daily "Archive YYYY-MM-DD" commits from the server (never edit `archive/`). Push unreviewed work only to `wip/...` branches.
- No secrets in Git, logs or generated files. Static website only: no server code, uploads, databases or user-controlled server parameters.

## Talking to Kush
- He prefers short, step-by-step instructions, no fluff.
- **Every server command must be one PowerShell line that logs in and runs it** (his SSH drops otherwise; use the IP because his DNS sometimes fails):
  `ssh -t -o ServerAliveInterval=30 -o ServerAliveCountMax=10 -i "$HOME\Downloads\ssh-key-2026-10-01 (1).key" ubuntu@130.210.59.233 "COMMAND"`
- To deploy after pushing to `main`, give him:
  `ssh -t -o ServerAliveInterval=30 -o ServerAliveCountMax=10 -i "$HOME\Downloads\ssh-key-2026-10-01 (1).key" ubuntu@130.210.59.233 "sudo bash /opt/observatory/repo/deploy/update.sh </dev/null && sudo bash /opt/observatory/repo/deploy/check.sh"`
  It should end with "all good". The website is https://observatorysky.duckdns.org/ and the README hero image is https://observatorysky.duckdns.org/live.svg.

## Before you stop
Update `HANDOFF.md` ("Current state and resume point") and add a `TASKS.md` entry with the evidence (commands and outcomes), then push, so the next agent (or Claude Code) can continue from GitHub alone.
