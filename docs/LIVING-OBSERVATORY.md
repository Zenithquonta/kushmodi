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
- Day and golden-hour foreground art may be generated from the approved painting, originals untouched (user: yes).
- Portfolio objects confirmed by the CV: drone station (NETRA, ESP32-S3 micro drone), telemetry console (ROS serial,
  ESP-NOW, GPS/IMU), PCB bench (user statement), star-tracker mount. Not confirmed: research terminal, LoRa.

## Open decisions (user)

- Keep or supersede the earlier "main = README + images only" cleanup (the plan places the renderer,
  config and archive in this repository).
- Archive format (WebP proposed) and whether the archive lives in git or on the VPS only.
- Public hostname/HTTPS for the live endpoint on the VPS (user agreed it is needed; the hostname itself is still to come).
- Stylized galaxy/planet: keep as art, or replace with the real sky.
- Which portfolio objects are real (drone/UAV, telemetry, PCB boards) — needs CV or confirmation.

## Phase status

| Phase | Status |
| --- | --- |
| 0 Repository audit | done (this file) |
| 1 Baseline | done: live hero at `569b58b` (GIF/poster/SVG), 34 tests, CI green |
| 2 SceneState (time, season, astronomy, seed) | done: `scripts/scene_state.py`, `config/observatory.json`, 22 tests; supervisor-verified sunset 14 Dec 2026 18:02 IST independently |
| 3 Day/night lighting on existing art | done: optional `state` path in the renderer, pixel-exact plate masks, `scripts/render_live.py`, 11 tests |
| 3b Day and golden-hour foreground art | done: `scripts/build_day_art.py`, `assets/observatory-day.png` and `-golden.png`, 6 tests |
| 4 Six-season visuals | done: dry vegetation plate, pixel clouds, monsoon overcast and seeded showers, wet ground and puddles, horizon haze, night visibility; 9 tests |
| 5 Mumbai skyline, haze and urban glow | done: fixed pixel skyline on both shores, sea link, night windows and blinking aviation lights, sodium glow on the low sky and cloud undersides; 6 tests |
| 6 Daily seed variation | done: seeded twinkles, meteors, sky crosses, clouds; 4 checked airliner timings and 4 satellite passes; more meteors on approximate shower peaks; 10 tests |
| 7 Portfolio objects | done: drone pad and hovering quadcopter, field ground station with telemetry trace, tracker controller on the tripod, PCB and soldering iron on the lantern crate; 8 tests |
| 8 Real Moon and planets | done: true Moon position and phase with the lit side towards the sun, moonlight on the ground, Mercury/Venus/Mars/Jupiter/Saturn by magnitude; dome projection; no real star field (no verifiable catalogue); 10 tests |
| 9 Daily day/night generator | done: `scripts/render_daily.py` (--date/--range), WebP frames at solar noon and 21:00, atomic + locked + idempotent, `archive/index.json`; 7 tests; no frames committed yet |
| 10 VPS deployment | done in the repo, not yet run on the VPS: compact live SVG (1.7-2.3 MB), `deploy/` (install, update, check, sandboxed systemd timer, Caddy template); 9 tests; Caddy rules verified locally |
| 11 Daily git sync | done in the repo, not yet run on the VPS: offline archive render at 21:10 IST, separate `obsync` user with a deploy key created on the server, archive-only clone, validated copy + index union, one commit a day; 13 tests incl. a bare-repo end-to-end |
| 12 README live switch | done 2026-10-02: README hero is the live view at https://observatorysky.duckdns.org (E2.1.Micro, 15-minute renders); branch test passed (camo serves the 2.3 MB SVG, animates, reduced motion gets the PNG, refreshes within ~2 min); revert with `python scripts/readme_live.py repo` |
| 13 Archive gallery | done in the repo: `deploy/archive_gallery.py` builds `archive/README.md` and one page per month in the daily sync commit; validated fields only; deterministic; 4 tests. Pages appear with the first VPS archive commit |
| 14 | pending |

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

## Phase 3 notes

- `scene(t, animated, state=...)`: without a state the output is byte-identical to the published assets (tested).
- Sky overlay (gradient, warm horizon glow, pixel sun) is masked by a **sky mask measured from the plate**: everything
  above SKYLINE, plus band pixels brighter than 0.55× their column's sky, flood-filled from the top and stopped at the
  horizon. Trees, telescope, van, roof and mountains occlude the sky pixel for pixel (no stair steps).
- The painted name is re-drawn above the sky through a **glyph mask** (three text lines detected from cyan pixels)
  with a dark pixel outline; noon contrast is tested at >= 3:1 on a real rasterized frame.
- Faint sky art (stars, galaxies, planet, lock-on, meteors, satellite) fades with its own curve: full at <= -14 deg,
  gone at >= -4 deg sun altitude. Ships stay; airliner nav lights fade by day.
- Interim look (superseded by 3b): the foreground was the night plate with a light lift by day.
- `scripts/render_live.py --at ISO --out DIR` writes live.svg/live.png/live.json, validated in a temp dir and moved
  into place only when all three are valid; a failed render leaves the previous files untouched (tested).
