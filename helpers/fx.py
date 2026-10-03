"""Per-segment effects (EDL range `fx`), applied during extraction.

Effects are baked into each segment when it's extracted, so the lossless
`-c copy` concat (Hard Rule 2) still holds. Every `at` / `until` is in seconds
relative to the range start, measured in SOURCE time (before any freeze or
speed change).

Supported effects:

  punch_in   {"scale": 1.15, "anchor": [0.5, 0.4], "at"?: s, "until"?: s}
             Static zoom. Whole range unless `at`/`until` limit it.
  crash_zoom {"at": s, "to": 1.6, "frames": 5, "until"?: s, "anchor"?: [x, y]}
             Ease-out ramp from 1.0 to `to` over `frames`, holds until
             `until` (or the range end), then snaps back.
  shake      {"at": s, "frames": 5, "amp": 12}
             Decaying positional shake, amp in output pixels.
  freeze     {"at": s, "hold": 1.4, "look"?: "none" | "desat" | "desat_vignette"}
             Holds one frame for `hold` seconds; audio is silent during the
             hold. The output gets `hold` seconds longer. Max one per range.
  speed      {"rate": 4.0, "pitch"?: true, "blend"?: false, "mute"?: false}
             Whole-range speed change. pitch=true gives chipmunk / slowed
             voice (default), false keeps the pitch (atempo). blend=true
             frame-blends slow motion. Can't be combined with freeze.

`anchor` is the normalized focus point (0..1, 0..1) the zoom pushes toward.
Zoom effects multiply together; the last anchor given wins.
"""

from __future__ import annotations

ZOOM_TYPES = {"punch_in", "crash_zoom"}
KNOWN_TYPES = ZOOM_TYPES | {"shake", "freeze", "speed"}
FREEZE_LOOKS = {
    "none": [],
    "desat": ["hue=s=0.15"],
    "desat_vignette": ["hue=s=0.15", "vignette=angle=PI/4"],
}
SAMPLE_RATE = 48000


class FxError(ValueError):
    pass


def _of_type(fx: list[dict], kind: str) -> list[dict]:
    return [e for e in fx if e.get("type") == kind]


def validate(fx: list[dict], duration: float) -> None:
    for e in fx:
        kind = e.get("type")
        if kind not in KNOWN_TYPES:
            raise FxError(f"unknown fx type {kind!r} (known: {sorted(KNOWN_TYPES)})")
        at = e.get("at")
        if at is not None and not 0 <= float(at) <= duration:
            raise FxError(f"{kind}: at={at} is outside the range (0–{duration:.3f}s)")
    freezes = _of_type(fx, "freeze")
    speeds = _of_type(fx, "speed")
    if len(freezes) > 1 or len(speeds) > 1:
        raise FxError("max one freeze and one speed per range: split the range instead")
    if freezes and speeds:
        raise FxError("freeze and speed can't share a range: split the range instead")
    if speeds and float(speeds[0].get("rate", 0)) <= 0:
        raise FxError("speed: rate must be > 0")
    for f in freezes:
        if float(f.get("hold", 0)) <= 0:
            raise FxError("freeze: hold must be > 0")
        if f.get("look", "desat_vignette") not in FREEZE_LOOKS:
            raise FxError(f"freeze: unknown look {f.get('look')!r} (known: {sorted(FREEZE_LOOKS)})")


def is_time_altering(fx: list[dict]) -> bool:
    return any(e.get("type") in ("freeze", "speed") for e in fx)


def output_duration(fx: list[dict], duration: float) -> float:
    for e in fx:
        if e["type"] == "freeze":
            return duration + float(e["hold"])
        if e["type"] == "speed":
            return duration / float(e["rate"])
    return duration


def map_time(fx: list[dict], t: float) -> float:
    """Map a source-relative time inside the range to segment-output time."""
    for e in fx:
        if e["type"] == "freeze":
            return t if t < float(e["at"]) else t + float(e["hold"])
        if e["type"] == "speed":
            return t / float(e["rate"])
    return t


# -------- Video ---------------------------------------------------------------


def _zoom_factor_expr(fx: list[dict], height: int, fps: int) -> tuple[str, bool]:
    """Return (expression for the zoom factor at time t, whether it varies with t)."""
    factors: list[str] = []
    varies = False
    for e in fx:
        kind = e["type"]
        if kind == "punch_in":
            s = float(e.get("scale", 1.15))
            if "at" in e or "until" in e:
                a = float(e.get("at", 0))
                u = float(e.get("until", 1e9))
                factors.append(f"if(between(t,{a:.4f},{u:.4f}),{s:.4f},1)")
                varies = True
            else:
                factors.append(f"{s:.4f}")
        elif kind == "crash_zoom":
            a = float(e["at"])
            to = float(e.get("to", 1.6))
            ramp = max(1, int(e.get("frames", 5))) / fps
            ramp_expr = f"1+{to - 1:.4f}*(1-pow(1-clip((t-{a:.4f})/{ramp:.4f},0,1),3))"
            if "until" in e:
                ramp_expr = f"if(gt(t,{float(e['until']):.4f}),1,{ramp_expr})"
            factors.append(ramp_expr)
            varies = True
        elif kind == "shake":
            a = float(e["at"])
            d = max(1, int(e.get("frames", 5))) / fps
            margin = 1 + 2.4 * float(e.get("amp", 12)) / height
            factors.append(f"if(between(t,{a:.4f},{a + d:.4f}),{margin:.4f},1)")
            varies = True
    return ("*".join(f"({f})" for f in factors) or "1"), varies


