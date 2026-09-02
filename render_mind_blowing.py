#!/usr/bin/env python3
"""Mind-Bending Spacetime Wormhole — Python procedural animation for Facebook Reel.

Renders a vertical (1080×1920) 30 fps clip about traversable wormhones,
suitable as a "mind blowing" science visual for social media.
The imagery is a conceptual visualization, not a numerical simulation.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WORK_W = 540
WORK_H = 960
FPS = 30
TAU = math.tau

# ---------------------------------------------------------------------------
# Shared image / projection utilities (adapted from fresh_3d_visuals.py)
# ---------------------------------------------------------------------------


def _raw_writer(path: Path, ffmpeg: str) -> subprocess.Popen[bytes]:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-y",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WORK_W}x{WORK_H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "15",
        "-profile:v",
        "high",
        "-level:v",
        "4.0",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(path),
    ]
    proc: subprocess.Popen[bytes] = subprocess.Popen(command, stdin=subprocess.PIPE)
    if proc.stdin is None:
        raise RuntimeError(f"Could not open raw-video writer for {path}")
    return proc


def _finish_writer(proc: subprocess.Popen[bytes], name: str) -> None:
    assert proc.stdin is not None
    proc.stdin.close()
    return_code = proc.wait()
    if return_code:
        raise RuntimeError(f"FFmpeg failed while rendering {name} (exit code {return_code})")


def _make_grids() -> tuple[np.ndarray, np.ndarray]:
    yy, xx = np.mgrid[0:WORK_H, 0:WORK_W].astype(np.float32)
    return xx, yy


def _background(t: float, xx: np.ndarray, yy: np.ndarray, hue: str) -> np.ndarray:
    """Build a deep-space base with subtle nebula and parallax stars."""
    y_norm = yy / WORK_H
    x_norm = xx / WORK_W
    frame = np.empty((WORK_H, WORK_W, 3), dtype=np.float32)
    if hue == "ember":
        frame[:, :, 0] = 3.0 + 12.0 * y_norm
        frame[:, :, 1] = 3.0 + 3.5 * y_norm
        frame[:, :, 2] = 12.0 + 15.0 * (1.0 - y_norm)
    elif hue == "violet":
        frame[:, :, 0] = 4.0 + 7.0 * (1.0 - y_norm)
        frame[:, :, 1] = 4.0 + 5.0 * y_norm
        frame[:, :, 2] = 16.0 + 23.0 * (1.0 - y_norm)
    else:
        frame[:, :, 0] = 2.0 + 3.5 * y_norm
        frame[:, :, 1] = 6.0 + 10.0 * y_norm
        frame[:, :, 2] = 17.0 + 27.0 * (1.0 - 0.55 * y_norm)

    # Slow large-scale nebula shifting under camera move
    cx = 0.46 + 0.13 * math.sin(t * 0.14)
    cy = 0.48 + 0.09 * math.cos(t * 0.19)
    cloud = np.exp(-(((x_norm - cx) / 0.47) ** 2 + ((y_norm - cy) / 0.34) ** 2) * 2.2)
    ripple = 0.45 + 0.55 * np.sin(11.0 * x_norm + 6.0 * y_norm + t * 0.37)
    if hue == "ember":
        frame[:, :, 0] += cloud * (18.0 + 10.0 * ripple)
        frame[:, :, 1] += cloud * (4.0 + 4.0 * ripple)
        frame[:, :, 2] += cloud * 5.0
    elif hue == "violet":
        frame[:, :, 0] += cloud * (11.0 + 6.0 * ripple)
        frame[:, :, 1] += cloud * 4.0
        frame[:, :, 2] += cloud * (17.0 + 9.0 * ripple)
    else:
        frame[:, :, 0] += cloud * 2.0
        frame[:, :, 1] += cloud * (8.0 + 4.0 * ripple)
        frame[:, :, 2] += cloud * (16.0 + 10.0 * ripple)

    return frame


def _make_stars(seed: int, count: int = 500) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "x": rng.uniform(0, WORK_W, count).astype(np.float32),
        "y": rng.uniform(0, WORK_H, count).astype(np.float32),
        "depth": rng.uniform(0.15, 1.25, count).astype(np.float32),
        "phase": rng.uniform(0, TAU, count).astype(np.float32),
        "drift": rng.uniform(0.3, 4.0, count).astype(np.float32),
        "brightness": rng.uniform(16, 132, count).astype(np.float32),
    }


def _project(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    yaw: float,
    pitch: float,
    distance: float,
    focal: float,
    cx: float = WORK_W * 0.5,
    cy: float = WORK_H * 0.50,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Project world points through a moving camera."""
    cyaw, syaw = math.cos(yaw), math.sin(yaw)
    cpitch, spitch = math.cos(pitch), math.sin(pitch)
    xr = x * cyaw + z * syaw
    zr = -x * syaw + z * cyaw
    yr = y * cpitch - zr * spitch
    zr2 = y * spitch + zr * cpitch
    denom = np.maximum(80.0, zr2 + distance)
    return cx + focal * xr / denom, cy + focal * yr / denom, zr2