- Browser parity on a daytime live SVG: worst 167x94 cell 4 px (limit 150).
- Implementation: coder agent (stopped by a usage limit partway); the two review fixes (title box, stair-step sky
  clip), the celestial fade curve and the tests were written by the supervisor agent at the user's request.

## Phase 3b notes — day and golden-hour foreground

- `scripts/build_day_art.py` derives two RGBA plates from the night painting, offline (Pillow + NumPy; the renderer
  never needs NumPy). Alpha is exactly the plate's ground mask, so the sky stays the renderer's.
- Per region (feathered polygons in plate pixels): moonlit blues become foliage green, workshop wood, van khaki,
  grey metal for the telescope and rover, grey stone for the rock; the far band (mountains, city, far trees) keeps its
  blue and fades into haze, and its city lights are off. Lamp-lit wood, the lanterns, screens and neon keep their own
  colours. A shadow floor stops pure black from reading as night.
- Renderer: golden plate fades in from -5 to +1 degrees and out from +8 to +14; the day plate fades in from +4 to +14
  and is drawn over golden. Only plates with non-zero opacity are embedded. The twilight lift fades out as plates come in.
- The sunrise sky overlay is a little deeper (-0.8 deg top 0.86, +4 deg 0.97) so the painted Milky Way does not show
  through a sunlit sky.
- Size: a live SVG with a day plate is 8.7 MB as PNG. The WebP re-encode (amendment 2) is part of Phase 10.
- This is a derived relight, not a new painting; a hand-painted day plate can replace the files without code changes.

## Phase 4 notes — six seasons

- Every effect is a continuous function of `SceneState['environment']`, never of the season's name, so seasons blend
  day by day (tested: overcast, haze and dryness change by less than 0.05 a day).
- **Greenery:** `assets/observatory-dry.png` (vegetation only, straw hue, built by `build_day_art.py`) lies over the
  day plate with opacity 0.9 x smoothstep((0.85 - greenery) / 0.6). Grishma and Shishira read dry, Varsha and Sharad green.
- **Cloud density:** pixel clouds on a 6 px grid, one path per tone (lit top, body, shadowed base) so cells merge without
  seams. Count and size grow with density; positions come from the daily seed; the name block stays clear. Colours
  follow daylight and the sunrise/sunset glow; rain clouds are darker than the grey overcast deck that starts at
  density 0.6. Clouds are masked by the plate's sky mask, so trees and the roof stay in front.
- **Rain:** likely only above cloud density 0.62; the seed decides which hours shower (chance rises with ground
  wetness). Two layers of streaks loop seamlessly (0.75 s and 1 s periods divide the 24 s cycle) and are masked out
  under the workshop roof.
- **Ground wetness:** darkened ground and three puddles on the earth path that reflect the sky colour.
- **Haze:** a horizon gradient on the sky, dusty in Grishma, blue-grey otherwise.
- **Night visibility:** stars and sky art keep 0.3 + 0.7 x night_visibility; a night murk veil dims the painted Milky Way.
- The redrawn name is now drawn above clouds, haze and overcast.
- Browser parity (monsoon rain at 09:00 and Grishma noon, t = 0, 3 and 12 s): worst cell 0 to 10 px (limit 150).
- Implemented by the supervisor agent at the user's request ("start phase 4 yourself, don't wait").

## Phase 5 notes — Mumbai

- **Skyline:** 38 pixel towers in two clusters standing on the far shores of the bay (x 424-640 at y 714, x 884-1104
  at y 716), with flat, stepped and spire tops; fixed by a constant seed so Mumbai keeps one skyline all year. A
  cable-stayed bridge across the bay is a stylized nod to the Bandra-Worli Sea Link, not a survey of it.
- **Occlusion:** `city_mask()` is measured from the plate: far-band pixels darker than 24 are near silhouettes (trees,
  rock), closed with a 5 px max/min filter to fill their bright specks. No tower stands behind the telescope.
- **Light:** colours follow daylight and the sunrise/sunset glow, with the season's haze and the monsoon overcast deck
  baked in (the skyline is drawn over the weather layer, so it must match it). At night 16-46 % of window cells light up (more with urban_glow), the sea link deck has lamps,
  and towers over 40 px plus both pylons carry red aviation lights blinking on a 2 s period.
- **Urban glow:** an orange ellipse over the city on the sky mask, opacity 0.62 x urban_glow x darkness (capped at
  0.75), stronger with haze and cloud. Night cloud tones take up to 55 % of a sodium orange from below. A/B at 840 px
  (urban_glow forced to 0): low-sky difference 30 (winter) and 37 (monsoon) summed RGB; plainly visible on cloudy
  monsoon nights, subtle on clear winter nights.
- **Live SVG size now:** 6.2 MB (winter night), 8.8 MB (monsoon morning), 9.9 MB (Grishma noon, day + dry plates). The
  animated file also repeats the static city and cloud markup in its reduced-motion copy. WebP re-encode is Phase 10.
- **Sky-mask fix:** the telescope's counterweight arm pokes above SKYLINE and was painted over by the day sky. Its box
  is now measured like the band below; the day, golden and dry plates were rebuilt against the corrected mask.
- Browser parity (winter night 23:00 and December 17:50, t = 0, 3 and 12 s): worst cell 0 to 10 px (limit 150).

