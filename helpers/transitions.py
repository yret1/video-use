"""Shot transitions (EDL range `transition_in`), applied between extracted segments.

Two families:

  Overlap transitions: the outgoing tail and incoming head (each `dur` long)
  are blended into one clip of length `dur`. Each one makes the output `dur`
  seconds SHORTER. Only the transition clip and the trimmed segment bodies
  around it are re-encoded; everything else stays lossless.

    {"type": "whip", "dir": "left"|"right"|"up"|"down", "dur": 0.27, "sfx"?: "whoosh_02"}
    {"type": "crossfade" | "dip_black" | "flash" | "zoom" | "wipe" | "circle", "dur": 0.3}
    {"type": "xfade", "xfade": "<any ffmpeg xfade transition name>", "dur": 0.4}

  Audio-only transitions: the picture cuts on time and the audio is patched
  by audio_mix.py. Total duration is unchanged.

    {"type": "j_cut", "lead": 0.5}   incoming audio starts `lead` s early, under the outgoing picture
    {"type": "l_cut", "lag": 0.5}    outgoing audio continues `lag` s under the incoming picture

  J/L-cuts read the extra audio straight from the source file, so the
  segment providing it can't have a speed/freeze fx, and the handle has to
  exist in the source.

`sfx` (optional, any transition) is a file path or an SFX name looked up in
<videos_dir>/assets/sfx/. It starts at the transition start; `sfx_offset`
shifts it in seconds and `sfx_gain_db` sets its level (default -8).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import fx as fxmod

XFADE_NAMES = {
    "crossfade": "fade",
    "dip_black": "fadeblack",
    "flash": "fadewhite",
    "zoom": "zoomin",
    "wipe": "wipeleft",
    "circle": "circleopen",
}
WHIP_DIRS = {"left": "slideleft", "right": "slideright", "up": "slideup", "down": "slidedown"}
AUDIO_ONLY = {"j_cut", "l_cut"}
EDGE_FADE = 0.01  # short fades where a body is cut mid-sound (the crossfade covers the rest)


class TransitionError(ValueError):
    pass


def overlap_duration(tr: dict | None, fps: int) -> float:
    """Frame-snapped overlap for a transition_in, 0.0 for none / audio-only."""
    if not tr or tr.get("type") in AUDIO_ONLY:
        return 0.0
    return max(1, round(float(tr.get("dur", 0.3)) * fps)) / fps


def _xfade_name(tr: dict) -> str:
    kind = tr.get("type")
    if kind == "whip":
        return WHIP_DIRS[tr.get("dir", "left")]
    if kind == "xfade":
        return tr["xfade"]
    if kind in XFADE_NAMES:
        return XFADE_NAMES[kind]
    raise TransitionError(
        f"unknown transition type {kind!r} "
        f"(known: whip, xfade, j_cut, l_cut, {', '.join(XFADE_NAMES)})"
    )


def validate(ranges: list[dict]) -> None:
    """Checks that don't need rendered segments; run before extraction."""
    for i, r in enumerate(ranges):
        tr = r.get("transition_in")
        if not tr:
            continue
        if i == 0:
            raise TransitionError("the first range can't have a transition_in")
        kind = tr.get("type")
        if kind == "j_cut" and fxmod.is_time_altering(r.get("fx") or []):
            raise TransitionError(f"range {i}: j_cut needs the incoming range free of speed/freeze fx")
        elif kind == "l_cut" and fxmod.is_time_altering(ranges[i - 1].get("fx") or []):
            raise TransitionError(f"range {i}: l_cut needs the outgoing range free of speed/freeze fx")
        elif kind not in AUDIO_ONLY:
            _xfade_name(tr)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _encode(cmd_inputs: list[str], filter_complex: str, out: Path, enc: dict) -> None:
    cmd = [
        "ffmpeg", "-y", *cmd_inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", enc["preset"], "-crf", enc["crf"],
        "-pix_fmt", "yuv420p", "-r", str(enc["fps"]),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _render_body(seg: Path, start: float, end: float, out: Path, enc: dict) -> None:
    length = end - start
    fades = []
    if start > 0:
        fades.append(f"afade=t=in:st=0:d={EDGE_FADE}")
    fades.append(f"afade=t=out:st={max(0.0, length - EDGE_FADE):.4f}:d={EDGE_FADE}")
    fc = (
        f"[0:v]trim=start={start:.4f}:end={end:.4f},setpts=PTS-STARTPTS[v];"
        f"[0:a]atrim=start={start:.4f}:end={end:.4f},asetpts=PTS-STARTPTS,{','.join(fades)}[a]"
    )
    _encode(["-i", str(seg)], fc, out, enc)


def _render_transition(a: Path, a_len: float, b: Path, tr: dict, d: float, out: Path, enc: dict) -> None:
    name = _xfade_name(tr)
    tail = a_len - d
    post = ""
    if tr.get("type") == "whip":
        # Directional motion blur through the middle of the slide.
        horizontal = tr.get("dir", "left") in ("left", "right")
        size = "sizeX=60:sizeY=1" if horizontal else "sizeX=1:sizeY=60"
        post = f",avgblur={size}:enable='between(t,{d * 0.15:.4f},{d * 0.85:.4f})'"
    fc = (
        f"[0:v]trim=start={tail:.4f},setpts=PTS-STARTPTS[va];"
        f"[1:v]trim=end={d:.4f},setpts=PTS-STARTPTS[vb];"
        f"[va][vb]xfade=transition={name}:duration={d:.4f}:offset=0{post}[v];"
        f"[0:a]atrim=start={tail:.4f},asetpts=PTS-STARTPTS[aa];"
        f"[1:a]atrim=end={d:.4f},asetpts=PTS-STARTPTS[ab];"
        f"[aa][ab]acrossfade=d={d:.4f}[a]"
    )
    _encode(["-i", str(a), "-i", str(b)], fc, out, enc)


def apply_transitions(
    seg_paths: list[Path],
    ranges: list[dict],
    sources: dict[str, Path],
    work_dir: Path,
    enc: dict,
) -> tuple[list[Path], list[float], list[dict], list[dict]]:
    """Render overlap transitions and collect audio-only ones.

    `enc` = {"fps": int, "crf": str, "preset": str}.

    Returns (paths to concat, output start time of each range, sfx events,
    audio patches for audio_mix). A range's output start is where its local
    time 0 lands on the output timeline.
    """
    fps = enc["fps"]
    lengths = [probe_duration(p) for p in seg_paths]
    d_in = [0.0] + [overlap_duration(r.get("transition_in"), fps) for r in ranges[1:]]
    d_in.append(0.0)  # nothing after the last range

    validate(ranges)
    for i in range(len(ranges)):
        if d_in[i] + d_in[i + 1] > lengths[i] - 1.0 / fps:
            raise TransitionError(
                f"range {i} ({lengths[i]:.2f}s) is too short for its transitions "
                f"({d_in[i]:.2f}s in + {d_in[i + 1]:.2f}s out)"
            )

    work_dir.mkdir(parents=True, exist_ok=True)
    out_paths: list[Path] = []
    offsets: list[float] = []
    events: list[dict] = []
    patches: list[dict] = []
    t = 0.0

    for i, seg in enumerate(seg_paths):
        head, tail = d_in[i], d_in[i + 1]
        offsets.append(t)  # local 0 = start of the overlap with the previous tail
        tr = ranges[i].get("transition_in")

        if head > 0:
            clip = work_dir / f"trans_{i:02d}.mp4"
            print(f"  transition {i - 1:02d}→{i:02d}: {tr['type']} ({head:.3f}s)")
            _render_transition(seg_paths[i - 1], lengths[i - 1], seg, tr, head, clip, enc)
            out_paths.append(clip)
            t += head

        if tr and tr.get("type") in AUDIO_ONLY:
            patches.append(_audio_patch(tr, ranges[i - 1], ranges[i], sources, t))

        if tr and tr.get("sfx"):
            transition_start = t - head
            events.append({
                "file": tr["sfx"],
                "at": max(0.0, transition_start + float(tr.get("sfx_offset", 0.0))),
                "gain_db": float(tr.get("sfx_gain_db", -8)),
            })

        if head > 0 or tail > 0:
            body = work_dir / f"body_{i:02d}.mp4"
            _render_body(seg, head, lengths[i] - tail, body, enc)
            out_paths.append(body)
        else:
            out_paths.append(seg)
        t += lengths[i] - head - tail

    return out_paths, offsets, events, patches


def _audio_patch(tr: dict, prev: dict, cur: dict, sources: dict[str, Path], boundary: float) -> dict:
    if tr["type"] == "j_cut":
        lead = float(tr.get("lead", 0.5))
        src_start = float(cur["start"]) - lead
        if src_start < 0:
            raise TransitionError(f"j_cut: source {cur['source']} has no {lead}s of audio before {cur['start']}")
        return {"at": boundary - lead, "len": lead, "source": str(sources[cur["source"]]), "src_start": src_start}

    lag = float(tr.get("lag", 0.5))
    return {"at": boundary, "len": lag, "source": str(sources[prev["source"]]), "src_start": float(prev["end"])}
