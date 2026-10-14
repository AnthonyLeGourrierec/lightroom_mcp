# Photo editing with Claude + Lightroom Classic: project context

Everything a new Claude session needs to edit Antho's photos in Lightroom Classic.

## 1. How it fits together

```
Claude Code (on Antho's Windows PC)
  └─ MCP server "lightroom" (Python, stdio)          C:\Users\ioman\Downloads\lightroom-mcp
       └─ TCP on localhost (127.0.0.1, dynamic ports in C:\tmp\lightroom_ports.txt)
            └─ Lightroom plugin "Lightroom Python Bridge" (Lua)
                 └─ Lightroom Classic (catalog on OneDrive, photos on E:\Photography)
```

- The MCP only runs on the PC where Lightroom is. Edits happen from a **Claude Code session
  on this PC** (desktop app or Remote Control). A claude.ai chat project on its own cannot
  reach Lightroom; it can plan, review exports and hand work to a session on the PC.
- Code: fork **github.com/AnthonyLeGourrierec/lightroom_mcp** (branch `main`), upstream
  noopz/lightroom_mcp. Local clone: `C:\Users\ioman\Downloads\lightroom-mcp` (venv inside).

## 2. Setup (already done on this PC)

- **MCP registration** (user scope, `C:\Users\ioman\.claude.json`):
  ```json
  "lightroom": {
    "type": "stdio",
    "command": "C:\\Users\\ioman\\Downloads\\lightroom-mcp\\venv\\Scripts\\python.exe",
    "args": ["C:\\Users\\ioman\\Downloads\\lightroom-mcp\\mcp_server\\main.py"],
    "env": {"PYTHONPATH": "C:\\Users\\ioman\\Downloads\\lightroom-mcp"}
  }
  ```
  Tools appear as `mcp__lightroom__*` in any new Claude Code session on this PC.
- **Lightroom plugin**: `%APPDATA%\Adobe\Lightroom\Modules\lightroom-python-bridge.lrdevplugin`.
  The bridge **auto-starts ~5 s after Lightroom opens** (localhost only; plugin pref
  `autoStart`). Manual: File > Plug-in Extras > Start Python Bridge.
- **Skill**: `C:\Users\ioman\.claude\skills\lightroom-photo-editing\SKILL.md` (copy in the
  repo under `skills/`). It holds the workflow, Antho's taste, IR recipes and all gotchas;
  load it before editing.
- **Catalog**: `C:\Users\ioman\OneDrive\Images\Lightroom\Lightroom Catalog.lrcat`
  (~8,100 photos). Backup from 2026-10-11 in `C:\Users\ioman\Downloads\lightroom-catalog-backup-2026-10-11`.
- **Exports** go to `C:\Users\ioman\Downloads\lightroom-demo`.

## 3. Updating the plugin

- Python changes (`mcp_server/`, `lightroom_sdk/`): take effect in the next Claude Code session.
- Lua changes (`lightroom-python-bridge.lrdevplugin/`): copy the `.lua` files into the Modules
  folder above, then **restart Lightroom once** (batch Lua changes). Syntax-check with
  `lupa` (installed in the venv) before asking for a restart.
- Commit to the fork with attribution; pushes go to `origin` (the fork).

## 4. Main tools (about 150 in total)

| Area | Tools |
|---|---|
| System | `system_ping`, `system_status`, `system_reconnect` |
| Find photos | `catalog_query_photos` (whole catalog: date range, folder, filename, camera, lens, keyword, rating, flag, colour label, format), `catalog_get_selected_photos`, `catalog_select_photo`, `catalog_get_photo_metadata`, `catalog_get_folders`, `catalog_get_collections` |
| Safety / versions | `develop_create_snapshot`, `develop_list_snapshots`, `catalog_create_virtual_copy` |
| Global develop | `develop_set_parameters` (batch of sliders), the `develop_adjust_*` tools, `develop_set_color_grading`, `develop_set_curve_points` / `develop_set_channel_curve`, `develop_set_enhance` (AI Denoise), `develop_get_enhance_state` |
| Geometry | `develop_get_geometry`, `develop_set_crop` (rect or aspect "4:5", angle), `develop_reset_crop`, `develop_set_upright`, `develop_set_transform` |
| Masks | `develop_create_ai_mask` (sky, subject, background, people, objects, landscape; incl. local hue), `develop_add_linear_gradient`, `develop_add_radial_gradient`, `develop_add_brush_stroke`, `develop_get_masks`, `develop_remove_mask` |
| Profiles / presets | `develop_list_profiles`, `develop_get_raw_settings`, `develop_copy_settings` (e.g. CameraProfile + Look), `develop_list_presets`, `develop_apply_preset`, `develop_save_preset` |
| Look at results | `preview_export_jpeg` (always use this to judge an edit), `preview_export_with_crops` (full size + 100 % crops + tonal stats), `preview_compare`, `histogram_*` |

