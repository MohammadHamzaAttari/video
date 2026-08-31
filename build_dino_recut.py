#!/usr/bin/env python3
"""
build_dino_recut.py — "Birds Are Dinosaurs" (Dino Day Recut)
27-29s full-bleed 1080x1920@30fps short per the production memo:
  * NO letterboxing, NO border lines, no vignette
  * hard cuts only (scene changes at VO boundaries)
  * captions inside safe margins (>=80px), bold white + black outline + shadow
  * new visual every 2-5s, hook text on screen within 1.5s

Usage:
  python3 build_dino_recut.py --plan       # probe VO, write plan_recut.json
  python3 build_dino_recut.py --render     # render scene clips
  python3 build_dino_recut.py --audio      # generate music+sfx beds
  python3 build_dino_recut.py --assemble   # final mux
"""
import os, sys, json, subprocess, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance
import imageio_ffmpeg

ROOT = os.path.dirname(os.path.abspath(__file__))
SYNTH = os.path.join(ROOT, "synth", "dino_recut")
CLIPS = os.path.join(ROOT, "sources_recut")
ASSETS = os.path.join(ROOT, "assets", "dino")
PLAN = os.path.join(ROOT, "plan_recut.json")
FINAL = os.path.join(ROOT, "dino_recut_9x16.mp4")
W, H, FPS = 1080, 1920, 30
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FF = imageio_ffmpeg.get_ffmpeg_exe()

VO_TEXT = [
    ("v1", "Three of every four species died... in one day."),
    ("v2", "An asteroid, six miles wide, hit Earth —"),
    ("v3", "and triggered fires, tsunamis, years of darkness."),
    ("v4", "Seventy-five percent of all life on the planet vanished."),
    ("v5", "But one line survived."),
    ("v6", "It's sitting on your windowsill right now. Birds are living dinosaurs."),
]

CAPS = {
    "s1": [("3 OF EVERY 4 SPECIES DIED — IN ONE DAY", 0.45)],
    "s2": [("AN ASTEROID 6 MILES WIDE", 0.30)],
    "s3": [("IT TRIGGERED FIRES, TSUNAMIS, YEARS OF DARKNESS", 0.30)],
    "s4": [("75% OF ALL LIFE ON EARTH — GONE", 0.30)],
    "s5": [("BUT ONE LINE SURVIVED", 0.25)],
    "s6": [("IT'S SITTING ON YOUR WINDOWSILL RIGHT NOW", 0.30),
           ("BIRDS ARE LIVING DINOSAURS", 2.6)],
    "s7": [("FOLLOW FOR MORE MIND-BLOWING DISCOVERIES", 0.4),
           ("LIKE  •  SHARE  •  FOLLOW", 1.3)],
}

def probe_dur(path):
    out = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return float(m.group(1))*3600 + float(m.group(2))*60 + float(m.group(3)) if m else 0

def compute_plan():
    durs = {k: probe_dur(os.path.join(SYNTH, f"{k}_voice.mp3")) for k, _ in VO_TEXT}
    starts, t = {}, 0.0
    for k, _ in VO_TEXT:
        starts[k] = t
        t += durs[k]
    total = t + 2.0  # end-card hold
    scenes = [
        {"id": "s1", "kind": "image", "src": f"{ASSETS}/img01_hook_trex.jpg",
         "start": starts["v1"], "end": starts["v2"], "zoom": (1.00, 1.14), "pan": ((0.5, 0.48), (0.5, 0.44)), "speed": "slow"},
        {"id": "s2", "kind": "image", "src": f"{ASSETS}/img11_asteroid_full.jpg",
         "start": starts["v2"], "end": starts["v3"], "zoom": (1.05, 1.32), "pan": ((0.42, 0.46), (0.58, 0.42)), "speed": "fast"},
        {"id": "s3", "kind": "image", "src": f"{ASSETS}/img06_tsunami.jpg",
         "start": starts["v3"], "end": starts["v4"], "zoom": (1.02, 1.10), "pan": ((0.5, 0.5), (0.5, 0.48)), "speed": "slow"},
        {"id": "s4", "kind": "image", "src": f"{ASSETS}/img08_darkness.jpg",
         "start": starts["v4"], "end": starts["v5"], "zoom": (1.14, 1.03), "pan": ((0.5, 0.42), (0.5, 0.52)), "speed": "slow"},
        {"id": "s5", "kind": "image", "src": f"{ASSETS}/img12_morph.jpg",
         "start": starts["v5"], "end": starts["v6"], "zoom": (1.00, 1.34), "pan": ((0.5, 0.45), (0.5, 0.42)), "speed": "fast"},
        {"id": "s6", "kind": "image", "src": f"{ASSETS}/img10_bird.jpg",
         "start": starts["v6"], "end": total - 2.0, "zoom": (1.00, 1.10), "pan": ((0.5, 0.47), (0.5, 0.45)), "speed": "slow"},
        {"id": "s7", "kind": "endcard", "start": total - 2.0, "end": total},
    ]
    for s in scenes:
        s["start"] = round(s["start"], 3); s["end"] = round(s["end"], 3)
    plan = {"starts": starts, "durations": durs, "total": round(total, 3), "scenes": scenes}
    json.dump(plan, open(PLAN, "w"), indent=1)
    print(f"plan_recut.json — total {total:.2f}s (target 27-30)")
    for s in scenes:
        print(f"  {s['id']}: {s['start']:6.2f} -> {s['end']:6.2f}  ({s['end']-s['start']:4.2f}s)")

