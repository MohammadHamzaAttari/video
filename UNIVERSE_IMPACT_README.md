# Universe Impact — Black-Hole Cosmology Reel

This project turns the supplied black-hole concept into a new, Facebook-ready **Universe Impact** Reel:

- **Title:** *Could the Big Bang Be Inside a Black Hole? | Hypothesis, Not Proof*
- **Output:** `deliverables/universe_impact_black_hole_reel.mp4`
- **Format:** 1080 × 1920 vertical, H.264/AAC, 30 fps, approximately 78 seconds
- **Voice setting:** `edge-tts` · `en-US-ChristopherNeural` · `+0%`

## What makes this version distinct

1. It has an original evidence-first script, not a recycled caption track.
2. It carries a visible **“Hypothesis / Not Established Fact”** disclosure throughout.
3. It adds two original artist-concept visuals and a custom procedural **collapse → bounce → expanding-space** animation.
4. It includes original score / impact accents, concise burned-in headline cards, an uploadable SRT, a cover image, and a ready-to-paste Facebook publishing pack.
5. It credits the NASA Scientific Visualization Studio source footage used in the edit and does not use source-clip audio.

## Re-rendering

```bash
python3 -m pip install -r requirements-universe-impact.txt
python3 build_universe_impact_v1.py
```

The build script intentionally includes the `socket.getaddrinfo` and `aiohttp` resolver workaround for `speech.platform.bing.com`, as requested. If an execution environment blocks Edge TTS, generate the narration on a network-permitted machine first:

```bash
python3 build_universe_impact_v1.py --voice-only --force
# copy build_universe_impact/audio/ back if necessary
python3 build_universe_impact_v1.py --render-only --force
```

Set `FFMPEG_BIN=/path/to/ffmpeg` to use a specific ffmpeg binary. `imageio-ffmpeg` is used automatically when system ffmpeg is unavailable.

## Upload package

Open `deliverables/UNIVERSE_IMPACT_FACEBOOK_POST.md` for the Facebook caption, hashtag set, pinned-comment prompt, source notes, cover direction, and accessibility alt text.

## Editorial guardrail

“Black-hole cosmology” remains speculative. The reel intentionally does **not** claim that NASA, JWST, or any observatory has proved we live inside a black hole.
