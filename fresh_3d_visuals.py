#!/usr/bin/env python3
"""Original, fully animated 3D-style visual sequences for Universe Impact v3.

This module renders six new motion clips from deterministic geometry, particles,
volumetric glow, perspective projection, and camera movement.  It contains no
still-image story backgrounds and does not read any of the legacy `sources/`
clips.  The public-domain NASA GIFs used elsewhere in v3 are composited by the
main build script; this module supplies the bespoke visual language around them.

The imagery is a conceptual science visualization, not a numerical simulation.
In particular, the bounce and CMB-style sequences are labeled as concepts by
the finished edit and must not be presented as observational evidence.
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


def _background(t: float, xx: np.ndarray, yy: np.ndarray, stars: dict[str, np.ndarray], hue: str) -> np.ndarray:
    """Build a dynamic deep-space base with parallax stars and a subtle nebula."""
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

    # A slow, large-scale nebula remains dim enough not to look like a static
    # backdrop; it shifts continuously under the foreground camera move.
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

    sx = ((stars["x"] + stars["depth"] * t * 11.0) % WORK_W).astype(np.int32)
    sy = ((stars["y"] + np.sin(t * 0.33 + stars["phase"]) * stars["drift"]) % WORK_H).astype(np.int32)
    twinkle = 0.58 + 0.42 * np.sin(t * (1.1 + stars["depth"] * 0.8) + stars["phase"])
    values = stars["brightness"] * twinkle
    # Fancy indexing is much faster than drawing hundreds of dim stars one by one.
    for channel, factor in enumerate((0.70, 0.88, 1.0)):
        np.add.at(frame[:, :, channel], (sy, sx), values * factor)
    return frame


def _make_stars(seed: int, count: int = 760) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    return {
        "x": rng.uniform(0, WORK_W, count).astype(np.float32),
        "y": rng.uniform(0, WORK_H, count).astype(np.float32),
        "depth": rng.uniform(0.15, 1.25, count).astype(np.float32),
        "phase": rng.uniform(0, TAU, count).astype(np.float32),
        "drift": rng.uniform(0.3, 4.0, count).astype(np.float32),
        "brightness": rng.uniform(16, 132, count).astype(np.float32),
    }


def _add_glow(
    frame: np.ndarray,
    xx: np.ndarray,
    yy: np.ndarray,
    cx: float,
    cy: float,
    sigma_x: float,
    sigma_y: float,
    colour: tuple[float, float, float],
    strength: float,
) -> None:
    x0 = max(0, int(cx - sigma_x * 3.2))
    x1 = min(WORK_W, int(cx + sigma_x * 3.2) + 1)
    y0 = max(0, int(cy - sigma_y * 3.2))
    y1 = min(WORK_H, int(cy + sigma_y * 3.2) + 1)
    if x0 >= x1 or y0 >= y1:
        return
    dist = ((xx[y0:y1, x0:x1] - cx) / max(1.0, sigma_x)) ** 2 + ((yy[y0:y1, x0:x1] - cy) / max(1.0, sigma_y)) ** 2
    value = np.exp(-0.5 * dist) * strength
    for channel, component in enumerate(colour):
        frame[y0:y1, x0:x1, channel] += value * component


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
    """Project world points through a deliberately exaggerated moving camera."""
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
    """Add light film grain so the upscaled matte holds together after encoding."""
    frame = np.asarray(image.convert("RGB"), dtype=np.int16)
    grain = rng.integers(-3, 4, (WORK_H // 2, WORK_W // 2, 1), dtype=np.int16)
    grain = np.repeat(np.repeat(grain, 2, axis=0), 2, axis=1)[:WORK_H, :WORK_W]
    return np.uint8(np.clip(frame + grain, 0, 255))


def _line(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], colour: tuple[int, int, int, int], width: int = 1) -> None:
    if len(points) >= 2:
        draw.line(points, fill=colour, width=width, joint="curve")


# ---------------------------------------------------------------------------
# Visual 01: orbiting camera / lensing-style accretion geometry
# ---------------------------------------------------------------------------


def render_lens_orbit(path: Path, ffmpeg: str, duration: float = 13.0, force: bool = False) -> None:
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] lens orbit  {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413201)
    xx, yy = _make_grids()
    stars = _make_stars(1413202, 920)
    count = 1120
    particle_radius = 45.0 + 235.0 * np.sqrt(rng.random(count))
    particle_angle = rng.uniform(0, TAU, count)
    particle_height = rng.normal(0.0, 7.0, count)
    particle_lane = rng.random(count)
    jet_height = rng.uniform(-330, 330, 180)
    jet_angle = rng.uniform(0, TAU, 180)
    jet_spread = rng.exponential(16.0, 180)
    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            frame = _background(t, xx, yy, stars, "violet")
            cx = WORK_W * 0.50 + 17.0 * math.sin(t * 0.42)
            cy = WORK_H * 0.49 + 14.0 * math.cos(t * 0.31)
            yaw = 0.72 * math.sin(t * 0.32 - 0.4) + 0.18 * math.sin(t * 0.93)
            pitch = 0.49 + 0.23 * math.sin(t * 0.38 + 0.3)
            orbit = particle_angle + t * (0.55 + 2.8 * (210.0 / particle_radius) ** 0.52)
            x = particle_radius * np.cos(orbit)
            z = particle_radius * np.sin(orbit)
            y = particle_height + 5.5 * np.sin(orbit * 3.0 + t * 0.6)
            sx, sy, depth = _project(x, y, z, yaw, pitch, 740.0, 640.0, cx, cy)
            visible = (sx > -12) & (sx < WORK_W + 12) & (sy > -12) & (sy < WORK_H + 12)

            # Gas glow lives behind crisp particle tracks.
            _add_glow(frame, xx, yy, cx, cy, 160.0, 90.0, (26, 5, 40), 0.34)
            _add_glow(frame, xx, yy, cx - 36 * math.cos(yaw), cy + 5, 118.0, 60.0, (19, 10, 8), 0.28)
            image = _rgba(frame)
            glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            crisp = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(crisp)

            # Draw far material first. Warm/cool halves simulate Doppler colour
            # separation without claiming a calibrated physical rendering.
            order = np.argsort(depth)[::-1]
            for idx in order:
                if not visible[idx]:
                    continue
                phase = math.sin(orbit[idx] + yaw * 1.7)
                front = max(0.0, -phase)
                far = max(0.0, phase)
                hot = 115 + int(125 * front + 45 * particle_lane[idx])
                cold = 82 + int(128 * far + 38 * particle_lane[idx])
                colour = (hot, 58 + int(78 * particle_lane[idx]), cold, 126 + int(105 * particle_lane[idx]))
                radius = 0.65 + 1.65 * particle_lane[idx] + (1.0 if depth[idx] < 0 else 0.0)
                px, py = float(sx[idx]), float(sy[idx])
                if particle_lane[idx] > 0.82:
                    gdraw.ellipse((px - radius * 3.4, py - radius * 3.4, px + radius * 3.4, py + radius * 3.4), fill=(255, 91, 32, 55))
                draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=colour)

            # Two new, animated particle jets puncture the disk.
            jx = jet_spread * np.cos(jet_angle + t * 0.24)
            jz = jet_spread * np.sin(jet_angle + t * 0.24)
            jy = jet_height + 16.0 * np.sin(t * 1.8 + jet_angle)
            jsx, jsy, jdepth = _project(jx, jy, jz, yaw, pitch, 740.0, 640.0, cx, cy)
            for px, py, pz, height in zip(jsx, jsy, jdepth, jet_height):
                if -4 < px < WORK_W + 4 and -4 < py < WORK_H + 4:
                    alpha = 70 if abs(height) > 130 else 155
                    colour = (84, 230, 255, alpha) if height > 0 else (255, 114, 54, alpha)
                    radius = 1.1 if pz < 0 else 0.7
                    draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=colour)

            # Lensing arcs sweep behind the horizon as the view tilts.
            for ring_index in range(7):
                rx = 70 + ring_index * 22
                ry = (18 + ring_index * 6) * (0.62 + 0.46 * abs(math.cos(pitch)))
                start = -2.7 + 0.17 * math.sin(t * 0.8 + ring_index)
                end = 2.7 + 0.18 * math.cos(t * 0.6 + ring_index)
                points = [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(start, end, 52)]
                hue = (56, 218, 255, 40 + ring_index * 5) if ring_index % 2 else (255, 111, 42, 44 + ring_index * 5)
                _line(gdraw, points, hue, 2 if ring_index in (1, 4) else 1)

            glow = glow.filter(ImageFilter.GaussianBlur(radius=4.0))
            image = Image.alpha_composite(image, glow)
            image = Image.alpha_composite(image, crisp)
            foreground = Image.new("RGBA", image.size, (0, 0, 0, 0))
            fdraw = ImageDraw.Draw(foreground)
            horizon_rx = 83.0 + 6.0 * math.sin(t * 1.7)
            horizon_ry = horizon_rx * (0.88 + 0.08 * math.sin(pitch))
            fdraw.ellipse(
                (cx - horizon_rx, cy - horizon_ry, cx + horizon_rx, cy + horizon_ry),
                fill=(0, 0, 4, 252),
                outline=(82, 183, 222, 150),
                width=2,
            )
            fdraw.ellipse(
                (cx - horizon_rx * 1.12, cy - horizon_ry * 1.10, cx + horizon_rx * 1.12, cy + horizon_ry * 1.10),
                outline=(255, 102, 34, 125),
                width=2,
            )
            image = Image.alpha_composite(image, foreground)
            writer.stdin.write(_finalize(image, rng).tobytes())  # type: ignore[union-attr]
    finally:
        _finish_writer(writer, path.name)


# ---------------------------------------------------------------------------
# Visual 02: conceptual collapse → bounce → expanding region
# ---------------------------------------------------------------------------


def render_bounce_tunnel(path: Path, ffmpeg: str, duration: float = 13.0, force: bool = False) -> None:
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] bounce tunnel {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413203)
    xx, yy = _make_grids()
    stars = _make_stars(1413204, 660)
    count = 940
    direction = rng.normal(0.0, 1.0, (count, 3))
    direction /= np.linalg.norm(direction, axis=1, keepdims=True)
    lane = rng.uniform(0.22, 1.0, count)
    spiral = rng.uniform(-1.0, 1.0, count)
    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            u = t / duration
            frame = _background(t, xx, yy, stars, "ember" if u < 0.52 else "cool")
            cx = WORK_W * 0.5 + 8.0 * math.sin(t * 0.7)
            cy = WORK_H * 0.47 + 10.0 * math.cos(t * 0.48)
            # The middle beat has a sharp but short bounce, with no implication
            # that this is a measured or unique cosmological process.
            collapse = min(1.0, u / 0.39)
            expansion = max(0.0, (u - 0.40) / 0.60)
            expansion_ease = 1.0 - (1.0 - min(1.0, expansion)) ** 3
            if u < 0.40:
                radius = 440.0 * (1.0 - collapse) ** 0.65 + 18.0 + lane * 75.0
            else:
                radius = 28.0 + (160.0 + lane * 440.0) * expansion_ease
            theta = np.arctan2(direction[:, 2], direction[:, 0]) + t * (0.55 + 1.6 / (0.25 + lane))
            vertical = direction[:, 1] * radius * (0.78 + 0.18 * np.sin(t * 0.45))
            x = np.cos(theta) * np.sqrt(np.maximum(0.0, radius**2 - vertical**2 * 0.25))
            z = np.sin(theta) * np.sqrt(np.maximum(0.0, radius**2 - vertical**2 * 0.25))
            y = vertical + 20.0 * spiral * np.sin(t * 1.1 + lane * 5.0)
            yaw = 0.24 * math.sin(t * 0.43)
            pitch = 0.28 + 0.20 * math.sin(t * 0.27)
            sx, sy, depth = _project(x, y, z, yaw, pitch, 860.0, 670.0, cx, cy)
            visible = (sx > -10) & (sx < WORK_W + 10) & (sy > -10) & (sy < WORK_H + 10)

            flash = math.exp(-((u - 0.405) / 0.035) ** 2)
            _add_glow(frame, xx, yy, cx, cy, 128.0 + 100.0 * flash, 128.0 + 100.0 * flash, (68, 42, 22), 1.0 + 0.75 * flash)
            _add_glow(frame, xx, yy, cx, cy, 44.0, 44.0, (254, 128, 62), 2.4 * flash)
            image = _rgba(frame)
            glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            crisp = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(crisp)

            order = np.argsort(depth)[::-1]
            for idx in order:
                if not visible[idx]:
                    continue
                px, py = float(sx[idx]), float(sy[idx])
                colour = (255, 100 + int(90 * lane[idx]), 48 + int(55 * lane[idx]), 125) if u < 0.42 else (58, 210 + int(42 * lane[idx]), 255, 125)
                size = 0.7 + 1.9 * lane[idx] * (1.0 if depth[idx] < 160 else 0.72)
                # A short direction line makes the flow visibly collapse/expand.
                ux = px - cx
                uy = py - cy
                norm = max(1.0, math.hypot(ux, uy))
                direction_sign = -1.0 if u < 0.40 else 1.0
                trail = 4.0 + 10.0 * lane[idx]
                gdraw.line((px, py, px - direction_sign * ux / norm * trail, py - direction_sign * uy / norm * trail), fill=colour, width=2)
                draw.ellipse((px - size, py - size, px + size, py + size), fill=(colour[0], colour[1], colour[2], 185))

            # Expanding wave shells make the hand-off at the bounce unmistakable.
            for ring in range(7):
                if u < 0.40:
                    rr = 42 + ring * 24 + 42 * (1.0 - collapse)
                    alpha = 66 - ring * 6
                    colour = (255, 105, 44, max(0, alpha))
                else:
                    wave_phase = (expansion_ease * 1.25 + ring / 7.0) % 1.0
                    rr = 22 + 460 * wave_phase
                    alpha = int(145 * (1.0 - wave_phase) ** 1.5)
                    colour = (80, 237, 255, alpha)
                gdraw.ellipse((cx - rr, cy - rr * 0.62, cx + rr, cy + rr * 0.62), outline=colour, width=2)

            glow = glow.filter(ImageFilter.GaussianBlur(radius=3.0))
            image = Image.alpha_composite(image, glow)
            image = Image.alpha_composite(image, crisp)
            front = Image.new("RGBA", image.size, (0, 0, 0, 0))
            fdraw = ImageDraw.Draw(front)
            core_r = 45.0 * (1.0 - min(1.0, expansion_ease * 0.76))
            if u < 0.44:
                fdraw.ellipse((cx - core_r, cy - core_r * 0.9, cx + core_r, cy + core_r * 0.9), fill=(0, 0, 4, 220))
            else:
                fdraw.ellipse((cx - 14, cy - 14, cx + 14, cy + 14), fill=(248, 214, 145, 220))
            image = Image.alpha_composite(image, front)
            writer.stdin.write(_finalize(image, rng).tobytes())  # type: ignore[union-attr]
    finally:
        _finish_writer(writer, path.name)


# ---------------------------------------------------------------------------
# Visual 03: forward flight through a three-dimensional cosmic web
# ---------------------------------------------------------------------------


def render_cosmic_web(path: Path, ffmpeg: str, duration: float = 13.0, force: bool = False) -> None:
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] cosmic web   {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413205)
    xx, yy = _make_grids()
    stars = _make_stars(1413206, 510)
    # A dense enough constellation of clusters keeps the forward camera flight
    # legible on a small phone screen; it is still sparse compared with a real
    # cosmological simulation, hence the conceptual treatment in the edit.
    clusters = 18
    per_cluster = 25
    anchors = np.column_stack((rng.uniform(-330, 330, clusters), rng.uniform(-390, 390, clusters), rng.uniform(-150, 1550, clusters)))
    points: list[list[float]] = []
    cluster_id: list[int] = []
    for ci, (ax, ay, az) in enumerate(anchors):
        for _ in range(per_cluster):
            points.append([ax + rng.normal(0, 35), ay + rng.normal(0, 35), az + rng.normal(0, 90)])
            cluster_id.append(ci)
    nodes = np.asarray(points, dtype=np.float32)
    cluster_id_a = np.asarray(cluster_id)
    # Link nearby nodes within every cluster and make sparse bridges between anchors.
    edges: list[tuple[int, int]] = []
    for ci in range(clusters):
        ids = np.where(cluster_id_a == ci)[0]
        for j, node in enumerate(ids):
            for k in ids[j + 1 : j + 4]:
                edges.append((int(node), int(k)))
    for ci in range(clusters - 1):
        a = np.where(cluster_id_a == ci)[0][0]
        b = np.where(cluster_id_a == ci + 1)[0][0]
        edges.append((int(a), int(b)))
    node_hue = rng.uniform(0.0, 1.0, len(nodes))
    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            frame = _background(t, xx, yy, stars, "cool")
            z = ((nodes[:, 2] - t * 105.0 + 260.0) % 1750.0) - 200.0
            x = nodes[:, 0] + 36.0 * np.sin(t * 0.27 + nodes[:, 2] * 0.012)
            y = nodes[:, 1] + 28.0 * np.cos(t * 0.22 + nodes[:, 0] * 0.015)
            yaw = 0.16 * math.sin(t * 0.37)
            pitch = 0.10 * math.cos(t * 0.29)
            sx, sy, depth = _project(x, y, z, yaw, pitch, 990.0, 730.0, WORK_W * 0.5, WORK_H * 0.51)
            image = _rgba(frame)
            glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            crisp = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(crisp)

            # Bridges make the dimensions read as a connected cosmic web rather
            # than a static star background.
            for a, b in edges:
                if depth[a] > -800 and depth[b] > -800:
                    ax, ay, bx, by = sx[a], sy[a], sx[b], sy[b]
                    if -80 < ax < WORK_W + 80 and -80 < bx < WORK_W + 80 and -80 < ay < WORK_H + 80 and -80 < by < WORK_H + 80:
                        alpha = int(31 + 76 * max(0.0, 1.0 - (depth[a] + depth[b] + 900.0) / 2100.0))
                        _line(gdraw, [(float(ax), float(ay)), (float(bx), float(by))], (46, 175, 255, max(0, min(118, alpha))), 1)

            order = np.argsort(depth)[::-1]
            for idx in order:
                if not (-18 < sx[idx] < WORK_W + 18 and -18 < sy[idx] < WORK_H + 18):
                    continue
                proximity = max(0.0, min(1.0, 1.0 - (depth[idx] + 480.0) / 1500.0))
                radius = 1.0 + 4.8 * proximity
                hue = node_hue[idx]
                if hue > 0.64:
                    colour = (62, 213, 255, int(80 + 140 * proximity))
                elif hue > 0.30:
                    colour = (196, 86, 255, int(75 + 145 * proximity))
                else:
                    colour = (255, 130, 68, int(70 + 145 * proximity))
                px, py = float(sx[idx]), float(sy[idx])
                if proximity > 0.52:
                    gdraw.ellipse((px - radius * 4.2, py - radius * 4.2, px + radius * 4.2, py + radius * 4.2), fill=(colour[0], colour[1], colour[2], 34))
                draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=colour)

            # A receding HUD-like reference grid gives the flight camera an
            # obvious motion cue without pretending to be mission data.
            for row in range(7):
                zline = 80 + ((row * 230 - t * 145) % 1300)
                xp = np.array([-420.0, 420.0])
                yp = np.array([260.0, 260.0])
                zp = np.array([zline, zline])
                gx, gy, _ = _project(xp, yp, zp, yaw, pitch, 990.0, 730.0)
                _line(gdraw, [(float(gx[0]), float(gy[0])), (float(gx[1]), float(gy[1]))], (44, 155, 234, 26), 1)

            glow = glow.filter(ImageFilter.GaussianBlur(radius=3.0))
            image = Image.alpha_composite(image, glow)
            image = Image.alpha_composite(image, crisp)
            writer.stdin.write(_finalize(image, rng).tobytes())  # type: ignore[union-attr]
    finally:
        _finish_writer(writer, path.name)


# ---------------------------------------------------------------------------
# Visual 04: a rotating, conceptual CMB-style sphere / testable fingerprint
# ---------------------------------------------------------------------------


def render_cmb_signal(path: Path, ffmpeg: str, duration: float = 13.0, force: bool = False) -> None:
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] signal sphere {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413207)
    xx, yy = _make_grids()
    stars = _make_stars(1413208, 620)
    latitudes = np.linspace(-math.pi / 2 + 0.045, math.pi / 2 - 0.045, 37)
    longitudes = np.linspace(0.0, TAU, 76, endpoint=False)
    lon, lat = np.meshgrid(longitudes, latitudes)
    lon = lon.ravel()
    lat = lat.ravel()
    base_x = np.cos(lat) * np.cos(lon)
    base_y = np.sin(lat)
    base_z = np.cos(lat) * np.sin(lon)
    texture = 0.52 * np.sin(lon * 5.0 + lat * 3.0) + 0.30 * np.sin(lon * 11.0 - lat * 7.0) + rng.normal(0, 0.34, len(lon))
    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            frame = _background(t, xx, yy, stars, "violet")
            cx = WORK_W * 0.50 + 9.0 * math.sin(t * 0.34)
            cy = WORK_H * 0.49 + 8.0 * math.cos(t * 0.27)
            sphere_r = 250.0 + 12.0 * math.sin(t * 0.31)
            yaw = t * 0.42
            pitch = 0.26 * math.sin(t * 0.31)
            cyaw, syaw = math.cos(yaw), math.sin(yaw)
            cp, sp = math.cos(pitch), math.sin(pitch)
            xr = base_x * cyaw + base_z * syaw
            zr = -base_x * syaw + base_z * cyaw
            yr = base_y * cp - zr * sp
            zr2 = base_y * sp + zr * cp
            sx = cx + sphere_r * xr
            sy = cy + sphere_r * yr
            image = _rgba(frame)
            glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            crisp = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(crisp)

            # Hazy outer atmosphere and a moving scan cone.
            gdraw.ellipse((cx - sphere_r * 1.16, cy - sphere_r * 1.16, cx + sphere_r * 1.16, cy + sphere_r * 1.16), outline=(64, 195, 255, 50), width=3)
            gdraw.ellipse((cx - sphere_r * 1.04, cy - sphere_r * 1.04, cx + sphere_r * 1.04, cy + sphere_r * 1.04), outline=(196, 92, 255, 45), width=2)
            order = np.argsort(zr2)
            for idx in order:
                if zr2[idx] < -0.12:
                    continue
                value = texture[idx] + 0.20 * math.sin(t * 1.6 + lon[idx] * 2.0)
                front = 0.30 + 0.70 * zr2[idx]
                if value > 0.44:
                    colour = (255, int(102 + 90 * front), 72, int(110 + 120 * front))
                elif value < -0.42:
                    colour = (47, int(164 + 65 * front), 255, int(108 + 120 * front))
                else:
                    colour = (175, int(108 + 78 * front), 236, int(92 + 108 * front))
                radius = 0.9 + 1.6 * max(0.0, zr2[idx])
                px, py = float(sx[idx]), float(sy[idx])
                if value > 0.82 and zr2[idx] > 0.15:
                    gdraw.ellipse((px - radius * 4, py - radius * 4, px + radius * 4, py + radius * 4), fill=(255, 123, 74, 46))
                draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=colour)

            scan_angle = -1.1 + ((t * 0.78) % 2.2)
            endx = cx + math.cos(scan_angle) * sphere_r
            endy = cy + math.sin(scan_angle) * sphere_r
            gdraw.line((cx, cy, endx, endy), fill=(108, 246, 255, 120), width=3)
            scan_r = 18 + ((t * 72.0) % (sphere_r * 1.32))
            gdraw.ellipse((cx - scan_r, cy - scan_r, cx + scan_r, cy + scan_r), outline=(86, 242, 255, int(110 * (1.0 - scan_r / (sphere_r * 1.35)))), width=2)
            # Concentric reticle circles outside the sphere explicitly signal a
            # conceptual "search for a pattern" rather than a literal map.
            for rr in (sphere_r * 0.45, sphere_r * 0.74, sphere_r):
                draw.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(135, 222, 255, 44), width=1)

            glow = glow.filter(ImageFilter.GaussianBlur(radius=4.0))
            image = Image.alpha_composite(image, glow)
            image = Image.alpha_composite(image, crisp)
            writer.stdin.write(_finalize(image, rng).tobytes())  # type: ignore[union-attr]
    finally:
        _finish_writer(writer, path.name)


# ---------------------------------------------------------------------------
# Visual 05: 3D spacetime grid with a binary merger and outgoing waves
# ---------------------------------------------------------------------------


def render_spacetime_waves(path: Path, ffmpeg: str, duration: float = 13.0, force: bool = False) -> None:
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] spacetime grid {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413209)
    xx, yy = _make_grids()
    stars = _make_stars(1413210, 430)
    gx = np.linspace(-330.0, 330.0, 35)
    gz = np.linspace(-300.0, 300.0, 29)
    grid_x, grid_z = np.meshgrid(gx, gz)
    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            u = t / duration
            frame = _background(t, xx, yy, stars, "cool")
            cx, cy = WORK_W * 0.5, WORK_H * 0.52
            separation = 150.0 * (1.0 - min(1.0, u * 1.15)) ** 0.72
            theta = t * (1.25 + u * 2.4)
            a_x, a_z = separation * math.cos(theta), separation * math.sin(theta)
            b_x, b_z = -a_x, -a_z
            d_a = np.sqrt((grid_x - a_x) ** 2 + (grid_z - a_z) ** 2 + 650.0)
            d_b = np.sqrt((grid_x - b_x) ** 2 + (grid_z - b_z) ** 2 + 650.0)
            wave_a = 19.0 * np.sin(d_a * 0.072 - t * 3.1) * np.exp(-d_a / 460.0)
            wave_b = 19.0 * np.sin(d_b * 0.072 - t * 3.1) * np.exp(-d_b / 460.0)
            gravity = -3800.0 / d_a - 3800.0 / d_b
            grid_y = gravity + wave_a + wave_b
            yaw = -0.35 + 0.24 * math.sin(t * 0.23)
            pitch = 0.58 + 0.09 * math.sin(t * 0.31)
            sx, sy, depth = _project(grid_x.ravel(), grid_y.ravel(), grid_z.ravel(), yaw, pitch, 990.0, 800.0, cx, cy)
            sx = sx.reshape(grid_x.shape)
            sy = sy.reshape(grid_x.shape)
            image = _rgba(frame)
            glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            crisp = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(crisp)

            for row in range(sx.shape[0]):
                points = [(float(sx[row, col]), float(sy[row, col])) for col in range(sx.shape[1])]
                major = row % 3 == 0
                _line(gdraw, points, (43, 218, 255, 92 if major else 48), 2 if major else 1)
                _line(draw, points, (95, 231, 255, 94 if major else 50), 1)
            for col in range(sx.shape[1]):
                points = [(float(sx[row, col]), float(sy[row, col])) for row in range(sx.shape[0])]
                major = col % 3 == 0
                _line(gdraw, points, (165, 76, 255, 76 if major else 38), 2 if major else 1)
                _line(draw, points, (172, 108, 255, 70 if major else 34), 1)

            # Project the two horizons onto the grid and then let them coalesce.
            if u < 0.88:
                bhx = np.array([a_x, b_x])
                bhz = np.array([a_z, b_z])
                bhy = np.array([-3800.0 / math.sqrt(650.0), -3800.0 / math.sqrt(650.0)])
                px, py, _ = _project(bhx, bhy, bhz, yaw, pitch, 990.0, 800.0, cx, cy)
                radii = (23 + 10 * (1.0 - u), 23 + 10 * (1.0 - u))
            else:
                px, py = np.array([cx]), np.array([cy + 58])
                radii = (45 + 13 * math.sin(t * 4.0),)
            for pxi, pyi, rr in zip(px, py, radii):
                gdraw.ellipse((pxi - rr * 2.7, pyi - rr * 2.7, pxi + rr * 2.7, pyi + rr * 2.7), outline=(255, 95, 47, 110), width=4)
                draw.ellipse((pxi - rr, pyi - rr, pxi + rr, pyi + rr), fill=(1, 2, 8, 245), outline=(255, 149, 70, 170), width=2)

            origin_x, origin_y = (float(np.mean(px)), float(np.mean(py)))
            for wave_index in range(6):
                phase = ((t * 0.75 + wave_index / 6.0) % 1.0)
                rr = 20 + phase * 520
                alpha = int(92 * (1.0 - phase) ** 1.8)
                gdraw.ellipse((origin_x - rr, origin_y - rr * 0.54, origin_x + rr, origin_y + rr * 0.54), outline=(255, 103, 48, alpha), width=2)

            glow = glow.filter(ImageFilter.GaussianBlur(radius=3.1))
            image = Image.alpha_composite(image, glow)
            image = Image.alpha_composite(image, crisp)
            writer.stdin.write(_finalize(image, rng).tobytes())  # type: ignore[union-attr]
    finally:
        _finish_writer(writer, path.name)


# ---------------------------------------------------------------------------
# Visual 06: expanding spiral / cosmic-dawn finale
# ---------------------------------------------------------------------------


def render_universe_dawn(path: Path, ffmpeg: str, duration: float = 13.0, force: bool = False) -> None:
    if path.exists() and path.stat().st_size > 100_000 and not force:
        return
    print(f"[3d] universe dawn {duration:.1f}s → {path.name}")
    rng = np.random.default_rng(1413211)
    xx, yy = _make_grids()
    stars = _make_stars(1413212, 800)
    count = 1440
    arm = rng.integers(0, 4, count)
    radial = 22.0 + 300.0 * np.sqrt(rng.random(count))
    arm_noise = rng.normal(0, 0.22, count)
    height = rng.normal(0, 24.0, count)
    brightness = rng.uniform(0.25, 1.0, count)
    writer = _raw_writer(path, ffmpeg)

    try:
        for frame_index in range(int(round(duration * FPS))):
            t = frame_index / FPS
            u = t / duration
            frame = _background(t, xx, yy, stars, "violet")
            cx = WORK_W * 0.5 + 12 * math.sin(t * 0.29)
            cy = WORK_H * 0.50 + 8 * math.cos(t * 0.37)
            # Slow pull-back shifts matter outward; the central region remains
            # decorative/illustrative, not a literal black-hole birth claim.
            growth = 0.65 + 0.43 * u
            r = radial * growth
            angle = arm * TAU / 4.0 + np.log(r / 20.0) * 1.68 + t * (0.28 + 1.7 * 110.0 / r) + arm_noise
            x = r * np.cos(angle)
            z = r * np.sin(angle)
            y = height + 14 * np.sin(angle * 2.0 + t)
            yaw = 0.38 * math.sin(t * 0.25)
            pitch = 0.72 + 0.14 * math.sin(t * 0.20)
            sx, sy, depth = _project(x, y, z, yaw, pitch, 870.0, 690.0, cx, cy)
            _add_glow(frame, xx, yy, cx, cy, 114 + 32 * math.sin(t * 0.4), 94 + 20 * math.sin(t * 0.47), (38, 15, 50), 0.76)
            image = _rgba(frame)
            glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            crisp = Image.new("RGBA", image.size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(crisp)

            order = np.argsort(depth)[::-1]
            for idx in order:
                if not (-8 < sx[idx] < WORK_W + 8 and -8 < sy[idx] < WORK_H + 8):
                    continue
                px, py = float(sx[idx]), float(sy[idx])
                phase = (arm[idx] + int(r[idx] / 42)) % 3
                if phase == 0:
                    colour = (54, 208, 255, int(88 + 150 * brightness[idx]))
                elif phase == 1:
                    colour = (255, 103, 61, int(88 + 150 * brightness[idx]))
                else:
                    colour = (213, 107, 255, int(88 + 150 * brightness[idx]))
                size = 0.65 + 2.2 * brightness[idx] * max(0.55, 1.0 - depth[idx] / 1700.0)
                if brightness[idx] > 0.84:
                    gdraw.ellipse((px - size * 4.0, py - size * 4.0, px + size * 4.0, py + size * 4.0), fill=(colour[0], colour[1], colour[2], 38))
                draw.ellipse((px - size, py - size, px + size, py + size), fill=colour)

            # Four arm guides subtly make the rotating depth structure legible.
            for arm_index in range(4):
                guide: list[tuple[float, float]] = []
                for rr in np.linspace(35, 330, 48):
                    aa = arm_index * TAU / 4.0 + math.log(rr / 20.0) * 1.68 + t * 0.33
                    gx = np.array([rr * math.cos(aa)])
                    gy = np.array([2.0 * math.sin(aa * 2 + t)])
                    gz = np.array([rr * math.sin(aa)])
                    px, py, _ = _project(gx, gy, gz, yaw, pitch, 870.0, 690.0, cx, cy)
                    guide.append((float(px[0]), float(py[0])))
                _line(gdraw, guide, (92, 223, 255, 42), 1)

            core = 32 + 7 * math.sin(t * 2.4)
            gdraw.ellipse((cx - core * 3.1, cy - core * 3.1, cx + core * 3.1, cy + core * 3.1), fill=(255, 102, 64, 70))
            glow = glow.filter(ImageFilter.GaussianBlur(radius=4.0))
            image = Image.alpha_composite(image, glow)
            image = Image.alpha_composite(image, crisp)
            core_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            cdraw = ImageDraw.Draw(core_layer)
            cdraw.ellipse((cx - core, cy - core * 0.86, cx + core, cy + core * 0.86), fill=(4, 3, 14, 220), outline=(255, 138, 77, 150), width=2)
            image = Image.alpha_composite(image, core_layer)
            writer.stdin.write(_finalize(image, rng).tobytes())  # type: ignore[union-attr]
    finally:
        _finish_writer(writer, path.name)


RENDERERS: dict[str, Callable[[Path, str, float, bool], None]] = {
    "lens_orbit": render_lens_orbit,
    "bounce_tunnel": render_bounce_tunnel,
    "cosmic_web": render_cosmic_web,
    "cmb_signal": render_cmb_signal,
    "spacetime_waves": render_spacetime_waves,
    "universe_dawn": render_universe_dawn,
}


def render_all(output_dir: Path, ffmpeg: str, force: bool = False, duration: float = 13.0) -> dict[str, Path]:
    """Render all original video clips and return their deterministic paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Path] = {}
    for key, renderer in RENDERERS.items():
        output = output_dir / f"{key}.mp4"
        renderer(output, ffmpeg, duration, force)
        outputs[key] = output
    return outputs


if __name__ == "__main__":
    # Useful independent smoke path; the project build calls render_all().
    import argparse
    import shutil

    parser = argparse.ArgumentParser(description="Render fresh 3D visual clips for Universe Impact v3.")
    parser.add_argument("output", type=Path, nargs="?", default=Path("fresh_3d_preview"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--duration", type=float, default=13.0)
    args = parser.parse_args()
    executable = shutil.which("ffmpeg")
    if not executable:
        import imageio_ffmpeg  # type: ignore

        executable = imageio_ffmpeg.get_ffmpeg_exe()
    render_all(args.output, executable, args.force, args.duration)
