#!/usr/bin/env python3
"""Build a vertical, Facebook-ready Universe Impact Reel.

Creative premise
----------------
"Are we inside a black hole?" is deliberately presented as a *hypothesis*,
not as a discovery.  The reel adds a clear science / speculation distinction,
original motion graphics, an evidence-first ending, burned-in headline cards,
an upload-ready SRT, cover art, and a Facebook publishing pack.

Voice setting requested for this project
----------------------------------------
Engine: edge-tts
Voice:  en-US-ChristopherNeural
Rate:   +0%

Usage
-----
Install the small Python dependencies once:
    python3 -m pip install edge-tts Pillow numpy imageio-ffmpeg

Build everything (requires outbound access to Edge TTS):
    python3 build_universe_impact_v1.py

Render from narration files already in build_universe_impact/audio/:
    python3 build_universe_impact_v1.py --render-only

Create/recreate just the Edge narration:
    python3 build_universe_impact_v1.py --voice-only --force

FFMPEG_BIN can be set to an ffmpeg executable.  If it is not set, the script
uses system ffmpeg or imageio-ffmpeg's bundled binary.
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
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
SOURCES = ROOT / "sources"
BUILD = ROOT / "build_universe_impact"
AUDIO_DIR = BUILD / "audio"
DELIVERABLES = ROOT / "deliverables"

VOICE = "en-US-ChristopherNeural"
RATE = "+0%"
FPS = 30
OUT_W, OUT_H = 1080, 1920
WORK_W, WORK_H = 540, 960
FADE_SECONDS = 0.32
SCENE_GAP = 0.42
LAST_SCENE_GAP = 1.35


@dataclass(frozen=True)
class Scene:
    key: str
    narration: str
    headline: str
    kicker: str
    visual: str  # source | image | bounce
    source: str = ""
    trim_start: float = 0.0


# The piece is intentionally concise (about one minute at Christopher's normal
# delivery) and has an evidence-first resolution rather than a clickbait claim.
SCENES: tuple[Scene, ...] = (
    Scene(
        "01_hook",
        "What if the Big Bang was the inside of a black hole?",
        "WHAT IF THE BIG BANG\nWAS INSIDE A BLACK HOLE?",
        "A COSMIC QUESTION",
        "source",
        "clip1_bh_orbit.mp4",
        6.8,
    ),
    Scene(
        "02_hypothesis",
        "Not a fact. Not a discovery. A breathtaking hypothesis called black hole cosmology.",
        "A HYPOTHESIS.\nNOT A DISCOVERY.",
        "BLACK HOLE COSMOLOGY",
        "image",
        "black_hole_bounce.png",
    ),
    Scene(
        "03_bounce",
        "In some models, collapse does not end at a singularity. Some quantum gravity ideas replace it with a bounce, opening a new region of expanding space time.",
        "COLLAPSE  •  BOUNCE\nEXPANDING SPACE",
        "ONE THEORETICAL PATH",
        "bounce",
    ),
    Scene(
        "04_inside",
        "From inside, that bounce could look like a Big Bang: no center, just space expanding everywhere at once.",
        "FROM INSIDE, IT COULD LOOK\nLIKE A BIG BANG",
        "ARTIST'S CONCEPT · NO CENTER",
        "image",
        "black_hole_bounce.png",
    ),
    Scene(
        "05_limit",
        "But this is where honesty matters. Our best theories clash in these extreme conditions, and no observation shows our universe was born this way.",
        "THE MATH BREAKS\nAT THE EXTREME",
        "RELATIVITY × QUANTUM PHYSICS",
        "source",
        "clip3_tde_disk.mp4",
        5.0,
    ),
    Scene(
        "06_fingerprint",
        "To become science, the idea needs a fingerprint: a unique pattern in the cosmic microwave background, or primordial gravitational waves that rival explanations cannot copy.",
        "SCIENCE NEEDS\nA FINGERPRINT",
        "CMB · PRIMORDIAL GRAVITATIONAL WAVES",
        "image",
        "cosmic_fingerprint.png",
    ),
    Scene(
        "07_honesty",
        "Until then, the answer is not yes. It is: we do not know.",
        "NO DIRECT PROOF.\nYET.",
        "STATUS: OPEN QUESTION",
        "source",
        "clip1_bh_orbit.mp4",
        1.4,
    ),
    Scene(
        "08_cta",
        "That is still astonishing. The cosmos may be stranger than our best story. Universe Impact. Follow for wonder, evidence first.",
        "WONDER, THEN EVIDENCE.",
        "UNIVERSE IMPACT · FOLLOW",
        "image",
        "black_hole_bounce.png",
    ),
)


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def ensure_dirs() -> None:
    for path in (ASSETS, BUILD, AUDIO_DIR, DELIVERABLES):
        path.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], *, label: str = "command", quiet: bool = False) -> subprocess.CompletedProcess[str]:
    printable = " ".join(str(part) for part in cmd)
    print(f"\n[{label}] {printable}")
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
    """Find an ffmpeg executable without hard-coding a local machine path."""
    configured = os.environ.get("FFMPEG_BIN")
    if configured and Path(configured).exists():
        return configured
    installed = shutil.which("ffmpeg")
    if installed:
        return installed
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - only relevant on a bare host
        raise RuntimeError(
            "ffmpeg was not found. Install ffmpeg, set FFMPEG_BIN, or install imageio-ffmpeg."
        ) from exc


def media_duration(path: Path, ffmpeg: str) -> float:
    """Read duration using ffmpeg so a separate ffprobe binary is unnecessary."""
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
    # Pillow accepts this fallback on hosts that expose the font through fontconfig.
    return "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"


def pillow_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(font_path(bold), size=size)
    except OSError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Edge TTS, with the requested DNS workaround kept in the build script.
# ---------------------------------------------------------------------------

def patch_edge_tts_getaddrinfo() -> None:
    """Route Edge TTS resolution through socket.getaddrinfo and force IPv4.

    Do not remove this workaround.  In some render environments, the async DNS
    resolver used by aiohttp returns an unusable record for
    speech.platform.bing.com.  The previous moon build worked around that by
    patching getaddrinfo for that host; this version keeps the same behaviour.

    Set EDGE_TTS_BING_IPV4 to a known-good IPv4 address if a locked-down runtime
    needs a particular Microsoft endpoint.  Without it, normal system IPv4 DNS
    is used.  The original hostname stays in the TLS SNI / HTTP Host fields.
    """
    if getattr(socket, "_universe_impact_edge_patch", False):
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
            # Explicit IPv4 prevents aiohttp / the OS from trying a stale IPv6
            # response before the known-working A record.
            requested_family = socket.AF_INET if family in (0, socket.AF_UNSPEC) else family
            return original_getaddrinfo(host, port, requested_family, type, proto, flags)
        return original_getaddrinfo(host, port, family, type, proto, flags)

    socket.getaddrinfo = patched_getaddrinfo  # type: ignore[assignment]
    socket._universe_impact_edge_patch = True  # type: ignore[attr-defined]

    # aiohttp can otherwise select its asynchronous resolver.  ThreadedResolver
    # deliberately calls the patched socket.getaddrinfo above.
    try:
        import aiohttp  # type: ignore
        import aiohttp.connector  # type: ignore
        from aiohttp.resolver import ThreadedResolver  # type: ignore

        original_connector_init = aiohttp.connector.TCPConnector.__init__
        if not getattr(aiohttp.connector.TCPConnector, "_universe_impact_edge_patch", False):
            def patched_connector_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                if kwargs.get("resolver") is None:
                    kwargs["resolver"] = ThreadedResolver()
                return original_connector_init(self, *args, **kwargs)

            aiohttp.connector.TCPConnector.__init__ = patched_connector_init  # type: ignore[method-assign]
            aiohttp.connector.TCPConnector._universe_impact_edge_patch = True  # type: ignore[attr-defined]
            aiohttp.TCPConnector = aiohttp.connector.TCPConnector  # type: ignore[attr-defined]
    except ImportError:
        # edge-tts will give a clear dependency error below if it is unavailable.
        pass


async def synthesize_one(scene: Scene, force: bool) -> None:
    path = AUDIO_DIR / f"{scene.key}.mp3"
    subtitles = AUDIO_DIR / f"{scene.key}.vtt"
    if not force and path.exists() and path.stat().st_size > 1024:
        print(f"[voice] Reusing {path.name}")
        return

    patch_edge_tts_getaddrinfo()
    try:
        import edge_tts  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install edge-tts first: python3 -m pip install edge-tts") from exc

    for stale in (path, subtitles):
        stale.unlink(missing_ok=True)

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            print(f"[voice] {VOICE} ({RATE}) — {scene.key}, attempt {attempt}/3")
            communicate = edge_tts.Communicate(scene.narration, voice=VOICE, rate=RATE)
            await communicate.save(str(path))
            if path.exists() and path.stat().st_size > 1024:
                return
            raise RuntimeError("Edge TTS returned an empty audio file")
        except Exception as exc:  # The service can occasionally reset a valid request.
            last_error = exc
            path.unlink(missing_ok=True)
            subtitles.unlink(missing_ok=True)
            if attempt < 3:
                await asyncio.sleep(float(attempt))

    raise RuntimeError(
        "Edge TTS could not reach speech.platform.bing.com after the IPv4/getaddrinfo workaround. "
        "The build script preserves the requested en-US-ChristopherNeural +0% setting; "
        "run --voice-only from a network-permitted host, then run --render-only."
    ) from last_error


async def synthesize_voice(force: bool) -> None:
    # Sequential requests are intentional: they are friendlier to the free Edge
    # service and preserve natural scene ordering in its generated files.
    for scene in SCENES:
        await synthesize_one(scene, force)

    manifest = {
        "provider": "edge-tts",
        "voice": VOICE,
        "rate": RATE,
        "resolver_workaround": "patched socket.getaddrinfo + aiohttp ThreadedResolver for speech.platform.bing.com",
        "scenes": [{"key": scene.key, "text": scene.narration} for scene in SCENES],
    }
    (BUILD / "voice_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Original visual assets / motion graphics
# ---------------------------------------------------------------------------

def make_fallback_artwork(path: Path, variant: str) -> None:
    """Create a tasteful fallback if the checked-in generated art is absent."""
    width, height = 768, 1344
    yy, xx = np.mgrid[0:height, 0:width]
    cx, cy = width * 0.5, height * 0.42
    radius = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    base = np.zeros((height, width, 3), dtype=np.float32)
    base[:, :, 0] = 3 + 6 * (yy / height)
    base[:, :, 1] = 8 + 8 * (yy / height)
    base[:, :, 2] = 20 + 24 * (yy / height)
    if variant == "bounce":
        ring = np.exp(-((radius - width * 0.25) / (width * 0.022)) ** 2)
        glow = np.exp(-(radius / (width * 0.31)) ** 2)
        base[:, :, 0] += 80 * ring + 58 * glow
        base[:, :, 1] += 180 * ring + 35 * glow
        base[:, :, 2] += 170 * ring + 120 * glow
        base[radius < width * 0.20] *= 0.13
    else:
        wave = np.sin(radius * 0.12) * np.exp(-radius / (width * 0.55))
        base[:, :, 0] += 28 * (wave + 1)
        base[:, :, 1] += 78 * (wave + 1)
        base[:, :, 2] += 82 * (wave + 1)
    image = Image.fromarray(np.uint8(np.clip(base, 0, 255)), "RGB")
    draw = ImageDraw.Draw(image)
    rng = np.random.default_rng(7)
    for x, y, brightness in zip(rng.integers(0, width, 340), rng.integers(0, height, 340), rng.integers(70, 220, 340)):
        draw.ellipse((int(x), int(y), int(x) + 2, int(y) + 2), fill=(brightness, brightness, min(255, brightness + 25)))
    image.save(path)


def ensure_artwork() -> None:
    bounce = ASSETS / "black_hole_bounce.png"
    fingerprint = ASSETS / "cosmic_fingerprint.png"
    if not bounce.exists():
        print("[assets] Generating a fallback black-hole concept image")
        make_fallback_artwork(bounce, "bounce")
    if not fingerprint.exists():
        print("[assets] Generating a fallback cosmic-fingerprint image")
        make_fallback_artwork(fingerprint, "fingerprint")


def add_radial_glow(canvas: np.ndarray, cx: float, cy: float, spread: float, colour: tuple[float, float, float], strength: float) -> None:
    """Add a soft RGB glow directly to a float image array."""
    height, width = canvas.shape[:2]
    y0 = max(0, int(cy - spread * 3.2))
    y1 = min(height, int(cy + spread * 3.2) + 1)
    x0 = max(0, int(cx - spread * 3.2))
    x1 = min(width, int(cx + spread * 3.2) + 1)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    falloff = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * spread * spread))) * strength
    for channel, value in enumerate(colour):
        canvas[y0:y1, x0:x1, channel] += falloff * value


def make_bounce_animation(path: Path, duration: float = 12.0) -> None:
    """Render an original, abstract collapse → bounce → expansion animation."""
    if path.exists() and path.stat().st_size > 100_000:
        return

    ffmpeg = find_ffmpeg()
    frame_count = int(round(duration * FPS))
    rng = np.random.default_rng(20260831)
    star_x = rng.uniform(0, WORK_W, 420)
    star_y = rng.uniform(0, WORK_H, 420)
    star_b = rng.uniform(32, 190, 420)
    particle_angles = rng.uniform(0, math.tau, 220)
    particle_offsets = rng.uniform(0, math.tau, 220)
    particle_lanes = rng.uniform(0.25, 1.0, 220)

    command = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WORK_W}x{WORK_H}", "-r", str(FPS), "-i", "-",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(path),
    ]
    print(f"[motion] Rendering original bounce animation ({duration:.1f}s)")
    proc = subprocess.Popen(command, stdin=subprocess.PIPE)
    if proc.stdin is None:
        raise RuntimeError("Could not open ffmpeg's video input")

    try:
        for frame_index in range(frame_count):
            t = frame_index / FPS
            yy, xx = np.mgrid[0:WORK_H, 0:WORK_W]
            frame = np.zeros((WORK_H, WORK_W, 3), dtype=np.float32)
            frame[:, :, 0] = 2.0 + 5.0 * (yy / WORK_H)
            frame[:, :, 1] = 6.0 + 8.0 * (yy / WORK_H)
            frame[:, :, 2] = 18.0 + 28.0 * (yy / WORK_H)

            # Subtle moving star field.
            shift = 5.0 * math.sin(t * 0.55)
            for sx, sy, sb in zip(star_x, star_y, star_b):
                x = int((sx + shift * (sy / WORK_H - 0.5)) % WORK_W)
                y = int((sy + t * 1.3) % WORK_H)
                frame[y:y + 1, x:x + 1] += (sb * 0.30, sb * 0.45, sb * 0.68)

            cx = WORK_W * 0.5
            cy = WORK_H * 0.40
            # The visual moves through collapse (0-2.7), a bright bounce (2.7-6.6), and expansion.
            collapse = min(1.0, t / 2.7)
            bounce = min(1.0, max(0.0, (t - 2.55) / 3.7))
            ease_bounce = 1.0 - (1.0 - bounce) ** 3
            horizon_radius = 76 + 3 * math.sin(t * 3.5)
            add_radial_glow(frame, cx, cy, horizon_radius * 1.5, (4, 22, 38), 1.4)
            add_radial_glow(frame, cx, cy, 118 + 8 * math.sin(t * 1.4), (5, 10, 22), 1.1)

            # A brief golden flash makes the theoretical "bounce" legible without claiming it is observed.
            if 2.45 <= t <= 3.4:
                flash = math.exp(-((t - 2.8) / 0.25) ** 2)
                add_radial_glow(frame, cx, cy, 92, (185, 125, 60), flash * 1.45)

            if bounce > 0.0:
                universe_radius = 10 + 184 * ease_bounce
                add_radial_glow(frame, cx, cy, max(10, universe_radius * 0.48), (48, 95, 155), 1.8)
                add_radial_glow(frame, cx, cy, max(8, universe_radius * 0.20), (255, 116, 54), 1.15)

            image = Image.fromarray(np.uint8(np.clip(frame, 0, 255)), "RGB").convert("RGBA")
            glow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_layer)

            # Infall / expansion particles trace a readable before-and-after trajectory.
            for angle, offset, lane in zip(particle_angles, particle_offsets, particle_lanes):
                if t < 2.7:
                    radial = 300 * (1.0 - collapse) ** 1.7 + 84 + 30 * lane
                    theta = angle + t * (1.5 + lane * 1.6)
                    alpha = int(70 + 150 * lane)
                    colour = (59, 214, 255, alpha) if lane > 0.57 else (255, 144, 70, alpha)
                else:
                    radial = 92 + 128 * ease_bounce + 18 * math.sin(offset + t * 1.4)
                    theta = angle + (t - 2.7) * (0.28 + lane * 0.38)
                    alpha = int(44 + 160 * lane * (0.45 + 0.55 * (1 - bounce)))
                    colour = (55, 242, 227, alpha) if lane > 0.50 else (255, 179, 73, alpha)
                px = cx + math.cos(theta) * radial
                py = cy + math.sin(theta) * radial * 0.60
                if -4 <= px < WORK_W + 4 and -4 <= py < WORK_H + 4:
                    radius = 1.0 + 1.7 * lane
                    glow_draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=colour)

            # Orbital arcs and later expanding rings create the science-illustration feeling.
            for ring_index in range(4):
                rr = horizon_radius + 12 + ring_index * 10
                colour = (45, 180, 224, 90 - ring_index * 12)
                glow_draw.ellipse((cx - rr, cy - rr * 0.54, cx + rr, cy + rr * 0.54), outline=colour, width=1)
            if bounce > 0.0:
                for ring_index in range(4):
                    rr = (26 + ring_index * 45) * (0.55 + ease_bounce)
                    alpha = int(138 * (1.0 - 0.12 * ring_index) * (1.0 - max(0.0, bounce - 0.82) * 2.6))
                    if alpha > 0:
                        glow_draw.ellipse((cx - rr, cy - rr * 0.61, cx + rr, cy + rr * 0.61), outline=(88, 238, 232, alpha), width=2)

            # Obsidian horizon in front; a growing luminous "new region" appears only after the bounce.
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=1.15))
            image = Image.alpha_composite(image, glow_layer)
            crisp = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(crisp)
            draw.ellipse(
                (cx - horizon_radius, cy - horizon_radius * 0.87, cx + horizon_radius, cy + horizon_radius * 0.87),
                fill=(0, 1, 5, 238),
                outline=(75, 210, 226, 115),
                width=2,
            )
            image = Image.alpha_composite(image, crisp)
            if bounce > 0.0:
                # The new region is intentionally an artist's concept: colourful,
                # expanding filaments appear *inside* the dark horizon rather than
                # a literal white point. This reads better at Reel size and makes
                # the otherwise abstract theoretical bounce memorable.
                universe = Image.new("RGBA", image.size, (0, 0, 0, 0))
                udraw = ImageDraw.Draw(universe)
                inner_r = 10 + 66 * ease_bounce
                udraw.ellipse(
                    (cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r),
                    fill=(11, 9, 32, 242),
                    outline=(101, 234, 239, int(100 + 120 * (1 - bounce))),
                    width=2,
                )
                for arm_index in range(9):
                    arm_angle = arm_index * math.tau / 9 + t * 0.75
                    arm_colour = (64, 242, 228, 205) if arm_index % 2 else (255, 153, 82, 205)
                    points = []
                    for step in range(19):
                        fraction = step / 18
                        radial = inner_r * (0.08 + 0.84 * fraction)
                        theta = arm_angle + fraction * 2.15 + t * 0.36
                        points.append((cx + math.cos(theta) * radial, cy + math.sin(theta) * radial * 0.75))
                    udraw.line(points, fill=arm_colour, width=1)
                    if arm_index % 3 == 0:
                        px, py = points[-1]
                        udraw.ellipse((px - 2, py - 2, px + 2, py + 2), fill=(255, 242, 176, 220))
                for ring_fraction in (0.28, 0.58, 0.88):
                    rr = inner_r * ring_fraction
                    udraw.ellipse(
                        (cx - rr, cy - rr * 0.77, cx + rr, cy + rr * 0.77),
                        outline=(88, 205, 255, int(55 + 70 * (1 - ring_fraction))),
                        width=1,
                    )
                core_r = 3 + 8 * (1 - bounce) + 5 * ease_bounce
                udraw.ellipse((cx - core_r, cy - core_r, cx + core_r, cy + core_r), fill=(255, 234, 171, 230))
                image = Image.alpha_composite(image, universe.filter(ImageFilter.GaussianBlur(radius=3.1)))
                image = Image.alpha_composite(image, universe)
            proc.stdin.write(np.asarray(image.convert("RGB"), dtype=np.uint8).tobytes())
    finally:
        proc.stdin.close()
        return_code = proc.wait()
        if return_code != 0:
            raise RuntimeError(f"Original motion graphic encoding failed ({return_code})")


def scene_audio_path(scene: Scene) -> Path:
    return AUDIO_DIR / f"{scene.key}.mp3"


def get_scene_timeline(ffmpeg: str) -> list[dict[str, float | Scene]]:
    timeline: list[dict[str, float | Scene]] = []
    cursor = 0.0
    for index, scene in enumerate(SCENES):
        audio_path = scene_audio_path(scene)
        if not audio_path.exists() or audio_path.stat().st_size < 1024:
            raise RuntimeError(
                f"Narration missing for {scene.key}. Run without --render-only, or place the requested Edge audio at {audio_path}."
            )
        voice_duration = media_duration(audio_path, ffmpeg)
        gap = LAST_SCENE_GAP if index == len(SCENES) - 1 else SCENE_GAP
        scene_duration = voice_duration + gap
        timeline.append({
            "scene": scene,
            "start": cursor,
            "voice_duration": voice_duration,
            "duration": scene_duration,
            "end": cursor + scene_duration,
        })
        cursor += scene_duration
    return timeline


def render_scene(entry: dict[str, float | Scene], index: int, ffmpeg: str, force: bool) -> Path:
    scene = entry["scene"]
    assert isinstance(scene, Scene)
    duration = float(entry["duration"])
    output = BUILD / "video" / f"{index + 1:02d}_{scene.key}.mp4"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not force and output.exists() and output.stat().st_size > 100_000:
        return output

    fade_out_start = max(0.0, duration - FADE_SECONDS)
    fade = f"fade=t=in:st=0:d={FADE_SECONDS:.3f},fade=t=out:st={fade_out_start:.3f}:d={FADE_SECONDS:.3f}"
    command: list[str]

    if scene.visual == "source":
        source = SOURCES / scene.source
        if not source.exists():
            raise RuntimeError(f"Required NASA source clip is missing: {source}")
        video_filter = (
            f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={OUT_W}:{OUT_H},setsar=1,fps={FPS},"
            "eq=contrast=1.08:saturation=1.12:brightness=-0.015,"
            f"{fade},format=yuv420p"
        )
        command = [
            ffmpeg, "-y", "-loglevel", "warning", "-ss", f"{scene.trim_start:.3f}", "-i", str(source),
            "-t", f"{duration:.3f}", "-an", "-vf", video_filter,
        ]
    elif scene.visual == "image":
        source = ASSETS / scene.source
        if not source.exists():
            raise RuntimeError(f"Required artwork is missing: {source}")
        zoom_speed = 0.00042 if index % 2 == 0 else 0.00034
        pan = "sin(on/45)*7" if index % 2 == 0 else "cos(on/48)*7"
        video_filter = (
            f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={OUT_W}:{OUT_H},"
            f"zoompan=z='min(zoom+{zoom_speed:.5f},1.12)':x='(iw-iw/zoom)/2+{pan}':"
            f"y='(ih-ih/zoom)/2+sin(on/55)*4':d=1:s={OUT_W}x{OUT_H}:fps={FPS},"
            "eq=contrast=1.06:saturation=1.08,"
            f"{fade},format=yuv420p"
        )
        command = [
            ffmpeg, "-y", "-loglevel", "warning", "-loop", "1", "-framerate", str(FPS), "-i", str(source),
            "-t", f"{duration:.3f}", "-an", "-vf", video_filter,
        ]
    elif scene.visual == "bounce":
        source = BUILD / "motion_bounce.mp4"
        make_bounce_animation(source)
        video_filter = (
            f"scale={OUT_W}:{OUT_H}:flags=lanczos,setsar=1,fps={FPS},"
            "eq=contrast=1.10:saturation=1.14,"
            f"{fade},format=yuv420p"
        )
        command = [
            ffmpeg, "-y", "-loglevel", "warning", "-stream_loop", "-1", "-i", str(source),
            "-t", f"{duration:.3f}", "-an", "-vf", video_filter,
        ]
    else:  # pragma: no cover - protected by the static scene list above
        raise RuntimeError(f"Unknown visual type: {scene.visual}")

    command.extend([
        "-r", str(FPS), "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ])
    run(command, label=f"scene {index + 1}")
    return output


def concat_visuals(scene_files: Iterable[Path], ffmpeg: str, force: bool) -> Path:
    output = BUILD / "visual_base.mp4"
    if not force and output.exists() and output.stat().st_size > 100_000:
        return output
    concat_list = BUILD / "visual_concat.txt"
    concat_list.write_text("".join(f"file '{path.as_posix()}'\n" for path in scene_files), encoding="utf-8")
    run([
        ffmpeg, "-y", "-loglevel", "warning", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", "-movflags", "+faststart", str(output),
    ], label="concat visuals")
    return output


# ---------------------------------------------------------------------------
# Captions, music, and publishing assets
# ---------------------------------------------------------------------------

def write_ass_and_srt(timeline: list[dict[str, float | Scene]]) -> tuple[Path, Path]:
    ass_path = BUILD / "universe_impact_captions.ass"
    srt_path = DELIVERABLES / "universe_impact_black_hole_reel.srt"

    ass_lines = [
        "[Script Info]",
        "Title: Universe Impact — Are We Inside a Black Hole?",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding",
        # BGR(A) colours: white title, cyan kicker, and a small muted brand lock-up.
        "Style: Brand,DejaVu Sans,29,&H00D7F6FF,&H000000FF,&H80000000,&H80000000,1,0,0,0,100,100,1.1,0,1,1.5,1.5,7,58,58,56,1",
        "Style: Kicker,DejaVu Sans,31,&H00E5FDFF,&H000000FF,&H9A010B12,&H9A010B12,1,0,0,0,100,100,2.0,0,1,2.2,2.5,2,68,68,470,1",
        "Style: Headline,DejaVu Sans,66,&H00FFFFFF,&H000000FF,&HDD02050D,&HCC02050D,1,0,0,0,100,100,0.8,0,1,3.3,4.2,2,66,66,218,1",
        "Style: Evidence,DejaVu Sans,24,&H00B5D6E2,&H000000FF,&H8C02050D,&H8C02050D,0,0,0,0,100,100,0.8,0,1,1.4,1.6,9,58,58,56,1",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    total_end = float(timeline[-1]["end"])
    # Small branded tag + the transparency cue remain visible but do not compete
    # with the narration headlines.
    ass_lines.append(
        f"Dialogue: 0,0:00:00.00,{ass_time(total_end)},Brand,,0,0,0,,UNIVERSE IMPACT  •  COSMIC QUESTIONS"
    )
    ass_lines.append(
        f"Dialogue: 0,0:00:00.00,{ass_time(total_end)},Evidence,,0,0,0,,HYPOTHESIS  /  NOT ESTABLISHED FACT"
    )

    srt_lines: list[str] = []
    for number, entry in enumerate(timeline, start=1):
        scene = entry["scene"]
        assert isinstance(scene, Scene)
        start = float(entry["start"])
        end = start + float(entry["voice_duration"])
        display_start = start + 0.14
        display_end = float(entry["end"]) - 0.10
        # Fades are ASS override tags.  The content itself stays plain enough to
        # remain robust across Facebook's mobile image compression.
        ass_lines.append(
            f"Dialogue: 1,{ass_time(display_start)},{ass_time(display_end)},Kicker,,0,0,0,,{{\\fad(180,260)}}{clean_ass(scene.kicker)}"
        )
        ass_lines.append(
            f"Dialogue: 2,{ass_time(display_start + 0.12)},{ass_time(display_end)},Headline,,0,0,0,,{{\\fad(220,300)}}{clean_ass(scene.headline)}"
        )
        srt_lines.extend([
            str(number),
            f"{srt_time(start)} --> {srt_time(end)}",
            scene.narration,
            "",
        ])

    ass_path.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return ass_path, srt_path


def make_music(path: Path, duration: float, scene_starts: list[float], force: bool) -> None:
    """Create an original, license-safe cinematic pulse bed (no sampled music)."""
    if not force and path.exists() and path.stat().st_size > 100_000:
        return

    sample_rate = 48000
    count = int(math.ceil((duration + 0.1) * sample_rate))
    t = np.arange(count, dtype=np.float32) / sample_rate
    left = np.zeros(count, dtype=np.float32)
    right = np.zeros(count, dtype=np.float32)

    # A slowly moving two-note dark pad.
    slow = 0.5 + 0.5 * np.sin(2 * math.pi * t / 19.0 - 0.7)
    for frequency, level, pan in ((43.65, 0.030, -0.25), (65.41, 0.020, 0.15), (98.00, 0.011, 0.38), (130.81, 0.008, -0.42)):
        tone = np.sin(2 * math.pi * frequency * t + 0.25 * np.sin(2 * math.pi * t / 7.0)) * level
        left += tone * (1.0 - pan) * (0.65 + 0.35 * slow)
        right += tone * (1.0 + pan) * (0.65 + 0.35 * slow)

    # A restrained, synthetic pulse every 1.5 seconds.
    for beat in np.arange(0.45, duration, 1.5):
        start = int(beat * sample_rate)
        length = min(int(0.42 * sample_rate), count - start)
        if length <= 0:
            continue
        local_t = np.arange(length, dtype=np.float32) / sample_rate
        frequency = 92.0 * np.exp(-local_t * 5.5)
        phase = 2 * math.pi * np.cumsum(frequency) / sample_rate
        kick = np.sin(phase) * np.exp(-local_t * 8.0) * 0.055
        left[start:start + length] += kick
        right[start:start + length] += kick

    # Gentle impact / whoosh accents at scene changes; this is generated from
    # tones and noise, so there is no third-party music to clear.
    rng = np.random.default_rng(909)
    for index, cue in enumerate(scene_starts[1:], start=1):
        start = int(max(0.0, cue - 0.05) * sample_rate)
        length = min(int(0.8 * sample_rate), count - start)
        if length <= 0:
            continue
        local_t = np.arange(length, dtype=np.float32) / sample_rate
        frequency = (115.0 + index * 4.0) * np.exp(-local_t * 3.4)
        phase = 2 * math.pi * np.cumsum(frequency) / sample_rate
        impact = np.sin(phase) * np.exp(-local_t * 4.5) * 0.045
        noise = rng.normal(0.0, 1.0, length).astype(np.float32)
        noise *= np.sin(np.pi * np.minimum(local_t / 0.48, 1.0)) * np.exp(-local_t * 2.3) * 0.011
        left[start:start + length] += impact + noise * 0.82
        right[start:start + length] += impact - noise * 0.55

    # A clean fade makes the loop-free ending feel intentional.
    fade_count = min(int(0.7 * sample_rate), count)
    envelope = np.ones(count, dtype=np.float32)
    envelope[:fade_count] = np.linspace(0.0, 1.0, fade_count, dtype=np.float32)
    envelope[-fade_count:] *= np.linspace(1.0, 0.0, fade_count, dtype=np.float32)
    stereo = np.stack((left * envelope, right * envelope), axis=1)
    stereo = np.clip(stereo, -0.28, 0.28)
    pcm = (stereo * 32767.0).astype("<i2")

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
    output = DELIVERABLES / "universe_impact_black_hole_reel.mp4"
    if not force and output.exists() and output.stat().st_size > 100_000:
        return output

    total_duration = float(timeline[-1]["end"])
    music_path = BUILD / "universe_impact_original_score.wav"
    make_music(music_path, total_duration, [float(item["start"]) for item in timeline], force)

    # Input 0 is video, input 1 is music, and the subsequent inputs are narrated
    # scene files. Padding each voice file makes it line up with its visual beat.
    command: list[str] = [ffmpeg, "-y", "-loglevel", "warning", "-i", str(visual_base), "-i", str(music_path)]
    command.extend([item for scene in SCENES for item in ("-i", str(scene_audio_path(scene)))])

    fonts_dir = str(Path(font_path()).parent)
    video_filter = f"[0:v]ass=filename='{ass_path.as_posix()}':fontsdir='{fonts_dir}',format=yuv420p[vout]"
    audio_filters: list[str] = []
    stream_labels: list[str] = []
    for index, entry in enumerate(timeline):
        duration = float(entry["duration"])
        voice_duration = float(entry["voice_duration"])
        padding = max(0.05, duration - voice_duration + 0.02)
        label = f"voice{index}"
        stream_labels.append(f"[{label}]")
        # 2 + index because input 0 = visual and input 1 = music. The final
        # scene has a longer gap for the CTA, so its padding is derived from
        # the timeline rather than assumed to be the standard scene gap.
        audio_filters.append(
            f"[{index + 2}:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
            f"apad=pad_dur={padding:.3f},atrim=duration={duration:.3f}[{label}]"
        )
    audio_filters.append("".join(stream_labels) + f"concat=n={len(timeline)}:v=0:a=1[voice]")
    audio_filters.append("[1:a]aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,volume=0.24[music]")
    audio_filters.append(
        "[voice][music]amix=inputs=2:duration=first:normalize=0,"
        "acompressor=threshold=-17dB:ratio=3:attack=12:release=150,"
        "alimiter=limit=0.94,loudnorm=I=-16:LRA=7:TP=-1.5[aout]"
    )
    filter_complex = ";".join([video_filter, *audio_filters])

    command.extend([
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-level:v", "4.1",
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-ar", "48000", "-b:a", "160k", "-movflags", "+faststart", "-shortest", str(output),
    ])
    run(command, label="final Facebook reel")

    # Decode validation catches truncated renders before the file is handed over.
    run([ffmpeg, "-v", "error", "-i", str(output), "-f", "null", "-"], label="final decode validation", quiet=True)
    return output


def extract_cover(video: Path, ffmpeg: str) -> Path:
    cover = DELIVERABLES / "universe_impact_black_hole_cover.jpg"
    run([
        ffmpeg, "-y", "-loglevel", "warning", "-ss", "0.700", "-i", str(video), "-frames:v", "1",
        "-q:v", "2", "-vf", f"scale={OUT_W}:{OUT_H}:flags=lanczos", str(cover),
    ], label="cover image")
    return cover


def write_publishing_pack(timeline: list[dict[str, float | Scene]], final_video: Path, cover: Path, ffmpeg: str) -> Path:
    package = DELIVERABLES / "UNIVERSE_IMPACT_FACEBOOK_POST.md"
    duration = media_duration(final_video, ffmpeg)
    sources = """# Universe Impact — Facebook publishing pack

