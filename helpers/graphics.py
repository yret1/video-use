"""Brand-styled motion graphics → transparent full-frame overlays.

Creator-style graphics in the channel brand (bold type, ink strokes, tilt,
translucent gray panels, marker scribbles, overshoot pops). Rendered frame by frame
with PIL and encoded as alpha WebM (VP9) to drop into an EDL `overlays`
entry at full frame. Every template also writes `<out>.cues.json`: suggested
SFX hits (relative seconds) to add to the EDL `sfx` list at
start_in_output + at.

Usage:
    python helpers/graphics.py spec.json -o edit/gfx/title.webm
    python helpers/graphics.py spec.json -o frame.png --still 0.6      # one frame, for checking
    python helpers/graphics.py batch.json                               # {"graphics": [{..., "out": "..."}]}
    python helpers/graphics.py --list                                   # templates + parameters

Common spec keys: template, duration (s), pos [x, y] (fractions of the
canvas, or pixels if > 1), tilt (deg), exit ("pop" | "cut").
Global flags: --brand <brand.json> (default: <videos_dir>/assets/brand.json
when found next to the spec, else video-use/assets/brand.json),
--size 1920x1080 (use 1080x1920 for Shorts), --fps 24.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parent.parent
FONTS_DIR = REPO / "assets" / "fonts"
DEFAULT_BRAND = REPO / "assets" / "brand.json"
SS = 2  # supersampling factor for sprites and strokes

# -------- Easing ---------------------------------------------------------------


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def ease_out_cubic(p: float) -> float:
    p = clamp01(p)
    return 1 - (1 - p) ** 3


def ease_out_back(p: float, s: float = 1.70158) -> float:
    p = clamp01(p)
    return 1 + (s + 1) * (p - 1) ** 3 + s * (p - 1) ** 2


def ease_in_back(p: float, s: float = 1.70158) -> float:
    p = clamp01(p)
    return (s + 1) * p ** 3 - s * p ** 2


# -------- Brand ----------------------------------------------------------------


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_brand(path: Path | None) -> dict:
    brand = json.loads(DEFAULT_BRAND.read_text())
    search = [FONTS_DIR]
    if path:
        brand = _merge(brand, json.loads(path.read_text()))
        search = [path.parent, path.parent / "fonts"] + search
    paths = {}
    for role, name in brand["fonts"].items():
        found = next((d / name for d in search if (d / name).exists()), None)
        if not found:
            sys.exit(f"brand font {role}={name!r} not found in {[str(d) for d in search]}")
        paths[role] = str(found)
    brand["_font_paths"] = paths
    return brand


def hex_rgba(h: str, a: int = 255) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a


@lru_cache(maxsize=256)
def _font(path: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, max(1, px))


class Ctx:
    def __init__(self, brand: dict, w: int, h: int, fps: int):
        self.brand, self.w, self.h, self.fps = brand, w, h, fps
        self.u = min(w, h)
        self.portrait = h > w
        self.c = {k: hex_rgba(v) for k, v in brand["colors"].items()}
        self.stroke = max(2, round(brand["stroke"] * self.u))
        self.shadow = (round(brand["shadow"][0] * self.u), round(brand["shadow"][1] * self.u))

    def font(self, role: str, px: float) -> ImageFont.FreeTypeFont:
        return _font(self.brand["_font_paths"][role], int(px))

    def color(self, name_or_hex: str) -> tuple[int, int, int, int]:
        return self.c[name_or_hex] if name_or_hex in self.c else hex_rgba(name_or_hex)

    def pos(self, spec: dict, key: str, default: tuple[float, float]) -> tuple[float, float]:
        x, y = spec.get(key, default)
        return (x * self.w if x <= 1 else x), (y * self.h if y <= 1 else y)

    def frames(self, t: float) -> float:
        return t * self.fps


# -------- Drawing primitives --------------------------------------------------


def composite(canvas: Image.Image, im: Image.Image, x: int, y: int) -> None:
    """alpha_composite that tolerates sprites hanging off the canvas."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.width, x + im.width), min(canvas.height, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    canvas.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def place(canvas: Image.Image, sprite: Image.Image, cx: float, cy: float,
          scale: float = 1.0, angle: float = 0.0, alpha: float = 1.0) -> None:
    """Draw an SS-resolution sprite centred at (cx, cy), scaled, rotated (deg, CCW)."""
    if scale <= 0.01 or alpha <= 0.01:
        return
    w = max(1, round(sprite.width * scale / SS))
    h = max(1, round(sprite.height * scale / SS))
    im = sprite.resize((w, h), Image.LANCZOS)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    composite(canvas, im, round(cx - im.width / 2), round(cy - im.height / 2))


EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def strip_unsupported(text: str) -> str:
    """Brand fonts have no emoji glyphs (they'd render as empty boxes): drop them."""
    cleaned = EMOJI.sub("", text)
    if cleaned == text:
        return text
    print(f"  note: removed emoji from {text!r} (brand fonts have no emoji)")
    return re.sub(r" {2,}", " ", cleaned).rstrip()


