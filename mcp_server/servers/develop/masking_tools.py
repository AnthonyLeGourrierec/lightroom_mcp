"""
Masking tools for develop server: AI masks, linear/radial gradients, Enhance (AI Denoise).

Gradients are written directly into the photo's MaskGroupBasedCorrections develop
setting (Lightroom's SDK cannot place gradient geometry through LrDevelopController).
Coordinates are normalized 0..1 of the image as displayed (x left->right, y top->bottom).
"""
import math
from typing import Dict, Any, Optional, List

# UI slider name -> (Lightroom correction key, divisor from UI units to stored units)
LOCAL_PARAMS = {
    "exposure": ("LocalExposure2012", 4.0),
    "contrast": ("LocalContrast2012", 100.0),
    "highlights": ("LocalHighlights2012", 100.0),
    "shadows": ("LocalShadows2012", 100.0),
    "whites": ("LocalWhites2012", 100.0),
    "blacks": ("LocalBlacks2012", 100.0),
    "clarity": ("LocalClarity2012", 100.0),
    "texture": ("LocalTexture", 100.0),
    "dehaze": ("LocalDehaze", 100.0),
    "saturation": ("LocalSaturation", 100.0),
    "temperature": ("LocalTemperature", 100.0),
    "tint": ("LocalTint", 100.0),
    "sharpness": ("LocalSharpness", 100.0),
    "noise": ("LocalLuminanceNoise", 100.0),
}

# AI mask locals go through LrDevelopController, which uses UI units and these names
AI_LOCAL_NAMES = {
    "exposure": "local_Exposure", "contrast": "local_Contrast", "highlights": "local_Highlights",
    "shadows": "local_Shadows", "whites": "local_Whites", "blacks": "local_Blacks",
    "clarity": "local_Clarity", "texture": "local_Texture", "dehaze": "local_Dehaze",
    "saturation": "local_Saturation", "temperature": "local_Temperature", "tint": "local_Tint",
    "sharpness": "local_Sharpness", "noise": "local_LuminanceNoise",
}


def build_correction(name: str, mask: Dict[str, Any], adjustments: Dict[str, float]) -> Dict[str, Any]:
    """Build one MaskGroupBasedCorrections entry from UI-unit adjustments."""
    correction: Dict[str, Any] = {
        "What": "Correction",
        "CorrectionName": name,
        "CorrectionActive": True,
        "CorrectionAmount": 1,
        "CorrectionMasks": [mask],
    }
    for key, value in adjustments.items():
        if value is None:
            continue
        if key not in LOCAL_PARAMS:
            raise ValueError(f"Unsupported local adjustment '{key}'. Use one of: {', '.join(LOCAL_PARAMS)}")
        lr_key, divisor = LOCAL_PARAMS[key]
        correction[lr_key] = round(float(value) / divisor, 6)
    return correction


def linear_gradient_mask(start_x: float, start_y: float, end_x: float, end_y: float) -> Dict[str, Any]:
    """Full effect at start, fading to none at end."""
    return {
        "What": "Mask/Gradient",
        "MaskActive": True,
        "MaskName": "Linear Gradient",
        "MaskBlendMode": 0,
        "MaskInverted": False,
        "MaskValue": 1,
        "FullX": start_x, "FullY": start_y,
        "ZeroX": end_x, "ZeroY": end_y,
    }


def radial_gradient_mask(top: float, left: float, bottom: float, right: float,
                         feather: float = 50, angle: float = 0, inverted: bool = False) -> Dict[str, Any]:
    return {
        "What": "Mask/CircularGradient",
        "MaskActive": True,
        "MaskName": "Radial Gradient",
        "MaskBlendMode": 0,
        "MaskInverted": inverted,
        "MaskValue": 1,
        "Top": top, "Left": left, "Bottom": bottom, "Right": right,
        "Angle": angle, "Midpoint": 50, "Roundness": 0,
        "Feather": feather, "Flipped": False, "Version": 2,
    }