# ---------------- render ----------------
_fonts = {}
def font(size):
    if size not in _fonts:
        _fonts[size] = ImageFont.truetype(FONT_B, size)
    return _fonts[size]

def enc_start(out):
    return subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-an", out], stdin=subprocess.PIPE)

def push(proc, frame):
    proc.stdin.write(np.ascontiguousarray(frame).tobytes())

def finish(proc):
    proc.stdin.close(); proc.wait()

def wrap_text(draw, text, fnt, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def fit_font(draw, text, max_w, start=62, min_sz=34):
    sz = start
    while sz > min_sz:
        f = font(sz)
        if draw.textlength(text, font=f) <= max_w:
            return f
        sz -= 2
    return font(min_sz)

def draw_caption(img, text, t, t0, t1, y_base=H - 400):
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img)
    if t < t0: return img
    if t > t1: return img
    fade = 0.15
    a = min(1.0, (t - t0) / fade, (t1 - t) / fade)
    if a <= 0: return img
    pop = 1.08 if t - t0 < 0.18 else 1.0
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    max_w = W - 160  # 80px safe margin each side
    f = fit_font(d, text, max_w)
    lines = wrap_text(d, text, f, max_w)
    lh = int(f.size * 1.22)
    total_h = lh * len(lines)
    y = y_base - total_h // 2
    for ln in lines:
        tw = d.textlength(ln, font=f)
        x = (W - tw) // 2
        for dx, dy in [(0, 0)]:
            pass
        # black outline (8-direction)
        for ox in (-3, 3):
            for oy in (-3, 3):
                d.text((x + ox, y + oy), ln, font=f, fill=(0, 0, 0, int(255 * a)))
        d.text((x, y), ln, font=f, fill=(0, 0, 0, int(160 * a)))  # fake shadow via offset below
        # white fill
        d.text((x, y), ln, font=f, fill=(255, 255, 255, int(255 * a)))
        y += lh
    # subtle backdrop for readability (soft dark pill) — NO box border, just translucent
    # (skip heavy box; outline text is enough per memo: bold white + black outline)
    if pop > 1.0:
        ov = ov.resize((W, H), Image.BILINEAR) if False else ov
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    return img

def load_cover(path):
    im = Image.open(path).convert("RGB")
    sc = max(W / im.width, H / im.height) * 1.35
    im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
    x = (im.width - W) // 2; y = (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))

def kens_frame(base, t, dur, zoom, pan):
    z0, z1 = zoom; (px0, py0), (px1, py1) = pan
    frac = min(1.0, t / dur)
    z = z0 + (z1 - z0) * frac
    px = px0 + (px1 - px0) * frac
    py = py0 + (py1 - py0) * frac
    cw, ch = int(W / z), int(H / z)
    cx = int(px * (base.width - cw)); cy = int(py * (base.height - ch))
    return base.crop((cx, cy, cx + cw, cy + ch)).resize((W, H), Image.LANCZOS)

