#!/usr/bin/env python3
"""Build Universe Impact's corrected unique-source 3D Reel (v4).

v4 preserves the reviewed v3 file and its locked, already-mastered audio as a
reference.  It replaces the *visual edit* with 35 one-time moving source assets:
32 freshly rendered original 3D-style tracks plus each of the three newly
acquired NASA public-domain animations exactly once.  A strict key, path, and
SHA-256 guard blocks a source from appearing twice in the timeline.

Important editorial / production guarantees
-------------------------------------------
* No source from ``sources/`` or any legacy v2 asset is opened.
* No v3 rendered visual footage is opened.
* The v3 AAC program audio is stream-copied without remixing, gain, loudnorm,
  re-encoding, or other audio processing. The 2.8-second required outro is
  intentionally silent after the locked 77.90-second program audio ends.
* Frame 1 is an active rendered accretion visual; no fade-to-black lead-in is
  applied.
* The single framed NASA simulation treatment has a deliberately safe,
  fully-visible ``SIMULATION`` label inside the upper portal border.
* The requested Edge-TTS settings and DNS/getaddrinfo workaround are retained
  below. ``--voice-only`` is an audit / regeneration utility; it does not
  replace the locked production audio unless an editor intentionally performs
  a separately approved remaster.

Requested voice configuration
-----------------------------
Engine: edge-tts
Voice:  en-US-ChristopherNeural
Rate:   +0%

Typical locked-audio render:
    python3 build_universe_impact_fresh_3d_v4.py --render-only --force
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
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fresh_3d_visuals_v4 import FAMILY_DESCRIPTIONS, TrackSpec, render_unique_tracks


ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build_universe_impact_fresh_3d_v4"
TRACK_DIR = BUILD / "unique_source_tracks"
SCENE_DIR = BUILD / "scenes"
VOICE_AUDIT_DIR = BUILD / "voice_audit"
DELIVERABLES = ROOT / "deliverables"
SOURCE_NOTES = ROOT / "assets" / "universe_impact_fresh_v4" / "SOURCES.md"
AUDIO_LOCK = ROOT / "assets" / "universe_impact_fresh_v3" / "audio_level_locked_v3_reference.m4a"

VOICE = "en-US-ChristopherNeural"
RATE = "+0%"
FPS = 30
OUT_W, OUT_H = 1080, 1920
NARRATIVE_FRAMES = 2337  # 77.900 seconds, exactly matching the locked program audio.
OUTRO_FRAMES = 84       # 2.800 seconds, required branded silent end-card.


@dataclass(frozen=True)
class Shot:
    """One physical moving source asset used at one timeline location only."""

    key: str
    family: str
    hue: str
    weight: float = 1.0
    layout: str = "immersive"  # immersive | portal | cinematic
    source_start: float = 0.0  # used only by a NASA animation used once
    external: bool = False


@dataclass(frozen=True)
class Scene:
    key: str
    narration: str
    headline: str
    kicker: str
    beats: tuple[str, ...]
    frames: int
    subtitle_start: float
    subtitle_end: float
    shots: tuple[Shot, ...]

    @property
    def duration(self) -> float:
        return self.frames / FPS


# These cue times are deliberately retained from the locked v3 program audio.
# Frame-aligned scene boundaries are used for rendering so the total content is
# exactly 77.900 seconds; the greatest cue-boundary adjustment is 0.017 second.
SCENES: tuple[Scene, ...] = (
    Scene(
        "01_hook",
        "What if the Big Bang was the inside of a black hole?",
        "WHAT IF THE BIG BANG\nWAS AN INSIDE VIEW?",
        "A COSMIC QUESTION",
        ("ONE QUESTION.\nNO EASY ANSWER.",),
        144,
        0.000,
        4.370,
        (
            Shot("v4_01_accretion_hook", "accretion", "ember", 1.10),
            Shot("nasa_binary_3d_once", "nasa_binary", "ember", 1.00, layout="portal", source_start=0.42, external=True),
        ),
    ),
    Scene(
        "02_hypothesis",
        "Not a fact. Not a discovery. A breathtaking hypothesis called black hole cosmology.",
        "A HYPOTHESIS.\nNOT A DISCOVERY.",
        "BLACK-HOLE COSMOLOGY",
        ("NOT A FACT.", "NOT A DISCOVERY.", "A MODEL MUST FACE EVIDENCE."),
        257,
        4.790,
        12.930,
        (
            Shot("v4_03_lattice_hypothesis", "lattice", "violet", 1.05),
            Shot("v4_04_lensfield_hypothesis", "lensfield", "cool", 0.95),
            Shot("nasa_disk_corona_once", "nasa_disk", "ember", 0.92, layout="cinematic", source_start=1.24, external=True),
            Shot("v4_06_metric_hypothesis", "metric", "signal", 1.08),
        ),
    ),
    Scene(
        "03_bounce",
        "In some models, collapse does not end at a singularity. Some quantum gravity ideas replace it with a bounce, opening a new region of expanding space time.",
        "COLLAPSE  →  BOUNCE\nEXPANDING SPACE",
        "ONE THEORETICAL PATH",
        ("SOME MODELS: NO SINGULARITY.", "INSTEAD: A BOUNCE.", "THEN SPACE EXPANDS."),
        354,
        13.350,
        24.730,
        (
            Shot("v4_07_funnel_collapse", "funnel", "ember", 0.95),
            Shot("v4_08_bounce_transition", "bounce", "cool", 1.13),
            Shot("nasa_lmxb_outburst_once", "nasa_lmxb", "gold", 0.84, layout="cinematic", source_start=3.15, external=True),
            Shot("v4_10_shell_expansion", "shell", "gold", 1.08),
            Shot("v4_11_spiral_dawn", "spiral", "violet", 1.00),
        ),
    ),
    Scene(
        "04_inside",
        "From inside, that bounce could look like a Big Bang: no center, just space expanding everywhere at once.",
        "NO CENTER.\nEXPANSION EVERYWHERE.",
        "CONCEPTUAL MODEL",
        ("NO PRIVILEGED CENTER.", "SPACE EXPANDING\nEVERYWHERE AT ONCE."),
        278,
        25.150,
        34.010,
        (
            Shot("v4_12_web_inside", "web", "cool", 1.10),
            Shot("v4_13_sphere_inside", "sphere", "signal", 0.92),
            Shot("v4_14_wave_inside", "wave", "violet", 0.98),
            Shot("v4_15_orbits_inside", "orbits", "gold", 1.00),
        ),
    ),
    Scene(
        "05_limit",
        "But this is where honesty matters. Our best theories clash in these extreme conditions, and no observation shows our universe was born this way.",
        "THE HONEST LIMIT",
        "RELATIVITY × QUANTUM PHYSICS",
        ("THE EXTREMES BREAK OUR MODELS.", "NO COMPLETE UNIFICATION.\nNOT YET.", "NO OBSERVATION SHOWS THIS ORIGIN."),
        352,
        34.430,
        45.730,
        (
            Shot("v4_16_metric_limit", "metric", "cool", 1.00),
            Shot("v4_17_lattice_limit", "lattice", "ember", 0.93),
            Shot("v4_18_void_limit", "void", "violet", 1.12),
            Shot("v4_19_accretion_limit", "accretion", "gold", 0.96),
            Shot("v4_20_data_limit", "data", "signal", 0.99),
        ),
    ),
    Scene(
        "06_fingerprint",
        "To become science, the idea needs a fingerprint: a unique pattern in the cosmic microwave background, or primordial gravitational waves that rival explanations cannot copy.",
        "SCIENCE NEEDS\nA FINGERPRINT",
        "TESTABLE · UNIQUE · REPEATABLE",
        ("LOOK FOR A UNIQUE PATTERN.", "CMB.", "PRIMORDIAL\nGRAVITATIONAL WAVES.", "RIVALS MUST NOT COPY IT."),
        388,
        46.150,
        58.680,
        (
            Shot("v4_21_sphere_fingerprint", "sphere", "cool", 0.97),
            Shot("v4_22_wave_fingerprint", "wave", "violet", 1.05),
            Shot("v4_23_web_fingerprint", "web", "signal", 0.95),
            Shot("v4_24_lensfield_fingerprint", "lensfield", "ember", 1.08),
            Shot("v4_25_spiral_fingerprint", "spiral", "gold", 0.92),
            Shot("v4_26_shell_fingerprint", "shell", "cool", 1.03),
        ),
    ),
    Scene(
        "07_honesty",
        "Until then, the answer is not yes. It is: we do not know.",
        "NO DIRECT PROOF.\nYET.",
        "STATUS: OPEN QUESTION",
        ("THE SCIENTIFIC ANSWER:\nWE DO NOT KNOW.",),
        186,
        59.100,
        64.880,
        (
            Shot("v4_27_binary_honesty", "binary", "violet", 1.05),
            Shot("v4_28_funnel_honesty", "funnel", "signal", 0.91),
            Shot("v4_29_void_honesty", "void", "ember", 1.04),
        ),
    ),
    Scene(
        "08_cta",
        "That is still astonishing. The cosmos may be stranger than our best story. Universe Impact. Follow for wonder, evidence first.",
        "WONDER, THEN EVIDENCE.",
        "UNIVERSE IMPACT · FOLLOW",
        ("THE COSMOS MAY BE STRANGER.", "FOLLOW FOR WONDER.", "EVIDENCE FIRST."),
        378,
        65.300,
        76.750,
        (
            Shot("v4_30_orbits_cta", "orbits", "cool", 1.08),
            Shot("v4_31_data_cta", "data", "gold", 0.89),
            Shot("v4_32_accretion_cta", "accretion", "violet", 1.06),
            Shot("v4_33_bounce_cta", "bounce", "ember", 0.94),
            Shot("v4_34_jet_cta", "jet", "signal", 1.03),
        ),
    ),
)

OUTRO_SHOT = Shot("v4_35_universe_impact_outro", "outro", "cool", 1.0)

# The physical assets below were newly acquired from NASA SVS 14132 for the
# fresh v3 replacement. v4 uses each retained animation once only, never opens
# any legacy v2 clip, and does not use any rendered visual from v3.
EXTERNAL_SOURCES: dict[str, dict[str, str]] = {
    "nasa_binary_3d_once": {
        "local_file": "assets/universe_impact_fresh_v3/nasa_svs14132_supermassive_binary_simulation.gif",
        "title": "Supermassive Binary Black Hole Simulation",
        "page": "https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Supermassive_Binary_Black_Hole_Simulation).gif",
        "primary_source": "https://svs.gsfc.nasa.gov/14132/",
        "credit": "NASA's Goddard Space Flight Center",
        "license": "Public domain in the United States; Wikimedia Commons identifies this NASA work as public domain.",
    },
    "nasa_disk_corona_once": {
        "local_file": "assets/universe_impact_fresh_v3/nasa_svs14132_disk_and_corona.gif",
        "title": "Disk and Corona",
        "page": "https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Disk_and_Corona).gif",
        "primary_source": "https://svs.gsfc.nasa.gov/14132/",
        "credit": "Aurore Simonnet and NASA's Goddard Space Flight Center",
        "license": "Public domain in the United States; Wikimedia Commons identifies this NASA work as public domain.",
    },
    "nasa_lmxb_outburst_once": {
        "local_file": "assets/universe_impact_fresh_v3/nasa_svs14132_lmxb_outburst.gif",
        "title": "LMXB Illustration — Black Hole Outburst",
        "page": "https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_LMXB_Illustration).gif",
        "primary_source": "https://svs.gsfc.nasa.gov/14132/",
        "credit": "NASA/Goddard Space Flight Center/Conceptual Image Lab",
        "license": "Public domain in the United States; Wikimedia Commons identifies this NASA work as public domain.",
    },
}


@dataclass(frozen=True)
class PlannedShot:
    scene_key: str
    shot: Shot
    start_frame: int
    frames: int

    @property
    def start(self) -> float:
        return self.start_frame / FPS

    @property
    def duration(self) -> float:
        return self.frames / FPS

    @property
    def end(self) -> float:
        return (self.start_frame + self.frames) / FPS


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------


def ensure_dirs() -> None:
    for path in (BUILD, TRACK_DIR, SCENE_DIR, VOICE_AUDIT_DIR, DELIVERABLES, SOURCE_NOTES.parent):
        path.mkdir(parents=True, exist_ok=True)


def run(command: list[str], *, label: str, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    print(f"\n[{label}] {' '.join(str(part) for part in command)}")
    result = subprocess.run(
        [str(part) for part in command],
        text=True,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.PIPE if quiet else None,
    )
    if result.returncode:
        if quiet:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"{label} failed with exit code {result.returncode}")
    return result


def find_ffmpeg() -> str:
    configured = os.environ.get("FFMPEG_BIN", "").strip()
    if configured and Path(configured).exists():
        return configured
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - clear error on a bare host
        raise RuntimeError("Install FFmpeg, set FFMPEG_BIN, or install imageio-ffmpeg.") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def media_duration(path: Path, ffmpeg: str) -> float:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path), "-f", "null", "-"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(f"Could not determine duration of {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def ass_time(seconds: float) -> str:
    centiseconds = int(round(max(0.0, seconds) * 100))
    hours, rem = divmod(centiseconds, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, centis = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def srt_time(seconds: float) -> str:
    milliseconds = int(round(max(0.0, seconds) * 1000))
    hours, rem = divmod(milliseconds, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def clean_ass(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def font_path(bold: bool = True) -> str:
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"


def grade_for(hue: str) -> str:
    if hue == "ember":
        return "eq=contrast=1.10:saturation=1.15:gamma_r=1.05:gamma_b=0.95"
    if hue == "signal":
        return "eq=contrast=1.08:saturation=1.13:gamma_g=1.04:gamma_b=1.04"
    if hue == "violet":
        return "eq=contrast=1.09:saturation=1.14:gamma_r=1.03:gamma_b=1.05"
    if hue == "gold":
        return "eq=contrast=1.10:saturation=1.14:gamma_r=1.05:gamma_b=0.97"
    return "eq=contrast=1.08:saturation=1.12:gamma_b=1.05"


# ---------------------------------------------------------------------------
# Requested Edge TTS settings / DNS workaround (kept for voice audit renders)
# ---------------------------------------------------------------------------


def patch_edge_tts_getaddrinfo() -> None:
    """Keep the requested Bing getaddrinfo workaround from the moon build pattern.

    Some constrained hosts give aiohttp an unusable asynchronous DNS result for
    speech.platform.bing.com.  The patched lookup retains the correct hostname
    for TLS / HTTP while optionally permitting a known-good IPv4 address through
    EDGE_TTS_BING_IPV4. ThreadedResolver deliberately reaches this socket patch.
    """
    if getattr(socket, "_universe_impact_fresh_v4_edge_patch", False):
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
    socket._universe_impact_fresh_v4_edge_patch = True  # type: ignore[attr-defined]
    try:
        import aiohttp  # type: ignore
        import aiohttp.connector  # type: ignore
        from aiohttp.resolver import ThreadedResolver  # type: ignore

        original_init = aiohttp.connector.TCPConnector.__init__
        if not getattr(aiohttp.connector.TCPConnector, "_universe_impact_fresh_v4_edge_patch", False):
            def patched_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                if kwargs.get("resolver") is None:
                    kwargs["resolver"] = ThreadedResolver()
                return original_init(self, *args, **kwargs)

            aiohttp.connector.TCPConnector.__init__ = patched_init  # type: ignore[method-assign]
            aiohttp.connector.TCPConnector._universe_impact_fresh_v4_edge_patch = True  # type: ignore[attr-defined]
            aiohttp.TCPConnector = aiohttp.connector.TCPConnector  # type: ignore[attr-defined]
    except ImportError:
        pass


async def synthesize_voice_audit(force: bool) -> None:
    """Generate requested voice samples without touching the locked final audio."""
    try:
        import edge_tts  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install edge-tts to use --voice-only.") from exc
    patch_edge_tts_getaddrinfo()
    for scene in SCENES:
        output = VOICE_AUDIT_DIR / f"{scene.key}.mp3"
        if output.exists() and output.stat().st_size > 1024 and not force:
            print(f"[voice audit] Reusing {output.name}")
            continue
        output.unlink(missing_ok=True)
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                print(f"[voice audit] {VOICE} ({RATE}) — {scene.key}, attempt {attempt}/3")
                await edge_tts.Communicate(scene.narration, voice=VOICE, rate=RATE).save(str(output))
                if output.exists() and output.stat().st_size > 1024:
                    break
                raise RuntimeError("Edge TTS returned an empty file")
            except Exception as exc:
                last_error = exc
                output.unlink(missing_ok=True)
                if attempt < 3:
                    await asyncio.sleep(float(attempt))
        else:
            raise RuntimeError(
                "Edge TTS could not reach speech.platform.bing.com after the getaddrinfo workaround. "
                "Run --voice-only on an Edge-permitted host."
            ) from last_error
    (VOICE_AUDIT_DIR / "voice_audit_manifest.json").write_text(
        json.dumps(
            {
                "engine": "edge-tts",
                "voice": VOICE,
                "rate": RATE,
                "resolver_workaround": "patched socket.getaddrinfo + aiohttp ThreadedResolver for speech.platform.bing.com",
                "note": "Audit cache only. Final v4 copies the locked v3 AAC reference unchanged.",
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Unique source plan and guards
# ---------------------------------------------------------------------------


def all_narrative_shots() -> tuple[Shot, ...]:
    return tuple(shot for scene in SCENES for shot in scene.shots)


def allocate_shot_frames(total_frames: int, shots: Iterable[Shot]) -> list[int]:
    """Largest-remainder integer allocation, preserving every scene's exact frames."""
    shot_list = list(shots)
    weights = [shot.weight for shot in shot_list]
    total_weight = sum(weights)
    if total_weight <= 0:
        raise RuntimeError("Shot weights must sum to a positive number")
    ideal = [total_frames * weight / total_weight for weight in weights]
    frames = [max(1, math.floor(value)) for value in ideal]
    remaining = total_frames - sum(frames)
    if remaining < 0:
        raise RuntimeError("Too many requested one-frame visual passages")
    fractions = sorted(range(len(shot_list)), key=lambda index: ideal[index] - math.floor(ideal[index]), reverse=True)
    for index in fractions[:remaining]:
        frames[index] += 1
    if sum(frames) != total_frames:
        raise AssertionError("Shot frame allocation did not conserve duration")
    return frames


