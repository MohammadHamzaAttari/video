#!/usr/bin/env python3
"""
Build "The Day the Dinosaurs Died" — a mind-blowing history discovery short.
Style-matched to the repo's eaten_star pipeline: 9:16, cinematic grade, letterbox,
baked captions, VO-synced beats, procedural score + SFX.

Usage:
  python3 build_dino_day.py --plan       # probe VO durations, write plan.json
  python3 build_dino_day.py --render     # run render_cgi.py (needs plan.json)
  python3 build_dino_day.py --audio      # run gen_music_dino.py + gen_sfx_dino.py
  python3 build_dino_day.py --assemble   # final mux (needs clips + audio)
"""
import os, sys, json, subprocess, re

ROOT = os.path.dirname(os.path.abspath(__file__))
SYNTH = os.path.join(ROOT, "synth", "dino")
CLIPS = os.path.join(ROOT, "sources_dino")
ASSETS = os.path.join(ROOT, "assets", "dino")
PLAN = os.path.join(ROOT, "plan.json")
FINAL = os.path.join(ROOT, "dino_day_9x16.mp4")

FFMPEG = None
def ff():
    global FFMPEG
    if FFMPEG is None:
        import imageio_ffmpeg
        FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
    return FFMPEG

SCRIPT = {
    "s01": "Sixty-six million years ago... three quarters of all life on Earth died in a single day. Now, scientists have found the exact moment it happened.",
    "s02": "The clue was a layer of rock. A thin band of iridium — a metal that almost only comes from space — buried in the ground, on every continent, at the exact same depth.",
    "s03": "One layer. Sixty-six million years old. Everywhere on Earth. That's when physicist Luis Alvarez asked the question that rewrote history: what if a giant asteroid hit the planet?",
    "s04": "They found the crime scene: a crater buried under Mexico, one hundred and eighty kilometers wide. The killer: an asteroid nine miles across, striking at forty thousand miles per hour. The force: ten billion Hiroshima bombs.",
    "s05": "Then, in 2019, the smoking gun. A fossil graveyard called Tanis. Fish preserved with glass from the impact still stuck in their gills — debris from the asteroid itself, raining down moments after the strike. The day the dinosaurs died... caught in the act.",
    "s06": "Here's what that day looked like. A megatsunami taller than skyscrapers. Firestorms that circled the planet. Then... darkness. Dust blocked the sun for years. Plants died. The plant-eaters starved. Then the predators — including every single T-Rex on Earth.",
    "s07": "Seventy-five percent of all species. Gone. But here's the twist: a few survivors — small, fast, feathered — found a way. And you're looking at their descendants right now.",
    "s08": "Every bird on Earth carries the DNA of that day. Follow for more mind-blowing discoveries that rewrite history. And if this blew your mind — share it with a dinosaur lover.",
}

TITLE_DUR = 2.9          # title slam card duration
GAP = 0.30               # breathing gap between VO segments
TAIL = 1.9               # hold after last VO

def probe_dur(path):
    out = subprocess.run([ff(), "-i", path], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    if not m:
        raise RuntimeError(f"cannot probe {path}")
    return int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))

