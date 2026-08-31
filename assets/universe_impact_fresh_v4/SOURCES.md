# Universe Impact — fresh 3D v4 source notes

## v4 visual-source rule

This corrective build has **35 placed moving visual source assets**. The timeline
guard in `build_universe_impact_fresh_3d_v4.py` refuses to render when any source
key, resolved local path, or SHA-256 content hash occurs more than once. This
means no background visual or clip can recur in the finished v4 timeline.

- **32 original one-time 3D-style video tracks** are rendered freshly by
  `fresh_3d_visuals_v4.py`. Each has its own output filename, seed, animated
  geometry / particle state, camera treatment, and full-file SHA-256 check.
- **3 retained fresh public-domain NASA animated files** are used *once each*:
  `nasa_svs14132_supermassive_binary_simulation.gif`,
  `nasa_svs14132_disk_and_corona.gif`, and
  `nasa_svs14132_lmxb_outburst.gif`. They remain stored in
  `assets/universe_impact_fresh_v3/` as the originally downloaded, documented
  production source assets. The v4 timeline does not copy or repeat them.
- **No legacy v2 source** under `sources/` is read by the v4 build.
- **No rendered visual MP4 from v3** is read by the v4 build.

## External public-domain source credits

1. **Supermassive Binary Black Hole Simulation** — NASA's Goddard Space Flight
   Center. Source: NASA SVS 14132; Commons public-domain file page:
   <https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Supermassive_Binary_Black_Hole_Simulation).gif>
2. **Disk and Corona** — Aurore Simonnet and NASA's Goddard Space Flight Center.
   Source: NASA SVS 14132; Commons public-domain file page:
   <https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Disk_and_Corona).gif>
3. **LMXB Illustration — Black Hole Outburst** — NASA/Goddard Space Flight
   Center/Conceptual Image Lab. Source: NASA SVS 14132; Commons public-domain
   file page:
   <https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_LMXB_Illustration).gif>

NASA SVS: <https://svs.gsfc.nasa.gov/14132/>. NASA SVS says its content is
public domain unless otherwise noted. Retain attribution where practical.

## Audio lock

`assets/universe_impact_fresh_v3/audio_level_locked_v3_reference.m4a` is the
reviewed v3 program's AAC reference. v4 stream-copies it without any mix,
normalization, gain, compressor, limiter, or re-encoding. Its approximately
-16 LUFS integrated loudness is measured in the v4 manifest. The mandated
2.8-second final end card is intentionally silent after the locked program.
