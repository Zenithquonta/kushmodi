import math
import unittest
import xml.etree.ElementTree as ET
import build_animation as scene

try:
 from PIL import Image
except ImportError:  # the plate check is skipped without Pillow
 Image=None

SVG='{http://www.w3.org/2000/svg}'
SAMPLES=[i/10 for i in range(scene.PERIOD*10)]  # exactly the GIF frame times
VISIBLE=scene.VISIBLE_OPACITY


def overlap(a,b):
 return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]


def on_canvas(box):
 return box[2]>0 and box[0]<scene.W and box[3]>0 and box[1]<scene.H


def lerp(keys,values,fraction):
 for (k0,v0),(k1,v1) in zip(zip(keys,values),zip(keys[1:],values[1:])):
  if fraction<=k1:
   return v0 if k1==k0 else tuple(a+(b-a)*(fraction-k0)/(k1-k0) for a,b in zip(v0,v1))
 return values[-1]


def smil_state(group,t):
 """Evaluate the SMIL on a traffic group the way a browser's linear interpolation would."""
 fade=group.find(SVG+'animate')
 inner=group.find(SVG+'g')
 move=inner.find(SVG+'animateTransform')
 out=[]
 for node,parse in ((fade,lambda v:(float(v),)),(move,lambda v:tuple(float(n) for n in v.split()))):
  dur=float(node.attrib['dur'].rstrip('s'))
  begin=float(node.attrib['begin'].rstrip('s'))
  keys=[float(k) for k in node.attrib['keyTimes'].split(';')]
  values=[parse(v) for v in node.attrib['values'].split(';')]
  assert len(keys)==len(values) and keys[0]==0 and keys[-1]==1 and keys==sorted(keys)
  assert node.attrib.get('calcMode','linear')=='linear'
  out.append(lerp(keys,values,((t-begin)%dur)/dur))
 return out[0][0],out[1]