def compute_plan():
    durs = {k: probe_dur(os.path.join(SYNTH, f"{k}_voice.mp3")) for k in sorted(SCRIPT)}
    starts, t = {}, 0.0
    for i, k in enumerate(sorted(SCRIPT)):
        starts[k] = t
        t += durs[k] + GAP
    title_start = starts["s01"] + durs["s01"] + 0.12
    # shift everything after s01 by title block
    shift = TITLE_DUR + 0.10 - GAP
    for k in ("s02", "s03", "s04", "s05", "s06", "s07", "s08"):
        starts[k] += shift
    s = starts
    total = starts["s08"] + durs["s08"] + TAIL

    def C(id, text, t0, t1, style="cap"):
        return {"id": id, "text": text, "t0": round(t0, 3), "t1": round(t1, 3), "style": style}

    shots = [
        {"id": "shot_hook",     "kind": "image", "src": f"{ASSETS}/img01_hook_trex.jpg", "start": s["s01"], "end": title_start - 0.02, "zoom": (1.00, 1.14), "pan": ((0.5, 0.46), (0.5, 0.40))},
        {"id": "title_slam",    "kind": "title", "start": title_start, "end": title_start + TITLE_DUR},
        {"id": "shot_iridium",  "kind": "image", "src": f"{ASSETS}/img02_iridium.jpg", "start": s["s02"], "end": s["s02"] + 12.98, "zoom": (1.10, 1.00), "pan": ((0.5, 0.35), (0.5, 0.55))},
        {"id": "shot_ast_sky",  "kind": "proc_asteroid", "start": s["s03"], "end": s["s03"] + 6.2},
        {"id": "shot_shred",    "kind": "video", "src": f"{ROOT}/sources/clip2_tde_shred.mp4", "vstart": 34.0, "start": s["s03"] + 6.2, "end": s["s03"] + 10.2},
        {"id": "shot_crater_a", "kind": "image", "src": f"{ASSETS}/img03_crater.jpg", "start": s["s03"] + 10.2, "end": s["s04"] + 7.9, "zoom": (1.12, 1.00), "pan": ((0.5, 0.45), (0.5, 0.42))},
        {"id": "shot_ast_img",  "kind": "image", "src": f"{ASSETS}/img04_asteroid.jpg", "start": s["s04"] + 7.9, "end": s["s04"] + 12.5, "zoom": (1.02, 1.16), "pan": ((0.5, 0.42), (0.5, 0.38)), "fx": "flicker"},
        {"id": "shot_impact",   "kind": "proc_impact", "start": s["s04"] + 12.5, "end": s["s04"] + 12.5 + 6.3},
        {"id": "shot_tanis_a",  "kind": "image", "src": f"{ASSETS}/img05_tanis.jpg", "start": s["s05"], "end": s["s05"] + 8.0, "zoom": (1.00, 1.12), "pan": ((0.5, 0.5), (0.5, 0.45))},
        {"id": "shot_ash",      "kind": "proc_ash", "start": s["s05"] + 8.0, "end": s["s05"] + 16.0},
        {"id": "shot_tanis_b",  "kind": "image", "src": f"{ASSETS}/img05_tanis.jpg", "start": s["s05"] + 16.0, "end": s["s05"] + 20.42, "zoom": (1.08, 1.00), "pan": ((0.5, 0.48), (0.5, 0.52))},
        {"id": "shot_tsunami",  "kind": "image", "src": f"{ASSETS}/img06_tsunami.jpg", "start": s["s06"], "end": s["s06"] + 8.0, "zoom": (1.00, 1.16), "pan": ((0.5, 0.5), (0.5, 0.46)), "fx": "tsunami"},
        {"id": "shot_fire",     "kind": "image", "src": f"{ASSETS}/img07_firestorm.jpg", "start": s["s06"] + 8.0, "end": s["s06"] + 16.0, "zoom": (1.10, 1.00), "pan": ((0.5, 0.45), (0.5, 0.48)), "fx": "flicker"},
        {"id": "shot_dark_a",   "kind": "image", "src": f"{ASSETS}/img08_darkness.jpg", "start": s["s06"] + 16.0, "end": s["s06"] + 20.0, "zoom": (1.00, 1.10), "pan": ((0.5, 0.5), (0.5, 0.47))},
        {"id": "shot_fade",     "kind": "video", "src": f"{ROOT}/sources/clip5_tde_fading.mov", "vstart": 5.0, "start": s["s06"] + 20.0, "end": s["s06"] + 23.26},
        {"id": "shot_surv",     "kind": "image", "src": f"{ASSETS}/img09_survivor.jpg", "start": s["s07"], "end": s["s07"] + 7.1, "zoom": (1.00, 1.13), "pan": ((0.5, 0.52), (0.5, 0.47))},
        {"id": "shot_bird",     "kind": "image", "src": f"{ASSETS}/img10_bird.jpg", "start": s["s07"] + 7.1, "end": s["s08"] + 7.0, "zoom": (1.06, 1.00), "pan": ((0.5, 0.45), (0.5, 0.5))},
        {"id": "end_card",      "kind": "endcard", "start": s["s08"] + 7.0, "end": total},
    ]

    caps = [
        C("c01", "66 MILLION YEARS AGO", s["s01"] + 0.9, s["s01"] + 5.0),
        C("c02", "3 OF EVERY 4 SPECIES DIED — IN ONE DAY", s["s01"] + 5.3, title_start - 0.25),
        C("c03", "A METAL FROM SPACE — ON EVERY CONTINENT", s["s02"] + 2.2, s["s02"] + 11.5),
        C("c04", "WHAT IF A GIANT ASTEROID HIT EARTH?", s["s03"] + 7.0, s["s03"] + 13.5),
        C("c05", "CHICXULUB: THE CRATER UNDER MEXICO", s["s04"] + 1.6, s["s04"] + 7.6),
        C("c06", "THE KILLER: 9 MILES ACROSS", s["s04"] + 7.9, s["s04"] + 12.2),
        C("c07", "10 BILLION HIROSHIMAS", s["s04"] + 12.8, s["s04"] + 18.3, "cap_big"),
        C("c08", "TANIS: THE FOSSIL GRAVEYARD", s["s05"] + 1.6, s["s05"] + 7.2),
        C("c09", "GLASS FROM THE ASTEROID — IN THEIR GILLS", s["s05"] + 9.4, s["s05"] + 15.2),
        C("c10", "THE DAY THE DINOSAURS DIED. CAUGHT IN THE ACT.", s["s05"] + 16.6, s["s05"] + 20.1),
        C("c11", "A MEGATSUNAMI — TALLER THAN SKYSCRAPERS", s["s06"] + 1.3, s["s06"] + 7.2),
        C("c12", "FIRESTORMS CIRCLED THE PLANET", s["s06"] + 9.3, s["s06"] + 15.2),
        C("c13", "DARKNESS. FOR YEARS.", s["s06"] + 17.3, s["s06"] + 22.6, "cap_big"),
        C("c14", "75% OF ALL SPECIES — GONE", s["s07"] + 0.8, s["s07"] + 4.4, "cap_big"),
        C("c15", "BUT SOME SURVIVED", s["s07"] + 4.9, s["s07"] + 9.8),
        C("c16", "YOU'RE LOOKING AT THEIR DESCENDANTS", s["s07"] + 10.6, s["s08"] + 6.5),
    ]

    plan = {
        "starts": s, "durations": durs, "total": round(total, 3),
        "title_start": title_start, "title_dur": TITLE_DUR,
        "shots": shots, "captions": caps,
    }
    json.dump(plan, open(PLAN, "w"), indent=1)
    print(f"plan.json written — total {total:.2f}s")
    for k in sorted(starts):
        print(f"  {k}: start={starts[k]:7.2f}  dur={durs[k]:6.2f}")

