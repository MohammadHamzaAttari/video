#!/usr/bin/env python3
"""Build the motion-first Universe Impact black-hole-cosmology Reel, v2.

Every editorial background in this version is an extracted, re-edited moving
NASA Scientific Visualization Studio (SVS) asset.  The cut list deliberately
changes shots about every two seconds, alternates immersive portrait crops with
moving "science-feed" compositions, and never uses a static illustration to
carry a narrative beat.

Scientific guardrail
--------------------
"Could the Big Bang be inside a black hole?" is presented as a speculative
hypothesis, never as a discovery or a NASA claim.

Requested narration configuration
---------------------------------
Engine: edge-tts
Voice:  en-US-ChristopherNeural
Rate:   +0%

The `patch_edge_tts_getaddrinfo()` workaround below is intentionally retained
for speech.platform.bing.com.  On a host where Edge TTS is unreachable, render
with a pre-generated narration cache instead:

    python3 build_universe_impact_dynamic_v2.py --render-only --force

The source clips are expected in ./sources, as downloaded by download_assets.py.
Source audio is never used: some source pages include third-party music, while
this edit uses its own generated score and accents.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources"
# Reuse the existing eight narration files so a permitted host can render the
# requested Christopher voice once and both project versions can use it.
NARRATION_DIR = ROOT / "build_universe_impact" / "audio"
BUILD = ROOT / "build_universe_impact_dynamic_v2"
DELIVERABLES = ROOT / "deliverables"

VOICE = "en-US-ChristopherNeural"
RATE = "+0%"
FPS = 30
OUT_W, OUT_H = 1080, 1920
SCENE_GAP = 0.42
LAST_SCENE_GAP = 1.35
SCENE_FADE = 0.22


@dataclass(frozen=True)
class Scene:
    key: str
    narration: str
    headline: str
    kicker: str
    beats: tuple[str, ...]


@dataclass(frozen=True)
class Shot:
    """A deliberately short extract from a moving NASA visualization."""

    source: str
    start: float
    weight: float = 1.0
    layout: str = "immersive"  # immersive portrait crop | wide moving science feed
    phase: float = 0.0
    tone: str = "cool"


SCENES: tuple[Scene, ...] = (
    Scene(
        "01_hook",
        "What if the Big Bang was the inside of a black hole?",
        "WHAT IF THE BIG BANG\nWAS INSIDE A BLACK HOLE?",
        "A COSMIC QUESTION",
        ("ONE QUESTION.\nNO EASY ANSWER.",),
    ),
    Scene(
        "02_hypothesis",
        "Not a fact. Not a discovery. A breathtaking hypothesis called black hole cosmology.",
        "A HYPOTHESIS.\nNOT A DISCOVERY.",
        "BLACK-HOLE COSMOLOGY",
        ("NOT A FACT.", "NOT A DISCOVERY.", "A MODEL MUST FACE EVIDENCE."),
    ),
    Scene(
        "03_bounce",
        "In some models, collapse does not end at a singularity. Some quantum gravity ideas replace it with a bounce, opening a new region of expanding space time.",
        "COLLAPSE  →  BOUNCE\nEXPANDING SPACE",
        "ONE THEORETICAL PATH",
        ("SOME MODELS: NO SINGULARITY.", "INSTEAD: A BOUNCE.", "THEN SPACE EXPANDS."),
    ),
    Scene(
        "04_inside",
        "From inside, that bounce could look like a Big Bang: no center, just space expanding everywhere at once.",
        "FROM INSIDE, IT COULD LOOK\nLIKE A BIG BANG",
        "CONCEPTUAL MODEL · NO CENTER",
        ("NO CENTER.", "SPACE EXPANDING\nEVERYWHERE AT ONCE."),
    ),
    Scene(
        "05_limit",
        "But this is where honesty matters. Our best theories clash in these extreme conditions, and no observation shows our universe was born this way.",
        "THE HONEST LIMIT",
        "RELATIVITY × QUANTUM PHYSICS",
        ("THE EXTREMES BREAK OUR MODELS.", "NO COMPLETE UNIFICATION.\nNOT YET.", "NO OBSERVATION SHOWS THIS ORIGIN."),
    ),
    Scene(
        "06_fingerprint",
        "To become science, the idea needs a fingerprint: a unique pattern in the cosmic microwave background, or primordial gravitational waves that rival explanations cannot copy.",
        "SCIENCE NEEDS\nA FINGERPRINT",
        "TESTABLE, UNIQUE, REPEATABLE",
        ("LOOK FOR A UNIQUE PATTERN.", "CMB.", "PRIMORDIAL\nGRAVITATIONAL WAVES.", "RIVALS MUST NOT COPY IT."),
    ),
    Scene(
        "07_honesty",
        "Until then, the answer is not yes. It is: we do not know.",
        "NO DIRECT PROOF.\nYET.",
        "STATUS: OPEN QUESTION",
        ("THE SCIENTIFIC ANSWER:\nWE DO NOT KNOW.",),
    ),
    Scene(
        "08_cta",
        "That is still astonishing. The cosmos may be stranger than our best story. Universe Impact. Follow for wonder, evidence first.",
        "WONDER, THEN EVIDENCE.",
        "UNIVERSE IMPACT · FOLLOW",
        ("THE COSMOS MAY BE STRANGER.", "FOLLOW FOR WONDER.", "EVIDENCE FIRST."),
    ),
)


# All excerpts below come from the moving NASA SVS source files already held in
# ./sources.  Start values are intentionally selected before source end cards or
# logos.  Different crops, time ranges, and layouts are used to keep a repeat
# from feeling like a repeated still.
SHOT_TEMPLATES: dict[str, tuple[Shot, ...]] = {
    "01_hook": (
        Shot("clip1_bh_orbit.mp4", 4.20, layout="immersive", phase=0.20, tone="cool"),
        Shot("clip5_tde_fading.mov", 0.60, layout="wide", phase=1.30, tone="ember"),
    ),
    "02_hypothesis": (
        Shot("clip2_tde_shred.mp4", 11.80, layout="wide", phase=0.00, tone="ember"),
        Shot("clip1_bh_orbit.mp4", 8.00, layout="immersive", phase=1.50, tone="cool"),
        Shot("clip5_tde_fading.mov", 3.20, layout="wide", phase=2.10, tone="ember"),
        Shot("clip2_tde_shred.mp4", 16.20, layout="immersive", phase=0.80, tone="ember"),
    ),
    "03_bounce": (
        Shot("clip2_tde_shred.mp4", 10.40, layout="wide", phase=0.70, tone="ember"),
        Shot("clip4_tde_partial.mp4", 15.20, layout="immersive", phase=2.00, tone="signal"),
        Shot("clip5_tde_fading.mov", 0.50, layout="immersive", phase=1.10, tone="ember"),
        Shot("clip3_tde_disk.mp4", 7.00, layout="wide", phase=2.70, tone="cool"),
        Shot("clip1_bh_orbit.mp4", 11.20, layout="immersive", phase=0.30, tone="cool"),
    ),
    "04_inside": (
        Shot("clip3_tde_disk.mp4", 9.60, layout="immersive", phase=0.10, tone="cool"),
        Shot("clip5_tde_fading.mov", 4.00, layout="wide", phase=2.40, tone="ember"),
        Shot("clip2_tde_shred.mp4", 20.10, layout="immersive", phase=1.70, tone="ember"),
        Shot("clip1_bh_orbit.mp4", 2.10, layout="immersive", phase=2.80, tone="cool"),
    ),
    "05_limit": (
        Shot("clip1_bh_orbit.mp4", 6.50, layout="immersive", phase=0.60, tone="cool"),
        Shot("clip4_tde_partial.mp4", 23.80, layout="wide", phase=1.40, tone="signal"),
        Shot("clip3_tde_disk.mp4", 12.50, layout="immersive", phase=2.20, tone="cool"),
        Shot("clip2_tde_shred.mp4", 24.20, layout="immersive", phase=0.20, tone="ember"),
        Shot("clip5_tde_fading.mov", 8.20, layout="wide", phase=2.90, tone="ember"),
    ),
    "06_fingerprint": (
        Shot("clip4_tde_partial.mp4", 17.20, layout="immersive", phase=2.20, tone="signal"),
        Shot("clip3_tde_disk.mp4", 8.50, layout="wide", phase=0.60, tone="cool"),
        Shot("clip2_tde_shred.mp4", 29.00, layout="immersive", phase=1.50, tone="ember"),
        Shot("clip5_tde_fading.mov", 5.00, layout="wide", phase=2.60, tone="ember"),
        Shot("clip1_bh_orbit.mp4", 11.80, layout="immersive", phase=0.10, tone="cool"),
        Shot("clip4_tde_partial.mp4", 25.50, layout="immersive", phase=1.00, tone="signal"),
    ),
    "07_honesty": (
        Shot("clip1_bh_orbit.mp4", 0.50, layout="immersive", phase=1.80, tone="cool"),
        Shot("clip2_tde_shred.mp4", 27.20, layout="wide", phase=0.50, tone="ember"),
        Shot("clip3_tde_disk.mp4", 14.20, layout="immersive", phase=2.40, tone="cool"),
    ),
    "08_cta": (
        Shot("clip5_tde_fading.mov", 9.60, layout="immersive", phase=1.10, tone="ember"),
        Shot("clip4_tde_partial.mp4", 25.00, layout="wide", phase=2.80, tone="signal"),
        Shot("clip1_bh_orbit.mp4", 9.60, layout="immersive", phase=0.30, tone="cool"),
        Shot("clip2_tde_shred.mp4", 18.00, layout="immersive", phase=1.90, tone="ember"),
        Shot("clip3_tde_disk.mp4", 5.00, layout="wide", phase=2.10, tone="cool"),
    ),
}


SOURCE_INFO: dict[str, dict[str, str]] = {
    "clip1_bh_orbit.mp4": {
        "title": "Isolated Black Hole Visualization — Orbiting a bare black hole",
        "page": "https://svs.gsfc.nasa.gov/14620/",
        "asset": "https://svs.gsfc.nasa.gov/vis/a010000/a014600/a014620/1-Orbiting_a_bare_black_hole-4K.mp4",
        "credit": "NASA's Goddard Space Flight Center; visualization by Robert Hurt",
    },
    "clip2_tde_shred.mp4": {
        "title": "Massive Black Hole Shreds Passing Star",
        "page": "https://svs.gsfc.nasa.gov/12005/",
        "asset": "https://svs.gsfc.nasa.gov/vis/a010000/a012000/a012005/12005_Swift_Tidal_Music_MPEG4_1920X1080_2997.mp4",
        "credit": "NASA's Goddard Space Flight Center / CI Lab",
    },
    "clip3_tde_disk.mp4": {
        "title": "Isolated Black Hole Visualization — Tidal disruption by black hole",
        "page": "https://svs.gsfc.nasa.gov/14620/",
        "asset": "https://svs.gsfc.nasa.gov/vis/a010000/a014600/a014620/3-Tidal_disruption_by_black_hole-4K.mp4",
        "credit": "NASA's Goddard Space Flight Center; visualization by Robert Hurt",
    },
    "clip4_tde_partial.mp4": {
        "title": "Supercomputer Simulations Test Star-destroying Black Holes",
        "page": "https://svs.gsfc.nasa.gov/14000/",
        "asset": "https://svs.gsfc.nasa.gov/vis/a010000/a014000/a014000/1Msol_Ryu_TDE_4k_1.mp4",
        "credit": "NASA's Goddard Space Flight Center / Taeho Ryu (MPA)",
    },
    "clip5_tde_fading.mov": {
        "title": "Swift Charts a Star's 'Death Spiral' into Black Hole — shocks at apocenter",
        "page": "https://svs.gsfc.nasa.gov/12499/",
        "asset": "https://svs.gsfc.nasa.gov/vis/a010000/a012400/a012499/Shocks_at_Apocenter_Animation_FINAL-1080.mov",
        "credit": "NASA's Goddard Space Flight Center",
    },
}


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    for path in (BUILD, BUILD / "video", DELIVERABLES, NARRATION_DIR):
        path.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], *, label: str, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"\n[{label}] {' '.join(str(part) for part in cmd)}")
    result = subprocess.run(
        [str(part) for part in cmd],
        text=True,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.PIPE if quiet else None,
    )
    if result.returncode != 0:
        if quiet:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")
    return result


def find_ffmpeg() -> str:
    configured = os.environ.get("FFMPEG_BIN")
    if configured and Path(configured).exists():
        return configured
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - relevant only on bare hosts
        raise RuntimeError("Install ffmpeg, set FFMPEG_BIN, or install imageio-ffmpeg.") from exc


def media_duration(path: Path, ffmpeg: str) -> float:
    process = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", process.stderr)
    if not match:
        raise RuntimeError(f"Could not read duration from {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def ass_time(seconds: float) -> str:
    centiseconds = int(round(max(0.0, seconds) * 100))
    hours, rem = divmod(centiseconds, 360000)
    minutes, rem = divmod(rem, 6000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def srt_time(seconds: float) -> str:
    milliseconds = int(round(max(0.0, seconds) * 1000))
    hours, rem = divmod(milliseconds, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def clean_ass(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def font_path(bold: bool = True) -> str:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"


# ---------------------------------------------------------------------------
# Edge TTS, with the requested getaddrinfo workaround retained verbatim in v2.
# ---------------------------------------------------------------------------

def patch_edge_tts_getaddrinfo() -> None:
    """Force the Edge voice endpoint through patched IPv4 getaddrinfo.

    Do not remove this workaround.  It mirrors the requested moon-build style
    patch for speech.platform.bing.com: a few render environments return an
    unusable record through aiohttp's async DNS resolver.  ThreadedResolver
    deliberately calls the patched `socket.getaddrinfo` below.  Set
    EDGE_TTS_BING_IPV4 only when a known-good endpoint needs to be pinned; the
    original hostname remains present in SNI and HTTP Host headers.
    """
    if getattr(socket, "_universe_impact_dynamic_edge_patch", False):
        return

    original_getaddrinfo = socket.getaddrinfo
    target = "speech.platform.bing.com"

    def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):  # type: ignore[no-untyped-def]
        hostname = str(host).rstrip(".").lower() if isinstance(host, str) else ""
        if hostname == target:
            pinned_ipv4 = os.environ.get("EDGE_TTS_BING_IPV4", "").strip()
            if pinned_ipv4:
                return original_getaddrinfo(
                    pinned_ipv4,
                    port,
                    socket.AF_INET,
                    type or socket.SOCK_STREAM,
                    proto,
                    flags,
                )
            requested_family = socket.AF_INET if family in (0, socket.AF_UNSPEC) else family
            return original_getaddrinfo(host, port, requested_family, type, proto, flags)
        return original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched_getaddrinfo  # type: ignore[assignment]
    socket._universe_impact_dynamic_edge_patch = True  # type: ignore[attr-defined]

    try:
        import aiohttp  # type: ignore
        import aiohttp.connector  # type: ignore
        from aiohttp.resolver import ThreadedResolver  # type: ignore

        original_connector_init = aiohttp.connector.TCPConnector.__init__
        if not getattr(aiohttp.connector.TCPConnector, "_universe_impact_dynamic_edge_patch", False):
            def patched_connector_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                if kwargs.get("resolver") is None:
                    kwargs["resolver"] = ThreadedResolver()
                return original_connector_init(self, *args, **kwargs)

            aiohttp.connector.TCPConnector.__init__ = patched_connector_init  # type: ignore[method-assign]
            aiohttp.connector.TCPConnector._universe_impact_dynamic_edge_patch = True  # type: ignore[attr-defined]
            aiohttp.TCPConnector = aiohttp.connector.TCPConnector  # type: ignore[attr-defined]
    except ImportError:
        pass


async def synthesize_one(scene: Scene, force: bool) -> None:
    path = NARRATION_DIR / f"{scene.key}.mp3"
    subtitle_path = NARRATION_DIR / f"{scene.key}.vtt"
    if not force and path.exists() and path.stat().st_size > 1024:
        print(f"[voice] Reusing {path.name}")
        return

    patch_edge_tts_getaddrinfo()
    try:
        import edge_tts  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install edge-tts first: python3 -m pip install edge-tts") from exc

    for stale in (path, subtitle_path):
        stale.unlink(missing_ok=True)

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            print(f"[voice] {VOICE} ({RATE}) — {scene.key}, attempt {attempt}/3")
            voice = edge_tts.Communicate(scene.narration, voice=VOICE, rate=RATE)
            await voice.save(str(path))
            if path.exists() and path.stat().st_size > 1024:
                return
            raise RuntimeError("Edge TTS returned an empty audio file")
        except Exception as exc:
            last_error = exc
            path.unlink(missing_ok=True)
            subtitle_path.unlink(missing_ok=True)
            if attempt < 3:
                await asyncio.sleep(float(attempt))

    raise RuntimeError(
        "Edge TTS could not reach speech.platform.bing.com after the IPv4/getaddrinfo workaround. "
        "Run --voice-only on a network-permitted host, then copy the Christopher files into "
        f"{NARRATION_DIR} and use --render-only."
    ) from last_error


async def synthesize_voice(force: bool) -> None:
    for scene in SCENES:
        await synthesize_one(scene, force)
    (BUILD / "voice_manifest.json").write_text(
        json.dumps(
            {
                "provider": "edge-tts",
                "voice": VOICE,
                "rate": RATE,
                "resolver_workaround": "patched socket.getaddrinfo + aiohttp ThreadedResolver for speech.platform.bing.com",
                "scenes": [{"key": scene.key, "text": scene.narration} for scene in SCENES],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Timeline and moving NASA source montage
# ---------------------------------------------------------------------------

def scene_audio_path(scene: Scene) -> Path:
    return NARRATION_DIR / f"{scene.key}.mp3"


def get_scene_timeline(ffmpeg: str) -> list[dict[str, float | Scene]]:
    timeline: list[dict[str, float | Scene]] = []
    cursor = 0.0
    for index, scene in enumerate(SCENES):
        audio_path = scene_audio_path(scene)
        if not audio_path.exists() or audio_path.stat().st_size < 1024:
            raise RuntimeError(
                f"Narration missing for {scene.key}: expected {audio_path}. "
                "Run --voice-only on an Edge-permitted host, or use the existing approved cache."
            )
        voice_duration = media_duration(audio_path, ffmpeg)
        gap = LAST_SCENE_GAP if index == len(SCENES) - 1 else SCENE_GAP
        duration = voice_duration + gap
        timeline.append(
            {
                "scene": scene,
                "start": cursor,
                "voice_duration": voice_duration,
                "duration": duration,
                "end": cursor + duration,
            }
        )
        cursor += duration
    return timeline


def source_lengths(ffmpeg: str) -> dict[str, float]:
    required = {shot.source for group in SHOT_TEMPLATES.values() for shot in group}
    lengths: dict[str, float] = {}
    for name in sorted(required):
        path = SOURCES / name
        if not path.exists():
            raise RuntimeError(f"Required NASA source clip is missing: {path}")
        lengths[name] = media_duration(path, ffmpeg)
    return lengths


def plan_scene_shots(scene: Scene, duration: float) -> list[tuple[Shot, float]]:
    templates = SHOT_TEMPLATES.get(scene.key)
    if not templates:
        raise RuntimeError(f"No moving shot plan exists for {scene.key}")
    total_weight = sum(item.weight for item in templates)
    remaining = duration
    plan: list[tuple[Shot, float]] = []
    for index, shot in enumerate(templates):
        if index == len(templates) - 1:
            shot_duration = remaining
        else:
            # Frame-aligned changes produce crisp hard cuts and exact-ish scene joins.
            shot_duration = round(duration * shot.weight / total_weight * FPS) / FPS
            remaining -= shot_duration
        if shot_duration < 0.45:
            raise RuntimeError(f"Shot plan for {scene.key} created an invalid {shot_duration:.3f}s shot")
        plan.append((shot, shot_duration))
    return plan


def grade_for(tone: str) -> str:
    grades = {
        "cool": "eq=contrast=1.10:saturation=1.10:brightness=-0.012:gamma=1.025",
        "ember": "eq=contrast=1.12:saturation=1.17:brightness=-0.012:gamma=1.015",
        "signal": "eq=contrast=1.16:saturation=1.25:brightness=-0.010:gamma=1.035",
    }
    try:
        return grades[tone]
    except KeyError as exc:
        raise RuntimeError(f"Unknown grade: {tone}") from exc


def build_immersive_filter(input_index: int, shot_index: int, shot: Shot, duration: float) -> str:
    """Portrait crop with a slight editorial camera drift over already-moving footage."""
    phase = shot.phase
    x_expr = f"(in_w-out_w)*(0.50+0.055*sin(1.12*t+{phase:.3f}))"
    y_expr = f"(in_h-out_h)*(0.50+0.18*cos(0.88*t+{phase:.3f}))"
    return (
        f"[{input_index}:v]trim=duration={duration:.3f},setpts=PTS-STARTPTS,"
        f"scale={OUT_W}:2040:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={OUT_W}:{OUT_H}:x='{x_expr}':y='{y_expr}':exact=1,"
        f"fps={FPS},{grade_for(shot.tone)},vignette=PI/5:eval=frame,"
        "unsharp=5:5:0.38:5:5:0.0,setsar=1,format=yuv420p"
        f"[shot{shot_index}]"
    )


def build_wide_filter(input_index: int, shot_index: int, shot: Shot, duration: float) -> list[str]:
    """Moving full-frame source over its own moving blurred portrait backdrop."""
    phase = shot.phase
    bg_x = f"(in_w-out_w)*(0.50+0.080*sin(0.90*t+{phase:.3f}))"
    bg_y = f"(in_h-out_h)*(0.50+0.16*cos(0.73*t+{phase:.3f}))"
    return [
        (
            f"[{input_index}:v]trim=duration={duration:.3f},setpts=PTS-STARTPTS,"
            f"split=2[wide_bg_src{shot_index}][wide_fg_src{shot_index}]"
        ),
        (
            f"[wide_bg_src{shot_index}]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={OUT_W}:{OUT_H}:x='{bg_x}':y='{bg_y}':exact=1,"
            f"fps={FPS},boxblur=18:2,{grade_for(shot.tone)},"
            "eq=brightness=-0.18,vignette=PI/4:eval=frame,setsar=1"
            f"[wide_bg{shot_index}]"
        ),
        (
            f"[wide_fg_src{shot_index}]scale=1000:570:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=1000:570:(ow-iw)/2:(oh-ih)/2:color=0x030711,"
            f"fps={FPS},{grade_for(shot.tone)},unsharp=5:5:0.38:5:5:0.0,setsar=1"
            f"[wide_fg{shot_index}]"
        ),
        (
            f"[wide_bg{shot_index}]drawbox=x=26:y=606:w=1028:h=582:color=0x52E8F0@0.58:t=4"
            f"[wide_frame{shot_index}]"
        ),
        (
            f"[wide_frame{shot_index}][wide_fg{shot_index}]overlay=x=(W-w)/2:"
            f"y='612+14*sin(0.90*t+{phase:.3f})':shortest=1,setsar=1,format=yuv420p"
            f"[shot{shot_index}]"
        ),
    ]


def render_scene(
    entry: dict[str, float | Scene],
    index: int,
    ffmpeg: str,
    lengths: dict[str, float],
    force: bool,
) -> Path:
    scene = entry["scene"]
    assert isinstance(scene, Scene)
    duration = float(entry["duration"])
    output = BUILD / "video" / f"{index + 1:02d}_{scene.key}.mp4"
    if not force and output.exists() and output.stat().st_size > 100_000:
        return output

    shot_plan = plan_scene_shots(scene, duration)
    command: list[str] = [ffmpeg, "-y", "-loglevel", "warning"]
    filters: list[str] = []
    for shot_index, (shot, shot_duration) in enumerate(shot_plan):
        source = SOURCES / shot.source
        if shot.start + shot_duration > lengths[shot.source] - 0.03:
            raise RuntimeError(
                f"{scene.key} requests {shot.source} through {shot.start + shot_duration:.2f}s, "
                f"but it only lasts {lengths[shot.source]:.2f}s"
            )
        # Input seeking avoids decoding unused 4K source frames.  A small input
        # tail ensures trim has enough decoded frames at a source keyframe edge.
        command.extend(["-ss", f"{shot.start:.3f}", "-t", f"{shot_duration + 0.10:.3f}", "-i", str(source)])
        if shot.layout == "immersive":
            filters.append(build_immersive_filter(shot_index, shot_index, shot, shot_duration))
        elif shot.layout == "wide":
            filters.extend(build_wide_filter(shot_index, shot_index, shot, shot_duration))
        else:
            raise RuntimeError(f"Unknown shot layout {shot.layout!r}")

    fade_out_start = max(0.0, duration - SCENE_FADE)
    filters.append(
        "".join(f"[shot{shot_index}]" for shot_index in range(len(shot_plan)))
        + f"concat=n={len(shot_plan)}:v=1:a=0,"
        + f"fade=t=in:st=0:d={SCENE_FADE:.3f},fade=t=out:st={fade_out_start:.3f}:d={SCENE_FADE:.3f},"
        "format=yuv420p[sceneout]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[sceneout]",
            "-an",
            "-r",
            str(FPS),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "18",
            "-profile:v",
            "high",
            "-level:v",
            "4.1",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run(command, label=f"dynamic scene {index + 1}: {scene.key}")
    return output


def concat_visuals(scene_files: list[Path], ffmpeg: str, force: bool) -> Path:
    output = BUILD / "visual_base_dynamic_v2.mp4"
    if not force and output.exists() and output.stat().st_size > 100_000:
        return output
    concat_list = BUILD / "visual_concat_dynamic_v2.txt"
    concat_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in scene_files), encoding="utf-8")
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "warning",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output),
        ],
        label="concat dynamic visual scenes",
    )
    return output


def cut_times(timeline: list[dict[str, float | Scene]]) -> list[float]:
    """Global timestamps for original impact accents at every editorial cut."""
    result: list[float] = []
    for entry in timeline:
        scene = entry["scene"]
        assert isinstance(scene, Scene)
        cursor = float(entry["start"])
        for _, duration in plan_scene_shots(scene, float(entry["duration"]))[:-1]:
            cursor += duration
            result.append(cursor)
    return result


# ---------------------------------------------------------------------------
# Captions, original score, final render, and publishing package
# ---------------------------------------------------------------------------

def write_ass_and_srt(timeline: list[dict[str, float | Scene]]) -> tuple[Path, Path]:
    ass_path = BUILD / "universe_impact_dynamic_v2.ass"
    srt_path = DELIVERABLES / "universe_impact_black_hole_reel_dynamic_v2.srt"
    total_end = float(timeline[-1]["end"])
    ass_lines = [
        "[Script Info]",
        "Title: Universe Impact — Motion-first black-hole cosmology Reel v2",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Brand,DejaVu Sans,23,&H00CDEAF6,&H000000FF,&H8C02050D,&H8C02050D,1,0,0,0,100,100,1.0,0,1,1.4,1.6,7,55,55,52,1",
        "Style: Source,DejaVu Sans,17,&H00CDEAF6,&H000000FF,&H9602050D,&H9602050D,0,0,0,0,100,100,0.4,0,1,1.1,1.2,9,55,55,56,1",
        "Style: Evidence,DejaVu Sans,22,&H0077E9FF,&H000000FF,&H9202050D,&H9202050D,1,0,0,0,100,100,0.8,0,1,1.5,1.8,2,58,58,62,1",
        "Style: Kicker,DejaVu Sans,27,&H006DEBF7,&H000000FF,&H9602050D,&H9602050D,1,0,0,0,100,100,2.0,0,1,1.7,2.0,8,55,55,255,1",
        "Style: Headline,DejaVu Sans,59,&H00FFFFFF,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,0.5,0,1,2.8,2.5,8,50,50,318,1",
        "Style: Beat,DejaVu Sans,39,&H00FFFFFF,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,1.0,0,1,2.4,2.1,2,70,70,290,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        f"Dialogue: 0,0:00:00.00,{ass_time(total_end)},Brand,,0,0,0,,UNIVERSE IMPACT  •  COSMIC QUESTIONS",
        f"Dialogue: 0,0:00:00.00,{ass_time(total_end)},Source,,0,0,0,,NASA SVS  •  MOVING VISUALS",
        f"Dialogue: 0,0:00:00.00,{ass_time(total_end)},Evidence,,0,0,0,,HYPOTHESIS  /  NOT ESTABLISHED FACT",
    ]

    srt_lines: list[str] = []
    for number, entry in enumerate(timeline, start=1):
        scene = entry["scene"]
        assert isinstance(scene, Scene)
        start = float(entry["start"])
        duration = float(entry["duration"])
        end = float(entry["end"])
        voice_end = start + float(entry["voice_duration"])

        # A fast kinetic title card makes room for the moving source footage;
        # it does not sit unchanged for the whole spoken scene.
        card_end = min(end - 0.15, start + min(3.25, max(2.45, duration * 0.43)))
        ass_lines.append(
            f"Dialogue: 1,{ass_time(start + 0.12)},{ass_time(card_end)},Kicker,,0,0,0,,{{\\fad(150,220)}}{clean_ass(scene.kicker)}"
        )
        ass_lines.append(
            f"Dialogue: 2,{ass_time(start + 0.30)},{ass_time(card_end)},Headline,,0,0,0,,{{\\fad(190,240)}}{clean_ass(scene.headline)}"
        )

        beat_start = card_end - 0.08
        beat_end = end - 0.13
        beat_span = max(0.20, (beat_end - beat_start) / len(scene.beats))
        for beat_index, beat in enumerate(scene.beats):
            local_start = beat_start + beat_index * beat_span
            local_end = min(beat_end, local_start + beat_span + 0.04)
            ass_lines.append(
                f"Dialogue: 3,{ass_time(local_start)},{ass_time(local_end)},Beat,,0,0,0,,{{\\fad(130,180)}}{clean_ass(beat)}"
            )

        srt_lines.extend(
            [
                str(number),
                f"{srt_time(start)} --> {srt_time(voice_end)}",
                scene.narration,
                "",
            ]
        )

    ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return ass_path, srt_path


def make_music(path: Path, duration: float, scene_starts: list[float], editorial_cuts: list[float], force: bool) -> None:
    """Create an original kinetic score: pad, pulses, and non-sampled cut accents."""
    if not force and path.exists() and path.stat().st_size > 100_000:
        return

    sample_rate = 48000
    count = int(math.ceil((duration + 0.12) * sample_rate))
    t = np.arange(count, dtype=np.float32) / sample_rate
    left = np.zeros(count, dtype=np.float32)
    right = np.zeros(count, dtype=np.float32)

    slow = 0.5 + 0.5 * np.sin(2 * math.pi * t / 17.0 - 0.55)
    for frequency, level, pan in ((43.65, 0.031, -0.25), (65.41, 0.022, 0.15), (98.0, 0.012, 0.38), (130.81, 0.008, -0.42)):
        tone = np.sin(2 * math.pi * frequency * t + 0.22 * np.sin(2 * math.pi * t / 6.8)) * level
        left += tone * (1.0 - pan) * (0.62 + 0.38 * slow)
        right += tone * (1.0 + pan) * (0.62 + 0.38 * slow)

    # An understated pulse bed supports cut density without competing with voice.
    for beat in np.arange(0.38, duration, 1.25):
        start = int(beat * sample_rate)
        length = min(int(0.34 * sample_rate), count - start)
        if length <= 0:
            continue
        local_t = np.arange(length, dtype=np.float32) / sample_rate
        frequency = 96.0 * np.exp(-local_t * 6.2)
        phase = 2 * math.pi * np.cumsum(frequency) / sample_rate
        kick = np.sin(phase) * np.exp(-local_t * 9.0) * 0.047
        left[start:start + length] += kick
        right[start:start + length] += kick

    # There is a quiet synthetic whoosh at every visual extraction cut and a
    # larger downbeat at each narrative scene boundary. No third-party sample.
    rng = np.random.default_rng(20260831)
    scene_start_set = {round(value, 2) for value in scene_starts[1:]}
    for index, cue in enumerate(editorial_cuts + scene_starts[1:]):
        start = int(max(0.0, cue - 0.025) * sample_rate)
        is_scene = round(cue, 2) in scene_start_set
        length = min(int((0.58 if is_scene else 0.28) * sample_rate), count - start)
        if length <= 0:
            continue
        local_t = np.arange(length, dtype=np.float32) / sample_rate
        frequency = (124.0 + (index % 6) * 7.0) * np.exp(-local_t * (3.8 if is_scene else 7.4))
        phase = 2 * math.pi * np.cumsum(frequency) / sample_rate
        level = 0.040 if is_scene else 0.014
        impact = np.sin(phase) * np.exp(-local_t * (5.0 if is_scene else 10.0)) * level
        noise = rng.normal(0.0, 1.0, length).astype(np.float32)
        noise *= np.sin(np.pi * np.minimum(local_t / 0.12, 1.0)) * np.exp(-local_t * (2.7 if is_scene else 9.0))
        noise *= 0.012 if is_scene else 0.0045
        left[start:start + length] += impact + noise * 0.80
        right[start:start + length] += impact - noise * 0.48

    fade_count = min(int(0.72 * sample_rate), count)
    envelope = np.ones(count, dtype=np.float32)
    envelope[:fade_count] = np.linspace(0.0, 1.0, fade_count, dtype=np.float32)
    envelope[-fade_count:] *= np.linspace(1.0, 0.0, fade_count, dtype=np.float32)
    stereo = np.stack((left * envelope, right * envelope), axis=1)
    pcm = (np.clip(stereo, -0.30, 0.30) * 32767.0).astype("<i2")

    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())


def render_final(
    visual_base: Path,
    ass_path: Path,
    timeline: list[dict[str, float | Scene]],
    ffmpeg: str,
    force: bool,
) -> Path:
    """Burn captions, mix audio, then mux in three stable render passes.

    Separating the high-resolution subtitle render from the multi-input audio
    graph avoids a fragile all-in-one ffmpeg graph on constrained machines, and
    makes each independently verifiable before the final mux.
    """
    output = DELIVERABLES / "universe_impact_black_hole_reel_dynamic_v2.mp4"
    if not force and output.exists() and output.stat().st_size > 100_000:
        return output

    total_duration = float(timeline[-1]["end"])
    music_path = BUILD / "universe_impact_dynamic_v2_original_score.wav"
    captioned_video = BUILD / "visual_captioned_dynamic_v2.mp4"
    mixed_audio = BUILD / "mixed_audio_dynamic_v2.m4a"
    make_music(
        music_path,
        total_duration,
        [float(entry["start"]) for entry in timeline],
        cut_times(timeline),
        force,
    )

    fonts_dir = str(Path(font_path()).parent)
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "warning",
            "-i",
            str(visual_base),
            "-vf",
            f"ass=filename='{ass_path.as_posix()}':fontsdir='{fonts_dir}',format=yuv420p",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-profile:v",
            "high",
            "-level:v",
            "4.1",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-movflags",
            "+faststart",
            str(captioned_video),
        ],
        label="burn dynamic v2 kinetic captions",
    )
    run([ffmpeg, "-v", "error", "-i", str(captioned_video), "-f", "null", "-"], label="captioned video decode validation", quiet=True)

    # The music is input 0; the eight scene narration files follow it. Padding
    # each voice file makes its silent beat line up with the visual scene length.
    audio_command: list[str] = [ffmpeg, "-y", "-loglevel", "warning", "-i", str(music_path)]
    audio_command.extend(item for scene in SCENES for item in ("-i", str(scene_audio_path(scene))))
    audio_filters: list[str] = []
    voice_labels: list[str] = []
    for index, entry in enumerate(timeline):
        scene_duration = float(entry["duration"])
        voice_duration = float(entry["voice_duration"])
        padding = max(0.05, scene_duration - voice_duration + 0.02)
        label = f"voice{index}"
        voice_labels.append(f"[{label}]")
        audio_filters.append(
            f"[{index + 1}:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
            f"apad=pad_dur={padding:.3f},atrim=duration={scene_duration:.3f}[{label}]"
        )
    audio_filters.append("".join(voice_labels) + f"concat=n={len(timeline)}:v=0:a=1[voice]")
    audio_filters.append("[0:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,volume=0.25[music]")
    audio_filters.append(
        "[voice][music]amix=inputs=2:duration=first:normalize=0,"
        "acompressor=threshold=-17dB:ratio=3:attack=12:release=150,"
        "alimiter=limit=0.94,loudnorm=I=-16:LRA=7:TP=-1.5[aout]"
    )
    audio_command.extend(
        [
            "-filter_complex",
            ";".join(audio_filters),
            "-map",
            "[aout]",
            "-vn",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(mixed_audio),
        ]
    )
    run(audio_command, label="mix dynamic v2 narration and original score")
    run([ffmpeg, "-v", "error", "-i", str(mixed_audio), "-f", "null", "-"], label="mixed audio decode validation", quiet=True)

    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "warning",
            "-i",
            str(captioned_video),
            "-i",
            str(mixed_audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c",
            "copy",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output),
        ],
        label="mux final dynamic v2 Facebook Reel",
    )
    run([ffmpeg, "-v", "error", "-i", str(output), "-f", "null", "-"], label="dynamic v2 full decode validation", quiet=True)
    return output


def extract_cover(video: Path, ffmpeg: str) -> Path:
    cover = DELIVERABLES / "universe_impact_black_hole_cover_dynamic_v2.jpg"
    run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "warning",
            "-ss",
            "0.900",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-vf",
            f"scale={OUT_W}:{OUT_H}:flags=lanczos",
            str(cover),
        ],
        label="dynamic v2 cover image",
    )
    return cover


def detailed_shot_manifest(timeline: list[dict[str, float | Scene]]) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for entry in timeline:
        scene = entry["scene"]
        assert isinstance(scene, Scene)
        cursor = float(entry["start"])
        for shot, duration in plan_scene_shots(scene, float(entry["duration"])):
            details.append(
                {
                    "scene": scene.key,
                    "timeline_start": round(cursor, 3),
                    "timeline_end": round(cursor + duration, 3),
                    "source_file": shot.source,
                    "source_start": shot.start,
                    "layout": shot.layout,
                    "source_page": SOURCE_INFO[shot.source]["page"],
                }
            )
            cursor += duration
    return details


def write_publishing_pack(timeline: list[dict[str, float | Scene]], final_video: Path, cover: Path, ffmpeg: str) -> Path:
    package = DELIVERABLES / "UNIVERSE_IMPACT_FACEBOOK_POST_DYNAMIC_V2.md"
    duration = media_duration(final_video, ffmpeg)
    package.write_text(
        f"""# Universe Impact — Facebook publishing pack (dynamic v2)

