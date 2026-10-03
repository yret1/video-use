---
name: fitness-video
description: Direct a fitness YouTube video end to end, long-form (8–25 min) or short-form (Shorts/Reels/TikTok), in the comedic, high-energy style of fitness creators like Will Tennyson or Jesse James West. Use when the user wants to script, edit, cut, add memes/GIFs, transitions, music, SFX or on-screen graphics to gym, diet, challenge or transformation footage. Orchestrates the fitness-* sub-skills on top of video-use.
---

# Fitness Video Director

You are the showrunner. Each sub-skill handles one craft, and this skill sets the order they run in and the bar the result has to clear.

**Foundation:** every cut, grade, overlay and caption goes through `video-use` (read `~/.claude/skills/video-use/SKILL.md` first). Its Hard Rules still apply: word-boundary cuts, 30ms fades, subtitles applied last, overlays PTS-shifted, and no editing before the strategy is confirmed. The rules below are added on top of them.

## The genre in one paragraph

These videos are built on a **premise with stakes** ("I ate like a bodybuilder for 24 hours", "I trained like an NFL lineman", "75 days of X", "testing viral gym hacks"), carried by a **likeable, self-deprecating host**, and kept moving with **constant small rewards**: a gag, a number going up, a meme, a sound effect, a reveal. Information (macros, workouts, weights) appears as **big, punchy on-screen graphics**, not narration. The tone is chaotic but the structure underneath is tight. Every chapter sets up a question and pays it off.

**Emulate the genre, never the person.** Don't copy anyone's intro, logo, catchphrases, recurring characters, sound stings or exact graphic designs. Build the user's own recognizable version (see `fitness-motion-style`).

## Sub-skills (read the one you need, when you need it)

Paths below are relative to `~/.claude/skills/video-use/`.

| Skill | Owns |
|---|---|
| `skills/fitness-script/` | Premise, hook, chapter beats, gag list, shot list, paper edit from transcript |
| `skills/fitness-comedic-cuts/` | Jump-cut rhythm, punch-ins, smash cuts, freeze-frames, speed gags, deadpan holds |
| `skills/fitness-meme-inserts/` | Finding, vetting, timing and compositing GIFs/memes/reaction clips |
| `skills/fitness-transitions/` | Shot-to-shot and chapter-to-chapter transitions |
| `skills/fitness-music-sfx/` | Music beds per section, beat sync, ducking, SFX library, loudness, licensing |
| `skills/fitness-motion-style/` | On-screen graphics design system: macro counters, titles, callouts, stickers |

## Pipeline

Each pass reads the EDL produced by the previous pass and writes a new one (`edl.v1-paper.json` → `edl.v2-rough.json` → …). Keep every version so any pass can be rolled back on its own.

1. **Intake.** Run video-use inventory (transcribe, pack, view samples). Ask: format (long/short/both), the premise, the result or payoff (did they hit the PR? finish the diet?), the user's brand palette and fonts, and any must-keep moments.
2. **Paper edit** (`fitness-script`): beat sheet + hook + gag list mapped to transcript timestamps. **Confirm with the user.**
3. **Rough cut**: assemble the beats. Get the story working with no polish yet. Check the runtime against the target.
4. **Comedy pass** (`fitness-comedic-cuts`): tighten, punch-ins, add the gag beats.
5. **Transition pass** (`fitness-transitions`).
6. **Graphics pass** (`fitness-motion-style`): counters, titles, callouts. Build them as parallel sub-agents.
7. **Meme pass** (`fitness-meme-inserts`): add memes last among the visual passes. They're seasoning and shouldn't be used to cover a scene that doesn't work.
8. **Music + SFX pass** (`fitness-music-sfx`): beds, stings, ducking, loudness.
9. **Captions**: short-form always. Long-form only if the user wants them.
10. **Retention review** (below), then preview render, self-eval (video-use step 7), and present.

## Format targets

| | Long-form (16:9) | Short-form (9:16) |
|---|---|---|
| Runtime | 8–20 min typical | 20–45s (hard cap 60s unless asked) |
| Hook | Cold open, 0–20s, shows the payoff and the stakes | First **1s**: visual + text on screen before any word lands |
| Visual change | Something changes every ~3–6s | Every ~1–2s |
| Gag density | ~1 gag every 20–40s | ~1 every 5–8s |
| Chapters | 4–8 mini-arcs, each with its own hook and payoff | 1 premise, 3–5 beats |
| Ending | Result reveal, then a tag joke, then a quick CTA (≤5s) | Payoff, then a loop point back into the first frame |
| Captions | Optional | Always (big, 1–3 words, centred in the safe zone) |
| Music | Changes per chapter mood | 1 track, cut to its beat |

**Short-form safe zone (1080×1920):** keep text and faces out of the top ~220px and bottom ~380px, and away from the right ~140px where the like and comment buttons sit.

**Long → short repurposing:** find self-contained 20–40s moments in the long-form EDL (one setup and one payoff). Reframe to 9:16 by face-tracked crop and write a new 1-second hook card. Don't just crop the long-form cut.

## Retention review (the "flow" check)

Before showing anything, watch the cut as a bored viewer and read the EDL against this list:

- **Dead air:** any stretch >6s (long-form) or >2s (short-form) with no new information, gag, graphic or angle change? Fix it.
- **Open loops:** does every chapter open a question ("can he finish the 4,000 calories?") and close it? Is there always at least one loop open?
- **Hook honesty:** does the cold open promise something the video actually delivers?
- **Energy curve:** it should rise across the video with dips for breath. Two high-energy chapters in a row with no contrast will wear the viewer out.
- **Repetition:** the same gag type, SFX or transition used 3 times running is a pattern the viewer will notice, so vary it.
- **Numbers on screen:** every number the host says (calories, kg, reps, days) appears as a graphic.
- **Payoff:** the result reveal gets the biggest moment in the video (a beat of silence, then the hit).

Write the review as a short list in `edit/review.md` along with what you changed.

## Render pipeline

`render.py` runs: extract (grade + `fx`) → `transition_in` → concat → `music`/`sfx` mix → overlays → subtitles → loudnorm. It prints the output time of every range, so use those times for overlay `start_in_output`, `music` and `sfx` (transitions shorten the timeline).

- `helpers/fx.py`: range `fx` (punch_in, crash_zoom, shake, freeze, speed). Field reference is in its docstring.
- `helpers/transitions.py`: range `transition_in` (whip, crossfade, dip_black, flash, zoom, wipe, circle, raw xfade, j_cut, l_cut).
- `helpers/audio_mix.py`: top-level `music` and `sfx`, plus ducking and the J/L audio patches.
- `helpers/beats.py <track>`: beat/downbeat/onset grid as JSON.
- `helpers/graphics.py`: brand graphics (title, counter, stamp, popup, arrow, circle, progress, reveal, sticker) as alpha WebM overlays, plus SFX cue files. See `fitness-motion-style`.
- `"caption_style": "brand"` + `--build-subtitles`: brand captions (ASS via libass).
- Overlays accept `rect: [x,y,w,h]`, `tilt` (degrees), `anim: "pop"`, PNG/JPG/WebP stills and alpha WebM.
- Sources with another aspect ratio, rotation or no audio are fitted onto the first range's canvas automatically.

**Captions need an ffmpeg with libass** (`ffmpeg -filters | grep subtitles`). Homebrew's default `ffmpeg` doesn't include it; `ffmpeg-full` does.
