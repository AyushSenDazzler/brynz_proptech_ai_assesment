import numpy as np
from scipy.signal import find_peaks
from scipy.spatial import cKDTree


def measurement(value=None, radius=None, unit="m", reason=None):
    if value is None:
        return {
            "value": None,
            "interval": None,
            "unit": unit,
            "status": "unobserved",
            "reason": reason or "Insufficient evidence.",
        }
    value, radius = float(value), max(float(radius), 0.001)
    return {
        "value": round(value, 5),
        "interval": [round(max(0, value - radius), 5), round(value + radius, 5)],
        "unit": unit,
        "status": "uncalibrated",
        "reason": reason,
    }


def voxelize(points, size=0.025):
    points = points[np.all(np.isfinite(points), axis=1)]
    if not len(points):
        raise ValueError("No finite 3D points available.")
    keys = np.floor(points / size).astype(np.int64)
    _, indices = np.unique(keys, axis=0, return_index=True)
    return points[np.sort(indices)]


def extract_planes(points, seed=42, max_planes=12, threshold=0.035):
    rng = np.random.default_rng(seed)
    sample = points[rng.choice(len(points), min(18000, len(points)), replace=False)]
    remaining = sample.copy()
    planes = []
    minimum = max(90, int(len(sample) * 0.018))
    for _ in range(max_planes):
        if len(remaining) < minimum:
            break
        best_mask = None
        best_count = 0
        for _ in range(120):
            triplet = remaining[rng.choice(len(remaining), 3, replace=False)]
            normal = np.cross(triplet[1] - triplet[0], triplet[2] - triplet[0])
            norm = np.linalg.norm(normal)
            if norm < 1e-8:
                continue
            normal /= norm
            mask = np.abs((remaining - triplet[0]) @ normal) < threshold
            count = int(mask.sum())
            if count > best_count:
                best_count, best_mask = count, mask
        if best_count < minimum:
            break
        support = remaining[best_mask]
        center = np.median(support, axis=0)
        _, _, basis = np.linalg.svd(support - center, full_matrices=False)
        normal = basis[-1]
        if normal[np.argmax(np.abs(normal))] < 0:
            normal = -normal
        residual = float(np.median(np.abs((support - center) @ normal)))
        planes.append(
            {
                "normal": normal,
                "center": center,
                "count": best_count,
                "residual": residual,
                "points": support,
            }
        )
        remaining = remaining[~best_mask]
    return planes


