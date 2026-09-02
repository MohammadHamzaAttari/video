#!/usr/bin/env python3
"""
WHY ANTARCTICA FROZE FIRST — mantle waves discovery (Science, Aug 2026)
9:16 cinematic reel #2. Engine shared with build_antarctica_quakes.py.
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
MAGMA  = (255, 120, 40)
WHITE  = (245, 250, 255)

def ease(t):
    t = min(max(t, 0.0), 1.0)
    return t*t*(3-2*t)

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

VOICE = [
    ("man_s01.mp3", "Here's a mystery that haunted science for decades: Antarctica froze 25 million years before the Arctic. Now... we finally know why."),
    ("man_s02.mp3", "34 million years ago, Earth was five degrees warmer than today. Lush forests grew near the poles. And yet Antarctica turned to ice. That should have been impossible."),
    ("man_s03.mp3", "The answer, just published in the journal Science, lies deep beneath your feet — slow-motion waves rolling through the Earth's mantle."),
    ("man_s04.mp3", "As ancient supercontinents tore apart, these mantle waves crept beneath East Antarctica, stripping dense rock from under the plate and pushing the land upward."),
    ("man_s05.mp3", "They raised a colossal escarpment two kilometers high, and lifted the Gamburtsev Mountains — an entire alpine range now buried under three kilometers of ice."),
    ("man_s06.mp3", "And high altitude means cold. On those rising peaks, snow survived the summers of a greenhouse world... and the first glaciers were born."),
    ("man_s07.mp3", "Then came the feedback loop. The young ice acted like a planetary mirror, bouncing sunlight back into space — cooling the entire globe by a full degree."),
    ("man_s08.mp3", "The Arctic? Its lands simply sat too low. No mountains, no altitude, no ice — for another 25 million years."),
    ("man_s09.mp3", "The implication is mind-blowing: ice ages aren't just written in the sky. They are born deep inside the Earth."),
    ("man_s10.mp3", "Today that same ice locks away 52 meters of sea level rise. Understanding how it was born may help us predict how it dies. Follow for more secrets of the deep Earth."),
]
vdur = [probe_dur(A("synth", f)) for f, _ in VOICE]
PRE, GAP, TAIL = 0.45, 0.55, 2.6
scene_start, t = [], 0.0
for d in vdur:
    scene_start.append(t)
    t += PRE + d + GAP
TOTAL = t + TAIL
N_FRAMES = int(TOTAL*FPS)
print(f"total {TOTAL:.2f}s frames {N_FRAMES}")

SHOT = {}
def load_shot(name, path):
    im = Image.open(A(path)).convert("RGB")
    scale = 2400/im.height
    SHOT[name] = im.resize((int(im.width*scale), 2400), Image.LANCZOS)

for n, p in {
    "hero":   "assets/antarctica_mantle/m01_hero.png",
    "warm":   "assets/antarctica_mantle/m02_warmworld.png",
    "mantle": "assets/antarctica_mantle/m03_mantle.png",
    "escarp": "assets/antarctica_mantle/m04_escarpment.png",
    "buried": "assets/antarctica_mantle/m05_buried.png",
    "peaks":  "assets/antarctica_mantle/m06_peaks.png",
    "albedo": "assets/antarctica_mantle/m07_albedo.png",
    "tundra": "assets/antarctica_mantle/m08_tundra.png",
    "aur":    "assets/antarctica_reel/shot09_aurora.png",
}.items():
    load_shot(n, p)

class KB:
    def __init__(self, img, z0, z1, a0, a1):
        self.img, self.z0, self.z1, self.a0, self.a1 = img, z0, z1, a0, a1
        iw, ih = img.size
        self.cover = max(W/iw, H/ih)
    def params(self, p):
        z = self.z0 + (self.z1-self.z0)*ease(p)
        ax = self.a0[0] + (self.a1[0]-self.a0[0])*ease(p)
        ay = self.a0[1] + (self.a1[1]-self.a0[1])*ease(p)
        s = self.cover*z
        cw, ch = W/s, H/s
        iw, ih = self.img.size
        cx = min(max(ax*iw, cw/2), iw-cw/2)
        cy = min(max(ay*ih, ch/2), ih-ch/2)
        return cx, cy, cw, ch, s
    def frame(self, p, shake=(0, 0)):
        cx, cy, cw, ch, s = self.params(p)
        iw, ih = self.img.size
        cx = min(max(cx+shake[0]/s, cw/2), iw-cw/2)
        cy = min(max(cy+shake[1]/s, ch/2), ih-ch/2)
        return self.img.resize((W, H), Image.BILINEAR,
                               (cx-cw/2, cy-ch/2, cx+cw/2, cy+ch/2))
    def project(self, u, v, p):
        cx, cy, cw, ch, s = self.params(p)
        iw, ih = self.img.size
        return ((u*iw-(cx-cw/2))*s, (v*ih-(cy-ch/2))*s)

def glow_layer():
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))

def comp_glow(frame, layer, blur=6):
    frame.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))
    frame.alpha_composite(layer)

def pulse_rings(layer, xy, tt, color=CYAN, rmax=150, n=2):
    d = ImageDraw.Draw(layer)
    for k in range(n):
        ph = (tt*0.8 + k/n) % 1.0
        r = 26 + ph*rmax
        d.ellipse([xy[0]-r, xy[1]-r, xy[0]+r, xy[1]+r],
                  outline=(*color, int(230*(1-ph))), width=max(2, int(8*(1-ph))))

def pointer(layer, xy, tt, t_in, angle_deg, label=None, color=CYAN, small=False):
    if tt < t_in: return
    a = ease_out((tt-t_in)/0.6)
    ang = math.radians(angle_deg)
    dist0, dist1 = (330, 120) if not small else (240, 92)
    dist = dist0 + (dist1-dist0)*a + math.sin(tt*2.6)*7
    tip = (xy[0]+math.cos(ang)*34, xy[1]+math.sin(ang)*34)
    tail = (xy[0]+math.cos(ang)*dist, xy[1]+math.sin(ang)*dist)
    d = ImageDraw.Draw(layer)
    al = int(255*a)
    d.line([tail, tip], fill=(*color, al), width=7 if not small else 5)
    hl = 34 if not small else 26
    left = (tip[0]+math.cos(ang+2.6)*hl, tip[1]+math.sin(ang+2.6)*hl)
    right = (tip[0]+math.cos(ang-2.6)*hl, tip[1]+math.sin(ang-2.6)*hl)
    d.polygon([tip, left, right], fill=(*color, al))
    pulse_rings(layer, xy, tt-t_in, color=color, rmax=130 if not small else 90)
    d.ellipse([xy[0]-7, xy[1]-7, xy[0]+7, xy[1]+7], fill=(*color, al))
    if label and a > 0.55:
        la = int(255*ease((a-0.55)/0.45))
        f = font(FONT_B, 40 if not small else 34)
        tw = d.textlength(label, font=f)
        pad = 18
        lx = tail[0]+math.cos(ang)*30; ly = tail[1]+math.sin(ang)*30
        lx = min(max(lx-tw/2, 30), W-30-tw)
        ly = min(max(ly-30, 90), H-160)
        d.rounded_rectangle([lx-pad, ly-12, lx+tw+pad, ly+(52 if not small else 46)],
                            radius=12, fill=(8, 16, 26, int(0.82*la)),
                            outline=(*color, la), width=2)
        d.text((lx, ly-4), label, font=f, fill=(*WHITE, la))

def counter(layer, tt, t_in, value, label, xy, color=ORANGE, big=110, suffix=""):
    if tt < t_in: return
    a = ease_out((tt-t_in)/0.5)
    cur = int(value*min(1.0, (tt-t_in)/1.4)**0.6)
    d = ImageDraw.Draw(layer)
    f1, f2 = font(FONT_M, big), font(FONT_B, 40)
    txt = f"{cur}{suffix}"
    tw = d.textlength(txt, font=f1)
    x, y = xy
    al = int(255*a)
    d.text((x-tw/2+4, y+4), txt, font=f1, fill=(0, 0, 0, int(0.6*al)))
    d.text((x-tw/2, y), txt, font=f1, fill=(*color, al))
    lw = d.textlength(label, font=f2)
    d.text((x-lw/2+2, y+big+16), label, font=f2, fill=(0, 0, 0, int(0.6*al)))
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

random.seed(4)
SNOW = [(random.random(), random.random(), random.uniform(0.35, 1.0),
         random.uniform(1.6, 4.4)) for _ in range(130)]
def snowfall(layer, tt, wind=40, amount=1.0):
    d = ImageDraw.Draw(layer)
    for (sx, sy, depth, r) in SNOW[:int(len(SNOW)*amount)]:
        y = (sy*H + tt*(90+220*depth)) % (H+40) - 20
        x = (sx*W + tt*wind*depth + math.sin(tt*1.7+sy*9)*24*depth) % (W+40) - 20
        rr = r*depth*1.6
        d.ellipse([x-rr, y-rr, x+rr, y+rr], fill=(255, 255, 255, int(150*depth)))

def mantle_wave(layer, tt, y_c, amp=46, color=MAGMA):
    """traveling glowing wave through the mantle"""
    d = ImageDraw.Draw(layer)
    pts = []
    for x in range(0, W+8, 8):
        ph = x*0.011 - tt*2.2
        y = y_c + math.sin(ph)*amp + math.sin(ph*0.37+1.3)*amp*0.4
        pts.append((x, y))
    d.line(pts, fill=(*color, 70), width=16)
    d.line(pts, fill=(*color, 200), width=5)
    # crest particles
    for k in range(7):
        cx = ((tt*190 + k*W/7) % (W+60)) - 30
        ph = cx*0.011 - tt*2.2
        cy = y_c + math.sin(ph)*amp + math.sin(ph*0.37+1.3)*amp*0.4
        d.ellipse([cx-6, cy-6, cx+6, cy+6], fill=(255, 200, 120, 220))

def uplift_arrows(layer, kb, tt, p, anchors, color=ORANGE):
    d = ImageDraw.Draw(layer)
    for k, (u, v) in enumerate(anchors):
        x, y = kb.project(u, v, p)
        drift = ((tt*0.35 + k*0.29) % 1.0)
        al = int(230*math.sin(drift*math.pi))
        yy = y - drift*150
        d.line([x, yy+80, x, yy], fill=(*color, al), width=7)
        d.polygon([(x, yy-26), (x-18, yy+2), (x+18, yy+2)], fill=(*color, al))

def sun_rays(layer, tt, origin, n=9):
    d = ImageDraw.Draw(layer)
    ox, oy = origin
    for k in range(n):
        ang = math.pi*(0.15 + 0.7*k/(n-1)) + math.sin(tt*0.7+k)*0.02
        al = int(60 + 45*math.sin(tt*1.3 + k*1.7)**2)
        ex = ox - math.cos(ang)*2400; ey = oy - math.sin(ang)*2400
        d.line([ox, oy, ex, ey], fill=(255, 250, 225, al), width=26)

def chunks_for(text):
    words = text.split()
    out, cur = [], []
    for w in words:
        cur.append(w)
        if sum(len(x)+1 for x in cur) > 17 or w.endswith((".", "?", "…")):
            out.append(" ".join(cur)); cur = []
    if cur: out.append(" ".join(cur))
    return out

HOTWORDS = {"25", "34", "five", "impossible.", "science,", "mantle.", "waves",
            "upward.", "escarpment", "gamburtsev", "mountains", "buried", "ice.",
            "glaciers", "born.", "mirror,", "degree.", "low.", "earth.", "52",
            "dies.", "altitude,", "cold.", "warmer", "frozen", "froze"}

def draw_caption(frame, text, prog):
    ch = chunks_for(text)
    weights = [len(c) for c in ch]
    totw = sum(weights)
    acc, idx, loc = 0, 0, 0.0
    for i, wt in enumerate(weights):
        if prog*totw <= acc+wt or i == len(ch)-1:
            idx = i; loc = (prog*totw-acc)/wt if wt else 0
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
        col = ORANGE if w.lower().strip(",…—") in HOTWORDS else WHITE
        d.text((x+2, y+3), w, font=f, fill=(0, 0, 0, 200))
        d.text((x, y), w, font=f, fill=col)
        x += wd

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
r = np.sqrt(((xx-W/2)/(W/2))**2 + ((yy-H*0.46)/(H/2))**2)
VIGNETTE = np.clip(1.15-0.42*r**2.1, 0.45, 1.0)[..., None].astype(np.float32)
rng_g = np.random.default_rng(11)
GRAIN = [rng_g.normal(0, 3.4, (H//2, W//2, 1)).astype(np.float32) for _ in range(12)]

def grade(arr, fi, cold=1.0):
    a = arr.astype(np.float32)
    a[..., 2] *= (1+0.055*cold)
    a[..., 1] *= (1+0.018*cold)
    a[..., 0] *= (1-0.028*cold)
    a = 255.0*(a/255.0)**0.96
    a *= VIGNETTE
    g = GRAIN[fi % len(GRAIN)]
    a += np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)[:H, :W]
    return np.clip(a, 0, 255).astype(np.uint8)

def letterbox(frame):
    d = ImageDraw.Draw(frame)
    d.rectangle([0, 0, W, 88], fill=(2, 5, 9, 255))
    d.rectangle([0, H-88, W, H], fill=(2, 5, 9, 255))

# ------------------------------------------------------------------ scenes
SC = []
def add(i, img, z0, z1, a0, a1, fx=None, cold=1.0, shake=0.0):
    SC.append(dict(i=i, kb=KB(SHOT[img], z0, z1, a0, a1), fx=fx or [],
                   cold=cold, shake=shake, t0=scene_start[i], dur=PRE+vdur[i]+GAP))

def fx_title(fr, layer, kb, tt, p):
    al = ease_out(tt/1.0) if tt < 1.0 else 1.0
    d = ImageDraw.Draw(layer)
    def fit(txt, size):
        f = font(FONT_B, size)
        while d.textlength(txt, font=f) > W-90 and size > 40:
            size -= 2; f = font(FONT_B, size)
        return f
    for i, (txt, y) in enumerate([("WHY ANTARCTICA", 200), ("FROZE  FIRST", 305)]):
        f = fit(txt, 96)
        tw = d.textlength(txt, font=f)
        d.text(((W-tw)/2+3, y+3), txt, font=f, fill=(0, 0, 0, int(190*al)))
        d.text(((W-tw)/2, y), txt, font=f,
               fill=(*WHITE, int(255*al)) if i == 0 else (*CYAN, int(255*al)))
    chip(layer, tt, 0.7, "NEW STUDY  •  JOURNAL: SCIENCE", 440, color=ORANGE)
    snowfall(layer, tt, amount=0.5)
add(0, "hero", 1.05, 1.2, (0.5, 0.6), (0.5, 0.42), fx=[fx_title], cold=1.15)

def fx_warm(fr, layer, kb, tt, p):
    counter(layer, tt, 1.0, 34, "MILLION YEARS AGO", (W/2, 230), color=ORANGE)
    chip(layer, tt, 3.2, "EARTH: +5°C WARMER THAN TODAY", 1150, color=ORANGE, size=32)
add(1, "warm", 1.02, 1.18, (0.5, 0.45), (0.5, 0.55), fx=[fx_warm], cold=-0.5)

def fx_mantle(fr, layer, kb, tt, p):
    x, y = kb.project(0.5, 0.52, p)
    mantle_wave(layer, tt, y, amp=44)
    pointer(layer, ((x+140+80*math.sin(tt*0.8)), y-30), tt, 1.6, -60,
            label="MANTLE WAVES", color=MAGMA)
add(2, "mantle", 1.04, 1.22, (0.5, 0.5), (0.5, 0.56), fx=[fx_mantle], cold=-0.8, shake=2.0)

def fx_uplift(fr, layer, kb, tt, p):
    uplift_arrows(layer, kb, tt, p, [(0.30, 0.55), (0.52, 0.48), (0.72, 0.58)])
    pointer(layer, kb.project(0.5, 0.34, p), tt, 2.2, -130, label="LAND RISING", color=ORANGE, small=True)
add(3, "escarp", 1.03, 1.2, (0.5, 0.6), (0.5, 0.38), fx=[fx_uplift], cold=0.8, shake=3.0)

def fx_buried(fr, layer, kb, tt, p):
    x, y = kb.project(0.5, 0.62, p)
    pointer(layer, (x, y), tt, 1.2, -125, label="GAMBURTSEV MOUNTAINS", color=CYAN)
    chip(layer, tt, 3.0, "AN ALPINE RANGE UNDER 1–3 KM OF ICE", 300, color=CYAN, size=31)
add(4, "buried", 1.05, 1.24, (0.5, 0.45), (0.5, 0.6), fx=[fx_buried], cold=1.2)

def fx_peaks(fr, layer, kb, tt, p):
    snowfall(layer, tt, amount=0.9)
    pointer(layer, kb.project(0.46, 0.38, p), tt, 2.0, -35, label="THE FIRST GLACIERS", color=CYAN, small=True)
add(5, "peaks", 1.02, 1.2, (0.5, 0.55), (0.46, 0.4), fx=[fx_peaks], cold=0.9)

def fx_albedo(fr, layer, kb, tt, p):
    x, y = kb.project(0.5, 0.42, p)
    sun_rays(layer, tt, (x, y))
    chip(layer, tt, 1.0, "THE ICE-ALBEDO EFFECT", 280, color=WHITE, size=36)
    chip(layer, tt, 3.4, "−1°C  GLOBAL COOLING", 1140, color=CYAN, size=40)
add(6, "albedo", 1.02, 1.16, (0.5, 0.45), (0.5, 0.5), fx=[fx_albedo], cold=0.3)

def fx_tundra(fr, layer, kb, tt, p):
    chip(layer, tt, 0.9, "THE ARCTIC: TOO LOW FOR ICE", 290, color=RED, size=34)
    pointer(layer, kb.project(0.5, 0.55, p), tt, 2.6, -40, label="NO ALTITUDE  •  NO ICE", color=RED, small=True)
add(7, "tundra", 1.02, 1.18, (0.5, 0.5), (0.5, 0.42), fx=[fx_tundra], cold=0.4)

def fx_reveal(fr, layer, kb, tt, p):
    mantle_wave(layer, tt*0.7, kb.project(0.5, 0.58, p)[1], amp=34)
    chip(layer, tt, 1.4, "ICE AGES ARE BORN INSIDE THE EARTH", 300, color=MAGMA, size=32)
add(8, "mantle", 1.26, 1.06, (0.5, 0.58), (0.5, 0.45), fx=[fx_reveal], cold=-0.6, shake=1.5)

def fx_cta(fr, layer, kb, tt, p):
    d = ImageDraw.Draw(layer)
    counter(layer, tt, 0.8, 52, "METERS OF SEA LEVEL, LOCKED IN THE ICE", (W/2, 220), color=CYAN, big=104)
    if tt > 4.6:
        a = ease_out((tt-4.6)/0.7)
        f = font(FONT_B, 66)
        txt = "FOLLOW  FOR  MORE"
        tw = d.textlength(txt, font=f)
        d.text(((W-tw)/2+3, 1163), txt, font=f, fill=(0, 0, 0, int(190*a)))
        d.text(((W-tw)/2, 1160), txt, font=f, fill=(*CYAN, int(255*a)))
        f2 = font(FONT_R, 27)
        src = "Source: Science — Gernon et al., Univ. of Southampton, Aug 2026"
        tw2 = d.textlength(src, font=f2)
        d.text(((W-tw2)/2, 1262), src, font=f2, fill=(*WHITE, int(200*a)))
add(9, "aur", 1.0, 1.18, (0.5, 0.55), (0.5, 0.4), fx=[fx_cta], cold=0.55)

# ------------------------------------------------------------------ audio
def decode(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)

def build_audio():
    n = int(TOTAL*SR)
    tt = np.arange(n)/SR
    rng = np.random.default_rng(7)

    noise = rng.normal(0, 1, n).astype(np.float32)
    S = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1/SR)
    S *= np.exp(-freqs/380)
    wind = np.fft.irfft(S, n).astype(np.float32)
    wind /= np.abs(wind).max()+1e-9
    wind *= 0.14*(0.65+0.35*np.sin(2*np.pi*tt/15+0.4))

    drone = np.zeros(n, dtype=np.float32)
    for f0, g in [(49, .5), (49.3, .4), (98, .3), (147, .15), (196, .08)]:
        drone += g*np.sin(2*np.pi*f0*tt + 0.6*np.sin(2*np.pi*0.06*tt)).astype(np.float32)
    drone *= 0.12*(0.75+0.25*np.sin(2*np.pi*tt/19))

    # deep slow "mantle" swell every 4 s
    pulse = np.zeros(n, dtype=np.float32)
    k = int(1.2*SR)
    kern = (np.sin(2*np.pi*36*np.arange(k)/SR)*np.exp(-np.arange(k)/(0.35*SR))).astype(np.float32)
    for b in np.arange(scene_start[2], TOTAL-1.5, 4.0):
        i0 = int(b*SR)
        g = 0.3 + 0.5*(b/TOTAL)
        pulse[i0:i0+k] += kern[:max(0, min(k, n-i0))]*g*0.4

    sfx = np.zeros(n, dtype=np.float32)
    kb_len = int(1.6*SR)
    tb = np.arange(kb_len)/SR
    boom = (np.sin(2*np.pi*40*tb)*np.exp(-tb/0.35) +
            0.4*np.sin(2*np.pi*28*tb)*np.exp(-tb/0.6)).astype(np.float32)
    for i, s in enumerate(scene_start):
        i0 = int(s*SR)
        g = 0.85 if i in (2, 4, 8) else 0.5
        sfx[i0:i0+kb_len] += (boom*g)[:max(0, min(kb_len, n-i0))]

    bgm = wind + drone + pulse + sfx

    voice = np.zeros(n, dtype=np.float32)
    for i, (f, _) in enumerate(VOICE):
        v = decode(A("synth", f))
        i0 = int((scene_start[i]+PRE)*SR)
        voice[i0:i0+len(v)] += v[:max(0, min(len(v), n-i0))]
    voice *= 0.95

    env = np.abs(voice)
    k2 = int(0.20*SR)
    env = np.convolve(env, np.ones(k2, dtype=np.float32)/k2, mode="same")
    mix = bgm*(1.0/(1.0+6.5*env))*0.9 + voice

    mix[:int(0.3*SR)] *= np.linspace(0, 1, int(0.3*SR))
    fade = int(1.4*SR)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix = np.tanh(mix*1.15)*0.92
    peak = np.abs(mix).max()
    if peak > 0.98: mix *= 0.98/peak

    pcm = (mix*32767).astype(np.int16)
    with open(A("synth", "man_mix.wav"), "wb") as f:
        f.write(b"RIFF"+struct.pack("<I", 36+len(pcm)*2)+b"WAVEfmt " +
                struct.pack("<IHHIIHH", 16, 1, 1, SR, SR*2, 2, 16) +
                b"data"+struct.pack("<I", len(pcm)*2))
        f.write(pcm.tobytes())
    print("audio written")

def fmt_ts(x):
    ms = int((x-int(x))*1000); s = int(x)
    return f"{s//3600:02d}:{s%3600//60:02d}:{s%60:02d},{ms:03d}"

def build_srt():
    lines = []
    for i, (_, txt) in enumerate(VOICE):
        a = scene_start[i]+PRE; b = a+vdur[i]
        lines.append(f"{i+1}\n{fmt_ts(a)} --> {fmt_ts(b)}\n{txt}\n")
    with open(os.path.join(OUTDIR, "antarctica_froze_first_reel.srt"), "w") as f:
        f.write("\n".join(lines))

def render():
    vp = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", A("synth", "man_mix.wav"),
         "-c:v", "libx264", "-preset", "medium", "-crf", "21",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-c:a", "aac", "-b:a", "192k", "-shortest",
         "/tmp/man_master.mp4"], stdin=subprocess.PIPE)
    for fi in range(N_FRAMES):
        gt = fi/FPS
        si = len(SC)-1
        for i, sc in enumerate(SC):
            if gt < sc["t0"]+sc["dur"]: si = i; break
        sc = SC[si]
        tt = gt - sc["t0"]
        p = min(1.0, tt/sc["dur"])
        shk = (0.0, 0.0)
        if sc["shake"] > 0:
            m = sc["shake"]
            shk = (m*math.sin(gt*23.7)+m*0.5*math.sin(gt*41.3),
                   m*math.sin(gt*19.1+2)+m*0.5*math.sin(gt*37.7))
        base = sc["kb"].frame(p, shk)
        arr = grade(np.asarray(base), fi, sc["cold"])
        frame = Image.fromarray(arr).convert("RGBA")
        layer = glow_layer()
        for fx in sc["fx"]:
            fx(frame, layer, sc["kb"], tt, p)
        comp_glow(frame, layer)
        va, vb = PRE, PRE+vdur[sc["i"]]
        if va <= tt <= vb:
            draw_caption(frame, VOICE[sc["i"]][1], (tt-va)/(vb-va))
        letterbox(frame)
        d = ImageDraw.Draw(frame)
        d.rectangle([0, 84, int(W*gt/TOTAL), 88], fill=(*CYAN, 255))
        fade = 1.0
        if gt < 0.6: fade = gt/0.6
        if TOTAL-gt < 1.2: fade = max(0.0, (TOTAL-gt)/1.2)
        out = np.asarray(frame.convert("RGB"))
        if fade < 1.0:
            out = (out.astype(np.float32)*fade).astype(np.uint8)
        vp.stdin.write(out.tobytes())
        if fi % 300 == 0:
            print(f"frame {fi}/{N_FRAMES} ({100*fi/N_FRAMES:.0f}%)", flush=True)
    vp.stdin.close(); vp.wait()
    print("master done:", vp.returncode)

if __name__ == "__main__":
    build_audio()
    build_srt()
    render()
    # final social-size encode
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "/tmp/man_master.mp4",
                    "-vf", "hqdn3d=2:2:6:6", "-c:v", "libx264", "-preset", "slow",
                    "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-c:a", "aac", "-b:a", "160k",
                    os.path.join(OUTDIR, "antarctica_froze_first_reel.mp4")], check=True)
    man = dict(
        title="Why Antarctica Froze First — mantle waves built the ice continent",
        duration_s=round(TOTAL, 2), resolution=f"{W}x{H}", fps=FPS,
        discovery="Mantle waves uplifted East Antarctica (escarpment + Gamburtsev Mts) enabling glaciation 34 Ma, 25 My before the Arctic; ice-albedo cooled globe ~1°C; EAIS holds ~52 m sea level",
        source_paper="Science — Gernon, Hincks et al., University of Southampton; ScienceDaily Aug 25/31 2026, Phys.org",
        visual_sources="AI-rendered plates styled on copyright-free Pexels/NASA/USGS imagery; all motion, pointer overlays, mantle-wave/uplift/albedo FX coded in Python (numpy+PIL+ffmpeg)",
    )
    with open(os.path.join(OUTDIR, "antarctica_froze_first_manifest.json"), "w") as f:
        json.dump(man, f, indent=2)
    print("all done")
