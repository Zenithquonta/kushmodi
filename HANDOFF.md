# Kush Modi's Pixel Observatory — full implementation handoff

This is a continuation package, not a request to start the design over. The user approved the illustrated direction and then the animation. The first animated deliverable is already built. Finish verification, resolve actual defects, refine where useful, and install the project into the user's existing repository.

![Approved concept](assets/approved-concept.png)

![Current looping hero](assets/observatory.gif)

## 1. Objective, identity and approval history

The GitHub account is **Zenithquonta**. The user's existing personal README is in **`Zenithquonta/kushmodi`**, default branch `main`. The display name, sourced from that README, is **Kush Modi**. Do not substitute the account handle for the person's name.

The original request was to improve the GitHub profile using an animated-profile reference. A preliminary ASCII profile implementation was prepared, but the user rejected its appearance. That design is now an archived prototype, not the active design. The user then described astronomy as the strongest passion, followed by innovation, aviation and things beyond reach. They asked to refer to their AstroFixxer repositories for visual language.

The user supplied a photograph of their telescope under the Milky Way and requested a pixel copy, rotating galaxies, planetary imagery, spacecraft, ships, LEGO, 3D printing, CAD, Star Trek/Star Wars influences, and a little cyberpunk. The proposed visual direction was approved. A generated still banner was then shown and the user said it was a good starting point and approved making it animated.

The user explicitly requested removal of clerical-work/employer references and does not want that part of their work shown at this stage. The current public README has been rewritten accordingly. The user also explicitly requested a detailed handoff, all supplied images/SVGs/scripts, an agent supervision loop, and pushing the work to GitHub. No further approval is required for those already-authorized actions in this repository.

## 2. Visual brief

The composition is a personal observatory at the edge of space. The telescope from the real photograph anchors the foreground. There are trees and a dark rocky/campsite horizon, warm city lights and mountains in the distance, a broad teal Milky Way and a deep navy sky. On the right, an open maker workshop has amber windows, restrained cyan/magenta LED strips, a printer, CAD display, interlocking construction bricks, a small brick-built spacecraft, and a rover.

Astronomy is dominant. The spacecraft and workshop support the telescope rather than taking over the scene. Typography must stay readable: `KUSH MODI`, `BUILDING TOWARD THE UNEXPLORED`, and `ZENITHQUONTA // OBSERVATORY`.

The artwork takes AstroFixxer's dark background, electric cyan (`#00bfff`) and celestial targeting language into an illustrated pixel environment. It uses deliberate pixel clusters, dithered light and stepped edges. The space should feel expansive; the cyberpunk aspects are small instruments, holography and LEDs, not a dense neon city.

The user approved Star Trek-inspired exploration vessels and Star Wars-inspired starfighters as visual references. Do not add combat, explosions or massive fleets. Aviation is represented by a small passenger airplane crossing below the starfield. It is an interest, not an invented pilot or aerospace employment credential.

## 3. What exists now

| Item | Status | Location |
| --- | --- | --- |
| User's original telescope photo | Supplied and retained | `assets/reference-telescope.jpg` |
| Approved still banner | Supplied and retained | `assets/approved-concept.png` |
| Clean animation background | Generated from approved banner | `assets/observatory-background.png` |
| Transparent sprite atlas | Generated to match banner | `assets/space-sprites.png` |
| Square pixel profile picture | Generated; needs small-size review | `assets/profile-picture.png` |
| Animated layered SVG | Built, structurally checked | `assets/observatory.svg` |
| Static SVG at first frame | Built | `assets/poster.svg` |
| Static PNG poster | Rendered with FFmpeg/librsvg | `assets/observatory-poster.png` |
| Looping GIF | Exported and metadata/motion checked | `assets/observatory.gif` |
| Three clickable navigation card SVGs | Built | `assets/*-card.svg` |
| Public README rewrite | Prepared locally | `README.md` |
| Interactive local preview | Generated; browser review pending | `preview.html` |
| Preview template and rebuild script | Supplied | `preview.template.html`, `scripts/build_preview.py` |
| Reproducible animation builder | Supplied | `scripts/build_animation.py` |
| Asset quality gate | Supplied and passing at initial check | `scripts/quality_gate.py` |
| CI workflow | Prepared, not remotely run yet | `.github/workflows/validate-profile.yml` |
| Agent gate, protocol, prompt and ledger | Supplied | `AGENTS.md`, `docs/AGENT-LOOP.md`, `SUPERVISOR-PROMPT.md`, `TASKS.md` |
| Earlier rejected ASCII SVGs | Reference-only archive | `assets/legacy/` |

