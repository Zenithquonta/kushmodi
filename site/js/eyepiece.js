// Deliberately pixel-art illustrations, never presented as live telescope photography.
export function drawEyepiece(canvas, target) {
  const ctx=canvas.getContext('2d'), size=192, center=96;
  canvas.width=canvas.height=size; ctx.imageSmoothingEnabled=false;
  ctx.fillStyle='#02050d';ctx.fillRect(0,0,size,size);
  if(target.altitude <= 0 || target.daylight) return;
  let seed=37;
  for(const c of target.name) seed=(seed*31+c.charCodeAt(0))>>>0;
  const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  for(let i=0;i<45;i++) {
    const x=10+random()*172,y=10+random()*172;
    if(Math.hypot(x-center,y-center)<58)continue;
    ctx.fillStyle=i%3?'#28364b':'#62768b';ctx.fillRect(Math.floor(x),Math.floor(y),1,1);
  }
  if(target.kind==='star') {
    for(let radius=13;radius>0;radius--) {
      ctx.fillStyle=`rgba(137,202,255,${.02+(.12*(1-radius/13))})`;
      ctx.fillRect(center-radius,center-radius,radius*2,radius*2);
    }
    ctx.fillStyle='#739fd0';ctx.fillRect(65,95,62,2);ctx.fillRect(95,65,2,62);
    ctx.fillStyle='#c2ddf4';ctx.fillRect(88,93,16,6);ctx.fillRect(93,88,6,16);
    ctx.fillStyle='#fff6d6';ctx.fillRect(93,93,6,6);return;
  }
  const palettes={Mercury:[157,145,130],Venus:[216,196,143],Mars:[200,100,61],Jupiter:[199,170,133],Saturn:[204,185,133],Uranus:[118,198,205],Neptune:[68,110,205],Moon:[173,180,185]};
  const base=palettes[target.name]||[170,180,190];
  const radius=target.name==='Saturn'?33:target.name==='Moon'?60:47;
  const ring=(front)=>{
    for(let y=-26;y<=26;y++)for(let x=-79;x<=79;x++) {
      const yy=y+x*.22, rr=Math.hypot(x,yy*3.4);
      if(rr<48||rr>79||(front?yy<0:yy>=0))continue;
      const tone=(rr>65&&rr<69)?.27:.68+Math.sin(rr*2)*.1;
      ctx.fillStyle=`rgb(${Math.floor(217*tone)},${Math.floor(194*tone)},${Math.floor(151*tone)})`;ctx.fillRect(center+x,center+y,1,1);
    }
  };
  if(target.name==='Saturn')ring(false);
  const fraction=target.illuminated??1;
  const phase=Math.acos(Math.min(1,Math.max(-1,2*fraction-1)));
  for(let y=-radius;y<=radius;y++)for(let x=-radius;x<=radius;x++) {
    const nx=x/radius,ny=y/radius,nz2=1-nx*nx-ny*ny;if(nz2<0)continue;
    const nz=Math.sqrt(nz2);
    const phaseDirection=target.name==='Moon'&&target.phaseAngle>180?-1:1;
    const lit=Math.max(0,nx*Math.sin(phase)*phaseDirection+nz*Math.cos(phase));
    let detail=(random()-.5)*.12;
    if(['Jupiter','Saturn'].includes(target.name))detail+=Math.sin(y*.29+Math.sin(x*.1)*.5)*.12+Math.sin(y*.63)*.05;
    if(['Moon','Mercury','Mars'].includes(target.name))detail+=Math.sin(x*.29)*Math.cos(y*.34)*.12;
    let shade=.12+.84*Math.sqrt(lit)+detail; shade=Math.max(.04,Math.min(1.1,shade));
    ctx.fillStyle=`rgb(${base.map(c=>Math.min(255,Math.floor(c*shade))).join(',')})`;ctx.fillRect(center+x,center+y,1,1);
  }
  if(target.name==='Jupiter') {ctx.fillStyle='#ad7153';ctx.fillRect(108,108,13,5);ctx.fillRect(111,106,8,9);}
  if(target.name==='Saturn')ring(true);
}
