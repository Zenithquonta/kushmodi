# Agent briefing: Kush Modi's Living Observatory (profile image, live backend and 3D website)

Paste this whole file to a new agent as its starting prompt. It explains what exists, how each part works, where the
ideas come from, what is in progress and the rules. Read `AGENTS.md`, `HANDOFF.md` (section "Current state and resume
point") and `TASKS.md` (ledger) next; they are the authority if anything here is out of date.

## 1. What this project is

Repository `Zenithquonta/kushmodi` is the GitHub profile README of Kush Modi, a Computer Engineering (Integrated MBA
Tech) student in Mumbai whose first love is astronomy; aviation, robotics, LEGO, CAD and 3D printing come next. The
profile is a "Living Observatory": a pixel-art scene of Kush's telescope on a hill above Mumbai, with a maker shed, a
rover, a van and the city on the horizon, which is redrawn every 15 minutes from the real sky, the real Mumbai weather
and the season. A companion 3D website lets visitors walk through the same world as a portfolio.

Three products share one repository:

| Product | Where | Built by |
|---|---|---|
| Profile image (animated SVG, still PNG, JSON state) | README hero → https://observatorysky.duckdns.org/live.svg | `scripts/render_live.py` on the VPS every 15 min |
| Fallback art (GIF, poster) | `assets/observatory.gif`, `assets/observatory.svg`, `assets/poster.svg` | `scripts/build_animation.py` with no state (must stay byte-identical) |
| 3D portfolio website | https://observatorysky.duckdns.org/ | static files in `site/`, served by Caddy |

## 2. Backend: what runs where and how

**Host.** Oracle Cloud E2.1.Micro VM (1 GB RAM, Ubuntu 24.04), public host `observatorysky.duckdns.org` (DuckDNS). The
repository is cloned at `/opt/observatory/repo`, with a Python venv in `/opt/observatory/venv`. The VM has SSH keys
only (no password login), a firewall, HTTPS via Caddy's automatic certificates and no GitHub write token (except the
optional archive deploy key). There is no server-side application code, no request-driven rendering, no uploads and no
user-controlled parameters.

**systemd units (`deploy/`), all sandboxed (ProtectSystem=strict, private tmp, minimal write paths):**

| Unit | Schedule | What it does |
|---|---|---|
| `observatory-weather.timer/.service` | :12/:27/:42/:57 | `scripts/weather.py fetch`: Open-Meteo current conditions for Mumbai (keyless, CC BY 4.0); validates whitelisted fields and ranges, maps WMO codes to clear/partly-cloudy/overcast/fog/drizzle/rain/heavy-rain/thunderstorm; atomically writes `/var/lib/observatory/weather/current.json` and a 48 h `history.json`. The only online step besides satellites. |
| `observatory-satellites.timer/.service` | 03:07 and 15:07 | `scripts/satellites.py fetch`: CelesTrak TLEs for ISS 25544, Hubble 20580, Tiangong 48274; strict validation (69-char lines, checksums, catalogue number, epoch age); names only from the code's own table; writes `tle.json`. |
| `observatory-live.timer/.service` | every 15 min on the 1 GB VM (`OBSERVATORY_EVERY` drop-in) | `scripts/render_live.py --out /var/lib/observatory/live --weather … --satellites …`: builds the scene state, renders `live.svg` (animated, compact JPEG/WebP embeds ~1.8-2.4 MB), `live.png` (still) and `live.json` (state), validates all three and replaces them atomically. Disk cache under `CacheDirectory=observatory` makes renders ~3 s. |
| `observatory-archive.timer/.service` + `observatory-sync.service` | 21:10 IST | Optional (`install-archive.sh` + deploy key): daily archive frames committed to `archive/` on `main` as "Archive YYYY-MM-DD". Never edit `archive/` by hand. |

**Caddy (`deploy/Caddyfile.template`)** serves `/live.svg`, `/live.png`, `/live.json` (CORS for GitHub's image proxy,
short cache, CSP) and the website from `site/` through an allowlist (`/`, `/index.html`, `/favicon.svg`, `/css/*`,
`/js/*`, `/vendor/*`, `/data/*`) with a strict CSP; everything else is a 404. `deploy/install.sh` sets everything up;
`deploy/update.sh` fast-forwards to `main` after showing the diff, reinstalls units, re-renders the Caddyfile and runs
a render; `deploy/check.sh` reports service, weather, satellites and site health.

**GitHub side.** README hero uses `<picture>` (reduced motion → PNG). GitHub's camo proxy fetches the live SVG; a
caption credits Open-Meteo. CI (`.github/workflows/validate-profile.yml`, 8 min limit) runs the quality gate and the
whole unittest suite; it never deploys.

## 3. The renderer pipeline (`scripts/`)

`scene_state.py` turns a time into a JSON-able **SceneState**: date/time (Asia/Kolkata), season (six Indian seasons:
Vasanta, Grishma, Varsha, Sharad, Hemanta, Shishira) and environment values, astronomy from `astronomy-engine` (Sun,
Moon with phase, all seven planets with constellation, distance, RA/Dec, rise/set, oppositions, Jupiter's Galilean
moons, past-3 h trails), sun and moon altitude by hour, local sidereal time, sky events (meteor showers), the validated
weather observation, satellites, and a daily seed. `build_animation.py` → `lighting(state)` → `season(light, state)`
computes everything the layers need; `scene(t, animated, state)` writes the SVG. Animation is SMIL with a shared
`Track` keyframe helper so the SVG and the rasterised frames agree (24 s loop; every `dur` divides 24; `begin` ≤ 0).
`story.py` holds the observatory-log templates.