## Reel title
**Could the Big Bang Be Inside a Black Hole? | Hypothesis, Not Proof**

## Ready-to-paste Facebook caption
What if the Big Bang was not the beginning of *everything* — but the inside of a black hole in a larger cosmos? 🌌

Black-hole cosmology is a real family of speculative ideas, but it is **not established science**. The exciting part is not pretending we have the answer; it is asking what evidence would make the idea testable.

What cosmic fingerprint would convince you: a pattern in the CMB, primordial gravitational waves, or something no one has imagined yet?

Follow **Universe Impact** for big cosmic questions — wonder first, evidence always.

#UniverseImpact #Space #Astronomy #BlackHole #BigBang #Cosmology #Science #JWST #CosmicMystery

## Pinned-comment prompt
**Mind-bender:** If this idea ever became testable, what evidence should scientists look for first? Drop your best answer below. 👇

## Upload settings
- **File:** `universe_impact_black_hole_reel.mp4`
- **Format:** 1080 × 1920, H.264/AAC, vertical 9:16
- **Length:** approximately %.1f seconds
- **Cover:** `universe_impact_black_hole_cover.jpg`
- **Captions:** upload `universe_impact_black_hole_reel.srt` if Facebook's caption option is available. The reel also includes concise, burned-in headline cards.
- **Suggested first-frame hook:** “WHAT IF THE BIG BANG WAS INSIDE A BLACK HOLE?”

