#!/usr/bin/env python3
"""
ANTARCTICA'S HIDDEN EARTHQUAKES — 9:16 cinematic reel builder
Discovery covered Aug 30 - Sep 1, 2026: 362 hidden glacial earthquakes,
245 at Thwaites "Doomsday Glacier" (Geophysical Research Letters).

Pipeline: stills (re-rendered hi-res from copyright-free Pexels/NASA/USGS
reference plates) -> Ken Burns camera -> overlays (animated POINTER system,
pulsing target rings, epicenter dots, seismogram, counters, captions)
-> ffmpeg H.264 + synthesized score + narration mix + SRT.
"""
import math, os, random, subprocess, struct, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
SR = 48000
ROOT = os.path.dirname(os.path.abspath(__file__))
A = lambda *p: os.path.join(ROOT, *p)
OUTDIR = A("deliverables")
os.makedirs(OUTDIR, exist_ok=True)

FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

CYAN   = (110, 235, 255)
ORANGE = (255, 156, 65)
RED    = (255, 92, 92)
WHITE  = (245, 250, 255)

# ---------------------------------------------------------------- utilities
def ease(t, a=3.0):
    t = min(max(t, 0.0), 1.0)
    return t*t*(3-2*t) if a == 3.0 else 1-(1-t)**a

def ease_out(t, p=3.0):
    t = min(max(t, 0.0), 1.0)
    return 1-(1-t)**p

def font(path, size):
    key = (path, size)
    if key not in font.cache:
        font.cache[key] = ImageFont.truetype(path, size)
    return font.cache[key]
font.cache = {}

def probe_dur(path):
    r = subprocess.run(["ffmpeg", "-i", path, "-f", "null", "-"],
                       capture_output=True, text=True)
    import re
    m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    if not m: return 0.0
    h, mn, s = m[-1]
    return int(h)*3600 + int(mn)*60 + float(s)

# ---------------------------------------------------------------- narration
VOICE = [
    ("ant_s01.mp3", "Antarctica just sent us a warning... and for 13 years, nobody heard it."),
    ("ant_s02.mp3", "Hidden in seismic data from the bottom of the world, scientists have just uncovered hundreds of secret earthquakes shaking the frozen continent."),
    ("ant_s03.mp3", "The discovery, published just days ago, reveals 362 hidden glacial quakes between 2010 and 2023."),
    ("ant_s04.mp3", "And 245 of them cluster at one terrifying location — the marine edge of Thwaites... the Doomsday Glacier."),
    ("ant_s05.mp3", "These are no ordinary earthquakes. They strike when icebergs the size of skyscrapers snap off, capsize, and slam into the glacier like battering rams."),
    ("ant_s06.mp3", "The signals are so low in frequency that global sensors missed them for over a decade. It took Antarctica's own seismic stations to finally hear the ice... screaming."),
    ("ant_s07.mp3", "And here's the chilling part. The quakes spiked exactly when Thwaites' floating ice tongue accelerated toward the sea — a sign the ocean itself may be destabilizing the ice."),
    ("ant_s08.mp3", "If Thwaites collapses completely, global sea levels rise by three meters. Entire coastlines... redrawn."),
    ("ant_s09.mp3", "For twenty years, we thought Antarctica was seismically silent. The truth? We just weren't listening."),
    ("ant_s10.mp3", "Now, every capsizing iceberg is a heartbeat we can measure — a countdown we can finally hear. Follow, for more from the edge of the world."),
]
vdur = [probe_dur(A("synth", f)) for f, _ in VOICE]
PRE, GAP, TAIL = 0.45, 0.55, 2.6           # lead-in, inter-scene gap, end tail

# scene schedule
scene_start, t = [], 0.0
for i, d in enumerate(vdur):
    scene_start.append(t)
    t += PRE + d + GAP
TOTAL = t + TAIL
N_FRAMES = int(TOTAL * FPS)
print(f"total {TOTAL:.2f}s  frames {N_FRAMES}")

# ---------------------------------------------------------------- sources
SHOT = {}
def load_shot(name, path):
    im = Image.open(A(path)).convert("RGB")
    scale = 2400 / im.height
    im = im.resize((int(im.width*scale), 2400), Image.LANCZOS)
    SHOT[name] = im

