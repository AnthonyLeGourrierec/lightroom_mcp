# Style library

Recipes for well-known looks. Values are starting points in `set_develop` slider units, to be
adjusted by eye on each photo: no recipe survives every light. Apply them on top of a clean base
(white balance, exposure, lens corrections done) unless the recipe says otherwise.

Each style lists: **Look** (what makes it recognisable), **Suits / avoid**, **Recipe**, **Local**,
**Check** (targets in `export_jpeg` stats: luminance percentiles p1 / p50 / p99 on 0-255, and
clipping %). Explain the key moves to Antho in plain words when using a style in a lesson.

Sources: Adobe Lightroom Classic help, Fstoppers, Digital Camera World, Photofocus, Matt Kloskowski,
Unique Photo, Imagen and preset vendors (their numbers treated as hints, not truths), plus general
editing practice. Researched 2026-10-14.

---

## 1. Clean natural ("polished, nothing fancy")
Default for Quick polish. Looks like a better version of the scene, never like an effect.
- **Suits:** anything; travel, family, daylight landscapes. **Avoid:** nothing, it is the baseline.
- **Recipe:** profile Adobe Color (or Adobe Adaptive Color if Antho picked it); LensProfileEnable 1,
  AutoLateralCA 1; WB neutral (auto, then by eye); Exposure so p50 lands ~110-130; Highlights -20..-50,
  Shadows +15..+35, Whites/Blacks set the end points (Whites +5..+20, Blacks -5..-20); Texture +5..+10,
  Clarity 0..+8, Vibrance +10..+15, Saturation 0; `set_tone_curve(s_curve=20)`; Sharpness 40,
  SharpenEdgeMasking 40-60.
- **Local:** sky mask Highlights -10..-30 if the sky is bright; subject mask Exposure +0.1..+0.2.
- **Check:** p1 > 4 and p99 < 252 (no crushed blacks or blown whites), clipping < 0.5 %; horizon level.

## 2. Light and airy / high-key
Bright, soft, pastel; shadows open, little contrast. Popular for portraits, food, interiors, beaches.
- **Suits:** bright scenes, white/pastel subjects, soft light. **Avoid:** dark or moody scenes, night.
- **Recipe:** Exposure +0.3..+0.8 (p50 ~150-175), Contrast -10..-25, Highlights -30..-60 (keep detail),
  Shadows +30..+50, Whites +10..+25, Blacks +5..+15; Clarity -5..0, Vibrance +5, Saturation -5..-15;
  LuminanceAdjustment Orange/Yellow +5..+10; slightly warm WB (+200..400 K); tone curve: lift the
  shadow end a little `[[0,10],[64,72],[192,206],[255,250]]`.
- **Local:** subject mask Exposure +0.1, Texture -5 on skin.
- **Check:** p50 150-175, p99 < 250, highlight clipping < 1 % (white dresses and skies keep detail).

## 3. Moody / dark
Rich shadows, muted highlights, earthy desaturated colours; atmosphere over detail.
- **Suits:** forests, overcast, rain, interiors, evening. **Avoid:** bright beach/celebration scenes.
- **Recipe:** Exposure -0.2..-0.5 (p50 ~70-95), Contrast +10..+25, Highlights -40..-70, Shadows -10..+10,
  Blacks -15..-30; Vibrance -5..-10 or Saturation -10..-20; HSL: Green and Yellow saturation -20..-40,
  Green hue +10..+20 (toward olive), Orange saturation -5; colour grading shadows cool (hue ~200-220,
  sat 10-15), highlights warm (hue ~40, sat 8-12); vignette -10..-20.
- **Local:** radial on the light source/subject Exposure +0.2..+0.4 so the eye goes there.
- **Check:** p1 2-8 (deep but not empty), p50 70-95; keep the subject readable.

