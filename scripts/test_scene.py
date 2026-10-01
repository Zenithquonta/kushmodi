import functools
import math
import random
import re
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


# ---------------------------------------------------------------------------
# Generic SMIL-vs-raster comparison.
#
# The animated SVG is parsed and every <animate>/<animateTransform> inside `.moving` is evaluated at time t
# by the small linear-SMIL interpreter below (written independently of build_animation.Track).  The result
# is a "snapshot" of the animated document at t.  Both that snapshot and the static frame scene(t, False) are
# flattened to a list of leaf shapes in document order: (tag, numeric/text attributes, cumulative transform
# matrix, cumulative opacity).  Flattening makes the comparison structure-independent (the moons nest
# scaled/rotated groups in SMIL but use one translate in the raster) while still covering every animated
# attribute: transform, opacity, x, y, x1, y1, x2, y2.
# ---------------------------------------------------------------------------
ANIMATIONS=(SVG+'animate',SVG+'animateTransform')
LEAVES={SVG+name for name in ('path','rect','line','ellipse','circle','svg')}  # nested <svg> is a sprite viewport
PX=.02  # px tolerance
OPACITY=.005
LINEAR=1e-4  # tolerance for matrix a-d (rotation/scale terms)
CHECK_TIMES=[0,.7,1.5,2.95,3.05,4.4,5.95,7.3,9.9,11.95,14.7,17.3,20.05,22.4,23.95]


def seconds(text):
 return float(text.rstrip('s'))


def numbers(text):
 return tuple(float(n) for n in text.replace(',',' ').split())


def smil_value(node,t):
 """Linear SMIL with repeatCount=indefinite and negative-begin semantics, as a browser evaluates it."""
 attrib=node.attrib
 assert attrib.get('repeatCount')=='indefinite',attrib
 assert attrib.get('calcMode','linear')=='linear',attrib
 assert not {'additive','accumulate','by','end','min','max','restart'} & set(attrib),attrib
 begin=seconds(attrib.get('begin','0s'))
 assert begin<=0,'positive begin would leave the first frames un-animated'
 dur=seconds(attrib['dur'])
 u=((t-begin)%dur)/dur
 if 'values' in attrib:
  values=[numbers(v) for v in attrib['values'].split(';')]
  if 'keyTimes' in attrib:
   keys=[float(k) for k in attrib['keyTimes'].split(';')]
  else:
   keys=[i/(len(values)-1) for i in range(len(values))]
  assert len(keys)==len(values) and keys[0]==0 and keys[-1]==1 and keys==sorted(keys),attrib
 else:
  values=[numbers(attrib['from']),numbers(attrib['to'])]
  keys=[0,1]
 for i in range(1,len(keys)):
  if u<=keys[i]:
   f=1 if keys[i]==keys[i-1] else (u-keys[i-1])/(keys[i]-keys[i-1])
   return tuple(a+(b-a)*f for a,b in zip(values[i-1],values[i]))
 return values[-1]


def matmul(m,n):
 a,b,c,d,e,f=m
 A,B,C,D,E,F=n
 return (a*A+c*B,b*A+d*B,a*C+c*D,b*C+d*D,a*E+c*F+e,b*E+d*F+f)


def parse_transform(text):
 matrix=(1,0,0,1,0,0)
 for name,args in re.findall(r'(\w+)\(([^)]*)\)',text or ''):
  v=numbers(args)
  if name=='translate':
   step=(1,0,0,1,v[0],v[1] if len(v)>1 else 0)
  elif name=='scale':
   step=(v[0],0,0,v[1] if len(v)>1 else v[0],0,0)
  elif name=='rotate':
   c,s=math.cos(math.radians(v[0])),math.sin(math.radians(v[0]))
   step=(c,s,-s,c,0,0)
  else:
   raise AssertionError(name)
  matrix=matmul(matrix,step)
 return matrix


def flatten(node,t=0,matrix=(1,0,0,1,0,0),opacity=1.0,out=None):
 """Leaf shapes under `node` at time t.  Animation children replace the attribute they target."""
 out=[] if out is None else out
 attrs=dict(node.attrib)
 for anim in node:
  if anim.tag in ANIMATIONS:
   value=smil_value(anim,t)
   name=anim.attrib['attributeName']
   if anim.tag==SVG+'animateTransform':
    attrs[name]=f'{anim.attrib["type"]}({" ".join(repr(v) for v in value)})'
   else:
    attrs[name]=repr(value[0])
 matrix=matmul(matrix,parse_transform(attrs.pop('transform',None)))
 opacity*=float(attrs.pop('opacity',1))
 if node.tag in LEAVES:
  out.append((node.tag.replace(SVG,''),attrs,matrix,opacity))
 else:
  for child in node:
   if child.tag not in ANIMATIONS:
    flatten(child,t,matrix,opacity,out)
 return out


WRAP='<g xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">{}</g>'


def animated_root():
 """The `.moving` content of scene(animated=True), i.e. layers(0,True), without the 6MB image data URIs."""
 return ET.fromstring(WRAP.format(scene.layers(0,True)))


@functools.lru_cache(maxsize=None)
def static_cached(t):
 return flatten(ET.fromstring(WRAP.format(scene.layers(t,False))))


def same(a,b,tol):
 try:
  return abs(float(a)-float(b))<=tol
 except ValueError:
  return a==b


def sprite_leaves(t,name):
 """Static-frame <svg> sprite viewports showing atlas rectangle `name`, in document order."""
 x,y,w,h=scene.RECTS[name][0]
 box=f'{x} {y} {w} {h}'
 return [l for l in static_cached(t) if l[0]=='svg' and l[1].get('viewBox')==box]


def leaf_index(t,name):
 """Document-order position of each sprite of `name` among all static leaves (drawing order)."""
 x,y,w,h=scene.RECTS[name][0]
 return [i for i,l in enumerate(static_cached(t)) if l[0]=='svg' and l[1].get('viewBox')==f'{x} {y} {w} {h}']


def parents(root):
 return {child:node for node in root.iter() for child in node}



