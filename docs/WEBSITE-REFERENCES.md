# Reference index for the layered 2D environment

All references below are committed on `wip/observatory-polish`. The user's latest direction is a 2.5D environment made from 2D art with depth, perspective, parallax and occlusion. The actual Mumbai sky calculation remains the source of celestial positions. The redesign has not started; current review views show the preserved earlier implementation.

| Reference | Purpose |
| --- | --- |
| [Original telescope photograph](../assets/reference-telescope.jpg) | Telescope identity, observing equipment and original scene inspiration. |
| [Approved concept](../assets/approved-concept.png) | Approved composition, rich pixel-art detail, foliage, workshop and foreground atmosphere. |
| [Observatory background](../assets/observatory-background.png) | Primary visual reference for landscape, rocky clearing, workshop, foliage and restrained cyan/amber lighting. Preserve this original when deriving environment layers. |
| [Historical transparent sprite atlas](../assets/space-sprites.png) | Existing pixel-art sprite technique and palette. Its fictional sky/ship imagery belongs to historical artwork; it does not supply celestial objects to the website's real sky. |
| [Original generated foliage atlas](../assets/website-foliage-source.png) | Full source PNG with alpha for deriving detailed plant sprites. |
| [Optimized foliage atlas](../site/data/foliage-atlas.webp) | Current 2 by 2 transparent atlas used for the walkable scene. |
| [Foliage generation prompt/provenance](WEBSITE-ART.md) | Complete generation instruction, approved style reference and current asset use. |
| [Night environment review](review/site-night.png) | Independently reviewed current compact environment and improved foreground flora; fixed Oct4 night test. |
| [Altair eyepiece review](review/site-telescope.png) | Independently reviewed target illustration/status/dialog; fixed night test. |
| [Mobile eyepiece review](review/site-mobile-eyepiece.png) | Current mobile dialog layout, retained for continuation. |
| [Current browser report](review/browser-results.txt) | Preserved verification report with the unresolved movement-resume assertion. |

Historical weather/palette artwork is also retained: [day](../assets/observatory-day.png), [golden hour](../assets/observatory-golden.png), [dry season](../assets/observatory-dry.png), and the [original poster](../assets/observatory-poster.png). They may inform environment palettes. Their painted skies must not be used as simulated celestial state.

The discarded synthetic sky is excluded. No illustrated sky switch is authorized. Deriving sprite art and depth layers must preserve the guide rings at the planets' actual projected coordinates, real telescope tracking, honest daylight/horizon states, and accessible movement/interactions.
