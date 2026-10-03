---
name: fitness-meme-inserts
description: Find, vet, time and composite reaction GIFs, memes, stickers and short cutaway clips into fitness/vlog edits, covering full-screen cutaways, corner pop-ins and cut-out stickers. Use during the meme pass of a fitness edit or whenever the user asks to "add a GIF/meme here".
---

# Meme & GIF Inserts

A meme insert is a **reaction shot borrowed from the internet**. It belongs where the viewer would otherwise react themselves: disbelief at the calorie number, pain on the last rep, smugness at a PR. It never replaces a missing joke.

## Placement modes

| Mode | Duration | Use |
|---|---|---|
| **Full-screen cutaway** | 0.6–2.0s | The main reaction beat. Hard cut in, hard cut out (or a whip). Audio from the meme only if it's iconic; otherwise use a SFX |
| **Corner pop-in** | 1–3s | Side commentary while the host keeps talking. ~30–40% width, scale in with overshoot, white stroke + drop shadow, tilt 3–6° |
| **Sticker** | 1–3s | Transparent cut-out (person/object) slapped on screen. Use `rembg` (installed in the venv) on a still, then animate with pop + wobble |
| **Green-screen key** | variable | Classic meme overlays with a green background: `colorkey=0x00FF00:0.3:0.1` |

**Density:** long-form ≤1 meme per ~45s. Short-form ≤2 per video. Never two in a row.

## Selection rules

1. **Read the moment first.** Write the reaction in plain words ("disbelief", "pain but proud", "this is fine") *before* searching.
2. **Recognisable in <0.5s.** If it needs explaining, it's the wrong meme.
3. **Matches the host's energy.** Self-deprecating video, so self-deprecating memes.
4. **Not dated or cringe.** Prefer evergreen reactions. Ask the user if unsure, since their audience age matters.
5. **No punching down.** No memes that mock bodies, ethnicities, disabilities, or real private people.

## Sources (in order of preference)

1. **User's own library**: `<videos_dir>/assets/memes/` with a `tags.json` (`{"file": "...", "tags": ["disbelief","shock"], "source": "...", "license": "..."}`). Build this up over time; it's the most reliable source and keeps the channel's style consistent.
2. **Own footage:** a reaction shot of the host themselves reused as a running "meme" works better than anything external, and builds a channel in-joke.
3. **GIPHY API** (`api.giphy.com/v1/gifs/search`, needs `GIPHY_API_KEY` in `.env`). Request the `mp4` rendition, not the gif. Record the GIPHY URL and the content creator in `tags.json`.
4. **Stock/meme-licensed libraries** the user subscribes to.

**Copyright caveat:** reaction clips from films, TV and sports are copyrighted. Short, transformative commentary use is common on YouTube, but it's a Content ID and claim risk, *not* a guarantee. Flag any clip from a major studio or broadcaster to the user, and never use more than ~2s of it. Never pull from a source the user can't name.

Download into `edit/memes/` and log every insert's source in `edit/memes/credits.md`.

## Prep (always)

```bash
# GIF/WebP → constant-frame-rate MP4 matching the project (no GIF goes straight into render)
ffmpeg -i in.gif -vf "fps=30,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p" -c:v libx264 -crf 18 -an meme_01.mp4

# Loop a short GIF to fill N seconds
ffmpeg -stream_loop -1 -i meme_01.mp4 -t 1.6 -c copy meme_01_1.6s.mp4

# Sticker cut-out (transparent) from a still
.venv/bin/rembg i still.png sticker.png
```

For full-screen cutaways with a different aspect ratio, prefer a **blurred-fill background** over black bars: `split[a][b];[a]scale=1920:1080,boxblur=30[bg];[b]scale=-2:1080[fg];[bg][fg]overlay=(W-w)/2:0`.

## Style for pop-ins and stickers

Follow `fitness-motion-style`: white 8–12px stroke, hard drop shadow, 3–6° tilt, scale-in 0→1.1→1.0 over 6–8 frames (ease-out-back), plus a "pop" SFX. Exit is a quick scale-down (4 frames) or a hard cut.

## EDL usage

**Full-screen cutaway** = a normal range. Add the meme to `sources` and give it a range between the host's ranges. Any aspect ratio is letterboxed onto the canvas, and silent GIF-MP4s get silence. Add its SFX in `sfx`. To keep the host talking underneath, give the meme range `"transition_in": {"type": "l_cut", "lag": <meme length>}`.

```json
"sources": {"meme_disbelief": "edit/memes/meme_01.mp4", ...},
"ranges": [..., {"source": "meme_disbelief", "start": 0, "end": 1.6, "beat": "CH2/G5",
                 "reason": "Reaction to 4,200 kcal reveal"}, ...],
"sfx": [{"file": "vine_boom", "at": 74.3, "gain_db": -6}]
```

**Corner pop-in / sticker** = an overlay (PTS-shifted per video-use Rule 4, under subtitles per Rule 1). `rect` is the box it's fitted and centred in, `tilt` is in degrees, and `anim: "pop"` gives an ease-out-back scale-in. PNG/WebP stills and alpha WebM work.

```json
"overlays": [{"file": "edit/memes/sticker_flex.png", "start_in_output": 112.0, "duration": 2.0,
              "rect": [1280, 120, 520, 520], "tilt": -4, "anim": "pop"}]
```

If a pip and a caption collide, move the pip.
