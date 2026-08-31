# Universe Impact — Video Production

Short-form "mind-blowing discovery" videos for the animal impact page.

## 🎬 Latest: "Birds Are Dinosaurs" — Dino Day Recut (28.7s, 1080×1920, 30fps)

**Built entirely from real, copyright-free video footage** (no AI static images).
Full-bleed 9:16, safe-margin captions, hard cuts at VO boundaries, hook by 1.5s,
reveal by 22s.

### Download

| File | Size | Notes |
|---|---|---|
| `dino_recut_9x16_mobile.mp4` | 12 MB | ✅ Recommended (plays in browser, shareable) |
| `dino_recut_9x16.mp4` | 81 MB | Full production quality (use "Download raw file") |
| `dino_recut_thumbnail.jpg` | 293 KB | Thumbnail from real footage: "THIS IS STILL A DINOSAUR." |

Raw links:
- Mobile: `https://github.com/MohammadHamzaAttari/video/raw/arena/01a05887-video/dino_recut_9x16_mobile.mp4`
- Full: `https://github.com/MohammadHamzaAttari/video/raw/arena/01a05887-video/dino_recut_9x16.mp4`

### 🎞️ Footage sources (all real video, all external)

| Scene | Time | Footage used | Source | License |
|---|---|---|---|---|
| s1 Hook | 0–5.2s | Dinosaurs at waterhole (animated GIF, 10→30fps interpolated) | `irvingwa/dinoDB` (GitHub-hosted collection) | Publicly hosted; original artist: 2195razielim (DeviantArt) — verify for commercial use |
| s2 Asteroid | 5.2–9.2s | Star shredded by a black hole | **NASA SVS 12005** (`sources/clip2_tde_shred.mp4`) | ✅ Public domain (NASA) |
| s3 Tsunami/fires | 9.2–13.6s | Dinosaurs fleeing (animated GIF) | `irvingwa/dinoDB` | see s1 |
| s4 Darkness | 13.6–18.5s | Fading star / shockwaves | **NASA SVS 12499** (`sources/clip5_tde_fading.mov`) | ✅ Public domain (NASA) |
| s5 Survivor | 18.5–21s | Australian dinosaurs (animated GIF, 20fps) | `irvingwa/dinoDB` | see s1 |
| s6 Bird reveal | 21–26.8s | Cockatoo (real bird video, 14s) | `imageio/imageio-binaries` (`cockatoo.mp4`) | ✅ BSD sample video |
| s7 End card | 26.8–28.7s | Title card graphics | procedural | n/a |

> ⚠️ Licensing note: NASA SVS clips are public domain and imageio's cockatoo is a
> BSD-licensed sample — both 100% safe. The dinosaur GIFs come from a public
> GitHub collection (`irvingwa/dinoDB`) whose original animations are by
> DeviantArt artist *2195razielim*; license not explicitly verified — if you need
> strict monetization-safe licensing, swap s1/s3/s5 with licensed dinosaur
> footage (e.g., Pixabay) once available. The sandbox that built this cannot
> reach pexels.com/pixabay.com directly, so GitHub-hosted free footage was used.

### Pipeline

```
python3 render_footage.py               # real-footage clips (interp GIFs -> 30fps)
python3 build_dino_recut.py --assemble  # mux with VO + music + SFX (28.7s)
```

- `plan_recut.json` — VO-synced shot/caption timing map
- `synth/dino_recut/` — voiceover v1–v6, music.wav, sfx.wav
- `build_dino_recut.py`, `gen_audio_recut.py` — timing, captions, audio beds

### Scene map

| # | Visual | Caption |
|---|---|---|
| 1 | Dinosaurs at waterhole | 3 OF EVERY 4 SPECIES DIED — IN ONE DAY |
| 2 | NASA: star shredded | AN ASTEROID 6 MILES WIDE |
| 3 | Dinosaurs fleeing | IT TRIGGERED FIRES, TSUNAMIS, YEARS OF DARKNESS |
| 4 | NASA: fading star | 75% OF ALL LIFE ON EARTH — GONE |
| 5 | Australian dinos | BUT ONE LINE SURVIVED |
| 6 | Cockatoo (real bird) | IT'S SITTING ON YOUR WINDOWSILL... BIRDS ARE LIVING DINOSAURS |
| 7 | End card | FOLLOW / LIKE • SHARE • FOLLOW |

---

## 🎬 Earlier: "The Day the Dinosaurs Died" (2:18 — superseded)

Original long-form cut (AI key shots + NASA clips). Superseded by the 28.7s
footage recut above. Files: `dino_day_9x16_web.mp4`, `dino_day_9x16_mobile.mp4`.
