---
name: fitness-comedic-cuts
description: Comedic editing techniques for fitness/vlog YouTube: tight jump cuts with alternating punch-ins, smash-cut contradictions, freeze-frame narration, crash zooms, speed-up and ironic slow-mo, deadpan holds, text contradictions and instant replays, with ffmpeg recipes and EDL fields. Use during the comedy pass of a fitness edit.
---

# Comedic Cuts

Comedy in editing comes from **timing and contrast**. A technique only works if there's a setup in the footage for it to pay off. Find the setup in `takes_packed.md` first, then pick the technique that fits.

## Base rhythm: the jump-cut talking head

- Remove every breath, "um", restart and gap >150ms between sentences (short-form) or >300ms (long-form). Remember video-use Rule 7 on padding.
- **Alternate framing on every jump cut**: 100% → 112–120% punch-in → 100%. This hides the jump and adds energy. On 4K sources, crop rather than upscale.
- Don't punch in on the same line twice in a row, and don't punch in during a gesture that leaves the frame.

## Technique catalog

| Technique | When | Recipe |
|---|---|---|
| **Smash-cut contradiction** | Host states an intention, then reality is the opposite | Hard cut on the last syllable, no padding after. Often with a 0.3s silence first, then the contradicting shot with a SFX hit |
| **Deadpan hold** | After a dumb or honest line | *Don't* cut. Hold 0.6–1.2s on the face. Optional slow 100→108% push-in. No music under it (duck to silence) |
| **Crash zoom** | Realisation, shock, the number reveal | Zoom 100→160% in 4–6 frames, centred on the face/eyes, plus an impact SFX. Hold, then cut |
| **Freeze-frame + VO** | "This is when I realised…" moments | Freeze the most awkward frame (grimace, mid-bite). Optional desaturate + vignette + record-scratch SFX. VO or text explains |
| **Speed-up** | Boring process (meal prep, warm-up, commute) | 4–16× with pitched-up audio or comedic music. Cap at 6s on screen |
| **Ironic slow-mo** | Mundane action treated as epic | 0.25–0.5× (only if shot at high fps; otherwise frame-blend, max 0.5×) + epic choir/orchestral sting |
| **Text contradiction** | Host says something the footage disproves | Small caption-style text: "(he was not fine)". Timed to appear 0.3s after the line ends |
| **Instant replay** | Fails, near-misses, big lifts | Rewind effect (reverse 0.5s at 2× + VHS tape SFX), then replay at 0.5× with a circle/arrow callout |
| **Reaction cutaway** | Anyone else in the shot | Cut to their face mid-sentence for 0.5–1s, then back |
| **"Anyway" cut** | A rambling tangent | Let it run 2–3s, then hard cut to the host already somewhere else, with no transition |
| **Censor bleep** | Swearing, or ironically on non-swear words | 1kHz sine bleep + mouth blur or emoji sticker over the mouth |
| **Shake** | Impact: dropping weights, slamming a protein shake | 3–6 frames of ±8–15px random offset, decaying |

## Timing rules

- **The cut is the punchline.** Cutting a beat early kills the joke. Cutting a beat late lets the viewer see it coming. Default to a 0–2 frame pause before a smash cut.
- **Let the laugh breathe.** If someone in the footage laughs, keep it (video-use: "the laugh IS the beat").
- **One effect per gag.** Crash zoom + freeze + meme + SFX on the same moment is noise, not comedy.
- **Escalate within a video.** Save the biggest treatment (freeze-frame + VO, instant replay) for the biggest moments.
- **Vary the technique.** Don't use the same technique 3 times in a row (see fitness-video's retention review).

## EDL fields (`helpers/fx.py`)

Add `fx` to a range; it's applied during per-segment extraction so the lossless concat stays intact:

```json
{"source": "C0042", "start": 31.0, "end": 38.2, "beat": "CH2/G3",
 "fx": [
   {"type": "punch_in", "scale": 1.15, "anchor": [0.5, 0.35]},
   {"type": "crash_zoom", "at": 2.1, "to": 1.6, "frames": 5, "until": 3.5},
   {"type": "shake", "at": 3.0, "frames": 5, "amp": 12}
 ]}
{"source": "C0042", "start": 38.2, "end": 41.0, "fx": [{"type": "freeze", "at": 0.8, "hold": 1.4, "look": "desat_vignette"}]}
{"source": "C0050", "start": 0.0,  "end": 40.0, "fx": [{"type": "speed", "rate": 8, "pitch": true}]}
```

- `at`/`until` are seconds from the range start, in source time.
- `anchor` is the normalized focus point (x, y in 0..1). There's no face tracking: look at a frame with `timeline_view` and estimate where the face is.
- Each range takes at most one freeze or one speed effect, never both. For a speed ramp, split into ranges (1× | 3× | 1×). For two freezes, split the range.
- A freeze makes its range `hold` seconds longer. A speed change makes it `duration / rate` long. Sped ranges get no captions.
- Gags that need audio (record scratch, bleep, sting) also add entries to `sfx` (see `fitness-music-sfx`), timed from render.py's printed output timeline.

## ffmpeg recipes (for effects fx.py doesn't cover)

```bash
# Static punch-in 115% (centred). For face anchoring, compute x/y from a face bbox.
-vf "scale=iw*1.15:ih*1.15,crop=iw/1.15:ih/1.15:(iw-iw/1.15)/2:(ih-ih/1.15)/2"

# Crash zoom over 5 frames starting at t=2.1s (30fps), centred, 1.0 → 1.6
-vf "zoompan=z='if(between(on,63,68),1+0.6*(on-63)/5,if(gt(on,68),1.6,1))':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1920x1080:fps=30"

# Speed-up 8× with pitched audio
-vf "setpts=PTS/8" -af "atempo=2,atempo=2,atempo=2,asetrate=48000*1.25,aresample=48000"

# Slow-mo 0.5× with frame blending
-vf "minterpolate=fps=60:mi_mode=blend,setpts=2*PTS" -af "atempo=0.5"

# Freeze frame at 5.8s held 1.4s (clone the frame, then grade it)
-vf "trim=0:5.8,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=1.4"
# Desat + vignette look for the frozen part: "hue=s=0.2,vignette=PI/4"

# Shake (decaying random offset) at 3.0s for 5 frames
-vf "crop=iw-30:ih-30:15+if(between(t,3,3.17),12*random(1)-6,0):15+if(between(t,3,3.17),12*random(2)-6,0),scale=1920:1080"
```

Always keep the 30ms boundary fades on any segment where you've changed the audio rate.

## Self-check

At each gag, run `timeline_view` on the rendered preview (±2s) and ask yourself: is the setup readable, does the cut land on the beat, and is there exactly one treatment on it?
