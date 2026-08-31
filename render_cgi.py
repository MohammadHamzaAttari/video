#!/usr/bin/env python3
"""
render_cgi.py — renders every shot of the dinosaur-day short to 1080x1920@30fps
clips with cinematic grade, film grain, letterbox bars, procedural CGI and baked
captions. Reads plan.json (from build_dino_day.py --plan).
"""
import os, sys, json, subprocess, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

ROOT = os.path.dirname(os.path.abspath(__file__))
PLAN = json.load(open(os.path.join(ROOT, "plan.json")))
CLIPS = os.path.join(ROOT, "sources_dino")
os.makedirs(CLIPS, exist_ok=True)

W, H, FPS = 1080, 1920, 30
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()

def enc_start(out):
    return subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-an", out], stdin=subprocess.PIPE)

def push(proc, frame):
    proc.stdin.write(np.ascontiguousarray(frame).tobytes())

def finish(proc):
    proc.stdin.close(); proc.wait()

# ---------------- fonts ----------------
_fonts = {}
def font(size):
    key = (size, "b")
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(FONT_B, size)
    return _fonts[key]

# ---------------- captions ----------------
CAP_POS = H - 350   # main caption line (above bottom letterbox)

def caption_alpha(t, t0, t1, fi=0.22, fo=0.25):
    if t < t0: return 0.0
    if t < t0 + fi: return (t - t0) / fi
    if t < t1 - fo: return 1.0
    if t < t1: return (t1 - t) / fo
    return 0.0

def bake_caption(img, text, t, t0, t1, style="cap"):
    a = caption_alpha(t, t0, t1)
    if a <= 0.01: return img
    size = {"cap": 44, "cap_big": 56}.get(style, 44)
    f = font(size)
    # pop-in scale
    pop = 1.0
    if t < t0 + 0.18:
        pop = 1.0 + 0.10 * ((t - t0) / 0.18)
    f2 = font(int(size * pop)) if pop > 1.01 else f
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    bb = d.textbbox((0, 0), text, font=f2)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x = (W - tw) // 2
    y = CAP_POS - th // 2
    padx, pady = 26, 14
    d.rectangle([x - padx, y - pady, x + tw + padx, y + th + pady], fill=(0, 0, 0, int(200 * a)))
    # gold accent line under the box
    d.rectangle([x - padx, y + th + pady - 3, x + tw + padx, y + th + pady + 1], fill=(255, 212, 0, int(235 * a)))
    d.text((x, y), text, font=f2, fill=(255, 212, 0, int(255 * a)))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    return img

# ---------------- post (grade / grain / letterbox) ----------------
_VIG = None
def vignette_mask():
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((xx - W/2)/(W/2))**2 + ((yy - H/2)/(H/2))**2)
        _VIG = np.clip(1.0 - 0.32 * np.clip(d - 0.62, 0, None) ** 1.6, 0, 1)[..., None]
    return _VIG

def post(frame, t, captions=(), letter=True, grade=True):
    """frame: np.uint8 HxWx3 -> graded, grained, letterboxed, captioned"""
    img = Image.fromarray(frame)
    if grade:
        img = ImageEnhance.Color(img).enhance(1.12)
        img = ImageEnhance.Contrast(img).enhance(1.06)
        img = ImageEnhance.Brightness(img).enhance(0.98)
    arr = np.asarray(img, dtype=np.float32) * vignette_mask()
    # subtle teal shadows / warm highlights
    arr[..., 0] *= 1.03
    arr[..., 2] *= 1.04
    rng = np.random.default_rng(int(t * 1000) % 2**31)
    arr += rng.integers(-5, 6, (H//2, W//2, 1)).repeat(2, 0).repeat(2, 1)[:H, :W]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if letter:
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 128], fill=(0, 0, 0))
        d.rectangle([0, H-128, W, H], fill=(0, 0, 0))
        d.rectangle([0, 128, W, 130], fill=(255, 212, 0))
        d.rectangle([0, H-130, W, H-128], fill=(255, 212, 0))
    for c in captions:
        img = bake_caption(img, c["text"], t, c["t0"], c["t1"], c.get("style", "cap"))
    return img

