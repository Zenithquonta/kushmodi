"""Record asset provenance metadata without modifying artwork."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
assets=ROOT/'assets'
entries=[]
for path in sorted(assets.rglob('*')):
 if not path.is_file() or path.name=='MANIFEST.json':continue
 item={'path':path.relative_to(ROOT).as_posix(),'bytes':path.stat().st_size,
       'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'role':'reference-only rejected prototype' if 'legacy' in path.parts else 'active artwork or source; see docs/ASSET-REGISTRY.md'}
 if path.suffix.lower() in ('.png','.jpg','.gif'):
  with Image.open(path) as im:
   item.update(width=im.width,height=im.height,mode=im.mode,format=im.format)
   if path.suffix=='.gif':
    item.update(frames=im.n_frames,loop=im.info.get('loop'))
    duration=0
    for i in range(im.n_frames):
     im.seek(i)
     duration+=im.info.get('duration',0)
    item['duration_ms']=duration
 elif path.suffix=='.svg':
  doc=ET.parse(path).getroot()
  item.update(width=doc.attrib.get('width'),height=doc.attrib.get('height'),viewBox=doc.attrib.get('viewBox'))
  item['animation_elements']=sum(e.tag.rsplit('}',1)[-1] in ('animate','animateTransform') for e in doc.iter())
 entries.append(item)
(assets/'MANIFEST.json').write_text(json.dumps({'schema_version':1,'assets':entries},indent=2)+'\n')
print('Recorded',len(entries),'artwork assets')
