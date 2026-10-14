# Ways of working with Antho

Antho is a hobbyist who wants polished photos and to learn styles; they can't give expert feedback,
so the expertise lives in this skill (styles.md, techniques.md) and the checks are Claude's job.
Pick the mode from the request: "teach me / show me styles / lesson" -> Lesson; "polish these /
make them nice / batch" -> Quick polish; "make it look like this photo" -> Reference.

## Efficient checking (all modes)
Check what can actually go wrong, once, at the right moment. No ritual re-reads.
- Trust tool results for plain sliders; they apply reliably. Don't read settings back after them.
- Verify only the known-fragile steps: AI masks and Denoise (they block Lightroom while computing
  and can drop other edits) and Upright/crop (can be overwritten); verify those once, right before
  the final export, with one `get_photo(include=["masks", "geometry", "enhance"])`.
- One look per stage: an `export_jpeg` at long_edge 1200 gives the image plus stats. Look at the
  image; use the stats against the style's Check line. 100 % crops (`crops=`) only when judging
  noise or sharpening.
- Run AI features one at a time and wait for each tool call to return before anything else.

## Speed benchmark (2026-10-14, funfair set)
Six photo proposals took ~5 minutes: read all photos' current settings in one SDK script
(`develop.getRawSettings`, ~1 s), then per photo one `set_develop` with ~20 keys + `set_tone_curve`
+ one mask + one 1000 px export (~20-30 s), one refinement round where needed. Faster still: decide
from the contact sheet, not from per-photo exports, which photos need a mask.

## Recipe notes from real photos
- Single-colour light on skin (red neon, teal LED): lower that colour's HSL saturation (-10..-20) and
  shift WB slightly away from it; keep the mood, make skin read as skin.
- Matte curves (black point lift 12-18) suit night shots; on bright dusk scenes they look washed out:
  lift <= 6 and add Contrast +20 instead.
- Long-exposure light trails: crush the sky to pure black (Blacks -35, S-curve), no matte, no heavy grain.
- Shooting through glass: a radial over the face with Dehaze +15, Exposure +0.25, Clarity +8 cuts
  the reflection haze locally.
- Strong coloured cast from foreground bokeh: cool WB 4300-4500 K, Highlights -100, Whites -45.
- Style recipes are relative to a well-exposed photo. Many shots arrive dark (night, forest shade):
  first bring p50 near the style's target with Exposure, THEN apply the recipe; 3 of 10 first
  passes were far too dark because the recipe's Exposure was applied to an already-dark file.
- Cooling the WB of a scene that is already blue (blue hour) kills the reds entirely (mean R 7/255):
  check mean_rgb, keep WB >= ~5000 K there.
- B&W without the B&W profile: Saturation -100 plus HSL Luminance per colour works as a B&W mix;
  watch crushed shadows (keep < 2-3 %).
- Black-sky subjects (rides, neon at night) legitimately show 50-80 % clipped shadows: judge the
  subject, not the percentage.
- Never put a call that needs a new virtual copy's ID in the same parallel batch as
  `create_virtual_copy`: wait for the returned ID (the open-photo guard catches it, but it wastes a call).
- Surveying an album: rendering a preview of every raw costs ~2.4 s each (750 photos = 30 min,
  a wasted session). Sample instead: preview every 5th-10th photo (or only the picks/rated ones),
  then render neighbours of interesting frames. Check for existing edits by reading
  Highlights/Shadows/Whites/Blacks/curve only (CameraProfile and Look are always set).
- Measure each pick's brightness (p50) from its preview before editing and set Exposure in the
  first pass: on the Milan/Venice set this removed the fix-up round entirely (9/9 right first time).
- Batch rhythm that worked: edit + snapshot + 900 px export for each photo without looking, then one
  contact sheet, then fix only the outliers (10 photos, 3 fixes, ~15 min).

## Lesson mode
Goal: Antho sees what each step does and learns the vocabulary.
1. Pick the photo with Antho; `create_virtual_copy` per style so the master stays untouched.
2. Snapshot "0 Original" on each copy.
3. Edit in stages, one Snapshot after each, named so they read like a lesson in Lightroom's
   Snapshots panel: "1 Base (profile, WB, lens)", "2 Tone", "3 Colour", "4 Local (masks)",
   "5 Finish (detail, grain, vignette)". Skip stages the photo doesn't need.
4. For each stage, one plain sentence: what changed and why it helps this photo, using the panel
   and slider names Antho will see (e.g. "Highlights -45 brought the clouds back").
5. Offer 2-3 styles that suit the photo (styles.md "Choosing styles") on separate virtual copies,
   export each once, and tell Antho to compare them in Survey view (select copies, press N).
6. Where a technique needs Antho's hands (techniques.md [Antho]), turn it into a small exercise:
   "try Point Color on the jacket: Color Mixer > Point Color > eyedropper".
7. Ask for a simple reaction ("which one? anything too much?") and translate it into settings.
8. Log the outcome in the taste log.

## Quick polish (bulk, low effort)
Goal: good-looking photos without Antho thinking about it.
- Work on virtual copies named "Claude polish" (originals stay untouched, nothing to undo).
- Per photo: read `get_photo(include=["info"])` to classify it (portrait, landscape, city, night,
  IR...) from camera/ISO/time/lens; apply the Clean natural style adapted to the type (night stays
  night, see SKILL.md taste) plus Antho's "my style" for that type if the taste log has one; Denoise
  only above ~ISO 1600; auto Upright "level" only when the horizon is visibly tilted.
- One export per photo at 1200 px with stats; fix only clear failures (clipping, tilt, colour cast).
- Report at the end in one message: which photos, which adaptations, anything Antho should look at.
- Keep it conservative: polish, not restyle. Many photos at once is fine (the old "one photo at a
  time" rule is lifted); still one tool call at a time per photo for AI features.

## Taste log ("my style")
File: `C:\Users\ioman\Documents\Photo Edit\taste-log.md` (living document, not in the repo).
- After each choice Antho makes, append one line: date, photo (file, type, light), styles shown,
  the one chosen, Antho's words, and what was tweaked after.
- "My style" depends on the photo type: when 3+ entries for one type agree, write or update a
  "My style - <type>" block at the top of the log (e.g. "My style - city night") with the settings
  that keep coming back. Use those blocks in Quick polish and as the first suggestion in lessons.

## Reference photos
Folder: `C:\Users\ioman\Documents\Photo Edit\references` (living; Antho drops images there whenever
they find one they like, with an optional note in the file name or a .txt next to it).
- To use one: look at the image, describe its look in style terms (tone: contrast, black point,
  brightness; colour: palette, WB, grading, saturation; texture: grain, sharpness; light: glow,
  vignette), name the closest styles.md entry, then build the recipe on Antho's photo and compare
  side by side with the reference.
- Measure the reference with the same stats when possible (load it with PIL: percentiles, mean RGB)
  so the match is objective, not just by eye.
- If a reference look works well, add it to styles.md as a new style with its recipe.