for n, p in {
    "hero":  "assets/antarctica_reel/shot01_iceberg_hero.png",
    "seis":  "assets/antarctica_reel/shot02_seismometer.png",
    "sat":   "assets/antarctica_reel/shot03_thwaites_sat.png",
    "globe": "assets/antarctica_reel/shot04_globe.png",
    "calv":  "assets/antarctica_reel/shot05_calving.png",
    "under": "assets/antarctica_reel/shot06_underwater.png",
    "cliff": "assets/antarctica_reel/shot07_icecliff.png",
    "city":  "assets/antarctica_reel/shot08_city_flood.png",
    "aur":   "assets/antarctica_reel/shot09_aurora.png",
    "peng":  "assets/antarctica_reel/shot10_penguins.png",
}.items():
    load_shot(n, p)

# ---------------------------------------------------------------- camera
class KB:
    """Ken Burns camera: z = zoom (1 = fit-cover), anchor = pan center (u,v in [0,1])."""
    def __init__(self, img, z0, z1, a0, a1):
        self.img, self.z0, self.z1, self.a0, self.a1 = img, z0, z1, a0, a1
        iw, ih = img.size
        self.cover = max(W/iw, H/ih)
    def params(self, p):
        z = self.z0 + (self.z1-self.z0)*ease(p)
        ax = self.a0[0] + (self.a1[0]-self.a0[0])*ease(p)
        ay = self.a0[1] + (self.a1[1]-self.a0[1])*ease(p)
        s = self.cover * z
        cw, ch = W/s, H/s
        iw, ih = self.img.size
        cx = min(max(ax*iw, cw/2), iw-cw/2)
        cy = min(max(ay*ih, ch/2), ih-ch/2)
        return cx, cy, cw, ch, s
    def frame(self, p, shake=(0, 0)):
        cx, cy, cw, ch, s = self.params(p)
        iw, ih = self.img.size
        cx = min(max(cx + shake[0]/s, cw/2), iw-cw/2)
        cy = min(max(cy + shake[1]/s, ch/2), ih-ch/2)
        box = (cx-cw/2, cy-ch/2, cx+cw/2, cy+ch/2)
        return self.img.resize((W, H), Image.BILINEAR, box)
    def project(self, u, v, p):
        """source-normalized (u,v) -> screen xy at progress p"""
        cx, cy, cw, ch, s = self.params(p)
        iw, ih = self.img.size
        return ((u*iw - (cx-cw/2)) * s, (v*ih - (cy-ch/2)) * s)

# ---------------------------------------------------------------- overlays
def glow_layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))

def comp_glow(frame, layer, blur=6, boost=True):
    if boost:
        g = layer.filter(ImageFilter.GaussianBlur(blur))
        frame.alpha_composite(g)
    frame.alpha_composite(layer)

def draw_ring(d, xy, r, color, width, alpha):
    c = (*color, int(alpha))
    d.ellipse([xy[0]-r, xy[1]-r, xy[0]+r, xy[1]+r], outline=c, width=width)

def pulse_rings(layer, xy, tt, color=CYAN, rmax=150, n=2):
    d = ImageDraw.Draw(layer)
    for k in range(n):
        ph = (tt*0.8 + k/n) % 1.0
        draw_ring(d, xy, 26 + ph*rmax, color, max(2, int(8*(1-ph))), 230*(1-ph))

