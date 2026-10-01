# Canonical execution ledger

This ledger is intentionally reviewable. The implementation and first rendered animation exist; the remaining work is verification, refinements and repository installation. A future supervisor should confirm current evidence, then update statuses here. Preserve each task and its evidence when it is complete.

States: `pending → assigned → implementing → ready_for_review → done`. A rejected review returns to `implementing`. An external dependency changes the task to `blocked`; describe exactly what was attempted and what would unblock it.

| ID | Task | Current state | Acceptance / evidence |
| --- | --- | --- | --- |
| T00 | Recover package into the cloud runtime | done | Package was not present in the container; recovered from user uploads and verified against `MANIFEST.json` (see review record). |
| T01 | Inspect supplied project and approved references | done | Read the gate and handoff; open reference photo, approved concept, current poster and square image. Record actual runtime/model IDs. Do not rebuild from scratch. |
| T02 | Review the layered scene and animation geometry | done | Background, sprites, galaxy rotation, moon orbits, ship traffic, twinkles, print head, wireframe cube and LEDs exist in the builder. Inspect 0/3/6/12/18/23.9 second frames for clipping, artifacts, title collisions and horizon crossings. |
| T03 | Review and refine the square profile picture | done | `assets/profile-picture.png` exists. Check telescope/galaxy readability at 96px and 192px, and in a circular crop preview. Keep source image unchanged. |
| T04 | Review README content, employer removal and scope | done | Name is Kush Modi; astronomy-first profile; four expandable sections; AstroFixxer project links; aviation/LEGO/CAD/printing interests; no removed-work references. Existing robotics/education/contact facts are grounded in the original README. |
| T05 | Verify actual GitHub README interactions | done | Render on GitHub after push, verify picture fallback, image links, section anchors and details. GitHub README must not depend on JavaScript, image maps or iframe controls. |
| T06 | Browser-test and refine the local interactive preview | done | At desktop and mobile widths, check inline SVG playback, pause/resume, keyboard focus, clickable scene areas, mission panels, reduced-motion behavior and no horizontal overflow. Save screenshots/evidence. |
| T07 | Align SVG and GIF animation timings | done | The same scene functions render both versions, but some workshop SMIL motion interpolates linearly while raster frames use sine. Review resulting differences and make them intentional or identical. Compare selected times and the wrap at 24 seconds. |
| T08 | Optimize size without damaging the approved look | done | Current GIF: 1000×563, 240 frames at 10fps, 24s, 11,744,470 bytes. Review 840/1000px and 8/10/12fps tradeoffs if needed. Prefer one accepted version, no noisy blur or flickering palettes. Document final output dimensions, bytes, duration and tool versions. |
| T02-R1 | Fix traffic clip, overlap and foreground crossings found in T02 | done |  Explorer hard-clipped at x=574 (t≈14.7); fighters overlap explorer and trees (t≈0/23.9); airplane crosses right trees/workshop roof (t≈15.6). Route geometry/fades only. |
| T02-R2 | Register the CAD cube to the painted cube; moons pass behind the planet | done | Found in T01 (double cube in every frame) and the known moon-occlusion item. |
| T13 | Animated mission cards + fourth Rover Bay card (user-approved addition) | done | Subtle SMIL card motion with static <picture> fallbacks; 2x2 card grid. |
| T14 | Scene additions: telescope lock-on, warp/hyperspace transitions, airplane nav lights (user-approved) | done | M51 lock-on with pixel readout; explorer warp exit; fighter drop-outs; nav lights + strobe. |
| T15 | Living sky: slower galaxies, twinkling painted stars, shooting stars, satellite (user-requested; push approved) | done | Ported from the user's PC session onto the reviewed builder with Track parity; 38 tests; Chromium vs GIF parity. |
| T16 | README mission logs updated from the user's CV | done | Facts from resume.tex only; GR Modi, Modi Fintelli, accounting/clerical skills excluded; contacts unchanged pending user. |
| T09 | Review meaningful source regression tests | done | Five tests now cover traffic period wrap, periodic/finite CAD geometry, deterministic and changing scene output, sprite crop bounds, and the observed open-path polygon regression. The quality gate additionally covers SVG references and removed live-content references. Review preview regeneration coverage and extend where meaningful. |
| T10 | Review handoff, registry and reproducibility | done | All supplied artwork, active SVGs, legacy SVGs, scripts, template, ledger, entry point and model loop are included. `assets/MANIFEST.json` should describe files and hashes. The handoff must accurately identify completed versus pending work. |
| T11 | Commit and push the entire handoff and profile project | implementing | Target is only `Zenithquonta/kushmodi`. Earlier writes to both Git Trees and Contents APIs failed with 403 `Resource not accessible by integration`. Refresh live permissions before retrying. Preserve HEAD/unrelated files and do not force-push. |
| T12 | Verify CI and live profile, then report | blocked | Depends on T11. Fetch pushed files, confirm the validation workflow run and inspect rendered README. Report actual commit SHA and repository URL. Do not claim a GitHub profile-top display: a `kushmodi` repository does not match the account name `Zenithquonta`. |

