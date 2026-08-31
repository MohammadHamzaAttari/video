# Universe Impact — Video Production

Short-form "mind-blowing discovery" videos for the animal impact page.

## 🎬 Latest: "Birds Are Dinosaurs" — Dino Day Recut (28.7s, 1080×1920, 30fps)

The production-ready recut per the performance spec: **27–29s, full-bleed (no
letterboxing), safe-margin captions (≥80px), hard cuts, hook text in frame by
1.5s, reveal ("birds ARE dinosaurs") by second 22**.

### Download

| File | Size | Notes |
|---|---|---|
| `dino_recut_9x16_mobile.mp4` | 6.6 MB | ✅ Recommended (plays in browser, shareable) |
| `dino_recut_9x16.mp4` | 57 MB | Full production quality (use "Download raw file") |
| `dino_recut_thumbnail.jpg` | 348 KB | Thumbnail: "THIS IS STILL A DINOSAUR." |
| `dino_recut_contact.jpg` | — | 8-frame contact sheet |

Raw links:
- Mobile: `https://github.com/MohammadHamzaAttari/video/raw/arena/01a05887-video/dino_recut_9x16_mobile.mp4`
- Full: `https://github.com/MohammadHamzaAttari/video/raw/arena/01a05887-video/dino_recut_9x16.mp4`

### Scene map (VO-driven cuts)

| Scene | Time | Visual | Caption |
|---|---|---|---|
| 1 | 0–5.2s | T-Rex god-rays, push-in | 3 OF EVERY 4 SPECIES DIED — IN ONE DAY |
| 2 | 5.2–9.2s | Asteroid full-frame, whip | AN ASTEROID 6 MILES WIDE |
| 3 | 9.2–13.6s | Tsunami, slow zoom | IT TRIGGERED FIRES, TSUNAMIS, YEARS OF DARKNESS |
| 4 | 13.6–18.5s | Ash wasteland, drift | 75% OF ALL LIFE ON EARTH — GONE |
| 5 | 18.5–21s | Feathered dino→bird morph, punch-in | BUT ONE LINE SURVIVED |
| 6 | 21–26.8s | Pigeon, slow push-in + hold | IT'S SITTING ON YOUR WINDOWSILL... BIRDS ARE LIVING DINOSAURS |
| 7 | 26.8–28.7s | End card | FOLLOW / LIKE • SHARE • FOLLOW |

### Pipeline

```
python3 build_dino_recut.py --plan      # probe VO, compute sync timings
python3 build_dino_recut.py --render    # full-bleed scene clips (no letterbox)
python3 gen_audio_recut.py              # music + SFX beds
python3 build_dino_recut.py --assemble  # final mux (hard cuts)
```

---

## 🎬 Earlier: "The Day the Dinosaurs Died" (2:18 — superseded by the recut)

The original long-form cut. Strong concept, but 138s exceeded the 25–30s
retention spec — see the recut above for the shipped version.

- `dino_day_9x16_mobile.mp4` (30 MB) / `dino_day_9x16_web.mp4` (93 MB)
- Pipeline: `build_dino_day.py`, `render_cgi.py`, `gen_music_dino.py`, `gen_sfx_dino.py`

