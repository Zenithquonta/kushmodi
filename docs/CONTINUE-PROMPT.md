# Continue the observatory website

Resume branch `wip/observatory-polish` in `Zenithquonta/kushmodi`. This branch contains the current website work for review; do not merge it into main or deploy it until the remaining checks and user review are complete. The user requested stopping work and pushing the complete continuation package on 2026-10-04.

## Execution roles and scope

The user's latest role instruction supersedes the historical role names in AGENTS.md: **Astra orchestrates, reviews and requests corrections; all coding, image generation and implementation must be delegated to Sol 6.1**, using runtime `gpt-6.1-sol` where available. Do not silently substitute a different implementation model. Keep these names in this execution handoff, not production content.

The user wants a dense, detailed walkable observatory environment inspired by `assets/observatory-background.png` and `assets/approved-concept.png`. **Use the real Mumbai sky simulation only.** Do not restore the discarded illustrated sky or add a sky mode switch. Thin circles/name tags identify actual planets in the current view. Visitors must be able to approach the telescope, enter with E/click/a nearby button, and see an explicitly labelled pixel-art illustration of the real object selected for that observing night. The target remains stable across midnight, tracks actual coordinates, and changes over successive nights. Daylight and below-horizon states must be honest.

Keep public profile content and exclusions intact. Do not edit archive or backend renderer code. The older unfinished `wip/walkable-world` expansion is separate future work, not a dependency of finishing this pass.

## Current implementation and evidence

- Compact telescope/workshop/van clearing, detailed foliage atlas, rocks, gravel, foreground grass/flower beds, layered ridges, maker workbench and signs, lighting, antialiased rendering, responsive controls.
- Generated source: `assets/website-foliage-source.png`; optimized transparent atlas: `site/data/foliage-atlas.webp`; complete prompt/provenance: `docs/WEBSITE-ART.md`.
- Planet guides use the same computed direction vectors as the sky. Faint planets are marked “telescope”. Offscreen/below-horizon/terrain-occluded labels are hidden; toggle is implemented.
- Noon-to-noon IST target picker uses a deterministic nightly choice and filters for evening visibility. Eyepiece supports stars, planet discs/rings and Moon phases. Dialog pauses movement, makes the background inert, traps focus, and supports close/E/Escape. Current sky positions/clock and weather calculation modules were preserved.
- `python -m unittest discover -s scripts -p test_site.py`: **25 tests OK, 1 Caddy skip**. Includes target stability through midnight/reload, coordinate updates, successive-night variation, never Sun, and evening/daylight checks.
- `python scripts/quality_gate.py`: **passed**. `git diff --check`: **passed**, with normal Windows line-ending warnings.
- Independent visual review approved the landscape and Altair eyepiece direction. Saved views: `docs/review/site-night.png`, `site-telescope.png`, `site-mobile-eyepiece.png`. These are fixed night test views, not the actual clock or live weather.
- The expanded browser regression completed but **failed one assertion: `walking resumes after modal`**. Its report is `docs/review/browser-results.txt`; do not claim the browser suite passes. Other assertions did not report failures. Investigate the failed movement behavior before approval; the cause has not been established.
- The focused click/below-horizon test was **stopped at the user's request before returning a result**. `scripts/site_interaction_check.mjs` also now includes a real Oct5 Saturn eyepiece capture; that added capture is unrun. Do not claim these checks pass.
- Earlier complete backend Python testing was blocked by Windows/Unix dependencies and temporary Git cleanup behavior. Repository-wide backend verification is not certified; do not repeatedly run it for these website changes. Renderer code and original README art were not changed.

## Resume in this order

1. Read AGENTS.md, HANDOFF.md, TASKS.md, this guide, and the saved visual/report evidence. Inspect the current files before implementing. Fetch origin/main; preserve its daily archive commits and unrelated changes. Never force-push.
2. Delegate the unresolved movement-after-modal investigation to the required implementation model. Check real movement pause/resume, E/Escape/close, proximity, click, pointer lock, and mobile close. Correct a demonstrated defect or repair the assertion if evidence proves it was a test timing issue; do not assume either.
3. Run the focused telescope checks, including an actual nightly Saturn selection, below-horizon blank eyepiece and nearby click. Review the resulting screenshots. Run the expanded browser suite and resolve remaining failures, including guide alignment/toggle/offscreen behavior, daylight and mobile layout. Finish with site tests, quality gate and diff checks.
4. Obtain independent supervisor review of the final implementation/evidence. Show the user the local preview with the actual clock, alongside clearly labelled fixed-night screenshots. Weather in the fixture preview is seasonal default, not current live weather.
5. Only after review, handle the user's next publication/deployment instruction. Current authorization was to push this working branch and preserve a guide, not to merge unreviewed work into main or claim VPS deployment.

## Reproduce locally

```sh
git clone https://github.com/Zenithquonta/kushmodi.git
cd kushmodi
git checkout wip/observatory-polish
python -m venv .venv
# Activate .venv for your operating system.
python -m pip install -r requirements.txt
# Windows additionally needs tzdata.
python scripts/site_preview.py --port 8099
```

In another terminal, visit `http://127.0.0.1:8099/` for the actual clock. The local preview serves `site/`, uses the production CSP, returns `{}` for `/live.json`, and serves existing fallback artwork for `/live.svg` and `/live.png`. The real astronomical sky still derives from the browser clock; weather falls back to seasonal defaults.

```sh
python -m unittest discover -s scripts -p test_site.py
python scripts/quality_gate.py
node scripts/site_browser_check.mjs http://127.0.0.1:8099 work/browser-check
node scripts/site_interaction_check.mjs http://127.0.0.1:8099 work/browser-check
git diff --check
```

Browser scripts require Playwright with Chromium installed. Set `PLAYWRIGHT_PATH` to an existing Playwright package if it is not on Node's normal module path. On the originating Windows machine the package was `C:/Users/kush/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright`; the Python environment was the sibling `../venv/Scripts/python.exe`. Those machine paths are optional local conveniences, not project dependencies. Use `--planet-only` on the focused script to capture only the real Oct5 Saturn selection. No illustrated sky is shipped.
