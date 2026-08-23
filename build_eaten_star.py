#!/usr/bin/env python3
import os, sys, subprocess, json, glob
import urllib.request

PROJ = "/home/hamza/Videos/eaten_star"
SYNTH = f"{PROJ}/synth"
SOURCES = f"{PROJ}/sources"
os.makedirs(SYNTH, exist_ok=True)

SCRIPT = {
    "s01": "This star should have died the first time.",
    "s02": "Instead, it's been eaten alive by a black hole — over, and over, and over again.",
    "s03": "When a star wanders too close to a supermassive black hole, the gravity on its near side gets so much stronger than the far side that the star gets torn apart. Astronomers call it a tidal disruption event.",
    "s04": "Usually, it's a one-time death.",
    "s05": "But scientists have now found about ten stars that don't fully die. They lose part of their mass... survive... and drift back around for another pass — months, sometimes years later. Then it happens again.",
    "s06": "Here's the part that stumped researchers for years. In several of these systems, every single flare comes back dimmer than the last. Something was stripping away less material each time — and nobody could explain why.",
    "s07": "This month, astrophysicists at Syracuse University think they cracked it. The star was already spinning extremely fast — before the black hole ever caught it.",
    "s08": "That spin resists the added force of each encounter, so less material tears loose every time.",
    "s09": "But that raises a stranger question. How does a star end up spinning that fast, in an orbit that tight, in the first place?",
    "s10": "The likely answer: it wasn't always alone. It was probably half of a binary — two stars orbiting each other — until the black hole's gravity tore the pair apart.",
    "s11": "One star was flung out of the galaxy forever, at incredible speed. The other was captured, trapped, and sentenced to this cycle of survival and injury, again and again.",
    "s12": "Some deaths don't happen all at once. Follow Universe Impact for the discoveries that redefine what we thought we knew. If you loved this video, please send stars to support the channel!"
}

CAPTIONS = [
    ("THIS STAR SHOULD HAVE DIED THE FIRST TIME", "s01", 0.0),
    ("TIDAL DISRUPTION EVENT: WHEN A BLACK HOLE TEARS A STAR APART", "s03", 0.0),
    ("USUALLY, IT'S A ONE-TIME DEATH", "s04", 0.0),
    ("~10 STARS SURVIVE — AND COME BACK", "s05", 0.0),
    ("MONTHS OR YEARS LATER... IT HAPPENS AGAIN", "s05", 5.0), # Approximate timing within s05
    ("EVERY FLARE, DIMMER THAN THE LAST", "s06", 0.0),
    ("WHY? NOBODY KNEW — UNTIL NOW", "s06", 4.0), # Approximate timing within s06
    ("THE STAR WAS ALREADY SPINNING FAST", "s07", 0.0),
    ("IT WAS PROBABLY HALF OF A BINARY PAIR", "s10", 0.0),
    ("ONE TWIN: FLUNG INTO DEEP SPACE FOREVER", "s11", 0.0),
    ("THE OTHER: TRAPPED IN THIS CYCLE", "s11", 3.5), # Approximate timing within s11
    ("SOME DEATHS DON'T HAPPEN ALL AT ONCE", "s12", 0.0),
    ("PLEASE SEND STARS TO SUPPORT!", "s12", 4.5)
]

def run(cmd):
    print(">", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"FAILED: {cmd}")
        sys.exit(1)

def esc_draw(text):
    # Extremely robust escaping for drawtext text string
    # Escapes \ then ' then : 
    # FFmpeg requires 4 backslashes for a literal colon if evaluating, 
    # but for simple drawtext text='', we replace colon with \: and single quote with \u2019
    text = text.replace("'", "\u2019").replace(":", "\\:").replace("\n", " ").strip()
    return text

def esc_filter(path):
    # Escape path for use in complex filter string (single quotes around path)
    return path.replace("\\", "\\\\").replace("'", "'\\''").replace(":", "\\:")

