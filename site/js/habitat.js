// A compact, layered hillside outpost, composed from the approved observatory artwork.
import * as THREE from '../vendor/three/three.module.js';
import { Bag } from './geom.js';
import { groundHeight } from './terrain.js';

export function buildHabitat(root, world, pos) {
  let seed = 829;
  const r = () => { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed / 4294967296; };
  const rocks = new Bag(), gravel = new Bag(), timber = new Bag();
  const clear = (x, z, margin = 0) => {
    // Keep the observing terrace, van, drone pad and workshop approach navigable.
    if (Object.values(pos).some(([a, b]) => Math.hypot(x - a, z - b) < 3.3 + margin)) return true;
    if (x > 4 && x < 14 && z > -6 && z < 5) return true;
    if (z > -2 && z < 12 && Math.abs(x + (10 - z) * .23) < 1.5 + margin) return true;
    if (z > 1 && z < 12 && Math.abs(x - (10 - z) * .6) < 1.8 + margin) return true;
    return false;
  };

  // Rock outcrops form a foreground and frame the observing terrace.
  const outcrops = [[-5.5,-5,2.8,1.7],[-8,-3,2.1,1.3],[-7,3,1.4,.7],[3,-6,2.5,1.3],[-14,-8,3,1.9],[16,-8,3.5,2],[-11,12,2.3,1.3],[10,13,2.1,1.1]];
  for (const [x,z,w,h] of outcrops) {
    rocks.add(Bag.cache('ico',1,2),x,groundHeight(x,z)+h*.38,z,.18,r()*6,.1,'#344952',w,h,w*.62);
    world.colliders.push({type:'circle',x,z,r:w*.74});
    for (let i=0;i<7;i++) {
      const a=r()*6.28,d=w*(.5+r()*.65),xx=x+Math.cos(a)*d,zz=z+Math.sin(a)*d;
      rocks.add(Bag.cache('ico',1,1),xx,groundHeight(xx,zz)+.1,zz,0,r()*6,0,i%2?'#3d5159':'#536263',.2+r()*.35,.15+r()*.25,.2+r()*.3);
    }
  }
  // Small stones break up the dirt clearing; these remain below foot height.
  for(let i=0;i<1100;i++) {
    const x=(r()-.5)*34,z=(r()-.5)*28;
    if (x>5 && x<13 && z>-5 && z<3) continue;
    const s=.025+r()*.1;
    gravel.add(Bag.cache('ico',1,0),x,groundHeight(x,z)+s*.1,z,0,r()*6,0,['#48545a','#72716b','#94816d'][i%3],s,s*.4,s*.7);
  }
  root.add(rocks.mesh(),gravel.mesh());

  // Cutout leaves supply detailed silhouettes, with crossed planes giving depth as visitors walk.
  const texture=new THREE.TextureLoader().load('data/foliage-atlas.webp');
  texture.colorSpace=THREE.SRGBColorSpace; texture.anisotropy=4;
  const matrix=new THREE.Matrix4(), q=new THREE.Quaternion(), e=new THREE.Euler(), v=new THREE.Vector3(), scale=new THREE.Vector3();
  for(let variant=0;variant<4;variant++) {
    const geometry=new THREE.PlaneGeometry(1,1); geometry.translate(0,.5,0);
    const uv=geometry.attributes.uv;
    const col=variant%2,row=Math.floor(variant/2);
    for(let j=0;j<uv.count;j++) uv.setXY(j,col*.5+.008+uv.getX(j)*.484,(1-row)*.5+.008+uv.getY(j)*.484);
    // Preserve the painted leaf detail at night instead of emitting a flat blue silhouette.
    const material=new THREE.MeshStandardMaterial({map:texture,alphaTest:.28,side:THREE.DoubleSide,roughness:1,metalness:0,emissiveMap:texture,emissive:0xffffff,emissiveIntensity:.38});
    const spots=[
      [-6.5,5,1.8,0], [-7.8,3,2.1,.7], [-9,8,2.4,1.4],
      [3.3,6,1.15,.4], [6.7,7.6,1.8,1.8], [12,7,2.1,0],
      [-6,-7,1.3,.3], [1,-7,1.1,1], [-14,-3,2.1,.6],
      [-4.6,8,1.4,.2], [-5.7,9.5,2.2,.1], [-3.6,6.5,.95,.4],
      [4.8,9,1.75,.3], [4.1,7.4,1.1,1], [6,10,2.3,.2],
      [-8.8,1.5,2.2,.3], [-10.8,-1,2.6,.4], [14,1,2.9,.2],
    ].filter((_,i)=>i%4===variant);
    // Close groups spill from the rock beds onto the clearing, framing the opening
    // viewpoint while leaving continuous routes to the telescope and workshop.
    for(const [cx,cz] of [[-5.5,7.5],[4.8,8],[-8,2],[3.8,-5],[14,3]]) {
      for(let i=0;i<14;i++) {
        const x=cx+(r()-.5)*3,z=cz+(r()-.5)*3;
        if(clear(x,z,-1.15))continue;
        spots.push([x,z,.35+r()*.65,r()*6.28]);
      }
    }
    for(let i=0;i<140;i++) {
      const x=(r()-.5)*76,z=(r()-.5)*68;
      if(clear(x,z,.2)) continue;
      const close=Math.hypot(x,z)<22;
      const h=close ? .6+r()*1.35 : 1.7+r()*3;
      spots.push([x,z,h,r()*6.28]);
    }
    const mesh=new THREE.InstancedMesh(geometry,material,spots.length*2);
    let index=0;
    for(const [x,z,h,a] of spots) for(let cross=0;cross<2;cross++) {
      e.set(0,a+cross*Math.PI/2,0);q.setFromEuler(e);v.set(x,groundHeight(x,z)-.05,z);scale.set(h*1.25,h,1);
      matrix.compose(v,q,scale);mesh.setMatrixAt(index++,matrix);
    }
    mesh.name='illustrated-foliage';root.add(mesh);
  }

  // Layered distant ridges sit behind the valley lights, never across the walking space.
  for(let layer=0;layer<3;layer++) {
    const vertices=[],indices=[];
    for(let i=0;i<=100;i++) {
      const x=(i-50)*34,z=-1200-layer*260;
      const peak=32+layer*16+Math.abs(Math.sin(i*.31+layer))*38+Math.sin(i*.77)*12;
      vertices.push(x,-15,z,x,peak,z);
      if(i<100) {const j=i*2;indices.push(j,j+1,j+2,j+1,j+3,j+2);}
    }
    const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setIndex(indices);g.computeVertexNormals();
    const mesh=new THREE.Mesh(g,new THREE.MeshLambertMaterial({color:[0x213d4d,0x305367,0x436477][layer],side:THREE.DoubleSide}));root.add(mesh);
  }

  // A porch worktable and stacked equipment make the workshop read as a lived-in maker space.
  timber.box(3.2,.13,.85,'#926440',.6,.92,2.65);
  for(const x of [-.8,2]) for(const z of [2.3,3]) timber.box(.1,.85,.1,'#493728',x,.43,z);
  for(let i=0;i<8;i++) {
    timber.box(.22,.15,.18,['#c96a3d','#bdab55','#408b91'][i%3],-.5+i*.3,1.06,2.65);
    timber.cyl(.045,.045,.17,'#b8b7a6',-.5+i*.3,1.15,2.65,0,0,Math.PI/2,12);
  }
  for(let i=0;i<3;i++) {
    timber.box(.9,.55,.75,'#3e5557',-3.3,.3+i*.57,1.8);
    timber.box(.72,.07,.025,'#96a29a',-3.3,.3+i*.57,2.19);
  }
  world.shed.add(timber.mesh());
  // Additional warm spill and cyan rim keep the workbench legible from the entrance.
  const warm=new THREE.PointLight(0xffaa55,32,15,1.5);warm.position.set(.5,2.2,2.4);
  const cyan=new THREE.PointLight(0x37cbdc,14,10,1.7);cyan.position.set(3.7,2.8,1.8);
  world.shed.add(warm,cyan);
  world.colliders.push({type:'box',x:pos.shed[0],z:pos.shed[1],yaw:-Math.PI/4,lx:.6,lz:2.65,hw:1.6,hd:.45});

  const label=labelTexture('MAKER WORKSHOP','CAD  /  ROBOTICS  /  FABRICATION');
  const sign=new THREE.Mesh(new THREE.PlaneGeometry(3.7,.64),new THREE.MeshBasicMaterial({map:label}));
  sign.position.set(.3,2.9,2.64);world.shed.add(sign);
}

function labelTexture(title,subtitle) {
  const canvas=document.createElement('canvas');canvas.width=768;canvas.height=128;
  const c=canvas.getContext('2d');c.fillStyle='#10222b';c.fillRect(0,0,768,128);
  c.strokeStyle='#48939b';c.lineWidth=3;c.strokeRect(5,5,758,118);
  c.fillStyle='#c4e1d8';c.font='500 38px monospace';c.fillText(title,28,56);
  c.fillStyle='#d5aa71';c.font='20px monospace';c.fillText(subtitle,28,95);
  const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;return texture;
}
