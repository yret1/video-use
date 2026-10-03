"""Synthesize the starter SFX kit into assets/sfx/ (48 kHz stereo WAV).

Everything is generated from oscillators and noise, so the kit is ours:
no licence, no attribution, no Content ID. Deterministic (fixed seed);
re-run to regenerate after tweaking a recipe.

Names match graphics.py cues (pop, slam, thud, tick, ding, boom, marker)
plus edit staples (whoosh, swish, whoosh_long, riser, record_scratch,
bleep, boing, click).

Usage:
    python helpers/make_sfx.py                 # → video-use/assets/sfx/
    python helpers/make_sfx.py -o <dir> --only boom ding
"""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

import numpy as np
from scipy import signal

SR = 48000
REPO = Path(__file__).resolve().parent.parent
rng = np.random.default_rng(1234)


# -------- Building blocks -----------------------------------------------------


def t_axis(dur: float) -> np.ndarray:
    return np.arange(int(dur * SR)) / SR


def noise(dur: float) -> np.ndarray:
    return rng.standard_normal(int(dur * SR))


def pink(dur: float) -> np.ndarray:
    # Voss-ish: white noise through a -3 dB/oct approximation filter
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1, -2.494956002, 2.017265875, -0.522189400]
    return signal.lfilter(b, a, noise(dur)) * 8


def sine_sweep(f: np.ndarray) -> np.ndarray:
    """Sine following an instantaneous-frequency curve f (Hz per sample)."""
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def env_exp(dur: float, decay: float, attack: float = 0.002) -> np.ndarray:
    t = t_axis(dur)
    return np.minimum(1.0, t / max(attack, 1e-6)) * np.exp(-t / decay)


def bell(dur: float) -> np.ndarray:
    """Smooth rise and fall (sin² window)."""
    return np.sin(np.pi * np.linspace(0, 1, int(dur * SR))) ** 2


def band(x: np.ndarray, lo: float, hi: float, order: int = 2) -> np.ndarray:
    sos = signal.butter(order, [lo, hi], btype="bandpass", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lowpass(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(signal.butter(order, fc, fs=SR, output="sos"), x)


def highpass(x: np.ndarray, fc: float, order: int = 2) -> np.ndarray:
    return signal.sosfilt(signal.butter(order, fc, btype="highpass", fs=SR, output="sos"), x)


def svf_bandpass(x: np.ndarray, fc: np.ndarray, q: float = 1.4) -> np.ndarray:
    """State-variable band-pass with a per-sample cutoff (for sweeps)."""
    out = np.empty_like(x)
    low = bp = 0.0
    damp = 1.0 / q
    f = 2 * np.sin(np.pi * np.clip(fc, 20, SR / 6) / SR)
    for i in range(len(x)):
        high = x[i] - low - damp * bp
        bp += f[i] * high
        low += f[i] * bp
        out[i] = bp
    return out


def curve(dur: float, points: list[tuple[float, float]]) -> np.ndarray:
    """Piecewise-exponential curve through (time_fraction, value) points."""
    t = np.linspace(0, 1, int(dur * SR))
    xs, ys = zip(*points)
    return np.exp(np.interp(t, xs, np.log(ys)))


def saturate(x: np.ndarray, drive: float = 1.5) -> np.ndarray:
    return np.tanh(x * drive) / np.tanh(drive)


def pan_stereo(x: np.ndarray, pan: np.ndarray | float = 0.0) -> np.ndarray:
    """Equal-power pan, -1 (L) … 1 (R). Returns (n, 2)."""
    p = (np.asarray(pan) + 1) * np.pi / 4
    return np.stack([x * np.cos(p), x * np.sin(p)], axis=1)


def widen(x: np.ndarray, ms: float = 9.0) -> np.ndarray:
    """Cheap stereo width: slightly delayed, filtered copy on the right."""
    d = int(ms / 1000 * SR)
    r = np.concatenate([np.zeros(d), lowpass(x, 6000)])[: len(x)]
    return np.stack([x, 0.6 * x + 0.4 * r], axis=1)


def room(x: np.ndarray, size: float = 0.35, mix: float = 0.18) -> np.ndarray:
    """Tiny noise-burst convolution reverb to take the dry edge off."""
    n = int(size * SR)
    ir = noise(size) * np.exp(-np.linspace(0, 6, n))
    ir = lowpass(ir, 5000)
    ir /= np.abs(ir).sum() / 4
    wet = np.pad(signal.fftconvolve(x, ir), (0, 1))[: len(x) + n]
    dry = np.concatenate([x, np.zeros(n)])
    return dry * (1 - mix) + wet * mix


def tail_fade(x: np.ndarray, frac: float = 0.3) -> np.ndarray:
    """Cosine fade over the last `frac` of the signal so ringing tails never cut off."""
    n = int(len(x) * frac)
    x = x.copy()
    x[-n:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, n)))
    return x


