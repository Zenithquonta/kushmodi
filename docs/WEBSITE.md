# Living Observatory website (Phase 16)

An explorable, pixel-art 3D version of the observatory, hosted from `site/` by the existing Caddy on
https://observatorysky.duckdns.org/. It is the same world as the README art (night plate, telescope, maker shed,
rover, van, Mumbai skyline) with a real, live sky. Static files only: no build step, no server code, no uploads, no
user input.

## World layout

Metres. Y is up. **-Z is north, +X is east, +Z is south.** With the camera at yaw 0 (looking down -Z) west is on the
left and east on the right, as the user asked. Ground height is a function `groundHeight(x, z)` in
`site/js/terrain.js`; the numbers below are footprints on the flat crown of the hill.

| Thing | Position (x, z) | Notes |
| --- | --- | --- |
| Player start | (0, 16) | facing north (yaw 0), eye height 1.7 m |
| Hill crown | radius 0 to 30 | flat; slopes away to about radius 90, then a plain with ridges to the east, south and west |
| Telescope | (-7, -4), drawn 1.5 times life size | equatorial mount (polar axis tilted to latitude 19.076 degrees) on a tripod; the tube points at the object chosen by the sky |
| Maker shed | (17, -9), 8 x 5 m, open front facing south-west | roof, workbench, glowing wall screen, 3D printer with a rocket, LEGO starship on a shelf, lantern with a warm point light, neon strips |
| Rover and robot | (-15, 7) | six-wheel rover with a mast camera and a small robot beside it |
| Overland van | (-24, -15) | parked at the western edge, warm window glow |
| Drone pad | (9, 11) | painted pad with a small quadcopter |
| Mumbai skyline | z = -760, x -320 to 320 | silhouette boxes with lit windows and red beacons on the north horizon |
| Fence posts | radius 46 | the soft walking boundary |

Pixel look: the WebGL canvas is rendered at about a third of the window size (one half on screens narrower than 600
px, where a third would be too coarse) and scaled up with CSS `image-rendering: pixelated`. No antialiasing, flat or Lambert colours from a small palette,
linear fog toward the horizon colour.

## Controls

- Desktop: `W A S D` move (Shift runs), arrow keys up/down move and left/right turn, mouse look with pointer lock
  (click the scene; `Esc` releases). Left-drag looks without pointer lock. `E` or a click on the telescope shows the
  object it points at. `C` toggles constellation lines, `H` toggles the HUD help.
- Touch: an on-screen joystick (lower left) moves, dragging anywhere else looks, a tap on the telescope shows its
  target.
- Collision: circles and boxes for the telescope, shed walls, van and rover; a soft radius limit keeps the player on
  the hill.
- `prefers-reduced-motion`: no head bob, no hovering drone or patrolling robot, no lightning, no sparkle. The sky still
  moves with the real clock because that is the point of the site.
- `scripts/site_browser_check.mjs` is the real-browser check (Chromium through Playwright with software GL, against the
  site served by Caddy with the repository's template, so the Content-Security-Policy is really in force).
- Test hooks (URL parameters, harmless for visitors): `?time=ISO8601-with-offset` starts the simulated clock there and
  lets it run, `?speed=N` multiplies the clock rate, `?heading=DEG` and `?pitch=DEG` set the view.

## Sky model

Computed in the browser from the visitor's clock (or the test hook) for Mumbai (latitude 19.076, longitude 72.8777,
elevation 14 m, read from `config/observatory.json` by `scripts/build_site_data.py` into `site/data/site.json`).

- `astronomy-engine` supplies `Rotation_EQJ_HOR(time, observer)`, the J2000 equatorial to horizontal rotation
  (precession and nutation included). Horizontal axes are x = north, y = west, z = zenith; the world is
  `(east, up, south) = (-y, z, -x)`. Stars, the Milky Way and constellation lines live in a group that holds this one
  matrix, so they turn with the sidereal day.
- Stars: Yale Bright Star Catalog 5, V < 6.0 (about 5000 stars), as `[ra_deg, dec_deg, mag, kelvin]`. Points are sized
  by magnitude, coloured by temperature and faded by a limiting magnitude that rises from about -2.5 in daylight to
  5.6 at astronomical night, then lowered by cloud cover and moonlight.
- Milky Way: the d3-celestial contour polygons, simplified at build time and filled into a small equirectangular canvas
  in the browser, which a sky-dome shader samples by J2000 direction.
- Constellation lines: d3-celestial, simplified.
- Sun, Moon and Mercury to Neptune: `Equator(body, time, observer, false, true)` (topocentric, J2000, aberration), then
  the same rotation, with magnitudes from `Illumination`. Their angular size is exaggerated (Sun and Moon about 3 to 4
  degrees across) because the picture is about 240 pixels tall; this is stated in the HUD help. The Moon is a lit
  sphere whose terminator comes from the true Sun direction, so phase and bright-limb tilt are real.
