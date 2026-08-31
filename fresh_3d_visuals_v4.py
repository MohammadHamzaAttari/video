#!/usr/bin/env python3
"""Distinct, all-motion 3D-style source tracks for Universe Impact v4.

Every requested track is rendered as its own video file with a separate seed,
visual family, camera path and particle state.  `render_unique_tracks()` is
intentionally strict: duplicate track keys are a build error, and byte-identical
outputs are detected before the edit is assembled.  This is the source-level
safeguard against the repeated-background issue found in v3.

The visuals are original conceptual renderings made with local geometry,
particles, grids and camera projection. They are not observational data or a
numerical GR simulation.
"""

from __future__ import annotations

import hashlib
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# Reuse only generic, local drawing utilities from the prior renderer. No v3
# rendered video or legacy source clip is read by this module.
from fresh_3d_visuals import (
    FPS,
    TAU,
    WORK_H,
    WORK_W,
    _add_glow,
    _background,
    _make_grids,
    _make_stars,
    _project,
    _rgba,
)


@dataclass(frozen=True)
class TrackSpec:
    key: str
    family: str
    seed: int
    hue: str
    duration: float
    label: str


FAMILY_DESCRIPTIONS: dict[str, str] = {
    "accretion": "inclined accretion-disk particle orbit",
    "lensfield": "lensed starfield around an event-horizon shadow",
    "binary": "two-horizon orbital gravity choreography",
    "lattice": "rotating three-dimensional conceptual lattice",
    "jet": "relativistic-jet style particle column",
    "funnel": "spiralling matter funnel",
    "bounce": "conceptual collapse-to-bounce particle field",
    "shell": "expanding shell and shock front",
    "spiral": "three-dimensional galaxy-arm flight",
    "web": "forward flight through connected cosmic-web nodes",
    "sphere": "rotating pattern sphere and scanning reticle",
    "metric": "warped metric-style grid",
    "wave": "outgoing gravitational-wave style ripples",
    "orbits": "layered orbital-plane sculpture",
    "data": "animated evidence / detector data sculpture",
    "void": "camera drift past a luminous horizon void",
    "outro": "branded living cosmic end-card background",
}


def _writer(path: Path, ffmpeg: str) -> subprocess.Popen[bytes]:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WORK_W}x{WORK_H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-profile:v",
        "high",
        "-level:v",
        "4.0",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(path),
    ]
    process: subprocess.Popen[bytes] = subprocess.Popen(command, stdin=subprocess.PIPE)
    if process.stdin is None:
        raise RuntimeError(f"Could not open raw-video writer for {path}")
    return process


def _finish(process: subprocess.Popen[bytes], name: str) -> None:
    assert process.stdin is not None
    process.stdin.close()
    status = process.wait()
    if status:
        raise RuntimeError(f"FFmpeg failed while rendering {name} (exit {status})")


def _finish_image(image: Image.Image) -> np.ndarray:
    """Keep a stable, compressible finish; intentional motion comes from geometry."""
    return np.uint8(np.clip(np.asarray(image.convert("RGB"), dtype=np.int16), 0, 255))


def _line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], colour: tuple[int, int, int, int], width: int = 1) -> None:
    if len(points) > 1:
        draw.line(points, fill=colour, width=width, joint="curve")


def _layers(frame: np.ndarray) -> tuple[Image.Image, Image.Image, Image.Image, ImageDraw.ImageDraw, ImageDraw.ImageDraw]:
    image = _rgba(frame)
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    crisp = Image.new("RGBA", image.size, (0, 0, 0, 0))
    return image, glow, crisp, ImageDraw.Draw(glow), ImageDraw.Draw(crisp)


def _merge(image: Image.Image, glow: Image.Image, crisp: Image.Image, blur: float = 3.0) -> Image.Image:
    if blur > 0:
        glow = glow.filter(ImageFilter.GaussianBlur(radius=blur))
    return Image.alpha_composite(Image.alpha_composite(image, glow), crisp)


def _palette(spec: TrackSpec) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    palettes = {
        "ember": ((255, 91, 40), (255, 193, 78), (154, 61, 255)),
        "cool": ((55, 211, 255), (83, 130, 255), (180, 89, 255)),
        "violet": ((204, 82, 255), (67, 224, 255), (255, 112, 83)),
        "signal": ((90, 245, 223), (255, 145, 62), (130, 112, 255)),
        "gold": ((255, 183, 62), (255, 91, 53), (78, 202, 255)),
    }
    return palettes.get(spec.hue, palettes["cool"])


def _build_context(spec: TrackSpec) -> dict[str, object]:
    rng = np.random.default_rng(spec.seed)
    count = 620
    p3 = rng.normal(0.0, 1.0, (count, 3)).astype(np.float32)
    p3 /= np.linalg.norm(p3, axis=1, keepdims=True)
    return {
        "spec": spec,
        "rng": rng,
        "xx": _make_grids()[0],
        "yy": _make_grids()[1],
        "stars": _make_stars(spec.seed + 17, 650),
        "angles": rng.uniform(0, TAU, count).astype(np.float32),
        "radii": (35 + 295 * np.sqrt(rng.random(count))).astype(np.float32),
        "lane": rng.uniform(0.15, 1.0, count).astype(np.float32),
        "height": rng.normal(0, 24, count).astype(np.float32),
        "p3": p3,
        "phase": float(rng.uniform(0, TAU)),
        "colours": _palette(spec),
    }