## 4. Matte / faded film
Lifted blacks that never reach true black; soft contrast; nostalgic.
- **Suits:** lifestyle, street, travel, portraits in soft light. **Avoid:** night skies (looks grey).
- **Recipe:** `set_tone_curve(points=[[0,25],[50,48],[128,128],[200,210],[255,245]])` (raised black
  point, slightly lowered white point); Contrast -5..-15, Clarity -5..0, Saturation -10..-20,
  GrainAmount 15-25, GrainSize 20-30; optional colour grading shadows ~210 sat 8.
- **Check:** p1 ~20-30 by design (that is the look), p99 < 245.

## 5. Warm film (Portra-like)
Soft contrast, peachy skin, warm greens, gentle highlights. The classic "film" look for people.
- **Suits:** portraits, golden hour, travel with people. **Avoid:** cold winter scenes, neon city.
- **Recipe:** WB +300..+600 K and Tint +5..+10; Highlights -30, Shadows +30..+40, Contrast -10;
  curve soft with lifted black `[[0,12],[64,66],[192,198],[255,248]]`; HSL Green hue -10 (warmer),
  Green saturation -15..-25, Orange hue +3..+5 / saturation -5 / luminance +5, Blue saturation -10;
  Calibration RedHue +5, BlueSaturation +10; colour grading highlights hue ~45 sat 8;
  GrainAmount 15-20, GrainSize 25.
- **Check:** skin hue between orange and yellow, not red; p1 ~10-15.

## 6. Cinematic teal & orange
Warm skin and highlights against teal shadows; the Hollywood blockbuster palette.
- **Suits:** city, street, people at golden hour or blue hour. **Avoid:** subjects already orange or
  teal everywhere (it oversaturates), nature-only scenes (green goes odd).
- **Recipe:** colour grading shadows hue ~185-200 sat 15-25, highlights hue ~35-45 sat 10-20,
  Balance -10..+10, Blending 50-70; HSL Blue hue -15..-30 (toward teal), Aqua hue -10, Orange
  saturation +5..+10, Green saturation -20; Contrast +10..+20; optional Calibration BlueHue -20,
  BlueSaturation +20; vignette -10.
- **Check:** skin stays natural (not orange-red); shadows teal, not cyan-green.

## 7. Golden hour glow (and Orton-style soft glow)
Warm, glowing light; soft highlights that bloom.
- **Suits:** sunset/sunrise, backlit portraits, landscapes. **Avoid:** midday flat light (looks fake).
- **Recipe:** WB +300..+800 K; Highlights -20, Whites +10; Dehaze -5..-15 (adds glow); Clarity -10..-20
  for the glow version (Orton approximation: Texture -10, Clarity -30..-50, Dehaze -10, then add
  Contrast +10 and Exposure +0.1 back; keep it at 5-10 % strength in spirit); colour grading
  highlights hue ~40 sat 15, midtones hue ~35 sat 5.
- **Local:** radial over the sun Exposure +0.3, Temperature +10, Dehaze -15 (glow at the source).
- **Check:** highlight clipping only in the sun itself; no orange skin.

## 8. Vibrant landscape ("punchy but believable")
Rich colour and depth without neon.
- **Suits:** landscapes, mountains, seascapes. **Avoid:** portraits (skin goes harsh).
- **Recipe:** profile Adobe Landscape or Adaptive Color; Highlights -40..-70, Shadows +25..+50,
  Whites +10..+25, Blacks -10..-25; Texture +10..+20, Clarity +5..+15, Dehaze +5..+15 (sky/distance
  only via mask is better); Vibrance +15..+25, Saturation 0..+5; Calibration BlueSaturation
  +15..+40 (enriches all colours, see techniques); `set_tone_curve(s_curve=30)`.
- **Local:** sky mask Highlights -20, Saturation +5, Dehaze +10; landscape/foreground mask
  Exposure +0.2, Texture +10; linear gradient to darken the top edge.
- **Check:** no saturation clipping in sky (blue stays blue, not cyan); p1 > 3.