def text_sprite(ctx: Ctx, runs: list[tuple[str, tuple]], role: str, size: float,
                stroke: int | None = None, shadow: bool = True) -> Image.Image:
    """Single line of coloured runs, ink stroke + hard ink shadow, at SS resolution."""
    runs = [(strip_unsupported(t), c) for t, c in runs]
    f = ctx.font(role, size * SS)
    sw = (ctx.stroke if stroke is None else stroke) * SS
    sx, sy = (ctx.shadow[0] * SS, ctx.shadow[1] * SS) if shadow else (0, 0)
    widths = [f.getlength(t) for t, _ in runs]
    asc, desc = f.getmetrics()
    pad = sw + int(size * SS * 0.18)  # italic overhang + stroke
    img = Image.new("RGBA", (int(sum(widths) + 2 * pad + sx), int(asc + desc + 2 * pad + sy)))
    d = ImageDraw.Draw(img)
    ink = ctx.c["ink"]
    if shadow:
        x = pad
        for (t, _), wd in zip(runs, widths):
            d.text((x + sx, pad + sy), t, font=f, fill=ink, stroke_width=sw, stroke_fill=ink)
            x += wd
    x = pad
    for (t, col), wd in zip(runs, widths):
        d.text((x, pad), t, font=f, fill=col, stroke_width=sw, stroke_fill=ink)
        x += wd
    return img.crop(img.getbbox() or (0, 0, 1, 1))