# ---------------- image shots (Ken Burns) ----------------
def load_cover(path):
    im = Image.open(path).convert("RGB")
    sc = max(W / im.width, H / im.height) * 1.25   # headroom for zoom
    im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
    x = (im.width - W) // 2; y = (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))

def kens_frame(base, t, dur, zoom, pan):
    z0, z1 = zoom; (px0, py0), (px1, py1) = pan
    frac = t / dur if dur > 0 else 1.0
    z = z0 + (z1 - z0) * frac
    px = px0 + (px1 - px0) * frac
    py = py0 + (py1 - py0) * frac
    cw, ch = int(W / z), int(H / z)
    cx = int(px * (base.width - cw)); cy = int(py * (base.height - ch))
    return base.crop((cx, cy, cx + cw, cy + ch)).resize((W, H), Image.LANCZOS)

def render_image_shot(sh):
    base = load_cover(sh["src"])
    dur = sh["end"] - sh["start"]
    caps = caps_for(sh)
    proc = enc_start(os.path.join(CLIPS, f"{sh['id']}.mp4"))
    n = int(round(dur * FPS))
    for i in range(n):
        t = i / FPS
        f = kens_frame(base, t, dur, sh["zoom"], sh["pan"])
        f = post(np.asarray(f), t, caps)
        if sh.get("fx") == "tsunami":
            f = fx_tsunami(f, t)
        if sh.get("fx") == "flicker":
            f = fx_flicker(f, t)
        push(proc, np.asarray(f))
    finish(proc)
    print("rendered", sh["id"])