def fade_edges(x: np.ndarray, ms: float = 3.0) -> np.ndarray:
    n = min(len(x) // 2, int(ms / 1000 * SR))
    ramp = np.linspace(0, 1, n)
    x = x.copy()
    x[:n] *= ramp[:, None] if x.ndim == 2 else ramp
    x[-n:] *= ramp[::-1][:, None] if x.ndim == 2 else ramp[::-1]
    return x


# -------- Recipes --------------------------------------------------------------


def whoosh(dur=0.55, lo=280, peak=3200, end=700, q=1.3):
    fc = curve(dur, [(0, lo), (0.55, peak), (1, end)])
    x = svf_bandpass(pink(dur), fc, q) * bell(dur)
    x += 0.25 * svf_bandpass(noise(dur), fc * 2.2, 2.5) * bell(dur) ** 2  # airy top
    return pan_stereo(x, np.linspace(-0.7, 0.7, len(x)))


def swish():
    return whoosh(0.24, lo=1200, peak=6500, end=2500, q=1.8)


def whoosh_long():
    return whoosh(1.05, lo=180, peak=2600, end=500, q=1.1)


def riser(dur=1.6):
    t = t_axis(dur)
    fc = curve(dur, [(0, 200), (1, 7000)])
    sweep = svf_bandpass(pink(dur), fc, 2.0)
    tone = sine_sweep(curve(dur, [(0, 180), (1, 1400)])) * 0.25
    tone += sine_sweep(curve(dur, [(0, 181.5), (1, 1412)])) * 0.25  # detuned → shimmer
    x = (sweep + tone) * (t / dur) ** 2.2
    return widen(x)


def boom(dur=1.8):
    f = curve(dur, [(0, 95), (0.08, 52), (1, 36)])
    body = sine_sweep(f) + 0.35 * sine_sweep(2 * f)
    body *= env_exp(dur, 0.55, attack=0.003)
    click = lowpass(noise(0.012), 2500) * np.linspace(1, 0, int(0.012 * SR))
    body[: len(click)] += 1.2 * click
    return widen(room(tail_fade(saturate(body, 2.2)), 0.6, 0.15))


def slam(dur=0.6):
    f = curve(dur, [(0, 140), (0.15, 60), (1, 50)])
    thump = sine_sweep(f) * env_exp(dur, 0.16, attack=0.001)
    crack = band(noise(dur), 1400, 4500) * env_exp(dur, 0.035, attack=0.0005)
    body = band(noise(dur), 200, 900) * env_exp(dur, 0.07)
    return widen(room(tail_fade(saturate(thump + 0.55 * crack + 0.4 * body, 2.0)), 0.3, 0.12))


def thud(dur=0.45):
    f = curve(dur, [(0, 95), (0.2, 55), (1, 48)])
    x = sine_sweep(f) * env_exp(dur, 0.12, attack=0.002)
    x += 0.5 * lowpass(noise(dur), 600) * env_exp(dur, 0.04)
    return widen(tail_fade(saturate(x, 1.6)))


def pop(dur=0.13):
    f = curve(dur, [(0, 950), (0.35, 260), (1, 220)])
    x = sine_sweep(f) * env_exp(dur, 0.045, attack=0.001)
    x += 0.3 * highpass(noise(dur), 3000) * env_exp(dur, 0.004)
    return widen(x, 4)


def click(dur=0.05):
    x = highpass(noise(dur), 2500) * env_exp(dur, 0.003, attack=0.0002)
    x += 0.6 * np.sin(2 * np.pi * 2200 * t_axis(dur)) * env_exp(dur, 0.008)
    return widen(x, 3)


def tick(dur=0.9, rate=22.0):
    """Counter tick-roll: fast clicks rising in pitch (pairs with a count-up)."""
    out = np.zeros(int(dur * SR))
    n_ticks = int(dur * rate)
    for k in range(n_ticks):
        # Ticks spread out towards the end, like an ease-out counter slowing to land
        pos = (k / n_ticks) ** 1.6 * dur * 0.97
        i = int(pos * SR)
        c = 0.06
        f0 = 1800 + 1400 * k / n_ticks
        blip = np.sin(2 * np.pi * f0 * t_axis(c)) * env_exp(c, 0.006, attack=0.0003)
        blip += 0.4 * highpass(noise(c), 4000) * env_exp(c, 0.002)
        out[i : i + len(blip)] += blip[: len(out) - i]
    return widen(out, 3)


def ding(dur=2.6, f0=1568.0):
    t = t_axis(dur)
    x = np.zeros_like(t)
    for ratio, amp, decay in [(1, 1.0, 0.9), (2.0, 0.45, 0.6), (2.76, 0.35, 0.4),
                              (5.4, 0.18, 0.2), (8.9, 0.08, 0.1)]:
        x += amp * np.sin(2 * np.pi * f0 * ratio * t) * np.exp(-t / decay)
    x *= np.minimum(1, t / 0.0015)
    return widen(room(tail_fade(x * 0.5, 0.4), 0.5, 0.2), 6)


def marker(dur=0.32):
    grain = np.repeat(rng.uniform(0.3, 1.0, int(dur * 220)), SR // 220)[: int(dur * SR)]
    grain = np.pad(grain, (0, int(dur * SR) - len(grain)), mode="edge")
    x = band(noise(dur), 1800, 6000) * grain * bell(dur) ** 0.5
    return pan_stereo(x * 0.8, 0.1)


def record_scratch(dur=0.62):
    """Variable-speed playback of a chord, back and forth, like a hand on vinyl."""
    src_dur = 2.0
    ts = t_axis(src_dur)
    chord = sum(signal.sawtooth(2 * np.pi * f * ts) for f in (196, 247, 294, 392)) / 4
    chord = lowpass(chord + 0.2 * noise(src_dur), 3500)
    t = t_axis(dur)
    speed = 3.2 * np.sin(2 * np.pi * 2.4 * t) * np.exp(-t / 0.5)
    pos = 0.6 * SR + np.cumsum(speed)
    x = np.interp(pos, np.arange(len(chord)), chord)
    x = band(x, 150, 5000) * np.minimum(1, np.abs(speed) * 1.5)
    return widen(saturate(x * 1.5, 1.3), 5)


def bleep(dur=0.6):
    x = np.sin(2 * np.pi * 1000 * t_axis(dur))
    return pan_stereo(fade_edges(x, 5) * 0.7, 0.0)


def boing(dur=0.75):
    t = t_axis(dur)
    f = 210 * (1 + 0.45 * np.exp(-t / 0.18) * np.sin(2 * np.pi * 13 * t)) + 90 * np.exp(-t / 0.05)
    x = sine_sweep(f) * env_exp(dur, 0.3, attack=0.002)
    x += 0.25 * sine_sweep(2 * f) * env_exp(dur, 0.15)
    return widen(x)


RECIPES = {
    "whoosh": (whoosh, "Medium whoosh, L→R. Transitions, whips, fast moves."),
    "swish": (swish, "Short bright swish. Text/graphic swoosh-ins, quick whips."),
    "whoosh_long": (whoosh_long, "Long, dark whoosh. Chapter transitions, slow pushes."),
    "riser": (riser, "1.6s build. Into drops, reveals, hype cuts; end it on the hit."),
    "boom": (boom, "Deep sub hit with tail. Reveals, crash zooms, big punchlines."),
    "slam": (slam, "Punchy impact. Title word slams, plate drops, smash cuts."),
    "thud": (thud, "Soft low thud. Stamps, landings, small impacts."),
    "pop": (pop, "Bubble pop. Graphic/sticker entrances."),
    "click": (click, "Single UI click."),
    "tick": (tick, "0.9s rising tick-roll. Number count-ups."),
    "ding": (ding, "Bright bell. Counter landings, correct answers, PRs."),
    "marker": (marker, "Felt-marker scribble. Arrows and circles drawing on."),
    "record_scratch": (record_scratch, "Vinyl scratch. Freeze-frames, 'wait what' moments, music stops."),
    "bleep": (bleep, "1 kHz censor bleep."),
    "boing": (boing, "Cartoon boing. Fails, bounces, silly moments."),
}


def write_wav(path: Path, x: np.ndarray, peak_db: float = -1.0) -> None:
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    x = fade_edges(x, 2.0)
    x = x / (np.abs(x).max() + 1e-9) * 10 ** (peak_db / 20)
    pcm = (x * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main() -> None:
    ap = argparse.ArgumentParser(description="Synthesize the starter SFX kit")
    ap.add_argument("-o", "--out", type=Path, default=REPO / "assets" / "sfx")
    ap.add_argument("--only", nargs="*", help="Only these sounds")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    names = args.only or list(RECIPES)
    index = {}
    for name in names:
        fn, desc = RECIPES[name]
        x = fn()
        write_wav(args.out / f"{name}.wav", x)
        index[name] = {"file": f"{name}.wav", "duration": round(len(x) / SR, 3), "use": desc}
        print(f"  {name:15s} {len(x) / SR:5.2f}s  {desc}")
    meta = args.out / "sfx.json"
    existing = json.loads(meta.read_text()) if meta.exists() else {}
    existing.update(index)
    meta.write_text(json.dumps({"_license": "Synthesized by helpers/make_sfx.py. Owned outright; "
                                            "no attribution needed.", **{k: v for k, v in existing.items()
                                                                       if not k.startswith("_")}},
                               indent=2))
    print(f"→ {args.out}")


if __name__ == "__main__":
    main()
