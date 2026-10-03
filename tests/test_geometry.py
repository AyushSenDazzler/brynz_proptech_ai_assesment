import numpy as np

from brynz.geometry import align_fragments, measurement, reconstruct, voxelize


def rectangular_room(seed=4):
    rng = np.random.default_rng(seed)
    clouds = []
    for axis, position in [(0, 0), (0, 4), (1, 0), (1, 2.6), (2, 0), (2, 3)]:
        points = rng.uniform([0, 0, 0], [4, 2.6, 3], (1800, 3))
        points[:, axis] = position + rng.normal(0, 0.005, len(points))
        clouds.append(points)
    return np.concatenate(clouds)


def test_known_room_dimensions():
    room, _, _ = reconstruct(rectangular_room())
    lengths = sorted(wall["length"]["value"] for wall in room["walls"])
    np.testing.assert_allclose(lengths, [3, 3, 4, 4], atol=0.04)
    assert abs(room["ceiling_height"]["value"] - 2.6) < 0.02
    assert abs(room["floor_area"]["value"] - 12) < 0.2


def test_floor_only_is_not_fabricated_room():
    rng = np.random.default_rng(2)
    points = rng.uniform([0, 0, 0], [4, 0.005, 3], (2500, 3))
    room, _, warnings = reconstruct(points)
    assert room["polygon"] == []
    assert room["ceiling_height"]["value"] is None
    assert warnings


def test_unknown_measurement():
    assert measurement()["interval"] is None
    assert measurement(1, 0.1)["status"] == "uncalibrated"


def test_nonfinite_rays_are_not_voxelized():
    points = voxelize(np.array([[0, 0, 1], [np.nan, 1, 2], [1, np.inf, 2]]))
    np.testing.assert_allclose(points, [[0, 0, 1]])


def test_fragment_corrections_are_exposed_for_camera_origin_alignment():
    rng = np.random.default_rng(42)
    points = rng.uniform([0, 0, 0], [4, 2.6, 3], (1000, 3))
    clouds = [points] * 15 + [points + np.array([0.02, 0, 0])] * 15
    corrected, report = align_fragments(clouds)
    translations = np.array(report["fragment_translations_m"])
    assert translations.shape == (2, 3)
    np.testing.assert_allclose(
        corrected[15] - clouds[15], np.broadcast_to(translations[1], points.shape), atol=1e-7
    )
    assert np.linalg.norm(translations[1]) > 0.005
