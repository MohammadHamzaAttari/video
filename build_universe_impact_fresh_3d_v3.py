#!/usr/bin/env python3
"""Build the fresh-source, original-3D Universe Impact Reel (v3).

This is a replacement build, not a recut of v2:

* It never reads from ``./sources/`` or any of v2's five motion files.
* It uses three **newly acquired public-domain animated 3D NASA SVS GIFs** in
  ``assets/universe_impact_fresh_v3/``. Their full animation frames are used;
  they are not static frame dumps.
* It renders six original 3D-style moving sequences from geometry, particles,
  perspective cameras, and volumetric glow through ``fresh_3d_visuals.py``.
* It strips / omits every source audio track and creates an original score and
  cut accents locally.

Scientific guardrail
--------------------
The question "Could the Big Bang be inside a black hole?" is a speculative
hypothesis, not an observation or a NASA discovery. The on-screen framing and
publishing pack preserve that distinction.

Requested narration configuration
---------------------------------
Engine: edge-tts
Voice:  en-US-ChristopherNeural
Rate:   +0%

The getaddrinfo workaround requested for speech.platform.bing.com is retained
below. On a host that cannot reach Edge TTS, render against an existing,
previously generated narration cache:

    python3 build_universe_impact_fresh_3d_v3.py --render-only --force

The sandbox may not be able to independently verify a pre-existing cache's
voice identity. Use --voice-only on an Edge-permitted host before making a
strict public claim about a fresh voice render.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
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

from fresh_3d_visuals import render_all as render_fresh_3d_sources


ROOT = Path(__file__).resolve().parent
FRESH_ASSETS = ROOT / "assets" / "universe_impact_fresh_v3"
# These are the existing narration cache paths used by the prior approved build.
# The scene copy remains identical, so cache reuse never changes spoken wording.
NARRATION_DIR = ROOT / "build_universe_impact" / "audio"
BUILD = ROOT / "build_universe_impact_fresh_3d_v3"
DELIVERABLES = ROOT / "deliverables"

VOICE = "en-US-ChristopherNeural"
RATE = "+0%"
FPS = 30
OUT_W, OUT_H = 1080, 1920
SCENE_GAP = 0.42
LAST_SCENE_GAP = 1.35
SCENE_FADE = 0.20


@dataclass(frozen=True)
class Scene:
    key: str
    narration: str
    headline: str
    kicker: str
    beats: tuple[str, ...]


@dataclass(frozen=True)
class Shot:
    """A short, all-moving extract from a fresh v3 source track."""

    source: str
    start: float
    weight: float = 1.0
    layout: str = "immersive"  # original 3D full-frame | public-domain source portal
    phase: float = 0.0
    tone: str = "cool"


SCENES: tuple[Scene, ...] = (
    Scene(
        "01_hook",
        "What if the Big Bang was the inside of a black hole?",
        "WHAT IF THE BIG BANG\nWAS AN INSIDE VIEW?",
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
        "NO CENTER.\nEXPANSION EVERYWHERE.",
        "CONCEPTUAL MODEL",
        ("NO PRIVILEGED CENTER.", "SPACE EXPANDING\nEVERYWHERE AT ONCE."),
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
        "TESTABLE · UNIQUE · REPEATABLE",
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


# There are 34 fast visual passages. All paths below refer either to the three
# newly acquired PD animation files or to v3's new original 3D outputs. None
# references the legacy v2 source directory or file list.
SHOT_TEMPLATES: dict[str, tuple[Shot, ...]] = {
    "01_hook": (
        Shot("original_lens_orbit", 0.20, layout="immersive", phase=0.20, tone="violet"),
        Shot("nasa_binary_3d", 0.40, layout="portal", phase=1.30, tone="ember"),
    ),
    "02_hypothesis": (
        Shot("nasa_binary_3d", 1.70, layout="portal", phase=0.00, tone="ember"),
        Shot("original_lens_orbit", 3.90, layout="immersive", phase=1.50, tone="violet"),
        Shot("original_spacetime_waves", 0.80, layout="immersive", phase=2.10, tone="signal"),
        Shot("nasa_disk_corona", 0.20, layout="portal", phase=0.80, tone="ember"),
    ),
    "03_bounce": (
        Shot("original_bounce_tunnel", 0.20, layout="immersive", phase=0.70, tone="ember"),
        Shot("nasa_lmxb_outburst", 0.30, layout="portal", phase=2.00, tone="ember"),
        Shot("original_bounce_tunnel", 4.10, layout="immersive", phase=1.10, tone="signal"),
        Shot("original_universe_dawn", 0.80, layout="immersive", phase=2.70, tone="violet"),
        Shot("original_bounce_tunnel", 8.10, layout="immersive", phase=0.30, tone="cool"),
    ),
    "04_inside": (
        Shot("original_cosmic_web", 0.40, layout="immersive", phase=0.10, tone="cool"),
        Shot("original_universe_dawn", 3.20, layout="immersive", phase=2.40, tone="violet"),
        Shot("original_cosmic_web", 5.10, layout="immersive", phase=1.70, tone="signal"),
        Shot("original_lens_orbit", 8.40, layout="immersive", phase=2.80, tone="violet"),
    ),
    "05_limit": (
        Shot("original_spacetime_waves", 0.50, layout="immersive", phase=0.60, tone="cool"),
        Shot("nasa_binary_3d", 0.70, layout="portal", phase=1.40, tone="ember"),
        Shot("original_cosmic_web", 7.20, layout="immersive", phase=2.20, tone="signal"),
        Shot("original_spacetime_waves", 5.10, layout="immersive", phase=0.20, tone="cool"),
        Shot("nasa_lmxb_outburst", 5.70, layout="portal", phase=2.90, tone="ember"),
    ),
    "06_fingerprint": (
        Shot("original_cmb_signal", 0.20, layout="immersive", phase=2.20, tone="signal"),
        Shot("original_spacetime_waves", 8.00, layout="immersive", phase=0.60, tone="cool"),
        Shot("original_cmb_signal", 4.00, layout="immersive", phase=1.50, tone="signal"),
        Shot("nasa_disk_corona", 0.80, layout="portal", phase=2.60, tone="ember"),
        Shot("original_universe_dawn", 5.20, layout="immersive", phase=0.10, tone="violet"),
        Shot("original_cmb_signal", 8.10, layout="immersive", phase=1.00, tone="signal"),
    ),
    "07_honesty": (
        Shot("original_spacetime_waves", 6.00, layout="immersive", phase=1.80, tone="cool"),
        Shot("original_lens_orbit", 8.80, layout="immersive", phase=0.50, tone="violet"),
        Shot("original_universe_dawn", 9.30, layout="immersive", phase=2.40, tone="violet"),
    ),
    "08_cta": (
        Shot("original_universe_dawn", 0.40, layout="immersive", phase=1.10, tone="violet"),
        Shot("nasa_lmxb_outburst", 6.40, layout="portal", phase=2.80, tone="ember"),
        Shot("original_lens_orbit", 4.70, layout="immersive", phase=0.30, tone="violet"),
        Shot("nasa_binary_3d", 2.00, layout="portal", phase=1.90, tone="ember"),
        Shot("original_universe_dawn", 7.10, layout="immersive", phase=2.10, tone="cool"),
    ),
}


EXTERNAL_SOURCE_INFO: dict[str, dict[str, str]] = {
    "nasa_binary_3d": {
        "local_file": "assets/universe_impact_fresh_v3/nasa_svs14132_supermassive_binary_simulation.gif",
        "title": "Supermassive Binary Black Hole Simulation",
        "page": "https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Supermassive_Binary_Black_Hole_Simulation).gif",
        "primary_source": "https://svs.gsfc.nasa.gov/14132/",
        "credit": "NASA’s Goddard Space Flight Center",
        "license": "Public domain in the United States; Wikimedia Commons identifies this NASA work as public domain.",
        "acquired_for_v3": "2026-08-31",
    },
    "nasa_disk_corona": {
        "local_file": "assets/universe_impact_fresh_v3/nasa_svs14132_disk_and_corona.gif",
        "title": "Disk and Corona",
        "page": "https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Disk_and_Corona).gif",
        "primary_source": "https://svs.gsfc.nasa.gov/14132/",
        "credit": "Aurore Simonnet and NASA’s Goddard Space Flight Center",
        "license": "Public domain in the United States; Wikimedia Commons identifies this NASA work as public domain.",
        "acquired_for_v3": "2026-08-31",
    },
    "nasa_lmxb_outburst": {
        "local_file": "assets/universe_impact_fresh_v3/nasa_svs14132_lmxb_outburst.gif",
        "title": "LMXB Illustration — Black Hole Outburst",
        "page": "https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_LMXB_Illustration).gif",
        "primary_source": "https://svs.gsfc.nasa.gov/14132/",
        "credit": "NASA/Goddard Space Flight Center/Conceptual Image Lab",
        "license": "Public domain in the United States; Wikimedia Commons identifies this NASA work as public domain.",
        "acquired_for_v3": "2026-08-31",
    },
}


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------


def ensure_dirs() -> None:
    for path in (BUILD, BUILD / "video", BUILD / "original_3d", DELIVERABLES, NARRATION_DIR):
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
    except Exception as exc:  # pragma: no cover
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
# Edge TTS — preserve the requested `getaddrinfo` workaround in this v3 build.
# ---------------------------------------------------------------------------


def patch_edge_tts_getaddrinfo() -> None:
    """Resolve speech.platform.bing.com through patched IPv4 getaddrinfo.

    Do not remove this workaround. It follows the requested moon-build pattern:
    some environments give aiohttp an unusable asynchronous DNS result. The
    ThreadedResolver below deliberately reaches this patched socket lookup. A
    supplied EDGE_TTS_BING_IPV4 can pin a known-good IPv4 address while SNI and
    the HTTP Host stay on the original Bing hostname.
    """
    if getattr(socket, "_universe_impact_fresh_v3_edge_patch", False):
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
    socket._universe_impact_fresh_v3_edge_patch = True  # type: ignore[attr-defined]

    try:
        import aiohttp  # type: ignore
        import aiohttp.connector  # type: ignore
        from aiohttp.resolver import ThreadedResolver  # type: ignore

        original_connector_init = aiohttp.connector.TCPConnector.__init__
        if not getattr(aiohttp.connector.TCPConnector, "_universe_impact_fresh_v3_edge_patch", False):
            def patched_connector_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                if kwargs.get("resolver") is None:
                    kwargs["resolver"] = ThreadedResolver()
                return original_connector_init(self, *args, **kwargs)

            aiohttp.connector.TCPConnector.__init__ = patched_connector_init  # type: ignore[method-assign]
            aiohttp.connector.TCPConnector._universe_impact_fresh_v3_edge_patch = True  # type: ignore[attr-defined]
            aiohttp.TCPConnector = aiohttp.connector.TCPConnector  # type: ignore[attr-defined]
    except ImportError:
        pass


async def synthesize_one(scene: Scene, force: bool) -> None:
    path = NARRATION_DIR / f"{scene.key}.mp3"
    if not force and path.exists() and path.stat().st_size > 1024:
        print(f"[voice] Reusing {path.name}")
        return

    patch_edge_tts_getaddrinfo()
    try:
        import edge_tts  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install edge-tts first: python3 -m pip install edge-tts") from exc

    path.unlink(missing_ok=True)
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
            if attempt < 3:
                await asyncio.sleep(float(attempt))
    raise RuntimeError(
        "Edge TTS could not reach speech.platform.bing.com after the IPv4/getaddrinfo workaround. "
        "Run --voice-only on an Edge-permitted host, then run --render-only."
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
# Timeline, fresh 3D sources, and all-motion source montage
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
                "Run --voice-only on an Edge-permitted host, or provide the requested cache."
            )
        voice_duration = media_duration(audio_path, ffmpeg)
        gap = LAST_SCENE_GAP if index == len(SCENES) - 1 else SCENE_GAP
        duration = voice_duration + gap
        timeline.append(
            {"scene": scene, "start": cursor, "voice_duration": voice_duration, "duration": duration, "end": cursor + duration}
        )
        cursor += duration
    return timeline


def plan_scene_shots(scene: Scene, duration: float) -> list[tuple[Shot, float]]:
    templates = SHOT_TEMPLATES.get(scene.key)
    if not templates:
        raise RuntimeError(f"No fresh motion plan exists for {scene.key}")
    total_weight = sum(item.weight for item in templates)
    remaining = duration
    plan: list[tuple[Shot, float]] = []
    for index, shot in enumerate(templates):
        if index == len(templates) - 1:
            shot_duration = remaining
        else:
            shot_duration = round(duration * shot.weight / total_weight * FPS) / FPS
            remaining -= shot_duration
        plan.append((shot, max(1 / FPS, shot_duration)))
    return plan


def fresh_source_paths(ffmpeg: str, force: bool) -> tuple[dict[str, Path], dict[str, dict[str, str]]]:
    """Generate original clips, bind fresh external GIFs, and validate inputs."""
    for key, info in EXTERNAL_SOURCE_INFO.items():
        path = ROOT / info["local_file"]
        if not path.exists():
            raise RuntimeError(f"Fresh public-domain source is missing: {path}")
        if path.stat().st_size < 100_000:
            raise RuntimeError(f"Fresh source appears truncated: {path}")

    original_paths = render_fresh_3d_sources(BUILD / "original_3d", ffmpeg, force=force, duration=13.0)
    paths: dict[str, Path] = {
        "nasa_binary_3d": FRESH_ASSETS / "nasa_svs14132_supermassive_binary_simulation.gif",
        "nasa_disk_corona": FRESH_ASSETS / "nasa_svs14132_disk_and_corona.gif",
        "nasa_lmxb_outburst": FRESH_ASSETS / "nasa_svs14132_lmxb_outburst.gif",
    }
    source_info: dict[str, dict[str, str]] = {key: dict(value) for key, value in EXTERNAL_SOURCE_INFO.items()}
    for visual_key, path in original_paths.items():
        key = f"original_{visual_key}"
        paths[key] = path
        source_info[key] = {
            "local_file": str(path.relative_to(ROOT)),
            "title": visual_key.replace("_", " ").title() + " — original Universe Impact 3D sequence",
            "page": "Created by fresh_3d_visuals.py during this v3 build.",
            "primary_source": "Original procedural geometry, particles, camera animation, and local generated textures.",
            "credit": "Universe Impact original visualization",
            "license": "Original project output; no third-party footage or source-audio used.",
            "acquired_for_v3": "Rendered during build",
        }
    # Confirm that every planned key exists before dispatching expensive FFmpeg jobs.
    planned = {shot.source for shots in SHOT_TEMPLATES.values() for shot in shots}
    missing = sorted(planned - set(paths))
    if missing:
        raise RuntimeError(f"Missing v3 source bindings: {', '.join(missing)}")
    return paths, source_info


def grade_for(tone: str) -> str:
    if tone == "ember":
        return "eq=contrast=1.10:saturation=1.20:gamma_r=1.05:gamma_b=0.94"
    if tone == "signal":
        return "eq=contrast=1.08:saturation=1.16:gamma_g=1.04:gamma_b=1.05"
    if tone == "violet":
        return "eq=contrast=1.09:saturation=1.15:gamma_r=1.03:gamma_b=1.04"
    return "eq=contrast=1.08:saturation=1.12:gamma_b=1.04"


def build_immersive_filter(input_index: int, shot_index: int, shot: Shot, duration: float) -> str:
    phase = shot.phase
    x_expr = f"60+24*sin(0.73*t+{phase:.3f})"
    y_expr = f"107+38*cos(0.51*t+{phase:.3f})"
    return (
        f"[{input_index}:v]trim=duration={duration:.3f},setpts=PTS-STARTPTS,"
        "scale=1250:2224:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={OUT_W}:{OUT_H}:x='{x_expr}':y='{y_expr}':exact=1,"
        f"fps={FPS},{grade_for(shot.tone)},vignette=PI/5.2:eval=frame,"
        "unsharp=5:5:0.40:5:5:0.0,noise=alls=2:allf=t,setsar=1,format=yuv420p"
        f"[shot{shot_index}]"
    )


def build_portal_filter(input_index: int, shot_index: int, shot: Shot, duration: float) -> list[str]:
    """Preserve a wide animated source in a moving vertical observation portal."""
    phase = shot.phase
    bg_x = f"(in_w-out_w)*(0.50+0.06*sin(0.82*t+{phase:.3f}))"
    bg_y = f"(in_h-out_h)*(0.50+0.10*cos(0.66*t+{phase:.3f}))"
    overlay_x = f"40+10*sin(0.76*t+{phase:.3f})"
    overlay_y = f"675+14*cos(0.72*t+{phase:.3f})"
    return [
        f"[{input_index}:v]trim=duration={duration:.3f},setpts=PTS-STARTPTS,split=2[portal_bg_src{shot_index}][portal_fg_src{shot_index}]",
        (
            f"[portal_bg_src{shot_index}]scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={OUT_W}:{OUT_H}:x='{bg_x}':y='{bg_y}':exact=1,fps={FPS},"
            f"boxblur=20:3,{grade_for(shot.tone)},eq=brightness=-0.18,"
            "vignette=PI/4:eval=frame,drawgrid=w=90:h=90:t=1:c=0x4BEFFF@0.08,setsar=1"
            f"[portal_bg{shot_index}]"
        ),
        (
            f"[portal_fg_src{shot_index}]crop=iw:ih-18:0:0,scale=1000:562:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=1000:562:(ow-iw)/2:(oh-ih)/2:color=0x03050C,fps=30,"
            f"{grade_for(shot.tone)},unsharp=5:5:0.42:5:5:0.0,setsar=1"
            f"[portal_fg{shot_index}]"
        ),
        (
            f"[portal_bg{shot_index}]drawbox=x=30:y=659:w=1020:h=594:color=0x57EAF8@0.72:t=3,"
            "drawbox=x=39:y=668:w=1002:h=576:color=0xFF8950@0.20:t=1"
            f"[portal_frame{shot_index}]"
        ),
        (
            f"[portal_frame{shot_index}][portal_fg{shot_index}]overlay=x='{overlay_x}':y='{overlay_y}':shortest=1,"
            "noise=alls=2:allf=t,setsar=1,format=yuv420p"
            f"[shot{shot_index}]"
        ),
    ]


def render_scene(
    entry: dict[str, float | Scene],
    index: int,
    ffmpeg: str,
    source_paths: dict[str, Path],
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
        source = source_paths[shot.source]
        # All source inputs are intentionally looped. It avoids a freeze / black
        # frame when an editorial excerpt crosses a short GIF's loop boundary.
        command.extend(["-stream_loop", "-1", "-ss", f"{shot.start:.3f}", "-t", f"{shot_duration + 0.12:.3f}", "-i", str(source)])
        if shot.layout == "immersive":
            filters.append(build_immersive_filter(shot_index, shot_index, shot, shot_duration))
        elif shot.layout == "portal":
            filters.extend(build_portal_filter(shot_index, shot_index, shot, shot_duration))
        else:
            raise RuntimeError(f"Unknown v3 shot layout: {shot.layout!r}")

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
    run(command, label=f"fresh v3 scene {index + 1}: {scene.key}")
    return output


def concat_visuals(scene_files: list[Path], ffmpeg: str, force: bool) -> Path:
    output = BUILD / "visual_base_fresh_3d_v3.mp4"
    if not force and output.exists() and output.stat().st_size > 100_000:
        return output
    concat_list = BUILD / "visual_concat_fresh_3d_v3.txt"
    concat_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in scene_files), encoding="utf-8")
    run(
        [ffmpeg, "-y", "-loglevel", "warning", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", "-movflags", "+faststart", str(output)],
        label="concat fresh v3 visual scenes",
    )
    return output


def cut_times(timeline: list[dict[str, float | Scene]]) -> list[float]:
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
# Captions, score, final mux, cover, and publication package
# ---------------------------------------------------------------------------


def write_ass_and_srt(timeline: list[dict[str, float | Scene]]) -> tuple[Path, Path]:
    ass_path = BUILD / "universe_impact_fresh_3d_v3.ass"
    srt_path = DELIVERABLES / "universe_impact_black_hole_reel_fresh_3d_v3.srt"
    total_end = float(timeline[-1]["end"])
    ass_lines = [
        "[Script Info]",
        "Title: Universe Impact — fresh public-domain and original 3D Reel v3",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Brand,DejaVu Sans,23,&H00CDEAF6,&H000000FF,&H8C02050D,&H8C02050D,1,0,0,0,100,100,1.0,0,1,1.4,1.6,7,55,55,52,1",
        "Style: Source,DejaVu Sans,16,&H00CDEAF6,&H000000FF,&H9602050D,&H9602050D,0,0,0,0,100,100,0.4,0,1,1.1,1.2,9,55,55,56,1",
        "Style: Evidence,DejaVu Sans,22,&H0077E9FF,&H000000FF,&H9202050D,&H9202050D,1,0,0,0,100,100,0.8,0,1,1.5,1.8,2,58,58,62,1",
        "Style: Kicker,DejaVu Sans,27,&H006DEBF7,&H000000FF,&H9602050D,&H9602050D,1,0,0,0,100,100,2.0,0,1,1.7,2.0,8,55,55,255,1",
        "Style: Headline,DejaVu Sans,59,&H00FFFFFF,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,0.5,0,1,2.8,2.5,8,50,50,318,1",
        "Style: Beat,DejaVu Sans,39,&H00FFFFFF,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,1.0,0,1,2.4,2.1,2,70,70,290,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        f"Dialogue: 0,0:00:00.00,{ass_time(total_end)},Brand,,0,0,0,,UNIVERSE IMPACT  •  COSMIC QUESTIONS",
        f"Dialogue: 0,0:00:00.00,{ass_time(total_end)},Source,,0,0,0,,FRESH 3D VISUALS  •  PD + ORIGINAL",
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
        card_end = min(end - 0.15, start + min(3.25, max(2.45, duration * 0.43)))
        ass_lines.append(f"Dialogue: 1,{ass_time(start + 0.12)},{ass_time(card_end)},Kicker,,0,0,0,,{{\\fad(150,220)}}{clean_ass(scene.kicker)}")
        ass_lines.append(f"Dialogue: 2,{ass_time(start + 0.30)},{ass_time(card_end)},Headline,,0,0,0,,{{\\fad(190,240)}}{clean_ass(scene.headline)}")
        beat_start = card_end - 0.08
        beat_end = end - 0.13
        beat_span = max(0.20, (beat_end - beat_start) / len(scene.beats))
        for beat_index, beat in enumerate(scene.beats):
            local_start = beat_start + beat_index * beat_span
            local_end = min(beat_end, local_start + beat_span + 0.04)
            ass_lines.append(f"Dialogue: 3,{ass_time(local_start)},{ass_time(local_end)},Beat,,0,0,0,,{{\\fad(130,180)}}{clean_ass(beat)}")
        srt_lines.extend([str(number), f"{srt_time(start)} --> {srt_time(voice_end)}", scene.narration, ""])

    ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return ass_path, srt_path


def make_music(path: Path, duration: float, scene_starts: list[float], editorial_cuts: list[float], force: bool) -> None:
    """Make a unique, non-sampled pulse bed and cut accents locally."""
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


def render_final(visual_base: Path, ass_path: Path, timeline: list[dict[str, float | Scene]], ffmpeg: str, force: bool) -> Path:
    """Burn captions, mix audio, mux, and validate in separate stable passes."""
    output = DELIVERABLES / "universe_impact_black_hole_reel_fresh_3d_v3.mp4"
    if not force and output.exists() and output.stat().st_size > 100_000:
        return output
    total_duration = float(timeline[-1]["end"])
    music_path = BUILD / "universe_impact_fresh_3d_v3_original_score.wav"
    captioned_video = BUILD / "visual_captioned_fresh_3d_v3.mp4"
    mixed_audio = BUILD / "mixed_audio_fresh_3d_v3.m4a"
    make_music(music_path, total_duration, [float(entry["start"]) for entry in timeline], cut_times(timeline), force)
    fonts_dir = str(Path(font_path()).parent)
    run(
        [
            ffmpeg, "-y", "-loglevel", "warning", "-i", str(visual_base),
            "-vf", f"ass=filename='{ass_path.as_posix()}':fontsdir='{fonts_dir}',format=yuv420p",
            "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart", str(captioned_video),
        ],
        label="burn fresh v3 kinetic captions",
    )
    run([ffmpeg, "-v", "error", "-i", str(captioned_video), "-f", "null", "-"], label="captioned v3 video decode validation", quiet=True)

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
    audio_command.extend([
        "-filter_complex", ";".join(audio_filters), "-map", "[aout]", "-vn", "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-movflags", "+faststart", str(mixed_audio),
    ])
    run(audio_command, label="mix fresh v3 narration and original score")
    run([ffmpeg, "-v", "error", "-i", str(mixed_audio), "-f", "null", "-"], label="mixed v3 audio decode validation", quiet=True)
    run(
        [
            ffmpeg, "-y", "-loglevel", "warning", "-i", str(captioned_video), "-i", str(mixed_audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-shortest", "-movflags", "+faststart", str(output),
        ],
        label="mux final fresh v3 Facebook Reel",
    )
    run([ffmpeg, "-v", "error", "-i", str(output), "-f", "null", "-"], label="fresh v3 full decode validation", quiet=True)
    return output


def extract_cover(video: Path, ffmpeg: str) -> Path:
    cover = DELIVERABLES / "universe_impact_black_hole_cover_fresh_3d_v3.jpg"
    run(
        [
            ffmpeg, "-y", "-loglevel", "warning", "-ss", "0.900", "-i", str(video), "-frames:v", "1", "-update", "1", "-q:v", "2",
            "-vf", f"scale={OUT_W}:{OUT_H}:flags=lanczos", str(cover),
        ],
        label="fresh v3 cover image",
    )
    return cover


def detailed_shot_manifest(timeline: list[dict[str, float | Scene]], source_info: dict[str, dict[str, str]]) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for entry in timeline:
        scene = entry["scene"]
        assert isinstance(scene, Scene)
        cursor = float(entry["start"])
        for shot, duration in plan_scene_shots(scene, float(entry["duration"])):
            origin = source_info[shot.source]
            details.append(
                {
                    "scene": scene.key,
                    "timeline_start": round(cursor, 3),
                    "timeline_end": round(cursor + duration, 3),
                    "source_key": shot.source,
                    "source_start": shot.start,
                    "layout": shot.layout,
                    "source_title": origin["title"],
                    "source_page": origin["page"],
                    "external_public_domain_source": shot.source in EXTERNAL_SOURCE_INFO,
                }
            )
            cursor += duration
    return details


def write_publishing_pack(timeline: list[dict[str, float | Scene]], final_video: Path, cover: Path, ffmpeg: str) -> Path:
    package = DELIVERABLES / "UNIVERSE_IMPACT_FACEBOOK_POST_FRESH_3D_V3.md"
    duration = media_duration(final_video, ffmpeg)
    package.write_text(
        f"""# Universe Impact — Facebook publishing pack (fresh 3D v3)