def _base(ctx: dict[str, object], t: float) -> tuple[np.ndarray, Image.Image, Image.Image, Image.Image, ImageDraw.ImageDraw, ImageDraw.ImageDraw]:
    spec = ctx["spec"]
    assert isinstance(spec, TrackSpec)
    xx = ctx["xx"]
    yy = ctx["yy"]
    stars = ctx["stars"]
    assert isinstance(xx, np.ndarray) and isinstance(yy, np.ndarray) and isinstance(stars, dict)
    frame = _background(t + float(ctx["phase"]) * 0.23, xx, yy, stars, spec.hue)
    image, glow, crisp, gdraw, draw = _layers(frame)
    return frame, image, glow, crisp, gdraw, draw


def _draw_accretion(ctx: dict[str, object], t: float) -> Image.Image:
    frame, image, glow, crisp, gdraw, draw = _base(ctx, t)
    xx, yy = ctx["xx"], ctx["yy"]
    assert isinstance(xx, np.ndarray) and isinstance(yy, np.ndarray)
    a, b, c = ctx["colours"]
    angles, radii, lane, height = (ctx[key] for key in ("angles", "radii", "lane", "height"))
    assert all(isinstance(value, np.ndarray) for value in (angles, radii, lane, height))
    phase = float(ctx["phase"])
    cx = WORK_W * (0.50 + 0.035 * math.sin(t * 0.67 + phase))
    cy = WORK_H * (0.53 + 0.028 * math.cos(t * 0.48 + phase))
    orbit = angles + t * (0.60 + 2.7 * (200 / radii) ** 0.48)
    x = radii * np.cos(orbit)
    z = radii * np.sin(orbit)
    y = height + 8 * np.sin(orbit * 2.3 + t)
    sx, sy, depth = _project(x, y, z, 0.68 * math.sin(t * 0.36 + phase), 0.55 + 0.17 * math.cos(t * 0.29 + phase), 780, 690, cx, cy)
    _add_glow(frame, xx, yy, cx, cy, 146, 76, tuple(float(v) / 12 for v in a), 1.3)
    order = np.argsort(depth)[::-1]
    for idx in order:
        if not (-8 < sx[idx] < WORK_W + 8 and -8 < sy[idx] < WORK_H + 8):
            continue
        mix = 0.5 + 0.5 * math.sin(float(orbit[idx]) + phase)
        colour = tuple(int(mix * a[ch] + (1 - mix) * b[ch]) for ch in range(3))
        size = 0.6 + 2.0 * float(lane[idx])
        px, py = float(sx[idx]), float(sy[idx])
        if lane[idx] > 0.78:
            gdraw.ellipse((px - size * 3.7, py - size * 3.7, px + size * 3.7, py + size * 3.7), fill=(*colour, 45))
        draw.ellipse((px - size, py - size, px + size, py + size), fill=(*colour, 178))
    # A moving, deliberately stylized photon-ring stack.
    for ring in range(6):
        rx = 78 + ring * 20
        ry = 18 + ring * 5
        offset = 7 * math.sin(t * 1.2 + ring)
        ring_colour = c if ring % 2 else a
        gdraw.ellipse((cx - rx, cy - ry + offset, cx + rx, cy + ry + offset), outline=(*ring_colour, 82), width=2)
    horizon = 74 + 7 * math.sin(t * 2.0 + phase)
    draw.ellipse((cx - horizon, cy - horizon * 0.88, cx + horizon, cy + horizon * 0.88), fill=(0, 0, 5, 252), outline=(*b, 150), width=2)
    return _merge(image, glow, crisp, 3.4)


def _draw_jet(ctx: dict[str, object], t: float) -> Image.Image:
    frame, image, glow, crisp, gdraw, draw = _base(ctx, t)
    xx, yy = ctx["xx"], ctx["yy"]
    assert isinstance(xx, np.ndarray) and isinstance(yy, np.ndarray)
    a, b, c = ctx["colours"]
    rng = ctx["rng"]
    assert isinstance(rng, np.random.Generator)
    phase = float(ctx["phase"])
    cx = WORK_W * (0.49 + .04 * math.sin(t * .41 + phase))
    cy = WORK_H * .55
    _add_glow(frame, xx, yy, cx, cy, 95, 95, tuple(v / 10 for v in b), 1.5)
    # The columns are reconstructed deterministically from the clip seed each
    # frame, so no texture or animation segment can be reused across tracks.
    count = 430
    heights = rng.uniform(-550, 550, count)
    ang = rng.uniform(0, TAU, count) + t * .42
    spread = (12 + np.abs(heights) * .11) * rng.random(count)
    px = cx + np.cos(ang) * spread + 10 * np.sin(t * 2.2 + heights * .04)
    py = cy - heights + 16 * np.cos(t * 1.2 + heights * .02)
    for x, y, h in zip(px, py, heights):
        if -5 < x < WORK_W + 5 and -5 < y < WORK_H + 5:
            colour = a if h > 0 else c
            size = 0.8 + (1 - min(1, abs(h) / 700)) * 2.0
            gdraw.ellipse((x - size * 3, y - size * 3, x + size * 3, y + size * 3), fill=(*colour, 42))
            draw.ellipse((x - size, y - size, x + size, y + size), fill=(*colour, 190))
    # Rotating disk provides an obviously different silhouette from accretion.
    for r in range(8):
        rx = 72 + r * 17
        ry = 12 + r * 3.3
        gdraw.ellipse((cx-rx, cy-ry, cx+rx, cy+ry), outline=(*b, 70), width=2)
    draw.ellipse((cx - 55, cy - 50, cx + 55, cy + 50), fill=(0, 0, 4, 250), outline=(*a, 170), width=2)
    return _merge(image, glow, crisp, 4.0)