**Layers (live mode), bottom to top:** painted plate (`assets/observatory-background.png`) and day/golden/dry plates
from `build_day_art.py` → real night sky (Phase 17, in progress: Yale BSC5 stars, d3-celestial Milky Way and lines,
north-facing) → Sun/Moon/planets with trails → clouds and weather → lightning (thunderstorm only, ≤ 2 flashes/s, never
at t=0) → Mumbai skyline with lit windows → title → air traffic (airliner removed when weather grounds flights) →
advisory hologram or observatory log panel → meteors → portfolio objects (drone, ground station, tracker, PCB) and the
wind-swept meadow → shed light flicker (lamp, cyan tube, magenta neons through masks of their own glow; storm surges)
→ wall screen (SUN, MOON, PLANET, SAT TRACK pages, blueprint) → reactive rover robot → rain → workshop animations.

**Where the elements come from (inspiration):** the scene is based on Kush's own telescope photograph; the painted plate
was generated from it and approved by Kush. The shed contents (3D printer with a rocket, LEGO starship, CAD wireframe
on the screen), the rover and drone reflect his robotics, fabrication and UAV work (Team Darwin/IGVC rovers, NETRA,
the ESP32 micro drone). Star Trek and Star Wars inspire the ships. The Mumbai skyline grounds it in his city. Every
moving or textual element is driven by real data: the sky (astronomy-engine), the weather (Open-Meteo), satellites
(CelesTrak), the season calendar, and history (on-this-day space and aviation dates). Nothing is generated by AI at
runtime.

**Rules the renderer enforces and tests check:** the default scene is byte-identical to the committed assets;
SMIL-versus-raster parity at sampled times; seamless loops; photosensitivity limits; text fits its panels (pixel
font `FONT`, cell 3, measured widths); nothing overlaps protected painted regions; live SVG under ~2.8 MB; renders
stay cheap on the 1 GB VM.

## 4. The 3D website (`site/`)

Static ES modules, no build step: `site/index.html`, `site/css/site.css`, `site/js/` (`main`, `world`, `terrain`,
`sky`, `ephemeris`, `controls`, `hud`, `live`, `target`, `geom`), vendored and pinned `three.js 0.186.1` and
`astronomy-engine 2.1.19` (MIT, licences included), and data from `scripts/build_site_data.py` (BSC5 stars, Milky Way,
constellation lines; sources and licences in `site/data/SOURCES.md`). Milestone 1 (done): a pixel-rendered 3D hill
with the telescope, shed, rover, van, drone pad and Mumbai skyline; a real 360° live sky computed in the browser for
Mumbai (initial view north; planets and Moon with fading 3-hour trails); HUD from `/live.json` (time, what is up,
weather); telescope readout; WASD/mouse and touch controls; a text fallback; tests in `scripts/test_site.py` and a
headless-Chromium check `scripts/site_browser_check.mjs`.

**Target design:** `docs/PORTFOLIO_3D_WORLD_SPEC.md` (Kush's own spec): a walkable engineering outpost with locations
START/Profile camp, Engineering Workshop, Robotics Field, UAV/NETRA Test Field, Research Lab, Observatory;
third-person camera, collision, ground detection, interaction prompts, data-driven project panels, pixelated
rendering, performance and mobile rules. The gap analysis is `docs/IMPLEMENTATION_GAP_ANALYSIS.md`.

## 5. Content rules (strict)

- Source of truth for facts: the approved `README.md` sections and the Living Observatory itself. Never invent
  achievements, numbers, project names or credentials. Projects named in the spec but not described in the README
  (AeroLink, the enclosure/chamber project, dengue forecasting) need text from Kush before they get real content.
- Excluded everywhere: GR Modi and any employer/clerical content, Modi Fintelli, Apps Script/VBA/Workspace automation,
  web scraping, TradingView, Model UN.
- Contacts exactly as in the README: GitHub https://github.com/Zenithquonta, LinkedIn
  https://www.linkedin.com/in/kush-modi-b85388311, email kushmodi@gmail.com.
- No secrets in Git, logs or generated files. No AI model names in files or commits.

## 6. How work is done

Delegation per `AGENTS.md`: a supervisor plans, sets acceptance criteria and verifies (diff review, full test suite
with real exit codes, renders at 840 px, Chromium parity, deliberate mutation checks); a coder subagent implements in
a git worktree and reports. Push to the working branch and to `main` only after verification; always fetch and merge
`origin/main` first; never force-push. After pushing, the user runs `sudo bash /opt/observatory/repo/deploy/update.sh`
and `check.sh` on the VPS. Keep `HANDOFF.md` and `TASKS.md` current.

## 7. State at the time of writing (2026-10-02)

Done and live after `update.sh`: Phases 13-15e (live hero, render cache, weather, storms and grounded flights, shed
flicker, tracking screen, reactive robot, observatory log with the Saturn opposition of 4 Oct 2026 17:42 IST, all
planets and Galilean moons, ISS/Hubble/Tiangong passes) and website M1. In progress: Phase 17 real north-facing sky in
the profile image (polish pass) and the website's walkable portfolio world per the spec (gap analysis, then P0/P1).
Waiting on Kush: running `update.sh`/`check.sh` on the VPS, and short descriptions for spec-only projects.
