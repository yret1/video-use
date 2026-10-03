"""Music beds, SFX hits, sidechain ducking and J/L-cut audio patches.

Runs on the concatenated base (picture-locked), before overlays/subtitles and
loudness normalization. Video is stream-copied.

EDL fields (times are on the OUTPUT timeline):

  "music": [{"file": "edit/audio/bed.wav" | "<name in assets/music>",
             "start_in_output": 0.0, "end_in_output"?: 18.4, "src_start"?: 0.0,
             "gain_db"?: -18, "fade_in"?: 0.0, "fade_out"?: 0.5,
             "duck"?: true, "loop"?: false}]
  "sfx":   [{"file": "<path or name in assets/sfx>", "at": 18.27,
             "gain_db"?: -8, "kill_music"?: false}]

`kill_music` hard-stops (20ms fade) every bed playing at that moment.

Standalone:
    python helpers/audio_mix.py <edl.json> --base edit/base.mp4 -o edit/mixed.mp4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SAMPLE_RATE = 48000
FMT = f"aresample={SAMPLE_RATE},aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo"
PATCH_FADE = 0.06  # crossfade length at J/L patch edges
DUCK = "sidechaincompress=threshold=0.02:ratio=8:attack=15:release=350"
AUDIO_EXTS = (".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".aif", ".aiff")
REPO_ASSETS = Path(__file__).resolve().parent.parent / "assets"
FREETOUSE = "https://freetouse.com/music"


def resolve_asset(name: str, edit_dir: Path, kind: str) -> Path:
    """Resolve a path (absolute / relative to edit dir or videos dir) or a bare
    asset name looked up in <videos_dir>/assets/<kind>/, then the video-use kit
    (video-use/assets/<kind>/, e.g. the synthesized SFX starter kit)."""
    p = Path(name)
    candidates = [p] if p.is_absolute() else [edit_dir / p, edit_dir.parent / p]
    if not p.suffix:
        for lib in (edit_dir.parent / "assets" / kind, REPO_ASSETS / kind):
            candidates += [lib / f"{name}{ext}" for ext in AUDIO_EXTS]
    for c in candidates:
        if c.exists():
            return c.resolve()
    raise FileNotFoundError(f"{kind} asset not found: {name!r} (looked in {[str(c) for c in candidates]})")


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _apply_kills(music: list[dict], sfx: list[dict]) -> None:
    for s in sfx:
        if not s.get("kill_music"):
            continue
        t = float(s["at"])
        for m in music:
            if m["_start"] < t < m["_end"]:
                m["_end"] = t
                m["fade_out"] = 0.02


def _patch_gain_expr(patches: list[dict]) -> str:
    """Dialogue gain: 1 everywhere, ramping to 0 inside each patch window."""
    f = PATCH_FADE
    terms = []
    for p in patches:
        a, b = float(p["at"]), float(p["at"]) + float(p["len"])
        terms.append(f"(1-clip(min((t-{a - f:.4f})/{f},({b + f:.4f}-t)/{f}),0,1))")
    return "*".join(terms)


def write_music_credits(music: list[dict], edit_dir: Path) -> Path | None:
    """Write the description credit block for every music track used.

    Free To Use (source "freetouse") requires this in the video description
    BEFORE the video goes public, or the upload gets a Content ID claim.
    Other sources: put the exact required text in the entry's `credit`.
    """
    if not music:
        return None
    seen, ftu, other, missing = set(), [], [], []
    for m in music:
        key = (m.get("title"), m.get("artist"), m["file"])
        if key in seen:
            continue
        seen.add(key)
        if m.get("source") == "freetouse":
            if m.get("title") and m.get("artist"):
                ftu.append(f"{m['title']} by {m['artist']}")
            else:
                missing.append(m["file"])
        elif m.get("credit"):
            other.append(m["credit"])
        else:
            missing.append(m["file"])
    lines = []
    if ftu:
        lines += ["Music from Free To Use", f"Source: {FREETOUSE}", *ftu]
    if other:
        lines += ([""] if lines else []) + other
    out = edit_dir / "description_credits.txt"
    out.write_text("\n".join(lines) + "\n")
    print(f"music credits → {out.name}  (paste into the description BEFORE publishing)")
    for f in missing:
        print(f"  WARNING: no attribution for music {f!r}: add source/title/artist "
              f"(Free To Use) or `credit` to its EDL entry")
    return out


def mix_audio(
    base: Path,
    out: Path,
    music: list[dict],
    sfx: list[dict],
    patches: list[dict],
    edit_dir: Path,
) -> None:
    total = probe_duration(base)
    inputs: list[str] = ["-i", str(base)]
    graph: list[str] = []
    n = 1

    # Dialogue (+ J/L patches)
    dlg = f"[0:a]{FMT}"
    if patches:
        dlg += f",volume='{_patch_gain_expr(patches)}':eval=frame"
    graph.append(f"{dlg}[dlg_raw]")
    patch_labels = []
    for i, p in enumerate(patches):
        f = min(PATCH_FADE, float(p["src_start"]))
        length = float(p["len"]) + f + PATCH_FADE
        inputs += ["-ss", f"{float(p['src_start']) - f:.4f}", "-t", f"{length:.4f}", "-i", p["source"]]
        delay_ms = int(round((float(p["at"]) - f) * 1000))
        graph.append(
            f"[{n}:a]{FMT},afade=t=in:d={f:.4f},"
            f"afade=t=out:st={length - PATCH_FADE:.4f}:d={PATCH_FADE},"
            f"adelay={delay_ms}:all=1[patch{i}]"
        )
        patch_labels.append(f"[patch{i}]")
        n += 1
    if patch_labels:
        graph.append(
            f"[dlg_raw]{''.join(patch_labels)}amix=inputs={1 + len(patch_labels)}"
            f":duration=first:normalize=0[dlg]"
        )
    else:
        graph.append("[dlg_raw]anull[dlg]")

    # Music
    beds = []
    for m in music:
        m = dict(m)
        m["_path"] = resolve_asset(m["file"], edit_dir, "music")
        m["_start"] = float(m.get("start_in_output", 0.0))
        src_start = float(m.get("src_start", 0.0))
        if "end_in_output" in m:
            m["_end"] = float(m["end_in_output"])
        elif m.get("loop"):
            m["_end"] = total
        else:
            m["_end"] = m["_start"] + probe_duration(m["_path"]) - src_start
        m["_end"] = min(m["_end"], total)
        beds.append(m)
    _apply_kills(beds, sfx)

    ducked, straight = [], []
    for i, m in enumerate(beds):
        length = m["_end"] - m["_start"]
        if length <= 0:
            continue
        if m.get("loop"):
            inputs += ["-stream_loop", "-1"]
        inputs += ["-ss", f"{float(m.get('src_start', 0.0)):.4f}", "-i", str(m["_path"])]
        fade_in = float(m.get("fade_in", 0.0))
        fade_out = min(float(m.get("fade_out", 0.5)), length)
        chain = [FMT, f"atrim=0:{length:.4f}", "asetpts=PTS-STARTPTS",
                 f"volume={float(m.get('gain_db', -18))}dB"]
        if fade_in > 0:
            chain.append(f"afade=t=in:d={fade_in:.4f}")
        chain.append(f"afade=t=out:st={length - fade_out:.4f}:d={fade_out:.4f}")
        chain.append(f"adelay={int(round(m['_start'] * 1000))}:all=1")
        graph.append(f"[{n}:a]{','.join(chain)}[mus{i}]")
        (ducked if m.get("duck", True) else straight).append(f"[mus{i}]")
        n += 1

    # SFX
    hits = []
    for i, s in enumerate(sfx):
        path = resolve_asset(s["file"], edit_dir, "sfx")
        inputs += ["-i", str(path)]
        graph.append(
            f"[{n}:a]{FMT},volume={float(s.get('gain_db', -8))}dB,"
            f"adelay={int(round(float(s['at']) * 1000))}:all=1[sfx{i}]"
        )
        hits.append(f"[sfx{i}]")
        n += 1

    # Buses
    final_inputs = ["[dlg_main]"]
    if ducked:
        graph.append("[dlg]asplit=2[dlg_main][dlg_sc]")
        graph.append(f"{''.join(ducked)}amix=inputs={len(ducked)}:normalize=0[mbus_raw]")
        graph.append(f"[mbus_raw][dlg_sc]{DUCK}[mbus]")
        final_inputs.append("[mbus]")
    else:
        graph.append("[dlg]anull[dlg_main]")
    if straight:
        graph.append(f"{''.join(straight)}amix=inputs={len(straight)}:normalize=0[mbus_dry]")
        final_inputs.append("[mbus_dry]")
    if hits:
        graph.append(f"{''.join(hits)}amix=inputs={len(hits)}:normalize=0[sbus]")
        final_inputs.append("[sbus]")

    graph.append(
        f"{''.join(final_inputs)}amix=inputs={len(final_inputs)}:duration=first:normalize=0,"
        f"alimiter=limit=0.97:level=false[mix]"
    )

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(graph),
        "-map", "0:v", "-map", "[mix]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SAMPLE_RATE),
        "-movflags", "+faststart",
        str(out),
    ]
    print(f"audio mix → {out.name}  (music: {len(ducked) + len(straight)}, "
          f"sfx: {len(hits)}, J/L patches: {len(patches)})")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def main() -> None:
    ap = argparse.ArgumentParser(description="Mix music + SFX onto a picture-locked base")
    ap.add_argument("edl", type=Path)
    ap.add_argument("--base", type=Path, required=True, help="Concatenated base video")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    edl_path = args.edl.resolve()
    if not edl_path.exists():
        sys.exit(f"edl not found: {edl_path}")
    edl = json.loads(edl_path.read_text())
    mix_audio(args.base.resolve(), args.output.resolve(), edl.get("music") or [],
              edl.get("sfx") or [], [], edl_path.parent)
    write_music_credits(edl.get("music") or [], edl_path.parent)


if __name__ == "__main__":
    main()