## Reel title
**Could the Big Bang Be Inside a Black Hole? | Hypothesis, Not Proof**

## Ready-to-paste Facebook caption
What if the Big Bang was not the beginning of *everything* — but the inside of a black hole in a larger cosmos? 🌌

Black-hole cosmology is a real family of speculative ideas, but it is **not established science**. The exciting part is not pretending we have the answer; it is asking what evidence would make the idea testable.

What cosmic fingerprint would convince you: a pattern in the CMB, primordial gravitational waves, or something no one has imagined yet?

Follow **Universe Impact** for big cosmic questions — wonder first, evidence always.

#UniverseImpact #Space #Astronomy #BlackHole #BigBang #Cosmology #Science #CosmicMystery

## Pinned-comment prompt
**Mind-bender:** If this idea ever became testable, what evidence should scientists look for first? Drop your best answer below. 👇

## Upload settings
- **File:** `{final_video.name}`
- **Format:** 1080 × 1920, H.264/AAC, vertical 9:16
- **Length:** approximately {duration:.1f} seconds
- **Cover:** `{cover.name}`
- **Captions:** Upload `universe_impact_black_hole_reel_dynamic_v2.srt` if Facebook's caption option is available. The Reel also includes intentionally short, burned-in kinetic headline cards.
- **Suggested first-frame hook:** “WHAT IF THE BIG BANG WAS INSIDE A BLACK HOLE?”

