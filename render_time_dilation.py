#!/usr/bin/env python3
"""Time Dilation Near Black Hole — Python procedural animation for Facebook Reel.

Renders a vertical (1080×1920) 30 fps clip about gravitational time dilation
— a confirmed prediction of general relativity where time runs slower near
massive objects. The "mind blowing" aspect: astronauts near a black hole could
return to find Earth has aged significantly more.

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


def _make_stars(seed: int, count: int = 400) -> dict[str, np.ndarray]:
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
# Visual: time dilation / gravitational redshift sequence
# ---------------------------------------------------------------------------


def render_time_dilation(path: Path, ffmpeg: str, duration: float = 15.0, force: bool = False) -> None:
    """Render a vertical time dilation sequence near a black hole.

    The view "falls" toward a black hole, with visual cues for:
    - Gravitational redshift (light shifting to redder wavelengths)
    - Time dilation (visual heartbeat slowing down)
    - Extreme curvature near the event horizon
    """
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] time dilation {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413215)
    xx, yy = _make_grids()
    stars = _make_stars(1413216, 400)

    # Falling particles/accortion simulation
    count = 600
    a = rng.uniform(0, TAU, count)  # initial angle
    r = rng.uniform(50.0, 400.0, count)  # orbital radius
    speed = rng.uniform(0.05, 0.25, count)  # angular speed (slow near BH)
    height = rng.normal(0, 40, count)  # vertical offset
    brightness = rng.uniform(20, 200, count)

    # Black hole parameters
    bh_x, bh_y = WORK_W * 0.5, WORK_H * 0.5
    bh_inner = 180.0  # photon sphere / inner boundary
    bh_outer = 300.0  # event horizon apparent size

    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            u = t / duration  # normalized [0,1]

            frame = _background(t, xx, yy, "ember")

            # Camera starts far and "falls" toward the black hole
            progress = math.sin(u * math.pi / 2.0)  # ease-in
            dist_from_bh = 500.0 * (1.0 - progress) + 250.0 * progress  # distance from BH center

            yaw = 0.02 * math.sin(t * 0.1)
            pitch = 0.01 * math.cos(t * 0.12)

            # Gravitational redshift factor: z = 1/sqrt(1 - r_s/r) - 1
            # Simulated: as particles get closer, light redshifts
            for i in range(count):
                # Orbital position
                angle = a[i] + t * speed[i]
                orbital_x = r[i] * math.cos(angle)
                orbital_y = height[i]
                orbital_z = r[i] * math.sin(angle)

                # Project through camera
                sx, sy, depth = _project(
                    np.array([orbital_x]),
                    np.array([orbital_y]),
                    np.array([orbital_z]),
                    yaw,
                    pitch,
                    dist_from_bh,
                    600.0,
                    bh_x,
                    bh_y,
                )
                sx, sy = float(sx[0]), float(sy[0])
                depth = float(depth[0])

                # Only draw if in view
                if not (-10 < sx < WORK_W + 10 and -10 < sy < WORK_H + 10):
                    continue

                # Distance from BH center for redshift effect
                dist_from_center = depth  # using depth as radial distance

                # Redshift: particles near BH appear increasingly red
                redshift = min(1.0, (bh_outer - dist_from_center) / bh_outer * 0.8) if dist_from_center < bh_outer * 1.2 else 0
                
                # Size increases as particles approach (visual perspective)
                size = 1.0 + 3.0 * (1.0 - redshift) * (dist_from_center / bh_outer)

                # Colour: cool blue → hot red shift
                if redshift > 0.5:
                    # Strongly redshifted
                    colour = (int(200 * redshift), int(50 + 150 * redshift), int(20 * redshift))
                elif redshift > 0.2:
                    # Moderate redshift
                    colour = (int(100 + 100 * redshift), int(50 + 100 * redshift), int(20 + 50 * redshift))
                else:
                    # Normal blue
                    colour = (int(50 + 100 * (1 - redshift)), int(100 - 50 * redshift), 255)

                if redshift > 0.05:
                    # Draw glowing particle
                    img = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
                    idraw = ImageDraw.Draw(img)
                    idraw.ellipse(
                        (sx - size, sy - size, sx + size, sy + size),
                        fill=(colour[0], colour[1], colour[2], int(200 * redshift)),
                    )
                    frame_np = np.array(frame, dtype=np.float32)
                    img_array = np.array(img, dtype=np.float32) / 255.0
                    for c in range(3):
                        frame_np[:, :, c] = np.clip(
                            frame_np[:, :, c] * (1.0 - img_array[:, :, 3]) + img_array[:, :, c] * img_array[:, :, 3], 0, 1
                        ) * 255
                    frame = frame_np.astype(np.uint8)

            # --- Black hole silhouette / event horizon ---
            # Dark central region with glowing accretion disk
            horizon_radius = int(250 * (1.0 - progress * 0.5))  # grows as we fall

            glow_surface = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow_surface)
            # Bright inner edge of accretion disk
            gdraw.ellipse(
                (bh_x - horizon_radius - 10, bh_y - horizon_radius * 1.5, bh_x + horizon_radius + 10, bh_y + horizon_radius * 1.5),
                outline=(255, 100, 20, 200),
                width=3,
            )
            # Faint outer Einstein ring
            gdraw.ellipse(
                (bh_x - horizon_radius * 1.8, bh_y - horizon_radius * 1.8, bh_x + horizon_radius * 1.8, bh_y + horizon_radius * 1.8),
                outline=(255, 200, 150, 50),
                width=2,
            )

            # --- Time dilation visual: slowing heartbeat ---
            # A visual pulse that slows down as we approach the BH
            u_time = u  # normalized time
            # Pulse frequency decreases as we get closer
            pulse_freq = 2.0 * (1.0 - 0.5 * progress)  # from 2Hz to 1Hz
            pulse_angle = (t * pulse_freq) % TAU
            
            # Draw a "heartbeat" pulse near the BH
            pulse_radius = 30.0 * (1.0 + 0.5 * progress)  # grows slightly
            pulse_x = bh_x + pulse_radius * math.cos(pulse_angle)
            pulse_y = bh_y + pulse_radius * math.sin(pulse_angle)
            
            # Color transitions from white (far) to red (near BH)
            pulse_alpha = 200 * (1.0 - progress)  # fades as we approach
            pulse_color = (255, int(100 + 100 * progress), 0)  # orange→red
            
            # Draw pulse ellipse
            pulse_surface = Image.new("RGBA", (WORK_W, WORK_H), (0, 0, 0, 0))
            pdraw = ImageDraw.Draw(pulse_surface)
            pdraw.ellipse(
                (pulse_x - pulse_radius, pulse_y - pulse_radius, pulse_x + pulse_radius, pulse_y + pulse_radius),
                outline=pulse_color + (int(pulse_alpha),),
                width=3,
            )

            # Composite everything
            frame_pil = _rgba(frame)
            frame_pil = Image.alpha_composite(frame_pil, glow_surface)
            frame_pil = Image.alpha_composite(frame_pil, pulse_surface)
            frame = np.array(frame_pil.convert("RGB"), dtype=np.float32)

            # Finalize with grain
            frame = _finalize(_rgba(frame), rng)

            writer.stdin.write(frame.tobytes() if isinstance(frame, np.ndarray) else frame.tobytes())  # type: ignore[union-attr]

    finally:
        _finish_writer(writer, path.name)


RENDERERS: dict[str, Callable[[Path, str, float, bool], None]] = {
    "time_dilation": render_time_dilation,
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

    parser = argparse.ArgumentParser(description="Render time dilation animation.")
    parser.add_argument("output", type=Path, nargs="?", default=Path("time_dilation_visual"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--duration", type=float, default=15.0)
    args = parser.parse_args()
    executable = shutil.which("ffmpeg")
    if not executable:
        import imageio_ffmpeg

        executable = imageio_ffmpeg.get_ffmpeg_exe()
    render_all(args.output, executable, args.force, args.duration)