class SceneTests(unittest.TestCase):
 def test_space_traffic_repeats_after_master_cycle(self):
  for t in (0,3,7.4,18):
   self.assertEqual(scene.traffic(t,False),scene.traffic(t+scene.PERIOD,False))

 def test_cad_geometry_is_periodic_and_finite(self):
  for t in (0,.3,2.7):
   a=scene.cube_points(t)
   b=scene.cube_points(t+2*math.pi)
   for p,q in zip(a,b):
    for x,y in zip(p,q):
     self.assertTrue(math.isfinite(x))
     self.assertAlmostEqual(x,y,places=8)

 def test_open_stroked_trajectory_cannot_fill_the_sky(self):
  doc=ET.fromstring('<svg xmlns="http://www.w3.org/2000/svg">'+scene.sky_details(0,False)+'</svg>')
  for path in doc.iter(SVG+'path'):
   d=path.attrib.get('d','')
   if d.count('L')>=2 and 'Z' not in d.upper():
    self.assertEqual(path.attrib.get('fill'),'none','An open trajectory would become an opaque polygon')

 def test_frame_generation_is_deterministic_and_changes_with_time(self):
  self.assertEqual(scene.layers(0,False),scene.layers(0,False))
  self.assertNotEqual(scene.layers(0,False),scene.layers(6,False))

 def test_sprite_rectangles_fit_the_supplied_atlas(self):
  for name,(rect,origin) in scene.RECTS.items():
   x,y,w,h=rect
   self.assertGreater(w,0,name)
   self.assertGreater(h,0,name)
   self.assertGreaterEqual(x,0,name)
   self.assertGreaterEqual(y,0,name)
   self.assertLessEqual(x+w,1536,name)
   self.assertLessEqual(y+h,1024,name)
   self.assertTrue(x<=origin[0]<=x+w,name)
   self.assertTrue(y<=origin[1]<=y+h,name)

 def test_traffic_stays_out_of_text_and_in_open_sky(self):
  self.assertLessEqual(len(scene.SKYLINE),40)
  self.assertEqual(sorted(p[0] for p in scene.SKYLINE),[p[0] for p in scene.SKYLINE])
  self.assertEqual((scene.SKYLINE[0][0],scene.SKYLINE[-1][0]),(0,scene.W))
  for t in SAMPLES:
   for state in scene.traffic_state(t):
    if state['opacity']<=VISIBLE:
     continue
    box=state['bbox']
    self.assertFalse(overlap(box,scene.TEXT_RECT),(t,state['id'],box))
    top=scene.skyline_top(box[0],box[2])
    if top is not None:
     self.assertLess(box[3],top,(t,state['id'],box,top))

 def test_airplane_clears_telescope_finder_and_right_edge_foreground(self):
  for t in SAMPLES:
   plane=[s for s in scene.traffic_state(t) if s['id']=='airplane'][0]
   if plane['opacity']>VISIBLE:
    if plane['bbox'][0]<830 and plane['bbox'][2]>790:
     self.assertLess(plane['bbox'][3],548,t)
    self.assertLess(plane['bbox'][2],1440,t)  # nothing near the workshop roof / trees

 def test_traffic_sprites_never_overlap_each_other(self):
  for t in SAMPLES:
   states=[s for s in scene.traffic_state(t) if s['opacity']>VISIBLE]
   for i,a in enumerate(states):
    for b in states[i+1:]:
     self.assertFalse(overlap(a['sprite_bbox'],b['sprite_bbox']),(t,a['id'],b['id']))
     # exhaust must not be painted across another craft either
     self.assertFalse(overlap(a['trail_bbox'],b['sprite_bbox']),(t,a['id'],'trail',b['id']))
     self.assertFalse(overlap(b['trail_bbox'],a['sprite_bbox']),(t,b['id'],'trail',a['id']))

 def test_no_hard_clip_and_traffic_fades_smoothly(self):
  for animated in (False,True):
   svg=scene.scene(0,animated)
   self.assertNotIn('clip-path',svg)
   self.assertNotIn('clipPath',svg)
  for route in scene.ROUTES:
   keys=route['fade_keys']
   for (u0,v0),(u1,v1) in zip(keys,keys[1:]):
    if v0!=v1:
     self.assertGreaterEqual((u1-u0)*route['period'],1.0,(route['id'],'fade shorter than 1s'))
  previous=None
  for t in SAMPLES+[scene.PERIOD]:
   states=scene.traffic_state(t)
   if previous:
    for a,b in zip(previous,states):
     if abs(a['opacity']-b['opacity'])>.11:
      # only allowed as a wrap-around while the object is wholly outside the canvas
      for side in (a,b):
       self.assertFalse(side['opacity']>VISIBLE and on_canvas(side['bbox']),(t,side['id']))
   previous=states
  explorer=[s for s in scene.traffic_state(14.7) if s['id']=='explorer'][0]
  self.assertLessEqual(explorer['opacity'],VISIBLE)  # formerly sliced at x=574

 def test_animated_traffic_smil_reproduces_traffic_state(self):
  root=ET.fromstring(scene.scene(0,True))
  moving=[g for g in root.iter(SVG+'g') if g.attrib.get('class')=='moving'][0]
  groups={g.attrib['data-traffic']:g for g in moving.iter(SVG+'g') if 'data-traffic' in g.attrib}
  self.assertEqual(sorted(groups),sorted(r['id'] for r in scene.ROUTES))
  for t in [0,.7,3.1,6,9.95,12,14.7,15.6,17.3,20.05,23.9]+[i*1.7 for i in range(14)]:
   for state in scene.traffic_state(t):
    opacity,(x,y)=smil_state(groups[state['id']],t)
    self.assertAlmostEqual(opacity,state['opacity'],delta=2e-3,msg=(t,state['id']))
    self.assertAlmostEqual(x,state['x'],delta=3e-2,msg=(t,state['id']))
    self.assertAlmostEqual(y,state['y'],delta=3e-2,msg=(t,state['id']))

 def test_traffic_keeps_approved_character(self):
  states=scene.traffic_state(0)
  self.assertEqual([s['id'] for s in states],['explorer','fighter-a','fighter-b','airplane'])
  self.assertEqual([s['width'] for s in states],[295,133,103,142])
  for route in scene.ROUTES:
   self.assertEqual(scene.PERIOD%route['period'],0)
   heading=route['end']-route['start']
   self.assertLess(heading,0) if route['sprite']!='airplane' else self.assertGreater(heading,0)
  seen={r['id']:0 for r in scene.ROUTES}
  for t in [sample+.05 for sample in SAMPLES]:  # offset keeps exact wrap instants out of float noise
   current=scene.traffic_state(t)
   again=scene.traffic_state(t+scene.PERIOD)
   for a,b in zip(current,again):
    for key in ('x','y','opacity'):
     self.assertAlmostEqual(a[key],b[key],places=6,msg=(t,a['id'],key))
    seen[a['id']]+=a['opacity']>.5
    if a['id']=='explorer':
     self.assertTrue(330<=a['y']<=420)
    if a['id'].startswith('fighter'):
     self.assertGreater(a['y'],current[0]['y']+40)  # lower than the explorer
  for key,count in seen.items():
   self.assertGreaterEqual(count/len(SAMPLES),.35,key)

 @unittest.skipIf(Image is None,'Pillow not installed')
 def test_skyline_is_above_the_dark_foreground_of_the_plate(self):
  plate=Image.open(scene.ASSETS/'observatory-background.png').convert('RGB')
  pixels=plate.load()
  for x0 in range(0,scene.W-8,16):
   # The lit workshop roof is not near-black, so only the dark silhouettes are checked here.
   limit=int(scene.skyline_top(x0,x0+8))
   for y in range(380,limit-6,3):
    dark=sum(max(pixels[x,yy])<42 for x in range(x0,x0+8) for yy in range(y,y+24,2))
    self.assertLess(dark/96,.8,(x0,y,limit))


if __name__=='__main__':
 unittest.main()