def synthesize_audio():
    print("Synthesizing Voiceover...")
    for k, v in SCRIPT.items():
        mp3_out = f"{SYNTH}/{k}_voice.mp3"
        vtt_out = f"{SYNTH}/{k}_timing.vtt"
        json_out = f"{SYNTH}/{k}_timing.json"
        if not os.path.exists(mp3_out):
            run(["edge-tts", "--voice", "en-US-ChristopherNeural", "--rate=+30%", "--text", v, "--write-media", mp3_out, "--write-subtitles", vtt_out])
            
            # Very basic VTT to JSON conversion for gen_sfx
            words = []
            if os.path.exists(vtt_out):
                with open(vtt_out, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                for i in range(len(lines)):
                    if "-->" in lines[i]:
                        t_start = lines[i].split("-->")[0].strip()
                        # simple convert HH:MM:SS.mmm to seconds
                        parts = t_start.split(":")
                        if len(parts) == 3:
                            s = float(parts[0])*3600 + float(parts[1])*60 + float(parts[2].replace(",", "."))
                        elif len(parts) == 2:
                            s = float(parts[0])*60 + float(parts[1].replace(",", "."))
                        text = lines[i+1].strip() if i+1 < len(lines) else ""
                        if text:
                            words.append({"text": text, "offset_s": s})
            with open(json_out, 'w') as f:
                json.dump(words, f)

def generate_graphics():
    if not os.path.exists(f"{SOURCES}/binary_split.mp4"):
        print("Generating procedural binary split animation...")
        run(["python3", f"{PROJ}/render_lib.py", f"{SOURCES}/binary_split.mp4"])
    
    # Generate background music (simple drone/pad)
    if not os.path.exists(f"{SYNTH}/bgm.wav"):
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=55:duration=120", "-f", "lavfi", "-i", "sine=frequency=82.5:duration=120", "-f", "lavfi", "-i", "anoisesrc=c=brown:d=120:a=0.1", "-filter_complex", "[0:a][1:a][2:a]amix=inputs=3,volume=0.3", f"{SYNTH}/bgm.wav"])

    # Generate SFX using gen_sfx
    if not os.path.exists(f"{SYNTH}/sfx.wav"):
        print("Generating SFX...")
        run(["python3", f"{PROJ}/gen_sfx.py"])

def get_audio_duration(file):
    if not os.path.exists(file): return 0
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file], capture_output=True, text=True)
    if res.stdout.strip():
        return float(res.stdout.strip())
    return 0