def brush_mask(points: List[List[float]], radius: float, feather: float = 50, flow: float = 100,
               erase: bool = False) -> Dict[str, Any]:
    """
    A brush stroke through the given points (normalized 0..1, displayed orientation).
    Dabs are interpolated so consecutive dabs overlap (spacing = radius / 3).
    """
    if not points:
        raise ValueError("points must contain at least one [x, y]")
    spacing = max(radius / 3.0, 1e-4)
    dabs = [points[0]]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / spacing))
        for i in range(1, steps + 1):
            t = i / steps
            dabs.append([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t])
    return {
        "What": "Mask/Paint",
        "MaskActive": True,
        "MaskName": "Brush",
        "MaskBlendMode": 1 if erase else 0,
        "MaskInverted": False,
        "MaskValue": 1,
        "Radius": radius,
        "Flow": flow / 100.0,
        "CenterWeight": 1 - feather / 100.0,
        "Dabs": [f"d {x:.6f} {y:.6f}" for x, y in dabs],
    }


def _adjustments(**kwargs) -> Dict[str, float]:
    return {k: v for k, v in kwargs.items() if v is not None}


def setup_masking_tools(server, execute_command):
    """Setup masking tools"""

    @server.tool
    async def develop_get_masks(photo_id: str) -> Dict[str, Any]:
        """
        Read the photo's masks (AI masks, gradients, brushes) with their adjustments, plus crop.
        Read-only. Local values are in Lightroom's stored units (exposure = EV/4, others = slider/100).
        """
        result = await execute_command("getMaskCorrections", {"photoId": str(photo_id)})
        return {"success": True, **result}

    @server.tool
    async def develop_add_linear_gradient(
        photo_id: str, name: str,
        start_x: float, start_y: float, end_x: float, end_y: float,
        exposure: Optional[float] = None, contrast: Optional[float] = None,
        highlights: Optional[float] = None, shadows: Optional[float] = None,
        whites: Optional[float] = None, blacks: Optional[float] = None,
        clarity: Optional[float] = None, texture: Optional[float] = None,
        dehaze: Optional[float] = None, saturation: Optional[float] = None,
        temperature: Optional[float] = None, tint: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Add a linear gradient mask with local adjustments (one undoable History step).

        Coordinates are normalized 0..1 (x left->right, y top->bottom). The effect is
        full at (start_x, start_y) and fades to nothing at (end_x, end_y).
        Example, darken the sky from the top edge down to 45% height:
        start=(0.5, 0.0), end=(0.5, 0.45), exposure=-0.3.

        Adjustments use slider units: exposure in EV (-4..4), the others -100..100.
        Use a unique name: it is how develop_remove_mask finds it again.
        """
        correction = build_correction(name, linear_gradient_mask(start_x, start_y, end_x, end_y), _adjustments(
            exposure=exposure, contrast=contrast, highlights=highlights, shadows=shadows, whites=whites,
            blacks=blacks, clarity=clarity, texture=texture, dehaze=dehaze, saturation=saturation,
            temperature=temperature, tint=tint))
        result = await execute_command("addMaskCorrection", {"photoId": str(photo_id), "correction": correction})
        return {"success": True, **result}

    @server.tool
    async def develop_add_radial_gradient(
        photo_id: str, name: str,
        top: float, left: float, bottom: float, right: float,
        feather: float = 50, inverted: bool = False,
        exposure: Optional[float] = None, contrast: Optional[float] = None,
        highlights: Optional[float] = None, shadows: Optional[float] = None,
        whites: Optional[float] = None, blacks: Optional[float] = None,
        clarity: Optional[float] = None, texture: Optional[float] = None,
        dehaze: Optional[float] = None, saturation: Optional[float] = None,
        temperature: Optional[float] = None, tint: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Add a radial (elliptical) gradient mask with local adjustments (one undoable step).

        The ellipse is the box (top, left, bottom, right), normalized 0..1. The effect is
        inside the ellipse, or outside it when inverted=True (classic custom vignette).
        Feather 0-100 controls the softness of the edge.
        """
        correction = build_correction(name, radial_gradient_mask(top, left, bottom, right, feather, 0, inverted), _adjustments(
            exposure=exposure, contrast=contrast, highlights=highlights, shadows=shadows, whites=whites,
            blacks=blacks, clarity=clarity, texture=texture, dehaze=dehaze, saturation=saturation,
            temperature=temperature, tint=tint))
        result = await execute_command("addMaskCorrection", {"photoId": str(photo_id), "correction": correction})
        return {"success": True, **result}

    @server.tool
    async def develop_add_brush_stroke(
        photo_id: str, name: str, points: List[List[float]],
        radius: float = 0.03, feather: float = 50, flow: float = 100,
        exposure: Optional[float] = None, contrast: Optional[float] = None,
        highlights: Optional[float] = None, shadows: Optional[float] = None,
        whites: Optional[float] = None, blacks: Optional[float] = None,
        clarity: Optional[float] = None, texture: Optional[float] = None,
        dehaze: Optional[float] = None, saturation: Optional[float] = None,
        temperature: Optional[float] = None, tint: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Paint a brush mask along a path, e.g. for dodge & burn (one undoable step).

        points: [[x, y], ...] normalized 0..1 (displayed image), dabs are filled in between.
        radius: brush radius as a fraction of the image (0.03 = 3%). feather/flow 0-100.
        Typical dodge: exposure=+0.3; burn: exposure=-0.3.
        """
        correction = build_correction(name, brush_mask(points, radius, feather, flow), _adjustments(
            exposure=exposure, contrast=contrast, highlights=highlights, shadows=shadows, whites=whites,
            blacks=blacks, clarity=clarity, texture=texture, dehaze=dehaze, saturation=saturation,
            temperature=temperature, tint=tint))
        result = await execute_command("addMaskCorrection", {"photoId": str(photo_id), "correction": correction})
        return {"success": True, "dabs": len(correction["CorrectionMasks"][0]["Dabs"]), **result}

    @server.tool
    async def develop_remove_mask(photo_id: str, name: str) -> Dict[str, Any]:
        """Remove the mask(s) with this exact name (one undoable step)."""
        result = await execute_command("removeMaskCorrection", {"photoId": str(photo_id), "name": name})
        return {"success": True, **result}

    @server.tool
    async def develop_create_ai_mask(
        mask_type: str,
        exposure: Optional[float] = None, contrast: Optional[float] = None,
        highlights: Optional[float] = None, shadows: Optional[float] = None,
        whites: Optional[float] = None, blacks: Optional[float] = None,
        clarity: Optional[float] = None, texture: Optional[float] = None,
        dehaze: Optional[float] = None, saturation: Optional[float] = None,
        temperature: Optional[float] = None, tint: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Create an AI mask on the photo open in Develop and apply local adjustments.

        mask_type: "sky", "subject", "background", "people", "objects", "landscape".
        The plugin waits (up to ~20 s) until Lightroom has computed the mask and
        accepted every value. Slider units: exposure in EV, others -100..100.
        """
        adjustments = _adjustments(
            exposure=exposure, contrast=contrast, highlights=highlights, shadows=shadows, whites=whites,
            blacks=blacks, clarity=clarity, texture=texture, dehaze=dehaze, saturation=saturation,
            temperature=temperature, tint=tint)
        local_settings = {AI_LOCAL_NAMES[k]: v for k, v in adjustments.items()}
        result = await execute_command("createMaskWithLocalAdjustments", {
            "maskType": "aiSelection", "maskSubtype": mask_type, "localSettings": local_settings})
        return {"success": True, **result}

    @server.tool
    async def develop_get_enhance_state() -> Dict[str, Any]:
        """Read the Enhance panel state (AI Denoise, Raw Details, Super Resolution) of the photo in Develop."""
        result = await execute_command("getEnhanceState")
        return {"success": True, **result}

    @server.tool
    async def develop_set_enhance(
        enhance_type: Optional[str] = None, enable: bool = True, denoise_amount: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Turn an Enhance option on/off for the photo in Develop and/or set the AI Denoise amount.
        enhance_type: e.g. "denoise" or "rawDetails" (as reported by develop_get_enhance_state).
        denoise_amount: 0-100. Requires a Lightroom Classic version with in-place Enhance.
        """
        params: Dict[str, Any] = {"enable": enable}
        if enhance_type:
            params["enhanceType"] = enhance_type
        if denoise_amount is not None:
            params["amount"] = denoise_amount
        result = await execute_command("setEnhance", params)
        return {"success": True, **result}
