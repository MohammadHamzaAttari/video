# Universe Impact — Black-Hole Cosmology Reel

## Active deliverable: motion-first dynamic v2

The current delivery is a vertical, Facebook-ready **Universe Impact** Reel that asks whether the Big Bang could be the inside of a black hole — while clearly labeling that premise as a **hypothesis, not established fact**.

- **Video:** `deliverables/universe_impact_black_hole_reel_dynamic_v2.mp4`
- **Cover:** `deliverables/universe_impact_black_hole_cover_dynamic_v2.jpg`
- **Upload captions:** `deliverables/universe_impact_black_hole_reel_dynamic_v2.srt`
- **Facebook copy / provenance:** `deliverables/UNIVERSE_IMPACT_FACEBOOK_POST_DYNAMIC_V2.md`
- **Shot-level render manifest:** `deliverables/universe_impact_black_hole_reel_dynamic_v2_manifest.json`
- **Format:** 1080 × 1920 vertical, H.264/AAC, 30 fps, approximately 78 seconds

## What changed in v2

This is not a static-image refresh. It replaces the earlier artist-concept/image-led narrative backgrounds with **34 short moving editorial extracts** from NASA Scientific Visualization Studio source footage.

1. The edit changes visual shots roughly every 2.1–2.6 seconds.
2. It combines immersive portrait crops with moving “science-feed” frames over a moving blurred source background — preserving wide NASA visualizations without frozen side bars.
3. It uses only motion footage for story beats; no still artwork carries a section of narration.
4. It adds short kinetic headline and evidence cards rather than holding a single title unchanged through an entire spoken scene.
5. It retains the original score / impact accents, on-screen **“Hypothesis / Not Established Fact”** disclosure, SRT captions, visual attribution, and evidence-first ending.
6. Every NASA source-audio track is stripped. The edit uses only the project’s original generated score and accents, avoiding any music attached to the source media.

### NASA motion-source pages

- **Isolated Black Hole Visualization** — orbiting a bare black hole and tidal-disruption visualization: https://svs.gsfc.nasa.gov/14620/
- **Massive Black Hole Shreds Passing Star**: https://svs.gsfc.nasa.gov/12005/
- **Supercomputer Simulations Test Star-destroying Black Holes**: https://svs.gsfc.nasa.gov/14000/
- **Swift Charts a Star’s “Death Spiral” into Black Hole**: https://svs.gsfc.nasa.gov/12499/

NASA SVS says its visualizations are public domain unless otherwise noted. See the v2 posting pack and manifest for the exact downloaded asset URLs, credits, and the timeline of every extract.

## Re-rendering v2

Install the small dependencies once:

```bash
python3 -m pip install -r requirements-universe-impact.txt
```

Render from an existing narration cache:

```bash
python3 build_universe_impact_dynamic_v2.py --render-only --force
```

The dynamic script intentionally retains the requested Edge-TTS configuration and the `socket.getaddrinfo` / `aiohttp` resolver workaround for `speech.platform.bing.com`:

```text
engine: edge-tts
voice:  en-US-ChristopherNeural
rate:   +0%
```

On a network-permitted host, create compliant narration first, then render:

```bash
python3 build_universe_impact_dynamic_v2.py --voice-only --force
python3 build_universe_impact_dynamic_v2.py --render-only --force
```

`FFMPEG_BIN=/path/to/ffmpeg` optionally selects a specific FFmpeg executable; `imageio-ffmpeg` is used automatically when system FFmpeg is not available.

> **Voice verification:** The code preserves the exact requested Christopher setting. The current sandbox could not reach Edge TTS, so its existing narration cache cannot independently be certified here as a strict Christopher render. Regenerate the cache on an Edge-permitted host before publicly claiming that exact voice identity.

## Editorial guardrail

“Black-hole cosmology” remains speculative. The Reel intentionally does **not** claim that NASA, JWST, or any observatory has proved humanity lives inside a black hole. It states that a serious model would need a unique observational fingerprint — for example in the CMB or primordial gravitational-wave data — that rival explanations cannot reproduce.