## Accessibility alt text
A vertical animated science reel from Universe Impact. It shows an orbiting black hole, a stylized collapse-and-bounce visualization, and cosmic background textures. On-screen text repeatedly states that the idea of a universe inside a black hole is a hypothesis, not established fact.

## Editorial integrity note
This reel intentionally separates **hypothesis** from **evidence**. It does **not** claim that humanity has discovered we live in a black hole. “Black-hole cosmology” is framed as a speculative family of models that would need a unique, testable observational signature to become supported science.

## Visual / audio provenance
- The black-hole source visualizations used in scenes 1, 5, and 7 are NASA Goddard Scientific Visualization Studio materials, downloaded from these pages / media endpoints:
  - `https://svs.gsfc.nasa.gov/vis/a010000/a014600/a014620/1-Orbiting_a_bare_black_hole-4K.mp4`
  - `https://svs.gsfc.nasa.gov/vis/a010000/a014600/a014620/3-Tidal_disruption_by_black_hole-4K.mp4`
- NASA SVS states that its content is public domain unless otherwise noted. Source visual audio is not used.
- The two vertical concept images are original AI-generated artwork for this reel and should be understood as **artist’s concepts**, not telescope imagery or evidence.
- The collapse → bounce animation, score, sound accents, captions, page lock-up, and edit are original to this project.
- Narration setting requested for rerenders: **edge-tts / en-US-ChristopherNeural / +0%%**.