## Phase 6 notes — daily variation

- `daily_variation(state)` derives everything from the daily seed (`kushmodi-YYYY-MM-DD`), never the hour, with an
  independent seed per layer (`sha256(seed-<layer>)`), so twinkles, meteors, clouds and traffic do not move in lockstep.
- **Varies:** star twinkle rhythm, phase and sparkle size (the stars themselves are the painted ones); shooting-star
  times, angles and lengths; the small sky crosses; cloud layout; which of 4 satellite passes; which of 4 airliner
  timings.
- **Checked variants, not free randomness:** a sweep of airliner altitude x phase against the traffic tests found only
  512-518 px safe between the fighters and the skyline while any phase works, so days differ mainly in when the
  airliner crosses. The explorer and fighters with their warp choreography stay the same every day.
- **Meteor showers:** `config/observatory.json` lists approximate peaks (Quadrantids 01-03, Perseids 08-12, Geminids
  12-14) with a +/-1 day window; on those nights 12 meteors run in 2 s slots instead of 6 in 4 s slots.
  `scene_state` reports it as `sky_events.meteor_shower`.
- **Fixes found by the seed sweep:** the meteor placement checked the head path and the tail's start, not the tail
  segment between, so some seeds let a tail cross the name or the lock-on readout; now the whole streak is sampled.
  The <= 6 s gap between meteors is enforced during placement; the loop is bounded and fails loudly. The published
  seed passes both, so the default output is unchanged.
- **Tests (`scripts/test_daily.py`):** every airliner variant reruns the five traffic tests; every satellite pass reruns
  its test; 40 seeds x {6, 12} meteors rerun the open-sky/reset test; two seeded days rerun the generic SMIL-vs-raster
  and loop tests; consecutive days differ; defs follow the seeded meteors.
- Browser parity on the Geminids night (12 meteors) at t = 0, 3, 6, 12, 14.7, 18, 23.9 s: worst cell 0 to 9 px.
- Cloud layout changed from Phase 4 because clouds now use their own layer seed.

## Phase 7 notes — portfolio objects

- Only work confirmed by the CV or the user: NETRA and the ESP32-S3 micro drone (drone pad and a hovering quadcopter,
  drawn as art; the CV lists the micro drone as in design), a field ground station (ROS serial / ESP-NOW / GPS-IMU
  telemetry, shown as a generic scrolling trace and a blinking fix light), the star tracker's controller (a box with
  power and step lights clamped to the tripod), and PCB work (a board with chips and a soldering iron sending up a
  wisp, on the lantern crate). No labels, numbers or specs. No research terminal or LoRa (not confirmed).
- The painted telescope's counterweight looks equatorial; the new box is described as the tracker's controller, not as
  a claim that the painting shows the alt-az mount.
- Live-only (drawn when a SceneState is given), after the weather and before the rain. Outdoor objects follow
  daylight and the sunrise/sunset glow and darken with ground wetness; the PCB keeps the lantern's light.
- Sized to read at 840 px: the drone is drawn at 1.6x on a 2 px grid and hovers in front of the dark bushes; at night
  its red/green lamps glow and a white strobe double-flashes (the airliner's strobe timing).
- `PROTECTED` lists painted things (rover, lantern, printer, LEGO ship, cube patch, tripod centre column and right leg)
  plus the puddles; a test asserts no object box touches them, the name, or each other.
- **Coverage gap closed:** `scripts/test_portfolio.py` reruns the generic SMIL-vs-raster and loop checks on lit scenes
  (winter night, rainy monsoon night, noon) via a patched `layers`, so rain, beacons, clouds and the portfolio
  animations are now checked, not only browser-sampled. It caught a positive SMIL `begin` on the telemetry trace (the
  columns would have stood still for up to 3 s in a browser). Rain is exempt from the loop-jump check: it shifts by
  exactly one tile of identical streaks, so its wrap is seamless by construction.
- Browser parity (winter night, 7 times): worst cell 0 to 9 px; 0 differing pixels around the objects.

## Phase 8 notes — real Moon and planets

- `scene_state` adds `astronomy.planets` (Mercury, Venus, Mars, Jupiter, Saturn: altitude, azimuth, magnitude) from
  astronomy-engine, the same geometric altitudes as the sun and moon.
- **Projection changed for every sky object, the sun included:** the south-facing dome puts east at the left edge,
  west at the right and the zenith at the top centre (x = centre + sin(az - 180) x cos(alt) x half width, y linear in
  altitude up to 90 degrees). The old mapping (x from azimuth only, 60 degrees at the top) dropped a high moon off the
  canvas. Objects in the northern half below 60 degrees are behind the viewer and are not drawn. Phase 3 sun positions
  moved slightly.
- **Moon:** a 2 px pixel disc of radius 18. A cell is lit when, in the moon's frame with x towards the sun,
  x >= -cos(phase angle) x sqrt(1 - y^2), so the lit share equals the illuminated fraction (tested at 15-degree steps
  and three directions). The sun direction is the great circle from the moon to the sun, projected, so a waxing
  crescent after sunset is lit on its lower right. Five fixed maria, a faint earthshine side, a halo by phase. By day
  it is a pale disc at 0.55 opacity. It sits in its own sky-masked group (so it shows at deep night too), behind
  trees, clouds and the name.
- **Moonlight:** a blue lift on the ground of 0.2 x illuminated fraction x sin(moon altitude) at night. A/B at 840 px on
  the 27 Oct 2026 full moon: ground mean summed-RGB difference 86.
- **Planets:** steady pixel points (8/6/4 px by magnitude) with a soft glow; each appears when the sun is low enough
  for its brightness (Venus by -1 degree, Saturn near -12), scaled by the season's night visibility.
- **Kept as art:** painted stars, Milky Way, the two spiral galaxies and the ringed planet with its moons. No real star
  catalogue is drawn: none could be verified in this environment, and real constellations turning across the fixed
  painted sky would show two skies that disagree.
- Browser parity on the full-moon night (t = 0, 3, 12, 18 s): worst cell 0 to 8 px.

## Phase 9 notes — daily archive generator

- `python scripts/render_daily.py [--date D | --range START END] [--out DIR] [--width W] [--force]`. With no date it
  renders today **in Asia/Kolkata**, whatever the machine's clock zone (a UTC VPS would otherwise be a day behind
  between 00:00 and 05:30 IST; tested).
