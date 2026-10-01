"""Generate small pixel UI navigation panels with accessible labels."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CARDS=[
 ('observatory-card.svg','01 / OBSERVATORY','ASTRONOMY · ASTROFIXXER','#57d9f7',[
 '         XX   ','        XXXX  ','       XXXX   ','      XXXX    ','     XXXX     ','      XX      ','      XX      ','     XXXX     ','     X  X     ','    XX  XX    ','   XX    XX   ','  XX      XX  ']),
 ('flight-card.svg','02 / FLIGHT DECK','AVIATION · EXPLORATION','#cf8efc',[
 '      X       ','      XX      ','      XX      ','      XX      ','   XXXXXXXX   ','XXXXXXXXXXXXXX','   XXXXXXXX   ','      XX      ','      XX      ','     XXXX     ','    XXXXXX    ','      XX      ']),
 ('fablab-card.svg','03 / FAB LAB','CAD · LEGO · 3D PRINTING','#f8c27d',[
 ' XXXXXXXXXXXX ',' XX        XX ',' XX  XXXX  XX ',' XX XXXXXXXX  ',' XX   XX   XX ',' XX   XX   XX ',' XX   XX   XX ',' XX  XXXX  XX ',' XX XXXXXX XX ',' XX   XX   XX ',' XX        XX ',' XXXXXXXXXXXX ']),
]
for filename,label,subtitle,color,pattern in CARDS:
 parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="360" height="136" viewBox="0 0 360 136" role="img"><title>{label}</title>',
 '<rect x=".5" y=".5" width="359" height="135" rx="4" fill="#081321" stroke="#253952"/>',
 f'<path d="M0 1H360" stroke="{color}" stroke-width="2"/>']
 for y,row in enumerate(pattern):
  for x,ch in enumerate(row):
   if ch=='X':parts.append(f'<rect x="{20+x*3}" y="{30+y*3}" width="3" height="3" fill="{color}"/>')
 parts += [f'<text x="86" y="53" fill="{color}" font-family="monospace" font-size="14" font-weight="700">{label}</text>',
 f'<text x="86" y="77" fill="#afbdd2" font-family="monospace" font-size="9">{subtitle}</text>',
 '<text x="86" y="106" fill="#8093ad" font-family="monospace" font-size="10">OPEN MISSION LOG →</text></svg>']
 (ROOT/'assets'/filename).write_text(''.join(parts))
 print('Generated',filename)