## Review record format

Append under the relevant task:

```text
Reviewed by: <supervisor actual model / agent identifier>
Coder: <actual model / agent identifier>
Attempt: <1, 2, or 3>
Files changed: <paths>
Commands and outcomes: <exact concise evidence>
Visual evidence: <screenshots/frame paths or explicitly not verified>
Decision: approve | revise | blocked
Reason: <specific finding>
Remaining caveats: <actual material limits>
```

## Current known evidence

- Background and sprite sheet were generated from the approved concept.
- The atlas is genuinely RGBA, with more than 40% fully transparent pixels.
- The first GIF has 240 frames, a 24-second duration and infinite looping.
- At four sampled times, decoded GIF frames are different.
- Active SVG resources are embedded PNG data; no script or foreign object is required.
- The scene contains 98 valid animation elements at the initial check.
- README image files and four section anchors resolve locally.
- Current public README contains no clerical/employer references requested for removal.
- Browser playback and live GitHub rendering remain unverified.

Marking a task `ready_for_review` is not a claim that a supervisor has approved it.

## Review records

### T00 — package recovery (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5"; Claude Code cloud session)
Coder: none (supervisor-only recovery and verification)
Attempt: 1
Files changed: AGENTS.md, HANDOFF.md, TASKS.md, SUPERVISOR-PROMPT.md, docs/*.md, scripts/*.py, preview.template.html, preview.html, requirements.txt, assets/{observatory.svg,poster.svg,observatory-poster.png,observatory.gif,observatory-background.png,space-sprites.png,*-card.svg}
Commands and outcomes:
  - Background + atlas extracted from supplied preview.html data URIs: sha256 b82feeb1… / 8d51e493… == MANIFEST.
  - observatory.svg extracted from preview.html: 5,876,534 bytes, sha256 bbcc7528… == MANIFEST.
  - python scripts/build_animation.py → observatory.svg, poster.svg, observatory-poster.png all byte-identical to MANIFEST.
  - python scripts/build_animation.py --gif --fps 10 --width 1000 → observatory.gif sha256 b50e46da…, 11,744,470 bytes == MANIFEST (1m49s, 4 workers).
  - python scripts/build_cards.py → three card SVGs byte-identical to MANIFEST.
  - preview.template.html recovered from preview.html; build_preview.py round-trips to sha256 ea1fb72d… == supplied preview.html.
  - unittest: 5/5 pass.
  Toolchain: Python 3.11.15, Pillow 12.3.0, FFmpeg 6.1.1-3ubuntu5 with librsvg decoder.
Visual evidence: not applicable (byte identity).
Decision: approve
Reason: recovered files are provably the supplied package versions.
Remaining caveats: README.md, CI workflow, profile-picture.png, approved-concept.png, reference-telescope.jpg and assets/legacy/ not yet supplied as files.
```

### T01 — inspection (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: none
Attempt: 1
Commands and outcomes: read all gate/handoff docs; rendered t=0,3,6,12,14.7,15.6,18,23.9 at 1672px and zoomed crops.
Visual evidence: frames inspected directly by supervisor (scratchpad, not committed).
Decision: approve
Findings fed to T02-R1 / later tasks:
  1. Explorer hard-clipped by fleet-zone at x=574 (t≈14.7).
  2. Fighter A overlaps explorer; fighters and trails drawn over right-edge trees (t≈0, 23.9).
  3. Airplane crosses right-hand trees and workshop roof (t≈15.6).
  4. Animated wireframe cube is offset ~(-25,-13) px from the cube painted in the plate, so two cubes are visible in every frame.
  5. Moons always drawn in front of the planet (known).
  6. Nozzle/scan/LED SMIL vs sine raster mismatch (known, T07).
  Name/typography clear in all sampled frames; airplane clears telescope finder at t≈6.3.
Model resolution: both user-selected names resolved to runtime models; the exact identifiers are reported to the user in the session, not stored in the repository.
```

### T02-R1 — traffic route refinement (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5", Agent tool alias `sonnet`)
Attempt: 1
Files changed: scripts/build_animation.py (traffic_state/ROUTES/SKYLINE; fleet-zone clipPath removed), scripts/test_scene.py (+7 tests)
Commands and outcomes:
  - unittest: 12/12 pass (supervisor re-run).
  - Coder brute force at 0.005s steps: 0 text/skyline/sprite-overlap violations.
  - Supervisor: sky empty of fully visible traffic 4% of the loop, longest gap 0.96s.
  - Supervisor browser parity: Chromium 1194 (Playwright 1.56.1) setCurrentTime vs librsvg frames at
    t=0,3,6,12,14.7,18,23.9 -> no traffic-region differences. Residual differences are confined to the
    planet (x1336-1670,y94-282): pre-existing planet-bob SMIL/raster sign inversion -> T07.
Visual evidence: supervisor inspected contact sheet (8 times) and SKYLINE overlay; skyline hugs van,
  finder, workshop roof and right-hand trees. Explorer warps out between x=900..720 (no slice); fighters
  fade in at x~1340 clear of trees; airplane dissolves before x=1330, clear of roof.
Decision: approve
Reason: D1-D3 resolved; single route table drives both SMIL and raster; browser playback matches.
Remaining caveats: explorer lane raised 385->338, fighter-b phase .20->.245; plane fades mid-sky by design
  (spec forbids painting over foreground). GIF/SVG assets not yet regenerated (after T07/T02-R2).
```

### T04 — README content review (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: none (user-supplied README.md from the package; supervisor review only)
Attempt: 1
Files changed: README.md (replaces the old public README on this branch)
Commands and outcomes:
  - python scripts/quality_gate.py -> passed (4/4): images/anchors resolve, four <details> logs, removed work absent.
  - URL-decoded scan for clerical|GR Modi|CA Tech|Apps Script|SaaS|employ|pilot|SolidWorks|Fusion 360|AutoCAD -> none.
  - Facts cross-checked against the original README (git show ab04e28..82dbf9a): NMIMS MPSTME CSE, Darwin Club,
    IGVC regional 1st / IGVC 5th overall (kept as the user's own project-log claims), ROS Noetic, tools, hardware,
    GitHub/LinkedIn/email links. Dropped: employer row, clerical SaaS, 80% workload claim, typing/capsule
    taglines, stale exam/travel notes, Apps Script badge.
Visual evidence: GitHub rendering not yet verified (T05, after publication).
Decision: approve
Reason: astronomy-first, no invented credentials, no removed-work references, only GitHub-supported interactions.
Remaining caveats: <picture> reduced-motion behaviour and card links must be verified on github.com (T05).
```

### Concurrent publication to main (2026-10-01)

```text
Observed: commit 316e993 on main ("feat: observatory profile README, assets and handoff docs"), authored by
Kush Modi at 2026-10-01 10:55 +0530, pushed outside this session. CI run 36819742217 on main: success.
Verified: all 15 assets on main match MANIFEST.json SHA-256; scripts, docs, preview and template are
byte-identical to the versions recovered in T00; README.md identical to the one approved in T04.
Merge into ccr-19e1f533-c4auq1: took main's original workflow, .gitignore and requirements.txt (authentic
package versions; the session's recreated workflow is superseded); kept this branch's TASKS.md and the
reviewed T02-R1 builder/tests. New on this branch from main: approved-concept.png, profile-picture.png,
reference-telescope.jpg, assets/legacy/*, assets/MANIFEST.json.
Consequence for T11: the original package is published on main by the user. Reviewed refinements on this
branch still need to reach main (normal merge, no force-push).
```

### T03 — profile picture review (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: none (review of existing artifact)
Attempt: 1
Files changed: none (assets/profile-picture.png unchanged, sha256 8c45c4c7… == MANIFEST)
Commands and outcomes: Pillow LANCZOS downscale to 460/192/96/48 px with anti-aliased circular mask.
Visual evidence: supervisor inspected the circular contact sheet (scratchpad, not committed).
  460/192: galaxy core and telescope silhouette fully inside the circle; ringed planet partly cut by the rim.
  96: galaxy, telescope against horizon glow and warm workshop remain readable.
  48: reads as galaxy + horizon glow; telescope barely discernible (expected at that size).
Decision: approve
Reason: focal points survive circular cropping at GitHub's avatar sizes; no edit warranted.
Remaining caveats: static image; uploading it as the GitHub avatar is a manual account-settings step for the user.
```

### T05 — live GitHub README verification (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempt: 1
Target: https://github.com/Zenithquonta/kushmodi main @ 316e993 (README identical to this branch)
Files changed: none
Commands and outcomes:
  - github.com page HTML fetched (200). In article.markdown-body: <picture> (wrapped in <themed-picture>),
    <source media="(prefers-reduced-motion: reduce)">, GIF <img>, 3 linked card <img>s, 4 <details>,
    anchors user-content-{observatory,flight-deck,fab-lab,mission-log}; 7/7 hrefs match; no script/iframe/map.
  - Images via /raw/main -> 302 -> raw.githubusercontent.com: GIF 200, 11,744,470 bytes, sha256 b50e46da…
    (served as application/octet-stream; Chromium decodes it, 1000x563); poster PNG and 3 card SVGs 200.
  - Chromium (Playwright 1.56.1, real GitHub HTML + bytes): currentSrc = GIF normally, = poster PNG under
    emulated prefers-reduced-motion:reduce, at 1280 and 390 widths. <summary> click opens <details>.
    Article width 390 == viewport at mobile: no horizontal overflow.
Visual evidence: supervisor inspected desktop-A-top.png and mobile-A-top.png (scratchpad/t05).
Decision: approve
Reason: every README interaction GitHub supports is present and works; none relies on JavaScript.
Remaining caveats: github.githubassets.com is blocked by the sandbox egress policy, so GitHub's own CSS/JS
  (short-hash -> user-content- scrolling, dark theme) was not exercised live; anchor ids verified instead.
  On ~390px phones the three cards render ~92x35px and their text is unreadable; the text nav row above
  them provides the same links. GIF content-type is octet-stream (GitHub raw behaviour).
```

### T07 — SVG/GIF timing parity (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempt: 1
Files changed: scripts/build_animation.py (Track keyframe helper; planet bob, nozzle, scan, LEDs, reticle,
  twinkles, meteor fade, cube vertices driven by Tracks on both paths), scripts/test_scene.py (+4 tests)
Commands and outcomes:
  - unittest 16/16 pass (supervisor re-run, ~1.0s).
  - Supervisor independent Chromium setCurrentTime vs librsvg parity (1672x941), pixels |diff|>60:
      t=0 541->1, t=3 6435->4, t=6 8118->5, t=12 567->1, t=14.7 5794->5, t=18 8168->5, t=23.9 240->0.
    Mean abs diff now 0.12-0.16 (renderer antialiasing only).
  - Fixed: planet bob inverted (SMIL rose while GIF fell), nozzle/scan/LED/reticle/twinkle phase and shape,
    reticle opacity applied on two nested nodes (multiplied), meteor fade shape, cube chord interpolation.
  - Animated SVG +3.7 KB (+0.06%).
Visual evidence: supervisor inspected workshop crops at t=0,1.5,3,6,12,23.9; all motions present, no jumps.
Decision: approve
Reason: SMIL and GIF frames are now identical by construction and verified in a real browser.
Remaining caveats: raster motion is a 24-keyframe sine approximation (<=0.2 px deviation from the old analytic
  curve); assets not yet regenerated (after T02-R2).
```

### T06 — local preview browser test (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempt: 1
Files changed: preview.template.html; preview.html regenerated via scripts/build_preview.py
Defects fixed:
  1. `.scene svg{width:100%}` also matched the 18 nested sprite <svg> viewports, so Chromium blew sprites up
     to full width (giant galaxy/fighter over the telescope). Present in the originally supplied preview.html;
     supervisor reproduced it in Chromium (original vs fixed screenshot). Selector now `.scene>svg`.
  2. <summary> had no visible focus ring on the dark page -> added to the #fe7cdc focus rule.
  3. Telescope/planet hotspots realigned to their landmarks.
  4. Under reduced motion the disabled button read "RESUME MOTION" -> "MOTION REDUCED", dimmed.
Commands and outcomes (Playwright 1.56.1 Chromium, 1280x900 and 390x844): playback advances; pause/resume by
  click, Enter and Space with aria-pressed/text; focus order motion -> 3 hotspots -> 3 cards -> 3 summaries ->
  footer, all with visible ring; hotspots and cards open + scroll to their <details>; reduced motion hides
  .moving, shows .still, disables the button and reacts to runtime changes; scrollWidth == innerWidth at both
  widths; 0 console/page errors.
Visual evidence: supervisor inspected original-vs-fixed Chromium render; coder screenshots in scratchpad/t06.
Decision: approve
Remaining caveats: Chromium only (no Firefox/WebKit); hotspots are fixed rectangles, not tracking moving sprites.
```

### T02-R2 — cube registration + moon occlusion, attempt 1 (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempt: 1
Files changed (uncommitted): scripts/build_animation.py, scripts/test_scene.py
Commands and outcomes: 21 tests pass; parity max cell 4 (limit 150); animated SVG +3.8 KB.
Visual evidence: supervisor inspected cube mid-rotation sheet (both options), 1000px workshop comparison,
  moon occlusion old/new x4.
Decision: revise
Reason: Moons approved (hidden behind the planet on the far half, in front on the near half, no pop at switches).
  Cube: option 1 (overlay on painted cube) reads as a cluttered double hexagon while turning -> rejected.
  Option 2 (plate-derived feathered patch + one cube) is correct, but the yaw-only projection collapses to a flat
  rectangle every 90 deg and the painted hologram glow is lost. Attempt 2: fixed tilt, subtle glow stroke,
  remove option-1 code, check faint patch bottom edge.
```

### T02-R2 — attempt 2 (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempt: 2
Files changed: scripts/build_animation.py (22 deg tilt + weak perspective cube registered on the painted cube,
  two-stroke restrained glow, plate-derived feathered patch with low strip + gradient, option-1 code removed;
  moons drawn as behind/front copies switched by opacity Tracks), scripts/test_scene.py (23 tests)
Commands and outcomes: 23/23 pass (supervisor re-run); parity max cell 4 at 7 times; animated SVG +35 KB.
Visual evidence: supervisor inspected x3 cube crops at 8 poses and the 1000px plate/t0/t0.75 workshop comparison.
Decision: approve
Reason: single cube, 3D at every pose, footprint matches the painted cube within 0.5px, glow matches the plate,
  no visible seam at README size; moons occluded correctly (approved in attempt 1).
Remaining caveats: patch loses the plate's soft halo (glow strokes stand in); faint plate-shadow step at x<1452,
  y~741 visible only at 1672px brightness-boosted.
```

### T13 — animated cards + Rover Bay card (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempts: 2 (attempt 1 revise: SVG-internal reduced-motion query is ignored when the SVG is shown via <img>)
Files changed: scripts/build_cards.py; assets/{observatory,flight,fablab,rover}-card.svg (+ -static.svg variants);
  README.md (card table only: 2x2 grid, each card in <picture> with a reduced-motion static source); MANIFEST.
Commands and outcomes: build_cards deterministic over 8 files (supervisor re-ran); static cards contain no
  animate/fx/style; quality gate passes and fails when a static srcset file is missing (coder mutation check);
  23 tests pass. Chromium: currentSrc = *-static.svg under reduced motion, animated cards otherwise.
Visual evidence: supervisor inspected the 2x2 animated sheet, 390px table and reduced-motion table renders.
Decision: approve
Remaining caveats: GitHub's handling of <source media> inside the card table follows the hero's (verified in T05)
  but the new table itself is verified after publication.
```

### T08 — GIF size (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempt: 1
Files changed: scripts/build_animation.py (GIF_WIDTH=840 default for --width/rasterize; bayer_scale 3->5; comment)
Commands and outcomes: 16 encoder variants measured from shared frames (scratchpad/t08/metrics.csv).
  A 1000px/10fps/bayer3 11,336,782 B (reproduces published); 840px/10fps/bayer5 8,075,059 B (-28.8%);
  8fps only -18%; sierra2_4a +109% and flickers; stats_mode=diff +8% and worse error; diff_mode=rectangle,
  new=0 byte-identical (muxer already emits sub-rectangles); gifsicle -O3 -0.13%.
  Static-region inter-frame MAD 0.000 for all Bayer variants; 23 tests pass.
Visual evidence: supervisor inspected 1000px vs 840px vs source resampled to GitHub's ~830px display width:
  lettering and telescope indistinguishable; 840px is ~1:1 at display size.
Decision: approve
Remaining caveats: fewer source pixels for high-DPI zoom; assets regenerated after T14 scene additions.
```

### T14 — scene additions (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempts: 2 (attempt 1 revise: targeting line lost against the Milky Way; warp flash bar read as a "T")
Files changed: scripts/build_animation.py (lock_on(), warp specs in ROUTES, nav_lights()), scripts/test_scene.py (34 tests)
Content: telescope acquires the face-on spiral as M51 (real J2000 RA 13h29m, Dec +47 11'), pixel-font readout
  (no <text>), single reticle at a time; explorer stretches to warp with a sparkle flash; fighters drop out of
  hyperspace; airplane red/green lights and 1.5 s double-flash strobe.
Commands and outcomes: 34/34 tests (supervisor re-run); parity worst cell <=5 (limit 150) at 7 standard times +
  lock hold + warp frames; animated SVG +22 KB; scratch GIF 840px 7,955,864 B.
Visual evidence: supervisor inspected lock hold full frame, GIF-decoded line crop at lock hold, readout x6 at GIF
  scale, explorer warp 5-frame strip (attempts 1 and 2).
Decision: approve
Remaining caveats: warp/drop-out are 4-5 GIF frames by design; line overlays ships passing at that moment.
```

### T09 — regression tests (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: n/a (tests were added and reviewed within T02-R1, T07, T02-R2, T14)
Outcome: 5 -> 34 tests. Coverage: traffic text/skyline/overlap/fade guarantees over all 240 samples; generic
  SMIL-vs-raster evaluation of every animation element; loop continuity; cube registration and 3D read; plate-only
  patch; moon layer switching; lock-on placement/timeline/pixel font; warp geometry; nav-light periods. Mutation
  checks by coders confirmed tests fail on injected regressions. CI runs them on every push.
Decision: approve
```

### T10 — handoff, registry, reproducibility (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempt: 1
Files changed: HANDOFF.md, docs/ANIMATION-SPEC.md, docs/ASSET-REGISTRY.md, docs/PUBLISH-STATUS.md, SUPERVISOR-PROMPT.md
Commands and outcomes: gate 4/4; 34 tests; stale-number grep leaves only two lines explicitly labelled history; no
  runtime model identifiers in docs. Supervisor corrected CI wording with the verified run #15 result.
Decision: approve
Remaining caveat: preview.html still shows three panels (the fourth card exists only in README).
```

### T15 — living sky (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5"; Claude Code cloud session)
Coder: same agent (no separate coder was delegated; the code was ported from an earlier session's edits)
Attempt: 1
Origin: The user asked for a slower galaxy and a livelier sky (twinkling stars, random shooting stars). A Claude Code
  session on the user's PC implemented it against the original package in Downloads (1000px GIF, pre-T02-R1/T07/T13/T14
  builder), rendered with Chrome because FFmpeg was absent, and asked to push. The user approved, but the PC went
  offline before the push. Its edits were recovered from that session's transcript. Pushing that folder would have
  rolled back T02-R1..T14, so the changes were ported onto the current builder instead.
Files changed: scripts/build_animation.py (slow_spin, twinkles/bright_stars/twinkle_plan, meteors/meteor_plan/meteor_tracks,
  satellite, QUIET, shared tw*/mt* gradient defs; rotate_node removed), scripts/test_scene.py (+4 tests; circle leaves
  added to the generic comparison), assets/{observatory.svg,poster.svg,observatory-poster.png,observatory.gif,MANIFEST.json},
  preview.html, docs.