## 5. Working rules

- One photo at a time; never bulk-edit, never move/rename/delete originals.
- Snapshot "Original (before Claude)" first; snapshot the final.
- Edit virtual copies when trying alternatives; never touch a master the user marked as his.
- Export **only the final** unless asked (no comparison sheets or per-round files).
- Explain the edit in plain words at the end.

## 6. Antho's taste

- AI Denoise moderate (~20-30), keep natural grain; a touch of fine grain is welcome.
- Respect the mood: evenings/nights stay dark and "nightlike"; brighten subjects locally.
- Natural, professional colour; use the tone curve (gentle S-curve) and masks.

## 7. Gotchas (learned the hard way)

1. Coordinates: tools take displayed coordinates (0..1); Lightroom stores masks and crop in
   sensor orientation. The tools convert using the photo's orientation (AB/BC/CD/DA).
2. Local mask units: exposure is stored as EV/4, other sliders as /100 (tools take slider units).
3. Create **AI masks first**, then gradients/radials/brushes: when an AI mask finishes
   computing it overwrites the mask list and drops corrections added meanwhile.
4. On the photo open in Develop, crop and Upright must go through the Develop controller
   (the tools do this). Upright/Denoise can be lost if the Develop photo changes; re-check
   with `develop_get_geometry` / `develop_get_enhance_state` before the final export.
5. Lightroom thumbnails are stale right after an edit: judge with `preview_export_jpeg`.
6. Profiles can't be set by name through the SDK: copy them from a photo that uses them
   (`develop_copy_settings`) or pick once in Develop > Profile.
7. Presets saved by the plugin aren't in Lightroom's preset folders; the plugin tracks them.

## 8. Infrared (Antho is an IR photographer)

- Cameras: converted Canon PowerShot ELPH 180 (DNG, ~590-720 nm), SX50 HS, Kolari 590 nm.
- Custom profiles in `%APPDATA%\Adobe\CameraRaw`: camera profiles "Infrared Temp -10...-100"
  (ELPH 180) and Looks "Infrared Temp(s) -XX rb swap", "Infrared -50/-100 Color Swap",
  RG_Swap, RB_70%, "Kolari Pocket 590nm IR Channel Mixer". **Always list profiles first.**
- Starting point (ELPH 180): Look "Infrared Temps -50 rb swap" at 200 % on "Infrared Temp -50".
  It can be copied from CRW_0804.DNG (master id 2309119).
- On the swap profile, **white balance is the main look knob**: ~10500 K = peach/gold foliage +
  navy sky; 50000 K = white foliage + cyan sky (Antho's CRW_0510 choice). Colour controls are
  inverted (temperature UP makes the sky bluer).
- Always check the horizon and straighten.
- Recipes for classic / Aerochrome / Goldie / B&W are in the skill.

## 9. Photos edited so far (for reference)

| Photo | Id | Result |
|---|---|---|
| IMG_0076 (Venice, Salute, blue hour) | 2310666 | gradient + S-curve + AI Denoise ("Claude r7" snapshot) |
| IMG_0072 (Grand Canal, wide) | 2310534 | snapshots "Claude final" and "Claude night" (darker, preferred) |
| IMG_0019 (Grand Canal sunset) | 2310654 | "Claude final (dusk…)" |
| CRW_0804 IR (canal) | master 2309119 (Antho's) | copies: 2663410 classic, 2663452 Aerochrome, 2663479 B&W, 2663630 Aerochrome v2 on swap profile (Antho's favourite) |
| CRW_0510 IR (garden) | Copy 2 = 2680049 | "golden garden"; Antho's own version 2099928 (white/cyan, 50000 K) |