# ---------------- fx ----------------
def fx_tsunami(img, t):
    if t < 0.3: return img
    a = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(a)
    tt = t - 0.3
    r = int(300 + tt * 2200)
    alpha = max(0, int(200 * (1 - tt / 1.6)))
    if r > 200:
        d.ellipse([W/2 - r, H*0.42 - r, W/2 + r, H*0.42 + r], outline=(255, 235, 200, alpha), width=14)
        d.ellipse([W/2 - r*0.82, H*0.42 - r*0.82, W/2 + r*0.82, H*0.42 + r*0.82], outline=(255, 160, 60, alpha//2), width=8)
    if t < 0.45:
        flash = Image.new("RGBA", img.size, (255, 255, 255, int(180 * (1 - (t-0.3)/0.15))))
        a = Image.alpha_composite(a, flash)
    if t < 1.4:
        j = int(10 * (1 - t / 1.4))
        if j:
            img = img.transform(img.size, Image.AFFINE, (1, 0, np.random.default_rng(int(t*100)).integers(-j, j), 0, 1, np.random.default_rng(int(t*100)+7).integers(-j, j)))
    return Image.alpha_composite(img.convert("RGBA"), a).convert("RGB")

def fx_flicker(img, t):
    rng = np.random.default_rng(int(t * 60))
    f = 0.82 + 0.18 * abs(rng.normal())
    arr = np.asarray(img, dtype=np.float32) * f
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

# ---------------- procedural: asteroid flyby ----------------
def render_asteroid(sh):
    dur = sh["end"] - sh["start"]
    caps = caps_for(sh)
    rng = np.random.default_rng(7)
    stars = [(rng.integers(0, W), rng.integers(0, H), rng.uniform(0.3, 1.0)) for _ in range(260)]
    proc = enc_start(os.path.join(CLIPS, f"{sh['id']}.mp4"))
    n = int(round(dur * FPS))
    # glow sprite
    s = 256
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.sqrt((xx - s/2)**2 + (yy - s/2)**2) / (s/2)
    core = np.clip(1 - r / 0.25, 0, 1)
    glow = np.clip(1 - r, 0, 1) ** 2.2
    sprite_core = np.stack([np.full_like(r, 255), np.full_like(r, 250), np.full_like(r, 220), core * 255], -1).astype(np.uint8)
    sprite_glow = np.stack([np.full_like(r, 255), np.full_like(r, 140), np.full_like(r, 30), glow * 255], -1).astype(np.uint8)
    trail = []
    for i in range(n):
        t = i / FPS
        frac = t / dur
        # path top-right -> lower-left
        x = W * (0.86 - 0.74 * frac)
        y = H * (0.06 + 0.72 * frac)
        fr = 34 + 60 * frac
        arr = np.zeros((H, W, 3), dtype=np.uint8)
        arr[:] = (4, 4, 8)
        for (sx, sy, sm) in stars:
            tw = 0.5 + 0.5 * np.sin(t * 2.0 + sx * 0.05)
            v = int(180 * sm * tw)
            arr[sy, sx] = (v, v, v)
        img = Image.fromarray(arr)
        # trail
        trail.append((x, y, fr))
        for j, (tx, ty, tr) in enumerate(trail):
            if j < len(trail) - 3:
                continue
            al = (j + 1) / len(trail)
            gs = sprite_glow
            g = Image.fromarray(gs).resize((int(tr * 4 * al) + 2, int(tr * 4 * al) + 2), Image.BILINEAR)
            img.paste(g, (int(tx) - g.width // 2, int(ty) - g.height // 2), g)
        c = Image.fromarray(sprite_core).resize((int(fr * 2.2), int(fr * 2.2)), Image.BILINEAR)
        img.paste(c, (int(x) - c.width // 2, int(y) - c.height // 2), c)
        img = img.filter(ImageFilter.GaussianBlur(1.2))
        # shake
        if t > dur - 1.2:
            j = int(6 * (t - (dur - 1.2)) / 1.2)
            if j:
                img = img.transform(img.size, Image.AFFINE, (1, 0, rng.integers(-j, j), 0, 1, rng.integers(-j, j)))
        img = post(np.asarray(img), t, caps)
        push(proc, np.asarray(img))
    finish(proc)
    print("rendered", sh["id"])

# ---------------- procedural: impact explosion ----------------
def render_impact(sh):
    dur = sh["end"] - sh["start"]
    caps = caps_for(sh)
    rng = np.random.default_rng(11)
    proc = enc_start(os.path.join(CLIPS, f"{sh['id']}.mp4"))
    n = int(round(dur * FPS))
    # fireball gradient sprites (precomputed once)
    s = 1024
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    r = np.sqrt((xx - s/2)**2 + (yy - s/2)**2) / (s/2)
    sprites = []
    for (rr, col) in [(0.30, (255, 250, 235)), (0.55, (255, 190, 60)), (0.80, (235, 90, 20)), (1.00, (140, 30, 8))]:
        mask = np.clip(1 - r / rr, 0, 1) ** 2.4
        rgba = np.stack([np.full_like(r, c) for c in col] + [mask * 255], -1).astype(np.uint8)
        sprites.append(Image.fromarray(rgba))
    debris = []
    for _ in range(420):
        ang = rng.uniform(-np.pi, 0)  # upward hemisphere
        sp = rng.uniform(0.05, 1.0)
        debris.append([W/2, H*0.5, ang, sp, rng.uniform(2, 7), rng.uniform(0.4, 1.0)])
    for i in range(n):
        t = i / FPS
        arr = np.zeros((H, W, 3), dtype=np.uint8)
        # bg gradient
        g = np.linspace(10, 26, H, dtype=np.float32)[:, None]
        arr[:] = np.tile(np.concatenate([g * 1.4, g * 0.55, g * 0.35], -1)[:, None, :], (1, W, 1)).astype(np.uint8)
        img = Image.fromarray(arr)
        if t < 1.9:
            R = int(60 + (t ** 1.35) * 520)
            rs = int(R * 0.45)
            for (rr, col), sprite in zip([(0.30, (255, 250, 235)), (0.55, (255, 190, 60)), (0.80, (235, 90, 20)), (1.00, (140, 30, 8))], sprites):
                size = int(rr * rs * 2.4)
                g2 = sprite.resize((size, size), Image.BILINEAR)
                img.paste(g2, (W//2 - size//2, int(H*0.5) - size//2), g2)
        # shock ring
        if 0.5 < t < 2.4:
            dr = Image.new("RGBA", img.size, (0, 0, 0, 0))
            dd = ImageDraw.Draw(dr)
            rr = int(120 + (t - 0.5) * 1500)
            al = int(220 * (1 - (t - 0.5) / 1.9))
            dd.ellipse([W/2 - rr, H*0.5 - rr, W/2 + rr, H*0.5 + rr], outline=(255, 220, 160, al), width=26)
            dd.ellipse([W/2 - rr*0.9, H*0.5 - rr*0.9, W/2 + rr*0.9, H*0.5 + rr*0.9], outline=(255, 140, 40, al//2), width=10)
            img = Image.alpha_composite(img.convert("RGBA"), dr).convert("RGB")
        # debris
        if t > 0.25:
            dr = Image.new("RGBA", img.size, (0, 0, 0, 0))
            dd = ImageDraw.Draw(dr)
            for d in debris:
                d[3] += d[4] * 0.02
                px = d[0] + np.cos(d[2]) * d[3] * 900 * t * 0.35
                py = d[1] + np.sin(d[2]) * d[3] * 900 * t * 0.35 + 220 * t * t
                if 0 < px < W and 0 < py < H:
                    dd.ellipse([px - d[5], py - d[5], px + d[5], py + d[5]], fill=(255, int(180*d[5]), 60, int(230 * min(1, t * 1.5))))
            img = Image.alpha_composite(img.convert("RGBA"), dr).convert("RGB")
        # smoke
        if t > 1.6:
            dr = Image.new("RGBA", img.size, (0, 0, 0, 0))
            dd = ImageDraw.Draw(dr)
            for k in range(14):
                st = t - 1.6 - k * 0.18
                if st <= 0: continue
                bx = W/2 + (rng.integers(-1, 1) or 1) * int(200 * st)
                by = H*0.5 - int(160 * st)
                rad = int(120 + 130 * st)
                dd.ellipse([bx - rad, by - rad, bx + rad, by + rad], fill=(20, 18, 18, int(90 * min(1, st))))
            img = Image.alpha_composite(img.convert("RGBA"), dr).convert("RGB")
        # flash
        if t < 0.30:
            fa = int(255 * (1 - t / 0.30))
            fl = Image.new("RGB", img.size, (255, 255, 255))
            img = Image.blend(img, fl, fa / 255 * 0.85)
        # shake
        if t < 2.2:
            j = int(9 * (1 - t / 2.2))
            if j:
                img = img.transform(img.size, Image.AFFINE, (1, 0, rng.integers(-j, j), 0, 1, rng.integers(-j, j)))
        img = post(np.asarray(img), t, caps)
        push(proc, np.asarray(img))
    finish(proc)
    print("rendered", sh["id"])

# ---------------- procedural: ash fall ----------------
def render_ash(sh):
    dur = sh["end"] - sh["start"]
    caps = caps_for(sh)
    rng = np.random.default_rng(23)
    proc = enc_start(os.path.join(CLIPS, f"{sh['id']}.mp4"))
    n = int(round(dur * FPS))
    motes = []
    for _ in range(320):
        motes.append([rng.uniform(0, W), rng.uniform(0, H), rng.uniform(6, 30), rng.uniform(2, 6), rng.uniform(0.15, 0.5), rng.uniform(0, 6.28)])
    for i in range(n):
        t = i / FPS
        g = np.linspace(16, 30, H, dtype=np.float32)[:, None]
        arr = np.concatenate([g, g * 0.98, g * 1.05], -1)
        arr = np.tile(arr[:, None, :], (1, W, 1))
        img = Image.fromarray(arr.astype(np.uint8))
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(ov)
        for m in motes:
            m[1] += m[2] / FPS
            if m[1] > H + 10: m[1] = -10
            x = m[0] + np.sin(t * 1.2 + m[5]) * 14
            al = int(255 * m[4])
            sz = m[3]
            dr.ellipse([x - sz, m[1] - sz, x + sz, m[1] + sz], fill=(168, 168, 172, al))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
        img = post(np.asarray(img), t, caps)
        push(proc, np.asarray(img))
    finish(proc)
    print("rendered", sh["id"])

# ---------------- title / endcard ----------------
def render_title(sh):
    dur = sh["end"] - sh["start"]
    proc = enc_start(os.path.join(CLIPS, f"{sh['id']}.mp4"))
    rng = np.random.default_rng(31)
    n = int(round(dur * FPS))
    embers = [[W/2 + rng.integers(-500, 500), H*0.75, rng.uniform(30, 90), rng.uniform(2, 5)] for _ in range(70)]
    TL = [("THE DAY", 0.30, 44, (255, 212, 0)),
          ("THE DINOSAURS", 0.55, 74, (255, 255, 255)),
          ("DIED", 0.85, 120, (255, 90, 40)),
          ("66 MILLION YEARS AGO", 1.15, 40, (255, 212, 0))]
    for i in range(n):
        t = i / FPS
        arr = np.zeros((H, W, 3), dtype=np.uint8)
        g = np.linspace(8, 18, H, dtype=np.float32)[:, None]
        arr[:] = np.tile(np.concatenate([g * 1.6, g * 0.6, g * 0.35], -1)[:, None, :], (1, W, 1)).astype(np.uint8)
        img = Image.fromarray(arr)
        # rising embers
        dr = ImageDraw.Draw(img)
        for e in embers:
            e[1] -= e[2] / FPS
            e[0] += np.sin(t * 2 + e[1] * 0.01) * 1.2
            if e[1] < -20:
                e[1] = H + 20; e[0] = rng.integers(100, W - 100)
            r = e[3]
            dr.ellipse([e[0]-r, e[1]-r, e[0]+r, e[1]+r], fill=(255, int(140 * 0.7), 40, 200))
        img = img.filter(ImageFilter.GaussianBlur(1.0))
        # fireball glow at bottom
        gl = Image.new("RGB", img.size, (0, 0, 0))
        gg = ImageDraw.Draw(gl)
        gg.ellipse([W/2-700, H-500, W/2+700, H+400], fill=(120, 30, 5))
        gl = gl.filter(ImageFilter.GaussianBlur(160))
        img = Image.blend(img, gl, 0.85)
        # flash at title hit
        if 0.5 < t < 0.75:
            fa = int(200 * (1 - (t - 0.5) / 0.25))
            fl = Image.new("RGB", img.size, (255, 255, 255))
            img = Image.blend(img, fl, fa / 255 * 0.8)
        if 0.5 < t < 1.3:
            j = int(12 * (1 - (t - 0.5) / 0.8))
            if j:
                img = img.transform(img.size, Image.AFFINE, (1, 0, rng.integers(-j, j), 0, 1, rng.integers(-j, j)))
        # title text
        img = img.convert("RGBA")
        for (txt, tt, size, col) in TL:
            if t < tt: continue
            local = t - tt
            f = font(int(size * min(1.0, 0.6 + local * 3.0)))
            ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(ov)
            bb = d.textbbox((0, 0), txt, font=f)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            a = int(255 * min(1.0, local / 0.25))
            # glow pass
            gl2 = Image.new("RGBA", img.size, (0, 0, 0, 0))
            dg = ImageDraw.Draw(gl2)
            dg.text((W//2 - tw//2 + 4, 560 - th//2 + 4), txt, font=f, fill=(0, 0, 0, a))
            gl2 = gl2.filter(ImageFilter.GaussianBlur(12))
            img = Image.alpha_composite(img, gl2)
            d.text((W//2 - tw//2, 560 - th//2), txt, font=f, fill=(*col, a))
            img = Image.alpha_composite(img, ov)
        img = img.convert("RGB")
        img = post(np.asarray(img), t, [], letter=False)
        push(proc, np.asarray(img))
    finish(proc)
    print("rendered", sh["id"])

def render_endcard(sh):
    dur = sh["end"] - sh["start"]
    proc = enc_start(os.path.join(CLIPS, f"{sh['id']}.mp4"))
    n = int(round(dur * FPS))
    lines = [("FOLLOW", 0.25, 96, (255, 212, 0)),
             ("FOR MORE", 0.55, 96, (255, 255, 255)),
             ("MIND-BLOWING", 0.85, 64, (255, 255, 255)),
             ("DISCOVERIES", 1.15, 64, (255, 255, 255)),
             ("LIKE  •  SHARE  •  FOLLOW", 1.7, 36, (255, 212, 0))]
    for i in range(n):
        t = i / FPS
        arr = np.zeros((H, W, 3), dtype=np.uint8)
        g = np.linspace(6, 14, H, dtype=np.float32)[:, None]
        arr[:] = np.tile(np.concatenate([g * 1.3, g * 0.5, g * 0.35], -1)[:, None, :], (1, W, 1)).astype(np.uint8)
        img = Image.fromarray(arr.astype(np.uint8))
        img = img.convert("RGBA")
        for (txt, tt, size, col) in lines:
            if t < tt: continue
            local = t - tt
            f = font(size)
            ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(ov)
            bb = d.textbbox((0, 0), txt, font=f)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            a = int(255 * min(1.0, local / 0.3))
            y = 640 + lines.index((txt, tt, size, col)) * 130
            d.text((W//2 - tw//2, y - th//2), txt, font=f, fill=(*col, a))
            img = Image.alpha_composite(img, ov)
        img = img.convert("RGB")
        img = post(np.asarray(img), t, [], letter=False)
        push(proc, np.asarray(img))
    finish(proc)
    print("rendered", sh["id"])

# ---------------- video shots (NASA stock) ----------------
def render_video_shot(sh):
    dur = sh["end"] - sh["start"]
    caps = caps_for(sh)
    cmd = [FF, "-loglevel", "error", "-ss", str(sh["vstart"]), "-i", sh["src"], "-t", str(dur),
           "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=rgb24",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    proc = enc_start(os.path.join(CLIPS, f"{sh['id']}.mp4"))
    i = 0
    while True:
        raw = p.stdout.read(W * H * 3)
        if not raw or len(raw) < W * H * 3:
            break
        frame = np.frombuffer(raw, np.uint8).reshape(H, W, 3)
        t = i / FPS
        img = post(frame, t, caps)
        push(proc, np.asarray(img))
        i += 1
    p.wait(); finish(proc)
    print("rendered", sh["id"])

# ---------------- dispatch ----------------
def caps_for(sh):
    """captions overlapping this shot, clamped to the shot window"""
    out = []
    for c in PLAN["captions"]:
        t0 = max(c["t0"], sh["start"])
        t1 = min(c["t1"], sh["end"])
        if t1 - t0 > 0.05:
            out.append({**c, "t0": t0, "t1": t1})
    return out

KIND = {"image": render_image_shot, "proc_asteroid": render_asteroid,
        "proc_impact": render_impact, "proc_ash": render_ash,
        "title": render_title, "endcard": render_endcard, "video": render_video_shot}

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for sh in PLAN["shots"]:
        if only and only not in sh["id"]:
            continue
        out = os.path.join(CLIPS, f"{sh['id']}.mp4")
        if os.path.exists(out):
            print("exists, skip", sh["id"])
            continue
        KIND[sh["kind"]](sh)
    print("all clips done")