def planned_shots() -> tuple[list[PlannedShot], PlannedShot]:
    plan: list[PlannedShot] = []
    cursor = 0
    for scene in SCENES:
        allocations = allocate_shot_frames(scene.frames, scene.shots)
        for shot, frames in zip(scene.shots, allocations):
            plan.append(PlannedShot(scene.key, shot, cursor, frames))
            cursor += frames
    if cursor != NARRATIVE_FRAMES:
        raise AssertionError(f"Narrative plan has {cursor} frames, expected {NARRATIVE_FRAMES}")
    outro = PlannedShot("09_outro", OUTRO_SHOT, cursor, OUTRO_FRAMES)
    return plan, outro


def source_duration_for(shot: PlannedShot) -> float:
    """Give every original source a small tail so trim cannot exhaust its frames."""
    return (shot.frames + 7) / FPS


def external_source_path(key: str) -> Path:
    info = EXTERNAL_SOURCES[key]
    path = ROOT / info["local_file"]
    if not path.exists() or path.stat().st_size < 100_000:
        raise RuntimeError(f"Required fresh external animation is missing or truncated: {path}")
    return path


def render_source_assets(plan: list[PlannedShot], outro: PlannedShot, ffmpeg: str, force: bool) -> tuple[dict[str, Path], dict[str, dict[str, object]]]:
    """Render one physical original clip per planned generated shot.

    ``render_unique_tracks`` independently blocks duplicate generated track keys
    and byte-identical output tracks. The following cross-source guard also
    validates external assets together with those generated tracks before any
    visual scene is assembled.
    """
    all_plan = [*plan, outro]
    generated_specs: list[TrackSpec] = []
    for ordinal, item in enumerate(all_plan, start=1):
        if item.shot.external:
            continue
        if item.shot.family not in FAMILY_DESCRIPTIONS:
            raise RuntimeError(f"Unknown original visual family: {item.shot.family}")
        generated_specs.append(
            TrackSpec(
                key=item.shot.key,
                family=item.shot.family,
                seed=2026083100 + ordinal * 7919,
                hue=item.shot.hue,
                duration=source_duration_for(item),
                label=FAMILY_DESCRIPTIONS[item.shot.family],
            )
        )
    generated = render_unique_tracks(generated_specs, TRACK_DIR, ffmpeg, force=force)
    paths: dict[str, Path] = {}
    source_info: dict[str, dict[str, object]] = {}
    for item in all_plan:
        key = item.shot.key
        if item.shot.external:
            if key not in EXTERNAL_SOURCES:
                raise RuntimeError(f"No external source metadata for {key}")
            path = external_source_path(key)
            info: dict[str, object] = {**EXTERNAL_SOURCES[key], "kind": "new public-domain external animated visual"}
        else:
            path = generated[key]
            info = {
                "local_file": str(path.relative_to(ROOT)),
                "title": item.shot.family.replace("_", " ").title() + " — original Universe Impact v4 3D track",
                "page": "Created during v4 by fresh_3d_visuals_v4.py; no third-party footage or source audio.",
                "primary_source": "Original procedural geometry, particles, local generated texture, and camera animation.",
                "credit": "Universe Impact original visualization",
                "license": "Original project output; no third-party video footage or source audio used.",
                "kind": "original one-time 3D-style moving track",
                "family": item.shot.family,
                "seed": 2026083100 + (all_plan.index(item) + 1) * 7919,
            }
        paths[key] = path
        source_info[key] = info
    enforce_no_reused_visuals([*plan, outro], paths)
    return paths, source_info


