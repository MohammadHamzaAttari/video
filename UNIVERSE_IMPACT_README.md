# Universe Impact — Black-Hole Cosmology Reel

## Active deliverable: fresh-source / original-3D v3

The active production package is a vertical, Facebook-ready **Universe Impact** Reel exploring whether the Big Bang could be the inside view of a black hole. It explicitly frames that as a **hypothesis, not established fact**.

| Deliverable | Path |
| --- | --- |
| Final Reel | `deliverables/universe_impact_black_hole_reel_fresh_3d_v3.mp4` |
| Cover | `deliverables/universe_impact_black_hole_cover_fresh_3d_v3.jpg` |
| Upload captions | `deliverables/universe_impact_black_hole_reel_fresh_3d_v3.srt` |
| Facebook copy / publishing notes | `deliverables/UNIVERSE_IMPACT_FACEBOOK_POST_FRESH_3D_V3.md` |
| Source / cut / render manifest | `deliverables/universe_impact_black_hole_reel_fresh_3d_v3_manifest.json` |
| New source-asset provenance | `assets/universe_impact_fresh_v3/SOURCES.md` |

**Delivery format:** 1080 × 1920 vertical, H.264 High / yuv420p, AAC stereo 48 kHz, 30 fps, about 77.9 seconds.

## What is different in v3

This is a real source replacement, not a new crop of the old cut.

1. **No v2 source clip is read or used.** The v3 build intentionally never opens `sources/clip1_bh_orbit.mp4`, `clip2_tde_shred.mp4`, `clip3_tde_disk.mp4`, `clip4_tde_partial.mp4`, or `clip5_tde_fading.mov`.
2. **Three newly acquired public-domain animated visual clips** are included as versioned source assets: NASA SVS 14132’s Supermassive Binary Black Hole Simulation, Disk and Corona, and LMXB Illustration. Their moving frames are retained in the edit; no frame dump or static background carries their story beats.
3. **Six original dynamic 3D tracks** are newly rendered for Universe Impact: an orbiting/lensing-style accretion disk, collapse-to-bounce tunnel, cosmic-web flight, rotating pattern sphere, warped-spacetime grid, and cosmic-dawn finale. They use local geometry, particles, perspective camera motion, glow, and an original edit—not downloaded old clips.
4. The Reel contains **34 short moving passages** (about 2.1–2.6 seconds each), animated portrait reframing / source portals, short kinetic headline cards, and an original generated score with cut accents.
5. All source audio is absent or stripped. No external music, source narration, NASA logo, or prior v2 video footage is used.
6. The copy keeps the evidence-first resolution: a viable model needs a **unique, testable observational fingerprint**; there is no claim that NASA, JWST, CMB data, or gravitational-wave data has established black-hole cosmology.

### Rights and source scope

The three external animated files are tracked in `assets/universe_impact_fresh_v3/` with acquisition hashes, source URLs, individual credit lines, and public-domain rationale. Their Commons file pages classify the selected NASA SVS works as public domain in the United States, and NASA SVS states its content is public domain unless otherwise noted.

## Re-render v3

Install dependencies once:

```bash
python3 -m pip install -r requirements-universe-impact.txt
```

The complete fresh v3 build is:

```bash
python3 build_universe_impact_fresh_3d_v3.py --render-only --force
```

This command renders the six original video tracks, re-edits the three tracked public-domain animated sources, burns captions, generates original music, muxes the final Reel, makes the cover, writes the SRT / publishing pack / manifest, and runs decode validation.

`FFMPEG_BIN=/path/to/ffmpeg` optionally selects a specific FFmpeg executable. If system FFmpeg is missing, the script tries `imageio-ffmpeg`.

### Required Edge-TTS configuration

The v3 build script retains the requested settings and a `socket.getaddrinfo` / `aiohttp` `ThreadedResolver` workaround for `speech.platform.bing.com`:

```text
engine: edge-tts
voice:  en-US-ChristopherNeural
rate:   +0%
```

On a network-permitted host, generate narration before rendering:

```bash
python3 build_universe_impact_fresh_3d_v3.py --voice-only --force
python3 build_universe_impact_fresh_3d_v3.py --render-only --force
```

The current sandbox cannot connect to the Edge endpoint, so the production render uses the existing local narration cache whose copy is identical to v3’s script. The script contains the exact requested configuration, but this sandbox cannot independently authenticate the cached speaker identity. Regenerate with `--voice-only` on an Edge-permitted host before publicly claiming that strict voice verification.

## Scientific editorial guardrail

“Black-hole cosmology” remains speculative. Keep “hypothesis,” “conceptual model,” and “no direct proof yet” in the post copy and replies. Do not promote the Reel as evidence that NASA, JWST, or any observatory has proved humanity lives inside a black hole.

## Prior package

The former motion-first v2 artifacts and `build_universe_impact_dynamic_v2.py` remain in the repository as an archived fallback. They are deliberately not inputs to v3.