## Reel title
**Could the Big Bang Be an Inside View? | Hypothesis, Not Proof**

## Ready-to-paste Facebook caption
What if the Big Bang was not the beginning of *everything* — but the inside view of a black hole in a larger cosmos? 🌌

Black-hole cosmology is a real family of speculative ideas, but it is **not established science**. The most exciting question is not “can we imagine it?” It is: **what observation could prove it wrong or right?**

A serious model needs a fingerprint — perhaps in the cosmic microwave background or primordial gravitational waves — that rival explanations cannot copy.

What cosmic clue would convince you? 👇

Follow **Universe Impact** for big cosmic questions — wonder first, evidence always.

#UniverseImpact #Space #Astronomy #BlackHole #BigBang #Cosmology #Science #CosmicMystery

## Pinned-comment prompt
**Mind-bender:** If this idea ever became testable, what observation should scientists look for first: a CMB pattern, primordial gravitational waves, or something else?

## Upload settings
- **File:** `{final_video.name}`
- **Format:** 1080 × 1920, H.264/AAC, vertical 9:16, 30 fps
- **Length:** approximately {duration:.1f} seconds
- **Cover:** `{cover.name}`
- **Captions:** Upload `universe_impact_black_hole_reel_fresh_3d_v3.srt` if Facebook's caption option is available. The Reel already includes brief burned-in kinetic text for silent autoplay.
- **Suggested first-frame hook:** “WHAT IF THE BIG BANG WAS AN INSIDE VIEW?”