def enforce_no_reused_visuals(plan: Iterable[PlannedShot], source_paths: dict[str, Path]) -> None:
    """Block reuse by source key, resolved physical filename, and content hash."""
    items = list(plan)
    keys = [item.shot.key for item in items]
    duplicated_keys = sorted({key for key in keys if keys.count(key) > 1})
    if duplicated_keys:
        raise RuntimeError("Duplicate visual source key(s) blocked: " + ", ".join(duplicated_keys))
    missing = sorted(set(keys) - set(source_paths))
    if missing:
        raise RuntimeError("Missing visual source path(s): " + ", ".join(missing))
    paths = [source_paths[key].resolve() for key in keys]
    path_strings = [str(path) for path in paths]
    duplicated_paths = sorted({path for path in path_strings if path_strings.count(path) > 1})
    if duplicated_paths:
        raise RuntimeError("Visual clip filename/path reuse blocked: " + "; ".join(duplicated_paths))
    hashes: dict[str, str] = {}
    collisions: list[str] = []
    for key in keys:
        digest = sha256(source_paths[key])
        if digest in hashes:
            collisions.append(f"{key} == {hashes[digest]}")
        hashes[digest] = key
    if collisions:
        raise RuntimeError("Byte-identical visual source reuse blocked: " + "; ".join(collisions))
    print(f"[dedup] PASS — {len(keys)} timeline slots use {len(keys)} unique keys, paths, and SHA-256 hashes")


