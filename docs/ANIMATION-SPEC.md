# Scene geometry, motion and rendering specification

## Coordinate system and palette

The artwork coordinate system is **1672×941**. SVG uses the same `viewBox`. The GIF and poster are rasterized to width 840 (`GIF_WIDTH`) and proportional height 473. Do not independently stretch either axis. A responsive page should fit the scene to its container while preserving its aspect ratio.

The quiet text region is roughly x=30..565 and y=218..375. Avoid moving large objects across that region. The telescope occupies the lower-middle, around x=750..860 and y=550..820. The maker workshop occupies the lower-right, starting near x=1170/y=530 and continuing to the right/lower edge. Preserve these landmarks when refining the art.

The matte colors are near-black, midnight blue and teal. Cyan instrument/target colors are around `#00bfff`, `#40daed`, `#72f0ff`. Magenta accents around `#ed78fc` should stay small. The background and artwork supply rich pixel dithering; do not add a full-scene Gaussian blur, glossy gradient panels or a dense overlay of badges.

## Source assets

![User source photograph](../assets/reference-telescope.jpg)

![Clean background](../assets/observatory-background.png)

![Transparent sprite atlas](../assets/space-sprites.png)

The background is a carefully edited plate based on the approved concept. Floating sky objects were removed so the renderer can place and animate them independently. The telescope, typography, horizon, buildings and workshop are part of this stable image. It still contains the base printer, CAD display and brick craft; animation details are layered above those objects.

The atlas has six independently usable objects: spiral galaxy, ringed planet, exploration ship, fighter, passenger aircraft and moon. The tool-generated sheet was requested as a 3×2 grid but actual painted margins differ. The builder therefore uses explicit source rectangles and origins rather than blindly treating each cell as a perfect 512px square.

| Sprite | Source rectangle x,y,w,h | Painted origin x,y | Reason |
| --- | --- | --- | --- |
| Galaxy | 0,45,510,545 | 300,328 | Keep the diffuse arm silhouette and rotate around the actual bright core |
| Planet | 512,190,522,315 | 784,346 | Include all diagonal rings without neighboring ship pixels |
| Explorer | 1035,245,500,220 | 1278,346 | Include saucer and both nacelles with a stable hull-centered origin |
| Fighter | 64,680,448,280 | 288,821 | Include splayed wings and bright engines |
| Aircraft | 520,700,515,205 | 784,815 | Include fuselage, wings, tail and nose |
| Moon | 1170,655,300,290 | 1298,805 | Retain its complete crescent silhouette and halo |

These coordinates are part of the current implementation, not an immutable aesthetic rule. If another sprite atlas is generated, inspect it, measure new rectangles/origins and update the map. Do not assume the replacement tool returns identical dimensions.

`sprite()` builds a nested SVG viewport with the source rectangle as its viewBox and a `<use>` reference to the atlas image. Scaling is uniform. Its x/y offset places the chosen painted origin at the containing node's origin. This prevents rotating a galaxy around the geometric centre of a padded cell instead of its core.

## Scene painter order

`layers()` returns, in order, over the background plate:

1. Celestial: main and secondary galaxy, orbital guide, the two "behind" moon copies, the planet, then the two "front" moon copies.
2. Traffic: the explorer, two fighters and airplane (with trails, warp markup and, on the airplane, navigation lights).
3. Sky details: extra star twinkles, the idle target path and reticle, the telescope lock-on, the meteor.
4. Workshop: the cube patch, the wireframe cube, printer nozzle, scan line and LEDs.

Foreground telescope/trees/buildings are baked into the background, so traffic cannot pass behind them. Instead traffic is kept above the `SKYLINE` outline (below) and fades or warps out before it reaches foreground objects. If full foreground occlusion becomes necessary, introduce a genuine separate foreground layer through an artistic edit rather than covering objects with arbitrary dark polygons. The one place the plate is covered is the painted CAD cube (see Workshop), and that patch is cut from the plate itself.