def _rgba(frame: np.ndarray) -> Image.Image:
    return Image.fromarray(np.uint8(np.clip(frame, 0, 255)), "RGB").convert("RGBA")


def _finalize(image: Image.Image, rng: np.random.Generator) -> np.ndarray:
    """Add light film grain."""
    frame = np.asarray(image.convert("RGB"), dtype=np.int16)
    grain = rng.integers(-3, 4, (WORK_H // 2, WORK_W // 2, 1), dtype=np.int16)
    grain = np.repeat(np.repeat(grain, 2, axis=0), 2, axis=1)[:WORK_H, :WORK_W]
    return np.uint8(np.clip(frame + grain, 0, 255))


def _line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], colour: tuple[int, int, int, int], width: int = 1) -> None:
    if len(points) >= 2:
        draw.line(points, fill=colour, width=width, joint="curve")


# ---------------------------------------------------------------------------
# Visual: traversable wormhole with Einstein ring and throat
# ---------------------------------------------------------------------------


def render_wormhole(path: Path, ffmpeg: str, duration: float = 15.0, force: bool = False) -> None:
    """Render a vertical wormhole/Einstein-ring travel sequence.

    The view flies down a throat with a luminous ring (gravitational lensing)
    and ends on a bright "exit" portal.  Colours shift from cool to warm as
    the traveler passes through, conveying the "mind blowing" nature of
    short-cut geometry.
    """
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] wormhole      {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413213)
    xx, yy = _make_grids()
    # Static deep-space background
    stars = _make_stars(1413214, 500)

    count = 800
    # Orbiters swirling around the throat
    a = rng.uniform(0, TAU, count)  # initial angle
    b = rng.uniform(0, TAU, count)  # secondary angle for radial drift
    radial = 80.0 + 300.0 * rng.random(count) ** 0.8  # distance from center
    height = rng.normal(0, 60, count)  # vertical offset (throat shape)
    speed = rng.uniform(0.8, 2.2, count)  # angular speed
    brightness = rng.uniform(30, 200, count)

    # Throat surface parameters
    throat_r = 300.0  # inner radius of the lensing ring
    throat_len = 400.0  # length along travel direction

    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            u = t / duration  # normalized [0,1]

            frame = _background(t, xx, yy, "violet")

            cx = WORK_W * 0.5
            cy = WORK_H * 0.5

            # Camera flies "into" the wormhole, starting far away and approaching the throat
            progress = math.sin(u * math.pi / 2.0)  # ease-in for smooth entrance
            cam_z = 800.0 * (1.0 - progress) + 200.0 * progress  # distance from throat

            yaw = 0.1 * math.sin(t * 0.15)  # subtle rotation
            pitch = 0.05 * math.cos(t * 0.12)

            # Generate orbiting particles around the throat
            for i in range(count):
                # Rotate each particle
                angle = a[i] + t * speed[i]
                # Position toroidally around the throat
                torus_x = (throat_r + radial[i] * math.cos(b[i] * 2.0)) * math.cos(angle)
                torus_y = height[i]  # vertical position
                torus_z = (throat_r + radial[i] * math.cos(b[i] * 2.0)) * math.sin(angle)

                # Project through camera
                sx, sy, depth = _project(
                    np.array([torus_x]),
                    np.array([torus_y]),
                    np.array([torus_z]),
                    yaw,
                    pitch,
                    cam_z,
                    600.0,
                    cx,
                    cy,
                )
                sx, sy = float(sx[0]), float(sy[0])
                depth = float(depth[0])

                # Only draw if in view
                if not (-10 < sx < WORK_W + 10 and -10 < sy < WORK_H + 10):
                    continue

                # Lens-ring effect: particles near the ring are brighter
                dist_from_ring = abs(depth - throat_r) / throat_r
                alpha = max(0, 1.0 - dist_from_ring * 3.0)
                size = 1.5 + 2.5 * alpha * (brightness[i] / 200.0)

                # Colour transitions from cool (entering) to warm (exiting)
                if u < 0.5:
                    # Entering: cool blues/cyans
                    colour = (int(50 + 80 * alpha), int(100 + 70 * alpha), int(200 + 55 * alpha))
                else:
                    # Exiting: warm oranges/purples
                    colour = (int(200 + 30 * alpha), int(80 + 70 * alpha), int(50 + 100 * alpha))

                if alpha > 0.1:
                    # Draw as a small glowing circle
                    img = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
                    idraw = ImageDraw.Draw(img)
                    idraw.ellipse(
                        (sx - size, sy - size, sx + size, sy + size),
                        fill=(colour[0], colour[1], colour[2], int(180 * alpha)),
                    )
                    frame = np.array(frame, dtype=np.float32)
                    img_array = np.array(img, dtype=np.float32) / 255.0
                    # Blend
                    for c in range(3):
                        frame[:, :, c] = np.clip(
                            frame[:, :, c] * (1.0 - img_array[:, :, 3]) + img_array[:, :, c] * img_array[:, :, 3], 0, 1
                        ) * 255
                    frame = frame.astype(np.uint8)

            # --- Main Einstein ring (gravitational lensing) ---
            # A bright ring formed by light bending around the wormhole throat
            ring_radius = int(300 * (1.0 - min(1.0, u * 1.2)))  # starts large, contracts
            ring_thickness = int(8 + 6 * math.sin(t * 0.5))

            # Draw the lensing ring
            for r in range(ring_thickness):
                r_radius = ring_radius - r * 2
                # Ring colour shifts
                if u < 0.5:
                    ring_colour = (100 + r * 10, 150 + r * 5, 255)  # cool blue-white
                else:
                    ring_colour = (255, 120 + r * 10, 60 + r * 5)  # warm

                # Thick arc segment covering bottom half (like an accretion disk view)
                points = []
                for angle_deg in range(180):
                    ang = math.radians(angle_deg)
                    # Elliptical ring representing the lensed horizon
                    px = cx + r_radius * 0.85 * math.cos(ang)
                    py = cy + r_radius * math.sin(ang) * 1.3  # stretched vertically
                    points.append((px, py))

                if len(points) >= 3:
                    idraw = ImageDraw.Draw(Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0)))
                    idraw.line(points, fill=(*ring_colour[:3], 120), width=max(1, ring_thickness))

            # --- Event horizon / throat opening ---
            # Dark central throat with glowing edge
            horizon_radius = int(200 * (1.0 - u * 0.8))
            # Glowing edge
            glow_surface = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow_surface)
            # Bright inner edge
            gdraw.ellipse(
                (cx - horizon_radius - 20, cy - horizon_radius - 20, cx + horizon_radius + 20, cy + horizon_radius + 20),
                outline=(255, 200, 80, 200),
                width=3,
            )
            # Faint outer Einstein ring
            gdraw.ellipse(
                (cx - horizon_radius * 1.4, cy - horizon_radius * 1.4, cx + horizon_radius * 1.4, cy + horizon_radius * 1.4),
                outline=(100, 200, 255, 80),
                width=2,
            )

            # --- Exit portal (as we emerge) ---
            if u > 0.7:
                exit_radius = int(250 * (u - 0.7) / 0.3)
                # Bright exit ellipse
                e_surface = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
                edraw = ImageDraw.Draw(e_surface)
                edraw.ellipse(
                    (cx - exit_radius, cy - exit_radius * 0.6, cx + exit_radius, cy + exit_radius * 0.6),
                    fill=(255, 255, 255, int(200 * (u - 0.7) / 0.3)),
                )
                # Composite
                frame_pil = _rgba(frame)
                frame_pil = Image.alpha_composite(frame_pil, glow_surface)
                frame_pil = Image.alpha_composite(frame_pil, e_surface)
                frame = np.array(frame_pil.convert("RGB"), dtype=np.float32)
            else:
                frame = _finalize(_rgba(frame), rng)

            writer.stdin.write(frame.tobytes() if isinstance(frame, np.ndarray) else frame.tobytes())  # type: ignore[union-attr]

    finally:
        _finish_writer(writer, path.name)


RENDERERS: dict[str, Callable[[Path, str, float, bool], None]] = {
    "wormhole": render_wormhole,
}


def render_all(output_dir: Path, ffmpeg: str, force: bool = False, duration: float = 15.0) -> dict[str, Path]:
    """Render all original video clips and return their deterministic paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for key, renderer in RENDERERS.items():
        output = output_dir / f"{key}.mp4"
        renderer(output, ffmpeg, duration, force)
        outputs[key] = output
    return outputs


if __name__ == "__main__":
    import argparse
    import shutil

    parser = argparse.ArgumentParser(description="Render mind-bending wormhole animation.")
    parser.add_argument("output", type=Path, nargs="?", default=Path("mind_blowing_wormhole"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--duration", type=float, default=15.0)
    args = parser.parse_args()
    executable = shutil.which("ffmpeg")
    if not executable:
        import imageio_ffmpeg

        executable = imageio_ffmpeg.get_ffmpeg_exe()
    render_all(args.output, executable, args.force, args.duration)