---
name: fitness-music-sfx
description: Music and sound design for fitness/vlog YouTube edits, covering licensed music selection per chapter mood, beat detection and cut-to-beat, sidechain ducking under dialogue, comedic SFX hits (whoosh, vine boom, record scratch, ding), music drop-outs for jokes, and final loudness for YouTube/TikTok. Use during the audio pass of a fitness edit or when the user asks about music.
---

# Music & SFX

In this genre, sound does about half the comedy. Music sets the emotion of each section, and **cutting the music** is often the joke. SFX makes every graphic and gag land.

## Licensing (hard rule)

**Never use commercially released songs** (charts, artists, film scores). They get Content ID claims: lost revenue, muted audio, or blocked videos. Only use:

- **This channel's library: [Free To Use](https://freetouse.com/music).** It's free, and monetized YouTube is allowed **with attribution**. The user downloads tracks from the site (Claude doesn't scrape it) into `<videos_dir>/assets/music/` and tells you the title and artist.
- Anything else must have a licence the user can name. Put the exact required credit in the entry's `credit` field.

**Free To Use attribution:** tag every music entry with `"source": "freetouse", "title": "…", "artist": "…"`. Every render writes `edit/description_credits.txt`:

```
Music from Free To Use
Source: https://freetouse.com/music
<Title> by <Artist>
```

Paste it into the YouTube description **before** the video goes public or unlisted. Free To Use registers its catalogue in Content ID, so a missing credit means a claim. If a claim still arrives, email copyright@freetouse.com with the video link (usually cleared within 24h). A paid Free To Use plan whitelists the channel and removes the attribution requirement. Render warns about any music entry without attribution; don't ship with that warning.

## Music map

Assign a mood per beat in the paper edit, then pick tracks:

| Section | Mood | Typical feel |
|---|---|---|
| Cold open | Tension → hype | Building trap/phonk/electronic, drops on the title |
| Setup / rules | Light, bouncy | Playful pizzicato, quirky hip-hop, lo-fi |
| Eating / food | Comedic, cheeky | Bouncy bass, jazzy, "cooking show" |
| Training / grind | Aggressive | Heavy phonk, drill, rock. Peaks on PR attempts |
| Low point | Sad, ironic | Sad piano or violin, played straight for comedy |
| Ironic epic | Grandiose | Choir, orchestral trailer hits |
| Reveal | Silence → hit | Cut music entirely for 0.5–1.5s, then the biggest drop |
| Outro | Warm, upbeat | Light, returns to the channel's "theme" feel |

- **Change music at chapter boundaries**, on a downbeat, or behind a transition SFX so the change is hidden.
- **Music stops = punchline.** Hard-stop the bed (with a record scratch or just silence) right before a deadpan line.
- **Short-form:** one track, chosen for a strong first 2s; cut the video to its beats.
- Keep a recurring **channel sting** (2–3s, user-owned) for the title card and outro so the brand is recognisable.

## Beat sync

```bash
python helpers/beats.py edit/audio/track.wav --src-start 12.0   # → track.beats.json (tempo, beats, downbeats, onsets)
```

Beat times are relative to `src_start`. Add the bed's `start_in_output` to get output times, then snap cuts, transitions and graphic hits to the nearest beat within ±2 frames.

Snap **hype montages, transitions and graphic slams** to beats. Don't snap dialogue cuts; speech timing always wins (video-use Rule 6).

## SFX kit

**Starter kit (built in):** `video-use/assets/sfx/`, synthesized by `helpers/make_sfx.py`. The channel owns it outright: no licence, no attribution, no claims. Use the bare name in `sfx` entries:

| Name | Use |
|---|---|
| `whoosh`, `swish`, `whoosh_long` | transitions, whips, text swoosh-ins |
| `riser` | 1.6s build into a drop, reveal or hype cut (end it on the hit) |
| `boom`, `slam`, `thud` | reveals and crash zooms / title slams and smash cuts / stamps and landings |
| `pop`, `click` | graphic and sticker entrances / UI |
| `tick`, `ding` | number count-up (0.9s roll) / counter landing, PRs |
| `marker` | arrows and circles drawing on |
| `record_scratch`, `boing`, `bleep` | freeze-frames and music stops / fails / censoring |

`graphics.py` cue names map 1:1 to these. A file with the same name in `<videos_dir>/assets/sfx/` overrides the kit for that project. Add real recordings there as the channel grows: plate clangs, chalk claps and the host's own grunts are funnier than anything synthetic.

Rules: every graphic entrance gets a soft SFX, every gag gets at most **one** featured SFX, and SFX peaks sit at about −6 to −10 dB under dialogue peaks, never louder than the voice. Vary the samples; the same whoosh 20 times sounds cheap.

## EDL fields (`helpers/audio_mix.py`)

`file` is a path or a bare name looked up in `<videos_dir>/assets/music|sfx/`. Times are on the output timeline (render.py prints it). Defaults: music `gain_db` −18, `duck` true, `fade_out` 0.5, `loop` false; sfx `gain_db` −8.

```json
"music": [
  {"file": "edit/audio/cold_open.wav", "start_in_output": 0.0, "end_in_output": 18.4,
   "src_start": 12.0, "gain_db": -18, "fade_in": 0.0, "fade_out": 0.3, "duck": true}
],
"sfx": [
  {"file": "assets/sfx/whoosh_02.wav", "at": 18.27, "gain_db": -8},
  {"file": "assets/sfx/record_scratch.wav", "at": 41.10, "gain_db": -6, "kill_music": true}
]
```

`kill_music: true` hard-stops any bed playing at that moment (with a 20ms fade to avoid a click).

## Mix recipe

render.py mixes automatically after concat (picture lock) whenever `music`, `sfx` or J/L-cuts are present: beds with `duck: true` are sidechain-compressed under dialogue, everything is summed and limited, and the video is stream-copied. To remix only the audio of an existing base, run `python helpers/audio_mix.py edit/edl.json --base edit/base.mp4 -o edit/base_mixed.mp4`.

The **final loudness** pass is render.py's two-pass loudnorm. Targets: **−14 LUFS integrated, −1 dBTP** for YouTube; −14 LUFS for TikTok/Reels/Shorts. Music bed under speech sits around −20 to −24 LUFS (short-form can sit a little hotter).

## Self-check

Listen at every chapter boundary, music drop and SFX. On `timeline_view` waveforms, check that the dialogue stays dominant, there are no clicks at music edits, SFX lands on the visual peak (±1 frame), and the final output measures −14 ±1 LUFS.