## Master time and periodicity

`PERIOD=24` seconds. GIF frame `i` samples time `i / fps`, for i from zero through 239 at the default 10fps. There is no duplicate frame at exactly t=24. The last sample is t=23.9, then the loop returns to t=0. This avoids double-holding a duplicated starting frame.

The common cycles are 1.5, 3, 4, 6, 8, 12 and 24 seconds, all divisors of the master cycle; `Track` asserts that every period divides `PERIOD`. Deterministic stars use a seeded random generator so repeated exports have consistent star positions and phases.

## Galaxies

Main galaxy: core position approximately **(810,184)**, displayed width **390**, positive rotation through one full turn in **24 seconds**. Its wings have enough space to turn above and beside the name region. The approved look has a larger more oblique galaxy; the separate sprite makes the core circular and lends itself to rotation. Review the comparison without silently discarding the user's approved composition.

Secondary galaxy: approximately **(1128,228)**, width **137**, opposite rotation through a full turn in **12 seconds**. It adds depth without competing with the main galaxy. Both are stylized celestial motion.

SVG rotation uses `animateTransform`; sampled frames calculate the equivalent angle. In static exports, angle values such as 0 and 360 are visually equivalent but their XML text is not identical. Tests should check geometric/visual periodicity instead of incorrectly expecting every serialized transform string to be equal at wrap.

## Planet and moons

The ringed planet is near **(1480,163)** with displayed width **305**. It moves vertically by about 3 artwork pixels over a 24-second cycle, which is gentle enough to keep it grounded in the sky composition.

The orbital guide is an ellipse with centre **(1480,162)** and radii **150×66** (`ORBIT`). Two moon sprites of widths **39** and **28** start opposite each other (phases 0 and pi) and have **12s** and **24s** cycles (`MOONS`).

SMIL projects a circular orbit through a vertically scaled parent and inverse-transforms the moon shape so the moon itself does not become a flattened or spinning bitmap. The sampled GIF coordinates use cosine/sine for the equivalent ellipse.

**Moon occlusion (resolved, T02-R2).** Each moon is drawn twice: a copy before the planet, visible on the far (upper, sin(theta)<0) half of its orbit, and a copy after it, visible on the near half. Complementary step opacity tracks (`moon_layer`, coincident key times) switch the copies exactly at theta=0 and theta=pi, where the moon is clear of the planet body, so a moon disappears behind the planet and comes back in front without popping.

## Spacecraft and aviation routes

One table, `ROUTES`, drives both the SMIL and the sampled frames. `traffic_state(t)` evaluates it and also returns each object's sprite, trail and warp-streak boxes, which the tests check.

| Object | Width | Lane y | Horizontal range | Cycle | Phase | Fade (x, opacity) | Warp event |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Explorer | 295 | 338 | 1900 → 490 | 24s | .31 | 1 until x≈973, 0 by x≈972 (just after the warp) | exits to warp at x=980 (t≈8.2s) |
| Fighter A | 133 | 434 | 1840 → -170 | 12s | .15 | 0 until x≈1324, 1 by x≈1317 | drops out of hyperspace at x=1250 (t≈1.7s and 13.7s) |
| Fighter B | 103 | 458 | 1840 → -170 | 12s | .245 | 0 until x≈1304, 1 by x≈1297 | drops out at x=1230, streaks at 80% scale (t≈0.7s and 12.7s) |
| Airplane | 142 | 518 | -200 → 1830 | 24s | .23 | 1 until x=1180, 0 at x=1330 | none |

The sampled position is `start + (end-start) * ((t/period + phase) % 1)`. SMIL uses negative animation start times to begin at the same phase without waiting through an empty intro. The explorer lane was raised from 385 to 338 and fighter B's phase moved from .20 to .245 in T02-R1; the fade rows above are the actual values in `ROUTES`.

