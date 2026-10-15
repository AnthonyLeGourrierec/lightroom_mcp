"""
Compact tool set: about 20 tools that cover the whole editing workflow, instead of
one tool per slider. Fewer, broader tools cost far less context in every session
and let one call do what used to take many (e.g. all Basic-panel sliders at once).

Most tools delegate to the original (legacy) tool functions so their tested logic
(coordinate conversion, mask units, export, ...) is reused unchanged. The legacy
tools stay available with LIGHTROOM_MCP_TOOLS=legacy or =all (see main.py).
"""
import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastmcp import FastMCP
from PIL import Image

from lightroom_sdk.types.develop import DEVELOP_PARAMETER_RANGES
from mcp_server.shared.resilient_client import resilient_client_manager

compact_server = FastMCP("Lightroom Classic (compact)")

_legacy_servers: List[FastMCP] = []


def register_legacy_servers(*servers: FastMCP) -> None:
    """Give the compact tools access to the legacy implementations they wrap"""
    _legacy_servers.extend(servers)


async def _legacy(name: str):
    for server in _legacy_servers:
        try:
            tool = await server.get_tool(name)
        except Exception:
            tool = None
        if tool is not None:
            return tool.fn
    raise RuntimeError(f"Legacy tool {name} is not available")


# Lightroom's Develop controller commits its own state of the open photo shortly after a
# slider change, silently reverting any direct (catalog) write made in the meantime:
# a colour grade, curve or mask written right after set_develop would vanish. So on the
# open photo, settings go through the controller where possible, and direct writes wait
# until the controller has settled (measured: lost at <0.5 s, kept at 2 s).
CONTROLLER_SETTLE_SECONDS = 2.5
CONTROLLER_COMMANDS = {
    "develop.setValue", "develop.applySettings", "develop.setCurvePoints", "develop.setAutoTone",
    "develop.setAutoWhiteBalance", "develop.resetToDefault", "develop.resetAllDevelopAdjustments",
}
DIRECT_WRITE_COMMANDS = {"develop.applyExtraSettings"}
_last_controller_write = 0.0


def _mark_controller_write() -> None:
    global _last_controller_write
    _last_controller_write = time.monotonic()


async def _settle() -> None:
    """Wait until a direct write can no longer be reverted by a pending controller commit"""
    remaining = CONTROLLER_SETTLE_SECONDS - (time.monotonic() - _last_controller_write)
    if remaining > 0:
        await asyncio.sleep(remaining)