def _draw_binary(ctx: dict[str, object], t: float) -> Image.Image:
    frame, image, glow, crisp, gdraw, draw = _base(ctx, t)
    a, b, c = ctx["colours"]
    phase = float(ctx["phase"])
    cx, cy = WORK_W * .5, WORK_H * .52
    separation = 118 + 30 * math.sin(t * .34 + phase)
    angle = t * 1.46 + phase
    positions = [
        (cx + separation * math.cos(angle), cy + separation * .48 * math.sin(angle)),
        (cx - separation * math.cos(angle), cy - separation * .48 * math.sin(angle)),
    ]
    # Tidal connector and two differently coloured mini disks.
    _line(gdraw, [positions[0], positions[1]], (*b, 110), 3)
    for number, (px, py) in enumerate(positions):
        primary = a if number == 0 else c
        secondary = b if number == 0 else a
        for ring in range(6):
            rr = 41 + ring * 13
            gdraw.ellipse((px - rr, py - rr * .36, px + rr, py + rr * .36), outline=(*primary, 82), width=2)
        gdraw.ellipse((px - 110, py - 60, px + 110, py + 60), fill=(*primary, 24))
        draw.ellipse((px - 38, py - 34, px + 38, py + 34), fill=(1, 1, 6, 250), outline=(*secondary, 180), width=2)
    # Gravitational-wave petal ripples travel out continuously.
    for ring in range(5):
        u = (t * .46 + ring / 5) % 1
        rx = 70 + 360 * u
        ry = rx * .48
        gdraw.ellipse((cx-rx, cy-ry, cx+rx, cy+ry), outline=(*b, int(100*(1-u)**1.7)), width=2)
    return _merge(image, glow, crisp, 3.0)


def _draw_funnel(ctx: dict[str, object], t: float) -> Image.Image:
    frame, image, glow, crisp, gdraw, draw = _base(ctx, t)
    a, b, c = ctx["colours"]
    angles, lane = ctx["angles"], ctx["lane"]
    assert isinstance(angles, np.ndarray) and isinstance(lane, np.ndarray)
    phase = float(ctx["phase"])
    cx, cy = WORK_W*.5, WORK_H*.51
    # A corkscrew tunnel makes depth legible without a black-hole disk look.
    depth = 90 + ((np.arange(len(angles)) * 47 + t * 420) % 1600)
    radius = 16 + 260 * (depth / 1600) ** .9
    theta = angles + t * 2.5 + depth * .006
    x = radius * np.cos(theta)
    y = radius * np.sin(theta) * .76
    scale = 950 / (depth + 260)
    sx = cx + x * scale
    sy = cy + y * scale
    for i in np.argsort(depth)[::-1]:
        if -5 < sx[i] < WORK_W+5 and -5 < sy[i] < WORK_H+5:
            colour = a if i % 3 else b if i % 3 == 1 else c
            size = .7 + 2.8 * (1-depth[i]/1700)
            if lane[i] > .75:
                gdraw.line((cx+(sx[i]-cx)*1.08, cy+(sy[i]-cy)*1.08, sx[i], sy[i]), fill=(*colour, 60), width=2)
            draw.ellipse((sx[i]-size, sy[i]-size, sx[i]+size, sy[i]+size), fill=(*colour, 180))
    for ring in range(12):
        z = 70 + ((ring*145 + t*230) % 1400)
        r = 285 * (z / 1400) ** .88 + 9
        alpha = int(105 * z/1400)
        gdraw.ellipse((cx-r, cy-r*.76, cx+r, cy+r*.76), outline=(*b, alpha), width=2)
    draw.ellipse((cx-20,cy-20,cx+20,cy+20),fill=(2,1,8,250),outline=(*c,150),width=2)
    return _merge(image, glow, crisp, 3.3)


