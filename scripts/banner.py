"""Draw the pixel-art sunset banner: dithered dusk sky, two swaying palms, and a tiny sun
glinting through the leaves.

Run:  python3 scripts/banner.py   (needs Pillow) -> assets/banner.gif
The scene is drawn at W x H and scaled up by SCALE with hard pixel edges.
"""

import math
import random
from pathlib import Path

from PIL import Image

W, H = 328, 72  # 984 x 216 on screen, the width of a GitHub README column
SCALE = 3
FRAMES = 72
FRAME_MS = 75  # 72 x 75ms: the same ~5.4s loop as before, just smoother
CLEAR = 96  # palette size; also the index used for unchanged pixels
OUT = Path(__file__).resolve().parent.parent / "assets" / "banner.gif"


# Sky colour stops from top (0) to bottom (1).
SKY = [
    (0.00, (72, 88, 184)),
    (0.20, (104, 88, 186)),
    (0.42, (150, 88, 188)),
    (0.62, (196, 90, 178)),
    (0.78, (222, 106, 176)),
    (0.90, (234, 136, 178)),
    (1.00, (228, 156, 172)),
]
SKY_STEPS = 18  # flat colour bands; dithering blends between them
DUSK = (24, 14, 22)  # the dark fade along the bottom edge
FADE_ROWS = 8

# The sun: a small bright disc with a glowing ring, set in a gap inside the right palm's
# crown so the swaying leaves cover and uncover it. Wide soft glare surrounds it, and a
# long horizontal streak with a rose-red edge shines whenever the gap opens up.
FLARE_X, FLARE_Y = 271, 18
FLARE = (255, 236, 222)
SPARK = (255, 255, 250)  # the sun's white-hot centre
SUN_R = 3
ROSE = (236, 118, 168)  # the reddish rim around the sun and along its streak

# Each palm has a back layer (lighter, hazier) and a front layer (darker).
LEAF_BACK = (104, 52, 112)
LEAF_FRONT = (66, 30, 74)
TRUNK_RING = (48, 20, 54)

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def sky_color(t):
    for (t0, c0), (t1, c1) in zip(SKY, SKY[1:]):
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0))
    return SKY[-1][1]


BANDS = [sky_color(i / (SKY_STEPS - 1)) for i in range(SKY_STEPS)]


def draw_sky(px):
    # Faint horizontal brush strokes across the sky.
    streak = [0.0] * H
    rnd = random.Random(7)
    for _ in range(14):
        y0, amp = rnd.uniform(4, H - 10), rnd.uniform(-0.7, 0.7)
        for y in range(H):
            streak[y] += amp * math.exp(-((y - y0) / 2.6) ** 2)
    for y in range(H):
        for x in range(W):
            wobble = 0.5 * math.sin(x / 19 + y / 9) + 0.3 * math.sin(x / 7 - y / 3) + streak[y]
            v = (y + wobble) / H * (SKY_STEPS - 1)
            v = max(0.0, min(SKY_STEPS - 1.0, v))
            lo = int(v)
            pick = lo + 1 if (v - lo) * 16 > BAYER[y % 4][x % 4] + 0.5 and lo + 1 < SKY_STEPS else lo
            px[x, y] = BANDS[pick]


def screen(base, color, amount):
    """Lighten like light through a lens (screen blend), by a dithered amount."""
    return tuple(round(c + (255 - c) * (t / 255) * amount) for c, t in zip(base, color))


def dithered(x, y, amount, steps=8):
    """Snap a 0..1 amount to a few flat steps, dithered, so the glow stays pixel art."""
    level = int(amount * steps + (BAYER[y % 4][x % 4] - 7.5) / 16)
    return max(0, min(steps, level)) / steps


def draw_bloom(px, theta):
    """The glare around the light source; drawn behind the palms so swaying fronds
    pass in front of it."""
    pulse = 1 + 0.07 * math.sin(theta)
    for y in range(H):
        for x in range(W):
            d = math.hypot(x - FLARE_X, y - FLARE_Y)
            glow = 0.4 * math.exp(-((d / (40 * pulse)) ** 2)) + 0.22 * math.exp(-d / (110 * pulse))
            glow += 0.35 * math.exp(-((d / 8) ** 2))
            a = dithered(x, y, min(1.0, glow), steps=16)
            if a:
                px[x, y] = screen(px[x, y], FLARE, a)