- Frame times live in `config/observatory.json` (`archive`): day at local solar noon (sun hour angle 0, rounded to the
  minute; tested to be the day's highest sun all year), night at 21:00 (sun below -18 degrees all year; tested).
- Output: `archive/YYYY/YYYY-MM-DD-day.webp` and `-night.webp` (840 px, WebP quality 85) and `archive/index.json`
  with a small entry per date (season, frame times, moon illuminated fraction, meteor shower, planets up at night,
  file sizes, renderer version).
- Both frames are rendered in a temporary directory, validated (decode, size, dimensions, not blank) and moved into
  place together; the index is rewritten atomically after every date; `archive/.lock` (flock) serializes writers.
  A date is skipped when both frames exist and decode (validity, not byte equality, since another libwebp or librsvg
  gives other bytes), unless `--force`. Dates outside the year window are refused.
- Measured: 13 dates across all six seasons average 79 KB per frame (day ~58 KB, night 57-112 KB; monsoon nights are
  smallest) -> about 58 MB for the year's 730 frames. A week renders in about 48 s here.
- No archive frames are committed in this phase: the archive is meant to grow one day at a time (Phase 11 sync).
- Tests mock the rasterizer except one real-render test that runs only where FFmpeg has librsvg.

## Phase 10 notes — VPS deployment

- **Compact live SVG** (`scene(..., compact=True)`, the default in `render_live.py`): measured first, the plate
  (3.4 MB), atlas (2.4 MB) and day plates (1.3 MB, embedded twice by mistake) dominated. Now: the plate and the day
  and golden plates go to JPEG 4:4:4 q90 (the day plates are drawn through the ground mask, which equals their alpha),
  the atlas and dry plate to WebP with lossless alpha; each raster is embedded once. Lossy WebP was rejected: it
  halves colour resolution and smeared the painted name and the workshop blueprint by up to 100 levels.
  Live SVG: 1.7-2.3 MB (was 6.2-9.9 MB), 1.8 MB gzipped. Full vs compact: Chromium worst cell 12 px, librsvg 1 px,
  name within 42 levels; compact Chromium vs librsvg worst cell 0. Day-plate alpha is exact after encoding.
- **`deploy/`**: `install.sh HOST` (Ubuntu 24.04 only; validates the host name; refuses if another server owns 80/443 or
  the Caddyfile is customised; Caddy from Ubuntu's own archive, 2.6.2), `update.sh` (fast-forward only, manual),
  `check.sh HOST` (timer, last result, file ages, HTTPS 200 for the three files, 404 elsewhere), `README.md`.
- **Layout:** code `/opt/observatory/repo` (root-owned, read-only to the service), venv `/opt/observatory/venv`, output
  `/var/lib/observatory/live`; Phase 11 will add its own clone and `/var/lib/observatory/archive`.
- **Service sandbox:** user `observatory`, `PrivateNetwork=yes`, `ProtectSystem=strict`, writes only the live
  directory, no capabilities, `NoNewPrivileges`, CPUQuota 80 %, 1 GB memory cap, 240 s timeout; timer every 5 min.
- **Verified here:** shellcheck clean; `systemd-analyze verify` (only the absent server paths are reported); Caddy
  2.6.2 validated and run locally from the template: 200 with correct types and headers for the three files; 404 for
  `/`, `/index.json`, `/.live-x/`, `/.live-x/f`, encoded traversal, a trailing slash and wrong case. One live render
  takes about 26 s in this container (slower on a small ARM core; the timeout is 240 s).
- **Not verified:** `install.sh` has not run on a real server; `check.sh` is how the user confirms it. Whether GitHub's
  image proxy accepts a 2 MB SVG and how often it refreshes it is still to be tested with the real URL (Phase 12).

## Phase 11 notes — daily git sync

- `observatory-archive.timer` (21:10 Asia/Kolkata, persistent) starts `observatory-archive.service`: as `observatory`,
  no network, `render_daily.py --recent 3` into `/var/lib/observatory/archive` (missed days in the last three are
  filled; outside the year window it renders nothing and exits 0). On success it starts `observatory-sync.service`.
- `observatory-sync.service` runs `deploy/sync.sh` as `obsync` (home 700, deploy key 600, network limited to
  IP/Unix sockets). Each run: fetch, reset its branch to `origin/main`, clean `archive/`, stage with
  `deploy/archive_tool.py` (from the root-owned code checkout; frames must match `YYYY/YYYY-MM-DD-(day|night).webp`,
  be regular files with WebP magic bytes and at most 2 MB; shared flock on the source; index merged as a union,
  server wins per date), refuse anything outside `archive/` or over 6 MB, commit once as
  `Observatory archive <archive@observatory.invalid>`, push; on rejection start again from the new main, at most
  three times. Never force.
- The sync clone is partial (`--filter=blob:none`) and sparse (`/archive/` only): no code in its working tree.
- `deploy/install-archive.sh` is two-pass: it creates the user, the key (on the server) and pinned GitHub host keys
  (from `https://api.github.com/meta` over TLS; that endpoint is not reachable from the build session, so the
  cross-check happens on the server), prints the public key with instructions, and on the second run clones and
  enables the timer. `update.sh` now shows every non-archive change and asks before merging; `check.sh` reports the
  archive timer, last results and key permissions.
- Tested here: `scripts/test_sync.py` runs the real `sync.sh` against a local bare repository: first run commits only
  archive paths with the archive identity, a rerun is a no-op, a rejected push is retried into one clean commit,
  upstream edits are kept, the index keeps older dates, junk names and non-WebP files stop the sync, the clone holds
  no code. Unit/config tests, shellcheck and `systemd-analyze verify` pass.
- Not run on a server yet. Agents working in this repository must fetch and merge before pushing once it is (noted in
  AGENTS.md and HANDOFF.md).

## Phase 12 notes — README live switch (prepared)

- README.md now wraps the hero in `<!-- hero:start -->` / `<!-- hero:end -->` (invisible on GitHub); nothing else in
  the published README changed. `scripts/readme_live.py live --host H` swaps in the live view (`live.svg`, with
  `live.png` for reduced motion, and a visible link to the repo animation) and records `live.host` in the config;
  `repo` restores the current hero byte for byte (tested); hosts must match the install.sh rule.
- `scripts/quality_gate.py` accepts external hero images only from `https://<live.host>/live.(svg|png)` and, in live
  mode, still requires the repo animation and poster and the link to them.
- There is no automatic fallback on GitHub (no `onerror`; `<picture>` picks by media query, not by load success).
  The choice between "live view as hero with a link back" and "repo animation as hero, live view below it" is the
  user's; the documented default is a few days of burn-in before switching.
- `docs/LIVE-SWITCH.md` holds the procedure: check.sh, burn-in, `scripts/probe_live.py HOST` (run from the user's
  machine or the server; this session's proxy cannot reach arbitrary hosts), then a test on the development branch
  on github.com: camo serves the SVG and accepts ~2 MB, SMIL runs in `<img>`, reduced motion selects the PNG, and
  freshness after the 240 s max-age is measured. If the SVG fails, use `live.png` as the image.

## Phase 13 notes — archive gallery

- `deploy/archive_gallery.py` (stdlib, imported by `archive_tool.py` from the read-only code checkout) writes
  `archive/README.md` (latest day large, up to six earlier days, links to months) and `archive/YYYY/YYYY-MM.md`
  (a row per day: noon, 21:00, season, moon, meteor shower, planets) in the same daily sync commit.
- Pages come from the merged index (so a reinstalled server cannot drop older months) and list a day only when both
  its frames are present. No timestamps: an unchanged archive regenerates identical pages and the sync stays a no-op.
- Index fields are checked against fixed vocabularies (six season ids, five planets, a capitalised shower name, a
  moon fraction in 0..1); anything else is dropped, not escaped. Tested with hostile entries.
- WebP in GitHub markdown was verified first on the development branch with a temporary 3 KB probe (both `![]()` and
  `<img>` render; raw is served as `image/webp`); the probe was removed in the next commit.
- The main README does not link the gallery yet: `archive/` does not exist until the first VPS archive commit. Add
  the link together with the Phase 12 switch.
- Sample output from the 13 scratchpad dates (Phase 9) was reviewed as text.

## Phase 14 notes — polish

- **Render cache:** the input-only steps (plate masks, city mask, bright-star list, compact JPEG/WebP encodings) are
  cached on disk when `OBSERVATORY_CACHE` or systemd's `CACHE_DIRECTORY` is set (`CacheDirectory=observatory` in the
  live and archive units). Keys cover this renderer's bytes, the source assets, parameters and Pillow's version;
  every value read back is validated (data URIs by pattern, the star list by shape) and anything doubtful is
  recomputed; writes are atomic. Measured here: 18.4 s uncached, 2.4 s warm, byte-identical output; a corrupted
  entry is recomputed. Off by default, so the default build and CI are unchanged. Tests: `scripts/test_cache.py`.

## Phase 15a notes — real Mumbai weather

- `scripts/weather.py` (stdlib) fetches Open-Meteo's current conditions for Mumbai (no key; data CC BY 4.0, credited
  under the live image). It keeps only whitelisted fields within fixed ranges (temperature, humidity, precipitation,
  rain, cloud cover, wind, gusts, is_day), maps the WMO code to the observatory's own conditions (clear,
  partly-cloudy, overcast, fog, drizzle, rain, heavy-rain, thunderstorm) and writes `current.json` and a 48-hour
  `history.json` atomically. Files read back are validated again; extra fields are dropped.
