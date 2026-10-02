# Sky data sources

The live observatory (`scripts/night_sky.py`) draws the real night sky for the render time and Mumbai from these
files. They are produced by `scripts/sky_catalog.py` from the public data below; nothing here is hand-edited.

| File | Content | Source |
| --- | --- | --- |
| `stars.json` | The 5.0-magnitude-or-brighter stars of the Yale Bright Star Catalogue, 5th revised edition (BSC5): J2000 position, visual magnitude, colour temperature in kelvin, Harvard Revised number and proper names | Hoffleit and Warren Jr. (1991), VizieR V/50, as a JSON file by Bretton Wade: https://github.com/brettonw/YaleBrightStarCatalog (`bsc5-short.json`) |
| `milkyway.json` | The Milky Way outline in five brightness steps, thinned to 0.45 degree spacing | Olaf Frohn, d3-celestial, `data/mw.json`: https://github.com/ofrohn/d3-celestial |
| `constellations.json` | The constellation stick figures | Olaf Frohn, d3-celestial, `data/constellations.lines.json` |

The star positions are J2000; the renderer applies precession and nutation for the render time.

## d3-celestial licence (BSD 3-Clause)

```text
Copyright (c) 2015, Olaf Frohn
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
