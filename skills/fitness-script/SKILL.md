---
name: fitness-script
description: Write scripts and paper edits for comedic fitness YouTube videos: premises, cold-open hooks, chapter beat sheets, gag lists and shot lists, either before filming or reconstructed from raw footage transcripts. Use for long-form or short-form fitness, diet, gym-challenge and transformation content.
---

# Fitness Script & Paper Edit

There are two modes, and the same structure applies to both:

- **Pre-production:** the user has an idea but no footage yet. Output a script and shot list they can film from.
- **Post-production (paper edit):** the user has footage. Output a beat sheet whose lines point at transcript timestamps in `takes_packed.md`. This is what the rough cut is built from.

For generic YouTube retention writing, `youtube-script-writer` is also available. This skill covers what's specific to the fitness-comedy genre.

## 1. Premise

A good premise works as a title and a thumbnail on its own and has a **measurable outcome**. Proven shapes:

- **Live like X:** "I ate / trained like [athlete, celebrity, character] for 24h / 7 days"
- **Extreme constraint:** "Only [food] for a week", "100 push-ups every time I [trigger]"
- **Test it:** "I tested viral gym hacks / supplements / diets", with a verdict on each
- **Versus:** "Me vs. [pro / older relative / 1-year-ago me]"
- **Transformation:** "X days to [goal]" with a weigh-in or PR reveal
- **Infiltration:** "Pretending to be a beginner at an elite gym" (prank-adjacent; get consent from anyone filmed)

Write the premise as one sentence, plus the **stakes** (what's hard about it or what could go wrong), plus the **payoff** (the number or moment we're waiting for).

## 2. Hook

**Long-form cold open (0–20s):**
1. Visual in the middle of the action (the hardest or funniest moment, shown out of context)
2. Premise in one line, with the number on screen
3. Stakes, or a moment from late in the video ("by day 3 I was…")
4. A promise ("…and the results genuinely shocked me"), then the title card or a straight smash cut into chapter 1

**Short-form (0–1s):** the first frame is already mid-action, the premise is already on screen as text, and there's no "hey guys". The spoken hook goes ≤7 words in.

## 3. Beat sheet (long-form)

```
COLD OPEN    → hook (see above)
SETUP        → rules of the challenge, the plan, the "how bad can it be"
CHAPTER 1..N → each = mini-hook → attempt → complication → gag → micro-payoff
               (e.g. each meal / each workout / each day)
MIDPOINT     → twist or low point (failure, injury scare, cheat temptation)
CLIMAX       → final test: weigh-in, max lift, last meal, race
REVEAL       → the number, given room to land
TAG          → one last joke after the "real" ending
CTA          → ≤5s, said in character, never a hard sell
```

Each chapter **opens with a question and closes it**. At least one larger loop (e.g. "will I make the weight?") stays open across all chapters until the reveal.

## 4. Gag list

Write gags **into** the script; don't leave them to be found in the edit. Tag each with the technique from `fitness-comedic-cuts` so the editor knows how to deliver it:

```
G1  [smash-cut contradiction] "I'll just have one bite" → empty plate
G2  [freeze-frame + VO]       mid-bench grimace → "this is when I realised…"
G3  [ironic slow-mo + choir]  cracking an egg like it's the Olympics
G4  [speed-up]                40 min of meal prep in 6s
G5  [meme cutaway]            reaction to the calorie total
G6  [text contradiction]      "I'm not even tired" / text: (he was tired)
```

Aim for at least one gag per chapter that's planned and filmed on purpose.

## 5. Output formats

**Pre-production script:** two columns, A/V:

| Time | VISUAL (shot / graphic / meme / SFX) | AUDIO (dialogue / VO / music) |
|---|---|---|

Then a **shot list** grouped by location (e.g. kitchen, gym, car), with the B-roll each chapter needs: food close-ups, plate-weight close-ups, gym establishing shots, reaction shots, "empty plate" payoff shots. Remind the user to film **payoff shots for every setup**, plus 2–3s of handles before and after each line.

**Paper edit:** a markdown beat sheet saved to `edit/paper_edit.md`:

```
## CH2 — Breakfast (target 1:10)
HOOK   C0042 [012.40-015.10] "Six eggs. Before 7am."      + GFX: macro counter starts
BEAT   C0042 [031.00-038.20] cracking eggs                 + G3 ironic slow-mo
GAG    C0043 [004.10-006.00] "honestly not that bad"       → smash cut C0044 [020.0-023.5] gagging
PAYOFF C0044 [041.20-044.00] "...that's 540 calories"      + GFX counter → 540, SFX ding
```

Then turn it into the v1 EDL using the video-use format, with `beat` set to the chapter and gag id.

## 6. Writing voice

- Self-deprecating, never mean toward other people. The host is the butt of the joke.
- Short sentences. Spoken rhythm. Contractions.
- Numbers are specific ("3,847 calories", not "a lot").
- Exaggerate the feeling, never the result. The reveal has to be true, because faked results lose trust.
- Health and safety: extreme diet or training content gets a brief on-screen "don't do this / consult a professional" note where it's actually risky. Never present a crash diet as advice.

**Confirm the paper edit with the user before any cutting starts.**