## Research context to keep in the post description, if needed
- NASA Scientific Visualization Studio usage FAQ: `https://svs.gsfc.nasa.gov/`
- A concise explanation of why tidal disruption / black-hole visuals are visualizations rather than observations: `https://www.nasa.gov/universe/nasas-swift-mission-maps-a-stars-death-spiral-into-a-black-hole/`
- For the claim itself, retain the wording “hypothesis” or “speculative model”; do not turn it into “NASA proved we live inside a black hole.”
""" % duration
    package.write_text(sources, encoding="utf-8")
    return package


def write_render_manifest(timeline: list[dict[str, float | Scene]], final_video: Path, cover: Path, ffmpeg: str) -> None:
    manifest = {
        "title": "Could the Big Bang Be Inside a Black Hole? | Hypothesis, Not Proof",
        "page": "Universe Impact",
        "output": final_video.name,
        "cover": cover.name,
        "format": {"width": OUT_W, "height": OUT_H, "fps": FPS, "duration_seconds": round(media_duration(final_video, ffmpeg), 3)},
        "voice_requested": {"engine": "edge-tts", "voice": VOICE, "rate": RATE},
        "scientific_framing": "Speculative hypothesis; no direct observational proof is claimed.",
        "timeline": [
            {
                "key": entry["scene"].key,  # type: ignore[index,union-attr]
                "start": round(float(entry["start"]), 3),
                "end": round(float(entry["end"]), 3),
                "narration": entry["scene"].narration,  # type: ignore[index,union-attr]
            }
            for entry in timeline
        ],
    }
    (DELIVERABLES / "universe_impact_black_hole_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def build_render(force: bool) -> tuple[Path, Path, Path]:
    ensure_artwork()
    ffmpeg = find_ffmpeg()
    timeline = get_scene_timeline(ffmpeg)
    print("\n[plan] Scene timing")
    for entry in timeline:
        scene = entry["scene"]
        assert isinstance(scene, Scene)
        print(f"  {scene.key}: {float(entry['start']):5.2f}s → {float(entry['end']):5.2f}s")

    scene_files = [render_scene(entry, index, ffmpeg, force) for index, entry in enumerate(timeline)]
    visual_base = concat_visuals(scene_files, ffmpeg, force)
    ass_path, _ = write_ass_and_srt(timeline)
    final_video = render_final(visual_base, ass_path, timeline, ffmpeg, force)
    cover = extract_cover(final_video, ffmpeg)
    write_publishing_pack(timeline, final_video, cover, ffmpeg)
    write_render_manifest(timeline, final_video, cover, ffmpeg)
    return final_video, cover, DELIVERABLES / "UNIVERSE_IMPACT_FACEBOOK_POST.md"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Universe Impact black-hole hypothesis Facebook Reel.")
    parser.add_argument("--voice-only", action="store_true", help="Generate only the Edge-TTS narration files.")
    parser.add_argument("--render-only", action="store_true", help="Render using narration files already in build_universe_impact/audio/.")
    parser.add_argument("--force", action="store_true", help="Recreate cached audio, motion, scenes, and final output.")
    args = parser.parse_args()
    if args.voice_only and args.render_only:
        parser.error("--voice-only and --render-only cannot be used together")

    ensure_dirs()
    if not args.render_only:
        asyncio.run(synthesize_voice(args.force))
    if not args.voice_only:
        final_video, cover, package = build_render(args.force)
        print("\nDone.")
        print(f"  Reel:    {final_video}")
        print(f"  Cover:   {cover}")
        print(f"  Posting: {package}")


if __name__ == "__main__":
    main()