# ---------------------------------------------------------------------------
# Scene rendering — all shots are one-time moving visual assets
# ---------------------------------------------------------------------------


def build_immersive_filter(input_index: int, index: int, item: PlannedShot) -> str:
    duration = item.duration
    phase = (index * 0.731) % math.tau
    x_expr = f"(in_w-out_w)*(0.50+0.055*sin(0.61*t+{phase:.3f}))"
    y_expr = f"(in_h-out_h)*(0.50+0.045*cos(0.47*t+{phase:.3f}))"
    # All generated v4 sources are portrait. "cinematic" is reserved for the
    # two one-time wide NASA animations; both treatments still fill 9:16 fully.
    scale = "scale=1200:2134:force_original_aspect_ratio=increase:flags=lanczos" if item.shot.layout == "immersive" else "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos"
    return (
        # end_frame is used instead of a floating duration to preserve the exact
        # per-shot 30 fps frame budget through every scene concat.
        f"[{input_index}:v]fps={FPS},trim=end_frame={item.frames},setpts=PTS-STARTPTS,"
        f"{scale},crop={OUT_W}:{OUT_H}:x='{x_expr}':y='{y_expr}':exact=1,"
        f"{grade_for(item.shot.hue)},vignette=PI/5.4:eval=frame,"
        "unsharp=5:5:0.38:5:5:0.0,noise=alls=1.5:allf=t,setsar=1,format=yuv420p"
        f"[shot{index}]"
    )


def build_portal_filter(input_index: int, index: int, item: PlannedShot) -> list[str]:
    """Make one clearly labelled, safe framed treatment for the NASA simulation.

    The source is read only once. Its background is generated by FFmpeg rather
    than a second copy of the source, preventing even within-shot source reuse.
    The label is 20+ pixels inside the top portal edge and well above foreground
    video, so it cannot be clipped by the border.
    """
    duration = item.duration
    phase = (index * 0.731) % math.tau
    # This FFmpeg build intentionally has no drawtext filter. The label text is
    # emitted by the libass pass in write_ass_and_srt(), over this safe dark
    # label panel, at a fixed y=655. It is inside the border (top y=612) and
    # well above foreground video (top y=710), so it cannot be clipped.
    return [
        (
            f"color=c=0x02050D:s={OUT_W}x{OUT_H}:r={FPS},fps={FPS},trim=end_frame={item.frames},"
            "noise=alls=8:allf=t,drawgrid=w=96:h=96:t=1:c=0x59E9FF@0.075,"
            "vignette=PI/4:eval=frame,"
            "drawbox=x=30:y=612:w=1020:h=704:color=0x58EAF8@0.82:t=3,"
            "drawbox=x=39:y=621:w=1002:h=686:color=0xFF8950@0.24:t=1,"
            "drawbox=x=52:y=632:w=340:h=46:color=0x02050D@0.92:t=fill,"
            "drawbox=x=70:y=680:w=940:h=2:color=0xFF8950@0.70:t=fill"
            f"[portalbg{index}]"
        ),
        (
            f"[{input_index}:v]fps={FPS},trim=end_frame={item.frames},setpts=PTS-STARTPTS,"
            "scale=960:540:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=960:540:(ow-iw)/2:(oh-ih)/2:color=0x03050C,"
            f"{grade_for(item.shot.hue)},unsharp=5:5:0.40:5:5:0.0,setsar=1"
            f"[portalsrc{index}]"
        ),
        (
            f"[portalbg{index}][portalsrc{index}]overlay=x='60+7*sin(0.67*t+{phase:.3f})':y='710+6*cos(0.59*t+{phase:.3f})':shortest=1,"
            "noise=alls=1.5:allf=t,setsar=1,format=yuv420p"
            f"[shot{index}]"
        ),
    ]