def pointer(layer, xy, tt, t_in, angle_deg, label=None, color=CYAN,
            label_side="auto", small=False):
    """Animated pointer: glowing arrow flies in toward target + pulsing rings + label chip."""
    if tt < t_in: return
    a = ease_out((tt-t_in)/0.6)
    ang = math.radians(angle_deg)
    dist0, dist1 = (330, 120) if not small else (240, 92)
    dist = dist0 + (dist1-dist0)*a + math.sin(tt*2.6)*7
    tipx = xy[0] + math.cos(ang)*(dist*0.28)*(1-a)
    tipy = xy[1] + math.sin(ang)*(dist*0.28)*(1-a)
    tip = (xy[0] + math.cos(ang)*(dist-dist1+34)*0 + math.cos(ang)*34,
           xy[1] + math.sin(ang)*34)
    tail = (xy[0] + math.cos(ang)*dist, xy[1] + math.sin(ang)*dist)
    d = ImageDraw.Draw(layer)
    al = int(255*a)
    # shaft
    d.line([tail, tip], fill=(*color, al), width=7 if not small else 5)
    # arrow head
    hl = 34 if not small else 26
    left = (tip[0] + math.cos(ang+2.6)*hl, tip[1] + math.sin(ang+2.6)*hl)
    right = (tip[0] + math.cos(ang-2.6)*hl, tip[1] + math.sin(ang-2.6)*hl)
    d.polygon([tip, left, right], fill=(*color, al))
    # rings on target
    pulse_rings(layer, xy, tt-t_in, color=color, rmax=130 if not small else 90)
    d.ellipse([xy[0]-7, xy[1]-7, xy[0]+7, xy[1]+7], fill=(*color, al))
    # label chip
    if label and a > 0.55:
        la = int(255*ease((a-0.55)/0.45))
        f = font(FONT_B, 40 if not small else 34)
        tw = d.textlength(label, font=f)
        pad = 18
        lx = tail[0] + math.cos(ang)*30; ly = tail[1] + math.sin(ang)*30
        if label_side == "auto":
            lx = min(max(lx - tw/2, 30), W-30-tw)
        ly = min(max(ly - 30, 90), H-160)
        d.rounded_rectangle([lx-pad, ly-12, lx+tw+pad, ly+52 if not small else ly+46],
                            radius=12, fill=(8, 16, 26, int(0.82*la)),
                            outline=(*color, la), width=2)
        d.text((lx, ly-4), label, font=f, fill=(*WHITE, la))

def seismogram(layer, tt, y0, h, seed=7, active=1.0, color=CYAN):
    """scrolling seismogram strip"""
    d = ImageDraw.Draw(layer)
    d.rectangle([0, y0, W, y0+h], fill=(5, 12, 20, 150))
    rng = np.arange(W)
    xoff = tt*260
    base = np.sin((rng+xoff)*0.05)*3 + np.sin((rng+xoff)*0.013)*5
    quake = np.zeros(W)
    for qx in [0.18, 0.45, 0.62, 0.83, 1.15, 1.5, 1.9, 2.3]:
        cx = qx*W - (xoff % (2.6*W))
        for c in (cx, cx + 2.6*W):
            m = np.abs(rng-c) < 130
            quake[m] += np.exp(-np.abs(rng[m]-c)/38) * 60 * np.sin((rng[m]-c)*0.55)
    sig = (base + quake*active)
    pts = [(int(x), int(y0+h/2+sig[x])) for x in range(0, W, 3)]
    d.line(pts, fill=(*color, 70), width=6)
    d.line(pts, fill=(*color, 235), width=2)
    d.line([0, y0, W, y0], fill=(*color, 60), width=1)
    d.line([0, y0+h, W, y0+h], fill=(*color, 60), width=1)

def counter(layer, tt, t_in, value, label, xy, color=ORANGE, big=110):
    if tt < t_in: return
    a = ease_out((tt-t_in)/0.5)
    cur = int(value * min(1.0, (tt-t_in)/1.4)**0.6)
    d = ImageDraw.Draw(layer)
    f1, f2 = font(FONT_M, big), font(FONT_B, 40)
    txt = f"{cur}"
    tw = d.textlength(txt, font=f1)
    x, y = xy
    al = int(255*a)
    d.text((x-tw/2+4, y+4), txt, font=f1, fill=(0, 0, 0, int(0.6*al)))
    d.text((x-tw/2, y), txt, font=f1, fill=(*color, al))
    lw = d.textlength(label, font=f2)
    d.text((x-lw/2+2, y+big+14+2), label, font=f2, fill=(0, 0, 0, int(0.6*al)))
    d.text((x-lw/2, y+big+14), label, font=f2, fill=(*WHITE, al))

def chip(layer, tt, t_in, text, y, color=CYAN, size=34):
    if tt < t_in: return
    a = ease_out((tt-t_in)/0.5)
    d = ImageDraw.Draw(layer)
    f = font(FONT_B, size)
    tw = d.textlength(text, font=f)
    x = (W-tw)/2
    al = int(255*a)
    d.rounded_rectangle([x-24, y-14, x+tw+24, y+size+18], radius=14,
                        fill=(8, 16, 26, int(0.8*al)), outline=(*color, al), width=2)
    d.text((x, y), text, font=f, fill=(*color, al))

# snow
random.seed(4)
SNOW = [(random.random(), random.random(), random.uniform(0.35, 1.0),
         random.uniform(1.6, 4.4)) for _ in range(130)]
