"""Beat grid for a music track: tempo, beats, approximate downbeats, onsets.

Snap hype cuts, transitions and graphic slams to these (never dialogue cuts).

Usage:
    python helpers/beats.py edit/audio/track.wav            → edit/audio/track.beats.json
    python helpers/beats.py track.mp3 -o beats.json --src-start 12.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import librosa
import numpy as np


def analyze(path: Path, src_start: float = 0.0) -> dict:
    y, sr = librosa.load(str(path), sr=None, mono=True, offset=src_start)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, units="time")

    # Downbeats: pick the 4-beat phase with the strongest onsets (assumes 4/4).
    beat_frames = librosa.time_to_frames(beats, sr=sr)
    strength = onset_env[np.clip(beat_frames, 0, len(onset_env) - 1)] if len(beats) else np.array([])
    phase = int(np.argmax([strength[p::4].sum() for p in range(4)])) if len(beats) >= 4 else 0

    def r(xs):
        return [round(float(x), 3) for x in xs]

    return {
        "file": str(path),
        "src_start": src_start,
        "tempo_bpm": round(float(np.atleast_1d(tempo)[0]), 2),
        "beats": r(beats),
        "downbeats": r(beats[phase::4]),
        "onsets": r(onsets),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Detect beats/downbeats/onsets in a music track")
    ap.add_argument("track", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=None)
    ap.add_argument("--src-start", type=float, default=0.0,
                    help="Seconds into the track where the bed starts (times are relative to this)")
    args = ap.parse_args()

    result = analyze(args.track, args.src_start)
    out = args.output or args.track.with_suffix(".beats.json")
    out.write_text(json.dumps(result, indent=2))
    print(f"{result['tempo_bpm']} BPM, {len(result['beats'])} beats, "
          f"{len(result['downbeats'])} downbeats → {out}")


if __name__ == "__main__":
    main()