def _shake_offset_expr(fx: list[dict], fps: int, axis: str) -> str:
    # Different frequencies per axis so x and y don't move in lockstep.
    freq = 97 if axis == "x" else 71
    terms = []
    for e in _of_type(fx, "shake"):
        a = float(e["at"])
        d = max(1, int(e.get("frames", 5))) / fps
        amp = float(e.get("amp", 12))
        terms.append(
            f"if(between(t,{a:.4f},{a + d:.4f}),{amp:.2f}*(1-(t-{a:.4f})/{d:.4f})*sin(t*{freq}),0)"
        )
    return "+".join(terms) or "0"


def video_chain(fx: list[dict], width: int, height: int, fps: int) -> list[str]:
    """Filters to append after the base scale + grade. Output stays width×height@fps."""
    chain = [f"fps={fps}"]

    if any(e["type"] in ZOOM_TYPES or e["type"] == "shake" for e in fx):
        anchor = [0.5, 0.5]
        for e in fx:
            if e["type"] in ZOOM_TYPES and "anchor" in e:
                anchor = [float(v) for v in e["anchor"]]
        z, varies = _zoom_factor_expr(fx, height, fps)
        sx = _shake_offset_expr(fx, fps, "x")
        sy = _shake_offset_expr(fx, fps, "y")
        eval_mode = "frame" if varies else "init"
        chain.append(
            f"scale=w='2*trunc({width}*({z})/2)':h='2*trunc({height}*({z})/2)':eval={eval_mode}"
        )
        chain.append(
            f"crop={width}:{height}"
            f":x='clip({anchor[0]:.4f}*iw-{width}/2+({sx}),0,iw-{width})'"
            f":y='clip({anchor[1]:.4f}*ih-{height}/2+({sy}),0,ih-{height})'"
        )

    for e in _of_type(fx, "freeze"):
        at, hold = float(e["at"]), float(e["hold"])
        chain.append(
            f"loop=loop={round(hold * fps)}:size=1:start={round(at * fps)}"
        )
        chain.append(f"setpts=N/({fps}*TB)")
        for look in FREEZE_LOOKS[e.get("look", "desat_vignette")]:
            chain.append(f"{look}:enable='between(t,{at:.4f},{at + hold:.4f})'")

    for e in _of_type(fx, "speed"):
        rate = float(e["rate"])
        chain.append(f"setpts=PTS/{rate:.6f}")
        if e.get("blend") and rate < 1:
            chain.append(f"minterpolate=fps={fps}:mi_mode=blend")
        else:
            chain.append(f"fps={fps}")

    return chain


# -------- Audio ---------------------------------------------------------------


def _atempo_chain(rate: float) -> list[str]:
    parts = []
    while rate > 2.0:
        parts.append("atempo=2.0")
        rate /= 2.0
    while rate < 0.5:
        parts.append("atempo=0.5")
        rate /= 0.5
    parts.append(f"atempo={rate:.6f}")
    return parts


def audio_graph(fx: list[dict], in_label: str, out_label: str, duration: float) -> str:
    """filter_complex fragment from `in_label` to `out_label`, edge fades included."""
    fmt = f"aresample={SAMPLE_RATE},aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo"
    out_dur = output_duration(fx, duration)
    fades = (
        f"afade=t=in:st=0:d=0.03,"
        f"afade=t=out:st={max(0.0, out_dur - 0.03):.3f}:d=0.03"
    )

    freezes = _of_type(fx, "freeze")
    if freezes:
        at, hold = float(freezes[0]["at"]), float(freezes[0]["hold"])
        return (
            f"{in_label}{fmt},asplit=2[fz_a][fz_b];"
            f"[fz_a]atrim=0:{at:.4f},asetpts=PTS-STARTPTS[fz_pre];"
            f"[fz_b]atrim=start={at:.4f},asetpts=PTS-STARTPTS[fz_post];"
            f"anullsrc=r={SAMPLE_RATE}:cl=stereo,atrim=0:{hold:.4f}[fz_sil];"
            f"[fz_pre][fz_sil][fz_post]concat=n=3:v=0:a=1,{fades}{out_label}"
        )

    chain = [fmt]
    for e in _of_type(fx, "speed"):
        rate = float(e["rate"])
        if e.get("pitch", True):
            chain += [f"asetrate={SAMPLE_RATE * rate:.0f}", f"aresample={SAMPLE_RATE}"]
        else:
            chain += _atempo_chain(rate)
        if e.get("mute"):
            chain.append("volume=0")
    chain.append(fades)
    return f"{in_label}{','.join(chain)}{out_label}"
