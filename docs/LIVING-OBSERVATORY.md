# Living Observatory — audit, amendments and phase status

The user's implementation plan ("Living Observatory — Implementation Plan", supplied in the 2026-10-01 session)
is the source of truth for intent. This file records the Phase 0 repository audit, the supervisor's
amendments that follow from measured facts, open decisions, and phase status.

## Phase 0 — repository audit (2026-10-01, HEAD 8c0e515)

### Repository map

| Path | Role | Reuse for Living Observatory |
| --- | --- | --- |
| `scripts/build_animation.py` | Renderer. `scene(t, animated)` → SVG; `layers(t)` = `celestial`, `traffic`, `sky_details` (incl. `lock_on`), `workshop`; `export_gif` rasterizes with FFmpeg/librsvg | **Core renderer is reused.** Already a pure function of time `t` within a 24 s loop |
| `Track` (in the builder) | Keyframed value: identical SMIL output and raster evaluation `at(t)` | Reuse for every time-driven parameter (lighting, sun/moon paths) |
| `ROUTES` / `traffic_state()` / `SKYLINE` / `TEXT_RECT` | Deterministic traffic with skyline/text/overlap guarantees | Reuse; daily seed can choose route variants |
| `scripts/test_scene.py` (34 tests) | Parity, loop, geometry, lock-on, warp, cube, moon tests | Extend; the generic SMIL-vs-raster test covers new animations automatically |
| `scripts/quality_gate.py` | README/SVG/GIF/atlas checks | Extend for live-SVG and archive validation (plan §42) |
| `scripts/build_cards.py`, `build_preview.py`, `build_manifest.py` | Cards, local preview, provenance | Unchanged |
| Chromium-vs-librsvg parity harness (supervisor scratch, method in `docs/ANIMATION-SPEC.md`) | Engine parity evidence | Reuse for live-SVG verification |
| `.github/workflows/validate-profile.yml` | Read-only CI | Keep |

### Asset inventory

| Asset | Content | Constraint found |
| --- | --- | --- |
| `assets/observatory-background.png` (1672×941) | **Night-only** painted plate: title text, Milky Way, mountains, distant city lights, trees, van, telescope on tripod, workshop | Telescope, skyline, trees and workshop are baked in one layer. No dome exists. Skyline is mountains + city lights, not Mumbai high-rises |
| `assets/space-sprites.png` | Galaxy, ringed planet, explorer, fighter, airliner, moon | Galaxy and ringed planet are stylized, not real-sky objects |
| `assets/approved-concept.png`, `reference-telescope.jpg`, `profile-picture.png` | Approved references | Keep unchanged |
| Hero outputs | `observatory.svg` (5.94 MB, 2 embedded PNGs), `observatory.gif` (840×473, 7.96 MB), `observatory-poster.png` (966 KB) | See size findings below |

### Flows

- **Build:** `build_cards` → `build_animation --gif --fps 10` → `build_preview` → `build_manifest` → `quality_gate` + unittest.
- **Deploy today:** none beyond git. README references relative files under `assets/`, served by GitHub via `raw.githubusercontent.com` (verified in T05; no camo proxy for relative images).
- **README image dependencies:** `observatory.gif`, `observatory-poster.png`, four `*-card.svg` + four `*-card-static.svg`.

## Supervisor amendments (from measured facts)

1. **Archive format.** A daily 840 px PNG is ~0.97 MB; 730 a year would add ~700 MB of git history. WebP at
   quality 85 is ~120 KB (~88 MB/year). Archive as WebP (or JPEG) unless the user prefers otherwise.
2. **Live SVG size.** The current SVG embeds the plate as PNG (5.9 MB). An SVG shown through `<img>` cannot
   load external resources, so rasters must stay embedded; re-encoding the plate as WebP drops it from 2.55 MB
   to ~0.46 MB. An external README image is proxied by GitHub's camo; its size/caching behaviour for the live
   URL must be verified with a real public URL before switching the README (spike in Phase 10).