## Accessibility alt text
A fast-moving vertical science Reel from Universe Impact. New animated visualizations show a luminous accretion disk warping around a dark black-hole shadow, two black holes spiraling together, particles collapsing and rebounding through a conceptual tunnel, a flight through a three-dimensional cosmic web, a rotating pattern sphere, and ripples across a warped grid. On-screen text repeatedly labels black-hole cosmology as a hypothesis, not established fact.

## Editorial integrity note
This Reel intentionally separates **hypothesis** from **evidence**. It does **not** claim NASA, JWST, the CMB, or gravitational-wave observations have proved that we live inside a black hole. “Black-hole cosmology” remains a speculative family of models that must yield a unique, testable prediction before it can gain scientific support.

## Fresh visual / audio provenance
This is a **true replacement**, not a v2 recut. The build does not read the legacy v2 source files or use any of v2's five NASA asset URLs.

- **Three fresh external animated clips:** newly acquired public-domain animated GIFs from NASA SVS 14132, via their Wikimedia Commons public-domain file pages. They are real animated 3D / conceptual visual clips, retained as moving footage and re-edited in the Reel:
  1. *Supermassive Binary Black Hole Simulation* — NASA’s Goddard Space Flight Center
  2. *Disk and Corona* — Aurore Simonnet and NASA’s Goddard Space Flight Center
  3. *LMXB Illustration — Black Hole Outburst* — NASA/Goddard Space Flight Center/Conceptual Image Lab
