"""
Geometry tools for develop server: crop / straighten / aspect ratio, Upright, tone curves per
channel, color grading wheels, snapshots, virtual copies and presets.

Crop coordinates in Lightroom's develop settings are stored in the photo's unrotated
(sensor) orientation. These tools take rectangles in the DISPLAYED orientation
(x left->right, y top->bottom, 0..1) and convert them using the photo's orientation.
"""
from typing import Dict, Any, Optional, Tuple

# Display rect (left, top, right, bottom) -> stored rect, per Lightroom orientation code
def display_to_stored(rect: Tuple[float, float, float, float], orientation: Optional[str]) -> Tuple[float, float, float, float]:
    left, top, right, bottom = rect
    if orientation in (None, "", "AB"):        # as shot
        return left, top, right, bottom
    if orientation == "BC":                    # displayed rotated 90 deg clockwise
        return top, 1 - right, bottom, 1 - left
    if orientation == "DA":                    # displayed rotated 90 deg counter-clockwise
        return 1 - bottom, left, 1 - top, right
    if orientation == "CD":                    # 180 deg
        return 1 - right, 1 - bottom, 1 - left, 1 - top
    raise ValueError(f"Unsupported orientation '{orientation}' (mirrored images are not handled)")


def displayed_size(dimensions: Dict[str, Any], orientation: Optional[str]) -> Tuple[float, float]:
    """Width/height as displayed. Lightroom's 'dimensions' are already oriented."""
    return float(dimensions["width"]), float(dimensions["height"])


def aspect_rect(width: float, height: float, aspect_w: float, aspect_h: float,
                center_x: float = 0.5, center_y: float = 0.5, scale: float = 1.0) -> Tuple[float, float, float, float]:
    """Largest rect of the given aspect (times scale), centered on (center_x, center_y), kept inside the image."""
    target = aspect_w / aspect_h
    if width / height > target:
        rect_h, rect_w = height, height * target
    else:
        rect_w, rect_h = width, width / target
    rect_w, rect_h = rect_w * scale / width, rect_h * scale / height   # normalized
    left = min(max(center_x - rect_w / 2, 0.0), 1.0 - rect_w)
    top = min(max(center_y - rect_h / 2, 0.0), 1.0 - rect_h)
    return left, top, left + rect_w, top + rect_h