Differences from the PC version: every motion is a Track, so SVG and GIF agree; no mix-blend-mode:plus-lighter (librsvg
  ignores it: a 50%+50% test rendered like normal blending), so eased 1-w^2 / 1-(1-w)^2 dissolve curves are used instead;
  static frames keep every element so the generic parity test compares like with like; meteor and satellite positions
  return to the start while invisible; QUIET also excludes the lock-on readout (so meteor positions differ slightly
  from the PC preview).
Commands and outcomes:
  - unittest 38/38 pass; quality gate 4/4 (10 SVGs, 520 animation elements in total, 504 in the hero).
  - GIF: 840x473, 240 frames, 10fps, loop=0, 8,150,550 bytes (+2.4% vs T14).
  - Loop wrap on the main-galaxy crop: mean abs step 239->0 = 6.25 vs normal steps 6.04-6.22.
  - Core luminance through the dissolve: 141.2-149.0 (start 144.9).
  - Chromium 1194 (Playwright 1.56.1) setCurrentTime vs librsvg at 1672px, t=0.4/6.4/13.6/20/23.9:
    pixels |diff|>60 = 2/6/7/4/0 of 1,573,352; mean abs diff 0.12-0.16.
Visual evidence: supervisor inspected a 6-frame decoded-GIF contact sheet (0, 0.4, 6.4, 13.6, 20, 23.9s) and a 9-frame
  main-galaxy strip through the dissolve and the wrap (scratchpad, not committed).
