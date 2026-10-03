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
