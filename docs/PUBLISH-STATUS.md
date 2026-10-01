# Publication state

Updated 2026-10-01.

**Target:** `Zenithquonta/kushmodi`, branch `main`.

## Commits

- `316e993` ("feat: observatory profile README, assets and handoff docs"): the original observatory package, pushed to `main` by the user.
- `569b58b` ("Regenerate hero at 840px with lock-on, warp and nav-light scenes"): current `main`. At the time of writing `origin/main` and `origin/ccr-19e1f533-c4auq1` both point at it, and the working tree was clean before this documentation update (not yet committed).
- Between the two, the reviewed refinements were developed on `ccr-19e1f533-c4auq1` and fast-forwarded to `main` as each part was approved and its assets were regenerated (no force-push): traffic routes (T02-R1), SVG/GIF parity (T07), preview fixes (T06), cube and moon fixes (T02-R2), animated cards plus the Rover Bay card (T13), 840px export (T08) and the lock-on, warp and navigation-light scene additions (T14). See `git log` and the `TASKS.md` review records for the exact commits.
- A local branch named `main` in an older checkout may be stale; compare with `origin/main`.

## What is live

`main` serves the README with the 840×473 GIF (240 frames, 10fps, 24s, 7,955,864 bytes), the poster PNG for reduced motion, and the 2×2 table of four animated cards with static reduced-motion twins. The full project (builders, tests, docs, ledger, source artwork, preview, workflow) is currently on `main` as well. Live rendering of the README was verified from github.com in T05, against `316e993`; the new 2×2 card table has not yet been checked on github.com.

## CI

`.github/workflows/validate-profile.yml` runs the quality gate and the unit tests with read-only permissions. Run 36819742217 on `316e993` succeeded, and every later push to `main` passed; run 36826783002 on `569b58b` (run #15) concluded `success`.

## Pending cleanup (planned, not yet done)

The user has decided that `main` will finally be reduced to `README.md` plus the images it references (`assets/observatory.gif`, `assets/observatory-poster.png`, the four `*-card.svg` and the four `*-card-static.svg` files). The full project is preserved on branch `ccr-19e1f533-c4auq1`. The user asked for it; it is scheduled after the README is updated from the user's CV. Keep the preserved branch intact. Under the plan the validation workflow, scripts and docs would exist only on that branch; no decision about CI on `main` has been recorded.