def stack(sprites: list[Image.Image], gap: float = 0.0) -> Image.Image:
    w = max(s.width for s in sprites)
    h = int(sum(s.height for s in sprites) + gap * (len(sprites) - 1))
    out = Image.new("RGBA", (w, h))
    y = 0
    for s in sprites:
        out.alpha_composite(s, ((w - s.width) // 2, int(y)))
        y += s.height + gap
    return out


def word_runs(text: str, highlight: list[str], base: tuple, hi: tuple,
              numbers: bool = True) -> list[tuple[str, tuple]]:
    keys = {re.sub(r"[^\w%]", "", w).upper() for w in highlight}
    words = text.split(" ")
    runs = []
    for i, w in enumerate(words):
        key = re.sub(r"[^\w%]", "", w).upper()
        is_hi = key in keys or (numbers and bool(re.search(r"\d", w)))
        runs.append((w + (" " if i < len(words) - 1 else ""), hi if is_hi else base))
    return runs


def text_block(ctx: Ctx, text: str, role: str, size: float, highlight: list[str],
               base: tuple, hi: tuple, upper: bool = False) -> Image.Image:
    lines = (text.upper() if upper else text).split("\n")
    sprites = [text_sprite(ctx, word_runs(line, highlight, base, hi), role, size) for line in lines]
    return stack(sprites, gap=-ctx.stroke * SS)


def pop_env(ctx: Ctx, t: float, dur: float, start: float = 0.0, exit: str = "pop",
            in_frames: int = 7, out_frames: int = 4) -> float:
    """Scale envelope: ease-out-back in, ease-in-back out (anticipation then gone)."""
    if t < start:
        return 0.0
    s = ease_out_back((t - start) / (in_frames / ctx.fps))
    fout = out_frames / ctx.fps
    if exit == "pop" and t > dur - fout:
        s *= 1 - ease_in_back((t - (dur - fout)) / fout)
    return max(0.0, s)


def wobble(t: float, amp: float = 1.0, period: float = 2.6, phase: float = 0.0) -> float:
    return amp * math.sin(2 * math.pi * t / period + phase)


def shake(ctx: Ctx, t: float, t0: float, frames: int = 4, amp: float = 0.008) -> tuple[float, float]:
    d = frames / ctx.fps
    if not t0 <= t < t0 + d:
        return 0.0, 0.0
    k = (1 - (t - t0) / d) * amp * ctx.u
    n = ctx.frames(t)
    return k * math.sin(n * 2.7), k * math.cos(n * 3.9)


def panel_fill(ctx: Ctx) -> tuple[int, int, int, int]:
    return ctx.c["panel"][:3] + (int(255 * ctx.brand.get("panel_alpha", 0.62)),)


def panel(ctx: Ctx, w: int, h: int, accent: bool = True) -> tuple[Image.Image, tuple[int, int]]:
    """Translucent gray rounded panel with a blue accent edge, at SS.
    Returns (sprite, (x, y) of the panel's top-left inside the sprite)."""
    margin = int(0.01 * ctx.u * SS)
    img = Image.new("RGBA", (w + 2 * margin, h + 2 * margin))
    d = ImageDraw.Draw(img)
    r = int(0.012 * ctx.u * SS)
    d.rounded_rectangle((margin, margin, margin + w, margin + h), r, fill=panel_fill(ctx))
    if accent:
        bar = max(4, int(0.008 * ctx.u * SS))
        mask = Image.new("L", img.size)
        ImageDraw.Draw(mask).rounded_rectangle((margin, margin, margin + w, margin + h), r, fill=255)
        edge = Image.new("RGBA", img.size)
        ImageDraw.Draw(edge).rectangle((margin, margin, margin + bar, margin + h), fill=ctx.c["accent_1"])
        edge.putalpha(Image.composite(edge.getchannel("A"), Image.new("L", img.size), mask))
        img.alpha_composite(edge)
    return img, (margin, margin)


def fmt_number(v: float, decimals: int = 0) -> str:
    return f"{v:,.{decimals}f}"


# -------- Templates ------------------------------------------------------------
#
# Each template takes (ctx, spec) and returns (render(t, canvas), duration, cues).


def tpl_popup(ctx: Ctx, s: dict):
    """Pop-up text (sarcasm, inner thoughts, contradictions).
    text (\\n for lines), highlight [words], size 0.075, font body, color white,
    pos [0.5, 0.78], tilt brand, duration 2.0, exit pop|cut."""
    dur = float(s.get("duration", 2.0))
    sprite = text_block(ctx, s["text"], s.get("font", "body"), s.get("size", 0.075) * ctx.u,
                        s.get("highlight", []), ctx.color(s.get("color", "white")), ctx.c["accent_1"],
                        upper=s.get("upper", False))
    # Portrait: above the captions (which sit ~30% up) and clear of the Shorts UI.
    cx, cy = ctx.pos(s, "pos", (0.5, 0.55 if ctx.portrait else 0.78))
    tilt = float(s.get("tilt", ctx.brand["tilt"]))

    def render(t, canvas):
        place(canvas, sprite, cx, cy, pop_env(ctx, t, dur, exit=s.get("exit", "pop")), tilt + wobble(t))

    return render, dur, [{"at": 0.0, "sfx": "pop"}]


def tpl_title(ctx: Ctx, s: dict):
    """Chapter title slam: words slam in one by one, group shakes on each landing.
    text, highlight [words], size 0.16, font display, stagger 0.12, band true,
    pos [0.5, 0.5], tilt -3, duration 1.8."""
    dur = float(s.get("duration", 1.8))
    size = s.get("size", 0.16) * ctx.u
    stagger = float(s.get("stagger", 0.12))
    slam_frames = 5
    words = s["text"].upper().split()
    hl = {re.sub(r"[^\w%]", "", w).upper() for w in s.get("highlight", [])}
    sprites = [
        text_sprite(ctx, [(w, ctx.c["accent_1"] if re.sub(r"[^\w%]", "", w) in hl or re.search(r"\d", w)
                           else ctx.c["white"])], s.get("font", "display"), size)
        for w in words
    ]
    # Wrap into lines no wider than 86% of the canvas.
    space = 0.22 * size
    max_w = 0.86 * ctx.w
    lines, cur, cur_w = [], [], 0.0
    for i, sp in enumerate(sprites):
        w = sp.width / SS
        if cur and cur_w + space + w > max_w:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append(i)
        cur_w += (space if len(cur) > 1 else 0) + w
    lines.append(cur)
    line_h = max(sp.height for sp in sprites) / SS * 1.05
    cx, cy = ctx.pos(s, "pos", (0.5, 0.5))
    tilt = float(s.get("tilt", -3))
    layout = {}
    top = cy - line_h * len(lines) / 2 + line_h / 2
    block_w = 0.0
    for li, line in enumerate(lines):
        widths = [sprites[i].width / SS for i in line]
        total = sum(widths) + space * (len(line) - 1)
        block_w = max(block_w, total)
        x = cx - total / 2
        for i, w in zip(line, widths):
            layout[i] = (x + w / 2, top + li * line_h)
            x += w + space
    rad = math.radians(tilt)
    land = [i * stagger + slam_frames / ctx.fps for i in range(len(words))]

    band = None
    if s.get("band", True):
        bw, bh = int((block_w + 0.12 * ctx.u) * SS), int((line_h * len(lines) + 0.06 * ctx.u) * SS)
        band, _ = panel(ctx, bw, bh)

    def render(t, canvas):
        exit_s = pop_env(ctx, t, dur, exit=s.get("exit", "pop"), in_frames=1)
        dx = dy = 0.0
        for t0 in land:
            ox, oy = shake(ctx, t, t0)
            dx, dy = dx + ox, dy + oy
        if band is not None:
            grow = ease_out_cubic(t / (6 / ctx.fps))
            if grow > 0:
                b = band.resize((max(1, int(band.width * grow)), band.height))
                place(canvas, b, cx + dx, cy + dy, exit_s, tilt)
        for i, sp in enumerate(sprites):
            p = (t - i * stagger) / (slam_frames / ctx.fps)
            if p < 0:
                continue
            slam = 1 + 0.9 * (1 - ease_out_back(p))
            # Rotate each word's position around the block centre so the line tilts with the band.
            x, y = layout[i]
            rx = cx + (x - cx) * math.cos(rad) + (y - cy) * math.sin(rad)
            ry = cy - (x - cx) * math.sin(rad) + (y - cy) * math.cos(rad)
            place(canvas, sp, rx + dx, ry + dy, slam * exit_s, tilt, alpha=clamp01(p * 3))

    cues = [{"at": round(t0, 3), "sfx": "slam"} for t0 in land]
    return render, dur, cues


def tpl_counter(ctx: Ctx, s: dict):
    """Macro / calorie HUD card: translucent panel, number counts up, bounce + ding on landing.
    label "KCAL", from 0, to, count_at 0.25, count_dur 0.9, target (number turns warn-red above it),
    sub "P 98g · C 140g · F 40g", decimals 0, pos [0.04, 0.06] (top-left of card),
    tilt 0, duration 3.0."""
    dur = float(s.get("duration", 3.0))
    v0, v1 = float(s.get("from", 0)), float(s["to"])
    at, cd = float(s.get("count_at", 0.25)), float(s.get("count_dur", 0.9))
    dec = int(s.get("decimals", 0))
    target = s.get("target")
    white, warn = ctx.c["white"], ctx.c["warn"]
    u = ctx.u
    label = text_sprite(ctx, [(s.get("label", "KCAL"), ctx.c["accent_3"])], "heavy", 0.034 * u,
                        stroke=0, shadow=False)
    sub = (text_sprite(ctx, [(s["sub"], white)], "light", 0.03 * u, stroke=0, shadow=False)
           if s.get("sub") else None)

    @lru_cache(maxsize=512)
    def number(txt: str, over: bool) -> Image.Image:
        return text_sprite(ctx, [(txt, warn if over else white)], "display", 0.1 * u, stroke=0, shadow=False)

    widest = number(fmt_number(max(abs(v0), abs(v1)), dec) + "0", False)
    pad = int(0.025 * u * SS)
    cw = max(label.width, widest.width, sub.width if sub else 0) + 3 * pad
    ch = label.height + widest.height + (sub.height if sub else 0) + 3 * pad
    card, (mx, my) = panel(ctx, cw, ch)
    mx += pad // 2  # clear the accent edge
    x0, y0 = ctx.pos(s, "pos", (0.05, 0.13) if ctx.portrait else (0.04, 0.06))  # below the Shorts top UI
    cx, cy = x0 + card.width / SS / 2, y0 + card.height / SS / 2
    tilt = float(s.get("tilt", 0))
    end = at + cd

    def render(t, canvas):
        p = ease_out_cubic((t - at) / cd) if cd > 0 else 1.0
        v = v0 + (v1 - v0) * p
        over = target is not None and v > float(target)
        frame = card.copy()
        frame.alpha_composite(label, (mx + pad, my + pad))
        num = number(fmt_number(v, dec), over)
        k = (t - end) / (6 / ctx.fps)
        bounce = 1 + 0.22 * math.sin(math.pi * clamp01(k)) if k >= 0 else 1.0
        if bounce != 1.0:
            num = num.resize((int(num.width * bounce), int(num.height * bounce)), Image.LANCZOS)
        ny = my + 2 * pad + label.height
        frame.alpha_composite(num, (mx + pad, max(0, ny - (num.height - widest.height) // 2)))
        if sub:
            frame.alpha_composite(sub, (mx + pad, my + 3 * pad + label.height + widest.height - pad))
        place(canvas, frame, cx, cy, pop_env(ctx, t, dur, exit=s.get("exit", "pop")), tilt + wobble(t, 0.6))

    return render, dur, [{"at": 0.0, "sfx": "pop"}, {"at": round(at, 3), "sfx": "tick"},
                         {"at": round(end, 3), "sfx": "ding"}]


def tpl_stamp(ctx: Ctx, s: dict):
    """Day / time stamp, thuds in.
    text "DAY 3", sub "7:42 AM", size 0.13, pos [0.2, 0.2], tilt -6, duration 2.0."""
    dur = float(s.get("duration", 2.0))
    parts = [text_sprite(ctx, [(s.get("text", "DAY 1").upper(), ctx.c["white"])], "display",
                         s.get("size", 0.13) * ctx.u)]
    if s.get("sub"):
        parts.append(text_sprite(ctx, [(s["sub"], ctx.c["accent_1"])], "body", 0.045 * ctx.u))
    sprite = stack(parts, gap=ctx.stroke * SS)
    cx, cy = ctx.pos(s, "pos", (0.2, 0.2))
    tilt = float(s.get("tilt", -6))
    land = 4 / ctx.fps

    def render(t, canvas):
        sc = 1.6 - 0.6 * ease_out_cubic(t / land)
        if s.get("exit", "pop") == "pop":
            sc *= pop_env(ctx, t, dur, in_frames=1)
        dx, dy = shake(ctx, t, land, frames=4, amp=0.01)
        place(canvas, sprite, cx + dx, cy + dy, sc, tilt, alpha=clamp01(t / land * 2))

    return render, dur, [{"at": round(land, 3), "sfx": "thud"}]


def _marker_layer(ctx: Ctx, polylines: list[list[tuple[float, float]]], color: tuple, width: float):
    """Draw marker polylines at SS on a bbox-sized layer. Returns (image, x, y) at 1×."""
    pts = [p for line in polylines for p in line]
    if not pts:
        return None
    m = width * 2
    x0, y0 = min(p[0] for p in pts) - m, min(p[1] for p in pts) - m
    x1, y1 = max(p[0] for p in pts) + m, max(p[1] for p in pts) + m
    layer = Image.new("RGBA", (max(1, int((x1 - x0) * SS)), max(1, int((y1 - y0) * SS))))
    d = ImageDraw.Draw(layer)
    w = max(1, int(width * SS))
    hi = tuple(min(255, c + 60) for c in color[:3]) + (140,)
    for line in polylines:
        if len(line) < 2:
            continue
        sp = [((x - x0) * SS, (y - y0) * SS) for x, y in line]
        # Ink shadow, then marker body, then a lighter streak for the felt-tip texture.
        sh = [(x + ctx.shadow[0] * SS * 0.6, y + ctx.shadow[1] * SS * 0.6) for x, y in sp]
        d.line(sh, fill=ctx.c["ink"], width=w, joint="curve")
        d.line(sp, fill=color, width=w, joint="curve")
        d.line([(x - w * 0.15, y - w * 0.15) for x, y in sp], fill=hi, width=max(1, w // 4), joint="curve")
        for (x, y) in (sp[0], sp[-1]):
            d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=color)
    small = layer.resize((max(1, int(layer.width / SS)), max(1, int(layer.height / SS))), Image.LANCZOS)
    return small, int(x0), int(y0)


def _label(ctx: Ctx, s: dict) -> Image.Image | None:
    if not s.get("label"):
        return None
    return text_sprite(ctx, [(s["label"], ctx.color(s.get("label_color", "white")))], "hand",
                       s.get("label_size", 0.06) * ctx.u)


def tpl_arrow(ctx: Ctx, s: dict):
    """Hand-drawn marker arrow that draws on, with an optional marker note at its tail.
    from [x, y], to [x, y], bend 0.25, color accent_2, width 0.014, draw_at 0, draw_dur 0.3,
    label "HIS FORM", label_color white, boil true, duration 2.0."""
    dur = float(s.get("duration", 2.0))
    ax, ay = ctx.pos(s, "from", (0.3, 0.3))
    bx, by = ctx.pos(s, "to", (0.5, 0.5))
    bend = float(s.get("bend", 0.25))
    color = ctx.color(s.get("color", "accent_2"))
    width = s.get("width", 0.014) * ctx.u
    at, dd = float(s.get("draw_at", 0.0)), float(s.get("draw_dur", 0.3))
    label = _label(ctx, s)
    length = math.hypot(bx - ax, by - ay)
    nx, ny = -(by - ay) / max(length, 1), (bx - ax) / max(length, 1)
    head_len = 0.05 * ctx.u

    def curve(seed: int):
        rng = random.Random(seed)
        j = 0.003 * ctx.u if s.get("boil", True) else 0
        jit = lambda: (rng.uniform(-j, j), rng.uniform(-j, j))  # noqa: E731
        (jax, jay), (jbx, jby), (jcx, jcy) = jit(), jit(), jit()
        cx_ = (ax + bx) / 2 + nx * bend * length + jcx
        cy_ = (ay + by) / 2 + ny * bend * length + jcy
        pts = []
        for i in range(41):
            k = i / 40
            pts.append(((1 - k) ** 2 * (ax + jax) + 2 * (1 - k) * k * cx_ + k ** 2 * (bx + jbx),
                        (1 - k) ** 2 * (ay + jay) + 2 * (1 - k) * k * cy_ + k ** 2 * (by + jby)))
        return pts

    def render(t, canvas):
        if t < at:
            return
        sc = pop_env(ctx, t, dur, exit=s.get("exit", "pop"), in_frames=1)
        if sc <= 0.01:
            return
        p = ease_out_cubic((t - at) / dd)
        pts = curve(int(ctx.frames(t) / 3))
        n = max(2, int(len(pts) * p))
        lines = [pts[:n]]
        hp = clamp01((t - at - dd) / (3 / ctx.fps))
        if hp > 0:
            ex, ey = pts[-1]
            ang = math.atan2(ey - pts[-4][1], ex - pts[-4][0])
            for side in (1, -1):
                a = ang + math.pi - side * math.radians(28)
                lines.append([(ex, ey), (ex + math.cos(a) * head_len * hp, ey + math.sin(a) * head_len * hp)])
        layer = _marker_layer(ctx, lines, color, width * sc)
        if layer:
            composite(canvas, *layer)
        if label is not None:
            lx = ax - (bx - ax) / max(length, 1) * label.width / SS * 0.6
            ly = ay - (by - ay) / max(length, 1) * label.height / SS * 0.9
            place(canvas, label, lx, ly, pop_env(ctx, t, dur, start=at, exit=s.get("exit", "pop")),
                  float(s.get("tilt", 5)) + wobble(t, 0.8))

    return render, dur, [{"at": round(at, 3), "sfx": "marker"}]


def tpl_circle(ctx: Ctx, s: dict):
    """Hand-drawn marker loop around something.
    center [x, y], radius 0.12 (or rx/ry), color accent_2, width 0.012, draw_at 0, draw_dur 0.35,
    label, label_color white, duration 2.0."""
    dur = float(s.get("duration", 2.0))
    cx, cy = ctx.pos(s, "center", (0.5, 0.5))
    r = s.get("radius", 0.12)
    rx, ry = s.get("rx", r) * ctx.u, s.get("ry", r * 0.8) * ctx.u
    color = ctx.color(s.get("color", "accent_2"))
    width = s.get("width", 0.012) * ctx.u
    at, dd = float(s.get("draw_at", 0.0)), float(s.get("draw_dur", 0.35))
    label = _label(ctx, s)

    def loop(seed: int):
        rng = random.Random(seed)
        ph = rng.uniform(0, 2 * math.pi)
        pts = []
        start = math.radians(-110)
        for i in range(73):
            a = start + 2 * math.pi * 1.12 * i / 72
            k = 1 + 0.045 * math.sin(3 * a + ph) + 0.03 * i / 72  # hand-drawn wobble, spirals out slightly
            pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
        return pts

    def render(t, canvas):
        if t < at:
            return
        sc = pop_env(ctx, t, dur, exit=s.get("exit", "pop"), in_frames=1)
        if sc <= 0.01:
            return
        pts = loop(int(ctx.frames(t) / 3))
        n = max(2, int(len(pts) * ease_out_cubic((t - at) / dd)))
        layer = _marker_layer(ctx, [pts[:n]], color, width * sc)
        if layer:
            composite(canvas, *layer)
        if label is not None:
            place(canvas, label, cx + rx * 0.6, cy - ry - label.height / SS * 0.4,
                  pop_env(ctx, t, dur, start=at + dd * 0.6, exit=s.get("exit", "pop")),
                  float(s.get("tilt", -6)) + wobble(t, 0.8))

    return render, dur, [{"at": round(at, 3), "sfx": "marker"}]


def tpl_reveal(ctx: Ctx, s: dict):
    """Result reveal: dims the shot, number counts in huge, lands with a flash + boom.
    to, from 0, prefix "", suffix " KG", label "FINAL WEIGHT", decimals 0,
    count_at 0.3, count_dur 1.2, size 0.3, dim 0.55, duration 3.5."""
    dur = float(s.get("duration", 3.5))
    v0, v1 = float(s.get("from", 0)), float(s["to"])
    at, cd = float(s.get("count_at", 0.3)), float(s.get("count_dur", 1.2))
    dec = int(s.get("decimals", 0))
    size = s.get("size", 0.3) * ctx.u
    label = (text_sprite(ctx, [(s["label"].upper(), ctx.c["white"])], "display", 0.07 * ctx.u)
             if s.get("label") else None)
    cx, cy = ctx.pos(s, "pos", (0.5, 0.52))
    end = at + cd
    dim = float(s.get("dim", 0.55))

    @lru_cache(maxsize=512)
    def number(txt: str) -> Image.Image:
        return text_sprite(ctx, [(txt, ctx.c["accent_1"])], "display", size)

    # Fit the widest (final) value to 90% of the canvas width, once, so the size doesn't jump.
    final = number(f"{s.get('prefix', '')}{fmt_number(max(abs(v0), abs(v1)), dec)}{s.get('suffix', '')}")
    fit = min(1.0, 0.9 * ctx.w * SS / final.width)

    def render(t, canvas):
        fade = ease_out_cubic(t / (6 / ctx.fps))
        if dur - t < 4 / ctx.fps:
            fade *= clamp01((dur - t) / (4 / ctx.fps))
        if dim > 0:
            canvas.alpha_composite(Image.new("RGBA", canvas.size, (0, 0, 0, int(255 * dim * fade))))
        if label is not None:
            place(canvas, label, cx, cy - size * 0.72, pop_env(ctx, t, dur), -2 + wobble(t, 0.6))
        if t >= at:
            v = v0 + (v1 - v0) * ease_out_cubic((t - at) / cd)
            txt = f"{s.get('prefix', '')}{fmt_number(v, dec)}{s.get('suffix', '')}"
            k = (t - end) / (5 / ctx.fps)
            punch = 1.3 - 0.3 * ease_out_cubic(k) if k >= 0 else 1.0
            dx, dy = shake(ctx, t, end, frames=6, amp=0.014)
            place(canvas, number(txt), cx + dx, cy + dy, fit * punch * pop_env(ctx, t, dur, start=at), -2)
        fk = (t - end) / (7 / ctx.fps)
        if 0 <= fk <= 1:
            canvas.alpha_composite(Image.new("RGBA", canvas.size, (255, 255, 255, int(230 * (1 - fk)))))

    return render, dur, [{"at": round(at, 3), "sfx": "tick"}, {"at": round(end, 3), "sfx": "boom"}]


def tpl_progress(ctx: Ctx, s: dict):
    """Chunky segmented challenge progress bar; the newest segment fills with a bump.
    segments 5, filled 3, fill_at 0.3, start_label "DAY 1", end_label "DAY 5",
    width 0.55 of canvas width (0.8 in portrait), pos [0.5, 0.82], tilt -2, duration 2.5."""
    dur = float(s.get("duration", 2.5))
    n, filled = int(s.get("segments", 5)), int(s.get("filled", 1))
    fill_at = float(s.get("fill_at", 0.3))
    portrait = ctx.h > ctx.w
    bw = s.get("width", 0.8 if portrait else 0.55) * ctx.w * SS
    bh = 0.055 * ctx.u * SS
    gap = 0.014 * ctx.u * SS
    seg_w = (bw - gap * (n - 1)) / n
    r = int(0.012 * ctx.u * SS)
    ol = max(2, int(0.005 * ctx.u * SS))
    sx, sy = ctx.shadow[0] * SS, ctx.shadow[1] * SS
    labels = [text_sprite(ctx, [(s[k].upper(), ctx.c["white"])], "display", 0.045 * ctx.u)
              if s.get(k) else None for k in ("start_label", "end_label")]
    lab_h = max([lb.height for lb in labels if lb] or [0])
    W, H = int(bw + sx + 2 * ol + 4), int(bh + sy + 2 * ol + lab_h + 4)
    cx, cy = ctx.pos(s, "pos", (0.5, 0.62) if ctx.portrait else (0.5, 0.82))  # above captions + Shorts UI

    def bar(t):
        img = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(img)
        p = ease_out_cubic((t - fill_at) / 0.3)
        for i in range(n):
            x = ol + i * (seg_w + gap)
            box = (x, ol, x + seg_w, ol + bh)
            d.rounded_rectangle((box[0] + sx, box[1] + sy, box[2] + sx, box[3] + sy), r, fill=ctx.c["ink"])
            d.rounded_rectangle(box, r, fill=panel_fill(ctx), outline=ctx.c["white"], width=ol)
            frac = 1.0 if i < filled - 1 else (p if i == filled - 1 else 0.0)
            if frac > 0:
                d.rounded_rectangle((x, ol, x + max(2 * r, seg_w * frac), ol + bh), r,
                                    fill=ctx.c["accent_1"], outline=ctx.c["ink"], width=ol)
        if labels[0]:
            img.alpha_composite(labels[0], (0, int(ol + bh + sy)))
        if labels[1]:
            img.alpha_composite(labels[1], (W - labels[1].width, int(ol + bh + sy)))
        return img

    land = fill_at + 0.3

    def render(t, canvas):
        k = (t - land) / (6 / ctx.fps)
        bump = 1 + 0.06 * math.sin(math.pi * clamp01(k)) if k >= 0 else 1.0
        place(canvas, bar(t), cx, cy, bump * pop_env(ctx, t, dur, exit=s.get("exit", "pop")),
              float(s.get("tilt", -2)))

    return render, dur, [{"at": 0.0, "sfx": "pop"}, {"at": round(land, 3), "sfx": "ding"}]


def tpl_sticker(ctx: Ctx, s: dict):
    """Cut-out sticker with thick white border + hard shadow, pops in and wobbles.
    image (path), cutout false (true = remove background with rembg), height 0.45,
    border 0.012, pos [0.75, 0.55], tilt brand, duration 2.0."""
    dur = float(s.get("duration", 2.0))
    src = Image.open(s["image"]).convert("RGBA")
    if s.get("cutout"):
        from rembg import remove  # lazy: downloads a model on first use
        src = remove(src)
    src = src.crop(src.getbbox() or (0, 0, src.width, src.height))
    th = int(s.get("height", 0.45) * ctx.u * SS)
    src = src.resize((max(1, int(src.width * th / src.height)), th), Image.LANCZOS)
    b = max(2, int(s.get("border", 0.012) * ctx.u * SS))
    pad = b * 2 + max(ctx.shadow) * SS
    alpha = Image.new("L", (src.width + 2 * pad, src.height + 2 * pad))
    alpha.paste(src.getchannel("A"), (pad, pad))
    outline = alpha.filter(ImageFilter.MaxFilter(b * 2 + 1)).point(lambda v: 255 if v > 40 else 0)
    img = Image.new("RGBA", alpha.size)
    sh = Image.new("RGBA", alpha.size, ctx.c["ink"])
    sh.putalpha(outline)
    img.alpha_composite(sh, (ctx.shadow[0] * SS, ctx.shadow[1] * SS))
    white = Image.new("RGBA", alpha.size, ctx.c["white"])
    white.putalpha(outline)
    img.alpha_composite(white)
    img.alpha_composite(src, (pad, pad))
    cx, cy = ctx.pos(s, "pos", (0.75, 0.55))
    tilt = float(s.get("tilt", ctx.brand["tilt"]))

    def render(t, canvas):
        place(canvas, img, cx, cy, pop_env(ctx, t, dur, exit=s.get("exit", "pop")), tilt + wobble(t, 1.5))

    return render, dur, [{"at": 0.0, "sfx": "pop"}]


TEMPLATES = {
    "popup": tpl_popup,
    "title": tpl_title,
    "counter": tpl_counter,
    "stamp": tpl_stamp,
    "arrow": tpl_arrow,
    "circle": tpl_circle,
    "reveal": tpl_reveal,
    "progress": tpl_progress,
    "sticker": tpl_sticker,
}


# -------- Rendering --------------------------------------------------------------


def render_graphic(ctx: Ctx, spec: dict, out: Path, still: float | None = None,
                   bg: Path | None = None) -> None:
    kind = spec.get("template")
    if kind not in TEMPLATES:
        sys.exit(f"unknown template {kind!r} (known: {', '.join(TEMPLATES)})")
    render, dur, cues = TEMPLATES[kind](ctx, spec)
    out.parent.mkdir(parents=True, exist_ok=True)

    if still is not None:
        canvas = Image.new("RGBA", (ctx.w, ctx.h))
        render(still, canvas)
        base = (Image.open(bg).convert("RGBA").resize(canvas.size) if bg
                else Image.new("RGBA", canvas.size, (90, 90, 90, 255)))
        base.alpha_composite(canvas)
        base.save(out)
        print(f"{kind} @ {still}s → {out}")
        return

    if out.suffix.lower() == ".mov":
        codec = ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le"]
    else:
        codec = ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "26",
                 "-deadline", "good", "-cpu-used", "5", "-row-mt", "1"]
    cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{ctx.w}x{ctx.h}", "-r", str(ctx.fps), "-i", "-",
           *codec, str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = max(1, round(dur * ctx.fps))
    for i in range(n):
        canvas = Image.new("RGBA", (ctx.w, ctx.h))
        render(i / ctx.fps, canvas)
        proc.stdin.write(canvas.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit(f"ffmpeg failed encoding {out}")
    cues_path = out.with_suffix(".cues.json")
    cues_path.write_text(json.dumps({"duration": n / ctx.fps, "cues": cues}, indent=2))
    print(f"{kind} ({n / ctx.fps:.2f}s) → {out}  cues: {', '.join(c['sfx'] + '@' + str(c['at']) for c in cues)}")


def find_brand(spec_path: Path | None) -> Path | None:
    """<videos_dir>/assets/brand.json if the spec lives somewhere under a videos dir."""
    if spec_path is None:
        return None
    for d in [spec_path.parent, *spec_path.parents]:
        cand = d / "assets" / "brand.json"
        if cand.exists() and cand.resolve() != DEFAULT_BRAND.resolve():
            return cand
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Render brand-styled motion graphics as alpha overlays")
    ap.add_argument("spec", type=Path, nargs="?", help="Graphic spec JSON (or {\"graphics\": [...]})")
    ap.add_argument("-o", "--output", type=Path, help="Output .webm/.mov (or .png with --still)")
    ap.add_argument("--still", type=float, default=None, help="Render one frame at this time to PNG")
    ap.add_argument("--bg", type=Path, default=None, help="Background image for --still (e.g. a frame of the shot)")
    ap.add_argument("--brand", type=Path, default=None)
    ap.add_argument("--size", default="1920x1080")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--list", action="store_true", help="List templates and their parameters")
    args = ap.parse_args()

    if args.list:
        for name, fn in TEMPLATES.items():
            print(f"{name}:\n  " + "\n  ".join(line.strip() for line in fn.__doc__.strip().splitlines()) + "\n")
        return
    if not args.spec:
        ap.error("spec is required")

    spec_path = args.spec.resolve()
    brand = load_brand(args.brand or find_brand(spec_path))
    w, h = (int(v) for v in args.size.lower().split("x"))
    ctx = Ctx(brand, w, h, args.fps)
    data = json.loads(spec_path.read_text())

    if "graphics" in data:
        for g in data["graphics"]:
            out = Path(g["out"])
            render_graphic(ctx, g, out if out.is_absolute() else spec_path.parent / out, args.still, args.bg)
    else:
        if not args.output:
            ap.error("-o/--output is required for a single spec")
        render_graphic(ctx, data, args.output.resolve(), args.still, args.bg)


if __name__ == "__main__":
    main()