def snowfall(layer, tt, wind=40, amount=1.0):
    d = ImageDraw.Draw(layer)
    n = int(len(SNOW)*amount)
    for (sx, sy, depth, r) in SNOW[:n]:
        y = (sy*H + tt*(90+220*depth)) % (H+40) - 20
        x = (sx*W + tt*wind*depth + math.sin(tt*1.7 + sy*9)*24*depth) % (W+40) - 20
        al = int(150*depth)
        rr = r*depth*1.6
        d.ellipse([x-rr, y-rr, x+rr, y+rr], fill=(255, 255, 255, al))

# ---------------------------------------------------------------- captions
def chunks_for(text):
    words = text.replace("—", "—").split()
    out, cur = [], []
    for w in words:
        cur.append(w)
        if sum(len(x)+1 for x in cur) > 17 or w.endswith((".", "?", "…")):
            out.append(" ".join(cur)); cur = []
    if cur: out.append(" ".join(cur))
    return out

HOTWORDS = {"warning", "13", "362", "245", "2010", "2023", "thwaites", "thwaites'",
            "doomsday", "glacier.", "earthquakes", "quakes", "capsize,", "screaming.",
            "three", "meters.", "redrawn.", "silent.", "listening.", "accelerated",
            "destabilizing", "heartbeat", "countdown", "secret", "skyscrapers"}

def draw_caption(frame, text, prog):
    ch = chunks_for(text)
    weights = [len(c) for c in ch]
    totw = sum(weights)
    acc, idx, loc = 0, 0, 0.0
    for i, wt in enumerate(weights):
        if prog*totw <= acc+wt or i == len(ch)-1:
            idx = i; loc = (prog*totw - acc)/wt if wt else 0
            break
        acc += wt
    cur = ch[idx]
    pop = 1.0 + 0.06*(1-ease(min(1, loc*3)))
    f = font(FONT_B, int(58*pop))
    d = ImageDraw.Draw(frame)
    words = cur.upper().split()
    widths = [d.textlength(w+" ", font=f) for w in words]
    tw = sum(widths)
    x = (W-tw)/2; y = 1565
    d.rounded_rectangle([x-28, y-18, x+tw+18, y+80], radius=16, fill=(4, 10, 18, 175))
    for w, wd in zip(words, widths):
        key = w.lower().strip(",…")
        col = ORANGE if key in HOTWORDS else WHITE
        d.text((x+2, y+3), w, font=f, fill=(0, 0, 0, 200))
        d.text((x, y), w, font=f, fill=col)
        x += wd

