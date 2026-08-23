#!/usr/bin/env python3
import os
import urllib.request

DEST = "/home/hamza/Videos/eaten_star/sources"
os.makedirs(DEST, exist_ok=True)

headers = {'User-Agent': 'Mozilla/5.0'}

assets = [
    {
        "name": "clip1_bh_orbit.mp4",
        "url": "https://svs.gsfc.nasa.gov/vis/a010000/a014600/a014620/1-Orbiting_a_bare_black_hole-4K.mp4"
    },
    {
        "name": "clip2_tde_shred.mp4",
        "url": "https://svs.gsfc.nasa.gov/vis/a010000/a012000/a012005/12005_Swift_Tidal_Music_MPEG4_1920X1080_2997.mp4"
    },
    {
        "name": "clip3_tde_disk.mp4",
        "url": "https://svs.gsfc.nasa.gov/vis/a010000/a014600/a014620/3-Tidal_disruption_by_black_hole-4K.mp4"
    },
    {
        "name": "clip4_tde_partial.mp4",
        "url": "https://svs.gsfc.nasa.gov/vis/a010000/a014000/a014000/1Msol_Ryu_TDE_4k_1.mp4"
    },
    {
        "name": "clip5_tde_fading.mov",
        "url": "https://svs.gsfc.nasa.gov/vis/a010000/a012400/a012499/Shocks_at_Apocenter_Animation_FINAL-1080.mov"
    }
]

for item in assets:
    target_path = os.path.join(DEST, item["name"])
    if os.path.exists(target_path):
        print(f"Already downloaded: {item['name']}")
        continue
    print(f"Downloading {item['name']}...")
    try:
        req = urllib.request.Request(item["url"], headers=headers)
        with urllib.request.urlopen(req) as resp, open(target_path, 'wb') as out_f:
            out_f.write(resp.read())
        print(f"  Saved {item['name']} ({os.path.getsize(target_path)} bytes)")
    except Exception as e:
        print(f"  Error downloading {item['name']}: {e}")
