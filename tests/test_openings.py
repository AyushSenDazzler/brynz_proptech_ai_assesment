import numpy as np

from brynz.geometry import measurement
from brynz.openings import detect_openings


def wall_fixture():
    columns, rows = np.meshgrid(np.arange(0, 4, 0.02), np.arange(0, 2.6, 0.02))
    wall = np.column_stack((columns.ravel(), rows.ravel(), np.zeros(columns.size)))
    door = (wall[:, 0] > 1.2) & (wall[:, 0] < 2.1) & (wall[:, 1] < 2.1)
    origin = np.array([1.6, 1.3, 1.5])
    crossings = wall[door]
    behind = origin + (crossings - origin) * 1.5
    room = {
        "floor_level": 0,
        "ceiling_level": 2.6,
        "walls": [{"id": "wall-1", "start": [0, 0], "end": [4, 0], "length": measurement(4, 0.04)}],
    }
    return room, wall[~door], behind, origin


def test_gap_without_beyond_wall_evidence_is_not_an_opening():
    room, wall, _, origin = wall_fixture()
    assert detect_openings(room, [wall], np.array([origin])) == []


def test_supported_door_candidate():
    room, wall, behind, origin = wall_fixture()
    found = detect_openings(room, [np.concatenate((wall, behind, behind))], np.array([origin]))
    assert len(found) == 1
    assert found[0]["class"] == "door"
    assert abs(found[0]["width"]["value"] - 0.9) < 0.12
