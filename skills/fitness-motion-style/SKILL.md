---
name: fitness-motion-style
description: Design system and build briefs for on-screen graphics in fitness/vlog YouTube, covering macro and calorie counters, rep/weight trackers, day and time stamps, chapter title slams, hand-drawn callouts, text pop-ups, cut-out stickers and result reveals, styled as bold creator-energy graphics rather than clean tech/terminal UI. Use during the graphics pass of a fitness edit or whenever building any overlay animation for one.
---

# Fitness Motion Style

The look is **loud, tactile and handmade**: thick type, stickers, marker scribbles, paper and tape, things that slam in and wobble. It should feel like a creator cut it together with personality. It should *not* feel like a SaaS dashboard, a terminal, or a corporate lower-third.

This **replaces** video-use's example palette (near-black + orange Menlo). Don't use monospace fonts, thin lines, dark glassmorphism, gradients-on-black, or anything that reads "dev tool".

## Design tokens (default — swap for the user's brand)

Confirm or replace these at intake. Store the confirmed version (as plain JSON, comments stripped) in `<videos_dir>/assets/brand.json` and reuse it on every video.

```jsonc
{
  "font_display": "Anton",              // tall condensed, all-caps titles & numbers
  "font_display_alt": "Bebas Neue",
  "font_body": "Montserrat ExtraBold Italic", // pop-up text, captions
  "font_hand": "Permanent Marker",      // scribbles, annotations
  "white": "#FFFFFF",
  "ink": "#111111",                      // strokes, shadows
  "accent_1": "#FFE600",                 // highlight yellow — numbers, key words
  "accent_2": "#FF2E2E",                 // red — arrows, circles, warnings
  "accent_3": "#2EE6A6",                 // optional third — "good" / protein
  "stroke_px": 10,
  "shadow": {"x": 6, "y": 8, "blur": 0, "color": "#111111"},
  "tilt_range_deg": [-6, 6],
  "texture": "paper"                     // paper grain / tape strips on cards
}
```

Fonts: Anton, Bebas Neue, Montserrat and Permanent Marker are all free on Google Fonts (OFL). Download them into `assets/fonts/` on first use. Impact is on the system as a fallback.

## Motion language

- **Entrances slam:** scale 0 → 1.12 → 1.0 over 6–8 frames (ease-out-back, overshoot ~1.6), plus a 2–3 frame shake on landing and a SFX. Text can come in word by word, each word slamming.
- **Idle:** a subtle wobble (±1° rotation, 2–3s period) or a 1–2% scale "breathe", so the graphic doesn't sit dead.
- **Exits:** fast. Scale to 0 in 4 frames (ease-in-back) or a hard cut. Never a slow fade.
- **Numbers count up** with ease-out and a tick SFX, ending in a bounce + "ding". Apply video-use's payoff sync so the final number lands on the spoken word.
- **Hand-drawn elements draw on:** an arrow or circle path draws in 6–10 frames with marker texture and slight jitter (re-randomise the path every 2–3 frames for a "boiling line" look).
- **Things are tilted.** Nothing sits at a perfect 0°. Alternate the tilt direction between consecutive graphics.
- **Easing:** never linear (video-use rule). Use ease-out-back for entrances, ease-in-back for exits, ease-out-cubic for counters.

## Graphic catalog

| Graphic | Spec |
|---|---|
| **Macro / calorie HUD** | Persistent corner card (top-left in 16:9, safe-zone in 9:16): `KCAL 1,240 / P 98g · C 140g · F 40g`. The number counts up on each meal. Paper card, tape strip, slight tilt. Turns red when it goes over the target |
| **Food label card** | Per meal/food: cut-out photo of the food (rembg) + name + kcal in yellow. Slams in beside the food, 2–3s |
| **Day / time stamp** | `DAY 3` big + `7:42 AM` small, stamped on with a thud, at chapter starts |
| **Chapter title slam** | Full-width Anton, word by word on the downbeat, over a blurred/darkened freeze of the shot. 1.2–2s |
| **Rep / set / weight tracker** | `SET 3/5 · 140 KG` plate-shaped badges; the rep count ticks on each rep (time it to the rep in the footage) |
| **Callout arrow / circle** | Red marker arrow + 1–3 word Permanent Marker note ("HIS FORM 💀"). Points at the subject. Tracks roughly if the subject moves |
| **Text pop-up** | Montserrat ExtraBold Italic, white with ink stroke, yellow on the key word. For contradictions, inner thoughts, sarcasm |
| **Sticker** | Cut-out of the host's face/body (rembg) with a thick white border; used for reactions or thumbnail-style moments |
| **Before / after split** | Two tilted polaroid frames, a stamped date on each, slamming in one after the other |
| **Result reveal** | Black/blur, then the number counts in huge (60% of frame height), then hits with a flash + the biggest SFX of the video. Hold ≥1.5s |
| **Progress bar** | Chunky segmented bar (Day 1 ▮▮▮▯▯ Day 5) for multi-day challenges, at chapter transitions |
| **"Don't try this" disclaimer** | Small, readable, not jokey, 2–3s, for genuinely risky content |

**Short-form captions** use this system too: Montserrat ExtraBold Italic or Anton, 1–3 words, white with a 10px ink stroke, the key word in yellow (or slammed bigger), placed centre-low inside the safe zone. They're still applied last (video-use Rule 1).

## Build engine

- **HyperFrames** (HTML/CSS/GSAP), the default for these graphics. CSS gives you real text strokes, shadows, textures and `back.out` easing for free, and renders to transparent WebM (`--format webm`) for overlays.
- **PIL + PNG sequence** for very simple counters if HyperFrames isn't installed.
- Bring the same CSS file (`assets/brand.css`, generated from `brand.json`) into every slot so all graphics match.

Every slot is its own sub-agent (video-use Rule 10: parallel). Add these to the brief:
- The `brand.json` values, verbatim, with absolute font file paths
- The output: **transparent WebM** (VP9 + alpha) at the project resolution/fps, or MP4 if it's full-screen
- The motion language bullets above, verbatim
- An anti-list: *"No monospace, no dark-UI panels, no thin lines, no gradients on black, no linear easing, no slow fades, no emojis unless specified, nothing perfectly level."*
- The exact numbers/text and the payoff timestamp to land on

## Brand-consistency check

Before the final render, extract one frame from each graphic and tile them in a contact sheet (`ffmpeg ... tile=4x3`). Do they look like one channel made them (same fonts, stroke, shadow, palette)? Fix any outliers.
