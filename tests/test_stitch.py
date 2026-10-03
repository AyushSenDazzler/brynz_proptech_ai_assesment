import numpy as np
from shapely.geometry import Polygon

from brynz.geometry import measurement
from brynz.stitch import room_adjacency, segment_floor


def room(identifier, left, right):
    return {
        "id": identifier,
        "polygon": [[left, 0], [right, 0], [right, 3], [left, 3]],
        "walls": [],
        "openings": [],
        "ceiling_height": measurement(),
    }


def test_overlap_is_reported_not_silently_stitched():
    adjacency, overlaps = room_adjacency([room("a", 0, 4), room("b", 3, 7)])
    assert adjacency == []
    assert overlaps == [["a", "b"]]


def test_touching_rooms_without_opening_evidence_are_not_connected():
    assert room_adjacency([room("a", 0, 4), room("b", 4, 8)]) == ([], [])


def test_floor_partitions_are_nonoverlapping_candidates():
    columns, rows = np.meshgrid(np.arange(0, 8, 0.05), np.arange(0, 4, 0.05))
    floor = np.column_stack((columns.ravel(), np.zeros(columns.size), rows.ravel()))
    along, height = np.meshgrid(np.arange(0, 4, 0.02), np.arange(0.4, 2.6, 0.04))
    barrier = np.column_stack((np.full(along.size, 4), height.ravel(), along.ravel()))
    barrier = barrier[(barrier[:, 2] < 1.6) | (barrier[:, 2] > 2.4)]
    prototype = {"ceiling_height": measurement(2.6, 0.05), "ceiling_level": 2.6, "walls": [{}] * 4}
    rooms, _, _ = segment_floor(np.concatenate((floor, barrier)), prototype)
    assert len(rooms) >= 2
    for index, first in enumerate(rooms):
        for second in rooms[index + 1 :]:
            assert Polygon(first["polygon"]).intersection(Polygon(second["polygon"])).area < 0.01


def test_floor_without_enclosing_walls_cannot_become_rooms():
    points = np.array([[0, 0, 0], [4, 0, 3]])
    rooms, adjacency, warnings = segment_floor(points, {"walls": []})
    assert rooms == []
    assert adjacency == []
    assert warnings