Decision: approve
Remaining caveats: mid-dissolve (about 19-21s) the main galaxy briefly shows four faint arms. The new frames were
  not shown to the user before this push; the user approved the PC version, which has the same features.
```

### T16 — README content from CV (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5")
Attempt: 1 (+ supervisor wording fix: IGVC placing labelled as team result)
Source: user-supplied resume.tex (session upload). Included: MBA Tech Computer Engineering 2024-2029 (MPSTME,
  NMIMS); alt-az star tracker mount; Team Astrofix SIH 2025 team leader; NETRA; ESP32-S3 micro drone (in design);
  trekking/skiing/scuba (in progress); Fusion 360/SolidWorks/FDM/fabrication; own PCBs (user statement in
  session); Team Darwin roles, Vega/Kaizen, Gazebo, chassis, cost-field approach, electronics integration;
  IGVC 1st qualifying / 5th AutoNav; tools.
Excluded: GR Modi and Co.; Modi Fintelli (accounting venture, pending user decision); Apps Script, VBA,
  Workspace automation, web scraping, TradingView; Model UN.
Checks: header/cards/footer byte-identical to HEAD; gate passes; 60 tests; exclusion grep empty.
Decision: approve
Open: CV contacts (kushsmodi@gmail.com, linkedin.com/in/kushsmodi) differ from README contacts; unchanged
  until the user confirms which are correct.
```