## Accessibility alt text
A fast-cut vertical science Reel from Universe Impact. Moving NASA scientific visualizations show an orbit around a black hole, a star stretching into a gas stream, and debris circling a black hole. Text identifies the footage as NASA visualizations and repeatedly labels the claim as a hypothesis, not established fact.

## Editorial integrity note
This Reel intentionally separates **hypothesis** from **evidence**. It does **not** claim that NASA, JWST, or any observatory has proved that we live in a black hole. “Black-hole cosmology” is framed as a speculative family of models that needs a unique, testable observational signature before it can gain support.

## Visual / audio provenance
This v2 cut removes the static artist-concept backgrounds used in the earlier candidate. It uses **34 short, moving editorial extracts** from these NASA Scientific Visualization Studio sources, with original portrait reframing, cut structure, kinetic typography, generated score, and generated accents:

1. **Isolated Black Hole Visualization** (orbiting bare black hole; also tidal disruption visualization), NASA Goddard / Robert Hurt
   - Page: `https://svs.gsfc.nasa.gov/14620/`
   - Assets: `1-Orbiting_a_bare_black_hole-4K.mp4`; `3-Tidal_disruption_by_black_hole-4K.mp4`
2. **Massive Black Hole Shreds Passing Star**, NASA Goddard / CI Lab
   - Page: `https://svs.gsfc.nasa.gov/12005/`
   - Asset: `12005_Swift_Tidal_Music_MPEG4_1920X1080_2997.mp4`
