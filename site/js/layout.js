// The plan of the outpost, as plain data (no three.js, so tests can import it). Metres. -Z is north, +X is east.
//
//                       OBSERVATORY            (0, -48)
//                            |
//                       RESEARCH LAB           (0, -26)
//                            |
//   ROBOTICS FIELD --- ENGINEERING WORKSHOP --- UAV / NETRA FIELD
//     (-36, 4)              (0, 2)                  (36, 4)
//                            |
//                       START / PROFILE CAMP   (0, 28)
//
// The original M1 hill stays the foundation: its crown (flat, radius 56 m) holds all six places. The M1 telescope,
// shed, rover, van and drone pad are re-used as the observatory's telescope, the workshop, the robotics field's rover
// and field vehicle, and the UAV field's landing pad.
export const HILL_TOP = 9;            // height of the flat crown
export const CROWN_RADIUS = 56;
export const WALK_RADIUS = 70;        // soft boundary (fence)
export const FAR = 2600;

export const LOCATIONS = [
  { id: 'profile', name: 'Start camp', x: 0, z: 28, r: 8, ground: '#7d6a48' },
  { id: 'workshop', name: 'Engineering workshop', x: 0, z: 2, r: 11, ground: '#7a6f58' },
  { id: 'robotics', name: 'Robotics field', x: -36, z: 4, r: 14, ground: '#8a7048' },
  { id: 'uav', name: 'UAV / NETRA test field', x: 36, z: 4, r: 15, ground: '#8f8a60' },
  { id: 'research', name: 'Research lab', x: 0, z: -26, r: 9, ground: '#6e6a58' },
  { id: 'observatory', name: 'Observatory', x: 0, z: -48, r: 12, ground: '#6a6e70' },
];
export const CENTRE = { id: 'hub', name: 'Crossroads', x: 0, z: 17, r: 4 };
export const SPAWN = { x: 0, z: 40 };

const byId = Object.fromEntries(LOCATIONS.map((l) => [l.id, l]));
export const place = (id) => byId[id];

// The spine runs south to north (Start, Workshop, Research, Observatory); the east-west branch reaches Robotics and UAV.
const SPINE = [
  [0, 44], [0, 36], [0, 28], [0, 21], [0, 17], [7, 13], [9, 5], [8, -5], [8, -15], [8, -23], [7, -31], [3, -38], [0, -42],
];
const WEST = [[0, 17], [-8, 15], [-17, 11], [-25, 7], [-30, 5]];
const EAST = [[7, 13], [16, 12], [25, 9], [31, 6]];

// Catmull-Rom through the control points, sampled about every metre
function spline(nodes, step = 1) {
  const out = [];
  const at = (i) => nodes[Math.max(0, Math.min(nodes.length - 1, i))];
  for (let i = 0; i < nodes.length - 1; i++) {
    const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
    const len = Math.hypot(p2[0] - p1[0], p2[1] - p1[1]);
    const n = Math.max(2, Math.round(len / step));
    for (let k = 0; k < n; k++) {
      const t = k / n, t2 = t * t, t3 = t2 * t;
      const f = (a, b, c, d) => 0.5 * ((2 * b) + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
      out.push([f(p0[0], p1[0], p2[0], p3[0]), f(p0[1], p1[1], p2[1], p3[1])]);
    }
  }
  out.push(nodes[nodes.length - 1].slice());
  return out;
}

export const MAIN_PATH = spline(SPINE);
export const WEST_PATH = spline(WEST);
export const EAST_PATH = spline(EAST);

// the dirt test loop on the robotics field (an oval)
export const ROBOTICS_LOOP = (() => {
  const { x, z } = byId.robotics;
  const out = [];
  for (let i = 0; i <= 48; i++) {
    const a = (i / 48) * Math.PI * 2;
    out.push([x - 1 + Math.cos(a) * 9.5, z - 0.6 + Math.sin(a) * 6.2]);
  }
  return out;
})();

// short spurs from the paths to the doors of the places
export const SPURS = [
  [[0, 21], [0, 24]],
  [[0, -42], [0, -40]],
  [[-30, 5], [-32.5, 4]],
  [[31, 6], [33, 5.5]],
];

export const PATHS = [MAIN_PATH, WEST_PATH, EAST_PATH, ROBOTICS_LOOP, ...SPURS];

const smooth = (a, b, x) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};

// distance to the nearest path sample (the three paths and the loop)
export function pathDistance(x, z) {
  let best = Infinity;
  for (const poly of [MAIN_PATH, WEST_PATH, EAST_PATH, ROBOTICS_LOOP]) {
    for (let i = 0; i < poly.length; i++) {
      const d = Math.hypot(x - poly[i][0], z - poly[i][1]);
      if (d < best) best = d;
    }
  }
  return best;
}

// 1 on the middle of a place, 0 outside: used to level the ground and keep the scatter away
export function siteMask(x, z, inner = 0.75, outer = 1.2) {
  let m = 0;
  for (const l of [...LOCATIONS, CENTRE]) m = Math.max(m, 1 - smooth(l.r * inner, l.r * outer, Math.hypot(x - l.x, z - l.z)));
  return m;
}

// which place (if any) the point is in; the nearest within its radius
export function locationAt(x, z) {
  let best = null, bd = Infinity;
  for (const l of LOCATIONS) {
    const d = Math.hypot(x - l.x, z - l.z);
    if (d < l.r && d / l.r < bd) { bd = d / l.r; best = l; }
  }
  return best;
}

export const orderedIds = LOCATIONS.map((l) => l.id);
