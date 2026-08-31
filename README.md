# Universe Impact — Video Production

Short-form "mind-blowing discovery" videos for the animal impact page.

## 🎬 Latest video: "The Day the Dinosaurs Died" (2:18, 1080×1920, 30fps)

A history-discovery short about the asteroid impact 66 million years ago —
and the animal angle: every bird alive today is a dinosaur descendant.

### Download the final video

| File | Size | Best for |
|---|---|---|
| `dino_day_9x16_mobile.mp4` | 30 MB | ✅ Recommended download (plays/renders on GitHub, easy to share) |
| `dino_day_9x16_web.mp4` | 93 MB | Full production quality (use "Download raw file" button) |

Download links (right-click → Save As):
- Mobile: `https://github.com/MohammadHamzaAttari/video/raw/arena/01a05887-video/dino_day_9x16_mobile.mp4`
- Full quality: `https://github.com/MohammadHamzaAttari/video/raw/arena/01a05887-video/dino_day_9x16_web.mp4`
- Preview sheet: `dino_preview_contact.jpg`

> ⚠️ Note: GitHub can't render/preview files larger than 50 MB in the browser —
> if the file page looks broken, use the raw links above instead.

### Pipeline (style-matched to `build_eaten_star.py`)

```
python3 build_dino_day.py --plan      # measure VO, compute sync timings
python3 render_cgi.py                 # render all scene clips (Ken Burns + CGI)
python3 gen_music_dino.py             # epic score bed
python3 gen_sfx_dino.py               # beat-synced SFX
python3 build_dino_day.py --assemble  # final mux: VO + music + SFX + video
```

- `assets/dino/` — 10 AI cinematic key shots
- `synth/dino/` — voiceover (s01–s08), music.wav, sfx.wav
- `plan.json` — VO-synced shot/caption timing map
