---
name: fitness-transitions
description: Choose and render shot and chapter transitions for energetic fitness/vlog edits, including hard cuts, J/L-cuts, whip pans, match cuts, zoom-through, speed ramps, flash/impact cuts and chapter title wipes, with ffmpeg recipes and an overlap-aware EDL schema. Use during the transition pass of a fitness edit.
---

# Transitions

**The default transition is a hard cut.** In this genre ~85–90% of cuts are plain cuts, and energy comes from what's *on either side* of them. A transition has to earn its place: it marks a change of time, place or chapter, or it *is* a gag.

## Choose by purpose

| Purpose | Transition | Notes |
|---|---|---|
| Same scene, tighten | **Hard cut** (+ punch-in alternation) | See `fitness-comedic-cuts` |
| Dialogue flow across shots | **J-cut / L-cut** | Next shot's audio starts 0.3–0.8s early (J) or current audio trails over the next picture (L). The most invisible way to make cuts feel smooth |
| New location, same energy | **Whip pan** | Best when *filmed*: whip the camera at the end of shot A and the start of B, then cut mid-blur. Synthetic version below. 6–10 frames total. Whoosh SFX |
| Before/after, day N → day N+1 | **Match cut** | Same framing, same action (e.g. same pose on day 1 and day 30, the plate full then empty). Needs planning in the shot list |
| Into a chapter | **Title slam / wipe** | Chapter card from `fitness-motion-style` wipes on, on the music downbeat |
| Hype moment, entering the gym | **Speed ramp** | 1× → 3–4× → 1× over ~1s with a riser SFX; land on the beat |
| Impact / reveal | **Flash cut** | 2–3 white frames (or a 1-frame overexposure) + impact SFX, often paired with a crash zoom |
| Through an object | **Zoom-through** | Zoom into a dark area (mouth, bag, barbell sleeve) and come out of a dark area in the next shot. 8–12 frames |
| Time skip, comedic | **"Later…" card** | Hard cut to a full-screen text card ("3 HOURS LATER") with a cartoonish sting, 0.8–1.2s |
| Mood drop (failure, low point) | **Dip to black / quick crossfade** | Rare. Keep under 0.5s. Pair with the music dropping out |

**Avoid** generic NLE presets (page curl, cube spin, star wipe, glitch packs on every cut). They read as amateur unless used ironically, once.

## Rhythm rules

- Land transitions **on a music beat** (see `fitness-music-sfx` beat grid). If no beat is within ±2 frames, use a hard cut instead.
- **Vary them.** Never use the same stylised transition twice in a row. Whips are the spice; budget ~1 per minute in long-form.
- **Short-form:** almost entirely hard cuts and whips; there's no time for 0.5s dissolves.
- **Every stylised transition carries a SFX** (whoosh, swish, impact). A silent whip feels broken.

## EDL schema (`helpers/transitions.py`)

Add `transition_in` to the **incoming** range:

```json
{"source": "C0050", "start": 10.0, "end": 18.0, "beat": "CH3",
 "transition_in": {"type": "whip", "dir": "left", "dur": 0.27, "sfx": "whoosh_02"}}
{"transition_in": {"type": "flash", "dur": 0.125, "sfx": "impact", "sfx_offset": 0.05}}
{"transition_in": {"type": "j_cut", "lead": 0.5}}
{"transition_in": {"type": "l_cut", "lag": 0.6}}
```

Types: `whip` (dir left/right/up/down), `crossfade`, `dip_black`, `flash`, `zoom`, `wipe`, `circle`, or `{"type": "xfade", "xfade": "<ffmpeg name>"}`.

- **Overlap transitions shorten the video by `dur`.** The outgoing tail and incoming head blend into one clip. Leave ~`dur/2` of spare action on each side of the intended cut point. Only the transition clip and its neighbours' bodies are re-encoded.
- **J/L-cuts** keep the picture cut exactly where it is and patch the audio from the source handles. The range supplying the audio can't have speed/freeze fx, and the handle has to exist in the source.
- The transition SFX starts at the overlap start. Nudge it with `sfx_offset` so the hit lands on the motion peak.

## ffmpeg recipes

```bash
# Built-in xfade on two prepared clips (A ends, B starts). Offset = A_dur - dur.
ffmpeg -i A.mp4 -i B.mp4 -filter_complex \
 "[0:v][1:v]xfade=transition=slideleft:duration=0.25:offset=1.75[v];[0:a][1:a]acrossfade=d=0.25[a]" \
 -map "[v]" -map "[a]" trans.mp4
# Useful xfade types: slideleft/right (whip base), fadewhite (flash), zoomin, circleopen, smoothleft, hblur

# Synthetic whip: slide + horizontal motion blur
"[0:v][1:v]xfade=transition=slideleft:duration=0.27:offset=1.73,
 tblend=all_mode=average,boxblur=luma_radius=40:luma_power=1:chroma_radius=20:enable='between(t,1.73,2.0)'"

# Flash cut: 2 white frames between A and B
ffmpeg -f lavfi -i "color=white:s=1920x1080:r=30:d=0.067" flash.mp4

# Speed ramp (piecewise): split into 3 parts at 1×, 3×, 1× and concat, or use a setpts expression:
-vf "setpts='if(between(T,2,3),PTS/3,PTS)'"   # coarse; prefer split + concat for clean audio
```

Prefer **filmed transitions** (real whips, real match cuts) over synthetic ones. When writing the shot list in `fitness-script`, add "whip out/in" and "match frame" notes so the user films them.

## Self-check

Run `timeline_view` across every transition (±1s) on the rendered output, and check: no flash of the wrong frame, the SFX is aligned to the motion peak, the duration is unchanged, and there's no audio pop.