def _draw_bounce(ctx: dict[str, object], t: float) -> Image.Image:
    frame, image, glow, crisp, gdraw, draw = _base(ctx, t)
    xx, yy = ctx["xx"], ctx["yy"]
    assert isinstance(xx, np.ndarray) and isinstance(yy, np.ndarray)
    a, b, c = ctx["colours"]
    p3, lane = ctx["p3"], ctx["lane"]
    assert isinstance(p3, np.ndarray) and isinstance(lane, np.ndarray)
    spec = ctx["spec"]
    assert isinstance(spec, TrackSpec)
    u = t / spec.duration
    cx, cy = WORK_W * .5, WORK_H * .50
    contraction = max(0, 1 - u / .45)
    expansion = max(0, (u-.33)/.67)
    if u < .44:
        rad = 410 * contraction**.54 + 25 + lane*30
    else:
        rad = 24 + (180 + 370*lane) * (1-(1-min(1,expansion))**3)
    x, y, z = p3[:,0]*rad, p3[:,1]*rad, p3[:,2]*rad
    sx, sy, depth = _project(x,y,z, .32*math.sin(t*.7), .35, 850, 650,cx,cy)
    flash = math.exp(-((u-.44)/.065)**2)
    _add_glow(frame,xx,yy,cx,cy,100+150*flash,100+150*flash,tuple(v/10 for v in b),1.4+1.3*flash)
    for i in np.argsort(depth)[::-1]:
        if -4<sx[i]<WORK_W+4 and -4<sy[i]<WORK_H+4:
            colour = a if u < .44 else b if i%2 else c
            size = .7 + 2.1*lane[i]
            dx,dy=sx[i]-cx,sy[i]-cy
            norm=max(1,math.hypot(float(dx),float(dy)))
            sign=-1 if u<.44 else 1
            gdraw.line((sx[i],sy[i],sx[i]-sign*dx/norm*(5+10*lane[i]),sy[i]-sign*dy/norm*(5+10*lane[i])),fill=(*colour,65),width=2)
            draw.ellipse((sx[i]-size,sy[i]-size,sx[i]+size,sy[i]+size),fill=(*colour,190))
    for ring in range(6):
        phase=(u*1.25+ring/6)%1
        rr=30+460*phase
        gdraw.ellipse((cx-rr,cy-rr*.62,cx+rr,cy+rr*.62),outline=(*b,int(135*(1-phase)**1.5)),width=2)
    return _merge(image,glow,crisp,3.7)


def _draw_shell(ctx: dict[str, object], t: float) -> Image.Image:
    frame, image, glow, crisp, gdraw, draw = _base(ctx, t)
    a,b,c=ctx["colours"]
    angles,lane=ctx["angles"],ctx["lane"]
    assert isinstance(angles,np.ndarray) and isinstance(lane,np.ndarray)
    phase=float(ctx["phase"])
    cx,cy=WORK_W*.5,WORK_H*.52
    for shell in range(9):
        progress=(t*.28+shell/9+phase*.08)%1
        rr=35+440*progress
        gdraw.ellipse((cx-rr,cy-rr*.65,cx+rr,cy+rr*.65),outline=(*(a if shell%2 else b),int(110*(1-progress)**1.7)),width=2)
    for i in range(len(angles)):
        rr=90+420*((t*.12+lane[i])%1)
        px=cx+math.cos(float(angles[i])+t*.32)*rr
        py=cy+math.sin(float(angles[i])+t*.32)*rr*.65
        if -6<px<WORK_W+6 and -6<py<WORK_H+6:
            colour=a if i%3 else c
            s=.8+1.8*lane[i]
            draw.ellipse((px-s,py-s,px+s,py+s),fill=(*colour,170))
    draw.ellipse((cx-22,cy-22,cx+22,cy+22),fill=(250,215,155,220),outline=(*b,185),width=2)
    return _merge(image,glow,crisp,3.6)