def align_fragments(clouds, enabled=True):
    if not enabled or len(clouds) < 8:
        return clouds, {
            "method": "disabled",
            "accepted_constraints": 0,
            "warning": "Poses used as-is; drift gate not satisfied.",
        }
    fragments = [
        voxelize(np.concatenate(clouds[index : index + 15]), 0.06)
        for index in range(0, len(clouds), 15)
    ]
    corrected = [fragments[0]]
    corrections = [np.zeros(3)]
    accepted = 0
    for fragment in fragments[1:]:
        tree = cKDTree(corrected[-1])
        correction = corrections[-1].copy()
        moved = fragment + correction
        for _ in range(8):
            distance, indices = tree.query(moved, workers=1)
            valid = distance < 0.12
            if int(valid.sum()) < max(100, int(len(fragment) * 0.15)):
                break
            delta = np.median(corrected[-1][indices[valid]] - moved[valid], axis=0)
            if np.linalg.norm(correction + delta) > 0.15:
                break
            moved += delta
            correction += delta
            if np.linalg.norm(delta) < 0.001:
                break
        accepted += int(np.linalg.norm(correction) > 0.001)
        corrections.append(correction)
        corrected.append(moved)
    corrected_clouds = [cloud + corrections[index // 15] for index, cloud in enumerate(clouds)]
    return corrected_clouds, {
        "method": "bounded overlapping-fragment translation ICP",
        "accepted_constraints": accepted,
        "fragment_translations_m": [np.round(item, 8).tolist() for item in corrections],
        "max_translation_m": round(float(max(np.linalg.norm(item) for item in corrections)), 5),
        "warning": "Translation-only local correction; no global loop closure or drift guarantee.",
    }


def _horizontal_surfaces(planes):
    horizontal = [plane for plane in planes if abs(plane["normal"][1]) > 0.985]
    levels = []
    for plane in sorted(horizontal, key=lambda item: -item["count"]):
        level = float(plane["center"][1])
        if not any(abs(level - previous[0]) < 0.12 for previous in levels):
            levels.append((level, plane))
    return sorted(levels, key=lambda item: item[0])


def _axis_walls(points, axis, low_y, high_y):
    band = points[(points[:, 1] > low_y + 0.25) & (points[:, 1] < high_y - 0.25)]
    if len(band) < 200:
        return []
    values = band[:, axis]
    lower, upper = np.percentile(values, [0.5, 99.5])
    bins = np.arange(lower - 0.04, upper + 0.08, 0.04)
    if len(bins) < 4:
        return []
    histogram, edges = np.histogram(values, bins=bins)
    peaks, _ = find_peaks(
        np.pad(histogram, 1), prominence=max(15, histogram.max() * 0.12), distance=5
    )
    candidates = []
    for peak in peaks - 1:
        if peak < 0 or peak >= len(histogram):
            continue
        level = (edges[peak] + edges[peak + 1]) / 2
        support = band[np.abs(values - level) < 0.06]
        if len(support) < 60:
            continue
        span = np.percentile(support[:, 1], 95) - np.percentile(support[:, 1], 5)
        if span < min(0.8, (high_y - low_y) * 0.45):
            continue
        candidates.append((float(np.median(support[:, axis])), len(support)))
    candidates = sorted(candidates, key=lambda item: -item[1])[:4]
    return sorted(candidates, key=lambda item: item[0])


def reconstruct(points, room_id="room-1", estimator="robust"):
    points = voxelize(points)
    planes = extract_planes(points)
    levels = _horizontal_surfaces(planes)
    warnings = []
    room = {
        "id": room_id,
        "name": room_id,
        "polygon": [],
        "walls": [],
        "openings": [],
        "floor_area": measurement(unit="m2"),
        "ceiling_height": measurement(),
        "floor_level": None,
        "ceiling_level": None,
        "geometry_model": "single Manhattan rectangle; not arbitrary multi-room segmentation",
    }
    if len(levels) >= 2 and levels[-1][0] - levels[0][0] >= 1.8:
        floor, ceiling = levels[0], levels[-1]
        height = ceiling[0] - floor[0]
        radius = max(0.03, 3 * (floor[1]["residual"] + ceiling[1]["residual"]))
        room["ceiling_height"] = measurement(height, radius)
        low_y, high_y = floor[0], ceiling[0]
        room["floor_level"], room["ceiling_level"] = round(low_y, 5), round(high_y, 5)
    else:
        low_y, high_y = np.percentile(points[:, 1], [1, 99])
        warnings.append("Floor and ceiling not both observed; ceiling height withheld.")
    vertical = [plane for plane in planes if abs(plane["normal"][1]) < 0.12]
    if not vertical or high_y - low_y < 1.2:
        warnings.append("Insufficient vertical-wall support; room footprint withheld.")
        return room, points, warnings
    dominant = max(vertical, key=lambda plane: plane["count"])
    angle = np.arctan2(dominant["normal"][2], dominant["normal"][0])
    cosine, sine = np.cos(angle), np.sin(angle)
    rotation = np.array([[cosine, 0, sine], [0, 1, 0], [-sine, 0, cosine]])
    aligned = points @ rotation.T
    axis_x, axis_z = _axis_walls(aligned, 0, low_y, high_y), _axis_walls(aligned, 2, low_y, high_y)
    if len(axis_x) < 2 or len(axis_z) < 2:
        warnings.append("Four enclosing walls not established; room footprint withheld.")
        return room, points, warnings
    min_x, max_x = axis_x[0][0], axis_x[-1][0]
    min_z, max_z = axis_z[0][0], axis_z[-1][0]
    if estimator == "baseline":
        min_x, max_x = np.percentile(aligned[:, 0], [0.5, 99.5])
        min_z, max_z = np.percentile(aligned[:, 2], [0.5, 99.5])
    if max_x - min_x < 0.7 or max_z - min_z < 0.7:
        warnings.append("Implausible enclosure; footprint withheld.")
        return room, points, warnings
    polygon = np.array([[min_x, min_z], [max_x, min_z], [max_x, max_z], [min_x, max_z]])
    world = np.column_stack((polygon[:, 0], np.zeros(4), polygon[:, 1])) @ rotation
    room["polygon"] = np.round(world[:, [0, 2]], 5).tolist()
    for index in range(4):
        start, end = world[index, [0, 2]], world[(index + 1) % 4, [0, 2]]
        length = np.linalg.norm(end - start)
        room["walls"].append(
            {
                "id": f"{room_id}:wall-{index + 1}",
                "start": np.round(start, 5).tolist(),
                "end": np.round(end, 5).tolist(),
                "length": measurement(length, max(0.04, length * 0.02)),
            }
        )
    width, depth = max_x - min_x, max_z - min_z
    room["floor_area"] = measurement(width * depth, (width + depth) * 0.08, "m2")
    room["orientation_rad"] = round(float(angle), 6)
    warnings.append(
        "Rectangular enclosure is a model assumption; furniture and alcoves can bias it."
    )
    warnings.append("Opening detection unavailable; empty openings does not assert no openings.")
    return room, points, warnings
