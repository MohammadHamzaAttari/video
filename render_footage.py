#!/usr/bin/env python3
"""
render_footage.py — re-renders the dino recut scenes using REAL external footage
(GitHub-hosted free clips) instead of AI images:
  s1: dinoDB 'timimus drinking' GIF (dinosaurs at waterhole)
  s2: NASA SVS clip2 (star shredded by black hole)  [public domain]
  s3: dinoDB 'qantassaurus fleeing' GIF (dinosaurs fleeing)
  s4: NASA SVS clip5 (fading star / darkness)       [public domain]
  s5: dinoDB 'australian dinosaurs' GIF (20fps)
  s6: imageio cockatoo.mp4 (real bird)              [BSD sample]
  s7: procedural end card (unchanged)

GIFs are motion-interpolated to 30fps in a first pass to an intermediate file,
then frames are read with imageio_ffmpeg.read_frames (no pipe deadlock).
Clips go to sources_recut/ so build_dino_recut.py --assemble keeps the same
VO/music/SFX sync.
"""
import os, sys, json, subprocess
import numpy as np
from PIL import Image
import imageio_ffmpeg
from imageio_ffmpeg import read_frames

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from build_dino_recut import (W, H, FPS, CLIPS, CAPS, draw_caption, grade,
                              enc_start, push, finish)
PLAN = json.load(open(os.path.join(ROOT, "plan_recut.json")))

STOCK = os.path.join(ROOT, "stock")
SOURCES = os.path.join(ROOT, "sources")
TMP = os.path.join(ROOT, "tmp_interp")
os.makedirs(TMP, exist_ok=True)
FF = imageio_ffmpeg.get_ffmpeg_exe()

SCENES = {
    "s1": {"input": f"{STOCK}/dinoDB/assets/images/timimus_and_qantassaurus_drinking_by_2195razielim-d5b0u73.gif",
           "interp": True, "ss": 0.0, "dur": 5.21, "zoom": (1.00, 1.08)},
    "s2": {"input": f"{SOURCES}/clip2_tde_shred.mp4",
           "interp": False, "ss": 34.0, "dur": 4.01, "zoom": (1.06, 1.00)},
    "s3": {"input": f"{STOCK}/dinoDB/assets/images/qantassaurus_and_timimus_flee_by_2195razielim-d5b0uvg.gif",
           "interp": True, "ss": 0.0, "dur": 4.42, "zoom": (1.00, 1.10)},
    "s4": {"input": f"{SOURCES}/clip5_tde_fading.mov",
           "interp": False, "ss": 5.0, "dur": 4.85, "zoom": (1.08, 1.00)},
    "s5": {"input": f"{STOCK}/dinoDB/assets/images/australian_dinosaurs_diamantinasaurus_by_2195razielim-d585l4z.gif",
           "interp": True, "ss": 0.0, "dur": 2.54, "zoom": (1.00, 1.12)},
    "s6": {"input": f"{STOCK}/imageio-binaries/images/cockatoo.mp4",
           "interp": True, "ss": 0.0, "dur": 5.74, "zoom": (1.00, 1.09)},
}

def kenburns(base, t, dur, zoom):
    z0, z1 = zoom
    frac = min(1.0, t / dur)
    z = z0 + (z1 - z0) * frac
    cw, ch = int(W / z), int(H / z)
    cx = (base.width - cw) // 2
    cy = int((base.height - ch) * (0.5 + 0.06 * np.sin(frac * np.pi)))
    cy = max(0, min(base.height - ch, cy))
    return base.crop((cx, cy, cx + cw, cy + ch)).resize((W, H), Image.LANCZOS)

def render_scene(sc_id):
    sc = SCENES[sc_id]
    plan_scene = next(s for s in PLAN["scenes"] if s["id"] == sc_id)
    dur = plan_scene["end"] - plan_scene["start"]
    caps = CAPS[sc_id]
    out = os.path.join(CLIPS, f"{sc_id}.mp4")
    interp = os.path.join(TMP, f"{sc_id}.mp4")

    # ---- phase 1: (interpolate) + full-bleed scale -> intermediate h264 file ----
    vf = ""
    if sc["interp"]:
        vf += "minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir,"
    vf += (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
           f"fps={FPS},format=yuv420p")
    cmd1 = [FF, "-y", "-loglevel", "error", "-ss", str(sc["ss"]), "-t", str(dur),
            "-i", sc["input"], "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "16", "-an", interp]
    r = subprocess.run(cmd1)
    if r.returncode != 0:
        raise RuntimeError(f"interp pass failed for {sc_id}")

    # ---- phase 2: read frames -> post -> encode final clip ----
    gen = read_frames(interp, pix_fmt="rgb24")
    meta = next(gen)  # header dict
    fw, fh = meta["size"]
    proc = enc_start(out)
    max_frames = int(round(dur * FPS))
    i = 0
    for raw in gen:
        if i >= max_frames:
            break
        frame = np.frombuffer(raw, np.uint8).reshape(fh, fw, 3)
        t = i / FPS
        base = Image.fromarray(frame)
        f = kenburns(base, t, dur, sc["zoom"])
        f = grade(np.asarray(f), t)
        for text, off in caps:
            f = draw_caption(np.asarray(f), text, t, off, dur + 0.3)
        push(proc, np.asarray(f))
        i += 1
    finish(proc)
    print(f"rendered {sc_id} ({i} frames, {i/FPS:.2f}s)", flush=True)

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for sc_id in ["s1", "s2", "s3", "s4", "s5", "s6"]:
        if only and only != sc_id:
            continue
        render_scene(sc_id)
    print("footage clips done", flush=True)