def _draw_web(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    a,b,c=ctx["colours"]
    rng=ctx["rng"]
    assert isinstance(rng,np.random.Generator)
    # Generate a stable wire structure from per-track seed on first draw.
    if "web_nodes" not in ctx:
        clusters=16
        anchors=np.column_stack((rng.uniform(-330,330,clusters),rng.uniform(-400,400,clusters),rng.uniform(-200,1550,clusters)))
        nodes=[]; group=[]
        for ci,anchor in enumerate(anchors):
            for _ in range(18):
                nodes.append(anchor+rng.normal((0,0,0),(38,38,90)))
                group.append(ci)
        ctx["web_nodes"]=np.asarray(nodes,dtype=np.float32)
        edges=[]
        for ci in range(clusters):
            ids=[i for i,g in enumerate(group) if g==ci]
            for j in range(len(ids)-1):
                edges.append((ids[j],ids[(j+1)%len(ids)]))
                if j+3<len(ids):edges.append((ids[j],ids[j+3]))
        for ci in range(clusters-1):edges.append((ci*18,(ci+1)*18))
        ctx["web_edges"]=edges
    nodes=ctx["web_nodes"]
    edges=ctx["web_edges"]
    assert isinstance(nodes,np.ndarray) and isinstance(edges,list)
    x=nodes[:,0]+30*np.sin(t*.32+nodes[:,2]*.013)
    y=nodes[:,1]+25*np.cos(t*.25+nodes[:,0]*.017)
    z=((nodes[:,2]-t*130+200)%1800)-250
    sx,sy,depth=_project(x,y,z,.18*math.sin(t*.34),.13*math.cos(t*.22),990,740,WORK_W*.5,WORK_H*.51)
    for i,j in edges:
        if -50<sx[i]<WORK_W+50 and -50<sx[j]<WORK_W+50 and -50<sy[i]<WORK_H+50 and -50<sy[j]<WORK_H+50:
            _line(gdraw,[(float(sx[i]),float(sy[i])),(float(sx[j]),float(sy[j]))],(*b,60),1)
    for i in np.argsort(depth)[::-1]:
        if -8<sx[i]<WORK_W+8 and -8<sy[i]<WORK_H+8:
            near=max(.18,min(1,1-(depth[i]+300)/1500))
            col=a if i%3==0 else b if i%3==1 else c
            size=.8+4*near
            if near>.52:gdraw.ellipse((sx[i]-size*3,sy[i]-size*3,sx[i]+size*3,sy[i]+size*3),fill=(*col,40))
            draw.ellipse((sx[i]-size,sy[i]-size,sx[i]+size,sy[i]+size),fill=(*col,int(110+120*near)))
    return _merge(image,glow,crisp,3.1)


def _draw_spiral(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    xx,yy=ctx["xx"],ctx["yy"]
    assert isinstance(xx,np.ndarray) and isinstance(yy,np.ndarray)
    a,b,c=ctx["colours"]
    rng=ctx["rng"]
    assert isinstance(rng,np.random.Generator)
    if "spiral_data" not in ctx:
        n=920
        ctx["spiral_data"]=(rng.integers(0,5,n),28+310*np.sqrt(rng.random(n)),rng.normal(0,.23,n),rng.normal(0,22,n),rng.uniform(.2,1,n))
    arms,radius,jitter,height,bright=ctx["spiral_data"]
    assert isinstance(arms,np.ndarray) and isinstance(radius,np.ndarray) and isinstance(jitter,np.ndarray) and isinstance(height,np.ndarray) and isinstance(bright,np.ndarray)
    cx,cy=WORK_W*.5+12*math.sin(t*.27),WORK_H*.51
    angle=arms*TAU/5+np.log(radius/20)*1.52+t*(.35+1.4*100/radius)+jitter
    x=radius*np.cos(angle); z=radius*np.sin(angle); y=height
    sx,sy,depth=_project(x,y,z,.45*math.sin(t*.24),.72+.15*math.sin(t*.2),880,710,cx,cy)
    _add_glow(frame,xx,yy,cx,cy,115,95,tuple(v/14 for v in c),1.0)
    for i in np.argsort(depth)[::-1]:
        if -6<sx[i]<WORK_W+6 and -6<sy[i]<WORK_H+6:
            col=a if arms[i]%3==0 else b if arms[i]%3==1 else c
            size=.7+2.3*bright[i]
            if bright[i]>.85:gdraw.ellipse((sx[i]-size*4,sy[i]-size*4,sx[i]+size*4,sy[i]+size*4),fill=(*col,35))
            draw.ellipse((sx[i]-size,sy[i]-size,sx[i]+size,sy[i]+size),fill=(*col,int(100+145*bright[i])))
    draw.ellipse((cx-26,cy-23,cx+26,cy+23),fill=(2,1,8,225),outline=(*b,160),width=2)
    return _merge(image,glow,crisp,3.3)


def _draw_metric(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    a,b,c=ctx["colours"]
    gx=np.linspace(-340,340,34);gz=np.linspace(-320,320,28)
    xxg,zzg=np.meshgrid(gx,gz)
    angle=t*1.05+float(ctx["phase"])
    sources=((110*math.cos(angle),110*math.sin(angle)),(-110*math.cos(angle),-110*math.sin(angle)))
    height=np.zeros_like(xxg)
    for sx0,sz0 in sources:
        d=np.sqrt((xxg-sx0)**2+(zzg-sz0)**2+750)
        height+=-3300/d+17*np.sin(d*.078-t*2.7)*np.exp(-d/450)
    px,py,depth=_project(xxg.ravel(),height.ravel(),zzg.ravel(),-.38+.2*math.sin(t*.26),.58,990,810,WORK_W*.5,WORK_H*.55)
    px=px.reshape(xxg.shape);py=py.reshape(xxg.shape)
    for r in range(px.shape[0]):
        pts=[(float(px[r,k]),float(py[r,k])) for k in range(px.shape[1])]
        _line(gdraw,pts,(*(a if r%3==0 else b),90 if r%3==0 else 45),2 if r%3==0 else 1)
        if r%4==0:_line(draw,pts,(*a,72),1)
    for col in range(px.shape[1]):
        pts=[(float(px[r,col]),float(py[r,col])) for r in range(px.shape[0])]
        _line(gdraw,pts,(*c,62 if col%3==0 else 30),2 if col%3==0 else 1)
    for sx0,sz0 in sources:
        bx,by,_=_project(np.array([sx0]),np.array([-120.0]),np.array([sz0]),-.38+.2*math.sin(t*.26),.58,990,810,WORK_W*.5,WORK_H*.55)
        draw.ellipse((bx[0]-31,by[0]-28,bx[0]+31,by[0]+28),fill=(0,1,6,245),outline=(*c,165),width=2)
    return _merge(image,glow,crisp,2.7)


def _draw_sphere(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    a,b,c=ctx["colours"]
    rng=ctx["rng"]
    assert isinstance(rng,np.random.Generator)
    if "sphere_data" not in ctx:
        lat=np.linspace(-math.pi/2+.045,math.pi/2-.045,34)
        lon=np.linspace(0,TAU,68,endpoint=False)
        lo,la=np.meshgrid(lon,lat)
        lo,la=lo.ravel(),la.ravel()
        texture=.48*np.sin(lo*5+la*2)+.31*np.sin(lo*11-la*6)+rng.normal(0,.26,len(lo))
        ctx["sphere_data"]=(lo,la,texture)
    lon,lat,texture=ctx["sphere_data"]
    assert isinstance(lon,np.ndarray) and isinstance(lat,np.ndarray) and isinstance(texture,np.ndarray)
    cx,cy=WORK_W*.5,WORK_H*.52
    radius=245+12*math.sin(t*.34)
    yaw=t*.55+float(ctx["phase"])
    x=np.cos(lat)*np.cos(lon+yaw);z=np.cos(lat)*np.sin(lon+yaw);y=np.sin(lat)
    pitch=.22*math.sin(t*.34+float(ctx["phase"]))
    yp=y*math.cos(pitch)-z*math.sin(pitch);zp=y*math.sin(pitch)+z*math.cos(pitch)
    sx=cx+radius*x;sy=cy+radius*yp
    for i in np.argsort(zp):
        if zp[i]<-.08:continue
        val=texture[i]+.18*math.sin(t*1.5+lon[i]*2)
        col=a if val>.38 else b if val<-.38 else c
        size=.8+1.7*max(0,zp[i])
        draw.ellipse((sx[i]-size,sy[i]-size,sx[i]+size,sy[i]+size),fill=(*col,int(105+115*max(0,zp[i]))))
    scan=(t*.72)%1
    rr=16+radius*1.22*scan
    gdraw.ellipse((cx-rr,cy-rr,cx+rr,cy+rr),outline=(*a,int(115*(1-scan))),width=2)
    gdraw.line((cx,cy,cx+math.cos(t*1.1)*radius,cy+math.sin(t*1.1)*radius),fill=(*b,110),width=3)
    draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=(*b,105),width=2)
    return _merge(image,glow,crisp,3.6)


def _draw_lensfield(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    xx,yy=ctx["xx"],ctx["yy"]
    assert isinstance(xx,np.ndarray) and isinstance(yy,np.ndarray)
    a,b,c=ctx["colours"]
    rng=ctx["rng"]
    assert isinstance(rng,np.random.Generator)
    if "lensstars" not in ctx:
        n=530
        ctx["lensstars"]=(rng.uniform(-80,WORK_W+80,n),rng.uniform(-90,WORK_H+90,n),rng.uniform(.2,1,n),rng.uniform(0,TAU,n))
    x,y,bright,angle0=ctx["lensstars"]
    assert isinstance(x,np.ndarray) and isinstance(y,np.ndarray) and isinstance(bright,np.ndarray) and isinstance(angle0,np.ndarray)
    cx,cy=WORK_W*.51,WORK_H*.5
    dx=x-cx;dy=y-cy;d=np.maximum(20,np.hypot(dx,dy))
    bend=2600/(d*d+2400)
    theta=np.arctan2(dy,dx)+bend*np.sin(t*.65+angle0)
    sx=cx+d*np.cos(theta)+18*np.sin(t*.25+angle0)
    sy=cy+d*np.sin(theta)
    _add_glow(frame,xx,yy,cx,cy,130,130,tuple(v/14 for v in a),1.0)
    for px,py,m in zip(sx,sy,bright):
        if -4<px<WORK_W+4 and -4<py<WORK_H+4:
            size=.6+2.1*m
            col=b if m>.67 else a
            if m>.85:gdraw.ellipse((px-size*4,py-size*4,px+size*4,py+size*4),fill=(*col,40))
            draw.ellipse((px-size,py-size,px+size,py+size),fill=(*col,int(100+130*m)))
    for ring in range(8):
        rr=84+ring*25+6*math.sin(t+ring)
        gdraw.arc((cx-rr,cy-rr*.65,cx+rr,cy+rr*.65),15+ring*11,164+ring*9,fill=(*c,78),width=2)
    draw.ellipse((cx-78,cy-70,cx+78,cy+70),fill=(0,0,4,255),outline=(*b,190),width=2)
    return _merge(image,glow,crisp,3.5)


def _draw_orbits(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    a,b,c=ctx["colours"]
    cx,cy=WORK_W*.5,WORK_H*.5
    phase=float(ctx["phase"])
    for plane in range(9):
        rx=85+plane*34;ry=18+plane*9
        tilt=(plane-4)*.15+math.sin(t*.35+plane)*.11
        points=[]
        for angle in np.linspace(0,TAU,75):
            x=rx*math.cos(angle);y=ry*math.sin(angle)
            points.append((cx+x*math.cos(tilt)-y*math.sin(tilt),cy+x*math.sin(tilt)+y*math.cos(tilt)))
        col=a if plane%3==0 else b if plane%3==1 else c
        _line(gdraw,points,(*col,88),2)
        sat_angle=t*(.9+plane*.12)+plane*TAU/9+phase
        px=cx+rx*math.cos(sat_angle)*math.cos(tilt)-ry*math.sin(sat_angle)*math.sin(tilt)
        py=cy+rx*math.cos(sat_angle)*math.sin(tilt)+ry*math.sin(sat_angle)*math.cos(tilt)
        gdraw.ellipse((px-10,py-10,px+10,py+10),fill=(*col,58))
        draw.ellipse((px-2,py-2,px+2,py+2),fill=(*col,230))
    draw.ellipse((cx-34,cy-34,cx+34,cy+34),fill=(2,2,9,238),outline=(*b,180),width=2)
    return _merge(image,glow,crisp,3.4)


def _draw_wave(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    a,b,c=ctx["colours"]
    cx,cy=WORK_W*.5,WORK_H*.52
    # Three moving wave sheets staggered in depth.
    for sheet in range(7):
        y0=180+sheet*85
        points=[]
        for x in np.linspace(-30,WORK_W+30,90):
            y=y0+23*math.sin(x*.025+t*(1.8+sheet*.06)+sheet)+10*math.sin(x*.055-t*.8)
            points.append((float(x),float(y)))
        col=a if sheet%3==0 else b if sheet%3==1 else c
        _line(gdraw,points,(*col,88),2)
    for ring in range(6):
        u=(t*.55+ring/6)%1
        rr=28+480*u
        gdraw.ellipse((cx-rr,cy-rr*.42,cx+rr,cy+rr*.42),outline=(*a,int(115*(1-u)**1.6)),width=2)
    draw.ellipse((cx-28,cy-25,cx+28,cy+25),fill=(0,1,7,248),outline=(*c,170),width=2)
    return _merge(image,glow,crisp,3.0)


def _draw_lattice(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    a,b,c=ctx["colours"]
    coords=[]
    for x in (-150,-75,0,75,150):
        for y in (-150,-75,0,75,150):
            for z in (-150,-75,0,75,150):coords.append((x,y,z))
    pts=np.asarray(coords,dtype=np.float32)
    sx,sy,depth=_project(pts[:,0],pts[:,1],pts[:,2],t*.52+float(ctx["phase"]),.40+math.sin(t*.33)*.18,680,600,WORK_W*.5,WORK_H*.51)
    # Edges only between adjacent lattice coordinates.
    for i,p in enumerate(pts):
        for axis in range(3):
            target=p.copy();target[axis]+=75
            match=np.where(np.all(np.isclose(pts,target),axis=1))[0]
            if len(match):
                j=int(match[0]);_line(gdraw,[(float(sx[i]),float(sy[i])),(float(sx[j]),float(sy[j]))],(*b,45),1)
    for i in np.argsort(depth)[::-1]:
        if -5<sx[i]<WORK_W+5 and -5<sy[i]<WORK_H+5:
            col=a if i%3==0 else b if i%3==1 else c
            size=1.0+1.7*max(.1,1-depth[i]/850)
            draw.ellipse((sx[i]-size,sy[i]-size,sx[i]+size,sy[i]+size),fill=(*col,195))
    return _merge(image,glow,crisp,2.5)


def _draw_data(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    a,b,c=ctx["colours"]
    rng=ctx["rng"]
    assert isinstance(rng,np.random.Generator)
    if "data_values" not in ctx:
        ctx["data_values"]=rng.uniform(.15,1,(10,28))
    vals=ctx["data_values"]
    assert isinstance(vals,np.ndarray)
    # Animated 3D-ish detector panels, deliberately different from all galaxy/BH
    # silhouettes. Strong movement is conveyed by scanning and cascaded dots.
    for row in range(10):
        y=180+row*55
        scan=int((t*11+row*3)%28)
        for col in range(28):
            x=45+col*16
            value=vals[row,col]*(.4+.6*math.sin(t*1.1+row*.7+col*.2)**2)
            if abs(col-scan)<2:value=1
            colr=a if row%3==0 else b if row%3==1 else c
            size=2+5*value
            draw.rounded_rectangle((x-size,y-size*.45,x+size,y+size*.45),radius=2,fill=(*colr,int(55+185*value)))
    for k in range(5):
        x=70+((t*90+k*98)%400)
        gdraw.line((x,130,x,770),fill=(*b,70),width=3)
    return _merge(image,glow,crisp,2.5)


def _draw_void(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    xx,yy=ctx["xx"],ctx["yy"]
    assert isinstance(xx,np.ndarray) and isinstance(yy,np.ndarray)
    a,b,c=ctx["colours"]
    phase=float(ctx["phase"])
    cx=WORK_W*(.5+.15*math.sin(t*.22+phase));cy=WORK_H*(.5+.08*math.cos(t*.27+phase))
    _add_glow(frame,xx,yy,cx,cy,190,150,tuple(v/10 for v in a),1.0)
    for arm in range(12):
        pts=[]
        base=arm*TAU/12+t*.32
        for r in np.linspace(85,430,48):
            theta=base+math.log(r/60)*.75
            pts.append((cx+math.cos(theta)*r,cy+math.sin(theta)*r*.55))
        _line(gdraw,pts,(*(a if arm%2 else c),72),2)
    for ring in range(6):
        rr=88+ring*23+9*math.sin(t*1.4+ring)
        draw.ellipse((cx-rr,cy-rr*.60,cx+rr,cy+rr*.60),outline=(*b,85),width=1)
    draw.ellipse((cx-77,cy-63,cx+77,cy+63),fill=(0,0,4,255),outline=(*a,155),width=2)
    return _merge(image,glow,crisp,4.0)


def _draw_outro(ctx: dict[str, object], t: float) -> Image.Image:
    frame,image,glow,crisp,gdraw,draw=_base(ctx,t)
    xx,yy=ctx["xx"],ctx["yy"]
    assert isinstance(xx,np.ndarray) and isinstance(yy,np.ndarray)
    a,b,c=ctx["colours"]
    cx,cy=WORK_W*.5,WORK_H*.54
    pulse=.55+.45*math.sin(t*2.7)**2
    _add_glow(frame,xx,yy,cx,cy,165,120,tuple(v/8 for v in b),pulse)
    for ring in range(12):
        rr=55+ring*21+10*math.sin(t*1.6+ring*.8)
        start=(t*.55+ring*.17)*180/math.pi
        gdraw.arc((cx-rr,cy-rr*.58,cx+rr,cy+rr*.58),start,start+168,fill=(*(a if ring%2 else b),85),width=3)
    for j in range(130):
        angle=j*TAU/130+t*.8
        r=110+95*math.sin(j*.69+t*.8)**2
        px=cx+math.cos(angle)*r;py=cy+math.sin(angle)*r*.58
        col=a if j%3==0 else b if j%3==1 else c
        draw.ellipse((px-1.5,py-1.5,px+1.5,py+1.5),fill=(*col,180))
    draw.ellipse((cx-62,cy-53,cx+62,cy+53),fill=(1,1,7,252),outline=(*b,185),width=2)
    return _merge(image,glow,crisp,3.8)


RENDERERS = {
    "accretion": _draw_accretion,
    "lensfield": _draw_lensfield,
    "binary": _draw_binary,
    "lattice": _draw_lattice,
    "jet": _draw_jet,
    "funnel": _draw_funnel,
    "bounce": _draw_bounce,
    "shell": _draw_shell,
    "spiral": _draw_spiral,
    "web": _draw_web,
    "sphere": _draw_sphere,
    "metric": _draw_metric,
    "wave": _draw_wave,
    "orbits": _draw_orbits,
    "data": _draw_data,
    "void": _draw_void,
    "outro": _draw_outro,
}


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def render_track(spec: TrackSpec, output: Path, ffmpeg: str, force: bool = False) -> Path:
    if spec.family not in RENDERERS:
        raise ValueError(f"Unknown fresh v4 visual family: {spec.family}")
    if output.exists() and output.stat().st_size > 80_000 and not force:
        return output
    print(f"[3d v4] {spec.key:<29} {spec.family:<10} {spec.duration:.2f}s")
    ctx = _build_context(spec)
    renderer = RENDERERS[spec.family]
    process = _writer(output, ffmpeg)
    try:
        frame_count = max(1, int(round(spec.duration * FPS)))
        for frame_index in range(frame_count):
            t = frame_index / FPS
            process.stdin.write(_finish_image(renderer(ctx, t)).tobytes())  # type: ignore[union-attr]
    finally:
        _finish(process, spec.key)
    return output


def render_unique_tracks(specs: Iterable[TrackSpec], output_dir: Path, ffmpeg: str, force: bool = False) -> dict[str, Path]:
    """Render source tracks while enforcing key and full-file hash uniqueness."""
    spec_list = list(specs)
    keys = [spec.key for spec in spec_list]
    duplicate_keys = sorted({key for key in keys if keys.count(key) > 1})
    if duplicate_keys:
        raise RuntimeError("Duplicate visual track key(s) blocked: " + ", ".join(duplicate_keys))
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {spec.key: render_track(spec, output_dir / f"{spec.key}.mp4", ffmpeg, force) for spec in spec_list}
    hashes: dict[str, str] = {}
    identical: list[str] = []
    for key, path in rendered.items():
        digest = _hash(path)
        if digest in hashes:
            identical.append(f"{key} == {hashes[digest]}")
        hashes[digest] = key
    if identical:
        raise RuntimeError("Byte-identical rendered backgrounds blocked: " + "; ".join(identical))
    return rendered
