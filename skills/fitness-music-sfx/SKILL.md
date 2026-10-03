---
name: fitness-music-sfx
description: Music and sound design for fitness/vlog YouTube edits, covering licensed music selection per chapter mood, beat detection and cut-to-beat, sidechain ducking under dialogue, comedic SFX hits (whoosh, vine boom, record scratch, ding), music drop-outs for jokes, and final loudness for YouTube/TikTok. Use during the audio pass of a fitness edit or when the user asks about music.
---

# Music & SFX

In this genre, sound does about half the comedy. Music sets the emotion of each section, and **cutting the music** is often the joke. SFX makes every graphic and gag land.

## Licensing (hard rule)

**Never use commercially released songs** (charts, artists, film scores). They get Content ID claims: lost revenue, muted audio, or blocked videos. Only use:

- The user's subscription library (Epidemic Sound, Artlist, Musicbed, Soundstripe…), with the channel whitelisted
- YouTube Audio Library (check each track's attribution requirement)
- Royalty-free or CC0 tracks with the license recorded
- AI-generated music from a service whose terms grant commercial use (record which one)

Ask the user which library they use at intake. Log every track and SFX in `edit/audio/credits.md` with its license.

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

Store it in `<videos_dir>/assets/sfx/` (reused across videos) with `sfx.json` tags. Core set:

- **Movement:** whoosh (short/long), swish, riser, reverse-cymbal
- **Impact:** boom/sub drop, punch, "vine-boom-style" bass hit, glass/metal clank (plates!)
- **Comedy:** record scratch, cartoon boing, slide whistle, crickets, sad trombone, bonk, bleep
- **UI/graphics:** pop, click, ding/cash register (calorie counters), typewriter tick, swoosh-in for text
- **Gym:** plate clang, chalk clap, grunt (filmed by the host, the funniest option)

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
