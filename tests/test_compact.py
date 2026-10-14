"""
Routing logic of the compact tools, with the bridge and the legacy tools faked.
No Lightroom needed.
"""
import pytest

from mcp_server.servers import compact


class FakeLightroom:
    def __init__(self, selected=("42",), crop_angle=1.5):
        self.selected = list(selected)
        self.crop_angle = crop_angle
        self.commands = []
        self.legacy_calls = []

    async def cmd(self, command, params=None):
        self.commands.append((command, params))
        if command == "catalog.getSelectedPhotos":
            return {"photos": [{"id": int(i)} for i in self.selected]}
        if command == "develop.getPhotoGeometry":
            return {"crop": {"CropAngle": self.crop_angle}}
        if command == "develop.getRawSettings":
            return {"settings": {"Exposure2012": 0.5, "Look": {"Name": "IR rb swap", "Amount": 2, "Table": [1] * 99},
                                 "Missing": None}}
        if command == "develop.applySettings":
            return {"applied": len(params["settings"])}
        return {}

    async def legacy(self, name):
        async def fn(**kwargs):
            self.legacy_calls.append((name, kwargs))
            return {"success": True}
        return fn

    def sent(self, command):
        return [params for c, params in self.commands if c == command]


@pytest.fixture
def lr(monkeypatch):
    fake = FakeLightroom()
    monkeypatch.setattr(compact, "_cmd", fake.cmd)
    monkeypatch.setattr(compact, "_legacy", fake.legacy)
    return fake


async def test_set_develop_routes_each_kind_of_setting(lr):
    result = await compact.set_develop("42", {
        "Exposure": 0.3, "Shadows": 20, "Temperature": 5600,
        "ColorGradeMidtoneHue": 210, "Clarity": "default"})

    assert lr.sent("develop.applySettings") == [{"photoId": "42", "settings": {"Exposure": 0.3, "Shadows": 20}}]
    assert lr.sent("develop.setValue") == [{"param": "Temperature", "value": 5600, "photoId": "42"}]
    assert lr.sent("develop.applyExtraSettings")[0]["settings"] == {"ColorGradeMidtoneHue": 210}
    assert lr.sent("develop.resetToDefault") == [{"param": "Clarity", "photoId": "42"}]
    assert set(result["applied"]) == {"Exposure", "Shadows", "Temperature", "ColorGradeMidtoneHue", "Clarity"}


async def test_set_develop_refuses_a_photo_that_is_not_open(lr):
    lr.selected = ["7"]
    with pytest.raises(ValueError, match="select_photo"):
        await compact.set_develop("42", {"Exposure": 0.3})
    assert not lr.sent("develop.applySettings")


async def test_set_develop_rejects_unknown_and_out_of_range_before_applying(lr):
    with pytest.raises(ValueError, match="Unknown setting.*set_geometry"):
        await compact.set_develop("42", {"Exposure": 0.3, "CropLeft": 0.1})
    with pytest.raises(ValueError, match="outside"):
        await compact.set_develop("42", {"Exposure": 9})
    assert not lr.sent("develop.applySettings")


async def test_set_develop_runs_auto_first(lr):
    await compact.set_develop("42", {"Exposure": 0.1}, auto=["tone", "white_balance"])
    order = [c for c, _ in lr.commands if c != "catalog.getSelectedPhotos"]
    assert order[:3] == ["develop.setAutoTone", "develop.setAutoWhiteBalance", "develop.applySettings"]


async def test_s_curve_points(lr):
    await compact.set_tone_curve("42", s_curve=40)
    name, kwargs = lr.legacy_calls[0]
    assert name == "develop_set_channel_curve"
    assert kwargs["points"] == [[0, 0], [64, 54], [128, 128], [192, 202], [255, 255]]


async def test_crop_keeps_the_current_straighten_angle(lr):
    await compact.set_geometry("42", crop={"aspect": "4:5"})
    name, kwargs = lr.legacy_calls[0]
    assert name == "develop_set_crop"
    assert kwargs["angle"] == 1.5 and kwargs["aspect"] == "4:5"


async def test_angle_only_on_a_photo_that_is_not_open_is_written_per_photo(lr):
    lr.selected = ["7"]
    await compact.set_geometry("42", angle=-1.97)
    assert lr.sent("develop.applyExtraSettings")[0]["settings"] == {"CropAngle": -1.97, "HasCrop": True}


async def test_add_mask_routes_by_kind(lr):
    await compact.add_mask("42", "sky", {"exposure": -0.3, "hue": -45})
    await compact.add_mask("42", "radial", {"exposure": 0.2}, area={"left": 0.3, "top": 0.3, "right": 0.7, "bottom": 0.7},
                           name="face")
    assert lr.legacy_calls[0] == ("develop_create_ai_mask", {"mask_type": "sky", "exposure": -0.3, "hue": -45})
    name, kwargs = lr.legacy_calls[1]
    assert name == "develop_add_radial_gradient"
    assert kwargs["name"] == "face" and kwargs["left"] == 0.3 and kwargs["exposure"] == 0.2


async def test_add_mask_rejects_hue_on_gradients(lr):
    with pytest.raises(ValueError, match="hue"):
        await compact.add_mask("42", "linear", {"hue": 10}, area={})


async def test_get_photo_trims_profile_tables_and_empty_values(lr):
    result = await compact.get_photo("42", include=["develop"])
    assert result["develop"] == {"Exposure2012": 0.5, "Look": {"Name": "IR rb swap", "Amount": 2}}
