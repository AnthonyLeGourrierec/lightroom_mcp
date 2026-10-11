---
name: lightroom-photo-editing
description: Edit photos in Antho's Lightroom Classic through the "lightroom" MCP server (fork of noopz/lightroom_mcp). Use when asked to edit, grade, denoise, mask, crop or straighten a photo in Lightroom, find photos in the catalog, or export an edit.
---

# Photo editing in Lightroom Classic via MCP

Lightroom Classic runs on this Windows PC with the "Lightroom Python Bridge" plugin
(repo: `C:\Users\ioman\Downloads\lightroom-mcp`, fork github.com/AnthonyLeGourrierec/lightroom_mcp).
The MCP server is registered as `lightroom` in `~/.claude.json`, so its tools appear in new sessions.

## Before starting
- The bridge auto-starts ~5 s after Lightroom opens (it only listens on localhost). If tools
  report "not connected", ask Antho to use File > Plug-in Extras > Start Python Bridge.
- If the MCP tools are not loaded in this session, drive the bridge with the SDK client:
  `venv\Scripts\python` + `from lightroom_sdk.client import LightroomClient` and
  `await client.execute_command("develop.applySettings", {...})`. Put several steps in one
  connection: after each disconnect the plugin needs ~2 s to accept a new client.
- PowerShell strips quotes from JSON passed as native arguments: pass JSON through a file.
- Plugin (Lua) changes only load after a Lightroom restart. Copy the changed `.lua` files to
  `%APPDATA%\Adobe\Lightroom\Modules\lightroom-python-bridge.lrdevplugin\`, then ask Antho
  to restart once for a batch of changes. Python-side changes need no restart.

## Ground rules
- One photo at a time. No bulk edits, never move/rename/delete originals (photos live on E:\).
- First step on any photo: `develop_create_snapshot(photo_id, "Original (before Claude)")`.
  End with a named snapshot of the final. Snapshots are how Antho compares and reverts.
- Develop-controller tools (AI masks, Denoise, Upright, curve points, setValue) act on the
  photo currently open in Develop. Check `catalog_get_selected_photos` first; don't switch the
  photo Antho is looking at without saying so.
- Export only the final (`preview_export_jpeg`, or `preview_export_with_crops` when you need
  to inspect detail) into `C:\Users\ioman\Downloads\lightroom-demo`. Antho does not want
  comparison sheets or per-round files unless asked. Never overwrite files.

## Antho's taste
- Keep it genuine: AI Denoise moderate (about 20-30, not 50+), leave some natural grain;
  add a touch of fine grain (amount ~10-15, size ~20) after denoising if it looks plastic.
- Respect the mood of the scene: evenings and nights stay dark and "nightlike"; don't lift
  exposure to daylight levels. Brighten the subject locally rather than the whole frame.
- Professional, clean, natural colour: warm light vs blue hour contrast is good, neon or
  over-saturated skies are not. Use the tone curve (gentle S-curve) and masks.

## Workflow
1. Inspect: `catalog_get_photo_metadata` (ISO, lens, time), `develop_get_geometry`
   (orientation, size), `develop_get_masks`, and export a view to look at. Measure the
   histogram (percentiles, clipping) instead of guessing.
2. Global: white balance, exposure, highlights/shadows/whites/blacks, presence, HSL,
   colour grading (`develop_set_color_grading`), S-curve, lens profile + CA.
3. Detail: `develop_set_enhance("denoise", True, 25)` for high ISO, then set the slider
   luminance NR to 0; sharpening ~40-50 with edge masking ~50.
4. Geometry: `develop_set_upright` (needs the photo open in Develop), `develop_set_crop`
   only if it genuinely improves composition.
5. Local: AI masks FIRST (`develop_create_ai_mask("sky", ...)`, "subject", ...), THEN
   gradients/radials/brushes (`develop_add_linear_gradient`, `develop_add_radial_gradient`,
   `develop_add_brush_stroke`). Verify with `develop_get_masks`.
6. Export, look (also at 100% crops for noise, halos, edges), refine, repeat.
7. Snapshot the final, export the final only, explain the edit in plain words.

## Infrared (Antho shoots IR: converted Canon PowerShot ELPH 180, DNG, ~590-720 nm)
- Edit virtual copies, never the master; one virtual copy per look so they compare side by side.
- FIRST, before touching anything:
  1. `develop_list_profiles(filter="infrared")`. Antho has custom IR profiles: camera profiles
     "Infrared Temp -10 ... -100" (elph180_ir_temp_*.dcp) and Look profiles
     "Infrared Temp(s) -XX rb swap" (red/blue channel swap), "Infrared -50/-100 Color Swap",
     "RG_Swap", "RB_70%", "Kolari Pocket 590nm IR Channel Mixer".
  2. Most photos will be unedited. Pick the profile that matches the camera (ELPH 180 ->
     "Infrared Temp(s) -XX rb swap"; SX50 -> "Infrared -50/-100 Color Swap", RG_Swap, RB_70%;
     Kolari 590nm -> its channel mixer) and start from Antho's proven baseline (his own
     CRW_0804 edit): Look "Infrared Temps -50 rb swap" at Amount 200 % on camera profile
     "Infrared Temp -50", WB about 10500 K / tint -150, Exposure about +1.2, Shadows +85,
     Whites +30, Blacks -45, Vibrance +20, curve 64->46 / 188->203, crop off the DNG border.
     Expected result: peach-gold foliage, deep navy sky, dark water. Then adjust:
     - Pick the "Temp -XX" variant by the light: try -30 / -50 / -70 and compare exports;
       stronger values give a bluer sky, weaker values warmer foliage.
     - Choose the look (classic, Aerochrome, Goldie, B&W) and refine from there.
  3. How to put a profile on a photo: it can't be set by name through the SDK.
     - Copy it from any photo that already uses it:
       `develop_copy_settings(source, target, ["CameraProfile", "CameraProfileDigest", "Look"])`.
       Find one with `catalog_query_photos(camera="ELPH 180", folder="Infrared")` +
       `develop_get_raw_settings(id, ["Look"])`.
     - Or ask Antho to pick it once in Develop > Profile, then continue.
  4. Optional: if other IR photos in the same folder are already edited, read their raw
     settings (`develop_get_raw_settings`) to match Antho's style for that series.
- With an rb swap profile the colour controls are inverted: local/global Temperature UP makes
  the sky bluer (down makes it dark/brown). Aerochrome on Antho's profile: WB ~9000 K / tint
  -120, Calibration RedHue -40 / RedSaturation +50, HSL Orange hue -80 / sat +60, Yellow hue
  -60, Red sat +25 / lum -10, then AI sky mask local temperature about +28 for a royal-blue sky.
- Without a swap profile (fallback): white balance hits Lightroom's floor (2000 K / tint -150)
  and the image stays magenta. HSL can't separate sky from foliage (same hue band). What works:
  - Calibration primaries: BlueHue -100 / BlueSaturation +100 -> blue sky, icy foliage
    (base for classic); RedHue -100, RedSat -50, BlueHue -100, BlueSat 50 -> magenta foliage
    (base for Aerochrome-style; push HSL Magenta hue +100 toward red).
  - AI sky mask with local hue -45..-90 plus temperature/tint toward blue to turn the sky blue.
  - Classic white foliage: global Saturation about -55 after the calibration, warm the
    highlights slightly (split toning ~48 / 20) for cream instead of icy blue.
  - B&W IR: Saturation -100, strong S-curve, sky mask exposure -0.7 (Wood effect), grain ~25;
    watch crushed blacks (keep < ~3 %).
- These DNGs have a dark border: crop ~2-2.5 % per side.
- Low ISO: no denoise needed; add grain instead.

## Gotchas learned the hard way
- On the photo open in Develop, settings written directly (crop, Upright) can be overwritten
  by the Develop controller; set them through the controller (the crop/Upright tools do).
- Coordinates: tools take displayed coordinates (0..1, x right, y down). Lightroom stores
  mask and crop geometry in sensor orientation; the tools convert using the photo's
  orientation ("AB" none, "BC" 90 CW, "DA" 90 CCW, "CD" 180). Don't bypass this.
- Local units stored in MaskGroupBasedCorrections: exposure = EV / 4, other sliders = /100.
  Tools take slider units.
- AI masks compute for a few seconds. When one finishes, Lightroom commits its own copy of
  the mask list and silently drops corrections added meanwhile. Create AI masks first.
- `PerspectiveUpright` written as a raw setting is ignored; Upright only works through the
  Develop controller (the tool does this). Upright and Denoise can be lost if the Develop
  photo changes before they settle; re-check with `develop_get_geometry` /
  `develop_get_enhance_state` before the final export.
- `preview_generate` thumbnails are stale or blank right after an edit; always judge edits
  from `preview_export_jpeg` (it waits ~1.5 s for the edit to commit).
- Presets saved by the plugin are not listed by Lightroom's preset folders; the plugin
  remembers their uuids (`develop_list_presets` shows them under "Claude (plugin presets)").
- `catalog_search_photos` only sees the current selection; use `catalog_query_photos` for
  the whole catalog (date range, folder, rating, flag, label, camera, lens, keyword).
