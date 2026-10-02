# Implementation gap analysis: Living Observatory website vs the walkable portfolio world spec

Compares the website as it stood after milestone 1 (M1: a first-person hill with a telescope, shed, rover, van, drone pad
and a real sky) with `docs/PORTFOLIO_3D_WORLD_SPEC.md` (the target; section numbers below are the spec's). Protocol:
spec section 29. Each component is KEEP, MODIFY, REPLACE, ADD, REMOVE or DEFER with a priority (P0 blocks the core
experience, P1 is required for a convincing MVP, P2 is polish, P3 is future). The principle of spec section 29 applies:
working systems are preserved, not rewritten for purity. Milestone 2 (LO-P16-M2) implements every P0 and P1 item.

Constraints that shape every item: static ES modules, three.js 0.186.1 vendored (no build step, no CDN, nothing new
vendored), Caddy allowlist (`/`, `css/`, `js/`, `vendor/`, `data/` only), a strict Content-Security-Policy (no inline
script or style, no `innerHTML`), under 1 MB gzipped for `site/`, and content only from `README.md`.

## 1. What is already correct (preserve)

| System | Where | Why it stays |
| --- | --- | --- |
| Real 360 degree sky: BSC5 stars, Milky Way, constellation lines, Sun, Moon with phase, planets, three-hour trails | `sky.js`, `ephemeris.js`, `target.js`, `data/` | Matches spec section 19 ("stars, observatory prominent at night") and is the product's identity. Verified against the renderer's numbers. |
| Day/night from the real Sun and the weather/season from `/live.json` (validated, never markup) | `live.js`, `main.js` `applyLook` | Spec 19 day/night; safe data path with tests. |
| Telescope pointing at the live target, with a readout (name, RA, Dec, altitude, azimuth) | `world.js` telescope, `target.js`, `hud.js` | Hero prop (spec 6, 12). Only moved to the observatory and wired to an interaction target. |
| Pixel look: low-resolution canvas scaled with `image-rendering: pixelated`, no antialiasing, flat Lambert colours | `main.js` `resize`, `css` | Spec 4. Extended (palette pass, shadow), not replaced. |
| Plain HTML text version, no-WebGL and no-JS fallback, "Text version" button | `index.html`, `main.js` | Spec 17 mobile fallback and accessibility; README text verbatim. |
| Caddy allowlist and CSP, vendored pinned libraries with licences | `deploy/`, `site/vendor/` | Security and deployment already done; do not touch. |
| Tests and the real-browser check | `scripts/test_site.py`, `scripts/site_browser_check.mjs` | Extended for the new content, never relaxed. |
| Merged-geometry helper `Bag`, collider format (circle and rotated box), `groundHeight` function | `geom.js`, `controls.js`, `terrain.js` | Good primitives for a procedural low-poly world. |

## 2. Component classification

### World and terrain

**C01 Hill terrain (`terrain.js`): MODIFY, P0**
- Current: one hill, flat crown of radius 30 m, soft walking radius 46 m, vertex-coloured polar mesh.
- Problem: far too small for six places; flat ("empty flat ground", spec layer 2); no clearings; paths drawn by blurry vertex colour.
- Change: crown radius about 54 m, walking radius 66 m; gentle swells (about 1.2 m) between the places; places flattened by a smooth site mask; crisp dirt paths and clearings as ground-hugging ribbons and discs.
- Why: spec 3 layer 2 and section 6 (clear main path). Notes: `groundHeight` stays the single source of truth for avatar, props and scatter. Accept: avatar y follows `groundHeight` everywhere; places are level; path ribbons visible in the start view.

**C02 Layout data (new `layout.js`): ADD, P0**
- Current: positions are scattered constants in `world.js`.
- Problem: no single description of the six places, the main path, and the signs.
- Change: one pure-data module (no three.js) with the locations, the path polyline and the order Profile, Workshop, Robotics, UAV, Research, Observatory.
- Why: spec 6, 21. Accept: a node test can import it; every place lies inside the walking radius; path joins all six in order.

**C03 Ground detail and vegetation: ADD, P1**
- Current: 90 pine cones merged into one mesh, 16 rocks, no grass.
- Problem: spec layers 3 and 4 missing: grass clumps, tall and dead grass, flowers, pebbles, rocks, bushes, trees, logs, fallen branches.
- Change: `InstancedMesh` families with variants and random rotation, scale and tint; density scaled by the graphics setting; vegetation frames places and keeps paths clear.
- Why: spec 3, 16 (instancing). Notes: a seeded generator so the world is the same every visit. Accept: at least 8 instanced families, draw calls stay under 120, density halves in lite mode.

**C04 Pine scatter and fence: MODIFY, P1.** Fence moves to the new walking radius and the trees become the sparse forest edge (spec layer 4); trees get colliders. Accept: no tree on a path or inside a place.

### Places (hero props and story props)

**C05 START / Profile camp: ADD, P0.** Current: the player simply stands on the hill. Change: camp with workbench, laptop (profile workstation, interactive), backpack (interactive), notebook, tools, tent, lantern, nameplate sign. Why: spec 7. Accept: spawn view shows the camp and the path; workstation opens the profile panel.

**C06 Engineering Workshop: MODIFY, P0.** Current: the M1 maker shed (printer with a rocket, LEGO ship, wall screen). Problem: tools and electronics (spec 8) are thin and nothing is interactive. Change: keep the shed; add oscilloscope, soldering station, multimeter, PCBs, breadboard, motors, servos, LiPo, wire spools, filament spools, shelves, CAD printouts and an enclosure chamber; make bench, printer, wall screen and enclosure interactive. Accept: five interactive objects inside or beside the shed.

**C07 Robotics Field: ADD, P0.** Current: the rover stands loose beside the van. Change: open field with a dirt test loop, rover tracks, cones, navigation markers, rocks and a telemetry mast; rover (Team Darwin) is the hero. Why: spec 9. Accept: rover sits on the terrain and casts a shadow; opens the Team Darwin panel.

**C08 UAV / NETRA Test Field: MODIFY, P0.** Current: a 3 m pad with a drone. Change: larger clearing, landing pad, drone, ground station, antenna mast, camera station, battery station, crates, micro drone on a stand, windsock. Why: spec 10. Accept: drone, ground station, micro drone, AeroLink crate are interactive.

**C09 Research Lab: ADD, P0.** Current: none. Change: cabin with a glowing window, outdoor terminal under an awning with a data screen, map board, graphs, weather mast, paper. Interaction opens the dengue forecasting entry ("details coming soon"). Why: spec 11. Accept: terminal opens a panel that makes no claims.

**C10 Observatory: MODIFY, P0.** Current: the telescope stands alone on the crown; the sky readout is a HUD. Change: deck with the telescope (moved, unchanged mathematics), star tracker mount, domed control building with the control computer, star charts, equipment cases, a warm lamp and a cool glow; the landmark at night. Why: spec 12, 19. Accept: visible from the start at night; telescope opens the star tracker panel with the live target readout.

**C11 Van: REMOVE, P3.** Current: a parked van at the hill's edge. Problem: no portfolio meaning; the new camp and cabins carry the story. Change: drop it; the van stays in the README art. Accept: no dead colliders.

**C12 Mumbai skyline: KEEP, P1.** Stays at the north horizon (spec 19 context); city lights at night. Notes: the Observatory sits west so the skyline remains in the start view.

**C13 Signs and the main path: ADD, P1.** Current: none. Change: signposts at each place and at path forks ("ROBOTICS FIELD") drawn as canvas textures with a small pixel font. Why: spec 6 (clear main path), 24. Accept: from each place a sign points to the next place.

### Player, camera, interaction

**C14 First-person controller (`controls.js`): REPLACE, P0.** Current: eye-height camera, bobbing, no avatar. Problem: spec 5 wants third person with an avatar; no jump or gravity. Change: third-person orbit camera over the shoulder, pixel avatar, WASD and arrows, mouse look, Shift sprint, collision, ground following, basic gravity (and a jump), camera pulled in by obstacles. Accept: avatar visible from behind at spawn; cannot walk through the shed wall, the rover or the telescope.

**C15 Collision: MODIFY, P0.** Current: circles and rotated boxes, one fence radius. Change: keep the format; add colliders for every new prop, trees and the dome. Accept: scripted walk along the main path is never blocked on the path, and a walk into a wall is blocked.

**C16 Avatar (new `avatar.js`): ADD, P0.** A neutral explorer, no likeness: helmet with visor, jacket, backpack; legs and arms swing while moving. Accept: reads as a person at 640 by 360.

**C17 Interaction system (new `interact.js`): ADD, P0.** Current: only the telescope can be clicked. Change: the idle, nearby, focused, activated, exit states of spec 13: "[ E ] INSPECT" prompt, corner-bracket highlight, click or E opens, Escape, click outside or the close button closes; tap button on touch. Accept: 14 targets, each referencing an id in `portfolio.json`.

**C18 Project panel (new `panel.js`): ADD, P0.** Current: the telescope readout box and a text fallback only. Change: an overlay card (spec 14: title, category, text, technologies, links) with the world visible; built with `textContent`; focus moves in and back. Accept: three panels open and close in the browser check without console errors.

**C19 Data-driven content (`data/portfolio.json`): ADD, P0.** Current: copy in HTML only. Change: projects, targets and contacts as data (spec 22). Content rule: every sentence comes from `README.md` verbatim; spec-only projects (AeroLink, enclosure/chamber, dengue forecasting) say "details coming soon" and nothing else. Accept: a unit test checks every snippet against the README, the contacts, and the exclusions.

### Rendering and style

**C20 Render path: MODIFY, P1.** Current: canvas at one third of the window, devicePixelRatio up to 1.5, direct draw. Problem: pixel size not uniform at ratio 1.5; no palette. Change: render at a 360 line target (about 640 by 360 on a desktop), ratio 1, via a low-resolution render target and a fullscreen pass that posterises and Bayer-dithers (switched off in lite mode). Accept: the Milky Way, Polaris and faint stars remain visible in the night screenshot.

**C21 Lighting and shadow: MODIFY, P1.** Current: hemisphere, sun, moon and three shed lights, no shadows. Change: sun with a hard-edged 1024 shadow map that follows the player (about 28 m), warm local lights at the workshop, research cabin and observatory, cool emissive screens. Accept: the rover and avatar cast shadows by day; point lights stay at five.

**C22 Palette and materials: MODIFY, P1.** Flat Lambert vertex colours stay; palette gets earth tones for terrain, steel blue for tech, amber for warm light. Accept: no PBR, no bloom.

**C23 Day and night: KEEP, P1.** Already real. Added: workshop, cabin and observatory lights brighten at dusk; the observatory dome glows.

### UI

**C24 Compass strip and large title panel: REMOVE, P1.** Problem: persistent HUD furniture (spec 20 "avoid excessive HUD"). Change: a small name chip and a location indicator remain.

**C25 "Up now" sky list and weather: MODIFY, P1.** Keep the data (`live.json`, computed sky) in a collapsed "Sky" chip that opens on demand. Accept: values still match the renderer.

**C26 Controls hint, help, graphics quality, sound: ADD, P1.** Hint fades after the first move; help panel; a Graphics toggle (high, lite) and a Sound toggle (off by default, synthesised, no files). Accept: both buttons keyboard operable.

**C27 Loading and entry: ADD, P1.** Current: the text page flashes before WebGL starts. Change: a dark loading screen with a short line, a fade into the world, then the controls hint (spec 23). Accept: no giant hero text over the world.

**C28 Touch controls: MODIFY, P1.** Current: joystick and tap on the telescope. Change: joystick plus swipe look plus a large INSPECT button; lite mode by default on touch; denser props removed. Accept: 390 by 844 screenshot shows the joystick and no horizontal scroll.

**C29 Text version and fallback: KEEP, P1.** Unchanged content; the loading screen never covers it.

### Performance, deployment, tests

**C30 Instancing, colliders, draw calls: MODIFY, P1.** Merged geometry per material stays; vegetation is instanced; keep under 120 calls and under 100k triangles. Accept: reported by `__obs.calls`.

**C31 Lazy loading of distant detail: DEFER, P2.** Everything is procedural and small; creating it is cheaper than a loader. Revisit if the frame time suffers.

**C32 Tests (`test_site.py`, `site_browser_check.mjs`): MODIFY, P0.** Add the portfolio schema, README-text, exclusion, target and file-reference tests; the browser check walks the path, opens panels, and takes the screenshots. Accept: both green.

**C33 Deployment: KEEP, P0.** Nothing in `deploy/` changes; no new top-level path in `site/`.

**C34 Audio, jump polish, grass sway: DEFER, P2.** A tiny synthesised ambience is included only if time allows; wind-swayed grass waits.

### Deferred (spec sections 25 and 26)

DEFER, P3: dynamic weather in the world beyond the sky, moving rover and drone takeoff, interactive map, achievements, timeline trail, live repository data, multiplayer, NPCs, quests, VR. Not built.

## 3. Asset requirements

Procedural only (no model files): `terrain_base/slope/dirt/rock/path` (terrain and ribbons), `grass_*` and `flowers`
(instanced blades), `rock_small/medium/large`, `bush_*`, `tree_small/medium`, `log`, `fallen_branch`, `workbench`,
`toolbox`, `oscilloscope`, `multimeter`, `pcb`, `breadboard`, `motor`, `servo`, `battery`, `wire_bundle`, `3d_printer`,
`filament_spool`, `rover`, `rover_wheel`, `lidar`, `telemetry_mast`, `uav`, `uav_stand`, `landing_pad`, `ground_station`,
`antenna`, `battery_station`, `telescope`, `tripod`, `camera`, `star_tracker`, `observatory`, `astronomy_case`. Textures
are small canvases drawn at load (signs, screens, star chart, map board). Nothing is downloaded.

## 4. Scene requirements

- Six places on one ring about 40 m from the centre, joined by a dirt path in the spec's order; a central fire ring with logs.
- Spawn at the south, facing north, with the camp in front, the workshop right, the observatory dome left.
- Terrain flat inside places, gently rolling between; fence and sparse forest at the edge.
- Every hero object stands on the ground (y from `groundHeight`) and casts a shadow by day.

## 5. Interaction requirements

States per target: idle, nearby ("[ E ] INSPECT" within reach), focused (amber corner brackets), activated (panel),
exit (Escape, click outside, close button). Targets and their projects (`data/portfolio.json`): profile workstation
and backpack (Profile); workshop bench and 3D printer (Fab lab, Fabrication); enclosure (details coming soon); wall
screen (Living Observatory); rover (Team Darwin); drone and ground station (NETRA); micro drone (ESP32-S3 micro
drone); AeroLink crate (details coming soon); research terminal (dengue forecasting, details coming soon); telescope
(star tracker plus the live target readout); observatory computer (Team Astrofix, Smart India Hackathon 2025).

## 6. Performance problems found

- M1 rendered at one third with ratio 1.5, so an upscaled pixel is not uniform; fixed by ratio 1.
- All trees were merged into one mesh of about 30,000 triangles; instancing and fewer segments reduce this.
- No shadows (cheap to add, but one map only, near the player, off in lite mode).
- The M1 browser check ran about 22 fps on software GL; the new check reports its own number and uses a fixed-step walk hook so it does not depend on the frame rate.

## 7. UI problems found

Compass strip, large title panel and the sky list were always on screen (spec 20 asks for a minimal UI); the only
interaction was a telescope click; no help for first-time visitors; no loading state; no graphics control.

## 8. Camera and movement problems found

First-person eye height with no avatar (spec 5 asks third person); no gravity or jump; look only after a click or a
drag; no camera collision. A sky-gazing mode is kept: the camera closes in on the avatar when looking up.

## 9. Visual-style mismatches

Tidy flat hilltop (spec: dense, gently varied); sparse props (spec: density rewards looking around); unlit signage and
screens fine, but no warm/cool contrast between workshop and observatory; no hard shadow edges.

## 10. Implementation order

1. This document. 2. `layout.js`, `terrain.js` (heights, ribbons, patches). 3. `controls.js` third-person player,
`avatar.js`. 4. Places: camp, workshop upgrade, robotics, UAV, research, observatory (`places.js`, `world.js`).
5. `portfolio.json`, `panel.js`, `interact.js`, prompt, highlight, location indicator, `index.html` and CSS.
6. Tests and the browser check; walk the path; screenshots. 7. P1: `scatter.js` (instancing), signs, shadow, post
pass, lite mode, mobile button, loading and hint. 8. Re-run everything; record the spec section 28 results. 9. P2
afterwards: ambience, grass sway, lazy distant detail.

## 11. MVP checklist (spec 27)

See section 12 of `docs/WEBSITE.md` for the verified state; the checklist: 3D world loads; player walks; camera works;
collision works; terrain exists; grass, rocks and vegetation exist; workshop, robotics area, UAV area, observatory
exist; at least three interactive objects; interactions open panels; works without a scrolling homepage; performance
acceptable; mobile fallback exists.

## 12. Acceptance test (spec 28)

A new visitor, without documentation, should: (1) understand they are inside a world; (2) figure out how to move; (3)
notice the engineering environment; (4) find an obvious interactive object; (5) open a project; (6) close it; (7)
continue exploring; (8) find another project through the environment; (9) understand that places are parts of Kush's
work; (10) reach the observatory. The results for this build are recorded in `docs/WEBSITE.md`.
