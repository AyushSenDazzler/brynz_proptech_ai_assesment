import numpy as np

from brynz.capture import backproject


def test_opencv_backprojection_and_confidence():
    depth = np.array([[1.0, 2.0], [0.0, 6.0]])
    confidence = np.array([[2, 1], [2, 2]])
    points = backproject(depth, [1, 1, 0, 0], np.eye(3), np.array([1, 2, 3]), 2, confidence)
    np.testing.assert_allclose(points, [[1, 2, 4]])


def test_downward_pixels_map_to_positive_camera_y():
    points = backproject(np.ones((2, 1)), [1, 1, 0, 0], np.eye(3), np.zeros(3))
    np.testing.assert_allclose(points, [[0, 0, 1], [0, 1, 1]])


def test_legacy_mode_can_reproduce_before_run():
    points = backproject(
        np.ones((2, 1)), [1, 1, 0, 0], np.eye(3), np.zeros(3), convention="legacy-arkit"
    )
    np.testing.assert_allclose(points, [[0, 0, -1], [0, -1, -1]])