def draw_sun(px):
    """The white disc, fading out through a rose-red rim (the sun's outline). Drawn between
    the right palm's back and front leaves, so the dark front fronds pass over it."""
    r = int(SUN_R + 5)
    for y in range(max(0, FLARE_Y - r), min(H, FLARE_Y + r + 1)):
        for x in range(max(0, FLARE_X - r), min(W, FLARE_X + r + 1)):
            d = math.hypot(x - FLARE_X, y - FLARE_Y)
            disc = 1.0 if d <= SUN_R else math.exp(-(((d - SUN_R) / 1.6) ** 2))
            a = dithered(x, y, disc, steps=16)
            if a:
                px[x, y] = screen(px[x, y], SPARK if disc > 0.6 else ROSE, a)


def draw_flare(px, clear):
    """The sun's long horizontal streak and a soft glare over nearby leaves, over
    everything. `clear` (0..1) is how open the gap in the leaves is: they shine when it
    opens and fade as it closes. Faint parts take the rose rim colour, bright parts white."""
    # Off while the gap is nearly closed, full strength once it is a bit under half open.
    t = max(0.0, min(1.0, (clear - 0.1) / 0.32))
    streak_on = t * t * (3 - 2 * t)
    for y in range(H):
        for x in range(W):
            dx, dy = x - FLARE_X, y - FLARE_Y
            d = math.hypot(dx, dy)
            # The streak holds near full strength for most of the loop, then fades out
            # completely while the leaves cover the sun.
            streak = 0.95 * math.exp(-((dy / 1.3) ** 2)) * math.exp(-abs(dx) / 110)
            core = 0.9 * math.exp(-((d / 4) ** 2))
            glow = core + 0.4 * math.exp(-((d / 13) ** 2))
            light = streak + glow
            a = dithered(x, y, min(1.0, streak * streak_on + glow * clear), steps=16)
            if a:
                color = SPARK if core > 0.5 else FLARE if light > 0.45 else ROSE
                px[x, y] = screen(px[x, y], color, a)


def right_palm_mask(theta):
    """Every pixel the right palm's front leaves cover at this moment of the sway."""
    mask = set()
    scratch = Image.new("RGB", (W, H)).load()
    draw_palm(scratch, RIGHT_CROWN, RIGHT_TRUNK, RIGHT_BACK, RIGHT_FRONT, theta, 20, mask)
    return mask


def coverage(mask, cx, cy, r=SUN_R):
    """How much of the sun's disc is hidden behind leaves (0 = clear, 1 = fully covered)."""
    disc = [(x, y) for x in range(int(cx - r), int(cx + r) + 1)
            for y in range(int(cy - r), int(cy + r) + 1) if math.hypot(x - cx, y - cy) <= r]
    return sum(p in mask for p in disc) / len(disc)


def draw_fade(px):
    for y in range(H - FADE_ROWS, H):
        t = ((y - (H - FADE_ROWS)) / (FADE_ROWS - 1)) ** 1.4
        for x in range(W):
            d = max(0.0, min(1.0, t + (BAYER[y % 4][x % 4] - 7.5) / 48))
            px[x, y] = lerp(px[x, y], DUSK, d)


class Canvas:
    """Plots leaf pixels, fading them toward the sky lower down (haze)."""

    def __init__(self, px, color, haze, mask=None):
        self.px, self.color, self.haze, self.mask = px, color, haze, mask

    def dot(self, x, y, color=None):
        x, y = round(x), round(y)
        if 0 <= x < W and 0 <= y < H:
            if self.mask is not None:
                self.mask.add((x, y))
            color = color or self.color
            fog = self.haze * max(0.0, (y - H * 0.25) / (H * 0.75)) ** 1.3
            self.px[x, y] = lerp(color, self.px[x, y], fog) if fog else color

    def line(self, x0, y0, x1, y1):
        n = max(1, int(max(abs(x1 - x0), abs(y1 - y0)) * 1.5))
        for i in range(n + 1):
            t = i / n
            self.dot(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)


def bezier(p0, p1, p2, t):
    return tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * b + t * t * c for a, b, c in zip(p0, p1, p2))