# ---------------------------------------------------------------- grade
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
r = np.sqrt(((xx-W/2)/(W/2))**2 + ((yy-H*0.46)/(H/2))**2)
VIGNETTE = np.clip(1.15 - 0.42*r**2.1, 0.45, 1.0)[..., None].astype(np.float32)
rng_g = np.random.default_rng(11)
GRAIN = [rng_g.normal(0, 5.0, (H//2, W//2, 1)).astype(np.float32) for _ in range(12)]

def grade(arr, fi, cold=1.0):
    a = arr.astype(np.float32)
    # cold cinematic: lift shadows blue, teal mids, protect highlights
    a[..., 2] *= (1 + 0.055*cold)
    a[..., 1] *= (1 + 0.018*cold)
    a[..., 0] *= (1 - 0.028*cold)
    a = 255.0 * (a/255.0) ** 0.96
    a *= VIGNETTE
    g = GRAIN[fi % len(GRAIN)]
    g2 = np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)[:H, :W]
    a += g2
    return np.clip(a, 0, 255).astype(np.uint8)


_WM = None
def watermark(frame):
    global _WM
    if _WM is None:
        from PIL import Image as _I
        _WM = _I.open(A("assets", "brand", "watermark_1080x1920.png")).convert("RGBA")
    frame.alpha_composite(_WM)

def letterbox(frame):
    d = ImageDraw.Draw(frame)
    d.rectangle([0, 0, W, 88], fill=(2, 5, 9, 255))
    d.rectangle([0, H-88, W, H], fill=(2, 5, 9, 255))

# ---------------------------------------------------------------- scenes
SC = []
def add(i, img, z0, z1, a0, a1, fx=None, cold=1.0, shake=0.0):
    SC.append(dict(i=i, kb=KB(SHOT[img], z0, z1, a0, a1), fx=fx or [],
                   cold=cold, shake=shake,
                   t0=scene_start[i], dur=PRE+vdur[i]+GAP))

# S1 hook — hero iceberg
def fx_title(fr, layer, kb, tt, p):
    if tt < 1.0: al = ease_out(tt/1.0)
    else: al = 1.0
    d = ImageDraw.Draw(layer)
    def fit(txt, size):
        f = font(FONT_B, size)
        while d.textlength(txt, font=f) > W-90 and size > 40:
            size -= 2; f = font(FONT_B, size)
        return f
    t1, t2 = "ANTARCTICA'S", "HIDDEN EARTHQUAKES"
    for i, (txt, y) in enumerate([(t1, 210), (t2, 315)]):
        f = fit(txt, 92)
        tw = d.textlength(txt, font=f)
        d.text(((W-tw)/2+3, y+3), txt, font=f, fill=(0, 0, 0, int(190*al)))
        d.text(((W-tw)/2, y), txt, font=f,
               fill=(*WHITE, int(255*al)) if i == 0 else (*CYAN, int(255*al)))
    chip(layer, tt, 0.7, "NEW DISCOVERY  •  PUBLISHED THIS WEEK", 445, color=ORANGE)
add(0, "hero", 1.06, 1.18, (0.5, 0.55), (0.5, 0.42), fx=[fx_title], cold=1.2)

# S2 seismometer + seismogram + pointer at the station
def fx_seis(fr, layer, kb, tt, p):
    seismogram(layer, tt, 1180, 190, active=min(1.0, tt/2))
    x, y = kb.project(0.52, 0.60, p)
    pointer(layer, (x, y), tt, 1.6, -130, label="SEISMIC STATION", color=CYAN)
    snowfall(layer, tt, amount=0.8)
add(1, "seis", 1.03, 1.16, (0.5, 0.52), (0.52, 0.58), fx=[fx_seis], cold=1.1)

# S3 thwaites satellite + epicenter dots + 362 counter
random.seed(21)
EPIC = [(random.gauss(0.47, 0.13), random.gauss(0.42, 0.10)) for _ in range(80)]
def fx_epic(fr, layer, kb, tt, p):
    d = ImageDraw.Draw(layer)
    n = int(min(1.0, max(0, tt-0.8)/3.2) * len(EPIC))
    for k in range(n):
        u, v = EPIC[k]
        x, y = kb.project(u, v, p)
        if not (0 < x < W and 0 < y < H): continue
        age = tt - (0.8 + 3.2*k/len(EPIC))
        fl = max(0.0, 1-age*1.5)
        rr = 5 + 26*fl
        d.ellipse([x-rr, y-rr, x+rr, y+rr], outline=(*RED, int(200*max(fl, 0.12))), width=2)
        d.ellipse([x-4, y-4, x+4, y+4], fill=(*RED, 220))
    counter(layer, tt, 1.2, 362, "HIDDEN GLACIAL QUAKES  •  2010–2023", (W/2, 240), color=RED)
add(2, "sat", 1.02, 1.22, (0.5, 0.42), (0.46, 0.5), fx=[fx_epic], cold=0.8, shake=2.0)

# S4 globe + POINTER to Thwaites
def fx_globe(fr, layer, kb, tt, p):
    tx, ty = kb.project(0.375, 0.545, p)     # Amundsen coast / Thwaites
    d = ImageDraw.Draw(layer)
    # cluster of quake dots around Thwaites
    random.seed(5)
    n = int(min(1.0, max(0, tt-1.2)/2.0)*26)
    for k in range(n):
        ang = random.random()*6.28; rr = random.random()*34
        d.ellipse([tx+math.cos(ang)*rr-3, ty+math.sin(ang)*rr-3,
                   tx+math.cos(ang)*rr+3, ty+math.sin(ang)*rr+3], fill=(*RED, 210))
    pointer(layer, (tx, ty), tt, 0.9, -35, label="THWAITES — “DOOMSDAY GLACIER”", color=ORANGE)
    counter(layer, tt, 2.2, 245, "QUAKES AT ITS MARINE EDGE", (W/2, 1310), color=ORANGE, big=100)
add(3, "globe", 1.0, 1.30, (0.5, 0.52), (0.42, 0.55), fx=[fx_globe], cold=0.6)

# S5 calving + impact shake + circle target on the slab
def fx_calv(fr, layer, kb, tt, p):
    x, y = kb.project(0.55, 0.42, p)
    pointer(layer, (x, y), tt, 1.1, -150, label="ICEBERG CAPSIZING", color=CYAN, small=True)
    seismogram(layer, tt*1.4, 1235, 150, active=1.4, color=RED)
    chip(layer, tt, 3.2, "EACH IMPACT = ONE GLACIAL EARTHQUAKE", 1120, color=RED, size=30)
add(4, "calv", 1.05, 1.22, (0.52, 0.40), (0.5, 0.52), fx=[fx_calv], cold=0.9, shake=9.0)

# S6 underwater + low-frequency label
def fx_under(fr, layer, kb, tt, p):
    seismogram(layer, tt*0.5, 1210, 170, active=0.6)
    chip(layer, tt, 0.9, "LOW-FREQUENCY  •  INVISIBLE TO GLOBAL SENSORS", 1130, color=CYAN, size=29)
    x, y = kb.project(0.5, 0.62, p)
    pointer(layer, (x, y), tt, 4.5, -120, label="ANTARCTIC STATIONS HEARD IT", color=ORANGE, small=True)
add(5, "under", 1.16, 1.02, (0.5, 0.6), (0.5, 0.45), fx=[fx_under], cold=1.25)

# S7 ice cliff + flow arrows seaward
def fx_flow(fr, layer, kb, tt, p):
    d = ImageDraw.Draw(layer)
    for k, (u, v) in enumerate([(0.40, 0.30), (0.58, 0.24), (0.50, 0.38)]):
        x, y = kb.project(u, v, p)
        drift = ((tt*0.35 + k*0.33) % 1.0)
        al = int(220 * math.sin(drift*math.pi))
        yy2 = y + drift*130
        d.line([x, yy2-70, x, yy2], fill=(*CYAN, al), width=6)
        d.polygon([(x, yy2+22), (x-16, yy2-2), (x+16, yy2-2)], fill=(*CYAN, al))
    chip(layer, tt, 1.2, "ICE TONGUE ACCELERATING TOWARD THE SEA", 300, color=CYAN, size=31)
    x, y = kb.project(0.5, 0.52, p)
    pointer(layer, (x, y), tt, 5.6, -40, label="OCEAN EATING THE ICE", color=RED, small=True)
add(6, "cliff", 1.03, 1.2, (0.5, 0.3), (0.5, 0.5), fx=[fx_flow], cold=1.0, shake=2.5)

# S8 city + rising sea level line
def fx_sea(fr, layer, kb, tt, p):
    d = ImageDraw.Draw(layer)
    a = ease(min(1.0, max(0.0, (tt-1.0)/3.5)))
    y = 1500 - a*430
    for x in range(0, W, 44):
        d.line([x, y, x+24, y], fill=(*CYAN, 235), width=5)
    d.rectangle([0, y, W, H], fill=(80, 190, 235, int(40+30*a)))
    pointer(layer, (W-190, y), tt, 1.4, -125, label="+3 M SEA LEVEL", color=RED)
add(7, "city", 1.02, 1.14, (0.5, 0.5), (0.5, 0.44), fx=[fx_sea], cold=0.5)

# S9 penguins quiet
def fx_quiet(fr, layer, kb, tt, p):
    snowfall(layer, tt, wind=25, amount=0.55)
    chip(layer, tt, 2.6, "WE JUST WEREN'T LISTENING", 300, color=WHITE, size=34)
add(8, "peng", 1.15, 1.02, (0.5, 0.5), (0.5, 0.46), fx=[fx_quiet], cold=0.7)

# S10 aurora CTA
def fx_cta(fr, layer, kb, tt, p):
    seismogram(layer, tt*0.8, 1235, 130, active=0.5)
    d = ImageDraw.Draw(layer)
    if tt > 3.4:
        a = ease_out((tt-3.4)/0.7)
        f = font(FONT_B, 66)
        txt = "FOLLOW  FOR  MORE"
        tw = d.textlength(txt, font=f)
        d.text(((W-tw)/2+3, 273), txt, font=f, fill=(0, 0, 0, int(190*a)))
        d.text(((W-tw)/2, 270), txt, font=f, fill=(*CYAN, int(255*a)))
        f2 = font(FONT_R, 27)
        src = "Source: Geophysical Research Letters — Pham (ANU), Aug 2026"
        tw2 = d.textlength(src, font=f2)
        d.text(((W-tw2)/2, 372), src, font=f2, fill=(*WHITE, int(200*a)))
add(9, "aur", 1.0, 1.18, (0.5, 0.55), (0.5, 0.4), fx=[fx_cta], cold=0.55)

# ---------------------------------------------------------------- audio
def decode(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)

def build_audio():
    n = int(TOTAL*SR)
    tt = np.arange(n)/SR
    rng = np.random.default_rng(3)

    # --- wind bed
    noise = rng.normal(0, 1, n).astype(np.float32)
    S = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1/SR)
    S *= np.exp(-freqs/420)
    wind = np.fft.irfft(S, n).astype(np.float32)
    wind /= np.abs(wind).max()+1e-9
    wind *= 0.16*(0.65+0.35*np.sin(2*np.pi*tt/13+1.2))

    # --- drone
    drone = np.zeros(n, dtype=np.float32)
    for f0, g in [(55, .5), (55.35, .4), (110, .30), (164.8, .16), (220, .08)]:
        drone += g*np.sin(2*np.pi*f0*tt + 0.6*np.sin(2*np.pi*0.07*tt)).astype(np.float32)
    drone *= 0.11*(0.75+0.25*np.sin(2*np.pi*tt/21))

    # --- slow sub pulse (heartbeat, grows through video)
    pulse = np.zeros(n, dtype=np.float32)
    beat = 2.0
    k = int(0.5*SR)
    kern = (np.sin(2*np.pi*48*np.arange(k)/SR)*np.exp(-np.arange(k)/(0.10*SR))).astype(np.float32)
    for b in np.arange(scene_start[2], TOTAL-1, beat):
        i0 = int(b*SR)
        g = 0.25 + 0.65*(b/TOTAL)
        pulse[i0:i0+k] += kern[:max(0, min(k, n-i0))]*g*0.5

    # --- transition booms + rumbles
    sfx = np.zeros(n, dtype=np.float32)
    kb_len = int(1.6*SR)
    tb = np.arange(kb_len)/SR
    boom = (np.sin(2*np.pi*42*tb)*np.exp(-tb/0.35) +
            0.4*np.sin(2*np.pi*30*tb)*np.exp(-tb/0.6)).astype(np.float32)
    for i, s in enumerate(scene_start):
        i0 = int(s*SR)
        g = 0.85 if i in (3, 4, 7) else 0.5
        seg = boom*g
        sfx[i0:i0+kb_len] += seg[:max(0, min(kb_len, n-i0))]
    # calving rumble
    r0 = int(scene_start[4]*SR); r1 = int((scene_start[4]+6)*SR)
    rum = rng.normal(0, 1, r1-r0).astype(np.float32)
    Sr = np.fft.rfft(rum); fr = np.fft.rfftfreq(r1-r0, 1/SR)
    Sr *= np.exp(-fr/90)
    rum = np.fft.irfft(Sr, r1-r0).astype(np.float32)
    rum /= np.abs(rum).max()+1e-9
    env = np.sin(np.linspace(0, np.pi, r1-r0))**0.7
    sfx[r0:r1] += rum*env*0.5

    bgm = wind + drone + pulse + sfx

    # --- voice track
    voice = np.zeros(n, dtype=np.float32)
    for i, (f, _) in enumerate(VOICE):
        v = decode(A("synth", f))
        i0 = int((scene_start[i]+PRE)*SR)
        voice[i0:i0+len(v)] += v[:max(0, min(len(v), n-i0))]
    voice *= 0.95

    # --- duck bgm under voice
    env = np.abs(voice)
    k2 = int(0.20*SR)
    ker = np.ones(k2, dtype=np.float32)/k2
    env = np.convolve(env, ker, mode="same")
    duck = 1.0/(1.0 + 6.5*env)
    mix = bgm*duck*0.9 + voice

    # fades + master
    fade = int(1.4*SR)
    mix[:int(0.3*SR)] *= np.linspace(0, 1, int(0.3*SR))
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix = np.tanh(mix*1.15)*0.92
    peak = np.abs(mix).max()
    if peak > 0.98: mix *= 0.98/peak

    pcm = (mix*32767).astype(np.int16)
    with open(A("synth", "ant_mix.wav"), "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", 36+len(pcm)*2) + b"WAVEfmt " +
                struct.pack("<IHHIIHH", 16, 1, 1, SR, SR*2, 2, 16) +
                b"data" + struct.pack("<I", len(pcm)*2))
        f.write(pcm.tobytes())
    print("audio written")

