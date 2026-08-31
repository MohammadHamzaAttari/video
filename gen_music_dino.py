#!/usr/bin/env python3
"""Epic minimal-score generator: sub-braams, tension risers, pulse, airy pad, taiko hits."""
import json, wave, os
import numpy as np
from scipy import signal
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SYNTH = os.path.join(ROOT, "synth", "dino")
SR = 48000
PLAN = json.load(open(os.path.join(ROOT, "plan.json")))

def place(t0, sig, mix):
    i0 = int(t0 * SR); i1 = min(i0 + len(sig), len(mix))
    if i1 > i0:
        mix[i0:i1] += sig[:i1 - i0]

def env_ar(n, a, r):
    e = np.ones(n)
    ea = min(a, n); er = min(r, n)
    e[:ea] = np.linspace(0, 1, ea)
    e[-er:] *= np.linspace(1, 0, er)
    return e

def braam(t0, dur=4.0, f0=46, f1=33, gain=0.9):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sig = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph + 0.7)) / 1.75
    sig *= env_ar(n, int(0.08 * SR), int(0.9 * SR))
    sig *= (0.6 + 0.4 * np.sin(2 * np.pi * 0.35 * t + 1.0))
    return t0, sig * gain

def riser(t0, dur=3.2, gain=0.5, f0=90, f1=900):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(t0 * 1000) + 5)
    noise = rng.normal(0, 1, n)
    seg = int(0.04 * SR)
    freqs = np.logspace(np.log10(f0), np.log10(f1), max(1, n // seg))
    out = np.zeros(n)
    for i in range(0, n - seg, seg):
        f = freqs[min(i // seg, len(freqs) - 1)]
        b, a = signal.butter(2, [max(50, f * 0.6) / (SR / 2), min(0.49 * SR, f * 1.4) / (SR / 2)], btype="band")
        out[i:i + seg] = signal.lfilter(b, a, noise[i:i + seg])
    out *= (np.arange(n) / n) ** 2.2
    out *= env_ar(n, int(0.03 * SR), int(0.15 * SR))
    return t0, out * gain

def taiko(t0, gain=0.55, f0=70, f1=42):
    dur = 1.6; n = int(dur * SR); t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-4.2 * t / dur)
    sig += np.random.default_rng(int(t0)).normal(0, 1, n) * np.exp(-30 * t) * 0.4
    return t0, sig * gain

def pulse(t0, dur=2.0, bpm=96, gain=0.30):
    n = int(dur * SR); t = np.arange(n) / SR
    beat = 60.0 / bpm
    sig = np.zeros(n)
    k = 0
    while k < dur:
        i = int(k * SR)
        if i < n:
            hn = int(0.18 * SR)
            if i + hn > n: hn = n - i
            sig[i:i + hn] += np.sin(2 * np.pi * 88 * np.arange(hn) / SR) * np.exp(-np.arange(hn) / (0.05 * SR))
        k += beat / 2
    return t0, sig * gain

def pad(t0, dur, gain=0.16, f=110.0):
    n = int(dur * SR); t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.5 * t + 1.1) + 0.4 * np.sin(2 * np.pi * f * 2.0 * t + 2.2)
    sig /= 2.0
    L = 4096
    win = np.hanning(L)
    sig = np.convolve(sig, win / win.sum(), mode="same")
    sig *= env_ar(n, int(0.8 * SR), int(1.2 * SR))
    sig *= (0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t))
    return t0, sig * gain

def main():
    s = PLAN["starts"]; total = PLAN["total"]
    T = int(total * SR) + SR
    mix = np.zeros(T)
    keys = sorted(s)
    # --- structure ---
    braams = [("s01", 0.2, 4.5, 0.55), ("s01", 6.8, 4.5, 0.5), ("s03", 7.0, 4.0, 0.55),
              ("s04", 0.5, 3.0, 0.6), ("s05", 3.0, 4.0, 0.55), ("s06", 12.6, 4.0, 0.6),
              ("s07", 0.2, 3.2, 0.5), ("s07", 10.5, 3.0, 0.45)]
    for k, off, dur, g in braams:
        place(s[k] + off, braam(s[k] + off, dur=dur, gain=g)[1], mix)
    risers = [("s01", 0.0, 4.5, 0.5), ("s03", 0.2, 6.0, 0.55), ("s04", 8.0, 4.5, 0.6),
              ("s04", 12.5, 6.0, 0.75), ("s06", 7.5, 6.0, 0.55), ("s06", 15.5, 4.0, 0.6),
              ("s07", 0.0, 3.0, 0.5), ("s08", 0.0, 2.0, 0.3)]
    for k, off, dur, g in risers:
        place(s[k] + off, riser(s[k] + off, dur=dur, gain=g)[1], mix)
    taikos = [("s01", 5.2), ("s03", 13.5), ("s04", 12.5), ("s05", 20.3), ("s06", 16.5), ("s07", 0.0), ("s07", 4.4)]
    for k, off in taikos:
        place(s[k] + off, taiko(s[k] + off)[1], mix)
    for k in keys:
        dur = s[k] + PLAN["durations"][k] - s[k]
        place(s[k], pad(s[k], dur + 1.0, gain=0.13)[1], mix)
    # heart pulse under title
    place(PLAN["title_start"], pulse(PLAN["title_start"], PLAN["title_dur"] + 0.6, gain=0.34)[1], mix)
    # final push
    place(s["s08"] + 4.5, braam(s["s08"] + 4.5, dur=4.5, f0=58, f1=36, gain=0.5)[1], mix)
    place(s["s08"] + 4.5, riser(s["s08"] + 4.5, dur=3.0, f0=100, f1=700, gain=0.4)[1], mix)
    mix = np.clip(mix, -1, 1)
    fade = int(1.2 * SR)
    if fade < len(mix):
        mix[-fade:] *= np.linspace(1, 0, fade)
    st = np.stack([mix, mix], -1)
    wavfile.write(os.path.join(SYNTH, "music.wav"), SR, (st * 32767).astype("<i2"))
    print("music.wav", total, "s")

if __name__ == "__main__":
    main()