def build_video():
    print("Building final video...")
    
    # Calculate timings
    timings = {}
    curr_time = 0.0
    concat_filter = ""
    inputs = []
    idx = 0
    
    for k in sorted(SCRIPT.keys()):
        mp3 = f"{SYNTH}/{k}_voice.mp3"
        dur = get_audio_duration(mp3)
        timings[k] = curr_time
        curr_time += dur
        inputs.extend(["-i", mp3])
        concat_filter += f"[{idx}:a]"
        idx += 1
        
    concat_filter += f"concat=n={len(SCRIPT)}:v=0:a=1[a_vo];"
    
    total_dur = curr_time + 1.0 # 1 second padding

    # Create empty audio file just in case
    # Combine BGM, SFX, and VO
    bgm = f"{SYNTH}/bgm.wav"
    sfx = f"{SYNTH}/sfx.wav"
    
    inputs.extend(["-i", bgm, "-i", sfx])
    idx_bgm = idx
    idx_sfx = idx + 1
    
    # Audio complex filter
    # Compress/limit the voice over
    a_filter = concat_filter
    a_filter += f"[a_vo]acompressor=threshold=-12dB:ratio=4:attack=5:release=50,volume=1.5[a_vo_comp];"
    # Mix
    a_filter += f"[{idx_bgm}:a]volume=0.2[a_bgm]; [{idx_sfx}:a]volume=0.8[a_sfx];"
    a_filter += f"[a_vo_comp][a_bgm][a_sfx]amix=inputs=3:duration=shortest,loudnorm=I=-16:LRA=11:TP=-1.5[a_out]"

    # Video mapping based on time
    # Shot list:
    # 0 - clip1 (s01, s02)
    # 1 - clip2 (s03)
    # 2 - clip3 (s04)
    # 3 - clip4 (s05)
    # 4 - clip5 (s06, s07)
    # 5 - clip1 (s08, s09)
    # 6 - binary_split (s10, s11)
    # 7 - clip1 (s12)
    
    shots = [
        {"file": f"{SOURCES}/clip1_bh_orbit.mp4", "start": timings["s01"], "end": timings["s03"]},
        {"file": f"{SOURCES}/clip2_tde_shred.mp4", "start": timings["s03"], "end": timings["s04"]},
        {"file": f"{SOURCES}/clip3_tde_disk.mp4", "start": timings["s04"], "end": timings["s05"]},
        {"file": f"{SOURCES}/clip4_tde_partial.mp4", "start": timings["s05"], "end": timings["s06"]},
        {"file": f"{SOURCES}/clip5_tde_fading.mov", "start": timings["s06"], "end": timings["s08"]},
        {"file": f"{SOURCES}/clip1_bh_orbit.mp4", "start": timings["s08"], "end": timings["s10"]},
        {"file": f"{SOURCES}/binary_split.mp4", "start": timings["s10"], "end": timings["s12"]},
        {"file": f"{SOURCES}/clip1_bh_orbit.mp4", "start": timings["s12"], "end": total_dur}
    ]
    
    v_inputs = []
    v_filter = ""
    idx_v = idx + 2
    
    for i, shot in enumerate(shots):
        if not os.path.exists(shot["file"]):
            print(f"Warning: {shot['file']} not found. Proceeding anyway, might fail.")
            
        v_inputs.extend(["-i", shot["file"]])
        dur = shot["end"] - shot["start"]
        # Use blurred background technique to maintain full landscape content in portrait mode
        vid = f"{idx_v+i}:v"
        v_filter += f"[{vid}]split[orig{i}][blur{i}];"
        v_filter += f"[blur{i}]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:20[bg{i}];"
        v_filter += f"[orig{i}]scale=1080:1920:force_original_aspect_ratio=decrease[fg{i}];"
        v_filter += f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=60,trim=0:{dur},setpts=PTS-STARTPTS[v{i}];"
        
    for i in range(len(shots)):
        v_filter += f"[v{i}]"
    v_filter += f"concat=n={len(shots)}:v=1:a=0[v_concat];"
    
    # Add captions via drawtext
    # Font path (fallback to standard sans)
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(font): font = "sans-serif" # ffmpeg fallback
    
    dt_filter = "[v_concat]"
    for i, (text, key, offset) in enumerate(CAPTIONS):
        t_start = timings[key] + offset
        t_end = t_start + 4.0 # default 4s duration
        if i < len(CAPTIONS) - 1 and CAPTIONS[i+1][1] == key:
            t_end = timings[key] + CAPTIONS[i+1][2]
        elif i < len(CAPTIONS) - 1:
            t_end = timings[CAPTIONS[i+1][1]]
        
        safe_text = esc_draw(text)
        # Add drawtext filter for this caption (Yellow text, black shadow, bottom center)
        dt_filter += f"drawtext=fontfile='{font}':text='{safe_text}':fontcolor=yellow:fontsize=48:box=1:boxcolor=black@0.6:boxborderw=10:x=(w-text_w)/2:y=h-250:enable='between(t,{t_start},{t_end})'"
        if i < len(CAPTIONS) - 1:
            dt_filter += ","
    
    dt_filter += "[v_out]"
    
    complex_filter = a_filter + ";" + v_filter + dt_filter
    
    cmd = ["ffmpeg", "-y", "-loglevel", "warning"]
    cmd.extend(inputs)
    cmd.extend(v_inputs)
    cmd.extend(["-filter_complex", complex_filter, "-map", "[v_out]", "-map", "[a_out]"])
    cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "19", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p"])
    cmd.extend([f"{PROJ}/eaten_star_9x16.mp4"])
    
    run(cmd)
    
if __name__ == "__main__":
    synthesize_audio()
    generate_graphics()
    build_video()
    print("Done! Check eaten_star_9x16.mp4")
