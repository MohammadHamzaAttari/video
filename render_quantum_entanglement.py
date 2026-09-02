#!/usr/bin/env python3
"""Quantum Entanglement — Python procedural animation for Facebook Reel.

Renders a vertical (1080×1920) 30 fps clip about quantum entanglement — 
the "spooky action at a distance" that Einstein disputed but is now 
experimentally verified. When two particles become entangled, measuring 
one instantly determines the state of the other, regardless of distance.

The "mind blowing" aspect: information appears to travel faster than light, 
though the theory forbids using this for faster-than-light communication.

The imagery is a conceptual visualization, not a numerical simulation of
quantum mechanics.
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
# Shared image / projection utilities
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


def _make_stars(seed: int, count: int = 300) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "x": rng.uniform(0, WORK_W, count).astype(np.float32),
        "y": rng.uniform(0, WORK_H, count).astype(np.float32),
        "depth": rng.uniform(0.15, 1.25, count).astype(np.float32),
        "phase": rng.uniform(0, TAU, count).astype(np.float32),
        "drift": rng.uniform(0.3, 4.0, count).astype(np.float32),
        "brightness": rng.uniform(16, 132, count).astype(np.float32),
    }


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
# Visual: quantum entanglement sequence
# ---------------------------------------------------------------------------


def render_quantum_entanglement(path: Path, ffmpeg: str, duration: float = 15.0, force: bool = False) -> None:
    """Render a quantum entanglement visualization.

    Shows two particles becoming entangled, moving apart, and when one
    is "measured," the other instantly correlates — visualized with color-
    matching paths and connecting lines.
    """
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] quantum entanglement {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413217)
    xx, yy = _make_grids()
    stars = _make_stars(1413218, 300)

    # Entangled particle pair
    count = 400  # total particles in the "cloud"
    # Two groups: left and right
    group_a_count = count // 2
    group_b_count = count - group_a_count

    # Group A: starts left, moves right
    a_angle = rng.uniform(0, TAU, group_a_count)
    a_r = rng.uniform(80.0, 300.0, group_a_count)
    a_speed = rng.uniform(0.5, 2.0, group_a_count)
    a_height = rng.normal(0, 100, group_a_count)
    a_brightness = rng.uniform(50, 255, group_a_count)

    # Group B: starts right, moves left
    b_angle = rng.uniform(0, TAU, group_b_count)
    b_r = rng.uniform(80.0, 300.0, group_b_count)
    b_speed = rng.uniform(0.5, 2.0, group_b_count)
    b_height = rng.normal(0, 100, group_b_count)
    b_brightness = rng.uniform(50, 255, group_b_count)

    # Entanglement link parameters
    link_thickness = 3
    link_opacity = 200

    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            u = t / duration  # normalized [0,1]

            frame = _background(t, xx, yy, "violet")

            # Camera gently moves back to show the full separation
            progress = math.sin(u * math.pi / 2.0)
            cam_z = 600.0 * (1.0 - 0.5 * progress) + 300.0 * 0.5 * progress

            yaw = 0.05 * math.sin(t * 0.15)
            pitch = 0.03 * math.cos(t * 0.12)

            bh_x, bh_y = WORK_W * 0.5, WORK_H * 0.5

            # --- Group A particles (left → right) ---
            for i in range(group_a_count):
                # Position moves outward over time
                current_r = a_r[i] * (1.0 + 0.5 * u)  # expands outward
                current_angle = a_angle[i] + t * a_speed[i]

                x = current_r * math.cos(current_angle)
                y = a_height[i]
                z = current_r * math.sin(current_angle)

                sx, sy, depth = _project(
                    np.array([x]),
                    np.array([y]),
                    np.array([z]),
                    yaw,
                    pitch,
                    cam_z,
                    600.0,
                    bh_x,
                    bh_y,
                )
                sx, sy = float(sx[0]), float(sy[0])

                # Only draw if in view
                if not (-10 < sx < WORK_W + 10 and -10 < sy < WORK_H + 10):
                    continue

                # Color: group A is blues/cyans
                colour = (int(50 + 100 * (1 - u)), int(100 + 50 * (1 - u)), 255)
                size = 2.0 + 3.0 * (1 - u) * (a_brightness[i] / 255.0)

                if u > 0.05:
                    img = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
                    idraw = ImageDraw.Draw(img)
                    idraw.ellipse(
                        (sx - size, sy - size, sx + size, sy + size),
                        fill=(colour[0], colour[1], colour[2], int(200 * (1 - u))),
                    )
                    frame_np = np.array(frame, dtype=np.float32)
                    img_array = np.array(img, dtype=np.float32) / 255.0
                    for c in range(3):
                        frame_np[:, :, c] = np.clip(
                            frame_np[:, :, c] * (1.0 - img_array[:, :, 3]) + img_array[:, :, c] * img_array[:, :, 3], 0, 1
                        ) * 255
                    frame = frame_np.astype(np.uint8)

            # --- Group B particles (right → left) ---
            for i in range(group_b_count):
                current_r = b_r[i] * (1.0 + 0.5 * (1.0 - u))  # expands outward the other way
                current_angle = b_angle[i] + t * b_speed[i] + TAU / 2  # opposite starting side

                x = current_r * math.cos(current_angle)
                y = b_height[i]
                z = current_r * math.sin(current_angle)

                sx, sy, depth = _project(
                    np.array([x]),
                    np.array([y]),
                    np.array([z]),
                    yaw,
                    pitch,
                    cam_z,
                    600.0,
                    bh_x,
                    bh_y,
                )
                sx, sy = float(sx[0]), float(sy[0])

                # Only draw if in view
                if not (-10 < sx < WORK_W + 10 and -10 < sy < WORK_H + 10):
                    continue

                # Color: group B is reds/magentas
                colour = (int(255 * u), int(50 + 200 * u), int(200 * u))
                size = 2.0 + 3.0 * u * (b_brightness[i] / 255.0)

                if u < 0.95:
                    img = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
                    idraw = ImageDraw.Draw(img)
                    idraw.ellipse(
                        (sx - size, sy - size, sx + size, sy + size),
                        fill=(colour[0], colour[1], colour[2], int(200 * u)),
                    )
                    frame_np = np.array(frame, dtype=np.float32)
                    img_array = np.array(img, dtype=np.float32) / 255.0
                    for c in range(3):
                        frame_np[:, :, c] = np.clip(
                            frame_np[:, :, c] * (1.0 - img_array[:, :, 3]) + img_array[:, :, c] * img_array[:, :, 3], 0, 1
                        ) * 255
                    frame = frame_np.astype(np.uint8)

            # --- Entanglement link: when measured, connect the particles ---
            # Find nearest pair and draw connecting line
            if u > 0.2 and u < 0.8:
                # Simple: draw a few entanglement links at random positions
                n_links = 5
                for _ in range(n_links):
                    # Pick random particles from opposite groups
                    link_a = rng.integers(0, group_a_count)
                    link_b = rng.integers(0, group_b_count)

                    # Get their positions at current time
                    a_r_cur = a_r[link_a] * (1.0 + 0.5 * u)
                    a_angle_cur = a_angle[link_a] + t * a_speed[link_a]
                    a_x = a_r_cur * math.cos(a_angle_cur)
                    a_z = a_r_cur * math.sin(a_angle_cur)
                    a_sx, a_sy, _ = _project(
                        np.array([a_x]), np.array([0]), np.array([a_z]), yaw, pitch, cam_z, 600.0, bh_x, bh_y
                    )
                    a_sx, a_sy = float(a_sx[0]), float(a_sy[0])

                    b_r_cur = b_r[link_b] * (1.0 + 0.5 * u)
                    b_angle_cur = b_angle[link_b] + t * b_speed[link_b] + TAU / 2
                    b_x = b_r_cur * math.cos(b_angle_cur)
                    b_z = b_r_cur * math.sin(b_angle_cur)
                    b_sx, b_sy, _ = _project(
                        np.array([b_x]), np.array([0]), np.array([b_z]), yaw, pitch, cam_z, 600.0, bh_x, bh_y
                    )
                    b_sx, b_sy = float(b_sx[0]), float(b_sy[0])

                    # Draw connecting line if both in view
                    if (-10 < a_sx < WORK_W + 10 and -10 < a_sy < WORK_H + 10 and
                        -10 < b_sx < WORK_W + 10 and -10 < b_sy < WORK_H + 10):
                        # Line color: purple/magenta for entanglement
                        line_colour = (255, 0, 255, 200)
                        # Draw line on crisp layer
                        crisp = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
                        cdraw = ImageDraw.Draw(crisp)
                        cdraw.line((a_sx, a_sy, b_sx, b_sy), fill=line_colour, width=link_thickness)

                        # Also draw glowing circles at the particle positions
                        glow = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
                        gdraw = ImageDraw.Draw(glow)
                        gdraw.ellipse((a_sx - 8, a_sy - 8, a_sx + 8, a_sy + 8), fill=(255, 0, 255, 100))
                        gdraw.ellipse((b_sx - 8, b_sy - 8, b_sx + 8, b_sy + 8), fill=(255, 0, 255, 100))

                        # Composite
                        frame_pil = _rgba(frame)
                        frame_pil = Image.alpha_composite(frame_pil, crisp)
                        frame_pil = Image.alpha_composite(frame_pil, glow)

            # --- Measurement collapse visualization ---
            if u > 0.8:
                # When "measured," a bright correlation appears
                measure_x = rng.integers(200, WORK_W - 200)
                measure_y = rng.integers(100, WORK_H - 100)
                measure_radius = 50 + 30 * math.sin(t * 10)
                
                measure_surface = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
                mdraw = ImageDraw.Draw(measure_surface)
                # Bright white flash at measurement
                mdraw.ellipse(
                    (measure_x - measure_radius, measure_y - measure_radius,
                     measure_x + measure_radius, measure_y + measure_radius),
                    fill=(255, 255, 255, int(200 * (u - 0.8) / 0.2)),
                )
                # Correlation label text concept (can't draw text easily without font, so use ellipse)
                
                frame_pil = _rgba(frame)
                frame_pil = Image.alpha_composite(frame_pil, measure_surface)

            # Finalize with grain
            frame = _finalize(_rgba(frame), rng)

            writer.stdin.write(frame.tobytes() if isinstance(frame, np.ndarray) else frame.tobytes())  # type: ignore[union-attr]

    finally:
        _finish_writer(writer, path.name)


RENDERERS: dict[str, Callable[[Path, str, float, bool], None]] = {
    "quantum_entanglement": render_quantum_entanglement,
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

    parser = argparse.ArgumentParser(description="Render quantum entanglement animation.")
    parser.add_argument("output", type=Path, nargs="?", default=Path("quantum_entanglement"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--duration", type=float, default=15.0)
    args = parser.parse_args()
    executable = shutil.which("ffmpeg")
    if not executable:
        import imageio_ffmpeg

        executable = imageio_ffmpeg.get_ffmpeg_exe()
    render_all(args.output, executable, args.force, args.duration)