3. **Astronomy dependency.** `astronomy-engine` (pure Python, ~155 KB wheel, no ephemeris download) is the
   smallest sufficient option; `skyfield` needs a separate ephemeris file.
4. **Art gaps that need deliberate new artwork** (plan §48–49; no runtime AI): day/golden-hour versions of the
   plate; the telescope as its own layer if it is to slew; a dome if one is wanted; Mumbai high-rise skyline
   layers. Until then Phase 3 can only tint the night plate.
5. **Portfolio objects** (drone station, telemetry console, research terminal, PCB station) are added only
   after the user confirms the underlying work (CV or direct statement). GR Modi is excluded.
6. **Real sky vs stylized objects.** The giant spiral galaxy and ringed planet are artistic, not real-sky.
   The plan's real star field and moon can coexist with them only as a deliberate art decision.
7. **VPS access.** The cloud session that builds this cannot reach the Oracle VPS. Deployment is delivered as
   a reviewed install script + systemd units that the user runs, or via an access path the user sets up.

## Decisions recorded (2026-10-01)

- PC session stopped; this session owns `scripts/build_animation.py` (user: yes).
- Phase 3 may tint the existing night plate until deliberate day/golden-hour art exists (user: yes).
- The earlier "main = README + images only" cleanup is cancelled; renderer, config and archive stay in this repo (user: yes).
- Defaults pending objection: archive as WebP in git; stylized galaxy/planet kept as art; Modi Fintelli excluded.
- Portfolio objects confirmed by the CV: drone station (NETRA, ESP32-S3 micro drone), telemetry console (ROS serial,
  ESP-NOW, GPS/IMU), PCB bench (user statement), star-tracker mount. Not confirmed: research terminal, LoRa.

## Open decisions (user)

- Keep or supersede the earlier "main = README + images only" cleanup (the plan places the renderer,
  config and archive in this repository).
- Archive format (WebP proposed) and whether the archive lives in git or on the VPS only.
- Public hostname/HTTPS for the live endpoint on the VPS.
- Stylized galaxy/planet: keep as art, or replace with the real sky.
- Which portfolio objects are real (drone/UAV, telemetry, PCB boards) — needs CV or confirmation.

## Phase status

| Phase | Status |
| --- | --- |
| 0 Repository audit | done (this file) |
| 1 Baseline | done: live hero at `569b58b` (GIF/poster/SVG), 34 tests, CI green |
| 2 SceneState (time, season, astronomy, seed) | done: `scripts/scene_state.py`, `config/observatory.json`, 22 tests; supervisor-verified sunset 14 Dec 2026 18:02 IST independently |
| 3 Day/night lighting on existing art | in progress |
| 4–14 | pending |

## Phase 2 implementation notes

- `config/observatory.json` holds the location, year window, renderer version and six Indian seasons with
  `MM-DD` start boundaries and target environment values. `scripts/scene_state.py` is one function,
  `scene_state(when, config=None)`, plus `season_for`, `environment_for`, `daylight` helpers. Dependency:
  `astronomy-engine` (pure Python).
- Season is chosen by the config boundaries (each season runs to the next start; Shishira wraps the year end).
  Environment parameters are blended between season *centres* with smoothstep, so there is no step at a
  boundary; the test enforces at most 0.03 change per day. Environment depends on the local date only.
- Sun and moon altitudes are geometric (no refraction) so the -0.833 / -6 / -12 / -18 degree thresholds mean
  what they say. Sunrise and sunset use astronomy-engine's rise/set (upper limb, standard refraction).
  `phase_angle_deg` is the Sun-Moon-Earth angle: 0 at full moon, 180 at new moon.
- `daylight` is smoothstep of sun altitude from -12 to +10 degrees. The seed is sha256 of
  `kushmodi-YYYY-MM-DD` (local date); astronomy never reads it.
- CLI: `python scripts/scene_state.py --at 2026-12-14T21:37:00+05:30` or `--date 2026-12-14` (21:00 local).
- No visual output changes in this phase.
