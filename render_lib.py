#!/usr/bin/env python3
"""Render Engine & procedural vector generator for Universe Impact: Eaten Star video."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import subprocess

def add_film_grain(frame, rng, amp=5):
    H, W = frame.shape[:2]
    g = rng.integers(-amp, amp+1, (H//2, W//2, 1), dtype=np.int16)
    g = np.repeat(np.repeat(g, 2, axis=0), 2, axis=1)[:H, :W]
    out = frame.astype(np.int16) + g
    return np.clip(out, 0, 255).astype(np.uint8)

def render_binary_split(out_path, W=1080, H=1920, FPS=60, DUR=15.0):
    """
    Procedural animation: Two bright points orbiting each other, black hole enters,
    one dot flings off-screen, the other snaps into tight orbit.
    """
    N = int(FPS * DUR)
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo",
                             "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
                             "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "17", "-pix_fmt", "yuv420p", "-an", out_path],
                            stdin=subprocess.PIPE)

    rng = np.random.default_rng(42)
    # Background stars
    num_stars = 200
    stars_x = rng.integers(0, W, num_stars)
    stars_y = rng.integers(0, H, num_stars)
    stars_m = rng.uniform(0.1, 0.8, num_stars)

    CX, CY = W // 2, H // 2

    # Black hole properties
    bh_x, bh_y = CX, CY - 800  # Starts above
    bh_r = 120

    for i in range(N):
        t = i / FPS
        
        # Black canvas
        frame = np.full((H, W, 3), 5, dtype=np.uint8)
        
        # Draw background stars
        for (sx, sy, sm) in zip(stars_x, stars_y, stars_m):
            tw = 0.6 + 0.4*np.sin(t*3.0 + sx*0.1)
            frame[sy, sx] = np.clip(np.array([255, 255, 255])*sm*tw, 0, 255)

        img = Image.fromarray(frame)
        draw = ImageDraw.Draw(img)

        # Black hole motion (moves down to center)
        if t < 5.0:
            bh_y = CY - 800 + (800 * (t / 5.0))
        else:
            bh_y = CY

        # Binary star parameters
        # Star 1 (trapped) and Star 2 (flung)
        orbit_r = 80
        orbit_speed = 3.0
        
        if t < 5.0:
            # Normal binary orbit, drifting up towards BH slightly
            center_x = CX
            center_y = CY + 300 - (300 * (t / 5.0))
            
            s1_x = center_x + np.cos(t * orbit_speed) * orbit_r
            s1_y = center_y + np.sin(t * orbit_speed) * orbit_r
            
            s2_x = center_x + np.cos(t * orbit_speed + np.pi) * orbit_r
            s2_y = center_y + np.sin(t * orbit_speed + np.pi) * orbit_r
            
        else:
            # Separation event
            time_since_split = t - 5.0
            
            # Star 1 gets trapped in tight orbit around BH
            tight_r = 180 - min(40, time_since_split * 10)
            tight_speed = 5.0 + min(5.0, time_since_split * 2)
            
            s1_x = CX + np.cos(time_since_split * tight_speed + (5.0*orbit_speed)) * tight_r
            s1_y = CY + np.sin(time_since_split * tight_speed + (5.0*orbit_speed)) * tight_r
            
            # Star 2 gets flung away
            fling_vx = 300
            fling_vy = 600
            s2_x = CX + np.cos(5.0 * orbit_speed + np.pi) * orbit_r + (fling_vx * time_since_split)
            s2_y = CY + np.sin(5.0 * orbit_speed + np.pi) * orbit_r + (fling_vy * time_since_split)

        # Draw BH
        if t > 1.0:
            # Accretion disk / glow
            glow_r = bh_r + 40 + np.sin(t*10)*10
            draw.ellipse([CX - glow_r, bh_y - glow_r*0.3, CX + glow_r, bh_y + glow_r*0.3], fill=(255, 100, 30))
            draw.ellipse([CX - bh_r, bh_y - bh_r, CX + bh_r, bh_y + bh_r], fill=(0, 0, 0))

        # Draw Star 1 (Trapped)
        r1 = 15
        draw.ellipse([s1_x - r1, s1_y - r1, s1_x + r1, s1_y + r1], fill=(200, 230, 255))
        draw.ellipse([s1_x - r1*2, s1_y - r1*2, s1_x + r1*2, s1_y + r1*2], outline=(100, 150, 255), width=3)
        
        # Draw Star 2 (Flung)
        if s2_x < W + 100 and s2_y < H + 100:
            r2 = 15
            draw.ellipse([s2_x - r2, s2_y - r2, s2_x + r2, s2_y + r2], fill=(255, 220, 180))
            if t >= 5.0:
                # Add motion blur / streak for flung star
                draw.line([s2_x, s2_y, s2_x - fling_vx*0.1, s2_y - fling_vy*0.1], fill=(255, 180, 100), width=8)

        # Blur to make it glowy
        img = img.filter(ImageFilter.GaussianBlur(radius=2))
        
        frame = np.array(img)
        frame = add_film_grain(frame, rng)
        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()
    print(f"Generated {out_path}")

if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "binary_split.mp4"
    render_binary_split(out)