## 9. Night city / blue hour (Antho: keep it dark)
Inky but clean night, coloured lights glowing, true to the evening.
- **Suits:** city at night, blue hour, neon streets. **Avoid:** lifting to daylight brightness.
- **Recipe:** WB 3800-4500 K (keep some warm sodium light against a blue sky); Exposure only enough
  that p50 ~45-70; Highlights -40..-70 (signs and lamps keep shape), Shadows +10..+25, Blacks -10..-20;
  Dehaze +5..+10 (cuts light-pollution haze); Clarity +5; Vibrance +10; HSL Orange saturation -10 if
  lamps are too orange, Blue luminance -10 for a deeper sky; denoise ~20-30 then GrainAmount 10.
- **Local:** subject/landmark mask Exposure +0.2..+0.4; radial vignette inverted Exposure -0.2.
- **Check:** p50 45-70 (it must stay night), p1 1-6, lamps may clip slightly (< 1 %).

## 10. Documentary black & white
Honest, contrasty monochrome; tonal separation instead of colour.
- **Suits:** street, people, architecture, harsh light, cluttered colour. **Avoid:** scenes whose
  point is colour.
- **Recipe:** profile Adobe Monochrome (or Adaptive B&W); then `set_develop` GrayMixer to separate
  tones: GrayMixerBlue -15..-30 (darker sky), GrayMixerOrange/Red +5..+15 (lighter skin),
  GrayMixerGreen +10 (foliage); Contrast +15..+30, Clarity +10..+20, Whites +15, Blacks -15..-25;
  `set_tone_curve(s_curve=35)`; GrainAmount 20-30, GrainSize 25-35; vignette -10..-15.
- **Local:** dodge/burn with brushes (subject Exposure +0.2, edges -0.2) rather than global moves.
- **Check:** a true black and a true white exist (p1 < 8, p99 > 240) unless going for a soft look.
  Keep sky darkening believable for documentary work.

## 11. Candid film / CCD digicam (Antho likes this)
Early-2000s compact camera: a bit underexposed, punchy-but-cheap colour, flash-like contrast,
visible grain, matte blacks.
- **Suits:** casual snapshots, friends, parties, street, night with flash. **Avoid:** fine landscapes.
- **Recipe:** Exposure -0.2..-0.4; Contrast +15..+25; curve with matte black
  `[[0,18],[60,50],[190,205],[255,250]]`; Saturation +5..+10 with Blue/Aqua hue -10 (cyan cast),
  or a cool WB (-300 K) for the CCD look; colour grading shadows hue ~200 sat 10, highlights
  hue ~45 sat 10 (teal/amber); Sharpness 60-70, SharpenRadius 0.8 (crunchy); Texture +10;
  GrainAmount 25-35, GrainSize 30-40, GrainFrequency 50; vignette -15.
- **Check:** p1 ~15-20 (matte), slightly dark p50 ~95-115.

## 12. Infrared looks (classic white/cyan, Aerochrome, Goldie, IR B&W)
See the Infrared section of SKILL.md: those recipes depend on Antho's custom profiles.

---

## Visual reference
`C:\Users\ioman\Documents\Photo Edit\style-gallery\style_gallery_IMG_9791.jpg` shows styles 1-11 (and
Antho's funfair B+C mix) on one daylight portrait; the virtual copy "Claude style gallery" of
IMG_9791 holds them as snapshots "Gallery 00..11" to click through. Lessons from it:
- HueAdjustmentBlue toward teal (-15..-20) turns a DAYLIGHT blue sky cyan (teal & orange, CCD,
  B+C mix). On daylight scenes mask the sky out or leave Blue hue at 0; the shift suits night/city.
- Golden glow's negative Dehaze/Clarity also fades a clear blue sky; keep it for backlit/low sun.

## Choosing styles to show in a lesson
Pick 2-3 that genuinely differ AND suit the photo: for a portrait in soft light, Warm film vs Light
and airy vs Documentary B&W; for a landscape, Vibrant landscape vs Moody vs Golden glow; for a
city at night, Night city vs Cinematic vs CCD digicam. Never show a style the "Avoid" line rules out.