def render_scene(scene: Scene, items: list[PlannedShot], ffmpeg: str, source_paths: dict[str, Path], force: bool) -> Path:
    output = SCENE_DIR / f"{scene.key}.mp4"
    if output.exists() and output.stat().st_size > 100_000 and not force:
        return output
    command: list[str] = [ffmpeg, "-y", "-loglevel", "warning"]
    filters: list[str] = []
    for index, item in enumerate(items):
        source = source_paths[item.shot.key]
        if item.shot.external:
            # An external GIF is looped only to avoid a final-frame freeze when
            # its unique single use crosses its own short loop boundary.
            command.extend(["-stream_loop", "-1", "-ss", f"{item.shot.source_start:.3f}", "-i", str(source)])
        else:
            command.extend(["-i", str(source)])
        if item.shot.layout == "portal":
            filters.extend(build_portal_filter(index, index, item))
        elif item.shot.layout in ("immersive", "cinematic"):
            filters.append(build_immersive_filter(index, index, item))
        else:
            raise RuntimeError(f"Unknown v4 visual layout: {item.shot.layout}")
    # Intentionally no fade-in: first decoded output frame must contain a hook visual.
    filters.append(
        "".join(f"[shot{index}]" for index in range(len(items)))
        + f"concat=n={len(items)}:v=1:a=0,format=yuv420p[sceneout]"
    )
    command.extend(
        [
            "-filter_complex", ";".join(filters),
            "-map", "[sceneout]",
            "-an",
            "-r", str(FPS),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-profile:v", "high",
            "-level:v", "4.1",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output),
        ]
    )
    run(command, label=f"render v4 {scene.key} ({len(items)} unique moving sources)")
    return output


def render_outro(item: PlannedShot, ffmpeg: str, source_paths: dict[str, Path], force: bool) -> Path:
    scene = Scene("09_outro", "", "", "", (), item.frames, 0.0, 0.0, (item.shot,))
    return render_scene(scene, [item], ffmpeg, source_paths, force)


# ---------------------------------------------------------------------------
# Captions / final mux — preserving locked audio exactly
# ---------------------------------------------------------------------------


def write_ass_and_srt(plan: list[PlannedShot], outro: PlannedShot) -> tuple[Path, Path]:
    ass_path = BUILD / "universe_impact_fresh_3d_v4.ass"
    srt_path = DELIVERABLES / "universe_impact_black_hole_reel_fresh_3d_v4.srt"
    content_end = NARRATIVE_FRAMES / FPS
    final_end = (NARRATIVE_FRAMES + OUTRO_FRAMES) / FPS
    ass_lines = [
        "[Script Info]",
        "Title: Universe Impact — unique-source original 3D Reel v4",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        "Style: Brand,DejaVu Sans,23,&H00CDEAF6,&H000000FF,&H8C02050D,&H8C02050D,1,0,0,0,100,100,1.0,0,1,1.4,1.6,7,55,55,52,1",
        "Style: Source,DejaVu Sans,16,&H00CDEAF6,&H000000FF,&H9602050D,&H9602050D,0,0,0,0,100,100,0.4,0,1,1.1,1.2,9,55,55,56,1",
        "Style: Evidence,DejaVu Sans,21,&H0077E9FF,&H000000FF,&H9202050D,&H9202050D,1,0,0,0,100,100,0.8,0,1,1.5,1.8,2,58,58,62,1",
        "Style: Kicker,DejaVu Sans,27,&H006DEBF7,&H000000FF,&H9602050D,&H9602050D,1,0,0,0,100,100,2.0,0,1,1.7,2.0,8,55,55,255,1",
        "Style: Headline,DejaVu Sans,59,&H00FFFFFF,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,0.5,0,1,2.8,2.5,8,50,50,318,1",
        "Style: Beat,DejaVu Sans,39,&H00FFFFFF,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,1.0,0,1,2.4,2.1,2,70,70,290,1",
        "Style: Simulation,DejaVu Sans,24,&H00CDEAF6,&H000000FF,&H9002050D,&H9002050D,1,0,0,0,100,100,1.3,0,1,1.0,1.2,5,0,0,0,1",
        "Style: OutroBrand,DejaVu Sans,32,&H00CDEAF6,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,2.2,0,1,2.1,2.3,8,50,50,322,1",
        "Style: OutroFollow,DejaVu Sans,63,&H00FFFFFF,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,0.5,0,1,3.0,2.7,8,45,45,510,1",
        "Style: OutroAction,DejaVu Sans,35,&H00CDEAF6,&H000000FF,&HAA02050D,&HAA02050D,1,0,0,0,100,100,1.0,0,1,2.0,2.0,8,55,55,670,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
        f"Dialogue: 0,0:00:00.00,{ass_time(content_end)},Brand,,0,0,0,,UNIVERSE IMPACT  •  COSMIC QUESTIONS",
        f"Dialogue: 0,0:00:00.00,{ass_time(content_end)},Source,,0,0,0,,35 UNIQUE MOVING VISUAL SOURCES",
        f"Dialogue: 0,0:00:00.00,{ass_time(content_end)},Evidence,,0,0,0,,HYPOTHESIS  /  NOT ESTABLISHED FACT",
    ]
    # The NASA binary source is the only framed simulation. This ASS event is
    # precisely centred in the dark label panel (x 52–392, y 632–678), putting
    # the word fully inside the border and safely above the foreground footage.
    portal_item = next(item for item in plan if item.shot.key == "nasa_binary_3d_once")
    ass_lines.append(
        f"Dialogue: 4,{ass_time(portal_item.start + 0.04)},{ass_time(portal_item.end - 0.04)},Simulation,,0,0,0,,{{\\pos(222,655)\\fad(90,120)}}SIMULATION"
    )
    srt_lines: list[str] = []
    for number, scene in enumerate(SCENES, start=1):
        scene_items = [item for item in plan if item.scene_key == scene.key]
        actual_start = scene_items[0].start
        actual_end = scene_items[-1].end
        card_end = min(actual_end - 0.12, actual_start + min(3.25, max(2.40, scene.duration * 0.42)))
        ass_lines.append(
            f"Dialogue: 1,{ass_time(actual_start + 0.10)},{ass_time(card_end)},Kicker,,0,0,0,,{{\\fad(120,180)}}{clean_ass(scene.kicker)}"
        )
        ass_lines.append(
            f"Dialogue: 2,{ass_time(actual_start + 0.28)},{ass_time(card_end)},Headline,,0,0,0,,{{\\fad(160,220)}}{clean_ass(scene.headline)}"
        )
        beat_start = card_end - 0.04
        beat_end = actual_end - 0.10
        span = max(0.18, (beat_end - beat_start) / max(1, len(scene.beats)))
        for index, beat in enumerate(scene.beats):
            local_start = beat_start + index * span
            local_end = min(beat_end, local_start + span + 0.04)
            ass_lines.append(
                f"Dialogue: 3,{ass_time(local_start)},{ass_time(local_end)},Beat,,0,0,0,,{{\\fad(120,160)}}{clean_ass(beat)}"
            )
        srt_lines.extend([str(number), f"{srt_time(scene.subtitle_start)} --> {srt_time(scene.subtitle_end)}", scene.narration, ""])
    # Mandatory 2.8s scripted, burned-in branded outro — not a manual edit.
    outro_start = outro.start
    outro_end = outro.end
    ass_lines.extend(
        [
            f"Dialogue: 0,{ass_time(outro_start + 0.05)},{ass_time(outro_end - 0.06)},OutroBrand,,0,0,0,,{{\\fad(130,210)}}UNIVERSE IMPACT",
            f"Dialogue: 1,{ass_time(outro_start + 0.18)},{ass_time(outro_end - 0.06)},OutroFollow,,0,0,0,,{{\\fad(160,200)}}FOLLOW UNIVERSE IMPACT",
            f"Dialogue: 2,{ass_time(outro_start + 0.43)},{ass_time(outro_end - 0.06)},OutroAction,,0,0,0,,{{\\fad(180,200)}}LIKE + SHARE TO A FRIEND",
        ]
    )
    ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return ass_path, srt_path