- Sky colour from the Sun's altitude (day, golden hour, civil, nautical and astronomical twilight, night), posterised
  into bands; a warm city glow on the north horizon at night; horizon haze matching the fog.
- Telescope pointing: the highest of the Moon and the planets brighter than magnitude 3 above 5 degrees, else the
  highest star brighter than magnitude 2 above 15 degrees, else Polaris. The Sun is never targeted. Clicking it shows
  name, RA, Dec, altitude, azimuth.
- Trails: the Moon and each planet leave a comet-like line over the path of the last three hours (36 segments of 5
  minutes, computed with `bodyTrails()` every 30 seconds of sky time), brightest at the body and fading to nothing at
  the oldest point; the head follows the body at every refresh. A trail fades with its body's visibility (limiting
  magnitude), so under heavy cloud or for Uranus and Neptune it is not drawn.
- The sky is a full 360 degrees: the sky objects sit on a sphere of 5 km radius, beyond the 2.6 km terrain, so the
  ground hides them through the depth test and the visitor can look in every direction (the start view faces north).
- Positions and the sidereal rotation are refreshed every 2 seconds of simulated time (sub-pixel at real speed); the
  telescope slews smoothly between refreshes.

## Data flow

```
config/observatory.json --build_site_data.py--> site/data/site.json
BSC5 + d3-celestial   --build_site_data.py--> site/data/stars.json, milkyway.json, constellations.json
browser clock (+ ?time) --astronomy-engine--> sky, HUD, telescope target
/live.json (renderer, every 15 min) --fetch, validated--> weather (clouds, rain, fog), season, greenery
```

`/live.json` is data, never markup. Strings are checked against a whitelist or a strict pattern and are only ever shown
with `textContent`; numbers are clamped. A missing or malformed file gives the default (fair weather, season from the
date). It is re-fetched every 5 minutes.

## Performance budget

- Transfer of `site/` excluding `/live.*`: under 2.5 MB gzipped (target about 0.8 MB: three.js 420 KB, astronomy-engine
  108 KB, data 150 KB, own code 40 KB).
- Render target about a third of the window, device pixel ratio capped at 1.5, 60 fps on a desktop.
- Draw calls: below about 120 (merged geometry per material), one `Points` for stars, one `LineSegments` for
  constellations, lights limited to a hemisphere light, one directional light and three point lights.
- Allocation-free frame loop (reused vectors); body ephemerides every 2 s, not every frame.

## Accessibility and fallback

- The page is a plain readable HTML document first. If JavaScript is off, WebGL is unavailable or the context cannot be
  created, that document stays visible: name, tagline, `/live.svg` (with `/live.png` for reduced motion) inside
  `<noscript>` or created by script on failure, the four portfolio sections taken from the README, and the three
  contacts. When the 3D scene runs, the text stays in the DOM for screen readers behind a visible "Text version"
  button, and the canvas has a label. The HUD is real HTML with an `aria-live` region for the telescope readout.
- Controls are never mouse-only: keyboard and touch work, focus is visible, contrast of HUD text is at least 4.5:1.
- Content is only what the README says: no employer, clerical or automation work, no invented achievements.

## Security

- Caddy serves the site at `/` from the repository's `site/` directory with
  `Content-Security-Policy: default-src 'self'; img-src 'self' data:; connect-src 'self'; style-src 'self'; script-src
  'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer` and a `Permissions-Policy` that disables camera, microphone and geolocation.
- No CDN, no third-party request at runtime, no inline script or inline `style=` attribute. Libraries are vendored and
  pinned with their licence files.
- No `innerHTML`, `eval` or `new Function` with dynamic data anywhere in `site/js`.
- Everything outside `site/` and the three live files still returns 404; there is no directory listing; `*.md` files inside `site/` are
  hidden, and only an allowlist of paths is served at all.
- The service user cannot write to `site/`; code reaches the server only through `deploy/update.sh`.

## Milestones

- **M1 (this change):** walkable observatory, real live sky, HUD, telescope readout, fallback page, Caddy deployment,
  tests and browser verification.
- **M2:** portfolio stations from the README content in the world (drone station for NETRA and the micro drone, fab lab
  bench, rover bay for Team Darwin, a telescope-mount plinth for the star tracker), each opening a text card; sound
  off by default; a guided "tour" mode.
- **M3:** shared story beats driven by `live.json` (opposition, meteor showers, season changes, the daily log) so the
  world narrates what the renderer already knows, and an archive gallery wall from `archive/`.

## Sources and licences

three.js 0.186.1 (MIT), astronomy-engine 2.1.19 (MIT), Yale Bright Star Catalog 5 via
brettonw/YaleBrightStarCatalog, d3-celestial (BSD 3-clause). Details and licence text are in `site/vendor/` and
`site/data/SOURCES.md`.
