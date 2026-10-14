# Lightroom Classic techniques (tips and tricks)

Antho's Lightroom Classic is 15.3 (checked 2026-10-14). Each tip says who can do it:
**[Claude]** through the MCP tools, or **[Antho]** by hand in Lightroom (the SDK can't reach it).
When a lesson would benefit from an [Antho] tip, tell Antho exactly where to click; that is part of
the learning. Sources: Adobe Lightroom Classic help and release notes, Fstoppers, Photofocus,
Digital Photography School, Matt Kloskowski, PhotoshopCAFE, Julieanne Kost. Researched 2026-10-14.

## Order of work (the one thing that saves the most time)
1. **Profile first** [Antho picks / Claude copies]: the profile sets the colour foundation; masks and
   grading built on another profile need redoing. Adaptive profiles must come before masks.
2. **AI Denoise second** [Claude, `set_enhance`]: Adobe recommends Denoise before AI masks and
   Content-Aware Remove because they are computed from the denoised pixels; denoising later makes
   Lightroom recompute them (one review measured 4x longer). Skip on low-ISO photos.
3. **AI masks third** [Claude, `add_mask` kind sky/subject/...]: while an AI mask or Denoise is
   computing, Lightroom does not accept other edits, and when it finishes it rewrites the mask list,
   dropping masks added meanwhile (seen in our testing). So: one AI feature at a time, wait for
   the tool to return, then continue. Never batch other edits "in parallel" with AI work.
4. **Global tone and colour** [Claude, `set_develop`, `set_tone_curve`, `set_color_grading`].
5. **Gradients, radials, brushes** [Claude, `add_mask` linear/radial/brush].
6. **Geometry** (Upright, crop, straighten) [Claude, `set_geometry`] can go anywhere, but crop last
   if vignettes or radials depend on the frame.
7. **Detail and finishing**: sharpening, grain, vignette [Claude, `set_develop`].

## Profiles
- **Adaptive Color / Adaptive B&W** [Antho] (LrC 14.2+, raw only): AI profile that balances the photo
  per image, amount 0-200. Great first step for a quick polish. Don't combine with Auto Tone
  (Adobe warns of unpredictable results). Weak spot: greens.
- **Adobe Landscape / Portrait / Vivid / Monochrome**, camera-matching profiles (e.g. Fujifilm film
  simulations on Fuji raws, Canon "Camera Faithful") [Antho, or Claude via `copy_settings` from a
  photo already using it]. Profile choice is often half of a style.
- Profile **Amount** slider can soften a strong profile instead of fighting it with sliders.

## Tone
- **Set the end points with Whites/Blacks**, not Exposure: Exposure places the midtones (p50),
  Whites/Blacks set p99/p1. Contrast, Texture, Clarity and Dehaze move the end points again, so
  check them last. [Claude]
- **Tone curve vs Contrast**: a gentle S-curve (`s_curve` 20-35) gives richer contrast than the
  Contrast slider; lifting the left end of the curve gives the matte/film fade. [Claude]
- **Parametric curve sliders** (ParametricShadows/Darks/Lights/Highlights) are a safe way to shape
  one tonal band without touching the point curve. [Claude]
- **Dehaze, negative**: -5..-20 adds atmosphere, mist or glow; positive cuts haze but darkens and
  cools the image, so re-check exposure and WB; +10..+30 covers most scenes. Better applied in a
  sky/background mask than globally. [Claude]
- **Orton-style glow**: Texture and Clarity strongly negative (-40..-80 in a mask, less globally),
  then add some Contrast and Exposure back; use sparingly. [Claude]

## Colour
- **Calibration Blue Primary saturation** (BlueSaturation +15..+50): the photographers' favourite
  trick; enriches nearly every colour (most colours contain some blue), more natural than
  Saturation. Use early. RedHue/BlueHue shift whole families of colour. [Claude]
- **HSL in moderation**: shift hues before pushing saturation; desaturating greens (-15..-30) is the
  quickest "pro" look on landscapes and portraits; skin lives in Orange (and Red). Keep skin hue
  natural: Orange luminance +5 brightens skin gently. [Claude]
- **Colour grading**: shadows and highlights in complementary hues (teal ~200 / amber ~40) at low
  saturation (5-20) is the cinematic base; Blending widens the overlap, Balance chooses which wins.
  [Claude, `set_color_grading`]
- **White balance as a creative tool**: warmer for nostalgia, cooler for calm/night; on IR the main
  knob. [Claude]
- **Point Color** [Antho] (Color Mixer panel and inside masks): pick a colour with the eyedropper and
  shift its hue/saturation/luminance precisely, e.g. fix one jacket or the skin only within a person
  mask. More precise than HSL bands.

## Masks
- **AI masks** [Claude]: sky, subject, background, people, objects, landscape. LrC 15.0 added a Snow
  element in Landscape masks. People masks split into skin, brows, eye whites, iris, lips, teeth,
  hair, clothes [Antho for the parts; the tool currently creates whole masks].
- **Invert the subject mask** instead of "background" when the background mask is poor. [Antho]
- **Radial dodge and burn**: a soft radial at Exposure +0.2..+0.3 on the subject and an inverted one
  at -0.2..-0.3 is a natural spotlight/vignette. [Claude]
- **Linear gradient on skies**: Highlights/Exposure down from the top, effect fading to the horizon;
  keep it subtle so the transition never shows. [Claude]
- **Brush with Auto Mask** [Antho]: keeps strokes inside edges; our brush tool has no auto mask.
- **Skin**: in a skin/person mask, Texture -10..-25 and Clarity -5..-10, then a little grain to keep
  it real; never smooth to plastic. [Claude for whole-subject masks]
- **Range masks (colour/luminance)** [Antho]: intersect a mask with a colour or brightness range.

## Detail
- **Denoise 20-30** for Antho (moderate), then manual LuminanceSmoothing 0; sharpen after (Sharpness
  40-60, SharpenEdgeMasking 40-70 so flat areas like sky aren't sharpened). [Claude]
- **Hold Alt while dragging Edge Masking** [Antho] shows what gets sharpened (white = sharpened).
- **Grain hides plastic**: after Denoise, GrainAmount 10-15 / GrainSize ~20 restores a photographic
  feel. [Claude]

## Effects and lens
- **Lens corrections**: LensProfileEnable 1 + AutoLateralCA 1 on almost every photo; Upright
  "auto"/"level" for horizons, "vertical" for buildings. [Claude]
- **Post-crop vignette** at -10..-20 with Feather ~50 draws the eye in; Highlights priority style
  keeps it natural. [Claude]
- **Lens Blur** [Antho; settings may be settable by Claude but untested] (LrC 13.3+): AI depth map
  background blur; use "Visualize Depth" to check the map and the Focus/Blur brushes to fix it;
  works best when the background is already a little soft; keep it light.
- **Generative Remove / Detect objects / Reflection removal** [Antho] (Remove panel): Firefly-based
  removal with 3 variations; LrC 15.0 detects objects with their shadows/reflections. Run after
  Denoise.

## Productivity
- **Virtual copies** for every alternative look; compare them with the Survey view (N) [Antho].
- **Snapshots** as checkpoints; clicking one restores that state. [Claude creates them]
- **Before/after**: backslash key (\) in Develop [Antho].
- **Clipping warnings**: press J in Develop [Antho]; Claude uses export stats instead.
- **Sync / Auto Sync** for series: edit one, select the others, Sync [Antho]; Claude does the same with
  `copy_settings` per photo.
