#!/usr/bin/env python3
"""gen_audio_recut.py — music + SFX beds for the 28s recut (VO-synced beats)."""
import json, os
import numpy as np
from scipy.io import wavfile
from scipy import signal

ROOT = os.path.dirname(os.path.abspath(__file__))
SYNTH = os.path.join(ROOT, "synth", "dino_recut")
SR = 48000
PLAN = json.load(open(os.path.join(ROOT, "plan_recut.json")))

def place(t0, sig, mix):
    i0 = int(t0 * SR); i1 = min(i0 + len(sig), len(mix))
    if i1 > i0:
        mix[i0:i1] += sig[:i1 - i0]

def drone(t0, dur, gain=0.12, f=32.0):
    n = int(dur * SR); t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 1.5 * t + 0.8)
    sig *= np.minimum(t / (0.5 * SR), 1) * np.minimum((dur - t) / (0.5 * SR), 1)
    return sig * gain

def boom(t0, dur=1.8, gain=0.8, f0=75, f1=30):
    n = int(dur * SR); t = np.arange(n) / SR
    f = f0 * (f1 / f0) ** (t / dur)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-3.5 * t / dur)
    sig += np.random.default_rng(int(t0 * 1000)).normal(0, 1, n) * np.exp(-16 * t / dur) * 0.4
    return sig * gain

def whoosh(t0, dur=0.8, gain=0.5, f0=900, f1=4800):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(t0 * 1000) + 4)
    noise = rng.normal(0, 1, n)
    seg = int(0.04 * SR)
    out = np.zeros(n)
    for i in range(0, n - seg, seg):
        f = f0 + (f1 - f0) * (i / (n - seg))
        b, a = signal.butter(2, [max(60, f * 0.7) / (SR / 2), min(0.49 * SR, f * 1.3) / (SR / 2)], btype="band")
        out[i:i + seg] = signal.lfilter(b, a, noise[i:i + seg])
    out *= np.sin(np.pi * np.linspace(0, 1, n)) ** 2
    return out * gain

def roar(t0, dur=4.4, gain=0.5):
    """water roar: brown noise band-passed"""
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(t0 * 1000) + 8)
    noise = rng.normal(0, 1, n)
    b, a = signal.butter(2, [150 / (SR / 2), 900 / (SR / 2)], btype="band")
    sig = signal.lfilter(b, a, noise)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.5
    return sig * env * gain * 1.6

def wind(t0, dur=4.9, gain=0.35):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(t0 * 1000) + 12)
    noise = rng.normal(0, 1, n)
    b, a = signal.butter(2, [700 / (SR / 2), 3200 / (SR / 2)], btype="band")
    sig = signal.lfilter(b, a, noise)
    sig *= (0.7 + 0.3 * np.sin(2 * np.pi * 0.3 * t + 1.0))
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 1.2
    return sig * env * gain * 2.2

def riser(t0, dur=2.0, gain=0.5, f0=120, f1=900):
    n = int(dur * SR); t = np.arange(n) / SR
    rng = np.random.default_rng(int(t0 * 1000) + 16)
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

def piano_hit(t0, gain=0.5, f=440.0):
    """soft piano-ish pluck: fundamental + harmonics with fast decay"""
    dur = 3.0; n = int(dur * SR); t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * f * t) * np.exp(-1.8 * t)
           + 0.4 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-3.0 * t)
           + 0.2 * np.sin(2 * np.pi * f * 3.02 * t) * np.exp(-4.0 * t))
    return sig * gain

def sting(t0, gain=0.7):
    dur = 2.4; n = int(dur * SR); t = np.arange(n) / SR
    f = 90 * (28 / 90) ** (t / dur)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-3.0 * t / dur)
    sig += 0.3 * np.sin(2 * np.pi * 660 * t) * np.exp(-6 * t) * (t > 0.05)
    return sig * gain

def main():
    s = PLAN["starts"]
    total = PLAN["total"]
    T = int(total * SR) + SR
    music = np.zeros(T)
    sfx = np.zeros(T)
    # music bed
    place(0, drone(0, total, gain=0.13), music)
    place(s["v2"] - 0.2, riser(s["v2"] - 0.2, dur=1.6, gain=0.4), music)
    place(s["v5"] - 0.4, riser(s["v5"] - 0.4, dur=1.8, gain=0.55, f0=150, f1=1100), music)
    place(s["v6"] + 0.05, piano_hit(s["v6"] + 0.05, gain=0.5, f=440), music)
    place(s["v6"] + 0.9, piano_hit(s["v6"] + 0.9, gain=0.35, f=523.25), music)
    # sfx bed
    place(0, boom(0, dur=2.6, gain=0.55, f0=70, f1=30), sfx)          # low rumble open
    place(s["v2"] + 0.4, whoosh(s["v2"] + 0.4, gain=0.55), sfx)       # asteroid whip
    place(s["v2"] + 0.7, boom(s["v2"] + 0.7, dur=2.4, gain=0.9, f0=85, f1=26), sfx)  # impact
    place(s["v3"] + 0.1, roar(s["v3"] + 0.1, dur=min(4.0, s["v4"] - s["v3"]), gain=0.5), sfx)  # tsunami
    place(s["v4"] + 0.1, wind(s["v4"] + 0.1, dur=min(4.5, s["v5"] - s["v4"]), gain=0.4), sfx)  # ash wind
    place(s["v6"] - 0.15, riser(s["v6"] - 0.15, dur=1.0, gain=0.35), sfx)  # rise into reveal
    place(PLAN["scenes"][-1]["start"] + 0.05, sting(PLAN["scenes"][-1]["start"] + 0.05, gain=0.7), sfx)  # end sting
    for name, mix in [("music", music), ("sfx", sfx)]:
        mix = np.clip(mix, -1, 1)
        fade = int(0.6 * SR)
        if fade < len(mix):
            mix[-fade:] *= np.linspace(1, 0, fade)
        st = np.stack([mix, mix], -1)
        wavfile.write(os.path.join(SYNTH, f"{name}.wav"), SR, (st * 32767).astype("<i2"))
        print(f"{name}.wav written ({total:.2f}s)")

if __name__ == "__main__":
    main()
