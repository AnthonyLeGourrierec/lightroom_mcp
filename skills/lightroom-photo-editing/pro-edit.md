# The finished edit: process (read before any "portfolio" / "finished" edit)

Antho's own workflow, made rigorous with the method of the "pro edit" skill from
[lightroom-ai-bridge](https://github.com/aslanoov/lightroom-ai-bridge) (MIT, Mustafa Aslanov),
itself synthesized from Adobe guidance, Fstoppers, PetaPixel, Michael Frye and Van Hurkman's
Color Correction Handbook. Antho's taste (`taste-log.md`) wins every conflict.

Why this exists: on 2026-10-15 Antho reviewed 40 proposals. The common faults were process
faults, not tool limits: no clear subject, weak crops, small "random" masks, noise left in,
looks applied to the photo instead of derived from it. Every step below targets one of those.

## The role
Think in problems, never in sliders: "the eye drifts to the bright water", "green cast in the
shadows". Two hats, never at once: the technician (is it accurate?) then the artist (what should
it feel like?). At the end a third, the inspector, who treats the result as someone else's work.

**Law of attention:** the eye goes to the brightest, sharpest, most contrasty, most saturated
area. That area must be the subject. Lift the subject, darken the competition, seal the edges.

**Quality bar:** a grade is felt before it is seen. If the edit is noticed before the subject,
it failed: dial the strongest move back 20-30 %.

## 0. Look and reset
Reset the virtual copy (Antho may have edited it), restore an IR profile if needed
(`copy_settings`), render it, and study the render, its histogram numbers and its noise at 100 %.

## 1. The brief (written before any slider, shown to Antho in the report)
- **Subject and story** in one sentence.
- **Eye path:** where the eye enters, where it lands, what currently steals attention.
  Measure it: `tools/lightroom_ai_bridge/attention_check.py render.jpg --region subject:L,R,T,B`
  (fractions of the frame). The subject should win or nearly win on luma and saturation.
- **Defects:** tilt (`measure_tilt.py`; correct at >= 0.5 deg), cast, clipping, noise, edge intrusions.
- **Intent sentence:** how the finished photo should feel, amplifying the real light, never
  inventing it. This sentence is the acceptance test.
- **What NOT to touch** (e.g. "do not lift the shadows, they are the drama").

## 2. Frame (Antho's step 1)
Crop and straighten early, near-final: every later judgement (histogram, masks) is made on the
frame that ships. Reason the crop out loud (thirds, lead room, remove the edge distraction),
render, compare, keep or revert. Native orientation unless there is a reason.

## 3. Denoise (Antho's step 2)
High ISO: AI Denoise first, enough to look clean at 100 % (about 35-45 at ISO 3200+), before any
AI mask. Low ISO: Raw Details or a small amount. No added grain on denoised photos.

## 4. Correction (Antho's step 3)
Exposure roughly right, then white balance, then exposure again. Then maximise the range:
recover Highlights / open Shadows first (they drag the end points), then Blacks as low and Whites
as high as possible without clipping what matters (skin, sky, clouds must not clip; speculars may).
Commit to a register: decisively low-key or high-key beats a muddy middle.

## 5. Presence (Antho's step 4)
Texture, Clarity, Dehaze with restraint; re-check WB after Dehaze. Vibrance before Saturation.

## 6. Tone curve (Antho's step 5)
Shape the range you now have into the one you want (contrast in the midtones, how deep the
blacks sit). Antho likes contrast and pop; matte only when the photo calls for a vintage vibe.

## 7. Masking: shape attention (Antho's step 6)
Global is locked; now build the focal hierarchy, structural planes first (sky, subject,
background). The two moves, in order of value:
1. **Darken the competition:** inverted subject mask or the background mask, Exposure -0.2..-0.5,
   or a burn brush on the brightest rival named in the brief.
2. **Lift the subject:** AI subject/people mask, Exposure +0.15..+0.35, a touch of Clarity.
Build with several gentle masks rather than one strong push. Every mask must answer a problem
named in the brief; no decorative radials. Re-run `attention_check.py`: the subject must win.
Watch halos on hard edges. AI masks first, gradients and brushes after (see SKILL.md gotchas).

## 8. Colour mixer (Antho's step 7)
Palette discipline, hue -> saturation -> luminance: pull neighbouring colours into 2-3 families,
mute colours that distract rather than boosting heroes, use luminance to direct attention.
Skin lives in orange and is fixed with WB and local work, not the mixer. IR: keep it surreal.

## 9. Colour grading (Antho's step 8, only if it serves the intent)
On top of a correct base: shadows first, then highlights, then midtones; saturation low
(5-15 shadows/highlights, 0-8 midtones); warm/cool separation from the scene's real light.
Memory colours must survive: skin R > G > B, believable sky and foliage, neutrals neutral
(IR excepted, where surreal is the point).

## 10. Detail
Sharpening judged now, at real scale, with edge masking; no output sharpening (that is export).

## 11. The inspector
Render, read it as someone else's work:
- Before/after: same place and light, only clearer in purpose. Reads instantly as edited? Back off
  the strongest move 20-30 %.
- Intent test: delivers the brief's sentence and nothing it did not ask for.
- Eye path: first, second, third landing points; the subject must win (`attention_check.py`).
  Edge patrol: no half-cut figures, no bright slivers pulling the eye out.
- Clipping, memory colours, noise at 100 %, halos and banding on hard edges and smooth skies.
- Would Antho prefer the original? If the edit doesn't clearly beat it, say so instead of
  proposing it.
Then snapshot ("<photo> final"), and report: the brief, what each step did and why, the QC result.

## 12. Learn
Antho's reaction to each edit goes into `taste-log.md` (with numbers when useful); patterns seen
on 3+ photos of one type become a "My style" rule. Corrections beat this file.