def draw_leaflet(canvas, x, y, dx, dy, length, gravity):
    """A leaflet that leaves the rib at (dx, dy) and bends downward toward its tip."""
    segs = max(2, int(length / 2))
    step = length / segs
    for k in range(segs):
        bend = gravity * (k + 1) / segs
        vx, vy = dx, dy + bend
        n = math.hypot(vx, vy) or 1
        nx, ny = x + vx / n * step, y + vy / n * step
        canvas.line(x, y, nx, ny)
        x, y = nx, ny


def draw_frond(canvas, crown, ang, length, droop, theta, ph, rnd):
    """A feathery frond: an arching rib with wide, curving leaflets on both sides."""
    kx, ky = crown
    a = math.radians(ang + 3 * math.sin(theta + ph))
    d = droop * (1 + 0.08 * math.sin(theta + ph + 1.3))
    ux, uy = math.cos(a), -math.sin(a)
    steps = int(length * 1.5)
    pts = [
        (kx + ux * length * s, ky + uy * length * s + d * length * s * s)
        for s in (i / steps for i in range(steps + 1))
    ]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        canvas.line(x0, y0, x1, y1)
    # Leaflets: widest a third of the way along, tapering to a point at the tip.
    span = 0.22 * length
    gravity = 0.35 + 0.6 * min(1.0, droop)
    for i in range(2, len(pts) - 1, 2):
        s = i / steps
        x, y = pts[i]
        tx, ty = pts[i + 1][0] - x, pts[i + 1][1] - y
        norm = math.hypot(tx, ty) or 1
        tx, ty = tx / norm, ty / norm
        shape = math.sin(math.pi * min(1.0, s ** 0.75)) ** 0.8
        sway = 0.2 * math.sin(theta + ph + s * 4)
        for side in (-1, 1):
            if rnd.random() < 0.2:
                continue  # gaps keep the frond airy
            # The leaflets under the rib hang longer than the ones on top.
            under = (-ty * side) * 0 + (tx * side)
            leaf = span * shape * (0.65 + 0.4 * rnd.random()) * (1.0 if under > 0 else 0.6)
            if leaf < 1.5:
                continue
            nx, ny = -ty * side, tx * side
            draw_leaflet(canvas, x, y, tx * 0.9 + nx + sway, ty * 0.9 + ny, leaf, gravity)


def droop_for(ang):
    """Fronds pointing up stay stiff; sideways and downward ones arch over."""
    up = math.sin(math.radians(ang))
    return 0.15 + 0.9 * (1 - up) / 2 + 0.2 * max(0.0, -up)


def make_fronds(seed, fronds, scale=1.0):
    """fronds: (angle deg, length) pairs, jittered a little so nothing looks ruled."""
    rnd = random.Random(seed)
    return [(a + rnd.uniform(-5, 5), scale * length * rnd.uniform(0.85, 1.1)) for a, length in fronds]


# Angles: 90 = straight up, 180 = left, 270 = straight down.
LEFT_CROWN = (28, 36)
LEFT_TRUNK = ((-2, H + 6), (16, 60))
LEFT_BACK = make_fronds(1, [(100, 50), (128, 42), (56, 50), (156, 38), (22, 52), (-8, 48), (200, 34)], 0.66)
LEFT_FRONT = make_fronds(2, [(84, 54), (112, 46), (70, 50), (38, 54), (140, 40), (6, 50), (-28, 44)], 0.66)

RIGHT_CROWN = (302, 12)
RIGHT_TRUNK = ((332, H + 6), (314, 48))
RIGHT_BACK = make_fronds(3, [(100, 52), (126, 64), (150, 74), (172, 78), (196, 74), (222, 66),
                             (248, 58), (58, 50), (24, 48)], 0.78)
RIGHT_FRONT = make_fronds(4, [(112, 58), (138, 70), (160, 78), (184, 76), (208, 70), (234, 62),
                              (80, 54), (40, 50), (8, 46)], 0.78)


def draw_trunk(canvas, trunk, crown):
    """A tapering, slightly curved trunk with darker bark rings."""
    (bx, by), ctrl = trunk
    for i in range(160):
        t = i / 159
        x, y = bezier((bx, by), ctrl, crown, t)
        r = 3.2 - 1.6 * t
        ring = int(y) % 4 == 0
        for dx in range(-4, 5):
            if abs(dx) <= r:
                canvas.dot(x + dx, y, TRUNK_RING if ring and abs(dx) < r - 0.5 else None)


