---
name: fitness-motion-style
description: The channel's on-screen graphics system for fitness/vlog YouTube: macro/calorie counters, chapter title slams, day stamps, marker arrows and circles, text pop-ups, stickers, progress bars, result reveals and brand captions, rendered by helpers/graphics.py in the channel brand (blue, black, translucent gray panels, Poppins + Space Grotesk). Use during the graphics pass of a fitness edit or whenever building any overlay or caption for one.
---

# Fitness Motion Style

**The brand:** blue, black and translucent gray. Bold Poppins type with an ink stroke sits straight on the footage. Information lives on **translucent gray panels with a blue accent edge**, and the key word or number is in blue. The motion keeps the creator energy (slams, overshoot pops, tilt, marker strokes that draw on), while the palette keeps it clean and on-brand. Don't use other colours, fonts or monospace, and don't build one-off designs outside this system.

## Brand tokens (`video-use/assets/brand.json`)

| Token | Value | Used for |
|---|---|---|
| `display` | Poppins Black | titles, big numbers, stamps |
| `body` | Poppins ExtraBold | pop-ups, captions |
| `heavy` / `light` | Space Grotesk Bold / Medium | panel labels, sub-lines, marker notes |
| `accent_1` / `accent_2` | `#2E7BFF` blue | key words, numbers, arrows, circles, panel edge |
| `accent_3` | `#8CB6FF` light blue | panel labels |
| `ink` | `#0B0B0F` | strokes, shadows |
| `panel` | `#3A3B40` at 62% | every background panel and the caption box |
| `warn` | `#FF3B3B` | only for "over target" on counters |

To change the brand for one project, add `<videos_dir>/assets/brand.json` containing only the keys you change; `graphics.py` and the captions pick it up automatically. To change it for the whole channel, edit the repo file. The brand fonts have **no emoji**, so emoji are stripped with a note.

## Rendering graphics

```bash
python helpers/graphics.py --list                                       # templates + every parameter
python helpers/graphics.py spec.json -o edit/gfx/title.webm             # alpha WebM, full frame
python helpers/graphics.py spec.json -o check.png --still 0.8 --bg frame.png   # one frame on the real shot
python helpers/graphics.py edit/gfx/batch.json                          # {"graphics": [{..., "out": "..."}]}
```

Add `--size 1080x1920` for Shorts. Portrait defaults already keep graphics inside the safe zone. Every render writes `<out>.cues.json` with SFX hits (`pop`, `slam`, `thud`, `tick`, `ding`, `boom`, `marker`). Add each one to the EDL `sfx` at `start_in_output + at`, using the names of your `assets/sfx/` files.

| Template | Use | Key params |
|---|---|---|
| `title` | Chapter title slam, word by word on a panel | `text`, `highlight`, `stagger` |
| `counter` | Macro / calorie HUD card, counts up, red over target | `label`, `from`, `to`, `target`, `sub` |
| `stamp` | `DAY 3` / `7:42 AM` thud-in | `text`, `sub` |
| `popup` | Sarcasm, inner thoughts, contradictions | `text`, `highlight`, `pos` |
| `arrow` | Marker arrow drawing on + note | `from`, `to`, `bend`, `label` |
| `circle` | Marker loop around something | `center`, `radius`, `label` |
| `progress` | Segmented challenge bar | `segments`, `filled`, `start_label`, `end_label` |
| `reveal` | Result number: dim, count, flash, boom | `to`, `suffix`, `label`, `decimals` |
| `sticker` | Cut-out with white border (`cutout: true` runs rembg) | `image`, `height` |

Overlay entry: `{"file": "gfx/title.webm", "start_in_output": 12.4, "duration": 1.79}` (the duration is in the cues file).

**Sync the payoff.** For counters and reveals, set `count_at + count_dur` so the number lands on the spoken word: `start_in_output = word_time - (count_at + count_dur)`.

## Brand captions

Set `"caption_style": "brand"` in the EDL and render with `--build-subtitles`. You get Poppins ExtraBold in uppercase, 2 words per chunk, on one translucent gray box, with the word being spoken in blue and a pop on each new chunk. They sit 30% up in portrait (clear of the Shorts UI) and 10% up in landscape. Tune them under `captions` in `brand.json`. They're always applied last, over every graphic (video-use Rule 1). They need an ffmpeg with libass, which `ffmpeg-full` provides.

## Motion rules

- **Entrances pop or slam** (ease-out-back) with a SFX. **Exits are fast** (4 frames). Never use slow fades or linear easing.
- **One new thing at a time.** Don't land two graphics in the same second.
- **Alternate tilt direction** between consecutive graphics (`tilt`).
- **Every number the host says** (kcal, kg, reps, days) gets a graphic.
- **The reveal is the biggest graphic in the video.** Use it once.

## Gaps (build when a video needs them)

Food label cards (sticker + name + kcal), rep/set tracker badges, before/after polaroid split, and the "don't try this" disclaimer. Add each as a new `tpl_*` in `graphics.py`, using the same `panel`, `text_sprite` and `pop_env` helpers so it matches the rest.

## Brand-consistency check

Before the final render, run `--still` on every graphic with `--bg` set to a frame of its shot, then tile the results (`ffmpeg ... tile=3x3`). Check that they look like one channel made them and that nothing collides with the captions or the Shorts UI.