Guarantees, each enforced by tests over the whole loop:

- **No hard clip.** The old clip zone at x=574 was removed. The explorer is never cut by a boundary; it leaves by warping out at x=980, and its streak (far end at about x=708) stays clear of the text block.
- **Text.** No visible traffic object (sprite, trail or warp streak) overlaps `TEXT_RECT` = (30, 218, 565, 375), the quiet name region.
- **Skyline.** `SKYLINE` is a polyline of the topmost foreground (trees, van, telescope finder, workshop roof) per column, measured from the plate and kept about 8px conservative. Every visible traffic box stays above it. The airplane stays clear of the telescope finder (box bottom above y=548 near x=790..830) and dissolves in open sky before x=1330, so it never crosses the workshop roof or right-hand trees. Fighters fade in around x≈1300-1320, clear of the trees.
- **No overlaps.** No sprite, exhaust trail or warp streak is drawn across another craft or its trail.
- **Smooth fades.** Opacity changes are straight segments; nothing pops except the intended warp flash.
- **Facing.** Spacecraft head left, the passenger airplane right. Trails are drawn in the same transform group as the object, short and restrained.

In T02-R1 (before the T14 warp changes) the sky was empty of fully visible traffic about 4% of the loop, with a longest gap of 0.96s.

### Warp transitions (T14)

**Explorer, going out.** In its last half second the hull stretches along the flight axis from the nose (scale 1, 1.35, 2, 3 at -0.5, -0.3, -0.2, -0.1 s relative to the event), while three stacked cyan-white streak lines run up to 130px ahead of the nose. The hull dims at -0.12s and is gone at -0.06s; a four-point cyan sparkle (size 13) peaks at the streak's far end between -0.12s and -0.03s and has faded by +0.09s. The route fade ends the object at +0.12..0.14s so the sparkle can finish.

**Fighters, coming in.** Magenta/white streaks start spread around the flight axis and converge on the hull over 0.4s (the streak group is visible from -0.4s); the hull is invisible until -0.2s and fully opaque at the event, then flies on normally. Fighters are invisible before their streaks appear.

Warp and drop-out last only 4-5 GIF frames by design. The tests check that streak and sparkle boxes stay in open sky, inside their declared boxes and clear of the other craft.

## Navigation lights (T14)

The airplane carries three lamps in its fuselage frame (heading right): red at (-26.5, -17.1) on the far wing tip, green at (11, 4.5) on the near wing by the engine, and a white anti-collision strobe at (-51.3, -22.1) on the fin. The red and green lamps are steady (opacity 0.85 ± 0.15, 3s period, offset half a cycle) with a faint glow square. The strobe double-flashes with peaks at 0.1s and 0.3s of every 1.5s (16 pairs per loop); the peaks sit on 0.1s multiples so every 10fps GIF frame sees a full flash or none. The lights ride the airplane group, so they fade and move with it.

## Stars, meteor and target instruments

32 possible extra star crosses are seeded with `Random(29)`. Any generated star within the quiet name rectangle is skipped. Their opacity is a `Track.sine` (0.6 ± 0.4) with a period chosen from 3/4/6/8 seconds and an independent phase. These are supplementary twinkles on the stable detailed background, not a replacement for its Milky Way texture.

An idle dotted cyan target path leads from near the telescope (811,551) toward a small reticle near (1020,97), then toward the planetary area. It must explicitly use `fill="none"`; an open multi-segment path otherwise fills an unintended dark triangle (an actual early defect, now covered by a regression test). The reticle is a four-corner stroked shape with a subtle 3-second opacity cycle. Keep both small and translucent so they read as an instrument overlay. While the lock-on sequence runs (below) the idle path and reticle fade out (opacity 1 until 12.4s, 0 from 13.0s to 20.9s, back to 1 by 21.9s) so there are never two reticles at once.