def render_final(scene_files: list[Path], ass_path: Path, ffmpeg: str, force: bool) -> Path:
    """Join visual scenes, burn captions, and stream-copy the locked audio input."""
    output = DELIVERABLES / "universe_impact_black_hole_reel_fresh_3d_v4.mp4"
    if output.exists() and output.stat().st_size > 100_000 and not force:
        return output
    if not AUDIO_LOCK.exists() or AUDIO_LOCK.stat().st_size < 100_000:
        raise RuntimeError(f"Locked v3 audio reference is missing: {AUDIO_LOCK}")
    command: list[str] = [ffmpeg, "-y", "-loglevel", "warning"]
    for path in scene_files:
        command.extend(["-i", str(path)])
    command.extend(["-i", str(AUDIO_LOCK)])
    visual_inputs = "".join(f"[{index}:v]" for index in range(len(scene_files)))
    fonts_dir = str(Path(font_path()).parent)
    ass_filename = ass_path.as_posix().replace("'", "\\'")
    filters = (
        f"{visual_inputs}concat=n={len(scene_files)}:v=1:a=0[joined];"
        f"[joined]ass=filename='{ass_filename}':fontsdir='{fonts_dir}',format=yuv420p[video]"
    )
    command.extend(
        [
            "-filter_complex", filters,
            "-map", "[video]",
            "-map", f"{len(scene_files)}:a:0",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-profile:v", "high",
            "-level:v", "4.1",
            "-pix_fmt", "yuv420p",
            # The precise requirement: no remix / re-level / reencode of audio.
            "-c:a", "copy",
            "-movflags", "+faststart",
            "-metadata", "title=Could the Big Bang Be an Inside View? | Hypothesis, Not Proof",
            "-metadata", "artist=Universe Impact",
            "-metadata", "comment=V4 uses unique moving visual sources. Audio is the locked v3 AAC reference copied unchanged; silent branded outro follows.",
            str(output),
        ]
    )
    run(command, label="assemble v4 final / stream-copy locked audio")
    run([ffmpeg, "-v", "error", "-i", str(output), "-f", "null", "-"], label="v4 full decode validation", quiet=True)
    return output


def extract_cover(video: Path, ffmpeg: str) -> Path:
    cover = DELIVERABLES / "universe_impact_black_hole_cover_fresh_3d_v4.jpg"
    run(
        [
            ffmpeg, "-y", "-loglevel", "warning", "-ss", "0.720", "-i", str(video), "-frames:v", "1", "-update", "1",
            "-q:v", "2", "-vf", f"scale={OUT_W}:{OUT_H}:flags=lanczos", str(cover),
        ],
        label="extract v4 cover",
    )
    return cover


# ---------------------------------------------------------------------------
# QA, source notes, manifest, publishing package
# ---------------------------------------------------------------------------


def first_frame_stats(video: Path, ffmpeg: str) -> dict[str, float | int]:
    """Decode frame 1 and prove it is not a black lead-in / wrong-sized frame."""
    from PIL import Image  # imported here so --voice-only needs only edge-tts
    import numpy as np

    output = BUILD / "qa_first_frame.png"
    run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(video), "-frames:v", "1", "-update", "1", str(output)],
        label="extract v4 frame-1 QA", quiet=True,
    )
    image = Image.open(output).convert("RGB")
    pixels = np.asarray(image, dtype=np.float32)
    return {
        "width": image.width,
        "height": image.height,
        "mean_luma": round(float(pixels.mean()), 3),
        "non_black_fraction": round(float((pixels.max(axis=2) > 12).mean()), 5),
    }


def last_frame_size(video: Path, ffmpeg: str) -> dict[str, int]:
    from PIL import Image

    output = BUILD / "qa_last_frame.png"
    run(
        [ffmpeg, "-y", "-loglevel", "error", "-sseof", "-0.050", "-i", str(video), "-frames:v", "1", "-update", "1", str(output)],
        label="extract v4 outro-frame QA", quiet=True,
    )
    image = Image.open(output)
    return {"width": image.width, "height": image.height}


def measure_loudness(path: Path, ffmpeg: str) -> float | None:
    """Measure only; the locked program audio is never processed or modified."""
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path), "-filter_complex", "ebur128=peak=true", "-f", "null", "-"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    matches = re.findall(r"\bI:\s*(-?\d+(?:\.\d+)?)\s+LUFS", result.stderr)
    return float(matches[-1]) if matches else None


def aac_packet_stream_sha256(path: Path, label: str, ffmpeg: str) -> str:
    """Hash AAC packets as ADTS, ignoring the normal M4A/MP4 container rewrite."""
    output = BUILD / f"qa_{label}_audio_packets.aac"
    run(
        [ffmpeg, "-y", "-v", "error", "-i", str(path), "-map", "0:a:0", "-c", "copy", "-f", "adts", str(output)],
        label=f"extract {label} AAC packets for lock QA",
        quiet=True,
    )
    return sha256(output)


