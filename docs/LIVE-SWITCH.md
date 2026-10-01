# Switching the README to the live view (Phase 12)

The README hero sits between `<!-- hero:start -->` and `<!-- hero:end -->`. `scripts/readme_live.py` switches only
that block; `config/observatory.json` (`live.host`) records the host. On `main` it stays in **repo mode** (the
committed animation) until every step below has passed.

## No automatic fallback

GitHub removes `onerror`, and `<picture>` chooses a source by media query, not by whether it loads. If the server is
down while the README points at it, visitors see a broken image. Live mode therefore shows a small link to the
repo animation under the picture, and switching back is one command (`readme_live.py repo`, byte for byte). The
alternative is to keep the repo animation as the hero and add the live view below it. The user chooses.

## Procedure (needs the real host)

1. On the server: `sudo bash /opt/observatory/repo/deploy/check.sh HOST` passes.
2. Burn-in: let it run for a few days; `check.sh` still passes.
3. From your own machine or the server: `python3 scripts/probe_live.py HOST` passes (the build session's network
   proxy cannot reach arbitrary hosts) (200 and the right type for the three files, live.json
   under 15 minutes old, 404 elsewhere).
4. On the development branch, never `main`: `python scripts/readme_live.py live --host HOST`, run the gate and the
   tests, commit and push the branch, open the branch README on github.com and record:
   - GitHub's image proxy (camo) serves the SVG at all, with which content type, and accepts its size (~2 MB);
   - the SVG animates inside `<img>` (SMIL);
   - with reduced motion, the `<source>` selects `live.png`;
   - freshness: fetch the camo URL, wait more than the 240 s `max-age`, fetch again, and compare (bytes, or the
     moment in `live.json` for the same render cycle).
   Do not rely on remembered limits for camo; measure them.
5. If the SVG is refused or does not refresh: use `live.png` as the image instead (about 440 KB) and say so.
6. Only then merge to `main`. To go back at any time: `python scripts/readme_live.py repo`, commit, push.
