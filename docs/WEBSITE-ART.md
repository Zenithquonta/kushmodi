# Website foliage provenance

`site/data/foliage-atlas.webp` is a transparent 2 by 2 foliage atlas generated with the built-in image generation tool on 2026-10-04. Its style reference was `assets/observatory-background.png`; the reference and approved concept remain unchanged. The generated PNG was optimized to an 832 by 832 WebP with alpha preserved. It supplies plant silhouettes on crossed planes in the walkable environment. It supplies no celestial imagery.

Generation prompt:

> Create a game-ready foliage sprite atlas for a walkable 3D observatory environment, inspired by the detailed painterly pixel-art plants in the supplied reference (STYLE REFERENCE ONLY). Square image, EXACT 2 by 2 grid of four separate plant clusters, with generous transparent padding within each equal quadrant, no borders or labels. Top left: lush broad low shrub with many small intricate leaves, dark blue-green. Top right: wild fern and long meadow grasses with delicate fronds, muted teal green. Bottom left: dense irregular leafy bush with a few small dry golden stems, forest green. Bottom right: large clump of wild grasses and small leafy plants with tiny pale flowers. Each complete cluster viewed straight-on at ground level, full silhouette visible, all four plants rooted at bottom of own cell. Beautiful hand-painted detailed environment concept art with tiny crisp clusters of texture matching the observatory reference, organic nuanced silhouettes, neutral diffuse illumination with subtle cool rim accents, no cast shadow, NO ground plane, NO scenery, NO text, NO sky, NO rocks. Genuine alpha transparent background around every leaf. Not low polygon, not geometric, not cartoon.

The website uses only its real Mumbai sky calculation. Planet guides project the computed planet coordinates. The separate eyepiece canvas draws explicitly identified pixel-art illustrations of the selected real target; these are not camera images. No generated sky image or alternate illustrated sky mode is included in the website.

## 2.5D scenery sprites (site/data/scenery, built by scripts/site_sprites.py)

The walkable scene is detailed 2D artwork placed at real depths (alpha-tested textured quads in the three.js scene, depth-sorted by the depth buffer, perspective-scaled, with parallax from the walking camera). All files below are derived or authored by `python scripts/site_sprites.py` (Pillow and numpy; no image-generation tool was used for this pass). Sources are never modified. The astronomical sky is not painted anywhere: cutouts keep only objects, and every pixel of sky behind them is removed.

| File | Origin and method |
| --- | --- |
| `telescope.webp` (288x320) | Crop (612,522)-(900,842) of `assets/observatory-background.png`. Sky removed by luminance key (dark silhouette below 52/255), 4-connected component from the tripod, small holes filled, the thin counterweight shaft re-added from a local threshold, distant mountains and city lights at the right clipped by a line, 1 px rim darkened to remove sky colour, bottom 10% faded, then a gamma lift (0.62) so the near-black body keeps form against the dark real sky. |
| `van.webp` (300x240) | Crop (0,560)-(300,800) of the same reference, same luminance key (threshold 58), left 6% and bottom 12% faded, gamma lift 0.7. The van is cut by the image border at the left, so it is placed against foliage. |
| `workshop.webp` (507x461) | Crop from x=1165 of the reference, masked by a polygon under the roof edge (found by overlaying a grid on the reference) and the rover removed (x<152 below y=322). A hanging "MAKER WORKSHOP / CAD / ROBOTICS / FABRICATION" board is painted onto it by the script (Pillow text), as the previous 3D shed carried the same label. |
| `rover.webp` (150x120) | Hand-traced polygon around the rover in the reference crop (1085,805)-(1235,925). |
| `tree_a/b/c.webp` | Three canopy crops (262,622)-(342,716), (392,664)-(452,752), (1094,634)-(1162,736) of the reference, luminance key (threshold 40), lower mass faded. They have hard side edges where the crop cut a neighbouring tree, so the page stacks them in overlapping groves and sinks their bases below the ground. |
| `rock_a/b/c.webp` | Authored by the script: fractal relief, cool upper-edge light, warm ground bounce, grain, fissures, moss patches. |
| `lantern.webp` (20x40) | Authored by the script: a pixel-art path lantern after the amber lanterns of the reference. |
| `ground.webp` (256x256) | Authored by the script: seamless noise, grass flecks and pebbles, neutral so the terrain vertex colours tint it. |
| `ridge_far/mid/near.webp` (4096x320) | Authored by the script: tileable ridge silhouettes (periodic multi-octave profile, stepped crest, conifer teeth on the near layer, low across the north so the valley and the city stay visible). They are luminance only; the page tints them each frame from the real horizon colour. |
| `../foliage-atlas.webp` | Unchanged generated atlas (see above), now used as camera-facing plants and as the grass tufts. |

The pixel-art scenery is magnified with nearest filtering to keep the look of the references. Added transfer: about 0.25 MB of webp; the site transfer test ceiling was raised from 1.0 MB to 1.5 MB gzipped for this reason.

Weaknesses of the cutouts, stated plainly: the tree canopies and the van are fragments (cut by the reference frame), the rocks are authored not painted, and the telescope is a static sprite in the reference pose, so the tube does not slew toward the target (the target is shown in the eyepiece and the readout).