async def _cmd(command: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if command in DIRECT_WRITE_COMMANDS:
        await _settle()
    result = await resilient_client_manager.execute_with_retry(command, params)
    if command in CONTROLLER_COMMANDS:
        _mark_controller_write()
    return result


async def _direct(tool_name: str, /, **kwargs) -> Dict[str, Any]:
    """Run a legacy tool that writes the catalog directly (masks, snapshots, export, ...)"""
    await _settle()
    return await (await _legacy(tool_name))(**kwargs)


async def _via_controller(tool_name: str, /, **kwargs) -> Dict[str, Any]:
    """Run a legacy tool that works through the Develop controller"""
    try:
        return await (await _legacy(tool_name))(**kwargs)
    finally:
        _mark_controller_write()


async def _selected_ids() -> List[str]:
    selected = await _cmd("catalog.getSelectedPhotos")
    return [str(p.get("id")) for p in selected.get("photos", [])]


async def _require_open(photo_id: str, what: str) -> None:
    """Develop-controller operations act on the photo open in Develop, whatever ID is passed"""
    ids = await _selected_ids()
    if ids != [str(photo_id)]:
        raise ValueError(
            f"{what} works on the photo open in Lightroom, but the selection is {ids or 'empty'}. "
            f"Call select_photo({photo_id}) first (and tell Antho you switched photos).")


# --- Develop setting names (mirror the lists in DevelopModule.lua) -------------------

# Written per photo with photo:applyDevelopSettings (no need for the photo to be open)
PER_PHOTO_KEYS = {
    "PerspectiveVertical", "PerspectiveHorizontal", "PerspectiveRotate", "PerspectiveScale",
    "PerspectiveAspect", "PerspectiveX", "PerspectiveY", "AutoLateralCA", "LensProfileEnable",
    "ColorGradeShadowLum", "ColorGradeMidtoneHue", "ColorGradeMidtoneSat", "ColorGradeMidtoneLum",
    "ColorGradeHighlightLum",
    "ColorGradeGlobalHue", "ColorGradeGlobalSat", "ColorGradeGlobalLum",
    "ColorGradeBlending", "SplitToningBalance",
}

_HSL = [f"{kind}Adjustment{color}" for kind in ("Hue", "Saturation", "Luminance")
        for color in ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")]
_GRAY = [f"GrayMixer{color}" for color in ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")]

# Set through the Develop controller (the photo must be the one open in Lightroom)
CONTROLLER_KEYS = {
    "Temperature", "Tint", "Exposure", "Contrast", "Highlights", "Shadows", "Whites", "Blacks",
    "Brightness", "Clarity", "Vibrance", "Saturation", "Texture", "Dehaze",
    "ParametricDarks", "ParametricLights", "ParametricShadows", "ParametricHighlights",
    "ParametricShadowSplit", "ParametricMidtoneSplit", "ParametricHighlightSplit",
    "SplitToningShadowHue", "SplitToningShadowSaturation", "SplitToningHighlightHue",
    "SplitToningHighlightSaturation",
    "PostCropVignetteAmount", "PostCropVignetteMidpoint", "PostCropVignetteFeather",
    "PostCropVignetteRoundness", "PostCropVignetteStyle", "PostCropVignetteHighlightContrast",
    "GrainAmount", "GrainSize", "GrainFrequency",
    "VignetteAmount", "VignetteMidpoint",
    "ShadowTint", "RedHue", "RedSaturation", "GreenHue", "GreenSaturation", "BlueHue", "BlueSaturation",
    "Sharpness", "SharpenRadius", "SharpenDetail", "SharpenEdgeMasking",
    "LuminanceSmoothing", "LuminanceNoiseReductionDetail", "LuminanceNoiseReductionContrast",
    "ColorNoiseReduction", "ColorNoiseReductionDetail", "ColorNoiseReductionSmoothness",
    "LensProfileDistortionScale", "LensProfileVignettingScale", "LensManualDistortionAmount",
    "DefringePurpleAmount", "DefringeGreenAmount", "CurveRefineSaturation",
    "LensBlurActive", "LensBlurAmount", "LensBlurCatEye", "LensBlurHighlightsBoost", "LensBlurFocalRange",
    *_HSL, *_GRAY,
}

# The colour grading shadow/highlight wheels are stored under the old split toning names:
# "ColorGradeShadowHue" etc. do not exist and Lightroom silently ignores them.
COLOR_GRADE_ALIASES = {
    "ColorGradeShadowHue": "SplitToningShadowHue", "ColorGradeShadowSat": "SplitToningShadowSaturation",
    "ColorGradeHighlightHue": "SplitToningHighlightHue", "ColorGradeHighlightSat": "SplitToningHighlightSaturation",
}

# Lightroom applies these one by one (bulk-applying them together is unreliable)
INDIVIDUAL_KEYS = {"Temperature", "Tint"}

# Read by get_photo when no develop_keys are given
DEFAULT_READ_KEYS = [
    "ProcessVersion", "CameraProfile", "Look", "WhiteBalance", "Temperature", "Tint",
    "Exposure2012", "Contrast2012", "Highlights2012", "Shadows2012", "Whites2012", "Blacks2012",
    "Texture", "Clarity2012", "Dehaze", "Vibrance", "Saturation",
    *_HSL,
    "SplitToningShadowHue", "SplitToningShadowSaturation", "SplitToningHighlightHue",
    "SplitToningHighlightSaturation", "SplitToningBalance",
    "ColorGradeMidtoneHue", "ColorGradeMidtoneSat", "ColorGradeMidtoneLum",
    "ColorGradeShadowLum", "ColorGradeHighlightLum", "ColorGradeGlobalHue", "ColorGradeGlobalSat",
    "ColorGradeGlobalLum", "ColorGradeBlending",
    "ToneCurveName2012", "ToneCurvePV2012", "ToneCurvePV2012Red", "ToneCurvePV2012Green", "ToneCurvePV2012Blue",
    "ParametricShadows", "ParametricDarks", "ParametricLights", "ParametricHighlights",
    "Sharpness", "SharpenRadius", "SharpenDetail", "SharpenEdgeMasking",
    "LuminanceSmoothing", "ColorNoiseReduction", "EnableLensCorrections", "LensProfileEnable",
    "AutoLateralCA", "PostCropVignetteAmount", "GrainAmount", "GrainSize", "GrainFrequency",
    "RedHue", "RedSaturation", "GreenHue", "GreenSaturation", "BlueHue", "BlueSaturation",
    "CropAngle", "HasCrop", "PerspectiveUpright",
]

MASK_ADJUSTMENTS = {"exposure", "contrast", "highlights", "shadows", "whites", "blacks", "clarity",
                    "texture", "dehaze", "saturation", "temperature", "tint"}
AI_MASK_TYPES = {"sky", "subject", "background", "people", "objects", "landscape"}


def _compact_value(value: Any) -> Any:
    """Shrink table settings (e.g. the Look profile) to what is useful to read"""
    if isinstance(value, dict) and "Name" in value:
        return {k: value[k] for k in ("Name", "Amount") if k in value}
    return value


def _tonal_stats(path: Path) -> Dict[str, Any]:
    pixels = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    luminance = 0.2126 * pixels[..., 0] + 0.7152 * pixels[..., 1] + 0.0722 * pixels[..., 2]
    return {
        "luminance_percentiles": {str(p): round(float(np.percentile(luminance, p)), 1) for p in (1, 5, 50, 95, 99)},
        "clipped_shadows_pct": round(float((luminance <= 2).mean() * 100), 2),
        "clipped_highlights_pct": round(float((pixels.max(axis=-1) >= 254).mean() * 100), 2),
        "mean_rgb": [round(float(v), 1) for v in pixels.reshape(-1, 3).mean(axis=0)],
    }


# --- Tools ---------------------------------------------------------------------------

@compact_server.tool
async def status() -> Dict[str, Any]:
    """Check the Lightroom connection and which photo(s) are selected (= open in Develop)."""
    selected = await _cmd("catalog.getSelectedPhotos")
    return {"connected": True, "selected": selected.get("photos", [])}


@compact_server.tool
async def find_photos(
    date_from: Optional[str] = None, date_to: Optional[str] = None, folder: Optional[str] = None,
    filename: Optional[str] = None, camera: Optional[str] = None, lens: Optional[str] = None,
    keyword: Optional[str] = None, min_rating: Optional[int] = None, max_rating: Optional[int] = None,
    flag: Optional[str] = None, color_label: Optional[str] = None, file_format: Optional[str] = None,
    include_virtual_copies: bool = True, newest_first: bool = False, limit: int = 50, offset: int = 0
) -> Dict[str, Any]:
    """
    Search the whole catalog (read-only). Filters combine with AND; text filters are
    case-insensitive substrings. Dates "YYYY-MM-DD". flag: "pick", "rejected", "none".
    """
    fn = await _legacy("catalog_query_photos")
    return await fn(date_from=date_from, date_to=date_to, folder=folder, filename=filename, camera=camera,
                    lens=lens, keyword=keyword, min_rating=min_rating, max_rating=max_rating, flag=flag,
                    color_label=color_label, file_format=file_format,
                    include_virtual_copies=include_virtual_copies, newest_first=newest_first,
                    limit=limit, offset=offset)


@compact_server.tool
async def select_photo(photo_id: str) -> Dict[str, Any]:
    """Select a photo (it becomes the one open in Develop). This changes what Antho sees."""
    await _settle()  # switching photos before Lightroom commits can lose the last edits
    return await (await _legacy("catalog_select_photo"))(photo_id=photo_id)


@compact_server.tool
async def get_photo(
    photo_id: Optional[str] = None,
    include: Optional[List[str]] = None,
    develop_keys: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Read everything about a photo in one call (read-only). photo_id defaults to the selection.
    include: any of "info" (file, camera, ISO, lens, date), "develop" (current settings),
    "masks", "geometry" (size, orientation, crop, Upright), "enhance" (AI Denoise state,
    open photo only), "snapshots". Default: ["info", "develop"].
    develop_keys: raw setting names to read instead of the usual ~110 (e.g. ["Look", "CameraProfile"]).
    Settings use Lightroom's stored names (Exposure2012, Clarity2012, ...).
    """
    await _settle()  # pending Develop changes are not in the catalog yet
    include = include or ["info", "develop"]
    if photo_id is None:
        ids = await _selected_ids()
        if not ids:
            raise ValueError("No photo selected; pass photo_id")
        photo_id = ids[0]
    photo_id = str(photo_id)
    out: Dict[str, Any] = {"photo_id": photo_id}
    if "info" in include:
        out["info"] = await (await _legacy("catalog_get_photo_metadata"))(photo_id=photo_id)
    if "develop" in include:
        raw = await _cmd("develop.getRawSettings", {"photoId": photo_id, "keys": develop_keys or DEFAULT_READ_KEYS})
        out["develop"] = {k: _compact_value(v) for k, v in raw.get("settings", {}).items() if v is not None}
    if "masks" in include:
        out["masks"] = await (await _legacy("develop_get_masks"))(photo_id=photo_id)
    if "geometry" in include:
        out["geometry"] = await (await _legacy("develop_get_geometry"))(photo_id=photo_id)
    if "enhance" in include:
        if await _selected_ids() == [photo_id]:
            out["enhance"] = await (await _legacy("develop_get_enhance_state"))()
        else:
            out["enhance"] = "only readable for the photo open in Develop"
    if "snapshots" in include:
        out["snapshots"] = await (await _legacy("develop_list_snapshots"))(photo_id=photo_id)
    return out


@compact_server.tool
async def set_develop(
    photo_id: str,
    settings: Optional[Dict[str, Any]] = None,
    auto: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Set any number of global Develop sliders in one call, using Lightroom's slider names:
    Basic: Temperature, Tint, Exposure, Contrast, Highlights, Shadows, Whites, Blacks,
      Texture, Clarity, Dehaze, Vibrance, Saturation.
    HSL: HueAdjustment<Color>, SaturationAdjustment<Color>, LuminanceAdjustment<Color>
      (Red, Orange, Yellow, Green, Aqua, Blue, Purple, Magenta); B&W: GrayMixer<Color>.
    Curve sliders: ParametricShadows/Darks/Lights/Highlights(+Split).
    Split toning: SplitToningShadowHue/Saturation, SplitToningHighlightHue/Saturation.
    Detail: Sharpness, SharpenRadius, SharpenDetail, SharpenEdgeMasking, LuminanceSmoothing,
      ColorNoiseReduction(+Detail, Smoothness).
    Effects: PostCropVignetteAmount/Midpoint/Feather/Roundness/Style, GrainAmount/Size/Frequency.
    Lens: LensProfileEnable, AutoLateralCA, DefringePurpleAmount, DefringeGreenAmount, VignetteAmount.
    Calibration: ShadowTint, RedHue, RedSaturation, GreenHue, GreenSaturation, BlueHue, BlueSaturation.
    A value of "default" resets that slider. auto: ["tone"] and/or ["white_balance"] run Auto first.
    The photo must be the one open in Develop (use select_photo). Crop, Upright and transform:
    use set_geometry; tone curve points: set_tone_curve; colour wheels: set_color_grading.
    """
    settings = {COLOR_GRADE_ALIASES.get(k, k): v for k, v in (settings or {}).items()}
    photo_id = str(photo_id)
    await _require_open(photo_id, "set_develop")

    unknown = [k for k in settings if k not in CONTROLLER_KEYS and k not in PER_PHOTO_KEYS]
    if unknown:
        hint = " Crop/straighten: use set_geometry." if any(k.startswith(("Crop", "Straighten")) for k in unknown) else ""
        raise ValueError(f"Unknown setting(s): {', '.join(unknown)}.{hint}")
    for key, value in settings.items():
        if value != "default" and key in DEVELOP_PARAMETER_RANGES:
            low, high = DEVELOP_PARAMETER_RANGES[key]
            if not low <= value <= high:
                raise ValueError(f"{key}={value} is outside {low}..{high}")

    done: Dict[str, Any] = {}
    for kind in auto or []:
        if kind == "tone":
            done["auto_tone"] = await _cmd("develop.setAutoTone")
        elif kind == "white_balance":
            done["auto_white_balance"] = await _cmd("develop.setAutoWhiteBalance", {"photoId": photo_id})
        else:
            raise ValueError('auto takes "tone" and/or "white_balance"')

    defaults = [k for k, v in settings.items() if v == "default"]
    for key in defaults:
        await _cmd("develop.resetToDefault", {"param": key, "photoId": photo_id})
    # Everything goes through the Develop controller (the photo is open), so nothing
    # written here can be reverted by it. applySettings only knows some names; the
    # rest (Temperature/Tint and the colour grading / lens keys) are set one by one.
    individual = {k: v for k, v in settings.items()
                  if (k in INDIVIDUAL_KEYS or k in PER_PHOTO_KEYS) and k not in defaults}
    bulk = {k: v for k, v in settings.items() if k not in individual and k not in defaults}

    if bulk:
        result = await _cmd("develop.applySettings", {"photoId": photo_id, "settings": bulk})
        if result.get("invalid"):
            done["rejected"] = result["invalid"]
    for key, value in individual.items():
        await _cmd("develop.setValue", {"param": key, "value": value, "photoId": photo_id})
    done["applied"] = {k: v for k, v in settings.items() if k not in done.get("rejected", {})}
    return done


@compact_server.tool
async def set_tone_curve(
    photo_id: str,
    channel: str = "rgb",
    points: Optional[List[List[float]]] = None,
    s_curve: Optional[float] = None
) -> Dict[str, Any]:
    """
    Point tone curve for channel "rgb", "red", "green" or "blue" (one undoable step).
    points: [[x, y], ...] in 0-255, e.g. [[0,0],[64,56],[192,200],[255,255]];
    [[0,0],[255,255]] resets it. Or s_curve: strength 0-100 for a symmetric S-curve
    (30 = gentle, 60 = strong).
    """
    photo_id = str(photo_id)
    if points is None:
        if s_curve is None:
            raise ValueError("Give points or s_curve")
        k = round(max(0.0, min(100.0, s_curve)) * 0.25)
        points = [[0, 0], [64, 64 - k], [128, 128], [192, 192 + k], [255, 255]]
    keys = {"rgb": "ToneCurvePV2012", "red": "ToneCurvePV2012Red",
            "green": "ToneCurvePV2012Green", "blue": "ToneCurvePV2012Blue"}
    if channel not in keys:
        raise ValueError("channel must be rgb, red, green or blue")
    if await _selected_ids() == [photo_id]:
        await _cmd("develop.setCurvePoints", {
            "param": keys[channel], "points": [{"x": int(round(x)), "y": int(round(y))} for x, y in points]})
        return {"success": True, "channel": channel, "points": points, "via": "develop controller"}
    return await _direct("develop_set_channel_curve", photo_id=photo_id, channel=channel, points=points)


@compact_server.tool
async def set_color_grading(
    photo_id: str,
    shadow_hue: Optional[int] = None, shadow_sat: Optional[int] = None, shadow_lum: Optional[int] = None,
    midtone_hue: Optional[int] = None, midtone_sat: Optional[int] = None, midtone_lum: Optional[int] = None,
    highlight_hue: Optional[int] = None, highlight_sat: Optional[int] = None, highlight_lum: Optional[int] = None,
    global_hue: Optional[int] = None, global_sat: Optional[int] = None, global_lum: Optional[int] = None,
    blending: Optional[int] = None, balance: Optional[int] = None
) -> Dict[str, Any]:
    """Colour grading wheels: hue 0-359, sat 0-100, lum -100..100, blending 0-100, balance -100..100."""
    photo_id = str(photo_id)
    values = dict(shadow_hue=shadow_hue, shadow_sat=shadow_sat, shadow_lum=shadow_lum,
                  midtone_hue=midtone_hue, midtone_sat=midtone_sat, midtone_lum=midtone_lum,
                  highlight_hue=highlight_hue, highlight_sat=highlight_sat, highlight_lum=highlight_lum,
                  global_hue=global_hue, global_sat=global_sat, global_lum=global_lum,
                  blending=blending, balance=balance)
    if await _selected_ids() == [photo_id]:
        keys = {"blending": "ColorGradeBlending", "balance": "SplitToningBalance"}
        settings = {}
        for name, value in values.items():
            if value is not None:
                key = keys.get(name) or "ColorGrade" + "".join(part.capitalize() for part in name.split("_"))
                settings[COLOR_GRADE_ALIASES.get(key, key)] = value
        for key, value in settings.items():
            await _cmd("develop.setValue", {"param": key, "value": value, "photoId": photo_id})
        return {"success": True, "applied": settings, "via": "develop controller"}
    if any(values[k] is not None for k in ("shadow_hue", "shadow_sat", "highlight_hue", "highlight_sat")):
        # Those are split toning settings, which the direct-write path does not accept
        raise ValueError(f"Shadow/highlight hue and saturation need the photo open: select_photo({photo_id}) first")
    return await _direct("develop_set_color_grading", photo_id=photo_id, **values)


@compact_server.tool
async def set_geometry(
    photo_id: str,
    crop: Optional[Dict[str, Any]] = None,
    angle: Optional[float] = None,
    upright: Optional[str] = None,
    transform: Optional[Dict[str, float]] = None,
    reset_crop: bool = False
) -> Dict[str, Any]:
    """
    Crop, straighten, Upright and manual transform in one call. Coordinates are 0..1 of
    the photo as displayed (x right, y down); rotation is handled for you.
    crop: {"left", "top", "right", "bottom"} or {"aspect": "4:5", "center_x", "center_y", "scale"}
      (scale 1.0 = largest crop of that aspect).
    angle: straighten in degrees (-45..45); kept as is when omitted.
    upright: "off", "auto", "level", "vertical" or "full" (photo must be open in Develop).
    transform: {"vertical", "horizontal" (-100..100), "rotate" (-10..10), "scale" (50..150), "aspect"}.
    reset_crop: remove crop and straighten first.
    """
    photo_id = str(photo_id)
    is_open = await _selected_ids() == [photo_id]
    done: Dict[str, Any] = {}
    if reset_crop:
        if is_open:
            for key, value in {"CropLeft": 0, "CropTop": 0, "CropRight": 1, "CropBottom": 1, "CropAngle": 0}.items():
                await _cmd("develop.setValue", {"param": key, "value": value})
            done["reset_crop"] = {"via": "develop controller"}
        else:
            done["reset_crop"] = await _direct("develop_reset_crop", photo_id=photo_id)
    if upright is not None:
        done["upright"] = await _via_controller("develop_set_upright", photo_id=photo_id, mode=upright)
    if transform:
        if is_open:
            keys = {"vertical": "PerspectiveVertical", "horizontal": "PerspectiveHorizontal",
                    "rotate": "PerspectiveRotate", "scale": "PerspectiveScale", "aspect": "PerspectiveAspect"}
            unknown = [k for k in transform if k not in keys]
            if unknown:
                raise ValueError(f"Unknown transform key(s): {', '.join(unknown)}")
            for name, value in transform.items():
                await _cmd("develop.setValue", {"param": keys[name], "value": value})
            done["transform"] = {"applied": transform, "via": "develop controller"}
        else:
            done["transform"] = await _direct("develop_set_transform", photo_id=photo_id, **transform)
    if crop:
        if angle is None:
            geometry = await _cmd("develop.getPhotoGeometry", {"photoId": photo_id})
            angle = (geometry.get("crop") or {}).get("CropAngle") or 0.0
        # The legacy crop tool itself uses the controller on the open photo, else a direct write
        if is_open:
            done["crop"] = await _via_controller("develop_set_crop", photo_id=photo_id, angle=angle, **crop)
        else:
            done["crop"] = await _direct("develop_set_crop", photo_id=photo_id, angle=angle, **crop)
    elif angle is not None:
        if is_open:
            done["angle"] = await _cmd("develop.setValue", {"param": "CropAngle", "value": angle})
        else:
            done["angle"] = await _cmd("develop.applyExtraSettings", {
                "photoId": photo_id, "settings": {"CropAngle": angle, "HasCrop": True}, "historyName": "Straighten"})
    return done


@compact_server.tool
async def add_mask(
    photo_id: str,
    kind: str,
    adjustments: Dict[str, float],
    area: Optional[Dict[str, Any]] = None,
    name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a local adjustment mask (one undoable step).
    kind: AI masks "sky", "subject", "background", "people", "objects", "landscape"
      (photo must be open in Develop; ADD THESE FIRST, they drop masks added while computing),
      or "linear", "radial", "brush".
    adjustments: exposure (EV), contrast, highlights, shadows, whites, blacks, clarity, texture,
      dehaze, saturation, temperature, tint (-100..100); AI masks also take hue (e.g. -45).
    area (0..1 of the displayed photo):
      linear: {"start_x", "start_y", "end_x", "end_y"} (effect fades from start to end)
      radial: {"left", "top", "right", "bottom", "feather": 50, "inverted": false}
      brush: {"points": [[x, y], ...], "radius": 0.03, "feather": 50, "flow": 100}
    name: label for gradients/brushes (needed to remove them later).
    """
    photo_id = str(photo_id)
    allowed = MASK_ADJUSTMENTS | ({"hue"} if kind in AI_MASK_TYPES else set())
    unknown = [k for k in adjustments if k not in allowed]
    if unknown:
        raise ValueError(f"Unknown adjustment(s) for {kind}: {', '.join(unknown)}")
    if kind in AI_MASK_TYPES:
        await _require_open(photo_id, "AI masks")
        # Lightroom gives a new mask the local sliders last used in the Masking panel (seen live:
        # temperature -60, tint -30, hue -25, saturation +40 left over from an earlier mask), so
        # every slider is set explicitly, at 0 unless asked otherwise.
        explicit = {key: 0 for key in sorted(MASK_ADJUSTMENTS | {"hue"})}
        explicit.update(adjustments)
        return await _via_controller("develop_create_ai_mask", mask_type=kind, **explicit)
    tools = {"linear": "develop_add_linear_gradient", "radial": "develop_add_radial_gradient",
             "brush": "develop_add_brush_stroke"}
    if kind not in tools:
        raise ValueError(f"kind must be one of {', '.join(sorted(AI_MASK_TYPES))}, linear, radial, brush")
    name = name or f"Claude {kind}"
    result = await _direct(tools[kind], photo_id=photo_id, name=name, **(area or {}), **adjustments)
    # A mask written directly can still be dropped by Lightroom (e.g. an AI mask finishing):
    # confirm it is there after a moment, and add it once more if it isn't.
    await asyncio.sleep(CONTROLLER_SETTLE_SECONDS)
    if name not in await _mask_names(photo_id):
        result = await _direct(tools[kind], photo_id=photo_id, name=name, **(area or {}), **adjustments)
        await asyncio.sleep(CONTROLLER_SETTLE_SECONDS)
        result["retried"] = True
        result["verified"] = name in await _mask_names(photo_id)
    else:
        result["verified"] = True
    return result


async def _mask_names(photo_id: str) -> List[str]:
    masks = await _cmd("develop.getMaskCorrections", {"photoId": photo_id})
    return [c.get("CorrectionName") for c in masks.get("maskGroupBasedCorrections") or []]


@compact_server.tool
async def remove_mask(photo_id: str, name: str) -> Dict[str, Any]:
    """Remove the mask(s) with this exact name (one undoable step)."""
    return await _direct("develop_remove_mask", photo_id=str(photo_id), name=name)


@compact_server.tool
async def set_enhance(enhance_type: Optional[str] = None, enable: bool = True,
                      denoise_amount: Optional[int] = None) -> Dict[str, Any]:
    """
    AI Denoise / Raw Details on the photo open in Develop. enhance_type "denoise" or
    "rawDetails"; denoise_amount 0-100 (Antho likes ~20-30). Check with get_photo(include=["enhance"]).
    """
    return await _via_controller("develop_set_enhance", 
        enhance_type=enhance_type, enable=enable, denoise_amount=denoise_amount)


@compact_server.tool
async def reset_develop(photo_id: str, parameters: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Reset slider(s) to default: the given parameters, or ALL develop settings when none are
    given (photo must be open in Develop). Prefer snapshots to go back to an earlier state.
    """
    photo_id = str(photo_id)
    await _require_open(photo_id, "reset_develop")
    if not parameters:
        await _cmd("develop.resetAllDevelopAdjustments")
        # Lightroom's reset leaves masks in place (seen live: a virtual copy kept 5 masks from
        # Antho's own edit), so remove them too: "reset" must mean a clean slate.
        removed = []
        for name in await _mask_names(photo_id):
            if name:
                await _direct("develop_remove_mask", photo_id=photo_id, name=name)
                removed.append(name)
        return {"reset": "all", "masks_removed": removed}
    for parameter in parameters:
        await _cmd("develop.resetToDefault", {"param": parameter, "photoId": photo_id})
    return {"reset": parameters}


@compact_server.tool
async def create_snapshot(photo_id: str, name: str, replace: bool = False) -> Dict[str, Any]:
    """
    Save the current settings as a named Snapshot, e.g. "Original (before Claude)".
    A master and all its virtual copies share ONE snapshot list, so prefix names per copy
    (e.g. "A1 Base", "B Final"). An existing name is refused unless replace=True.
    """
    photo_id = str(photo_id)
    existing = await _cmd("develop.listSnapshots", {"photoId": photo_id})
    names = [s.get("name") for s in existing.get("snapshots") or []]
    if name in names and not replace:
        raise ValueError(f'Snapshot "{name}" already exists on this photo or one of its virtual copies '
                         f"(they share snapshots). Use a unique name, or replace=True to overwrite it.")
    return await _direct("develop_create_snapshot", photo_id=photo_id, name=name)


@compact_server.tool
async def create_virtual_copy(photo_id: str, name: str = "Claude") -> Dict[str, Any]:
    """Create a virtual copy (selects it) to try a look without touching the master."""
    return await _direct("catalog_create_virtual_copy", photo_id=str(photo_id), name=name)


@compact_server.tool
async def list_profiles(camera: Optional[str] = None, filter: Optional[str] = None) -> Dict[str, Any]:
    """List custom camera/Look profiles installed on this PC (e.g. filter="infrared")."""
    return await (await _legacy("develop_list_profiles"))(camera=camera, filter=filter)


@compact_server.tool
async def copy_settings(from_photo_id: str, to_photo_id: str, keys: List[str]) -> Dict[str, Any]:
    """
    Copy raw develop settings between photos, e.g. keys=["CameraProfile", "CameraProfileDigest",
    "Look"] to apply a profile (profiles can't be set by name). One undoable step.
    """
    return await _direct("develop_copy_settings", 
        from_photo_id=str(from_photo_id), to_photo_id=str(to_photo_id), keys=keys)


@compact_server.tool
async def presets(
    action: str = "list",
    photo_id: Optional[str] = None,
    preset: Optional[str] = None,
    name: Optional[str] = None,
    filter: Optional[str] = None,
    include_white_balance: bool = False,
    include_masks: bool = False
) -> Dict[str, Any]:
    """
    Develop presets. action "list" (optional filter), "apply" (photo_id + preset name or uuid),
    or "save" (photo_id + name; crop/spot removal never included).
    """
    if action == "list":
        return await (await _legacy("develop_list_presets"))(filter=filter)
    if action == "apply":
        return await _direct("develop_apply_preset", photo_id=str(photo_id), preset=preset)
    if action == "save":
        return await _direct("develop_save_preset", 
            photo_id=str(photo_id), name=name, include_white_balance=include_white_balance,
            include_masks=include_masks)
    raise ValueError('action must be "list", "apply" or "save"')


@compact_server.tool
async def set_metadata(photo_id: str, rating: Optional[int] = None,
                       keywords: Optional[List[str]] = None) -> Dict[str, Any]:
    """Set the star rating (0-5) and/or add keywords."""
    done: Dict[str, Any] = {}
    if rating is not None:
        done["rating"] = await (await _legacy("catalog_set_rating"))(photo_id=str(photo_id), rating=rating)
    if keywords:
        done["keywords"] = await (await _legacy("catalog_add_keywords"))(photo_id=str(photo_id), keywords=keywords)
    return done


@compact_server.tool
async def export_jpeg(
    photo_id: str,
    out_dir: str,
    file_name: Optional[str] = None,
    long_edge: Optional[int] = None,
    quality: int = 90,
    crops: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Render the current edit to a JPEG through Lightroom's export (the only reliable way to
    see fresh edits) and return tonal stats: luminance percentiles and clipping. Never
    overwrites files. long_edge defaults to 2048.
    crops: [{"name": "face", "left", "top", "right", "bottom"}] (0..1) also writes 100% crops
    plus a view copy, from a full-size export (long_edge default 6000), to inspect detail.
    """
    if crops:
        return await _direct("preview_export_with_crops", 
            photo_id=str(photo_id), out_dir=out_dir, file_name=file_name or f"photo_{photo_id}",
            crops=crops, long_edge=long_edge or 6000)
    result = await _direct("preview_export_jpeg", 
        photo_id=str(photo_id), out_dir=out_dir, file_name=file_name, long_edge=long_edge or 2048,
        quality=quality)
    if result.get("path"):
        result["stats"] = _tonal_stats(Path(result["path"]))
    return result


@compact_server.tool
async def compare_images(image_paths: List[str], out_path: str, height: int = 1600,
                         labels: Optional[List[str]] = None) -> Dict[str, Any]:
    """Put exported JPEGs side by side in one image (only when Antho asks for a comparison)."""
    return await (await _legacy("preview_compare"))(
        image_paths=image_paths, out_path=out_path, height=height, labels=labels)