def run(cmd):
    print(">", " ".join(str(c) for c in cmd))
    res = subprocess.run([str(c) for c in cmd])
    if res.returncode != 0:
        sys.exit(f"FAILED: {cmd}")

def assemble():
    plan = json.load(open(PLAN))
    os.makedirs(CLIPS, exist_ok=True)

    # --- video concat ---
    lst = os.path.join(ROOT, "clips.txt")
    with open(lst, "w") as f:
        for sh in plan["shots"]:
            p = os.path.join(CLIPS, f"{sh['id']}.mp4")
            if not os.path.exists(p):
                sys.exit(f"missing clip {p}")
            f.write(f"file '{p}'\n")

    # --- audio graph ---
    keys = sorted(SCRIPT)
    inputs, af, idx = [], "", 1   # index 0 = concat video input
    vo_labels = []
    for k in keys:
        mp3 = os.path.join(SYNTH, f"{k}_voice.mp3")
        ms = int(plan["starts"][k] * 1000)
        inputs += ["-i", mp3]
        af += f"[{idx}:a]aresample=48000,adelay={ms}|{ms}[vo{idx}];"
        vo_labels.append(f"[vo{idx}]")
        idx += 1
    inputs += ["-i", os.path.join(SYNTH, "music.wav"), "-i", os.path.join(SYNTH, "sfx.wav")]
    mi, si = idx, idx + 1
    af += f"[{mi}:a]volume=0.30[mus];[{si}:a]volume=0.85[sfx];"
    af += "".join(vo_labels) + f"[mus][sfx]amix=inputs={len(keys) + 2}:duration=longest:normalize=0,"
    af += "acompressor=threshold=-14dB:ratio=3:attack=8:release=120,"
    af += "loudnorm=I=-14.5:LRA=12:TP=-1.5[aout]"

    cmd = [ff(), "-y", "-loglevel", "warning", "-f", "concat", "-safe", "0", "-i", lst] + inputs
    cmd += ["-filter_complex", af, "-map", "0:v", "-map", "[aout]"]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", FINAL]
    run(cmd)
    print(f"Done -> {FINAL}")

if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "--plan"
    if a == "--plan":
        compute_plan()
    elif a == "--render":
        run(["python3", os.path.join(ROOT, "render_cgi.py")])
    elif a == "--audio":
        run(["python3", os.path.join(ROOT, "gen_music_dino.py")])
        run(["python3", os.path.join(ROOT, "gen_sfx_dino.py")])
    elif a == "--assemble":
        assemble()
    else:
        print(__doc__)