3. **Supercomputer Simulations Test Star-destroying Black Holes**, NASA Goddard / Taeho Ryu (MPA)
   - Page: `https://svs.gsfc.nasa.gov/14000/`
   - Asset: `1Msol_Ryu_TDE_4k_1.mp4`
4. **Swift Charts a Star's ‘Death Spiral’ into Black Hole — shocks at apocenter**, NASA Goddard
   - Page: `https://svs.gsfc.nasa.gov/12499/`
   - Asset: `Shocks_at_Apocenter_Animation_FINAL-1080.mov`

NASA SVS states that its visualizations are public domain unless otherwise noted. **All source audio is stripped**. This is particularly important for source pages that identify separately licensed music. The score, transition accents, captions, reframing, and edit are original to Universe Impact.

## Production note (not for the social caption)
- Requested narration setting for a compliant rerender: **edge-tts / en-US-ChristopherNeural / +0%**.
- Verify the active narration cache's voice identity before publicly representing this file as a strict Christopher-voice render. The current sandbox could not reach Edge TTS, so it cannot independently prove that existing cached narration meets that setting.

## Research context
- NASA SVS usage FAQ: `https://svs.gsfc.nasa.gov/`
- NASA explainer of tidal-disruption visualizations: `https://www.nasa.gov/universe/nasas-swift-mission-maps-a-stars-death-spiral-into-a-black-hole/`
- Keep “hypothesis,” “speculative model,” and “no direct proof” in captions or replies; do not turn this into “NASA proved we live inside a black hole.”
""",
        encoding="utf-8",
    )
    return package


def write_render_manifest(timeline: list[dict[str, float | Scene]], final_video: Path, cover: Path, ffmpeg: str) -> Path:
    manifest_path = DELIVERABLES / "universe_impact_black_hole_reel_dynamic_v2_manifest.json"
    manifest = {
        "version": "dynamic-v2",
        "title": "Could the Big Bang Be Inside a Black Hole? | Hypothesis, Not Proof",
        "page": "Universe Impact",
        "output": final_video.name,
        "cover": cover.name,
        "format": {
            "width": OUT_W,
            "height": OUT_H,
            "fps": FPS,
            "duration_seconds": round(media_duration(final_video, ffmpeg), 3),
        },
        "visual_strategy": {
            "static_story_backgrounds_used": False,
            "moving_nasa_source_shot_count": sum(len(shots) for shots in SHOT_TEMPLATES.values()),
            "typical_shot_duration_seconds": "approximately 2.1–2.6",
            "source_audio_used": False,
            "edit_elements": ["portrait reframing", "moving science-feed layouts", "kinetic headline cards", "original procedural score and accents"],
        },
        "voice_requested": {"engine": "edge-tts", "voice": VOICE, "rate": RATE},
        "voice_verification": "Requested configuration is retained in the build script. Existing render-only narration cache is not independently verified as Christopher in this sandbox.",
        "scientific_framing": "Speculative hypothesis; no direct observational proof is claimed.",
        "source_clips": SOURCE_INFO,
        "timeline": [
            {
                "key": entry["scene"].key,  # type: ignore[index,union-attr]
                "start": round(float(entry["start"]), 3),
                "end": round(float(entry["end"]), 3),
                "narration": entry["scene"].narration,  # type: ignore[index,union-attr]
            }
            for entry in timeline
        ],
        "shots": detailed_shot_manifest(timeline),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def build_render(force: bool) -> tuple[Path, Path, Path, Path]:
    ensure_dirs()
    ffmpeg = find_ffmpeg()
    timeline = get_scene_timeline(ffmpeg)
    lengths = source_lengths(ffmpeg)
    print("\n[plan] Dynamic scene timing / source cuts")
    for entry in timeline:
        scene = entry["scene"]
        assert isinstance(scene, Scene)
        plan = plan_scene_shots(scene, float(entry["duration"]))
        print(
            f"  {scene.key}: {float(entry['start']):5.2f}s → {float(entry['end']):5.2f}s "
            f"({len(plan)} moving NASA extracts)"
        )

    scene_files = [render_scene(entry, index, ffmpeg, lengths, force) for index, entry in enumerate(timeline)]
    visual_base = concat_visuals(scene_files, ffmpeg, force)
    ass_path, _ = write_ass_and_srt(timeline)
    final_video = render_final(visual_base, ass_path, timeline, ffmpeg, force)
    cover = extract_cover(final_video, ffmpeg)
    package = write_publishing_pack(timeline, final_video, cover, ffmpeg)
    manifest = write_render_manifest(timeline, final_video, cover, ffmpeg)
    return final_video, cover, package, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the all-moving Universe Impact black-hole Reel, dynamic v2.")
    parser.add_argument("--voice-only", action="store_true", help="Create/recreate requested Edge TTS narration only.")
    parser.add_argument("--render-only", action="store_true", help="Render using narration cache already in build_universe_impact/audio/.")
    parser.add_argument("--force", action="store_true", help="Recreate dynamic scenes, score, final output, and cover.")
    args = parser.parse_args()
    if args.voice_only and args.render_only:
        parser.error("--voice-only and --render-only cannot be used together")

    ensure_dirs()
    if not args.render_only:
        asyncio.run(synthesize_voice(args.force))
    if not args.voice_only:
        final_video, cover, package, manifest = build_render(args.force)
        print("\nDone — dynamic v2 candidate rendered.")
        print(f"  Reel:     {final_video}")
        print(f"  Cover:    {cover}")
        print(f"  Posting:  {package}")
        print(f"  Manifest: {manifest}")


if __name__ == "__main__":
    main()