def draw_palm(px, crown, trunk, back, front, theta, seed, mask=None, between=None):
    """Back (hazy) fronds, then `between` (e.g. the sun), then trunk and front fronds.
    `mask` collects the front layer's pixels: the leaves that can hide the sun."""
    rnd = random.Random(seed)
    back_canvas = Canvas(px, LEAF_BACK, 0.55)
    front_canvas = Canvas(px, LEAF_FRONT, 0.42, mask)
    for ang, length in back:
        draw_frond(back_canvas, crown, ang, length, droop_for(ang), theta, rnd.uniform(0, 6.3), rnd)
    if between:
        between()
    draw_trunk(front_canvas, trunk, crown)
    for ang, length in front:
        draw_frond(front_canvas, crown, ang, length, droop_for(ang), theta, rnd.uniform(0, 6.3), rnd)


_OPENNESS = None


def openness(f):
    """0 when the leaves cover the sun the most over the loop, 1 when they cover it least."""
    global _OPENNESS
    if _OPENNESS is None:
        raw = [coverage(right_palm_mask(2 * math.pi * k / FRAMES), FLARE_X, FLARE_Y) for k in range(FRAMES)]
        # Smooth over neighbouring frames so the glow eases in and out instead of jumping
        # each time a single leaf pixel crosses the sun.
        weights = [math.exp(-((k / 3.5) ** 2)) for k in range(-8, 9)]
        c = [sum(w * raw[(i + k - 8) % FRAMES] for k, w in enumerate(weights)) / sum(weights)
             for i in range(FRAMES)]
        lo, hi = min(c), max(c)
        _OPENNESS = [((hi - v) / (hi - lo)) ** 1.3 if hi > lo else 1.0 for v in c]
    return _OPENNESS[f]


def frame(f):
    theta = 2 * math.pi * f / FRAMES
    img = Image.new("RGB", (W, H))
    px = img.load()
    clear = openness(f)
    draw_sky(px)
    draw_bloom(px, theta)
    draw_palm(px, LEFT_CROWN, LEFT_TRUNK, LEFT_BACK, LEFT_FRONT, theta, 10)
    draw_palm(px, RIGHT_CROWN, RIGHT_TRUNK, RIGHT_BACK, RIGHT_FRONT, theta, 20,
              between=lambda: draw_sun(px))
    draw_flare(px, clear)
    draw_fade(px)
    return img


def main():
    frames = [frame(f).resize((W * SCALE, H * SCALE), Image.NEAREST) for f in range(FRAMES)]
    # One shared palette so colours never shift between frames.
    # The sun's few white pixels would lose their palette slot to the sky, so the area
    # around it is repeated in the sample to give its colours more weight.
    fw, fh = W * SCALE, H * SCALE
    sun = (int((FLARE_X - 30) * SCALE), 0, int((FLARE_X + 30) * SCALE), int((FLARE_Y + 10) * SCALE))
    sw, sh = sun[2] - sun[0], sun[3] - sun[1]
    sample = Image.new("RGB", (fw, fh * 6 + sh * 6))
    for i, f in enumerate(range(0, FRAMES, FRAMES // 6)):
        sample.paste(frames[f], (0, fh * i))
    for i in range(6):
        for j in range(fw // sw):
            sample.paste(frames[0].crop(sun), (j * sw, fh * 6 + sh * i))
    palette = sample.quantize(colors=CLEAR, dither=Image.Dither.NONE)
    out, prev = [], None
    for fr in frames:
        cur = list(fr.quantize(palette=palette, dither=Image.Dither.NONE).getdata())
        # Later frames only carry pixels that changed; the rest are see-through.
        data = cur if prev is None else [c if c != p else CLEAR for c, p in zip(cur, prev)]
        prev = cur
        img = Image.new("P", fr.size)
        img.putpalette(palette.getpalette()[: CLEAR * 3] + [0, 0, 0] * (256 - CLEAR))
        img.putdata(data)
        out.append(img)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out[0].save(
        OUT, save_all=True, append_images=out[1:], duration=FRAME_MS, loop=0,
        transparency=CLEAR, disposal=1, optimize=False,
    )
    print(f"{OUT} {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
