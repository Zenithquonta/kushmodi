#!/usr/bin/env python3
"""Validate the deliverable without browser/network access or image editing."""
from pathlib import Path
import hashlib
import json
import re
import sys
from urllib.parse import unquote_plus
import xml.etree.ElementTree as ET
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
SVG='{http://www.w3.org/2000/svg}'
checks=[]


def check(label,fn):
 try:
  result=fn()
  checks.append({'name':label,'passed':True,'details':result or 'OK'})
 except Exception as exc:
  checks.append({'name':label,'passed':False,'details':str(exc)})


def readme():
 text=(ROOT/'README.md').read_text()
 decoded=unquote_plus(text)
 assert not re.search(r'clerical|GR\s*Modi|CA Tech Builder|Automation Developer',decoded,re.I),'Removed work references remain'
 for name in re.findall(r'(?:src|srcset)="\./([^"]+)"',text):
  assert (ROOT/name).is_file(),f'Missing README image {name}'
 anchors={re.sub(r'[^\w -]','',h.lower()).replace(' ','-') for h in re.findall(r'^## (.+)$',text,re.M)}
 for anchor in re.findall(r'href="#([^"]+)"|\]\(#([^)]+)\)',text):
  target=anchor[0] or anchor[1]
  assert target in anchors,f'Missing README anchor {target}'
 assert text.count('<details>')==text.count('</details>')==4
 return 'Images resolve, anchors resolve, four mission logs, removed work absent'


def svg_art():
 paths=list((ROOT/'assets').glob('*.svg'))
 assert paths,'No SVG files'
 animation_count=0
 for path in paths:
  text=path.read_text()
  doc=ET.fromstring(text)
  assert doc.tag==SVG+'svg',path.name
  ids=[e.attrib['id'] for e in doc.iter() if 'id' in e.attrib]
  assert len(ids)==len(set(ids)),f'Duplicate IDs: {path.name}'
  for element in doc.iter():
   assert element.tag not in (SVG+'script',SVG+'foreignObject'),f'Executable SVG content: {path.name}'
   for key,value in element.attrib.items():
    if key.endswith('href'):
     assert value.startswith(('#','data:image/png;base64,')),f'External SVG resource: {path.name}'
     if value.startswith('#'):assert value[1:] in ids,f'Unknown SVG ID {value}'
   if element.tag in (SVG+'animate',SVG+'animateTransform'):
    animation_count+=1
    if 'keyTimes' in element.attrib:
     keys=[float(x) for x in element.attrib['keyTimes'].split(';')]
     assert keys[0]==0 and keys[-1]==1 and keys==sorted(keys)
     assert len(keys)==len(element.attrib['values'].split(';'))
  assert set(re.findall(r'url\(#([^)]+)\)',text))<=set(ids),path.name
 assert animation_count>20,'Hero animation missing'
 return f'{len(paths)} SVGs; {animation_count} valid animation elements; all resources embedded'


def gif_art():
 path=ROOT/'assets/observatory.gif'
 assert path.is_file(),'GIF has not been exported'
 with Image.open(path) as im:
  assert im.is_animated and im.n_frames>1,'GIF is static'
  assert im.info.get('loop')==0,'GIF must loop indefinitely'
  frame_count=im.n_frames
  duration=0
  hashes=set()
  for i in range(frame_count):
   im.seek(i)
   duration+=im.info.get('duration',0)
   if i in (0,frame_count//4,frame_count//2,3*frame_count//4):
    hashes.add(hashlib.sha256(im.convert('RGB').tobytes()).hexdigest())
  assert len(hashes)>=3,'Expected visible motion across sampled frames'
  assert 23500<=duration<=24500,f'Loop should be approximately 24 seconds, got {duration} ms'
  size=im.size
 assert path.stat().st_size<25_000_000,'GIF exceeds 25 MB review budget'
 with Image.open(ROOT/'assets/observatory-poster.png') as poster:
  assert poster.size==size,'Poster dimensions differ from GIF'
 return f'{frame_count} frames, {duration/1000:g}s, {size[0]}×{size[1]}, {path.stat().st_size:,} bytes, sampled frames differ'


def sprite_alpha():
 with Image.open(ROOT/'assets/space-sprites.png') as im:
  assert im.mode=='RGBA','Sprite atlas requires transparency'
  h=im.getchannel('A').histogram()
  assert h[0]>im.width*im.height*.4,'Sprite atlas has insufficient clear space'
  assert sum(h[128:])>1000,'Sprite atlas is empty'
 return 'Atlas has real transparency and visible sprites'


def main():
 check('README content and links',readme)
 check('SVG structure and embedded resources',svg_art)
 check('GIF loop and visible motion',gif_art)
 check('Sprite atlas transparency',sprite_alpha)
 result={'passed':all(c['passed'] for c in checks),'checks':checks}
 print(json.dumps(result,indent=2))
 return 0 if result['passed'] else 1


if __name__=='__main__':
 sys.exit(main())
