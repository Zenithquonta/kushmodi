import math
import unittest
import xml.etree.ElementTree as ET
import build_animation as scene

SVG='{http://www.w3.org/2000/svg}'


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


if __name__=='__main__':
 unittest.main()
