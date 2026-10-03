from PIL import Image

from brynz.cli import run_capture
from brynz.rgb import prepare_photos


def test_photo_folders_are_not_merged_or_given_fake_dimensions(tmp_path):
    source = tmp_path / "photos"
    for room_id in ["kitchen", "hall"]:
        room = source / room_id
        room.mkdir(parents=True)
        for index in range(2):
            Image.new("RGB", (100, 80), "white").save(room / f"{index}.jpg")
    groups = prepare_photos(source, tmp_path / "images")
    assert set(groups) == {"kitchen", "hall"}
    assert not set(groups["kitchen"]) & set(groups["hall"])
    result = run_capture(source, tmp_path / "out", model_dir=tmp_path / "missing-model")
    assert result["tier"] == "photos"
    assert result["status"] == "insufficient_evidence"
    assert len(result["rooms"]) == 2
    assert all(room["floor_area"]["value"] is None for room in result["rooms"])
    assert any("Single-view fallback unavailable" in item for item in result["warnings"])


def test_live_depth_bypasses_existing_cache(tmp_path):
    import pytest

    torch = pytest.importorskip("torch")
    from types import SimpleNamespace

    from brynz.rgb import _predict_depth

    image_path = tmp_path / "image.jpg"
    Image.new("RGB", (8, 6), "white").save(image_path)
    calls = []

    def processor(**kwargs):
        return {"pixel_values": torch.ones((1, 3, 4, 4))}

    def model(**kwargs):
        calls.append(1)
        return SimpleNamespace(predicted_depth=torch.ones((1, 4, 4)))

    first, hit = _predict_depth(image_path, processor, model, tmp_path, "fixture")
    assert not hit
    cached, hit = _predict_depth(image_path, processor, model, tmp_path, "fixture")
    assert hit and len(calls) == 1
    assert (first == cached).all()
    _, hit = _predict_depth(image_path, processor, model, tmp_path, "fixture", use_cache=False)
    assert not hit and len(calls) == 2


def _pitched_room(pitch_degrees=10, seed=3):
    import numpy as np

    rng = np.random.default_rng(seed)
    floor = np.column_stack((rng.uniform(-2, 2, 4000), np.full(4000, 1.4), rng.uniform(1, 5, 4000)))
    ceiling = floor.copy()
    ceiling[:, 1] = -1.2
    wall = np.column_stack(
        (rng.uniform(-2, 2, 4000), rng.uniform(-1.2, 1.4, 4000), np.full(4000, 5.0))
    )
    angle = np.radians(pitch_degrees)
    rotation = np.array(
        [[1, 0, 0], [0, np.cos(angle), -np.sin(angle)], [0, np.sin(angle), np.cos(angle)]]
    )
    return np.concatenate((floor, ceiling, wall)) @ rotation.T


def test_single_view_ceiling_height_survives_camera_pitch():
    from brynz.rgb import view_ceiling_height

    assert abs(view_ceiling_height(_pitched_room()) - 2.6) < 0.05


def test_single_view_without_ceiling_returns_none():
    from brynz.rgb import view_ceiling_height

    points = _pitched_room()
    assert view_ceiling_height(points[points @ [0, 1, 0] > -0.5]) is None


def test_ceiling_measurement_is_wide_and_labelled():
    from brynz.rgb import ceiling_measurement

    known = ceiling_measurement([2.5, 2.7])
    assert known["interval"][1] - known["interval"][0] >= 0.5 * known["value"]
    assert "Single-view" in known["reason"]
    assert ceiling_measurement([])["value"] is None