The GIF is an actual animation: **1000×563**, **240 frames**, **10fps**, **24 seconds**, infinite looping, **11,744,470 bytes** at the initial export. The active SVG initially has **98 animation elements**. The source background is 1672×941; the sprite atlas is 1536×1024 RGBA. Inspect the current manifest for final file hashes and metadata rather than relying on prose after later changes.

## 4. Project structure and asset use

```text
AGENTS.md                     agent entry point / gate
HANDOFF.md                    this document
SUPERVISOR-PROMPT.md          ready-to-paste startup instruction
TASKS.md                      retained execution/review ledger
README.md                     public profile
preview.template.html         interactive preview source template
preview.html                  generated self-contained SVG preview
requirements.txt              Pillow for verification only
.github/workflows/validate-profile.yml
assets/
  approved-concept.png
  reference-telescope.jpg
  observatory-background.png
  space-sprites.png
  profile-picture.png
  observatory.svg
  poster.svg
  observatory.gif
  observatory-poster.png
  observatory-card.svg
  flight-card.svg
  fablab-card.svg
  MANIFEST.json
  legacy/
scripts/
  build_animation.py
  build_cards.py
  build_preview.py
  quality_gate.py
  test_scene.py
docs/
  ANIMATION-SPEC.md
  ASSET-REGISTRY.md
  AGENT-LOOP.md
  PUBLISH-STATUS.md
```

Only the GIF/poster and navigation cards are referenced by the public README. The SVG and source images remain available for inspection and regeneration. The local preview embeds the SVG inline for actual browser interactions. It is not a hosted website and should not be deployed without a separate request.

Retain the approved concept and user photo. If the artwork needs artistic changes, use an image-generation/editing tool and the approved references. Do not overwrite the approved source with a later experiment. Crop/viewbox changes for scene composition belong in the builder; modifications to painted source content need an artistic image edit.

## 5. Reproducible build

Use Python 3.12 or another compatible Python 3 version. The builder uses the Python standard library and an external FFmpeg executable. The quality gate uses Pillow to inspect image metadata, alpha and sampled frames.

```bash
python -m pip install -r requirements.txt
ffmpeg -hide_banner -decoders
python scripts/build_cards.py
python scripts/build_animation.py --gif --fps 10 --width 1000
python scripts/build_preview.py
python scripts/quality_gate.py
python -m unittest discover -s scripts -p 'test_*.py' -v
```

Confirm that the FFmpeg decoder listing includes **librsvg**. This is necessary to rasterize the layered SVG frames. Do not mistake the presence of the FFmpeg command alone for SVG support.

The builder reads the two source PNGs into data URIs, generates the animated SVG and a static SVG, rasterizes the static poster, then optionally exports every time sample for the GIF. Four render workers are used. Each temporary SVG is removed after its PNG frame is produced; the temporary directory is removed after successful completion. A render temporarily consumes significant disk space for PNG frames. The final artifact generation used four workers successfully in the original workspace.

The GIF pipeline creates a shared 256-color palette from all frames and uses ordered Bayer dithering. This avoids a different palette per frame and reduces distracting color flicker. Avoid changing palette strategy without viewing the result at normal README size.

