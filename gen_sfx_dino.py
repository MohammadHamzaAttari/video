#!/usr/bin/env python3
"""SFX bed synced to the VO beats: impact booms, whooshes, heartbeats, glass chime, bird chirp."""
import json, os
import numpy as np
from scipy.io import wavfile
from scipy import signal

ROOT = os.path.dirname(os.path.abspath(__file__))
SYNTH = os.path.join(ROOT, "synth", "dino")
SR = 48000
PLAN = json.load(open(os.path.join(ROOT, "plan.json")))

def place(t0, sig, mix):
    i0 = int(t0 * SR); i1 = min(i0 + len(sig), len(mix))
    if i1 > i0:
        mix[i0:i1] += sig[:i1 - i0]

def boom(t0, dur=2.4, gain=0.85, f0=80, f1=32):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-3.2 * t / dur)
    sig += np.sin(2 * np.pi * 34 * t) * np.exp(-6 * t / dur) * 0.5
    sig += np.random.default_rng(int(t0 * 1000)).normal(0, 1, n) * np.exp(-14 * t / dur) * 0.4
    return sig * gain

def whoosh(t0, dur=1.1, gain=0.5, up=True):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(t0 * 1000) + 3)
    noise = rng.normal(0, 1, n)
    seg = int(0.05 * SR)
    f0, f1 = (700, 5200) if up else (5200, 700)
    out = np.zeros(n)
    for i in range(0, n - seg, seg):
        f = f0 + (f1 - f0) * (i / (n - seg))
        b, a = signal.butter(2, [max(60, f * 0.7) / (SR / 2), min(0.49 * SR, f * 1.3) / (SR / 2)], btype="band")
        out[i:i + seg] = signal.lfilter(b, a, noise[i:i + seg])
    out *= np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return out * gain

def heartbeat(t0, gain=0.8, beats=2, bpm=66):
    dur = beats * 60.0 / bpm
    n = int(dur * SR)
    sig = np.zeros(n)
    for b in range(beats):
        start = b * 60.0 / bpm
        for k, off in enumerate([0.0, 0.14]):
            i0 = int((start + off) * SR)
            hn = int(0.16 * SR)
            if i0 + hn > n: continue
            tt = np.arange(hn) / SR
            sig[i0:i0 + hn] += np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 26) * (1.0 if k == 0 else 0.7)
    return sig * gain

def chime(t0, gain=0.35, f=1320):
    dur = 2.0; n = int(dur * SR); t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f * t) * np.exp(-2.4 * t)
    sig += 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-3.5 * t)
    return sig * gain

def chirp(t0, gain=0.4, f0=3100, f1=4300):
    dur = 0.9; n = int(dur * SR); t = np.arange(n) / SR
    f = f0 + (f1 - f0) * np.clip((t - 0.1) / 0.5, 0, 1)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-3.0 * t)
    return sig * gain

def subdrop(t0, gain=0.6, f0=120, f1=30, dur=1.4):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-2.5 * t) * gain

