import cv2
import numpy as np
from scipy import ndimage
from shapely.geometry import Polygon
from skimage.morphology import h_maxima
from skimage.segmentation import watershed

from brynz.geometry import extract_planes, measurement


def room_adjacency(rooms):
    adjacency, overlaps = [], []
    observed = [room for room in rooms if len(room["polygon"]) >= 3]
    for index, first in enumerate(observed):
        first_shape = Polygon(first["polygon"])
        if not first_shape.is_valid:
            continue
        for second in observed[index + 1 :]:
            second_shape = Polygon(second["polygon"])
            if not second_shape.is_valid:
                continue
            intersection = first_shape.intersection(second_shape).area
            if intersection > 0.05:
                overlaps.append([first["id"], second["id"]])
                continue
            for left in first["openings"]:
                for right in second["openings"]:
                    left_wall = next(
                        wall for wall in first["walls"] if wall["id"] == left["surface_id"]
                    )
                    right_wall = next(
                        wall for wall in second["walls"] if wall["id"] == right["surface_id"]
                    )
                    left_mid = _opening_midpoint(left, left_wall)
                    right_mid = _opening_midpoint(right, right_wall)
                    if np.linalg.norm(left_mid - right_mid) < 0.3:
                        adjacency.append(
                            {
                                "rooms": [first["id"], second["id"]],
                                "openings": [left["id"], right["id"]],
                                "status": "candidate",
                                "rule": "Shared-coordinate opening proximity",
                            }
                        )
    return adjacency, overlaps


def _opening_midpoint(opening, wall):
    start, end = np.asarray(wall["start"]), np.asarray(wall["end"])
    tangent = (end - start) / np.linalg.norm(end - start)
    return start + tangent * (opening["offset"]["value"] + opening["width"]["value"] / 2)


def segment_floor(points, prototype, resolution=0.08):
    if len(prototype.get("walls", [])) < 4:
        return [], [], ["Room partitioning withheld: enclosing wall evidence not established."]
    planes = extract_planes(points)
    horizontal = [plane for plane in planes if abs(plane["normal"][1]) > 0.985]
    if not horizontal:
        return [], [], ["Room partitioning skipped: no supported horizontal floor plane."]
    floor_plane = min(horizontal, key=lambda item: item["center"][1])
    floor_points = points[np.abs((points - floor_plane["center"]) @ floor_plane["normal"]) < 0.07]
    if len(floor_points) < 500:
        return [], [], ["Room partitioning skipped: sparse floor coverage."]
    angle = prototype.get("orientation_rad", 0.0)
    cosine, sine = np.cos(angle), np.sin(angle)
    rotation = np.array([[cosine, sine], [-sine, cosine]])
    horizontal_points = points[:, [0, 2]] @ rotation.T
    horizontal_floor = floor_points[:, [0, 2]] @ rotation.T
    minimum = horizontal_points.min(axis=0) - resolution * 3
    maximum = horizontal_points.max(axis=0) + resolution * 3
    shape = np.ceil((maximum - minimum) / resolution).astype(int) + 1
    if shape.max() > 1000:
        return [], [], ["Room partitioning skipped: footprint exceeds bounded raster size."]
    floor_mask = np.zeros((shape[1], shape[0]), dtype=np.uint8)
    pixels = np.floor((horizontal_floor - minimum) / resolution).astype(int)
    floor_mask[pixels[:, 1], pixels[:, 0]] = 1
    floor_mask = cv2.morphologyEx(floor_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    floor_mask = ndimage.binary_fill_holes(floor_mask)
    floor_y = float(floor_plane["center"][1])
    above = points[:, 1] > floor_y + 0.4
    wall_counts = np.zeros_like(floor_mask, dtype=np.int32)
    pixels = np.floor((horizontal_points[above] - minimum) / resolution).astype(int)
    np.add.at(wall_counts, (pixels[:, 1], pixels[:, 0]), 1)
    barrier = cv2.dilate((wall_counts >= 12).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(
        bool
    )
    free = floor_mask & ~barrier
    distance = ndimage.distance_transform_edt(free) * resolution
    peaks = h_maxima(distance, 0.25) & (distance >= 0.45)
    seeds, count = ndimage.label(peaks)
    if count < 2:
        return [], [], ["Room partitioning found no supported multi-room split."]
    labels = watershed(-distance, seeds, mask=free)
    rooms, retained_labels = [], []
    for label in range(1, count + 1):
        mask = (labels == label).astype(np.uint8)
        if mask.sum() * resolution**2 < 1.5:
            continue
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour = max(contours, key=cv2.contourArea)
        contour = cv2.approxPolyDP(contour, 1.0, True).reshape(-1, 2)
        if len(contour) < 3:
            continue
        aligned_polygon = minimum + (contour + 0.5) * resolution
        polygon = aligned_polygon @ rotation
        shape_polygon = Polygon(polygon)
        if not shape_polygon.is_valid:
            continue
        if not shape_polygon.exterior.is_ccw:
            polygon = polygon[::-1]
            shape_polygon = Polygon(polygon)
        room_id = f"room-{len(rooms) + 1}"
        walls = []
        for index, start in enumerate(polygon):
            end = polygon[(index + 1) % len(polygon)]
            length = np.linalg.norm(end - start)
            walls.append(
                {
                    "id": f"{room_id}:wall-{index + 1}",
                    "start": np.round(start, 5).tolist(),
                    "end": np.round(end, 5).tolist(),
                    "length": measurement(length, max(0.16, length * 0.08)),
                }
            )
        rooms.append(
            {
                "id": room_id,
                "name": room_id,
                "polygon": np.round(polygon, 5).tolist(),
                "walls": walls,
                "openings": [],
                "floor_area": measurement(
                    shape_polygon.area, shape_polygon.length * resolution * 2, "m2"
                ),
                "ceiling_height": dict(prototype["ceiling_height"]),
                "floor_level": floor_y,
                "ceiling_level": prototype.get("ceiling_level"),
                "geometry_model": "candidate watershed partition of observed floor; raster boundary is not a fitted wall",
            }
        )
        retained_labels.append(label)
    adjacency = []
    for index, first in enumerate(retained_labels):
        expanded = ndimage.binary_dilation(labels == first, iterations=2)
        for second_index in range(index + 1, len(retained_labels)):
            second = retained_labels[second_index]
            shared_cells = int((expanded & (labels == second)).sum())
            if shared_cells >= 5:
                adjacency.append(
                    {
                        "rooms": [rooms[index]["id"], rooms[second_index]["id"]],
                        "status": "candidate",
                        "rule": "Shared observed free-space watershed boundary",
                        "shared_cells": shared_cells,
                    }
                )
    return (
        rooms,
        adjacency,
        [
            "Watershed rooms and adjacency are candidates, not validated topology.",
            "Incomplete floor coverage, furniture and wide doorways can split or merge rooms.",
        ],
    )
