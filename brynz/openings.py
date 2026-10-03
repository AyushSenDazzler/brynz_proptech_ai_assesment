import cv2
import numpy as np

from brynz.geometry import measurement


def detect_openings(room, clouds, origins, resolution=0.04):
    if not room["walls"]:
        return []
    all_points = np.concatenate(clouds)
    floor = room.get("floor_level")
    ceiling = room.get("ceiling_level")
    low_y = float(np.percentile(all_points[:, 1], 1)) if floor is None else floor
    high_y = float(np.percentile(all_points[:, 1], 99)) if ceiling is None else ceiling
    found = []
    for wall in room["walls"]:
        start, end = np.asarray(wall["start"]), np.asarray(wall["end"])
        length = np.linalg.norm(end - start)
        tangent = (end - start) / length
        inward = np.array([-tangent[1], tangent[0]])
        width_bins = max(1, int(np.ceil(length / resolution)))
        height_bins = max(1, int(np.ceil((high_y - low_y) / resolution)))
        if height_bins < 20:
            continue
        beyond = np.zeros((height_bins, width_bins), dtype=np.int32)
        occupied = np.zeros_like(beyond)
        for points, origin in zip(clouds, origins, strict=True):
            horizontal = points[:, [0, 2]] - start
            signed = horizontal @ inward
            origin_signed = float((origin[[0, 2]] - start) @ inward)
            if origin_signed < 0.15:
                continue
            hit = np.abs(signed) < 0.06
            along = horizontal[hit] @ tangent
            columns = np.floor(along / resolution).astype(int)
            rows = np.floor((points[hit, 1] - low_y) / resolution).astype(int)
            valid = (columns >= 0) & (columns < width_bins) & (rows >= 0) & (rows < height_bins)
            np.add.at(occupied, (rows[valid], columns[valid]), 1)
            behind = signed < -0.12
            if not behind.any():
                continue
            fraction = origin_signed / (origin_signed - signed[behind])
            crossing = origin + fraction[:, None] * (points[behind] - origin)
            columns = np.floor(((crossing[:, [0, 2]] - start) @ tangent) / resolution).astype(int)
            rows = np.floor((crossing[:, 1] - low_y) / resolution).astype(int)
            valid = (columns >= 0) & (columns < width_bins) & (rows >= 0) & (rows < height_bins)
            np.add.at(beyond, (rows[valid], columns[valid]), 1)
        candidate = ((beyond >= 2) & (occupied < 3)).astype(np.uint8)
        candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, np.ones((5, 3), np.uint8))
        components, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, 8)
        for component in range(1, components):
            left, bottom, width_cells, height_cells, area = stats[component]
            width, height = width_cells * resolution, height_cells * resolution
            if not (
                0.5 <= width <= 2.5
                and height >= 0.7
                and area / (width_cells * height_cells) >= 0.55
            ):
                continue
            evidence = int(beyond[labels == component].sum())
            if evidence < 100:
                continue
            opening_type = (
                "door"
                if floor is not None and bottom * resolution < 0.25 and height >= 1.6
                else "opening"
            )
            found.append(
                {
                    "id": f"{wall['id']}:opening-{component}",
                    "surface_id": wall["id"],
                    "class": opening_type,
                    "status": "candidate",
                    "beyond_wall_rays": evidence,
                    "offset": measurement(left * resolution, resolution * 2),
                    "width": measurement(width, max(0.08, width * 0.05)),
                    "height": measurement(height, max(0.08, height * 0.05)),
                    "bottom_height": measurement(bottom * resolution, 0.08),
                    "rule": "Beyond-wall ray support, low wall occupancy, connected gap",
                }
            )
    return found