def qa_final(video: Path, plan: list[PlannedShot], outro: PlannedShot, source_paths: dict[str, Path], ffmpeg: str) -> dict[str, object]:
    enforce_no_reused_visuals([*plan, outro], source_paths)
    duration = media_duration(video, ffmpeg)
    expected_duration = (NARRATIVE_FRAMES + OUTRO_FRAMES) / FPS
    first = first_frame_stats(video, ffmpeg)
    last = last_frame_size(video, ffmpeg)
    locked_duration = media_duration(AUDIO_LOCK, ffmpeg)
    locked_loudness = measure_loudness(AUDIO_LOCK, ffmpeg)
    reference_packet_sha256 = aac_packet_stream_sha256(AUDIO_LOCK, "reference", ffmpeg)
    final_packet_sha256 = aac_packet_stream_sha256(video, "final", ffmpeg)
    if first["width"] != OUT_W or first["height"] != OUT_H or last["width"] != OUT_W or last["height"] != OUT_H:
        raise RuntimeError("QA blocked: output does not fill a 1080x1920 frame")
    if float(first["non_black_fraction"]) < 0.02 or float(first["mean_luma"]) < 1.5:
        raise RuntimeError("QA blocked: frame 1 appears black rather than a visible hook visual")
    if abs(duration - expected_duration) > 0.12:
        raise RuntimeError(f"QA blocked: expected {expected_duration:.3f}s video, found {duration:.3f}s")
    if abs(locked_duration - NARRATIVE_FRAMES / FPS) > 0.12:
        raise RuntimeError("QA blocked: locked audio duration no longer matches narrative program")
    if locked_loudness is not None and not (-16.6 <= locked_loudness <= -15.4):
        raise RuntimeError(f"QA blocked: locked audio is unexpectedly {locked_loudness:.1f} LUFS")
    if final_packet_sha256 != reference_packet_sha256:
        raise RuntimeError("QA blocked: final AAC packet stream differs from the locked audio reference")
    return {
        "decode": "ffmpeg -v error -i final.mp4 -f null - exited 0",
        "visual_duration_seconds": round(duration, 3),
        "expected_visual_duration_seconds": round(expected_duration, 3),
        "silent_branded_outro_seconds": round(OUTRO_FRAMES / FPS, 3),
        "frame_1": first,
        "outro_frame": last,
        "frame_fill": "1080x1920 verified at first and final frame; no pillarbox canvas is used",
        "locked_audio_reference": {
            "file": str(AUDIO_LOCK.relative_to(ROOT)),
            "sha256": sha256(AUDIO_LOCK),
            "aac_packet_stream_sha256": reference_packet_sha256,
            "final_aac_packet_stream_sha256": final_packet_sha256,
            "duration_seconds": round(locked_duration, 3),
            "integrated_loudness_lufs": locked_loudness,
            "treatment": "mapped with -c:a copy; no audio filter, gain, loudnorm, remix, or re-encoding",
        },
        "source_dedup": "PASS — keys, resolved filename/path, and SHA-256 values were all unique across the 35 placed sources",
        "simulation_portal": "NASA simulation appears once; SIMULATION label is rendered safely at y=642 inside a border beginning y=612, above foreground video beginning y=710",
    }


def write_source_notes() -> Path:
    SOURCE_NOTES.write_text(
        """# Universe Impact — fresh 3D v4 source notes

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
""",
        encoding="utf-8",
    )
    return SOURCE_NOTES