# ---------------------------------------------------------------- srt
def fmt_ts(x):
    ms = int((x-int(x))*1000)
    s = int(x)
    return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d},{ms:03d}"

def build_srt():
    lines = []
    for i, (_, txt) in enumerate(VOICE):
        a = scene_start[i]+PRE
        b = a+vdur[i]
        lines.append(f"{i+1}\n{fmt_ts(a)} --> {fmt_ts(b)}\n{txt}\n")
    with open(os.path.join(OUTDIR, "antarctica_hidden_quakes_reel.srt"), "w") as f:
        f.write("\n".join(lines))

# ---------------------------------------------------------------- render
def render():
    vp = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", A("synth", "ant_mix.wav"),
         "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-c:a", "aac", "-b:a", "192k", "-shortest",
         os.path.join(OUTDIR, "antarctica_hidden_quakes_reel.mp4")],
        stdin=subprocess.PIPE)

    XFADE = 0.55
    for fi in range(N_FRAMES):
        gt = fi/FPS
        # find scene
        si = len(SC)-1
        for i, sc in enumerate(SC):
            if gt < sc["t0"]+sc["dur"]: si = i; break
        sc = SC[si]
        tt = gt - sc["t0"]
        p = min(1.0, tt/sc["dur"])

        shk = (0.0, 0.0)
        if sc["shake"] > 0:
            m = sc["shake"]
            if si == 4:
                m *= (1.0 + 2.4*math.exp(-abs(tt-1.6)*1.8))
            shk = (m*math.sin(gt*23.7)+m*0.5*math.sin(gt*41.3),
                   m*math.sin(gt*19.1+2)+m*0.5*math.sin(gt*37.7))

        base = sc["kb"].frame(p, shk)
        arr = grade(np.asarray(base), fi, sc["cold"])
        frame = Image.fromarray(arr).convert("RGBA")

        layer = glow_layer()
        for fx in sc["fx"]:
            fx(frame, layer, sc["kb"], tt, p)
        comp_glow(frame, layer)

        # caption
        va, vb = PRE, PRE+vdur[sc["i"]]
        if va <= tt <= vb:
            draw_caption(frame, VOICE[sc["i"]][1], (tt-va)/(vb-va))

        letterbox(frame)
        watermark(frame)
        # progress bar
        d = ImageDraw.Draw(frame)
        d.rectangle([0, 84, int(W*gt/TOTAL), 88], fill=(*CYAN, 255))

        # crossfade between scenes
        nt = sc["t0"]+sc["dur"]
        if si+1 < len(SC) and nt-gt < XFADE:
            pass  # simple cut with boom; cheaper & punchier

        # global fade in/out
        fade = 1.0
        if gt < 0.6: fade = gt/0.6
        if TOTAL-gt < 1.2: fade = max(0.0, (TOTAL-gt)/1.2)
        out = np.asarray(frame.convert("RGB"))
        if fade < 1.0:
            out = (out.astype(np.float32)*fade).astype(np.uint8)

        vp.stdin.write(out.tobytes())
        if fi % 300 == 0:
            print(f"frame {fi}/{N_FRAMES} ({100*fi/N_FRAMES:.0f}%)")
    vp.stdin.close()
    vp.wait()
    print("video done:", vp.returncode)

if __name__ == "__main__":
    build_audio()
    build_srt()
    render()
    man = dict(
        title="Antarctica's Hidden Earthquakes — the Doomsday Glacier is speaking",
        duration_s=round(TOTAL, 2), resolution=f"{W}x{H}", fps=FPS,
        discovery="362 hidden glacial earthquakes (2010-2023), 245 at Thwaites marine edge",
        source_paper="Geophysical Research Letters — Thanh-Son Pham (ANU); The Conversation/ScienceDaily Aug 30-31 2026; ScienceBlog Sep 1 2026",
        visual_sources="Copyright-free reference plates: Pexels (icebergs, penguins), NASA (Thwaites satellite/OIB), USGS-Google Earth (Antarctica globe); re-rendered hi-res; overlays/pointer/seismograms coded in Python (numpy+PIL+ffmpeg)",
    )
    with open(os.path.join(OUTDIR, "antarctica_hidden_quakes_manifest.json"), "w") as f:
        json.dump(man, f, indent=2)
    print("manifest written")
