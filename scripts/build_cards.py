"""Generate the four animated pixel navigation cards (deterministic output).

Each card is a complete, legible static image. The motion lives in a single
`.fx` overlay group (top-edge sweep, icon pulse, one twinkling pixel, block
cursor) that an SVG-internal prefers-reduced-motion rule hides, so the card
never depends on the animation to be readable. No scripts, no external assets.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
# (file, short id, label, subtitle, accent, description, twinkle (row,col), 14x12 pattern)
CARDS=[
 ('observatory-card.svg','observatory','01 / OBSERVATORY','ASTRONOMY · ASTROFIXXER','#57d9f7',
  'a pixel telescope pointing at the sky','the astronomy',(0,9),[
 '         XX   ','        XXXX  ','       XXXX   ','      XXXX    ','     XXXX     ','      XX      ','      XX      ','     XXXX     ','     X  X     ','    XX  XX    ','   XX    XX   ','  XX      XX  ']),
 ('flight-card.svg','flight','02 / FLIGHT DECK','AVIATION · EXPLORATION','#cf8efc',
  'a pixel aircraft seen from above','the aviation and exploration',(0,6),[
 '      X       ','      XX      ','      XX      ','      XX      ','   XXXXXXXX   ','XXXXXXXXXXXXXX','   XXXXXXXX   ','      XX      ','      XX      ','     XXXX     ','    XXXXXX    ','      XX      ']),
 ('fablab-card.svg','fablab','03 / FAB LAB','CAD · LEGO · 3D PRINTING','#f8c27d',
  'a pixel workshop frame with a build plate','the CAD, LEGO and 3D printing',(2,4),[
 ' XXXXXXXXXXXX ',' XX        XX ',' XX  XXXX  XX ',' XX XXXXXXXX  ',' XX   XX   XX ',' XX   XX   XX ',' XX   XX   XX ',' XX  XXXX  XX ',' XX XXXXXX XX ',' XX   XX   XX ',' XX        XX ',' XXXXXXXXXXXX ']),
 ('rover-card.svg','rover','04 / ROVER BAY','ROBOTICS · IGVC · ROS NOETIC','#6fe3b4',
  'a pixel rover with a sensor mast and three wheels','the robotics and IGVC',(0,5),[
 '     XXXX     ','     X  X     ','      XX      ','      XX      ',' XXXXXXXXXXXX ','XXXXXXXXXXXXXX',' XXXXXXXXXXXX ','  X   XX   X  ',' XX  XXXX  XX ','XXXX XXXX XXXX','XXXX XXXX XXXX',' XX  XXXX  XX ']),
]
STYLE='<style>@media (prefers-reduced-motion: reduce){.fx{display:none}}</style>'
EASE=' calcMode="spline" keySplines=".4 0 .6 1;.4 0 .6 1"'
DISCRETE=' calcMode="discrete"'
LINK_TEXT='OPEN MISSION LOG →'
LINK_WIDTH=108  # 18 monospace glyphs at 10px; fixed so the cursor position is deterministic


def runs(pattern,x0,y0,cell=3):
 """Horizontal pixel runs as one compact path."""
 out=[]
 for y,row in enumerate(pattern):
  x=0
  while x<len(row):
   if row[x]=='X':
    start=x
    while x<len(row) and row[x]=='X':x+=1
    w=(x-start)*cell
    out.append(f'M{x0+start*cell} {y0+y*cell}h{w}v{cell}h-{w}z')
   else:x+=1
 return ''.join(out)


def anim(attr,values,dur,begin,key=None,extra=''):
 k=f' keyTimes="{key}"' if key else ''
 return f'<animate attributeName="{attr}" values="{values}"{k} dur="{dur}s" begin="{begin}s" repeatCount="indefinite"{extra}/>'


def build(index,filename,key,label,subtitle,color,icon_desc,topic,twinkle,pattern):
 """Write the animated card and its static twin (same card, no motion layer)."""
 begin=round(index*.5,1)
 icon=runs(pattern,20,30)
 tr,tc=twinkle
 summary=(f'Navigation card for {topic} mission log, showing {icon_desc}, the label {label} '
          f'and the prompt to open the mission log.')
 desc_motion=summary+' A light sweeps along the top edge, the icon pulses softly and a block cursor blinks; with reduced motion the card is still.'

 def card(desc,style,overlay):
  return ''.join([
  f'<svg xmlns="http://www.w3.org/2000/svg" width="360" height="136" viewBox="0 0 360 136" role="img" aria-labelledby="t-{key} d-{key}">',
  f'<title id="t-{key}">{label}</title><desc id="d-{key}">{desc}</desc>',style,
  '<rect x=".5" y=".5" width="359" height="135" rx="4" fill="#081321" stroke="#253952"/>',
  f'<path d="M0 1H360" stroke="{color}" stroke-width="2"/>',
  f'<path d="{icon}" fill="{color}" shape-rendering="crispEdges"/>',
  f'<text x="86" y="53" fill="{color}" font-family="monospace" font-size="14" font-weight="700">{label}</text>',
  f'<text x="86" y="77" fill="#afbdd2" font-family="monospace" font-size="9">{subtitle}</text>',
  f'<text x="86" y="106" fill="#8093ad" font-family="monospace" font-size="10" textLength="{LINK_WIDTH}" lengthAdjust="spacing">{LINK_TEXT}</text>',
  overlay,'</svg>'])

 # animated overlay: removable without changing what the card says
 overlay=''.join([
 '<g class="fx" shape-rendering="crispEdges">',
 f'<rect x="-70" y="0" width="70" height="2" fill="#fff" opacity=".55">{anim("x","-70;360;360",6,begin,"0;.5;1")}</rect>',
 f'<path d="{icon}" fill="#fff" opacity="0">{anim("opacity","0;.2;0",4,begin,"0;.5;1",EASE)}</path>',
 f'<rect x="{20+tc*3}" y="{30+tr*3}" width="3" height="3" fill="#fff" opacity="0">{anim("opacity","0;.9;0",3,begin,"0;.5;1",EASE)}</rect>',
 f'<rect x="{86+LINK_WIDTH+5}" y="97" width="6" height="10" fill="#8093ad" opacity="0">{anim("opacity","1;0",1.6,begin,None,DISCRETE)}</rect>',
 '</g>'])
 static=filename.replace('-card.svg','-card-static.svg')
 (ROOT/'assets'/filename).write_text(card(desc_motion,STYLE,overlay),encoding='utf-8')
 (ROOT/'assets'/static).write_text(card(summary+' This version has no motion.','',''),encoding='utf-8')
 print('Generated',filename,static)


if __name__=='__main__':
 for i,card in enumerate(CARDS):build(i,*card)
