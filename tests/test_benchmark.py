import pytest

from brynz.benchmark import fixloop_axis, repeatability, score
from brynz.geometry import measurement
from brynz.rgb import empty_room


def result():
    room = empty_room("room-1", "fixture")
    room["walls"] = [{"id": "room-1:wall-1", "length": measurement(4, 0.1)}]
    return {"tier": "lidar", "rooms": [room]}


def test_missing_and_phantom_openings_are_misses():
    output = result()
    output["rooms"][0]["openings"] = [{"id": "phantom", "width": measurement(0.9, 0.1)}]
    truth = {"measurements": {"door-1": {"value": 0.9, "kind": "opening"}}}
    scores = score(output, truth)
    assert scores["opening_success_rate"] == 0
    assert scores["opening_gate"] == "fail"
    assert scores["phantom_openings"] == ["phantom"]


def test_missing_truth_is_not_a_pass():
    assert score(result(), {})["opening_gate"] == "unscored"
    assert score(result(), {})["interval_coverage"] is None


def test_missing_height_fails_measurement():
    truth = {"measurements": {"room-1:ceiling_height": {"value": 2.6, "kind": "ceiling_height"}}}
    assert not score(result(), truth)["measurements"][0]["within_tolerance"]


def test_same_capture_cannot_pass_repeatability_gate():
    assert repeatability(result(), result())["gate"] == "unscored"
    output = result()
    output["rooms"][0]["ceiling_height"] = measurement(2.6, 0.1)
    output["rooms"][0]["floor_area"] = measurement(12, 0.5, "m2")
    assert repeatability(output, output, independent=True)["gate"] == "pass"


def test_cross_tier_comparison_cannot_be_repeatability():
    first, second = result(), result()
    second["tier"] = "photos"
    with pytest.raises(ValueError, match="same tier"):
        repeatability(first, second, independent=True)


def test_axis_summary_points_to_retrospective_declaration(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "brynz.cli.run_capture", lambda *args, **kwargs: {**result(), "status": "partial"}
    )
    summary = fixloop_axis(tmp_path, tmp_path)
    assert summary["declaration"] == "fix-declaration-axis-retrospective.json"
