#!/usr/bin/env python3
import json, wave, os, numpy as np
from scipy import signal

SR = 48000
PROJ = "/home/hamza/Videos/eaten_star"
SYNTH = f"{PROJ}/synth"
KEYS = ["s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08", "s09", "s10", "s11", "s12"]

def load_words(key):
    path = f"{SYNTH}/{key}_timing.json"
    if os.path.exists(path):
        d = json.load(open(path))
        return [(w['text'].lower(), w['offset_s']) for w in d]
    return []

WORDS = {k: load_words(k) for k in KEYS}

def get_durations():
    import subprocess
    offs = [0.0]
    for k in KEYS:
        mp3 = f"{SYNTH}/{k}_voice.mp3"
        d = 0.0
        if os.path.exists(mp3):
            out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", mp3], capture_output=True, text=True).stdout
            if out: d = float(out)
        else:
            d = 5.0
        offs.append(round(offs[-1] + d, 3))
    dur_total = round(offs[-1] + 0.5, 3)
    s = {k: offs[i] for i, k in enumerate(KEYS)}
    return dur_total, s

def boom(t0, dur=2.2, gain=0.9, f0=75, f1=35):
    n = int(dur*SR); t = np.arange(n)/SR
    f = f0*(f1/f0)**(t/dur)
    env = np.exp(-3.5*t/dur)
    sig = np.sin(2*np.pi*np.cumsum(f)/SR)*env
    sub = np.sin(2*np.pi*32*t)*np.exp(-5*t/dur)*0.6
    noise = np.random.default_rng(int(t0*1000)).normal(0,1,n)*np.exp(-12*t/dur)*0.5
    return t0, (sig+sub+noise)*gain

def whoosh(t0, dur=1.2, gain=0.5, hi=8000, lo=1000):
    n = int(dur*SR); t = np.arange(n)/SR
    rng = np.random.default_rng(int(t0*1000)+99)
    noise = rng.normal(0,1,n)
    freqs = np.linspace(lo, hi, n)
    seg = int(0.05*SR); out = np.zeros(n)
    for i in range(0, n, seg):
        f = freqs[i]
        lo2=max(80,f*0.7); hi2=min(0.49*SR, f*1.3)
        b,a=signal.butter(2, [lo2/(SR/2), hi2/(SR/2)], btype="band")
        out[i:i+seg] = signal.lfilter(b, a, noise[i:i+seg])
    env = np.sin(np.pi*np.linspace(0,1,n))**2
    return t0, out*env*gain*0.5

def riser(t0, dur=3.0, gain=0.35, f_start=100, f_end=850):
    n = int(dur*SR); t = np.arange(n)/SR
    rng = np.random.default_rng(int(t0*1000)+7)
    noise = rng.normal(0,1,n)
    seg = int(0.03*SR)
    freqs = np.logspace(np.log10(f_start), np.log10(f_end), max(1, n//seg))
    out = np.zeros(n)
    for i in range(0, n, seg):
        f = freqs[min(i//seg, len(freqs)-1)]
        lo2=max(60,f*0.6); hi2=min(0.49*SR, f*1.4)
        b,a=signal.butter(2, [lo2/(SR/2), hi2/(SR/2)], btype="band")
        out[i:i+seg] = signal.lfilter(b, a, noise[i:i+seg])
    env = (np.arange(n)/n)**2.5
    return t0, out*env*gain

def generate_sfx_bed():
    DUR_TOTAL, S = get_durations()
    EVENTS = []
    
    # Specific beats from the script
    EVENTS.append((S["s01"] + 0.1, boom, dict(gain=0.8, f0=80, f1=30)))
    EVENTS.append((S["s02"] + 0.5, whoosh, dict(gain=0.6)))
    EVENTS.append((S["s04"] + 0.1, boom, dict(gain=0.7)))
    EVENTS.append((S["s05"] + 1.0, riser, dict(dur=2.5, gain=0.4)))
    EVENTS.append((S["s06"] + 0.5, boom, dict(gain=0.8)))
    EVENTS.append((S["s07"] + 0.2, whoosh, dict(gain=0.5)))
    EVENTS.append((S["s09"] + 0.1, riser, dict(dur=3.0, gain=0.4)))
    EVENTS.append((S["s10"] + 0.1, boom, dict(gain=0.7, f0=100, f1=40)))

    EVENTS.sort(key=lambda e: e[0])
    
    mix = np.zeros(int(DUR_TOTAL*SR))
    for t0, fn, kw in EVENTS:
        t0, sig = fn(t0, **kw)
        i0 = int(t0*SR); i1 = min(int(i0+len(sig)), len(mix))
        mix[i0:i1] += sig[:i1-i0]
    mix = np.clip(mix, -1, 1)

    fades = int(0.8*SR)
    if fades < len(mix):
        mix[:fades] *= np.linspace(0,1,fades)
        mix[-fades:] *= np.linspace(1,0,fades)

    out_wav = f"{SYNTH}/sfx.wav"
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        st = np.stack([mix, mix], axis=1)
        w.writeframes((st*32767).astype("<i2").tobytes())
    print(f"Generated {out_wav} ({DUR_TOTAL:.2f}s)")

if __name__ == "__main__":
    generate_sfx_bed()