def path_points(d):
 """Corner points of an absolute/relative M L H V h v l z path (the only commands the scene uses)."""
 tokens=re.findall(r'[MLHVhvlz]|-?\d*\.?\d+',d)
 points,x,y,start,i,cmd=[],0.0,0.0,(0.0,0.0),0,None
 while i<len(tokens):
  if tokens[i].isalpha():
   cmd=tokens[i]
   i+=1
   if cmd=='z':
    x,y=start
    continue
  if cmd in 'ML':
   x,y=float(tokens[i]),float(tokens[i+1])
   i+=2
   if cmd=='M':
    start=(x,y)
    cmd='L'
  elif cmd=='l':
   x,y=x+float(tokens[i]),y+float(tokens[i+1])
   i+=2
  elif cmd=='H':
   x=float(tokens[i]); i+=1
  elif cmd=='h':
   x+=float(tokens[i]); i+=1
  elif cmd=='V':
   y=float(tokens[i]); i+=1
  elif cmd=='v':
   y+=float(tokens[i]); i+=1
  else:
   raise AssertionError(cmd)
  points.append((x,y))
 return points


def leaf_bbox(leaf):
 """Scene-space bounding box of a flattened path/rect/line leaf, stroke included (None for anything else)."""
 tag,attrs,m,_=leaf
 if tag=='path':
  points=path_points(attrs['d'])
  pad=float(attrs.get('stroke-width',0))/2 if attrs.get('stroke') else 0
 elif tag=='rect':
  x,y,w,h=(float(attrs[k]) for k in ('x','y','width','height'))
  points,pad=[(x,y),(x+w,y+h)],0
 elif tag=='line':
  points=[(float(attrs['x1']),float(attrs['y1'])),(float(attrs['x2']),float(attrs['y2']))]
  pad=float(attrs['stroke-width'])/2
 else:
  return None
 xs=[m[0]*x+m[2]*y+m[4] for x,y in points]
 ys=[m[1]*x+m[3]*y+m[5] for x,y in points]
 padx,pady=pad,pad
 if tag=='line' and m[1]==0 and m[2]==0:  # butt caps: a horizontal line is only as thick as its stroke, a vertical one as wide
  horizontal=points[0][1]==points[1][1]
  vertical=points[0][0]==points[1][0]
  padx,pady=(0 if horizontal else pad),(0 if vertical else pad)
 return (min(xs)-padx,min(ys)-pady,max(xs)+padx,max(ys)+pady)


def contains(outer,inner,slack=.05):
 return outer[0]-slack<=inner[0] and outer[1]-slack<=inner[1] and inner[2]<=outer[2]+slack and inner[3]<=outer[3]+slack


def lock_parts(t):
 """{part name: [(bbox, effective opacity)]} of every leaf of the lock-on layer in the static frame at t."""
 root=ET.fromstring(WRAP.format(scene.lock_on(t,False)))
 return {g.attrib['data-lock']:[(leaf_bbox(l),l[3]) for l in flatten(g) if leaf_bbox(l)] for g in root}