- **Six original moving 3D sequences:** lens-orbit geometry, a conceptual collapse-to-bounce tunnel, cosmic-web flight, rotating pattern sphere, warped-spacetime grid, and cosmic-dawn finale. These are newly rendered by `fresh_3d_visuals.py` from local geometry, particles, perspective-camera motion, and generated glow — no external footage or still background is used for those story beats.
- **Rights basis:** the selected Commons pages identify each NASA SVS 14132 asset as public domain in the United States. NASA SVS states its content is public domain unless otherwise noted. The exact pages, hashes, credits, and local filenames are in `assets/universe_impact_fresh_v3/SOURCES.md` and the v3 manifest.
- **Audio:** the source GIFs carry no source audio; no external soundtrack is used. The score and cut accents are original generated audio. The requested `edge-tts / en-US-ChristopherNeural / +0%` configuration remains in the build script.

### Important rights / voice publishing note
The source documentation supports the public-domain classification of the three listed external GIFs; retain the NASA credits in the description or credits where practical.

The current sandbox cannot independently validate the existing narration cache's speaker identity because Edge TTS network access is blocked here. Before publicly stating that a newly rendered file uses the requested exact speaker, rerun `--voice-only` on an Edge-permitted host; the code specifies **`en-US-ChristopherNeural` at `+0%`** and retains the DNS workaround.

