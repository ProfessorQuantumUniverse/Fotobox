"""Render the review loading animation ONCE into a looping file.

Why a file instead of live JS physics? On the Pi 3 a per-frame canvas
simulation costs CPU/GPU while the photo is still downloading. Pre-rendering a
seamless looping animation here on a dev machine and letting the kiosk simply
decode an animated WebP is far cheaper – and it always looks identical.

Seamless loop trick: each ball is a real projectile bouncing on the floor.
A bounce of height ~A has period proportional to sqrt(A); we give every ball a
bounce period that divides the global loop length T (T, T/2, T/3 …), so after
exactly T every ball is back to its start → the animation loops with no jump.

Run:  python docs/make_loading_animation.py
Out:  server/static/loading.webp
"""
import math
import os
import random

from PIL import Image, ImageDraw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "server", "static", "loading.webp")

# Output geometry (3:2, matches the review photo slot). Rendered at SS× and
# downscaled for crisp anti-aliased circles.
W, H = 600, 400
SS = 2
FPS = 30
T = 2.0                      # loop length in seconds
FRAMES = int(round(T * FPS))
BG = (0, 0, 0)
FG = (255, 255, 255)

random.seed(7)               # reproducible build

# Build the ball set. Same global period T for all; per-ball "bounces" k makes
# the bounce period T/k (so it still divides T), and lower, faster bounces for
# higher k look like a lively, fluid cascade.
FLOOR = H - 6                # resting line near the bottom
balls = []
n = 13
for i in range(n):
    k = random.choice([1, 1, 2, 2, 3])          # how many bounces per loop
    r = random.uniform(14, 34)
    x = (i + 0.5) * (W / n) + random.uniform(-12, 12)
    amp = (H - 2.4 * r) / (k * k)               # higher k → lower bounce
    amp = max(amp, r * 1.2)
    phase = random.random()                      # start somewhere in its cycle
    balls.append({"x": x, "r": r, "k": k, "amp": amp, "phase": phase})


def render_frame(t_norm: float) -> Image.Image:
    """Render one frame at loop position t_norm in [0, 1)."""
    img = Image.new("RGB", (W * SS, H * SS), BG)
    d = ImageDraw.Draw(img)
    for b in balls:
        # local cycle position in [0,1) for this ball's sub-period
        u = ((t_norm * b["k"]) + b["phase"]) % 1.0
        h = 4.0 * b["amp"] * u * (1.0 - u)       # parabolic bounce height
        cy = FLOOR - b["r"] - h
        cx, r = b["x"], b["r"]
        d.ellipse(
            [(cx - r) * SS, (cy - r) * SS, (cx + r) * SS, (cy + r) * SS],
            fill=FG,
        )
    return img.resize((W, H), Image.LANCZOS)


def main() -> None:
    frames = [render_frame(i / FRAMES) for i in range(FRAMES)]
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=int(round(1000 / FPS)),
        loop=0,
        format="WEBP",
        quality=82,
        method=6,
    )
    size_kb = os.path.getsize(OUT) / 1024
    print(f"Wrote {OUT}  ({FRAMES} frames, {size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