def grade(frame, t):
    img = Image.fromarray(frame)
    img = ImageEnhance.Color(img).enhance(1.12)
    img = ImageEnhance.Contrast(img).enhance(1.07)
    arr = np.asarray(img, dtype=np.float32)
    rng = np.random.default_rng(int(t * 1000) % 2**31)
    arr += rng.integers(-4, 5, (H//2, W//2, 1)).repeat(2, 0).repeat(2, 1)[:H, :W]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def render_image(sc):
    base = load_cover(sc["src"])
    dur = sc["end"] - sc["start"]
    caps = CAPS[sc["id"]]
    proc = enc_start(os.path.join(CLIPS, f"{sc['id']}.mp4"))
    n = int(round(dur * FPS))
    for i in range(n):
        t = i / FPS
        f = kens_frame(base, t, dur, sc["zoom"], sc["pan"])
        f = grade(np.asarray(f), t)
        for text, off in caps:
            f = draw_caption(np.asarray(f), text, t, off, dur + 0.3)
        push(proc, np.asarray(f))
    finish(proc)
    print("rendered", sc["id"])

def render_endcard(sc):
    dur = sc["end"] - sc["start"]
    proc = enc_start(os.path.join(CLIPS, f"{sc['id']}.mp4"))
    n = int(round(dur * FPS))
    lines = [("FOLLOW FOR MORE", 0.25, 84, (255, 255, 255)),
             ("MIND-BLOWING DISCOVERIES", 0.55, 84, (255, 255, 255)),
             ("LIKE  •  SHARE  •  FOLLOW", 1.15, 40, (255, 212, 0))]
    for i in range(n):
        t = i / FPS
        arr = np.zeros((H, W, 3), dtype=np.uint8)
        g = np.linspace(8, 20, H, dtype=np.float32)[:, None]
        arr[:] = np.tile(np.concatenate([g * 1.4, g * 0.5, g * 0.4], -1)[:, None, :], (1, W, 1)).astype(np.uint8)
        img = Image.fromarray(arr)
        img = img.convert("RGBA")
        for (txt, tt, size, col) in lines:
            if t < tt: continue
            local = t - tt
            f = font(int(size * min(1.0, 0.7 + local * 2.0)))
            ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(ov)
            tw = d.textlength(txt, font=f)
            a = int(255 * min(1.0, local / 0.25))
            y = 800 + lines.index((txt, tt, size, col)) * 120
            for ox in (-3, 3):
                for oy in (-3, 3):
                    d.text((W//2 - tw//2 + ox, y + oy), txt, font=f, fill=(0, 0, 0, a))
            d.text((W//2 - tw//2, y), txt, font=f, fill=(*col, a))
            img = Image.alpha_composite(img, ov)
        img = img.convert("RGB")
        push(proc, np.asarray(img))
    finish(proc)
    print("rendered", sc["id"])

def render():
    os.makedirs(CLIPS, exist_ok=True)
    plan = json.load(open(PLAN))
    for sc in plan["scenes"]:
        out = os.path.join(CLIPS, f"{sc['id']}.mp4")
        if os.path.exists(out):
            print("exists, skip", sc["id"]); continue
        if sc["kind"] == "image":
            render_image(sc)
        elif sc["kind"] == "endcard":
            render_endcard(sc)
    print("clips done")

# ---------------- assemble ----------------
def run(cmd):
    print(">", " ".join(str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd])
    if r.returncode != 0:
        sys.exit(f"FAILED: {cmd}")

def assemble():
    plan = json.load(open(PLAN))
    lst = os.path.join(ROOT, "clips_recut.txt")
    with open(lst, "w") as f:
        for sc in plan["scenes"]:
            p = os.path.join(CLIPS, f"{sc['id']}.mp4")
            if not os.path.exists(p): sys.exit(f"missing {p}")
            f.write(f"file '{p}'\n")
    keys = [k for k, _ in VO_TEXT]
    inputs, af, idx = [], "", 1  # 0 = concat video
    vo_labels = []
    for k in keys:
        ms = int(plan["starts"][k] * 1000)
        inputs += ["-i", os.path.join(SYNTH, f"{k}_voice.mp3")]
        af += f"[{idx}:a]aresample=48000,adelay={ms}|{ms}[vo{idx}];"
        vo_labels.append(f"[vo{idx}]")
        idx += 1
    inputs += ["-i", os.path.join(SYNTH, "music.wav"), "-i", os.path.join(SYNTH, "sfx.wav")]
    mi, si = idx, idx + 1
    af += f"[{mi}:a]volume=0.30[mus];[{si}:a]volume=0.85[sfx];"
    af += "".join(vo_labels) + f"[mus][sfx]amix=inputs={len(keys)+2}:duration=longest:normalize=0,"
    af += "acompressor=threshold=-14dB:ratio=3:attack=8:release=120,"
    af += "loudnorm=I=-14.5:LRA=12:TP=-1.5[aout]"
    cmd = [FF, "-y", "-loglevel", "warning", "-f", "concat", "-safe", "0", "-i", lst] + inputs
    cmd += ["-filter_complex", af, "-map", "0:v", "-map", "[aout]"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", FINAL]
    run(cmd)
    print("Done ->", FINAL)

if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "--plan"
    if a == "--plan": compute_plan()
    elif a == "--render": render()
    elif a == "--audio":
        run(["python3", os.path.join(ROOT, "gen_audio_recut.py")])
    elif a == "--assemble": assemble()
    else: print(__doc__)
