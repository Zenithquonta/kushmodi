# Sources of the site data

The files in this directory are produced by `scripts/build_site_data.py` (run it again to reproduce them byte for byte
from the sources below). Nothing here is fetched by the site at run time.

| File | Source |
| --- | --- |
| `stars.json` | Yale Bright Star Catalog, 5th revised edition (BSC5; Hoffleit and Warren, 1991), in the JSON conversion `bsc5-short.json` from https://github.com/brettonw/YaleBrightStarCatalog (original ASCII catalogue: http://tdc-www.harvard.edu/catalogs/bsc5.html). Stars with V magnitude 6.0 or brighter; positions are J2000. |
| `milkyway.json` | `data/mw.json` from d3-celestial, https://github.com/ofrohn/d3-celestial (Milky Way outlines, simplified with a 0.4 degree tolerance and rounded to 0.1 degree) |
| `constellations.json` | `data/constellations.lines.json` from d3-celestial (rounded to 0.01 degree) |
| `site.json` | `config/observatory.json` of this repository (location of the observatory) |

SHA-256 of the downloaded inputs used for the committed files:

```
94b0581379ef9ea49f1ce664734a06d2fbbff2d7487f926acad3e9ef0960e0d8  bsc5-short.json
aee221a7a0e879418e685de00c3e68fbdfac5667c0a8aab74929ef9cf4aab4fb  mw.json
294f66bef5d5cf50b1e17f16d2efa1d97a15131612c68dd935adef6e7373e13c  constellations.lines.json
```

## Credits

- Yale Bright Star Catalog: D. Hoffleit and W. H. Warren Jr., *The Bright Star Catalogue*, 5th revised edition, Astronomical
  Data Center, NSSDC/ADC, 1991. JSON conversion by Bretton Wade (brettonw).
- d3-celestial: Olaf Frohn, https://github.com/ofrohn/d3-celestial, BSD 3-clause licence (text below). The constellation
  and Milky Way data in that project derive from other public sources named in its repository.

## d3-celestial licence

```
Copyright (c) 2015, Olaf Frohn
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