The loop period is 24 seconds. Most local subloops are divisors of 24 so the scene can wrap cleanly. Review geometry at the wrap rather than assuming mathematically periodic movement guarantees a perceptually clean last-frame transition.

Do not regenerate a GIF after every prose change. A new export is necessary after animation source or source artwork changes. Rebuild `preview.html` after changing `observatory.svg` or its template. Regenerate the asset manifest after final asset changes.

## 6. Animation implementation

The detailed map is in `docs/ANIMATION-SPEC.md`. The builder's major functions are:

| Function | Responsibility |
| --- | --- |
| `png_uri` | Read a source PNG into an embedded data URI |
| `sprite` | Select one atlas region through a nested SVG viewport and position its origin |
| `rotate_node` | Place and rotate a sprite, with SMIL for the animated export |
| `celestial` | Main/secondary galaxies, ringed planet and two projected moon orbits |
| `traffic` | Exploration ship, two fighters and aviation plane with attached trails |
| `cube_points` | Project a yaw-rotating 3D wireframe cube into the workshop display |
| `workshop` | Cube edge motion, printer nozzle/scanning line and status LEDs |
| `sky_details` | Deterministic star twinkles, targeting path, reticle and occasional meteor |
| `layers` | Scene painter order |
| `scene` | Build complete SVG, including reduced-motion static alternative |
| `rasterize` | Render an SVG into PNG using FFmpeg/librsvg |
| `export_gif` | Generate sampled frames, shared palette, looping GIF and first-frame poster |

The source artwork is a background layer and a single sprite atlas referenced once by ID. Every moving object's viewport reuses the atlas. This keeps geometric logic inspectable and avoids per-frame artistic regeneration. Both SVG and GIF use the same scene functions, with either SMIL elements or time-sampled coordinates.

There are known review points: some workshop SMIL paths use linear interpolation while the raster version samples sine; moon draw order does not currently make the moon fully disappear behind the planet; the galaxy is a stylized rotation, not a simulation; and the spacecraft/planet sprite atlas margins need inspection while objects rotate or move. These are concrete review/refinement tasks, not hidden failures.

The first poster was inspected. An unintended filled open targeting path created a dark wedge across the sky; that was corrected by explicitly setting `fill="none"` and the animation was rerendered. Retain a regression check for open stroked trajectories so this artifact does not return.

## 7. README content and interaction

The current README is a new coherent observatory layout rather than a generic badge wall. It uses the GIF as the hero and the static PNG for reduced-motion users through `<picture>`. Four links lead to section headings. Three image panels lead to Observatory, Flight Deck and Fab Lab. Each main section contains a `<details>` mission log.

The content is intentionally grounded:

- Astronomy as the main interest, based on the user's explicit statement and telescope image.
- Aviation and science fiction as interests, not invented professional experience.
- LEGO, CAD and 3D printing as explicitly requested hobbies.
- Robotics, NMIMS MPSTME, Darwin Club, tools and hardware from the user's existing README.
- Existing reported IGVC milestones retained as the user's project-log claims; they were not independently verified.
- AstroFixxer links point to the supplied repositories, not a guessed new deployment.
- Existing GitHub, LinkedIn and email links are retained.

Do not put the removed employment content into a tooltip, a collapsed section, an SVG title, a generated tagline or an old typing URL. Search URL-decoded public content as well as ordinary words.

GitHub README cannot run JavaScript interaction inside an embedded image. Expandable mission logs, ordinary anchors and linked panels are the supported interactions. Actual drag/pan controls, interactive flight or image hotspot controls belong in a separate page. The current standalone preview provides some of that interaction locally; the README makes no claim that those controls run on GitHub.

## 8. Local preview

Open `preview.html` in a browser, or serve the project directory with:

```bash
python -m http.server 8000
```

Then visit `http://localhost:8000/preview.html` in that execution environment. Serving is useful if a browser restricts local file behavior. It does not publish a website.

