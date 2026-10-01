# Gate and entry point for agents continuing this project

Read this file, then `HANDOFF.md`, `TASKS.md`, `docs/ANIMATION-SPEC.md`, and `docs/AGENT-LOOP.md` before changing the project. `SUPERVISOR-PROMPT.md` contains a complete startup prompt.

## User-approved objective

Update the existing README in `Zenithquonta/kushmodi` into a personal pixel observatory for **Kush Modi**. Astronomy comes first; aviation, innovation, robotics, LEGO, CAD, and 3D printing support it. Base the environment on the user's telescope photograph. Preserve the approved visual direction, but refine implementation problems found by inspection.

The user approved the first visual preview and subsequently approved making it animated. The user also explicitly requested pushing the handoff, images, SVGs and implementation files to GitHub. These actions are authorized within this repository. Do not ask for the same approval again. GitHub credentials or permissions may still block execution; record the actual error and continue independent local work.

Remove employer/clerical-work references from public profile content. Do not recreate them through old README content, descriptions, typing animations, achievement tables, generated artwork captions, or previous prototype configurations.

## Roles

The user requests **Opus 5.5 as supervisor** and **Sonnet 5.5 as coder**. Treat these as user-selected model names, not evidence that the current runtime supports those exact identifiers. Use the runtime's available model listing/provider configuration to resolve them. Do not invent an API model identifier, claim an unavailable model ran, or silently substitute a model. Record the actual model identifiers used. If separate models cannot be invoked, explain that specific execution limitation and keep the artifacts usable by another runtime.

The supervisor decomposes tasks, sets acceptance criteria, delegates narrow implementation tasks, independently checks evidence, requests corrections, and maintains the task ledger. The coder implements assigned tasks and returns changed files, verification evidence, unresolved issues, and a concise summary. The supervisor does not approve a task merely because the coder says it is done.

## Scope and file ownership

- `README.md`: public personal profile and GitHub-supported interactions.
- `assets/`: source artwork, final GIF/PNG/SVG output, and archived rejected prototypes under `assets/legacy/`.
- `scripts/`: reproducible animation/card/preview builders and verification.
- `preview.template.html`: interactive browser preview template. `preview.html` is generated from it and the SVG.
- `HANDOFF.md`, `docs/`, `TASKS.md`, `SUPERVISOR-PROMPT.md`: execution instructions and evidence.
- `.github/workflows/validate-profile.yml`: CI verification; it does not deploy a website or rewrite profile content.

Do not edit the AstroFixxer repositories as part of this task; they are visual/project references. Do not publish to the only unrelated repository that may be writable. Do not create a new profile repository, rename `kushmodi`, change visibility, or delete existing repository content without an explicit new instruction. The current objective is the user's existing README.

## Required execution loop

Use the state machine in `docs/AGENT-LOOP.md`. Preserve completed tasks with evidence rather than deleting their records. Stop when all required tasks are reviewed and complete, or when a concrete external blocker prevents the remaining tasks. Use bounded correction loops. Do not spin indefinitely on missing GitHub write access.

## Evidence rules

1. Check the current files before implementing. Much of the artwork and first animation already exists.
2. Run `python scripts/quality_gate.py` after changes to the README/assets.
3. Run `python -m unittest discover -s scripts -p 'test_*.py' -v` after source changes once the tests exist.
4. Inspect rendered frames and real browser playback. A valid SVG or GIF metadata check alone is not visual approval.
5. Distinguish browser-verified behavior from code-reviewed behavior. Previous browser launches were blocked by the execution sandbox.
6. Before Git writes, fetch the live README and branch HEAD. Preserve unrelated concurrent edits. Never force-push.
7. Verify the final README and workflow from GitHub after a successful push. No live deployment has occurred merely because local files exist.

## Image workflow

The original photograph, approved concept, background plate, transparent sprite sheet, and square profile artwork are supplied. Retain their originals. Use an image-generation/editing capability for further artistic image edits, and reference the approved image. The Python builder composes independently authored layers into SVG animation and exports frames through FFmpeg/librsvg. Pillow in the quality gate inspects image metadata and sampled frames; it is not the artwork editor.

No unrequested email, Slack, comments to third parties, site deployment, or public announcements are part of this task.