### T16 follow-up — contact email (2026-10-01)

```text
User instruction: "use kushmodi@gmail.com". README footer mailto changed from kushmodi13@gmail.com to
kushmodi@gmail.com. LinkedIn link unchanged (linkedin.com/in/kushmodi) pending user confirmation.
```

### LO-P3 — Living Observatory day/night lighting (2026-10-01)

```text
Reviewed by: supervisor agent (user-selected "Opus 5.5")
Coder: delegated coder agent (user-selected "Sonnet 5.5") until a usage limit stopped it; at the user's instruction
  ("do the two fixes yourself") the supervisor agent implemented the remaining fixes and tests.
Attempt: 1 coder (partial) + supervisor completion
Files changed: scripts/build_animation.py (lighting, plate_masks, night_factor), scripts/render_live.py,
  scripts/test_lighting.py (11 tests), docs/LIVING-OBSERVATORY.md
Review findings on coder partial: dark night box around the title at noon; stair-step night sky above the horizon
  from the conservative SKYLINE clip; galaxies visible over sunrise/civil-dusk sky.
Fixes: plate-derived sky/ground/glyph/outline masks; title redrawn with outline; separate celestial fade (-14..-4 deg).
Commands and outcomes: 70 tests pass; quality gate passes; default scene byte-identical to published SVG/poster;
  Chromium vs librsvg on a 08:33 day state: worst cell 4 px.
Visual evidence: supervisor inspected contact sheets for 2026-12-14 and 2027-07-15 (8 times each) and fixed-frame
  re-renders at 07:08 and 18:14.
Decision: approve (interim tint; day art still required for a convincing daytime foreground)
```