def distance_to_box(point,box):
 dx=max(box[0]-point[0],0,point[0]-box[2])
 dy=max(box[1]-point[1],0,point[1]-box[3])
 return math.hypot(dx,dy)


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
     # warp streaks are light, but still must not be painted across another craft or its exhaust
     for p,q in ((a,b),(b,a)):
      if p['streak_bbox']:
       self.assertFalse(overlap(p['streak_bbox'],q['sprite_bbox']),(t,p['id'],'streak',q['id']))
       self.assertFalse(overlap(p['streak_bbox'],q['trail_bbox']),(t,p['id'],'streak',q['id'],'trail'))
       if q['streak_bbox']:
        self.assertFalse(overlap(p['streak_bbox'],q['streak_bbox']),(t,p['id'],q['id'],'streaks'))

 def test_no_hard_clip_and_traffic_fades_smoothly(self):
  for animated in (False,True):
   svg=scene.scene(0,animated)
   self.assertNotIn('clip-path',svg)
   self.assertNotIn('clipPath',svg)
  for route in scene.ROUTES:
   keys=route['fade_keys']
   for (u0,v0),(u1,v1) in zip(keys,keys[1:]):
    if v0!=v1 and not route.get('warp'):
     self.assertGreaterEqual((u1-u0)*route['period'],1.0,(route['id'],'fade shorter than 1s'))
  previous=None
  for t in SAMPLES+[scene.PERIOD]:
   states=scene.traffic_state(t)
   if previous:
    for a,b in zip(previous,states):
     if abs(a['opacity']-b['opacity'])>.11 and not (a['warp'] and (a['warp']['active'] or b['warp']['active'])):
      # only allowed as a wrap-around while the object is wholly outside the canvas (warps handle their own transition)
      for side in (a,b):
       self.assertFalse(side['opacity']>VISIBLE and on_canvas(side['bbox']),(t,side['id']))
   previous=states
  explorer=[s for s in scene.traffic_state(14.7) if s['id']=='explorer'][0]
  self.assertLessEqual(explorer['opacity'],VISIBLE)  # formerly sliced at x=574
  # the explorer is only ever visible right of its warp point, well clear of the text block
  for t in SAMPLES:
   explorer=[s for s in scene.traffic_state(t) if s['id']=='explorer'][0]
   if explorer['opacity']>VISIBLE:
    self.assertGreater(explorer['bbox'][0],scene.TEXT_RECT[2]+30,t)

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

 def test_every_animation_reproduces_the_raster_frame(self):
  self.assertIn('<g class="moving">'+scene.layers(0,True)+'</g>',scene.scene(0,True))  # what animated_root() parses
  self.assertIn('<g class="still">'+scene.layers(0,False)+'</g>',scene.scene(0,True))
  moving=animated_root()
  animations=[n for n in moving.iter() if n.tag in ANIMATIONS]
  names={n.attrib['attributeName'] for n in animations}
  self.assertTrue({'transform','opacity','x','y','x1','y1','x2','y2'}<=names,names)
  self.assertGreater(len(animations),90)
  for t in CHECK_TIMES:
   animated=flatten(moving,t)
   static=static_cached(t)
   self.assertEqual([leaf[0] for leaf in animated],[leaf[0] for leaf in static],t)
   for index,((tag,a_attrs,a_m,a_o),(_,s_attrs,s_m,s_o)) in enumerate(zip(animated,static)):
    where=(t,index,tag,s_attrs.get('d','')[:20] or s_attrs.get('x') or s_attrs.get('x1'))
    self.assertEqual(sorted(a_attrs),sorted(s_attrs),where)
    for key in a_attrs:
     self.assertTrue(same(a_attrs[key],s_attrs[key],PX),(where,key,a_attrs[key],s_attrs[key]))
    self.assertAlmostEqual(a_o,s_o,delta=OPACITY,msg=where)
    for k in range(4):
     self.assertAlmostEqual(a_m[k],s_m[k],delta=LINEAR,msg=(where,'matrix',k))
    for k in (4,5):
     self.assertAlmostEqual(a_m[k],s_m[k],delta=PX,msg=(where,'matrix',k))

 def test_animation_comparison_would_notice_a_phase_error(self):
  moving=animated_root()
  bob=[n for n in moving.iter(SVG+'animateTransform') if n.attrib['dur']=='24s' and n.attrib['type']=='translate'
       and 'values' in n.attrib and n.attrib['values'].startswith('1480 ')][0]
  true_y=lambda t:163+3*math.sin(2*math.pi*t/24)
  self.assertAlmostEqual(smil_value(bob,6)[1],true_y(6),delta=.05)
  # the old triangle (163,160,163,166,163) would have been 6px away from the raster here
  self.assertGreater(abs(160-true_y(6)),5.9)

 def test_motion_keeps_the_approved_raster_definitions(self):
  def leaf(t,**match):
   found=[l for l in static_cached(t) if all(l[1].get(k)==v for k,v in match.items())]
   self.assertEqual(len(found),1,match)
   return found[0]
  for t in [i/10 for i in range(0,240,7)]:
   sine=lambda period,phase=0:math.sin(2*math.pi*t/period+phase)
   # planet bob, nozzle, scan: centre, amplitude, period of the approved GIF
   planet_y=sprite_leaves(t,'planet')[0][2][5]
   self.assertAlmostEqual(planet_y,163+3*sine(24),delta=.05,msg=t)
   self.assertAlmostEqual(float(leaf(t,fill='#71edff')[1]['x']),1335+20*sine(3),delta=.25,msg=t)
   self.assertAlmostEqual(float(leaf(t,fill='#83eaff')[1]['y']),749+18*sine(6),delta=.25,msg=t)
   for x,phase in ((1596,0),(1380,.4),(1196,.7),(1505,.2)):
    led=leaf(t,x=str(x),width='4')
    self.assertAlmostEqual(led[3],.35+.65*(.5+.5*sine(3,phase)),delta=.01,msg=(t,x))
   reticle=[l for l in static_cached(t) if l[1].get('stroke')=='#4ae8f2'][0]
   self.assertAlmostEqual(reticle[3],(.5+.3*sine(3))*scene.LOCK['idle'].at(t),delta=.01,msg=t)  # steps aside during the lock-on
   u=(t/12)%1
   meteor=leaf(t,stroke='#88e4fc')
   self.assertAlmostEqual(meteor[3],math.sin(math.pi*u/.16)**2 if u<.16 else 0,delta=.01,msg=t)
   self.assertAlmostEqual(meteor[2][4],1100+390*u,delta=.01)
   cube=scene.cube_points(t*2*math.pi/6)
   edge=[l for l in static_cached(t) if l[1].get('stroke')=='#72f0ff'][0]  # cube edge from vertex 0 to 1
   self.assertAlmostEqual(float(edge[1]['x1']),cube[0][0],delta=.25,msg=t)
   self.assertAlmostEqual(float(edge[1]['y1']),cube[0][1],delta=.25,msg=t)
   self.assertAlmostEqual(float(edge[1]['x2']),cube[1][0],delta=.25,msg=t)
   self.assertAlmostEqual(float(edge[1]['y2']),cube[1][1],delta=.25,msg=t)
  # seeded star field: same positions, periods and phases as the approved scene
  rng=random.Random(29)
  expected=[]
  for _ in range(32):
   x,y=rng.randint(20,1650),rng.randint(18,500)
   if 30<x<565 and 218<y<375:
    continue
   expected.append((x,y,rng.choice([3,4,6,8]),rng.random()))
  stars=[n for n in animated_root().iter(SVG+'path') if n.attrib.get('stroke')=='#a7deff']
  self.assertEqual(len(stars),len(expected))
  for node,(x,y,period,phase) in zip(stars,expected):
   self.assertEqual(node.attrib['d'],f'M{x-3} {y}h6M{x} {y-3}v6')
   anim=node.find(SVG+'animate')
   self.assertEqual(seconds(anim.attrib['dur']),period)
   self.assertAlmostEqual(seconds(anim.attrib['begin']),-phase*period,delta=1e-4)
   for t in (0,1.3,period/3,5.5):
    self.assertAlmostEqual(smil_value(anim,t)[0],.2+.8*(.5+.5*math.sin(2*math.pi*(t/period+phase))),delta=.01)

 def test_every_animation_loops_without_a_jump(self):
  moving=animated_root()
  up=parents(moving)
  count=0
  for node in moving.iter():
   if node.tag not in ANIMATIONS:
    continue
   ancestors=[]
   walker=up.get(node)
   while walker is not None:
    ancestors.append(walker)
    walker=up.get(walker)
   if any('data-traffic' in g.attrib for g in ancestors):
    continue  # traffic is an intentional sawtooth that wraps while fully transparent (see traffic tests)
   if any('data-spin' in g.attrib for g in ancestors):
    continue  # galaxy copies hand over to each other at their wrap (see the slow-spin test)
   if any(g.attrib.get('data-season')=='rain' for g in ancestors):
    continue  # rain shifts by exactly one tile of identical streaks per period, so its wrap is seamless by construction
   count+=1
   dur=seconds(node.attrib['dur'])
   self.assertEqual(scene.PERIOD%dur,0,node.attrib)
   if 'values' in node.attrib:
    values=[numbers(v) for v in node.attrib['values'].split(';')]
    self.assertEqual(values[0],values[-1],node.attrib)
    keys=([float(k) for k in node.attrib['keyTimes'].split(';')] if 'keyTimes' in node.attrib
          else [i/(len(values)-1) for i in range(len(values))])
    slope=max((math.dist(a,b)/((k1-k0)*dur) for a,b,k0,k1 in zip(values,values[1:],keys,keys[1:]) if k1>k0),default=0)
    before,after=smil_value(node,23.95),smil_value(node,24)
    self.assertLessEqual(math.dist(before,after),.05*slope+1e-6,node.attrib)
    for t in (0,2.9,5.5):
     self.assertLess(math.dist(smil_value(node,t),smil_value(node,t+scene.PERIOD)),1e-6,node.attrib)
   elif node.attrib['type']=='rotate':
    self.assertEqual(abs(float(node.attrib['to'])-float(node.attrib['from'])),360,node.attrib)
   else:
    # the meteor translate restarts from its origin; it must be fully transparent at the wrap
    fade=[n for n in up[node] if n.tag==SVG+'animate' and n.attrib['attributeName']=='opacity'][0]
    for t in (23.95,24,0):
     self.assertLessEqual(smil_value(fade,t)[0],VISIBLE,t)
  self.assertGreater(count,80)

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

 def test_animated_cube_is_registered_on_the_painted_cube(self):
  left,top,right,bottom=scene.PAINTED_CUBE
  # the painted extent as stored must still be what the plate contains (bright cyan outline pixels)
  if Image is not None:
   pixels=Image.open(scene.ASSETS/'observatory-background.png').convert('RGB').load()
   lit=[(x,y) for y in range(680,745) for x in range(1425,1496)
        if pixels[x,y][1]>180 and pixels[x,y][2]>200 and pixels[x,y][0]<130]
   self.assertGreater(len(lit),300)
   self.assertEqual((min(p[0] for p in lit),min(p[1] for p in lit),max(p[0] for p in lit)+1,max(p[1] for p in lit)+1),
                    scene.PAINTED_CUBE)
  # rest pose (the t=0 frame): footprint is the painted 46x45 box to within 3px, centred on it to within 1.5px
  points=scene.cube_points(0)
  xs,ys=[p[0] for p in points],[p[1] for p in points]
  for found,wanted in ((min(xs),left),(min(ys),top),(max(xs),right),(max(ys),bottom)):
   self.assertAlmostEqual(found,wanted,delta=3)
  self.assertAlmostEqual((min(xs)+max(xs))/2,(left+right)/2,delta=1.5)
  self.assertAlmostEqual((min(ys)+max(ys))/2,(top+bottom)/2,delta=1.5)
  self.assertAlmostEqual(max(xs)-min(xs),right-left,delta=3)
  self.assertAlmostEqual(max(ys)-min(ys),bottom-top,delta=3)
  # the first frame of the SVG/raster draws that same pose, and the cube never leaves the workshop wall
  edge=[l for l in static_cached(0) if l[1].get('stroke')=='#72f0ff'][0]
  self.assertAlmostEqual(float(edge[1]['x1']),points[0][0],delta=.01)
  for theta in (i*2*math.pi/24 for i in range(24)):
   for x,y in scene.cube_points(theta):
    self.assertTrue(1432<=x<=1490 and 684<=y<=738,(theta,x,y))

 def test_cube_reads_as_three_dimensional_at_every_pose(self):
  for step in range(96):  # four poses per animation keyframe
   pts=scene.cube_points(step*2*math.pi/96)
   top=[pts[i] for i in (0,1,5,4)]  # the y=-1 face
   area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(top,top[1:]+top[:1])))/2
   self.assertGreater(area,250,step)  # ~295 at every pose: the top face never collapses to an edge
   # perspective: the four vertical edges are never all the same length, so a face-on pose still shows near/far faces
   edges=[math.dist(pts[i],pts[j]) for i,j in ((0,3),(1,2),(4,7),(5,6))]
   self.assertGreater(max(edges)/min(edges),1.08,step)

 def test_cube_has_restrained_glow_under_the_crisp_edges(self):
  strokes=[l for l in static_cached(0) if l[0]=='line' and l[1].get('stroke-linecap')=='round']  # warp streaks are other <line>s
  crisp=[l for l in strokes if l[1]['stroke']=='#72f0ff']
  glow=[l for l in strokes if l[1]['stroke']!='#72f0ff']
  self.assertEqual(len(crisp),12)
  self.assertEqual(len(glow),12*len(scene.GLOW))
  self.assertEqual(strokes[-12:],crisp)  # crisp edges drawn on top of the glow
  for l in glow:
   self.assertGreater(float(l[1]['stroke-width']),float(crisp[0][1]['stroke-width']))
   self.assertLessEqual(l[3],.25)
  self.assertNotIn('<filter id="cube-glow"',scene.scene(0,True))  # plain strokes only, identical in every engine

 def test_painted_cube_is_covered_by_a_patch_of_the_embedded_plate_only(self):
  svg=scene.scene(0,True)
  self.assertEqual(svg.count('data:image/png'),2)  # atlas and plate, no third raster copy
  self.assertEqual(svg.count('<image '),2)
  self.assertIn('href="#plate"',svg)
  self.assertIn('id="cube-feather"',svg)
  self.assertNotIn('clip-path',svg)
  ET.fromstring(svg)
  x,y,w,h=scene.PATCH_TARGET
  left,top,right,bottom=scene.PAINTED_CUBE
  self.assertTrue(x<=left-4 and y<=top-4 and x+w>=right+4 and y+h>=bottom+4)  # covers the outline with margin
  for sx,sy,sw,sh in (scene.PATCH_SOURCE,scene.PATCH_LOW):
   self.assertTrue(sy+sh<=top-1 or sy>=bottom+3)  # strips come from wall outside the painted cube

 def test_moons_hide_behind_the_planet_on_the_far_half_only(self):
  for t in SAMPLES:
   order=leaf_index(t,'planet')
   self.assertEqual(len(order),1)
   moons=leaf_index(t,'moon')
   self.assertEqual(len(moons),4)  # (behind, front) copies of both moons, behind copies first
   self.assertEqual([i<order[0] for i in moons],[True,True,False,False],t)
   for moon,(phase,size,period) in enumerate(scene.MOONS):
    theta=2*math.pi*t/period+phase
    behind,front=(static_cached(t)[moons[moon+offset]] for offset in (0,2))
    cx,cy,rx,ry=scene.ORBIT
    for leaf in (behind,front):
     self.assertAlmostEqual(leaf[2][4],cx+rx*math.cos(theta),delta=.01,msg=(t,moon))
     self.assertAlmostEqual(leaf[2][5],cy+ry*math.sin(theta),delta=.01,msg=(t,moon))
    self.assertAlmostEqual(behind[3]+front[3],1,delta=1e-9,msg=(t,moon))  # never both, never neither
    if math.sin(theta)<-1e-9:
     self.assertEqual((behind[3],front[3]),(1,0),(t,moon,'far half: occluded by the planet'))
    elif math.sin(theta)>1e-9:
     self.assertEqual((behind[3],front[3]),(0,1),(t,moon,'near half: in front of the planet'))

 def test_moon_layer_switches_are_exact_steps_at_theta_zero_and_pi(self):
  for phase,size,period in scene.MOONS:
   behind=scene.moon_layer(phase,period,True)
   front=scene.moon_layer(phase,period,False)
   for k in range(2):  # theta = pi (near -> far) and theta = 2*pi (far -> near)
    switch=(math.pi*(k+1)-phase)/(2*math.pi)*period
    for dt,far in ((-.01,k==1),(.01,k==0)):
     self.assertEqual(behind.at(switch+dt),1.0 if far else 0.0,(phase,k,dt))
     self.assertEqual(front.at(switch+dt),0.0 if far else 1.0,(phase,k,dt))
   self.assertEqual(behind.values[0],behind.values[-1])
   # an exact SMIL step, not a fade: only the coincident key times change the value
   self.assertEqual(len(set(behind.key_times)),4)

 def test_moon_layer_markup_uses_coincident_key_times(self):
  moving=ET.fromstring(WRAP.format(scene.layers(0,True)))
  layers=[g for g in moving.iter(SVG+'g') if g.attrib.get('data-moon')]
  self.assertEqual([g.attrib['data-moon'] for g in layers],['behind','behind','front','front'])
  for g in layers:
   anim=g.find(SVG+'animate')
   self.assertEqual(anim.attrib['attributeName'],'opacity')
   keys=anim.attrib['keyTimes'].split(';')
   self.assertEqual(keys,['0','0.25','0.25','0.75','0.75','1'])
   self.assertEqual(len(keys),6)
   self.assertEqual(keys[1],keys[2])
   self.assertEqual(keys[3],keys[4])

 # ------------------------------------------------------------------ telescope lock-on
 def test_lock_on_never_touches_the_text_block_or_covers_the_galaxy_core(self):
  core=scene.LOCK_CORE
  seen=set()
  for t in SAMPLES:
   parts=lock_parts(t)
   state=scene.lock_state(t)
   self.assertEqual(sorted(parts),['leader','line','readout','reticle'])
   for name,leaves in parts.items():
    for box,opacity in leaves:
     self.assertFalse(overlap(box,scene.TEXT_RECT),(t,name,box))   # every leaf, visible or not
     self.assertGreaterEqual(box[0],0); self.assertLessEqual(box[2],scene.W)
     self.assertGreaterEqual(box[1],0); self.assertLessEqual(box[3],scene.H)
     if name in ('readout','leader'):
      self.assertGreater(distance_to_box(core,box),60,(t,name,box))  # core and its immediate bright disc stay clear
     if opacity>VISIBLE:
      seen.add(name)
      if name!='line':  # the dotted line deliberately starts on the telescope finder itself
       self.assertLess(box[3],scene.skyline_top(box[0],box[2]),(t,name))
    # the declared boxes (used for the area budget) really contain the drawn geometry
    union=(min(b[0] for b,_ in leaves),min(b[1] for b,_ in leaves),max(b[2] for b,_ in leaves),max(b[3] for b,_ in leaves))
    self.assertTrue(contains(state[name]['bbox'],union,1.0) or name=='readout',(t,name,union,state[name]['bbox']))
   readout=[b for b,_ in parts['readout']]
   for box in readout:
    self.assertTrue(contains(scene.LOCK_READOUT_BOX,box),(t,box,scene.LOCK_READOUT_BOX))
  self.assertEqual(seen,{'line','reticle','leader','readout'})  # and it really does show up

 def test_lock_on_sequence_runs_once_and_holds_for_a_few_seconds(self):
  visible=[t for t in SAMPLES if scene.lock_state(t)['readout']['opacity']>.5]
  self.assertTrue(4<=len(visible)/10<=6.5,len(visible)/10)  # hold ~4-6 s with the full readout
  self.assertEqual([round(v*10) for v in visible],[round(visible[0]*10)+i for i in range(len(visible))])  # one contiguous hold per loop
  first=min(t for t in SAMPLES if scene.lock_state(t)['line']['opacity']>VISIBLE)
  last=max(t for t in SAMPLES if scene.lock_state(t)['reticle']['opacity']>VISIBLE)
  self.assertLess(first,visible[0]); self.assertLess(visible[-1],last)  # line first, readout once locked, then it fades
  for t in (0,5,11,22,23.9):
   state=scene.lock_state(t)
   self.assertLessEqual(max(state[k]['opacity'] for k in ('line','reticle','leader','readout')),VISIBLE,t)
  # the reticle snaps around the galaxy core: brackets close in, overshoot slightly, then settle on LOCK_HALF
  half=scene.LOCK['half']
  self.assertGreater(half.at(13.4),2*scene.LOCK_HALF)
  self.assertLess(min(half.at(i/100) for i in range(1300,1600)),scene.LOCK_HALF)
  self.assertEqual(half.at(17),scene.LOCK_HALF)
  box=scene.lock_state(17)['reticle']['bbox']
  self.assertEqual(((box[0]+box[2])/2,(box[1]+box[3])/2),scene.LOCK_CORE)
  # the dotted line starts at the finder and ends under the reticle, drawn on by its end point only
  self.assertEqual((scene.LOCK['line_x'].at(12),scene.LOCK['line_y'].at(12)),scene.LOCK_FROM)
  self.assertEqual((scene.LOCK['line_x'].at(17),scene.LOCK['line_y'].at(17)),scene.LOCK_END)
  self.assertLess(scene.LOCK_END[1],scene.LOCK_CORE[1]+scene.LOCK_HALF+10)

 def test_there_is_never_more_than_one_reticle_and_the_lock_stays_small(self):
  sky=scene.W*580  # sky above the horizon
  for t in SAMPLES:
   state=scene.lock_state(t)
   idle=scene.LOCK['idle'].at(t)
   self.assertFalse(idle>.25 and state['reticle']['opacity']>.25,t)  # old target reticle steps aside for the lock
   area=sum((state[k]['bbox'][2]-state[k]['bbox'][0])*(state[k]['bbox'][3]-state[k]['bbox'][1])
            for k in ('line','reticle','leader','readout') if state[k]['opacity']>VISIBLE)
   self.assertLess(area,.10*sky,t)
  # the idle reticle really is the only other one: a single 4-corner bracket in each layer
  idle_group=[g for g in ET.fromstring(WRAP.format(scene.sky_details(0,False))).iter(SVG+'g') if 'data-idle' in g.attrib]
  self.assertEqual(len(idle_group),1)
  reticles=[l for l in flatten(idle_group[0]) if l[1].get('stroke')=='#4ae8f2']
  self.assertEqual(len(reticles),1)

 def test_readout_is_pixel_font_rectangles_and_says_what_was_requested(self):
  svg=scene.scene(0,True)
  self.assertNotIn('<text',svg)
  self.assertNotIn('<script',svg)
  self.assertEqual(scene.LOCK_READOUT,("TARGET LOCK \u00b7 M51","RA 13h29m","DEC +47\u00b011'"))
  self.assertEqual(len(scene.LOCK_LINES),3)
  for text,(d,x,y,w,h) in zip(scene.LOCK_READOUT,scene.LOCK_LINES):
   d2,w2,h2=scene.pixel_text(text,x,y)
   self.assertEqual((d,w,h),(d2,w2,h2))
   points=path_points(d)
   cell=scene.CELL
   self.assertTrue(all(x<=px<=x+w and y<=py<=y+h for px,py in points),text)
   self.assertTrue(all((px-x)%cell==0 and (py-y)%cell==0 for px,py in points))  # snapped to the cell grid
   self.assertEqual(h,5*cell)
  # glyph coverage and shape sanity: every character is defined, rows are the same width
  for char,rows in scene.FONT.items():
   self.assertEqual(len(rows),5,char)
   self.assertEqual(len({len(r) for r in rows}),1,char)
  for text in scene.LOCK_READOUT:
   for char in text:
    self.assertIn(char,scene.FONT)
  # the readout appears below the lock layer's own cyan, translucent text colour
  self.assertIn('fill="#72f0ff"',scene.lock_on(15,False))

 # ------------------------------------------------------------------ warp / hyperspace
 def test_warp_geometry_stays_in_open_sky_and_inside_its_declared_boxes(self):
  streak_seen={'explorer':0,'fighter-a':0,'fighter-b':0}
  stretched=flashes=0
  for t in SAMPLES:
   states=scene.traffic_state(t)
   root=ET.fromstring(WRAP.format(scene.traffic(t,False)))
   lines=[l for l in flatten(root) if l[0]=='line']
   expected=sum(len(r['warp']['lines']) for r in scene.ROUTES if r.get('warp'))
   self.assertEqual(len(lines),expected)
   cursor=0
   for route,state in zip(scene.ROUTES,states):
    warp=route.get('warp')
    if not warp:
     continue
    mine,cursor=lines[cursor:cursor+len(warp['lines'])],cursor+len(warp['lines'])
    for leaf in mine:
     box=leaf_bbox(leaf)
     if leaf[3]>VISIBLE:
      streak_seen[state['id']]+=1
      self.assertIsNotNone(state['streak_bbox'],(t,state['id']))
      self.assertTrue(contains(state['streak_bbox'],box),(t,state['id'],box,state['streak_bbox']))
      self.assertFalse(overlap(box,scene.TEXT_RECT),(t,state['id'],'streak',box))
      top=scene.skyline_top(box[0],box[2])
      self.assertTrue(top is None or box[3]<top,(t,state['id'],'streak'))
    if warp['flash']:  # the sparkle must lie inside the declared streak box and clear of the text block while visible
     for leaf in flatten(root):
      if leaf[0]=='path' and leaf[1].get('fill') in ('#f2ffff','#8af0ff') and leaf[3]>VISIBLE:
       flashes+=1
       box=leaf_bbox(leaf)
       self.assertTrue(contains(state['streak_bbox'],box),(t,'sparkle',box,state['streak_bbox']))
       self.assertFalse(overlap(box,scene.TEXT_RECT),(t,'sparkle',box))
       self.assertTrue(9<=box[2]-box[0]<=22,box)
    if state['opacity']>VISIBLE:
     box=state['bbox']
     self.assertFalse(overlap(box,scene.TEXT_RECT),(t,state['id'],box))
     top=scene.skyline_top(box[0],box[2])
     self.assertTrue(top is None or box[3]<top,(t,state['id']))
    if state['warp'] and state['warp']['sx']>1.01:
     stretched+=1
     self.assertLessEqual(state['warp']['sx'],3.0)
     self.assertEqual(state['id'],'explorer')
  self.assertTrue(all(streak_seen.values()),streak_seen)
  self.assertGreaterEqual(stretched,3)
  self.assertGreaterEqual(flashes,4)  # the sparkle shows up in the sampled frames (core + halo)

 def test_warp_sequences_are_short_and_end_in_normal_flight(self):
  for route in scene.ROUTES:
   warp=route.get('warp')
   if not warp:
    continue
   self.assertTrue(.3<=warp['span']<=.6,(route['id'],warp['span']))
   self.assertEqual(scene.PERIOD%warp['ship'].dur,0)
   speed=(route['end']-route['start'])/route['period']
   if warp['kind']=='out':
    # stretch from the nose only, up to 3x, in the last half second; the ship is gone at the event
    scales=[v[0] for v in warp['stretch'].values]
    self.assertEqual(max(scales),3.0)
    self.assertEqual(warp['stretch'].values[0],(1.0,1.0))
    event=(warp['u0']*route['period']-route['phase']*route['period'])%route['period']
    self.assertAlmostEqual(warp['ship'].at(event),0,delta=.01)
    self.assertEqual(warp['ship'].at(event-.6),1)
    self.assertEqual(warp['stretch'].at(event-.6),(1,1))
    self.assertEqual(warp['stretch'].at(event-.01)[1],1)  # y is never scaled
    self.assertLess(warp['nose'],0)  # nose is on the flight side (these ships head left)
    flash=warp['flash']
    peak=event-.12
    self.assertGreater(flash['a'].at(peak),.99)
    self.assertLess(flash['a'].at(peak+.21),.01)       # the sparkle fades out over about 0.2 s
    self.assertLess(warp['ship'].at(peak+.1),.01)      # and the hull is gone one 10 fps frame after the flash
    self.assertGreater(warp['ship'].at(peak),.2)
    self.assertTrue(9<=flash['size']<=13)
    self.assertAlmostEqual(flash['pos'].at(peak)[0],warp['lines'][0]['x1'].at(peak),delta=.05)  # centred on the streak end
    self.assertLess(speed,0)
   else:
    event=(warp['u0']*route['period']-route['phase']*route['period'])%route['period']
    self.assertEqual(warp['ship'].at(event-.45),0)
    self.assertAlmostEqual(warp['ship'].at(event),1,delta=.01)       # fully there when the streaks have collapsed
    self.assertAlmostEqual(warp['streak'].at(event),0,delta=.01)
    self.assertEqual(warp['streak'].at(event+.3),0)
    self.assertEqual(warp['streak'].at(event-.45),0)
    for line in warp['lines']:
     self.assertAlmostEqual(line['x1'].at(event),0,delta=.1)  # collapsed to a point
     self.assertAlmostEqual(line['x2'].at(event),0,delta=.1)
     self.assertGreater(line['x2'].at(event-.4)-line['x1'].at(event-.4),60)
     self.assertLessEqual(abs(line['y'].at(event)),abs(line['y'].at(event-.4)))  # converging on the hull
    self.assertEqual({l['stroke'] for l in warp['lines']}<={'#ed78fc','#fff0ff'},True)  # magenta and white only
  # every warp channel is a Track on the route's own clock, so SMIL equals the raster by construction
  for route in scene.ROUTES:
   warp=route.get('warp')
   if warp:
    tracks=[warp['ship'],warp['streak']]+([warp['stretch']] if warp['stretch'] else [])
    for line in warp['lines']:
     tracks+=[v for v in (line['x1'],line['x2'],line['y']) if isinstance(v,scene.Track)]
    for track in tracks:
     self.assertEqual((track.dur,track.begin),(route['period'],round(-route['phase']*route['period'],4)+0.0))

 def test_objects_are_off_canvas_when_warp_channels_wrap(self):
  for route in scene.ROUTES:
   for t in (i/100 for i in range(0,2400,5)):
    u=(t/route['period']+route['phase'])%1
    if u<.01 or u>.99:
     state=[s for s in scene.traffic_state(t) if s['id']==route['id']][0]
     self.assertFalse(on_canvas(state['bbox']) and state['opacity']>VISIBLE,(route['id'],t,state['bbox']))

 def test_warp_markup_is_one_group_per_route_inside_the_moving_object(self):
  moving=animated_root()
  up=parents(moving)
  groups=[g for g in moving.iter(SVG+'g') if 'data-warp' in g.attrib]
  self.assertEqual([g.attrib['data-warp'] for g in groups],['out','in','in'])
  for g in groups:
   walker,ids=up.get(g),[]
   while walker is not None:
    ids.append(walker.attrib.get('data-traffic'))
    walker=up.get(walker)
   self.assertTrue(any(ids),ids)  # inside a data-traffic group, so it inherits the route motion
   anims=[n for n in g.iter() if n.tag in ANIMATIONS]
   self.assertGreaterEqual(len(anims),3)
   for n in anims:
    self.assertEqual(n.attrib['repeatCount'],'indefinite')
    self.assertLess(seconds(n.attrib['begin']),0)
   self.assertIsNone(g.find(SVG+'filter'))
  layers=scene.layers(0,True)
  for forbidden in ('<filter','filter=','<text','<script','<image','<foreignObject','<mask'):
   self.assertNotIn(forbidden,layers)

 # ------------------------------------------------------------------ airplane navigation lights
 def test_navigation_lights_ride_the_airplane_and_their_periods_divide_the_loop(self):
  moving=animated_root()
  up=parents(moving)
  lights=[g for g in moving.iter(SVG+'g') if g.attrib.get('data-lights')=='airplane']
  self.assertEqual(len(lights),1)
  walker,ancestors=up.get(lights[0]),[]
  while walker is not None:
   ancestors.append(walker.attrib.get('data-traffic'))
   walker=up.get(walker)
  self.assertIn('airplane',ancestors)  # inside the airplane's own moving group
  durations={}
  for node in lights[0].iter():
   if node.tag in ANIMATIONS:
    dur=seconds(node.attrib['dur'])
    self.assertEqual(scene.PERIOD%dur,0,node.attrib)  # period divides 24 s
    self.assertEqual(node.attrib['attributeName'],'opacity')
    durations[dur]=durations.get(dur,0)+1
  self.assertEqual(durations,{3.0:2,scene.STROBE_PERIOD:1})  # red + green lamps (3 s), one strobe
  self.assertTrue(1<=scene.STROBE_PERIOD<=1.5)
  self.assertEqual(scene.PERIOD/scene.STROBE_PERIOD,16)
  # three lamps: red, green, white, each only a few pixels across
  rects=[l for l in flatten(lights[0]) if l[0]=='rect']
  cores=[l for l in rects if float(l[1]['width'])<=3]
  self.assertEqual(sorted(l[1]['fill'] for l in cores),['#38ff7a','#ff3b3b','#ffffff'])
  for l in rects:
   self.assertLessEqual(float(l[1]['width']),8)
  red=[l for l in cores if l[1]['fill']=='#ff3b3b'][0]
  green=[l for l in cores if l[1]['fill']=='#38ff7a'][0]
  # heading right, seen from starboard: the far (port, red) wing tip is up and aft of the near (starboard, green) one
  self.assertLess(float(red[1]['y']),float(green[1]['y'])-1)
  self.assertLess(float(red[1]['x']),float(green[1]['x']))

 def test_strobe_double_flashes_and_is_seen_in_the_gif_frames(self):
  strobe=scene.Track([v for _,v in scene.STROBE_KEYS],[s/scene.STROBE_PERIOD for s,_ in scene.STROBE_KEYS],scene.STROBE_PERIOD)
  samples=[strobe.at(i/1000) for i in range(0,1500)]
  flashes=sum(1 for a,b,c in zip(samples,samples[1:],samples[2:]) if b>a and b>=c and b>.5)
  self.assertEqual(flashes,2)  # exactly two flashes per period
  gif=[strobe.at(i/10) for i in range(240)]
  on=[v>.99 for v in gif]
  self.assertEqual(sum(on),32)  # 16 periods x 2 flashes: each lands exactly on a GIF frame
  self.assertTrue(all(v>.99 or v<.01 for v in gif))  # a frame sees a flash fully on or fully off
  self.assertEqual(sum(1 for a,b in zip(on,on[1:]) if a and b),0)  # never lit in two consecutive frames
  self.assertEqual(strobe.at(0),strobe.at(scene.STROBE_PERIOD))

 def test_galaxies_turn_slowly_and_hand_over_without_a_jump(self):
  moving=animated_root()
  spins=[g for g in moving.iter(SVG+'g') if 'data-spin' in g.attrib]
  self.assertEqual(len(spins),2)
  dissolving=[]
  for group in spins:
   copies=list(group)
   self.assertEqual(len(copies),2)
   def state(t):
    out=[]
    for copy in copies:
     fade=copy.find(SVG+'animate')
     turn=copy.find(SVG+'g').find(SVG+'animateTransform')
     out.append((smil_value(fade,t)[0],smil_value(turn,t)[0]))
    return out
   turn=copies[0].find(SVG+'g').find(SVG+'animateTransform')
   self.assertEqual(abs(float(turn.attrib['to'])-float(turn.attrib['from'])),180)  # half the old speed
   begin=-seconds(turn.attrib.get('begin','0s'))
   wrap=(scene.PERIOD-begin)%scene.PERIOD or scene.PERIOD
   # just before the wrap only the incoming copy shows, at the angle the outgoing copy restarts from
   (a_end,_),(b_end,b_angle)=state(wrap-1e-6)
   (a_start,a_angle),(b_start,_)=state(wrap)
   self.assertLess(a_end,1e-3)
   self.assertLess(b_start,1e-3)
   self.assertAlmostEqual(b_end,1,delta=1e-3)
   self.assertAlmostEqual(a_start,1,delta=1e-3)
   self.assertLess(abs((b_angle-a_angle+180)%360-180),.01)
   # normal blending: where both copies are opaque the incoming one on top keeps the core bright
   times=[i/10 for i in range(scene.PERIOD*10)]
   for t in times:
    (a,_),(b,_)=state(t)
    self.assertGreaterEqual(b+(1-b)*a,.93,(group.attrib['data-spin'],t))
   dissolving.append({t for t in times if .01<state(t)[1][0]<.99})
  self.assertFalse(dissolving[0]&dissolving[1],'the two galaxies should not dissolve at the same moment')

 def test_twinkling_stars_are_painted_stars_in_open_sky(self):
  stars=scene.bright_stars()
  self.assertEqual(len(stars),scene.TWINKLE_COUNT)
  self.assertEqual(sum(1 for star in stars if star[2]),scene.TWINKLE_BIG)
  for x,y,*_ in stars:
   self.assertFalse(scene.quiet(x,y,10),(x,y))
   self.assertFalse(overlap((x-15,y-15,x+15,y+15),scene.TEXT_RECT),(x,y))
  for plan in scene.twinkle_plan():
   for track in plan[-2:]:
    self.assertEqual(scene.PERIOD%track.dur,0)
    self.assertEqual(track.values[0],track.values[-1])
  # the stars actually twinkle: some are dimmed and some flare at any moment of the loop
  for t in (0,5.3,11.7,19.1):
   self.assertGreater(sum(1 for p in scene.twinkle_plan() if p[-2].at(t)>.3),10,t)
   self.assertGreater(sum(1 for p in scene.twinkle_plan() if p[-1].at(t)>.3),10,t)

 def test_shooting_stars_stay_in_open_sky_and_reset_while_invisible(self):
  plan=scene.meteor_plan()
  self.assertEqual(len(plan),scene.METEOR_COUNT)
  self.assertEqual(sum(1 for m in plan if m[-1]),1)  # one big, bright one
  for start,duration,x0,y0,dx,dy,tail,bright in plan:
   self.assertLess(start+duration+.05,scene.PERIOD)
   fade,move=scene.meteor_tracks(start,duration,x0,y0,dx,dy)
   length=math.hypot(dx,dy)
   for t in SAMPLES+[start+i*duration/50 for i in range(51)]:
    if fade.at(t)<=VISIBLE:
     continue
    x,y=move.at(t)
    tail_end=(x-dx/length*tail,y-dy/length*tail)
    for px,py in ((x,y),tail_end):
     self.assertFalse(scene.quiet(px,py),(t,px,py))
     self.assertTrue(0<px<scene.W and py<560,(t,px,py))
   # it snaps back to its start only after it has faded out
   self.assertLessEqual(fade.at(start+duration+.025),VISIBLE)
  starts=sorted(m[0] for m in plan)
  self.assertLessEqual(max(b-a for a,b in zip(starts,starts[1:]+[starts[0]+scene.PERIOD])),6)

 def test_satellite_crosses_once_and_returns_while_invisible(self):
  fade,move=scene.satellite_tracks()
  previous=None
  for t in SAMPLES:
   x,y=move.at(t)
   if fade.at(t)>VISIBLE:
    self.assertTrue(y<120 and not overlap((x-4,y-4,x+4,y+4),scene.TEXT_RECT),(t,x,y))
    if previous is not None:
     self.assertGreater(x,previous)
    previous=x
  for t in (23.9,23.95,0):
   self.assertLessEqual(fade.at(t),VISIBLE)

 def test_every_new_animated_group_is_covered_by_the_generic_raster_comparison(self):
  moving=animated_root()
  def count(predicate):
   return sum(1 for g in moving.iter(SVG+'g') if predicate(g) for n in g.iter() if n.tag in ANIMATIONS)
  self.assertGreaterEqual(count(lambda g:'data-lock' in g.attrib),14)
  self.assertGreaterEqual(count(lambda g:'data-warp' in g.attrib),12)
  self.assertGreaterEqual(count(lambda g:'data-lights' in g.attrib),3)
  self.assertGreaterEqual(count(lambda g:'data-spin' in g.attrib),8)
  self.assertGreaterEqual(count(lambda g:g.attrib.get('data-sky')=='twinkles'),2*scene.TWINKLE_COUNT)
  self.assertGreaterEqual(count(lambda g:g.attrib.get('data-sky')=='meteors'),2*scene.METEOR_COUNT)
  self.assertGreaterEqual(count(lambda g:g.attrib.get('data-sky')=='satellite'),2)
  # the generic test flattens every animated attribute; make sure the new ones are among those it evaluates
  kinds={(n.tag.replace(SVG,''),n.attrib['attributeName'],n.attrib.get('type')) for n in moving.iter() if n.tag in ANIMATIONS}
  for needed in (('animateTransform','transform','scale'),('animate','x2',None),('animate','y2',None),('animate','x1',None),('animate','y1',None)):
   self.assertIn(needed,kinds)


if __name__=='__main__':
 unittest.main()