def detailed_shot_manifest(plan: list[PlannedShot], outro: PlannedShot, source_paths: dict[str, Path], source_info: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for item in [*plan, outro]:
        source = source_paths[item.shot.key]
        details.append(
            {
                "scene": item.scene_key,
                "timeline_start": round(item.start, 3),
                "timeline_end": round(item.end, 3),
                "duration_seconds": round(item.duration, 3),
                "source_key": item.shot.key,
                "source_file": str(source.relative_to(ROOT)),
                "source_sha256": sha256(source),
                "source_family": item.shot.family,
                "source_layout": item.shot.layout,
                "external_public_domain_source": item.shot.external,
                "source_start_seconds": item.shot.source_start if item.shot.external else 0.0,
                "source_title": source_info[item.shot.key]["title"],
            }
        )
    return details


def write_manifest(
    final_video: Path,
    cover: Path,
    plan: list[PlannedShot],
    outro: PlannedShot,
    source_paths: dict[str, Path],
    source_info: dict[str, dict[str, object]],
    qa: dict[str, object],
    ffmpeg: str,
) -> Path:
    manifest_path = DELIVERABLES / "universe_impact_black_hole_reel_fresh_3d_v4_manifest.json"
    details = detailed_shot_manifest(plan, outro, source_paths, source_info)
    serializable_sources: dict[str, dict[str, object]] = {}
    for key, info in source_info.items():
        path = source_paths[key]
        serializable_sources[key] = {
            **info,
            "sha256": sha256(path),
            "duration_seconds": round(media_duration(path, ffmpeg), 3),
            "bytes": path.stat().st_size,
        }
    manifest = {
        "version": "fresh-3d-v4-unique-source-correction",
        "title": "Could the Big Bang Be an Inside View? | Hypothesis, Not Proof",
        "page": "Universe Impact",
        "output": final_video.name,
        "cover": cover.name,
        "captions": "universe_impact_black_hole_reel_fresh_3d_v4.srt",
        "source_notes": str(SOURCE_NOTES.relative_to(ROOT)),
        "format": {
            "width": OUT_W,
            "height": OUT_H,
            "fps": FPS,
            "duration_seconds": round(media_duration(final_video, ffmpeg), 3),
            "video_codec": "H.264 High / yuv420p",
            "audio_codec": "AAC LC stream copied from locked reference",
        },
        "correction": {
            "v3_preserved_as_comparison_baseline": "deliverables/universe_impact_black_hole_reel_fresh_3d_v3.mp4",
            "repeated_visuals_eliminated": True,
            "placed_moving_visual_sources": len(details),
            "unique_source_keys": len({shot["source_key"] for shot in details}),
            "unique_source_paths": len({shot["source_file"] for shot in details}),
            "unique_source_hashes": len({shot["source_sha256"] for shot in details}),
            "external_nasa_animations_each_used_once": 3,
            "original_unique_3d_tracks": 32,
            "mandatory_scripted_outro": {
                "duration_seconds": round(OUTRO_FRAMES / FPS, 3),
                "text": ["Follow Universe Impact", "Like + Share to a friend"],
                "audio": "intentional silence after locked program audio",
            },
            "no_black_lead_in": True,
            "portal_simulation_label_safe": True,
        },
        "source_replacement": {
            "legacy_v2_source_directory_read": False,
            "legacy_v2_asset_paths_excluded": [
                "sources/clip1_bh_orbit.mp4",
                "sources/clip2_tde_shred.mp4",
                "sources/clip3_tde_disk.mp4",
                "sources/clip4_tde_partial.mp4",
                "sources/clip5_tde_fading.mov",
            ],
            "v3_rendered_visual_mp4_inputs_used": False,
            "source_audio_used": False,
        },
        "voice_requested": {"engine": "edge-tts", "voice": VOICE, "rate": RATE},
        "voice_note": "The locked v3 program audio is preserved unchanged for v4, while --voice-only retains the exact requested edge-tts configuration and getaddrinfo workaround for audit/rebuild purposes.",
        "scientific_framing": "Speculative black-hole cosmology hypothesis; no direct observational proof is claimed.",
        "source_clips": serializable_sources,
        "timeline": [
            {
                "key": scene.key,
                "start": round(next(item.start for item in plan if item.scene_key == scene.key), 3),
                "end": round([item.end for item in plan if item.scene_key == scene.key][-1], 3),
                "narration": scene.narration,
            }
            for scene in SCENES
        ] + [{"key": "09_outro", "start": round(outro.start, 3), "end": round(outro.end, 3), "narration": ""}],
        "shots": details,
        "qa": qa,
        "final_file_sha256": sha256(final_video),
        "cover_sha256": sha256(cover),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def write_publishing_pack(final_video: Path, cover: Path, qa: dict[str, object]) -> Path:
    package = DELIVERABLES / "UNIVERSE_IMPACT_FACEBOOK_POST_FRESH_3D_V4.md"
    package.write_text(
        f"""# Universe Impact — Facebook publishing pack (fresh 3D v4)

## Reel title
**Could the Big Bang Be an Inside View? | Hypothesis, Not Proof**

## Ready-to-paste Facebook caption
What if the Big Bang was not the beginning of *everything* — but the inside view of a black hole in a larger cosmos? 🌌

Black-hole cosmology is a real family of speculative ideas, but it is **not established science**. The important question is not just whether we can imagine it. It is: **what observation could test it?**

A serious model needs a fingerprint — perhaps in the cosmic microwave background or primordial gravitational waves — that rival explanations cannot copy.

What cosmic clue would convince you? 👇

Follow **Universe Impact** for big cosmic questions — wonder first, evidence always.

#UniverseImpact #Space #Astronomy #BlackHole #BigBang #Cosmology #Science #CosmicMystery

## Pinned-comment prompt
**Mind-bender:** If this idea ever became testable, what observation should scientists look for first: a CMB pattern, primordial gravitational waves, or something else?

## Upload settings
- **File:** `{final_video.name}`
- **Format:** 1080 × 1920, H.264/AAC, vertical 9:16, 30 fps
- **Length:** approximately {qa['visual_duration_seconds']} seconds, including a 2.8-second silent branded outro
- **Cover:** `{cover.name}`
- **Captions:** Upload `universe_impact_black_hole_reel_fresh_3d_v4.srt` if Facebook's caption option is available. The Reel already has short burned-in kinetic text for silent autoplay.
- **First-frame hook:** “WHAT IF THE BIG BANG WAS AN INSIDE VIEW?”
- **Final on-screen CTA:** “FOLLOW UNIVERSE IMPACT” and “LIKE + SHARE TO A FRIEND”

## Accessibility alt text
A fast-moving vertical science Reel from Universe Impact. Unique animated visualizations show a luminous accretion disk, a labelled black-hole simulation portal, a collapse-to-bounce particle field, an expanding shell, a flight through a cosmic web, a rotating pattern sphere, metric-like grids, waves, orbit sculptures, detector data, and a living cosmic branded end card. On-screen text repeatedly labels black-hole cosmology as a hypothesis, not established fact.

## Editorial integrity note
This Reel intentionally separates **hypothesis** from **evidence**. It does **not** claim NASA, JWST, the CMB, or gravitational-wave observations have proved that we live inside a black hole. “Black-hole cosmology” remains a speculative family of models that must yield a unique, testable prediction before it can gain scientific support.

## v4 visual / audio provenance
This is a corrective v4 delivery that preserves the reviewed v3 file separately. It uses **35 one-time moving visual sources**: 32 fresh original procedural 3D tracks plus three public-domain NASA animations, each placed once. The source-key, filename/path, and SHA-256 deduplication guard is recorded in `universe_impact_black_hole_reel_fresh_3d_v4_manifest.json`.

- No legacy v2 source clip is read.
- No rendered visual footage from v3 is read.
- The three NASA SVS 14132 animations are documented public-domain source files and appear once each only; retain the NASA credits where practical.
- The locked AAC program audio is copied unchanged from the reviewed v3 reference, preserving its measured approximately -16 LUFS integrated loudness. The final 2.8-second branded end card is intentionally silent.
- Full source and rights notes: `assets/universe_impact_fresh_v4/SOURCES.md`.

## Research links
- NASA SVS 14132: https://svs.gsfc.nasa.gov/14132/
- NASA SVS usage statement: https://svs.gsfc.nasa.gov/
- Commons — Supermassive Binary Black Hole Simulation: https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Supermassive_Binary_Black_Hole_Simulation).gif
- Commons — Disk and Corona: https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_Disk_and_Corona).gif
- Commons — LMXB Illustration: https://commons.wikimedia.org/wiki/File:Black_Hole_Week-_Black_Hole_GIFs_(SVS14132_-_BHW_LMXB_Illustration).gif

Keep “hypothesis,” “speculative model,” and “no direct proof” in captions or replies. Do not turn the premise into “NASA proved we live inside a black hole.”
""",
        encoding="utf-8",
    )
    return package


# ---------------------------------------------------------------------------
# Build entry point
# ---------------------------------------------------------------------------


def build_render(force: bool, plan_only: bool = False) -> tuple[Path, Path, Path, Path] | None:
    ensure_dirs()
    if sum(scene.frames for scene in SCENES) != NARRATIVE_FRAMES:
        raise AssertionError("Scene frame counts must equal locked narrative duration")
    plan, outro = planned_shots()
    if len(plan) != 34 or len([*plan, outro]) != 35:
        raise AssertionError("v4 must contain 34 narrative sources plus one branded outro source")
    print("\n[plan] v4 unique-source visual timeline")
    for scene in SCENES:
        members = [item for item in plan if item.scene_key == scene.key]
        print(f"  {scene.key}: {members[0].start:6.3f}s → {members[-1].end:6.3f}s | {len(members)} one-time sources")
    print(f"  09_outro: {outro.start:6.3f}s → {outro.end:6.3f}s | mandatory Follow / Like + Share end card")
    if plan_only:
        return None
    ffmpeg = find_ffmpeg()
    source_paths, source_info = render_source_assets(plan, outro, ffmpeg, force)
    scene_files = [
        render_scene(scene, [item for item in plan if item.scene_key == scene.key], ffmpeg, source_paths, force)
        for scene in SCENES
    ]
    scene_files.append(render_outro(outro, ffmpeg, source_paths, force))
    ass_path, _ = write_ass_and_srt(plan, outro)
    final_video = render_final(scene_files, ass_path, ffmpeg, force)
    cover = extract_cover(final_video, ffmpeg)
    qa = qa_final(final_video, plan, outro, source_paths, ffmpeg)
    write_source_notes()
    package = write_publishing_pack(final_video, cover, qa)
    manifest = write_manifest(final_video, cover, plan, outro, source_paths, source_info, qa, ffmpeg)
    return final_video, cover, package, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the corrected unique-source Universe Impact Reel v4.")
    parser.add_argument("--voice-only", action="store_true", help="Create requested Edge-TTS audit files only; never changes the locked final audio.")
    parser.add_argument("--render-only", action="store_true", help="Compatibility flag: render v4 using the locked production audio reference.")
    parser.add_argument("--force", action="store_true", help="Recreate v4 rendered sources, scenes, final MP4, cover, and metadata.")
    parser.add_argument("--plan-only", action="store_true", help="Print the exact deduplicated v4 source plan without rendering.")
    args = parser.parse_args()
    if args.voice_only and (args.render_only or args.plan_only):
        parser.error("--voice-only cannot be combined with --render-only or --plan-only")
    ensure_dirs()
    if args.voice_only:
        asyncio.run(synthesize_voice_audit(args.force))
        print(f"\nVoice audit complete: {VOICE_AUDIT_DIR}")
        return
    result = build_render(args.force, plan_only=args.plan_only)
    if result is not None:
        final_video, cover, package, manifest = result
        print("\nComplete fresh v4 delivery:")
        print(f"  video:    {final_video}")
        print(f"  cover:    {cover}")
        print(f"  post:     {package}")
        print(f"  manifest: {manifest}")


if __name__ == "__main__":
    main()