### LO-P3b — Day and golden-hour foreground art (2026-10-01)

```text
Requested by: user ("yes" to generating day and golden-hour versions matched to the approved art, originals untouched)
Implemented and reviewed by: supervisor agent (user-selected "Opus 5.5"); the coder agent was still usage-limited
Files: scripts/build_day_art.py (new, offline, Pillow + NumPy), assets/observatory-day.png, assets/observatory-golden.png
  (RGBA, ground only, alpha = plate ground mask), scripts/build_animation.py (plate crossfade, sunrise sky depth),
  scripts/test_lighting.py (+6 tests), assets/MANIFEST.json, docs
Method: per-region relight of the night painting (vegetation, telescope, rock, van, workshop wood, rover, far haze);
  lamp-lit wood, lantern, screens and neon keep their own colour; city lights off by day; shadow floor under pure black.
Commands and outcomes: 77 tests pass (includes committed plates == builder output, alpha == ground mask);
  quality gate passes; default scene byte-identical to the published assets; Chromium vs librsvg at 12:30 and 17:40
  live states: worst cell 0 px.
Visual evidence: contact sheets 2026-12-14 (06:40 to 18:14) and 2027-07-15 (06:30 to 19:05) inspected.
Known limits: live.svg is 8.7 MB with PNG plates (WebP re-encode belongs to Phase 10); the art is a derived relight,
  not a new painting.
Decision: approve
```

