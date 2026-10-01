#!/usr/bin/env python3
"""Build the observatory SVG and render a portable GIF with FFmpeg/librsvg.

The background and transparent sprites are authored with image generation.
This script composes those layers and defines their animation timelines.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import math
from pathlib import Path
import random
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
W, H, PERIOD = 1672, 941, 24
RECTS = {
    'galaxy': ((0, 45, 510, 545), (300, 328)),
    'planet': ((512, 190, 522, 315), (784, 346)),
    'explorer': ((1035, 245, 500, 220), (1278, 346)),
    'fighter': ((64, 680, 448, 280), (288, 821)),
    'airplane': ((520, 700, 515, 205), (784, 815)),
    'moon': ((1170, 655, 300, 290), (1298, 805)),
}


def png_uri(name):
    return 'data:image/png;base64,' + base64.b64encode((ASSETS / name).read_bytes()).decode()


BACKGROUND = png_uri('observatory-background.png')
ATLAS = png_uri('space-sprites.png')


def sprite(name, width):
    (x, y, sw, sh), (ox, oy) = RECTS[name]
    scale = width / sw
    return (f'<svg x="{-(ox-x)*scale:.3f}" y="{-(oy-y)*scale:.3f}" '
            f'width="{width}" height="{sh*scale:.3f}" viewBox="{x} {y} {sw} {sh}" '
            f'overflow="hidden"><use href="#atlas" xlink:href="#atlas"/></svg>')


def rotate_node(name, width, x, y, angle, animated, seconds=24):
    motion = (f'<animateTransform attributeName="transform" type="rotate" '
              f'from="{angle}" to="{angle+360}" dur="{seconds}s" repeatCount="indefinite"/>' if animated else '')
    return f'<g transform="translate({x:.3f} {y:.3f})"><g transform="rotate({angle:.3f})">{motion}{sprite(name,width)}</g></g>'


def opacity_motion(duration=3, low=.35, high=1):
    return f'<animate attributeName="opacity" values="{low};{high};{low}" dur="{duration}s" repeatCount="indefinite"/>'


def celestial(t, animated):
    a = 2*math.pi*t/PERIOD
    parts = [rotate_node('galaxy', 390, 810, 184, t*360/PERIOD, animated),
             rotate_node('galaxy', 137, 1128, 228, -t*360/12, animated, seconds=12)]
    # Secondary galaxy counter-rotates with an independent 12-second loop.
    if animated:
        parts[1] = (f'<g transform="translate(1128 228)"><g><animateTransform attributeName="transform" '
                    f'type="rotate" from="0" to="-360" dur="12s" repeatCount="indefinite"/>{sprite("galaxy",137)}</g></g>')
    orbit = '<ellipse cx="1480" cy="162" rx="150" ry="66" fill="none" stroke="#71d6ef" stroke-width="1.4" stroke-dasharray="3 10" opacity=".4"/>'
    parts.append(orbit)
    px, py = 1480, 163+3*math.sin(a)
    planet_motion = ('<animateTransform attributeName="transform" type="translate" values="1480 163;1480 160;1480 163;1480 166;1480 163" dur="24s" repeatCount="indefinite"/>' if animated else '')
    parts.append(f'<g transform="translate({px} {py:.3f})">{planet_motion}{sprite("planet",305)}</g>')
    for phase, size, period in [(0,39,12),(math.pi,28,24)]:
        theta = 2*math.pi*t/period+phase
        mx, my = 1480+150*math.cos(theta), 162+66*math.sin(theta)
        if animated:
            # Circular parameter is projected to an ellipse by scaling its parent.
            parts.append(f'<g transform="translate(1480 162) scale(1 .44)"><g transform="rotate({math.degrees(phase):.3f})">'
                         f'<animateTransform attributeName="transform" type="rotate" from="{math.degrees(phase):.3f}" to="{math.degrees(phase)+360:.3f}" dur="{period}s" repeatCount="indefinite"/>'
                         f'<g transform="translate(150 0)"><g transform="rotate({-math.degrees(phase):.3f})">'
                         f'<animateTransform attributeName="transform" type="rotate" from="{-math.degrees(phase):.3f}" to="{-math.degrees(phase)-360:.3f}" dur="{period}s" repeatCount="indefinite"/>'
                         f'<g transform="scale(1 {1/.44:.5f})">{sprite("moon",size)}</g></g></g></g></g>')
        else:
            parts.append(f'<g transform="translate({mx:.3f} {my:.3f})">{sprite("moon",size)}</g>')
    return ''.join(parts)


def traffic(t, animated):
    parts = []
    routes = [('explorer',295,385,1900,490,24,.31),
              ('fighter',133,438,1840,-170,12,.15),
              ('fighter',103,475,1840,-170,12,.20),
              ('airplane',142,524,-200,1830,24,.23)]
    for name,width,y,start,end,period,phase in routes:
        u = (t/period+phase)%1
        x = start+(end-start)*u
        motion = (f'<animateTransform attributeName="transform" type="translate" from="{start} {y}" to="{end} {y}" '
                  f'dur="{period}s" begin="{-phase*period:.4f}s" repeatCount="indefinite"/>' if animated else '')
        clip = ' clip-path="url(#fleet-zone)"' if name=='explorer' else ''
        parts.append(f'<g{clip}><g transform="translate({x:.3f} {y})">{motion}')
        # Exhaust is part of the moving object, rather than a fixed streak.
        if name=='explorer':
            parts.append('<path d="M115 -17H208M115 7H192" stroke="#50d8f5" stroke-width="3" opacity=".65"/>')
        elif name=='fighter':
            parts.append('<path d="M44 -9H117M44 9H104" stroke="#ed78fc" stroke-width="2" opacity=".55"/>')
        else:
            parts.append('<path d="M-57 1H-174" stroke="#dbf3fa" stroke-width="2" stroke-dasharray="14 7" opacity=".4"/>')
        parts.append(sprite(name,width)+'</g></g>')
    return ''.join(parts)


def cube_points(theta):
    points=[]
    for x,y,z in [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]:
        rx=x*math.cos(theta)+z*math.sin(theta)
        rz=-x*math.sin(theta)+z*math.cos(theta)
        points.append((1435+rx*18,697+y*18-rz*6))
    return points


def workshop(t, animated):
    parts=[]
    edges=[(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)]
    poses=[cube_points(i*2*math.pi/24) for i in range(25)]
    current=cube_points(t*2*math.pi/6)
    for i,j in edges:
        p,q=current[i],current[j]
        anim=''
        if animated:
            for attribute,k,axis in [('x1',i,0),('y1',i,1),('x2',j,0),('y2',j,1)]:
                values=';'.join(f'{pose[k][axis]:.2f}' for pose in poses)
                anim+=f'<animate attributeName="{attribute}" values="{values}" dur="6s" repeatCount="indefinite"/>'
        parts.append(f'<line x1="{p[0]:.2f}" y1="{p[1]:.2f}" x2="{q[0]:.2f}" y2="{q[1]:.2f}" stroke="#72f0ff" stroke-width="1.8" opacity=".9">{anim}</line>')
    nozzle=1335+20*math.sin(t*2*math.pi/3)
    motion='<animate attributeName="x" values="1315;1355;1315" dur="3s" repeatCount="indefinite"/>' if animated else ''
    parts.append(f'<rect x="{nozzle:.3f}" y="727" width="9" height="5" fill="#71edff">{motion}</rect>')
    scan=749+18*math.sin(t*2*math.pi/6)
    motion='<animate attributeName="y" values="731;767;731" dur="6s" repeatCount="indefinite"/>' if animated else ''
    parts.append(f'<rect x="1318" y="{scan:.3f}" width="39" height="1.6" fill="#83eaff" opacity=".55">{motion}</rect>')
    for x,y,c,phase in [(1596,775,'#fa6cec',0),(1380,733,'#48dffc',.4),(1196,816,'#66eeeb',.7),(1505,591,'#e760e7',.2)]:
        alpha=.35+.65*(.5+.5*math.sin(t*2*math.pi/3+phase))
        parts.append(f'<rect x="{x}" y="{y}" width="4" height="3" fill="{c}" opacity="{alpha:.3f}">{opacity_motion() if animated else ""}</rect>')
    return ''.join(parts)


def sky_details(t, animated):
    rng=random.Random(29)
    parts=[]
    for i in range(32):
        x,y=rng.randint(20,1650),rng.randint(18,500)
        if 30<x<565 and 218<y<375:
            continue
        period=rng.choice([3,4,6,8])
        phase=rng.random()
        alpha=.2+.8*(.5+.5*math.sin(2*math.pi*(t/period+phase)))
        motion=(f'<animate attributeName="opacity" values=".2;1;.2" dur="{period}s" begin="{-phase*period:.3f}s" repeatCount="indefinite"/>' if animated else '')
        parts.append(f'<path d="M{x-3} {y}h6M{x} {y-3}v6" stroke="#a7deff" stroke-width="1.4" opacity="{alpha:.3f}">{motion}</path>')
    parts.append('<path d="M811 551L1020 97L1460 133" fill="none" stroke="#40daed" stroke-width="1.6" stroke-dasharray="6 11" opacity=".38"/>')
    parts.append(f'<g opacity="{.5+.3*math.sin(2*math.pi*t/3):.3f}"><path d="M996 94V72H1013M1028 72H1045V94M1045 104V121H1028M1013 121H996V104" fill="none" stroke="#4ae8f2" stroke-width="2">'
                 f'{opacity_motion(3,.3,.8) if animated else ""}</path></g>')
    u=(t/12)%1
    mx,my=1100+390*u,380+150*u
    alpha=math.sin(math.pi*u/.16)**2 if u<.16 else 0
    move=('<animateTransform attributeName="transform" type="translate" from="1100 380" to="1490 530" dur="12s" repeatCount="indefinite"/>' if animated else '')
    fade=('<animate attributeName="opacity" values="0;1;0;0" keyTimes="0;.08;.16;1" dur="12s" repeatCount="indefinite"/>' if animated else '')
    parts.append(f'<g transform="translate({mx:.3f} {my:.3f})" opacity="{alpha:.3f}">{move}{fade}<path d="M-58 -23L0 0" stroke="#88e4fc" stroke-width="2"/><rect x="-2" y="-2" width="4" height="4" fill="#ebfdff"/></g>')
    return ''.join(parts)


def layers(t, animated):
    return celestial(t,animated)+traffic(t,animated)+sky_details(t,animated)+workshop(t,animated)


def scene(t=0, animated=False, embedded=True):
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
           '<title id="title">Kush Modi — building toward the unexplored</title>',
           '<desc id="desc">Pixel observatory based on Kush\'s telescope photograph. Rotating galaxies, planetary moons, exploration spacecraft, an airplane and a working maker workshop.</desc>',
           '<defs><clipPath id="fleet-zone"><rect x="574" y="0" width="1098" height="510"/></clipPath>',
           f'<image id="atlas" width="1536" height="1024" href="{ATLAS}" xlink:href="{ATLAS}"/></defs>',
           f'<image width="{W}" height="{H}" href="{BACKGROUND}" xlink:href="{BACKGROUND}"/>']
    if animated:
        parts.append('<style>.still{display:none}@media(prefers-reduced-motion:reduce){.moving{display:none}.still{display:inline}}</style>')
        parts.append('<g class="moving">'+layers(t,True)+'</g><g class="still">'+layers(0,False)+'</g>')
    else:
        parts.append(layers(t,False))
    parts.append('</svg>')
    # SVG2 href and xlink fallback need only one copy of raster data.
    result=''.join(parts)
    result=result.replace(f' href="{ATLAS}"','').replace(f' href="{BACKGROUND}"','')
    return result


def rasterize(svg_path,png_path,width=1000):
    subprocess.run(['ffmpeg','-v','error','-threads','1','-width',str(width),'-i',str(svg_path),
                    '-frames:v','1','-threads','1','-y',str(png_path)],check=True)


def export_gif(fps,width):
    with tempfile.TemporaryDirectory(prefix='observatory-frames-',dir=ROOT) as directory:
        temp=Path(directory)
        def render(i):
            svg=temp/f'frame-{i:04d}.svg'
            png=temp/f'frame-{i:04d}.png'
            svg.write_text(scene(i/fps,False))
            rasterize(svg,png,width)
            svg.unlink()
            return i
        count=PERIOD*fps
        with ThreadPoolExecutor(max_workers=4) as pool:
            for i in pool.map(render,range(count)):
                if i%fps==0:
                    print(f'Rendered {i}/{count} frames',flush=True)
        # A single fixed palette avoids flickering colors across this pixel scene.
        subprocess.run(['ffmpeg','-v','error','-framerate',str(fps),'-i',str(temp/'frame-%04d.png'),
                        '-vf','palettegen=max_colors=256:stats_mode=full','-frames:v','1','-threads','1','-y',str(temp/'palette.png')],check=True)
        subprocess.run(['ffmpeg','-v','error','-framerate',str(fps),'-i',str(temp/'frame-%04d.png'),
                        '-i',str(temp/'palette.png'),'-lavfi','paletteuse=dither=bayer:bayer_scale=3',
                        '-loop','0','-threads','1','-y',str(ASSETS/'observatory.gif')],check=True)
        shutil.copyfile(temp/'frame-0000.png',ASSETS/'observatory-poster.png')
    print(f'GIF exported: {(ASSETS/"observatory.gif").stat().st_size:,} bytes',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gif',action='store_true')
    parser.add_argument('--fps',type=int,default=10)
    parser.add_argument('--width',type=int,default=1000)
    args=parser.parse_args()
    (ASSETS/'observatory.svg').write_text(scene(animated=True))
    (ASSETS/'poster.svg').write_text(scene(0,False))
    rasterize(ASSETS/'poster.svg',ASSETS/'observatory-poster.png',args.width)
    print('Animated SVG and poster exported',flush=True)
    if args.gif:
        export_gif(args.fps,args.width)


if __name__=='__main__':
    main()