- `observatory-weather.timer` (:12/:27/:42/:57) runs the fetcher, the only online part (IP sockets, writes only
  `/var/lib/observatory/weather`). The renderers stay offline: `render_live.py --weather current.json` uses it when
  within 90 minutes of the render, `render_daily.py --weather-log history.json` uses the reading nearest each frame;
  otherwise the seasonal model is used and `live.json` shows `"weather": null`.
- Mapping: cloud cover sets cloud density (at least 0.72 when it rains); precipitation (mm per 15 minutes) and the
  condition set the rain amount, replacing the seeded showers; rain wets the ground; fog thickens the haze.
- Verified against a real response captured on the server (2 Oct 2026 16:00: drizzle, 69 % cloud, gusts 31 km/h),
  saved as `scripts/fixtures/open-meteo-2026-10-02T1600.json`. Measured on the Micro before the cache: 43-47 s CPU
  per render, 142 MB peak.
- Phase 15b followed: lightning, wind-driven grass, grounded airliner with an advisory hologram.

## Phase 15b notes — storms, the grounded airliner and the meadow

Everything here needs a real observation (the seasonal model never grounds flights or throws lightning), and the
default `scene()` stays byte-identical.

- Storm deck: heavy rain and thunderstorms raise the overcast deck to 0.80/0.86 and darken it toward black (the
  Milky Way disappears), and a `storm-shade` rect dims the sunlit ground.