### LO-P4 — Six-season visuals (2026-10-01)

```text
Requested by: user ("start phase 4 yourself, don't wait"); coder agent usage-limited
Implemented and reviewed by: supervisor agent (user-selected "Opus 5.5")
Files: scripts/build_animation.py (season(), clouds, overcast, rain, wet ground, haze, night visibility; title drawn
  above the weather), scripts/build_day_art.py (dry vegetation grade), assets/observatory-dry.png,
  scripts/test_lighting.py (+9 tests), assets/MANIFEST.json, docs
Self-review fixes during the phase: overcast washed out the name (title moved above weather); a hard haze block over
  the far band (haze now on the sky mask only); fair-weather clouds on a monsoon sky (rain clouds darker than the deck);
  anti-aliased seams between cloud rows (one path per tone).
Commands and outcomes: 86 tests pass; quality gate passes; default scene byte-identical to published assets;
  Chromium vs librsvg on monsoon rain and Grishma noon at t = 0/3/12 s: worst cell 0 to 10 px.
Visual evidence: six-season sheet (10:00-10:30 for each season plus Varsha and Shishira nights), July and May day sheets.
Decision: approve
```

### LO-P5 — Mumbai skyline, haze and urban glow (2026-10-01)

```text
Requested by: user ("yes start phase 5 yourself, don't wait")
Implemented and reviewed by: supervisor agent (user-selected "Opus 5.5")
Files: scripts/build_animation.py (city_mask, city_towers, city_markup, city_windows, city_beacons, city_glow, cloud
  underglow, counterweight sky-mask fix), assets/observatory-day.png, -golden.png, -dry.png (rebuilt for the
  corrected mask), scripts/test_lighting.py (+6 tests, mask probes updated), assets/MANIFEST.json, docs
Self-review fixes during the phase: day towers looked ghostly because haze covered them only above the ridge (skyline
  now drawn over the haze with haze baked into its colours); low day contrast; telescope counterweight erased by the
  day sky since Phase 3.
Commands and outcomes: 92 tests pass; quality gate passes; default scene byte-identical to published assets;
  Chromium vs librsvg at winter 23:00 and December 17:50, t = 0/3/12 s: worst cell 0 to 10 px.
Visual evidence: skyline zooms at noon, golden hour, winter night and monsoon night; full frames 10 Jan 2027.
Advisor review (after first push): CI confirmed green for Phases 4 and 5; July 11:00 towers popped out of the grey
  overcast (now mixed toward the deck colour); city glow was not visible at 840 px (peak 0.34 -> 0.62, cloud
  underglow 0.32 -> 0.55, re-measured by A/B); tree-edge fringe checked at 4x, none; counterweight fix noted as a
  change to Phase 3/3b output.
Decision: approve
```

