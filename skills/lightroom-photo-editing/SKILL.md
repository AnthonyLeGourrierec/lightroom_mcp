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

## Gotchas learned the hard way
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