The meteor uses a 12-second cycle with visibility only in roughly the first 16% of the cycle, a sin² fade in and out. A short line and bright head move diagonally from around (1100,380) toward (1490,530).

## Telescope lock-on (T14)

Once per loop the telescope acquires the main galaxy, identified as M51 (the Whirlpool, a face-on spiral). Real J2000 coordinates are RA 13h29m52.7s, Dec +47°11′43″; the readout shows them rounded to RA 13h29m and Dec +47°11′. Timeline in loop seconds (the `LOCK` tracks in `_lock_tracks`):

| Time | Event |
| --- | --- |
| 12.8-14.4 | A dotted line grows from the telescope finder (811,551) to just below the target (810,234); it fades in by 13.1 |
| 13.4-14.6 | Four corner brackets (arm length 14) fly in from a half-size of 100 to 50 around the galaxy core (810,184) |
| 14.6-14.95 | Reticle snaps to a half-size of 38 then settles at 44; a brighter pulse peaks at 14.75 |
| 14.9-15.3 | Leader line (M860 134 L890 106 H938) fades in |
| 15.0, 15.3, 15.6 | The three readout lines start fading in one by one (0.3s each): `TARGET LOCK · M51`, `RA 13h29m`, `DEC +47°11′` at (946,98) |
| 20.0-20.9 | Everything fades out; line and reticle reset to their start while invisible by 21.0 |

The readout uses a hand-made 3×5-cell pixel font (`FONT`, each cell 3 scene px, about 1.5px in the 840px GIF) drawn as filled rectangles through `pixel_text`. It deliberately avoids `<text>` so it renders the same in every renderer regardless of installed fonts. The sequence never touches `TEXT_RECT` and never covers the galaxy core; a test also checks there is at most one reticle at any time. The dotted line has a dark under-stroke so it stays legible against the Milky Way. It is drawn over any ship that happens to pass at that moment (accepted in T14).

## Workshop

**CAD cube (resolved, T02-R2).** The plate paints its own glowing cube on the wall (outline x 1438..1484, y 689..734). The first package drew a second, offset wireframe cube over it, so two cubes were visible in every frame. Now:

- `cube_patch()` covers the painted cube with a patch made only from the plate's own wall: a clean 3px strip above the cube stretched over the target area (1432,683,60,58), plus a strip from below faded in over the lower part so the bottom edge matches, both feathered by 2px through masks. No new flat colors are painted.
- The animated cube is drawn where the painted one was, centred near (1461,709), half-edge 15.5, with a fixed 22° downward tilt, a 45° starting yaw, and weak perspective (camera distance 140px). The tilt keeps top faces visible, so the cube never collapses to a flat rectangle at 90° yaw. Its footprint matches the painted cube within 0.5px at rest.
- Two soft under-strokes (widths 7 and 4, opacities .12 and .24) echo the painted halo; the crisp 1.8px edges (`#72f0ff`, opacity .9) sit on top. Twelve edges, eight vertices.
- Each projected vertex coordinate is a 24-pose `Track` over **6 seconds**, shared by every edge that uses it, so SMIL and raster frames are identical.
- Residual: the patch loses the plate's soft halo (the glow strokes stand in), and a faint plate-shadow step near x<1452, y≈741 is visible only at 1672px with boosted brightness.

The print-head overlay (9×5px) slides along x = 1335 ± 20 at y=727 with a 3-second sine. The scanner line (39px wide, 1.6px high, x=1318) moves along y = 749 ± 18 with a 6-second sine. The underlying rocket remains drawn in the background; the code does not accumulate extrusion layers from zero. If a genuine build-up effect is implemented, retain the rocket/pixel style and use a clean source plate rather than covering it with arbitrary rectangles.

Four small workshop/rover LEDs pulse near (1596,775), (1380,733), (1196,816) and (1505,591), opacity between .35 and 1 on a 3-second sine with different phases. They should be discovered on closer viewing, not become large flashing distractions.