### LO-P6 — Daily seed variation (2026-10-01)

```text
Requested by: user ("yes start phase 6 yourself, don't wait")
Implemented and reviewed by: supervisor agent (user-selected "Opus 5.5"); approach reviewed by the advisor before coding
Files: scripts/build_animation.py (seeded plans, routes_for, satellite paths, daily_variation, layer_seed, meteor
  placement fixes), scripts/scene_state.py (sky_events.meteor_shower), config/observatory.json (approximate shower
  peaks), scripts/test_daily.py (10 tests), scripts/test_scene_state.py (shape), docs
Findings during the phase: tail segment unchecked in meteor placement; meteor gaps could exceed 6 s; two guessed
  airliner variants clipped a fighter (replaced by sweep-checked variants).
Commands and outcomes: 102 tests pass; quality gate passes; default scene byte-identical to published assets;
  Chromium vs librsvg on the Geminids night at 7 times: worst cell 0 to 9 px.
Visual evidence: 10 and 11 Feb 2027 at 23:00, four loop times each.
Decision: approve
```

### LO-P7 — Portfolio objects (2026-10-01)

```text
Requested by: user ("yes start phase 7 yourself, don't wait")
Implemented and reviewed by: supervisor agent (user-selected "Opus 5.5"); approach reviewed by the advisor before coding
Files: scripts/build_animation.py (drone, ground_station, tracker_controller, pcb_bench, portfolio, PROTECTED,
  object_boxes), scripts/test_portfolio.py (8 tests), scripts/test_scene.py (rain loop exemption with reason), docs
Findings during the phase: objects were unreadable at 840 px at first (drone 1.6x and higher hover, larger tracker
  box); the new lit-scene coverage caught a positive SMIL begin on the telemetry trace.
Commands and outcomes: 110 tests pass; quality gate passes; default scene byte-identical to published assets;
  Chromium vs librsvg on a winter night at 7 times: worst cell 0 to 9 px, 0 px around the objects.
Visual evidence: 4x zooms of each object at noon, golden hour, winter night and monsoon morning; 840 px crops.
Decision: approve
```

### LO-P8 — Real Moon and planets (2026-10-01)

```text
Requested by: user ("yes start phase 8 yourself, don't wait")
Implemented and reviewed by: supervisor agent (user-selected "Opus 5.5"); approach reviewed by the advisor before coding
Files: scripts/scene_state.py (planets), scripts/build_animation.py (dome projection, in_view, moon_cells,
  sun_direction, moon_markup, planets_markup, moonlight, sky_bodies), scripts/test_sky_bodies.py (10 tests), docs
Findings during the phase: the first projection dropped a high full moon off the canvas (replaced by a dome
  projection); planets at 2-4 px were invisible at 840 px; the planet visibility curve hid Venus in civil twilight.
Not done: a real star field (no verifiable catalogue; would contradict the painted sky). Recorded for the user.
Commands and outcomes: 120 tests pass; quality gate passes; default scene byte-identical to published assets;
  Chromium vs librsvg on the 27 Oct 2026 full-moon night: worst cell 0 to 8 px; moonlight A/B difference 86.
Visual evidence: dusk crescent 13 Dec 2026, daytime quarter moon 18 Oct 2026, full moon 27 Oct 2026, 24 Jan 2027.
Decision: approve
```