The SVG is inline so its `pauseAnimations`/`unpauseAnimations` methods can be controlled by the page. Hotspot buttons over the telescope, workshop and planet open and scroll to the corresponding mission logs. They have accessible names, visible keyboard focus and hover outlines. Navigation card links perform the same log-opening behavior. `<details>` remains usable without JavaScript for basic content disclosure.

Reduced-motion media hides the animated SVG layers and shows the static layer. The preview disables its motion toggle under that preference. The README uses a separate static PNG source. Test both; one does not prove the other works.

Browser launch in the originating execution sandbox previously failed with a crashpad socket-permission error. The project therefore distinguishes source review and rendered-frame verification from actual interactive browser verification. Do not mark T06 complete until your runtime successfully performs that browser check.

## 9. Verification and current results

The quality gate checks local README image/anchor resolution, disclosure structure and removed-work absence; parses SVGs and checks IDs, animation key times and embedded resource references; verifies the GIF's actual frame count, infinite loop, duration, dimensions, differing sampled frames and byte budget; and checks atlas transparency.

The initial quality gate passed. It measured 240 frames at 24 seconds and found different content in at least three of four sampled frames. This is evidence of actual animation, not a substitute for assessing its visual rhythm.

The CI workflow installs Pillow, runs the quality gate, and discovers source regression tests. It has read-only repository permissions. It does not regenerate images, rewrite README text, fetch private GitHub activity or deploy anything. It will not have run remotely until the project has been pushed.

Future visual verification should inspect the scene at 0, 3, 6, 12, 18 and 23.9 seconds, then play at normal speed. Check scene layout at approximately 1000px and 390px widths, readable typography, telescope visibility, ship collisions, clipping, transparent sprite edges, painter order, printer/cube registration and continuity at wrap.

## 10. GitHub publication status and strategy

At handoff, no GitHub README change has been confirmed. The actual writes attempted earlier returned **403: Resource not accessible by integration**. Repository metadata reported `push:false`. The account installation later showed `repository_selection: all`, but this did not make the active connection's write succeed. Treat those as separate observations; do not claim the connection is writable merely because the installation UI was changed.

Target only `Zenithquonta/kushmodi`. Earlier the connected tool listed a different private repository as writable; that is unrelated and must not receive this work. Do not bypass the failed credentials, print secret values, invent a token, or open an interactive login without appropriate runtime/user setup.

When actual write access is available:

1. Fetch the current branch and README and record HEAD.
2. Preserve unrelated repository files and any concurrent user edits. Use a checked-out Git worktree or a Git tree based on current HEAD.
3. Include the complete project, including handoff and artwork, in a coherent commit. Exclude temporary frames, caches, virtual environments and local runtime logs.
4. Push normally, without force.
5. Fetch the committed README/assets from GitHub, inspect their rendering and wait for the validation workflow result.
6. Record the actual commit SHA and workflow run URL in the ledger/publication status.

GitHub profile-top README behavior requires a public repository with a name equal to the account handle. The user explicitly chose updating the existing `kushmodi` README. Do not rename or create a `Zenithquonta` repository automatically. The deliverable can work as a repository README while that separate profile-top naming question remains outside the current scope.

## 11. Agent execution and remaining work

Use `AGENTS.md` as the entry gate and `docs/AGENT-LOOP.md` for delegation. The user-selected supervisor/coder names must be resolved to actual supported runtime identifiers. There is no hardcoded provider login or fake background model daemon.

The next supervisor should first inspect the already-working scene, rather than remake it. The highest-value remaining work is browser testing, animation interpolation/parity review, size/clarity optimization, source regression checks, and actual Git installation. The ledger documents those dependencies.

The endpoint is a verified, visually reviewed profile and complete handoff in the actual repository. If GitHub access remains blocked, the correct endpoint for the current runtime is a ready-to-use package plus the exact failed operation and remaining task state. Do not present local files as a successful Git push.