## Research links
- NASA SVS 14132: https://svs.gsfc.nasa.gov/14132/
- NASA SVS usage statement: https://svs.gsfc.nasa.gov/
- Commons: Supermassive Binary Black Hole Simulation: https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Supermassive_Binary_Black_Hole_Simulation).gif
- Commons: Disk and Corona: https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Disk_and_Corona).gif
- Commons: LMXB Illustration: https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_LMXB_Illustration).gif

Keep “hypothesis,” “speculative model,” and “no direct proof” in captions or replies. Do not turn the premise into “NASA proved we live inside a black hole.”
""",
        encoding="utf-8",
    )
    return package


def write_render_manifest(
    timeline: list[dict[str, float | Scene]],
    final_video: Path,
    cover: Path,
    ffmpeg: str,
    source_paths: dict[str, Path],
    source_info: dict[str, dict[str, str]],
) -> Path:
    manifest_path = DELIVERABLES / "universe_impact_black_hole_reel_fresh_3d_v3_manifest.json"
    details = detailed_shot_manifest(timeline, source_info)
    serializable_sources: dict[str, dict[str, str | float]] = {}
    for key, info in source_info.items():
        path = source_paths[key]
        serializable_sources[key] = {
            **info,
            "sha256": sha256(path),
            "duration_seconds": round(media_duration(path, ffmpeg), 3),
            "bytes": path.stat().st_size,
        }
    manifest = {
        "version": "fresh-3d-v3",
        "title": "Could the Big Bang Be an Inside View? | Hypothesis, Not Proof",
        "page": "Universe Impact",
        "output": final_video.name,
        "cover": cover.name,
        "format": {"width": OUT_W, "height": OUT_H, "fps": FPS, "duration_seconds": round(media_duration(final_video, ffmpeg), 3)},
        "source_replacement": {
            "is_true_replacement_not_v2_recut": True,
            "legacy_v2_source_directory_read": False,
            "legacy_v2_asset_paths_excluded": [
                "sources/clip1_bh_orbit.mp4",
                "sources/clip2_tde_shred.mp4",
                "sources/clip3_tde_disk.mp4",
                "sources/clip4_tde_partial.mp4",
                "sources/clip5_tde_fading.mov",
            ],
            "fresh_external_public_domain_animated_assets": 3,
            "original_3d_video_tracks_rendered": 6,
            "source_audio_used": False,
        },
        "visual_strategy": {
            "static_story_backgrounds_used": False,
            "total_moving_shots": len(details),
            "external_public_domain_animation_shots": sum(1 for shot in details if shot["external_public_domain_source"]),
            "original_3d_animation_shots": sum(1 for shot in details if not shot["external_public_domain_source"]),
            "typical_shot_duration_seconds": "approximately 2.1–2.6",
            "edit_elements": [
                "new public-domain animated NASA 3D source clips",
                "six original 3D moving visual tracks",
                "portrait reframing and animated observation portals",
                "kinetic headline cards",
                "original procedural score and cut accents",
            ],
        },
        "voice_requested": {"engine": "edge-tts", "voice": VOICE, "rate": RATE},
        "voice_verification": "The exact requested Edge-TTS configuration and getaddrinfo workaround are retained in the v3 build script. The existing cache could not be independently re-authenticated in this sandbox because the Edge endpoint is unreachable.",
        "scientific_framing": "Speculative hypothesis; no direct observational proof is claimed.",
        "source_clips": serializable_sources,
        "timeline": [
            {"key": entry["scene"].key, "start": round(float(entry["start"]), 3), "end": round(float(entry["end"]), 3), "narration": entry["scene"].narration}
            for entry in timeline  # type: ignore[index,union-attr]
        ],
        "shots": details,
        "final_file_sha256": sha256(final_video),
        "cover_sha256": sha256(cover),
        "decode_validation": "ffmpeg -v error -i final.mp4 -f null - completed with exit code 0 during build",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def build_render(force: bool) -> tuple[Path, Path, Path, Path]:
    ensure_dirs()
    ffmpeg = find_ffmpeg()
    timeline = get_scene_timeline(ffmpeg)
    source_paths, source_info = fresh_source_paths(ffmpeg, force)
    print("\n[plan] Fresh v3 scene timing / all-motion cuts")
    for entry in timeline:
        scene = entry["scene"]
        assert isinstance(scene, Scene)
        plan = plan_scene_shots(scene, float(entry["duration"]))
        print(f"  {scene.key}: {float(entry['start']):5.2f}s → {float(entry['end']):5.2f}s ({len(plan)} moving fresh-source passages)")
    scene_files = [render_scene(entry, index, ffmpeg, source_paths, force) for index, entry in enumerate(timeline)]
    visual_base = concat_visuals(scene_files, ffmpeg, force)
    ass_path, _ = write_ass_and_srt(timeline)
    final_video = render_final(visual_base, ass_path, timeline, ffmpeg, force)
    cover = extract_cover(final_video, ffmpeg)
    package = write_publishing_pack(timeline, final_video, cover, ffmpeg)
    manifest = write_render_manifest(timeline, final_video, cover, ffmpeg, source_paths, source_info)
    return final_video, cover, package, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the fresh-source, original-3D Universe Impact Reel v3.")
    parser.add_argument("--voice-only", action="store_true", help="Create/recreate requested Edge TTS narration only.")
    parser.add_argument("--render-only", action="store_true", help="Render using the existing narration cache.")
    parser.add_argument("--force", action="store_true", help="Recreate 3D tracks, scenes, score, final output, and cover.")
    args = parser.parse_args()
    if args.voice_only and args.render_only:
        parser.error("--voice-only and --render-only cannot be used together")
    ensure_dirs()
    if not args.render_only:
        asyncio.run(synthesize_voice(args.force))
    if not args.voice_only:
        final_video, cover, package, manifest = build_render(args.force)
        print("\nComplete fresh v3 delivery:")
        print(f"  video:    {final_video}")
        print(f"  cover:    {cover}")
        print(f"  post:     {package}")
        print(f"  manifest: {manifest}")


if __name__ == "__main__":
    main()