def setup_geometry_tools(server, execute_command):
    """Setup crop, transform, curves, color grading, snapshot, virtual copy and preset tools"""

    @server.tool
    async def develop_get_geometry(photo_id: str) -> Dict[str, Any]:
        """Read photo dimensions, orientation, current crop and Upright settings (read-only)."""
        result = await execute_command("getPhotoGeometry", {"photoId": str(photo_id)})
        return {"success": True, **result}

    @server.tool
    async def develop_set_crop(
        photo_id: str,
        left: Optional[float] = None, top: Optional[float] = None,
        right: Optional[float] = None, bottom: Optional[float] = None,
        aspect: Optional[str] = None,
        center_x: float = 0.5, center_y: float = 0.5, scale: float = 1.0,
        angle: float = 0.0
    ) -> Dict[str, Any]:
        """
        Crop and/or straighten the photo (one undoable step).

        Either give an explicit rectangle (left, top, right, bottom; 0..1 of the image
        as displayed), or an aspect ratio like "16:9", "4:5", "1:1", "9:16" with an
        optional center (center_x, center_y, 0..1) and scale (1.0 = largest possible).
        angle: straighten angle in degrees (-45..45).
        """
        geometry = await execute_command("getPhotoGeometry", {"photoId": str(photo_id)})
        orientation = geometry.get("orientation")
        if aspect:
            aw, ah = (float(v) for v in aspect.split(":"))
            width, height = displayed_size(geometry["dimensions"], orientation)
            rect = aspect_rect(width, height, aw, ah, center_x, center_y, scale)
        else:
            if None in (left, top, right, bottom):
                raise ValueError("Give left, top, right, bottom or an aspect ratio")
            rect = (left, top, right, bottom)
        s_left, s_top, s_right, s_bottom = display_to_stored(rect, orientation)
        settings = {
            "CropLeft": round(s_left, 6), "CropTop": round(s_top, 6),
            "CropRight": round(s_right, 6), "CropBottom": round(s_bottom, 6),
            "CropAngle": angle, "HasCrop": True,
        }
        result = await execute_command("applyExtraSettings", {
            "photoId": str(photo_id), "settings": settings, "historyName": "Crop"})
        return {"success": True, "displayed_rect": rect, "orientation": orientation, "stored": settings, **result}

    @server.tool
    async def develop_reset_crop(photo_id: str) -> Dict[str, Any]:
        """Remove the crop and straighten angle (one undoable step)."""
        settings = {"CropLeft": 0, "CropTop": 0, "CropRight": 1, "CropBottom": 1, "CropAngle": 0, "HasCrop": False}
        result = await execute_command("applyExtraSettings", {
            "photoId": str(photo_id), "settings": settings, "historyName": "Reset crop"})
        return {"success": True, **result}

    @server.tool
    async def develop_set_upright(photo_id: str, mode: str = "auto") -> Dict[str, Any]:
        """
        Upright perspective correction: mode "off", "auto", "level", "vertical" or "full".
        Turns the lens profile on as well (Upright works best with it).
        """
        modes = {"off": 0, "auto": 1, "level": 2, "vertical": 3, "full": 4}
        if mode not in modes:
            raise ValueError(f"mode must be one of {', '.join(modes)}")
        settings = {"PerspectiveUpright": modes[mode]}
        if mode != "off":
            settings["LensProfileEnable"] = 1
        result = await execute_command("applyExtraSettings", {
            "photoId": str(photo_id), "settings": settings, "historyName": f"Upright {mode}"})
        return {"success": True, "mode": mode, **result}

    @server.tool
    async def develop_set_transform(
        photo_id: str,
        vertical: Optional[float] = None, horizontal: Optional[float] = None,
        rotate: Optional[float] = None, scale: Optional[float] = None, aspect: Optional[float] = None
    ) -> Dict[str, Any]:
        """Manual transform sliders (vertical/horizontal -100..100, rotate -10..10, scale 50..150, aspect -100..100)."""
        mapping = {"PerspectiveVertical": vertical, "PerspectiveHorizontal": horizontal,
                   "PerspectiveRotate": rotate, "PerspectiveScale": scale, "PerspectiveAspect": aspect}
        settings = {k: v for k, v in mapping.items() if v is not None}
        result = await execute_command("applyExtraSettings", {
            "photoId": str(photo_id), "settings": settings, "historyName": "Transform"})
        return {"success": True, **result}

    @server.tool
    async def develop_set_color_grading(
        photo_id: str,
        shadow_hue: Optional[int] = None, shadow_sat: Optional[int] = None, shadow_lum: Optional[int] = None,
        midtone_hue: Optional[int] = None, midtone_sat: Optional[int] = None, midtone_lum: Optional[int] = None,
        highlight_hue: Optional[int] = None, highlight_sat: Optional[int] = None, highlight_lum: Optional[int] = None,
        global_hue: Optional[int] = None, global_sat: Optional[int] = None, global_lum: Optional[int] = None,
        blending: Optional[int] = None, balance: Optional[int] = None
    ) -> Dict[str, Any]:
        """Color grading wheels: hue 0-359, sat 0-100, lum -100..100, blending 0-100, balance -100..100."""
        mapping = {
            "ColorGradeShadowHue": shadow_hue, "ColorGradeShadowSat": shadow_sat, "ColorGradeShadowLum": shadow_lum,
            "ColorGradeMidtoneHue": midtone_hue, "ColorGradeMidtoneSat": midtone_sat, "ColorGradeMidtoneLum": midtone_lum,
            "ColorGradeHighlightHue": highlight_hue, "ColorGradeHighlightSat": highlight_sat,
            "ColorGradeHighlightLum": highlight_lum, "ColorGradeGlobalHue": global_hue,
            "ColorGradeGlobalSat": global_sat, "ColorGradeGlobalLum": global_lum,
            "ColorGradeBlending": blending, "SplitToningBalance": balance,
        }
        settings = {k: v for k, v in mapping.items() if v is not None}
        result = await execute_command("applyExtraSettings", {
            "photoId": str(photo_id), "settings": settings, "historyName": "Color grading"})
        return {"success": True, **result}

    @server.tool
    async def develop_set_channel_curve(photo_id: str, channel: str, points: list) -> Dict[str, Any]:
        """
        Set a point tone curve: channel "rgb", "red", "green" or "blue";
        points like [[0,0],[64,58],[192,200],[255,255]] (0-255, integers).
        """
        keys = {"rgb": "ToneCurvePV2012", "red": "ToneCurvePV2012Red",
                "green": "ToneCurvePV2012Green", "blue": "ToneCurvePV2012Blue"}
        if channel not in keys:
            raise ValueError("channel must be rgb, red, green or blue")
        flat = []
        for x, y in points:
            flat.extend([int(round(x)), int(round(y))])
        settings = {keys[channel]: flat}
        if channel == "rgb":
            settings["ToneCurveName2012"] = "Custom"
        result = await execute_command("applyExtraSettings", {
            "photoId": str(photo_id), "settings": settings, "historyName": f"Tone curve {channel}"})
        return {"success": True, **result}

    @server.tool
    async def develop_create_snapshot(photo_id: str, name: str) -> Dict[str, Any]:
        """Save the current develop settings as a named Snapshot (Develop > Snapshots panel)."""
        result = await execute_command("createSnapshot", {"photoId": str(photo_id), "name": name})
        return {"success": True, **result}

    @server.tool
    async def develop_list_snapshots(photo_id: str) -> Dict[str, Any]:
        """List the photo's Snapshots."""
        result = await execute_command("listSnapshots", {"photoId": str(photo_id)})
        return {"success": True, **result}

    @server.tool
    async def catalog_create_virtual_copy(photo_id: str, name: str = "Claude") -> Dict[str, Any]:
        """
        Create a virtual copy of one photo (selects it first). Edit the copy to try a
        look without touching the original's settings. Returns the new photo id(s).
        """
        result = await execute_command("createVirtualCopy", {"photoId": str(photo_id), "name": name})
        return {"success": True, **result}

    @server.tool
    async def develop_list_presets(filter: Optional[str] = None) -> Dict[str, Any]:
        """List Develop presets (name, folder, uuid), optionally filtered by text."""
        params = {"filter": filter} if filter else {}
        result = await execute_command("listPresets", params)
        return {"success": True, **result}

    @server.tool
    async def develop_apply_preset(photo_id: str, preset: str) -> Dict[str, Any]:
        """Apply a Develop preset by exact name or uuid to one photo (one undoable step)."""
        result = await execute_command("applyPreset", {"photoId": str(photo_id), "preset": preset})
        return {"success": True, **result}

    @server.tool
    async def develop_save_preset(
        photo_id: str, name: str, include_white_balance: bool = False, include_masks: bool = False
    ) -> Dict[str, Any]:
        """
        Save the photo's current look as a Develop preset (in this plugin's preset folder).
        Crop, spot removal and (by default) white balance and masks are left out.
        """
        result = await execute_command("savePreset", {
            "photoId": str(photo_id), "name": name,
            "includeWhiteBalance": include_white_balance, "includeMasks": include_masks})
        return {"success": True, **result}
