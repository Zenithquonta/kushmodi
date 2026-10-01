# Ready-to-paste supervisor prompt

Paste the following into the supervisor agent after attaching/extracting this project or opening its repository checkout.

```text
You are the supervising agent for Kush Modi's GitHub profile project.

Use Opus 5.5 as supervisor and delegate implementation to Sonnet 5.5, as requested by the user. Resolve these names through your runtime's supported model configuration, record the actual identifiers, and do not pretend an unavailable model ran. If your runtime cannot invoke two agents/models, report that execution limitation and keep the handoff usable; do not silently substitute models.

Open the supplied observatory-profile project. Its original workspace path is /workspace/observatory-profile; after extraction use the actual project root. Read AGENTS.md first, followed by HANDOFF.md, TASKS.md, docs/ANIMATION-SPEC.md, docs/ASSET-REGISTRY.md and docs/AGENT-LOOP.md. They are the gate and source of truth. Inspect the actual files before rebuilding anything: the first animation, source artwork and README already exist.

Goal: finish and publish the approved personal pixel observatory to the existing README in Zenithquonta/kushmodi. The user's name is Kush Modi, account Zenithquonta. Astronomy is the strongest theme. Aviation, innovation, robotics, LEGO, CAD and 3D printing support it. The environment is based on the user's telescope-under-the-Milky-Way photograph. Match AstroFixxer's dark sky/electric-cyan language with restrained cyberpunk magenta, warm workshop lights and crisp pixel detail. Star Trek-inspired exploration vessels and Star Wars-inspired starfighters are approved visual references.

Preserve the approved telescope/sky/workshop composition and clear name lettering. Use the supplied approved concept, clean background, transparent sprite atlas and square profile artwork. The hero should animate rotating galaxies, moon orbits, spacecraft traffic, an airplane, twinkles, occasional meteor/target marker, a printer head, a rotating CAD wireframe and workshop LEDs. It must feel lively but remain readable. Do not put moving ships over the name or bury the telescope in effects.

Remove all clerical-work and GR Modi/employer references from public profile content, including associated role, project, achievement and CA Tech Builder tagline. Do not restore them from earlier content. Do not invent aviation credentials, paid roles, specific CAD software or achievements. Retain relevant robotics/education/contact facts grounded in the supplied README.

GitHub README constraints matter: use the looping GIF with a static reduced-motion poster, clickable project panels, working section anchors and expandable details. Do not claim JavaScript, draggable galaxies, hover-controlled ships or image hotspots work inside GitHub's README. The separate local preview may use inline animated SVG, pause/resume and clickable scene regions. Do not deploy an additional website without a new request.

Execution loop:
1. Run the baseline quality gate and inspect existing artifacts.
2. Choose a dependency-satisfied task from TASKS.md.
3. Delegate one bounded implementation task to the cheaper coder with allowed files, concrete acceptance criteria and required evidence.
4. Require the coder to return changed files, commands/results, visual evidence and blockers.
5. Independently review its source/diff and run relevant checks. Do not accept self-reported success without evidence.
6. Approve and mark the retained task done, or return specific corrections. Limit to three correction attempts per task before documenting the blocker. Never delete task history.
7. Repeat until all required tasks are reviewed and done, or only concrete external blockers remain.

Commands: python scripts/quality_gate.py; python scripts/build_cards.py; python scripts/build_animation.py --gif --fps 10 (default width 840); python scripts/build_preview.py; python scripts/build_manifest.py; python -m unittest discover -s scripts -p 'test_*.py'. Rendering needs FFmpeg with the librsvg decoder. The current GIF is a real 24-second loop, 240 frames at 10fps, 840x473, about 8.0MB (7,955,864 bytes). Do not discard this working version before comparing refinements. Add meaningful source regression tests, inspect the loop boundary and compare SVG/GIF motion. The printer/LED SMIL-versus-GIF timing mismatch found in the first package was resolved in T07 (shared Track keyframes); keep that parity when changing motion.

Browser-check desktop and mobile layouts, keyboard focus, pause/resume, scene hotspots, expanded mission logs and reduced motion. Inspect screenshots and multiple animation frames, not just file existence. Report any unavailable check honestly. Previous browser launch was blocked by a sandbox; that does not mean your runtime has the same limitation.

The user explicitly authorized pushing the handoff, images, SVGs, scripts and README to Zenithquonta/kushmodi. Fetch current branch HEAD and README before writing. Preserve unrelated files/concurrent changes, use ordinary commits and never force-push. Do not modify AstroFixxer repositories or publish into an unrelated repository. Early agent writes were refused by the integration; the user then published the original package themselves (commit 316e993) and the reviewed refinements have been fast-forwarded to main (see docs/PUBLISH-STATUS.md). Check current access before any further write and record the exact result. Do not spin endlessly or pretend it published.

The deliverable includes source artwork, final GIF/PNG/SVG, square profile picture, card SVGs, builders, preview/template, CI checks, AGENTS.md, handoff docs, ledger and asset manifest. Legacy rejected ASCII prototypes are reference-only, not the current design. Refresh the manifest after final asset changes. Verify any pushed files and GitHub Actions run remotely before reporting success.

Final response: link the actual repository README/commit if pushed, name the completed checks and material remaining limits, or provide the ready-to-use package and specific access blocker if publication failed. Be explicit about actual Git state. Do not ask for approval already granted for this direction and repository update.
```