def riser_sfx(t0, dur=3.0, gain=0.5, f0=100, f1=950):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(t0 * 1000) + 9)
    noise = rng.normal(0, 1, n)
    seg = int(0.04 * SR)
    freqs = np.logspace(np.log10(f0), np.log10(f1), max(1, n // seg))
    out = np.zeros(n)
    for i in range(0, n - seg, seg):
        f = freqs[min(i // seg, len(freqs) - 1)]
        b, a = signal.butter(2, [max(50, f * 0.6) / (SR / 2), min(0.49 * SR, f * 1.4) / (SR / 2)], btype="band")
        out[i:i + seg] = signal.lfilter(b, a, noise[i:i + seg])
    out *= (np.arange(n) / n) ** 2.0
    return out * gain

def main():
    s = PLAN["starts"]; total = PLAN["total"]
    mix = np.zeros(int(total * SR) + SR)
    # hook
    place(s["s01"] + 0.1, boom(s["s01"] + 0.1, dur=3.0, gain=0.8, f0=90, f1=30), mix)
    place(s["s01"] + 5.1, whoosh(s["s01"] + 5.1, dur=1.2, gain=0.55), mix)
    place(s["s01"] + 5.15, boom(s["s01"] + 5.15, dur=2.6, gain=0.7, f0=70, f1=28), mix)
    place(s["s01"] + 5.2, heartbeat(s["s01"] + 5.2, gain=0.7, beats=3, bpm=72), mix)
    # iridium
    place(s["s02"] + 2.0, whoosh(s["s02"] + 2.0, dur=1.0, gain=0.4), mix)
    # alvarez
    place(s["s03"] + 7.0, riser_sfx(s["s03"] + 7.0, dur=4.0, gain=0.5), mix)
    place(s["s03"] + 13.6, boom(s["s03"] + 13.6, dur=2.6, gain=0.85), mix)
    # crater / killer
    place(s["s04"] + 0.6, whoosh(s["s04"] + 0.6, dur=1.2, gain=0.5), mix)
    place(s["s04"] + 8.2, subdrop(s["s04"] + 8.2, gain=0.6), mix)
    place(s["s04"] + 12.4, riser_sfx(s["s04"] + 12.4, dur=5.8, gain=0.75), mix)
    place(s["s04"] + 18.2, boom(s["s04"] + 18.2, dur=3.4, gain=0.95, f0=85, f1=26), mix)
    place(s["s04"] + 18.3, heartbeat(s["s04"] + 18.3, gain=0.9, beats=2, bpm=60), mix)
    # tanis
    place(s["s05"] + 2.0, whoosh(s["s05"] + 2.0, dur=1.0, gain=0.4), mix)
    place(s["s05"] + 8.2, whoosh(s["s05"] + 8.2, dur=1.2, gain=0.5), mix)
    place(s["s05"] + 20.2, boom(s["s05"] + 20.2, dur=2.2, gain=0.65, f0=75, f1=30), mix)
    # the day
    place(s["s06"] + 1.2, boom(s["s06"] + 1.2, dur=3.0, gain=0.9, f0=88, f1=28), mix)
    place(s["s06"] + 7.8, riser_sfx(s["s06"] + 7.8, dur=3.5, gain=0.55), mix)
    place(s["s06"] + 8.0, boom(s["s06"] + 8.0, dur=2.8, gain=0.8), mix)
    place(s["s06"] + 16.2, boom(s["s06"] + 16.2, dur=3.4, gain=0.85, f0=60, f1=26), mix)
    place(s["s06"] + 16.3, heartbeat(s["s06"] + 16.3, gain=0.75, beats=2, bpm=56), mix)
    # survivors
    place(s["s07"] + 4.5, whoosh(s["s07"] + 4.5, dur=1.3, gain=0.5, up=True), mix)
    place(s["s07"] + 6.8, chime(s["s07"] + 6.8, gain=0.4, f=880), mix)
    place(s["s07"] + 10.6, chime(s["s07"] + 10.6, gain=0.45, f=1174), mix)
    # birds
    place(s["s08"] + 0.3, chirp(s["s08"] + 0.3, gain=0.45, f0=2900, f1=4100), mix)
    place(s["s08"] + 2.6, chirp(s["s08"] + 2.6, gain=0.4, f0=3300, f1=4600), mix)
    place(s["s08"] + 4.4, chirp(s["s08"] + 4.4, gain=0.4, f0=2700, f1=3900), mix)
    place(s["s08"] + 7.0, boom(s["s08"] + 7.0, dur=2.6, gain=0.6, f0=70, f1=28), mix)
    # title slam
    ts = PLAN["title_start"]
    place(ts, boom(ts, dur=2.8, gain=0.9, f0=95, f1=26), mix)
    place(ts + 0.05, heartbeat(ts + 0.05, gain=0.85, beats=2, bpm=58), mix)
    mix = np.clip(mix, -1, 1)
    fade = int(1.0 * SR)
    if fade < len(mix):
        mix[-fade:] *= np.linspace(1, 0, fade)
    st = np.stack([mix, mix], -1)
    wavfile.write(os.path.join(SYNTH, "sfx.wav"), SR, (st * 32767).astype("<i2"))
    print("sfx.wav written")

if __name__ == "__main__":
    main()