- Lightning (thunderstorm only): three seeded strikes per 24 s loop, one in each of 1.5-7, 9-15 and 17-22.5 s.
  Each is a double flicker (0 -> 1 -> 0.12 -> 0.9 -> 0 over 0.24 s): a jagged bolt with branches from the cloud
  base to behind the skyline (sky-masked; the city is drawn over it) and a sky flash at opacity 0.3. Never more than
  two flashes in any second (limit 3), and opacity 0 at t = 0, so the still PNG and the reduced-motion copy never
  show a flash.
- Grounded airliner: thunderstorm, heavy rain, fog, or gusts of 60 km/h or more remove the airliner route (the
  fictional starships keep flying). A cyan hologram projected from the van's roof rack reads `! AIRSPACE ADVISORY /
  FLIGHTS SUSPENDED / <reason> OVER MUMBAI / WIND n KM/H · GUSTS n KM/H / STAND BY >>`. It has shimmer, a glitch
  dip, scanlines, amber corner brackets and a blinking last line. The text comes only from the validated numbers
  and fixed strings.
- Meadow: 64 grass tufts along the foreground (only on ground-mask pixels, clear of objects, puddles and protected
  painting). They sway with a 4 s period, phase-shifted across the field so gusts roll through. Sway amplitude
  `min(22°, 1.5 + 0.42·wind + 0.12·gust)` uses the real wind, otherwise a seasonal breeze from cloud and wetness.
  Colour follows day/night, dry season and storm shade.
- Verified: 11 new tests in `test_storm.py`. The generic SMIL-vs-raster and loop checks rerun on a stormy night,
  sampled inside every strike; deliberately broken lightning and meadow timing are both caught. Chromium vs librsvg
  worst 167×94 cell is 19 (limit 150) at five times including two strikes. The animated SVG is 1.8 MB (stormy
  night) to 2.4 MB (day).

## Phase 15c notes — flickering shed lights, the tracking screen and the reactive robot

All live only; the default `scene()` stays byte-identical.

- **Lights.** Four lights flicker, each dimmed through its own mask built from the plate's own glow and cached:
  - the pendant lamp's warm wood and bulb;
  - the cyan tube's white core and halo;
  - the left and right magenta neons.

  The lantern never flickers. Shapes are flicker, sputter, blink (neon) and brownout (lamp only). Two to four
  events per loop sit in separate slots, re-seeded every quarter hour, so each redraw tells a slightly different
  story. In a thunderstorm every light dips together 1 s after each strike, like a power surge. Depth is 0.55
  (lamp) and 0.8 (tubes) at night, and 40 % of that by day. Combined with the lightning there are never more than
  three dips in any second, and nothing at t = 0.
- **Wall screen.** It cycles SUN TRACK (0–8 s), MOON TRACK (8–16 s) and the painted blueprint (16–24 s), with a
  refresh line at each change. Each page shows:
  - the body's real altitude through the local day (`astronomy.altitude_by_hour`, 25 hourly values now in the
    state and `live.json`);
  - a cursor at the current time and the body on it (an outline when below the horizon);
  - ALT/AZ;
  - for the sun, the next sunrise or sunset; for the moon, the illuminated percentage and WAXING/WANING, plus a
    pixel phase disc.

  The text is built only from computed numbers.
- **Robot.** Its mood colours its eyes, ping rings and lidar: calm (cyan), rain (amber, dimmer eyes, lidar off,
  "sheltering"), alert (red; thunderstorm or grounded flights). It reacts to real scene events:
  - perks its head up 2 px (a copy of the painted head lifting on its neck) and turns its eye toward the
    telescope's lock-on, toward each lightning strike, and toward whichever light flickers;
  - idle glances fill the gaps;
  - the antenna pings at the lock-on (and after each strike in a storm), and the mast beacon blinks (faster on
    alert).

  The lidar fan sweeps the field, the tail light breathes, the cyan panel scrolls telemetry, the headlight glows
  after dark, and the eye glow flares when lightning strikes.
- **Verified.**
  - 17 new tests in `test_shed.py`.
  - The generic SMIL-vs-raster and loop checks run on a calm night, a storm night and a clear day, sampled inside
    every flicker, glance, ping and page change. Their tolerances are 1e-3 and 0.05 px, because the older starship
    warp-flash scale keyframes differ by 0.04 px between keyframes at those times.
  - Deliberately broken lights, robot and screen timing are all caught.
  - Chromium vs librsvg worst cell is 8.5 out of 150, at six times.
  - SVG size is 1.8 MB (night) to 2.4 MB (day).
  - CI timeout raised from 5 to 8 minutes (the suite is now 179 s locally).


## Phase 15d notes — the observatory log, planet tracking and the planets page

All live only (they need a scene state); the default `scene()` stays byte-identical.

- **Log.** `scripts/story.py` holds a library of story-beat templates: oppositions, on this day, meteor shower, moon,
  planets up or rising, Jupiter's moons, Uranus and Neptune, sun events, weather, season, night sky, workshop. A beat
  is a title plus up to three detail lines, an optional eyepiece inset and an optional target planet. Each beat is
  built only from the scene state (computed astronomy, a validated weather observation, the season) and fixed
  strings; nothing is invented. `choose()` takes every eligible must-show beat first (oppositions, then on this day,
  meteor shower, full or new moon), then weighted picks, seeded per quarter hour. Two beats per loop show in the log
  panel under the name: 0-12 s and 12-24 s, crossfading over 0.4 s. The still frame shows the first.
- **Fit rule.** Every line is drawn with the 3-px pixel font from the panel's left margin and must end at or before
  `INSET_TEXT_LIMIT` when the beat has an eyepiece, else 12 px inside the panel. `story.context()` takes a `fits(text,
  inset)` callable (the renderer passes one measured with the real glyph widths) and templates give ordered options
  to `story.pick()`, which returns the first that fits and otherwise the shortest. Examples: `SATURN AT OPPOSITION`
  then `SATURN · OPPOSITION` (the timing goes on the next line); `JUPITER UP IN SAGITTARIUS`, `JUPITER UP IN SGR`,
  `JUPITER UP`; `IN SAGITTARIUS · ALT 88°`, `SGR · ALT 88°`, `ALT 88°`; `MAG 7.8 · TELESCOPE ONLY`, then `MAG 7.8 ·
  SCOPE ONLY`. Only the outer planets (Mars to Neptune) have an opposition beat.
- **Weather.** In a grounding storm the advisory hologram keeps the panel and the log does not draw.
- **Reticle.** A beat about a planet that is drawn in the sky puts a pulsing amber reticle on it. It is skipped under
  thick cloud (overcast above 0.3), when the planet is faint in the sky, and wherever it would touch the name, the
  lock-on readout, the dotted line, the galaxy's own reticle, the log panel, the canvas edge or the skyline.
- **Screen.** The wall screen now cycles SUN TRACK (0-6 s), MOON TRACK (6-12 s), PLANET TRACK (12-18 s) and the
  painted blueprint (18-24 s). The planets page lists up to six planets, those above the horizon first (highest
  first, with the constellation abbreviation), then the rest by rise time. This supersedes the 8-second pages in the
  15c notes.
- **State.** Each planet now carries its constellation (IAU boundaries) and abbreviation, distance in AU, rise and
  set for the coming night ("tonight" turns over at 06:00), and for the outer planets the nearest opposition (the
  last 30 days, else the next). Uranus and Neptune and Jupiter's four moons (arcsecond offsets) are in the state.
  Saturn's opposition is 04 Oct 2026 at 17:42 IST (8.434 AU, magnitude 0.2, in Cetus).
- **Verified.**
  - `scripts/test_story.py`: every eligible beat over a year (every 9th day at 00, 05, 11, 18 and 21 h) with no
    weather, the drizzle fixture and clear, hot, humid, windy, cloudy and thunderstorm observations, plus a
    synthetic worst case (all planets at 88 degrees, magnitude -4.7 and 7.9, 30.07 AU, the longest constellation
    names, oppositions 3 days either side); glyphs, line count and widths; `choose()` determinism, priority and
    variety; the Saturn opposition night facts; story and advisory exclusivity; reticle clearances and cloud
    behaviour; the planets page fit; the SMIL-vs-raster and loop checks on 5 Oct 00:00 IST sampled at the story swap
    and fade and the screen page changes, with the same 1e-3 and 0.05 px tolerances as 15c.
  - `test_shed.py` fit test covers the planets page.
  - A temporary revert of the fit mechanism makes the fit test fail on `MAG 5.6 · TELESCOPE ONLY`.
  - Browser playback of the log, reticle and screen has not been verified by the coder; it is for the supervisor.

## Phase 15e notes (ISS, Hubble and Tiangong)

- **Data.** `scripts/satellites.py fetch` (the `observatory-satellites.timer`, 03:07 and 15:07 plus two minutes after
  boot) asks CelesTrak for the two-line elements of the ISS (25544), Hubble (20580) and Tiangong (48274), one request
  each, a second apart. Every element set is validated like the weather feed: 69-character lines, characters from the
  TLE alphabet, mod-10 checksums, line numbers, the catalogue number on both lines, an epoch no older than 7 days and
  no more than a day ahead. Names come from the fixed `SATELLITES` table, never from the feed. The result is
  `/var/lib/observatory/satellites/tle.json`, written atomically; a satellite that fails keeps its previous entry
  (dropped after 14 days) and never stops the others. The fetcher is the second and last part that goes online; it
  runs under the same hardening as the weather fetcher (`ReadWritePaths` limited to its own directory).
- **Computation.** The renderers stay offline. `satellites.compute()` propagates the stored elements with SGP4
  (`sgp4` through `skyfield`'s built-in time scale, nothing downloaded; both are in `requirements.txt`), takes the sun
  from astronomy-engine and models the Earth's shadow as a cylinder. A pass is visible while the satellite is sunlit,
  above 10 degrees, and the sun is more than 6 degrees below the observer's horizon. The state key `satellites` holds
  per satellite: now (altitude, azimuth, sunlit, visible, height in km), the epoch, and `next_pass` (start, top and
  end times, maximum altitude, start and end azimuth with compass directions, and a coarse track sampled every 10 s)
  for the first visible pass still to end within 24 hours. Missing, stale or invalid elements give `None`, and then
  the picture, the screen and the log simply have no satellite content. An independent SGP4 + Earth-rotation check in
  the tests agrees with the computed look angles to within 0.1 degree.
- **Cost.** Each render is a fresh process, so passes for the two local-noon windows that cover the next 24 hours are
  cached on disk in `OBSERVATORY_CACHE` / `CACHE_DIRECTORY` (the services' `CacheDirectory=observatory`), keyed by
  the code and library versions, the element lines, the day and the location, and re-validated when read (the cache
  is no more trusted than the network). Uncached, one satellite over two windows takes about 0.4 s; a cache hit costs a
  few milliseconds. Entries older than 4 days are removed.
- **Screen.** The wall screen cycles SUN TRACK (0-5 s), MOON TRACK (5-10 s), PLANET TRACK (10-15 s), SAT TRACK
  (15-20 s) and the painted blueprint (20-24 s). The sats page follows the bezel rules of the screen: a title and at
  most five rows at 13 px pitch from `SCREEN_MARGIN`, ending at or before `SCREEN[2] - 1`. Each row reads
  `ISS 19:32 68° SW` (start time of the next visible pass, highest point, start direction), `HST --:--` when none is
  due within a day. If a row would overrun the screen the space before the direction goes (`68°SW`), and if that
  would still overrun the degree sign goes (`88 NW`); the choice is made once for the whole page. `NO ORBIT DATA`
  when there are no elements. This supersedes the 6-second pages in the 15d notes.
- **Log.** A visible pass starting within 90 minutes (or under way) is announced ahead of everything else with its real
  numbers: `ISS PASS 19:32`, `MAX 68° · SW TO N`, `VISIBLE 4 MIN`, `LOOK UP AFTER DUSK`. It never says "now" or
  "overhead". Otherwise the beats are an ordinary `NEXT PASS` line and one fact per satellite (the ISS crewed since
  2000, Hubble in orbit since 1990, Tiangong's orbit height from the computed state).
- **Pass animation.** When a visible pass overlaps the next 15 minutes, the sky shows a pale dot with a short trail
  crossing along the real track (the part in view: the south and everything above 60 degrees; the longest run is
  used), 7 s of each loop from 3 s, with its label (`ISS 19:32`) placed near the start clear of the skyline, the name,
  the readouts, the log panel and the edges. Nothing is drawn under thick cloud (overcast above 0.3) or when fewer
  than three track points are in view. The default scene (`observatory.svg`, `poster.svg`) has no state and is
  byte-identical to before.
- **Tests.** `scripts/test_satellites.py` (48 tests): element validation (checksums, lengths, epochs, tampering,
  the 14-day staleness, previous elements kept after a failed download), SGP4 against an independent calculation, the
  shadow model, pass geometry on a real CelesTrak fixture (`scripts/fixtures/celestrak-2026-10-02.tle`), the screen
  page fit for every direction, story beats with real times, pass animation against the raster, the label search
  and the offline `render_live` behaviour. `test_deploy.py` checks the units' sandboxing and wiring.
- **Not verified by the coder.** Browser playback of the pass dot and the sats page, and a live fetch from
  CelesTrak on the server (the sandbox only fetched the fixture). The supervisor verifies both.