## SVG/GIF parity (resolved, T07)

Every non-trivial motion (planet bob, nozzle, scan line, LEDs, reticle, twinkles, meteor fade, cube vertices, moon layers, warp and lock-on channels, navigation lights) is a `Track`: one keyframe table evaluated by `Track.at(t)` for the sampled GIF frames and printed as SMIL `values`/`keyTimes` for the SVG, rounded to the same precision. Sine motions are 24-keyframe approximations (at most 0.2px from the analytic curve). T07 fixed an inverted planet bob, nozzle/scan/LED phase and shape, a doubled reticle opacity, the meteor fade shape and cube chord interpolation.

Verification: Chromium `setCurrentTime` on the animated SVG versus librsvg frames at 1672×941 on the standard sample times (0, 3, 6, 12, 14.7, 18, 23.9), plus the lock-on hold and warp frames in T14. Pixels differing by more than 60 fell from thousands to a handful at every time (T07: for example 8118 to 5 at t=6); the largest differing cell is 4-5 against a limit of 150, which is renderer antialiasing. The unit tests also compare each animated element's SMIL against the raster value and check every animation loops without a jump at t=24.

## Formats and accessibility

The animated SVG includes all PNG resources as data URIs and reuses them internally. No JavaScript, external font or foreign object is embedded in the SVG. Its reduced-motion media rule switches from `.moving` to `.still` groups.

The GIF is used in README for portability. A static PNG of matching dimensions is supplied through the `<picture>` element for reduced motion. Confirm GitHub's actual renderer retains the picture/source behavior. If not, provide a clearly accessible static alternative without pretending the GIF can respect media queries by itself.

The local preview has a real button for pause/resume, named hotspot buttons, visible focus and native expandable logs. Do not rely only on hover. Test the square image in a circular preview at small sizes; it is a static matching profile picture, not a promise that GitHub animates account avatars (reviewed in T03, see `ASSET-REGISTRY.md`).

## Export controls and quality limits

Default export is **840px wide at 10fps** (`GIF_WIDTH = 840`, `--fps 10`), 240 frames, with a shared 256-color palette (`palettegen stats_mode=full`) and ordered Bayer dithering at `bayer_scale=5`. Reasons, from the T08 measurements on identical rendered frames:

- GitHub displays the hero at about 830px, so 1000px frames only add bytes. 840px is roughly 1:1 at display size and about 29% smaller (1000px/Bayer 3: 11,336,782 bytes; 840px/Bayer 5: 8,075,059 bytes). Lettering and the telescope were indistinguishable at display size.
- Reducing to 8fps saved only about 18%, so frame rate was kept at 10.
- Bayer dithering is position-locked, so static areas do not crawl between frames. Error diffusion (`sierra2_4a`) roughly doubled the size and flickered. `dither=none` was rejected because of banding risk in the sky gradients. Scale 5 gives a finer, less visible texture and a slightly smaller file than scale 3.
- `stats_mode=diff` gave a larger file (about +8%) and worse error on the static background. FFmpeg's GIF muxer already writes changed-rectangle frames, so `diff_mode=rectangle` and a gifsicle `-O3` pass gained nothing (-0.13%).
- Trade-off: fewer source pixels for high-DPI zoom. The animated SVG is the full-resolution version.

The committed GIF is 7,955,864 bytes after the T14 scene additions. Increasing to 12fps smooths traffic but increases frames and bytes. More complex halos or full-scene motion can inflate GIF size quickly.

The quality gate's 25MB budget is a review ceiling, not a requirement to approach it. Prefer smaller files when readability, pixel texture and perceived movement remain intact. Check shared-palette dithering for crawl/noise around sprite edges. Do not shrink and blur the scene so the user's distinctive telescope silhouette disappears.

Use inspected screenshots/frame samples and recorded playback, if available, as review evidence. Do not certify aesthetic correctness from XML parsing alone.
