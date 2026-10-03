import csv
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation

from brynz.capture import backproject
from brynz.geometry import measurement


def image_candidates(image):
    image = cv2.resize(image, (256, 192))
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    stain = cv2.inRange(hsv, np.array([12, 45, 50]), np.array([40, 220, 235]))
    stain = cv2.morphologyEx(stain, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    dark_lines = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, np.ones((7, 7), np.uint8))
    cracks = (dark_lines > 45).astype(np.uint8) * 255
    candidates = []
    for damage_class, mask in [("water_stain", stain), ("crack", cracks)]:
        count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for label in range(1, count):
            left, top, width, height, area = stats[label]
            if not 35 <= area <= 4000:
                continue
            if damage_class == "crack" and max(width, height) / max(1, min(width, height)) < 4:
                continue
            candidates.append(
                {
                    "class": damage_class,
                    "mask": labels == label,
                    "pixel_box": [int(left), int(top), int(width), int(height)],
                }
            )
    return candidates[:12]


def rules_and_scope(regions):
    flags, scope = [], []
    for region in regions:
        if region["class"] == "water_stain":
            rule = (
                "stain_near_wall_base"
                if region.get("bottom_height_m") is not None and region["bottom_height_m"] < 0.3
                else "visible_stain_on_wall"
            )
            flags.append(
                {
                    "surface_id": region["surface_id"],
                    "region_id": region["id"],
                    "rule": rule,
                    "flag": "possible_concealed_moisture",
                    "status": "review_required",
                    "explanation": "Candidate discoloration is not evidence of a hidden leak.",
                }
            )
        scope.append(
            {
                "id": f"scope:{region['id']}",
                "surface_id": region["surface_id"],
                "region_id": region["id"],
                "action": "inspect_candidate_before_repair",
                "quantity": region["area"],
                "status": "pending_review",
            }
        )
    return flags, scope


def scan_lidar_damage(path, room, frame_ids, convention="opencv", frame_offsets=None):
    path = Path(path)
    if not room["walls"]:
        return [], ["Damage projection skipped: no fitted wall surfaces."]
    with (path / "odometry.csv").open(newline="", encoding="utf-8-sig") as stream:
        records = {
            record["frame"].strip(): record
            for record in csv.DictReader(stream, skipinitialspace=True)
        }
    selected = frame_ids[:: max(1, len(frame_ids) // 10)][:10]
    video = cv2.VideoCapture(str(path / "rgb.mp4"))
    width, height = video.get(cv2.CAP_PROP_FRAME_WIDTH), video.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if not video.isOpened():
        video.release()
        return [], ["Damage projection skipped: RGB video unavailable."]
    regions = []
    try:
        for frame_id in selected:
            video.set(cv2.CAP_PROP_POS_FRAMES, int(frame_id))
            success, image = video.read()
            if not success:
                continue
            candidates = image_candidates(image)
            if not candidates:
                continue
            with Image.open(path / "depth" / f"{frame_id}.png") as depth_image:
                depth = np.asarray(depth_image, dtype=float) / 1000
            confidence_path = path / "confidence" / f"{frame_id}.png"
            if not confidence_path.exists():
                continue
            with Image.open(confidence_path) as confidence_image:
                confidence = np.asarray(confidence_image)
            record = records[frame_id]
            intrinsics = np.array([float(record[key]) for key in ["fx", "fy", "cx", "cy"]])
            intrinsics *= [256 / width, 192 / height, 256 / width, 192 / height]
            rotation = Rotation.from_quat(
                [float(record[key]) for key in ["qx", "qy", "qz", "qw"]]
            ).as_matrix()
            translation = np.array([float(record[key]) for key in ["x", "y", "z"]])
            if frame_offsets is not None:
                translation += frame_offsets.get(frame_id, np.zeros(3))
            for candidate in candidates:
                masked = np.where(candidate["mask"], depth, 0)
                points = backproject(
                    masked, intrinsics, rotation, translation, 2, confidence, convention
                )
                if len(points) < 25:
                    continue
                center = np.median(points, axis=0)
                surfaces = []
                for wall in room["walls"]:
                    start, end = np.asarray(wall["start"]), np.asarray(wall["end"])
                    tangent = (end - start) / np.linalg.norm(end - start)
                    inward = np.array([-tangent[1], tangent[0]])
                    along = (center[[0, 2]] - start) @ tangent
                    if 0 <= along <= wall["length"]["value"]:
                        distance = abs((center[[0, 2]] - start) @ inward)
                        surfaces.append((distance, wall, tangent))
                if not surfaces:
                    continue
                distance, wall, tangent = min(surfaces, key=lambda item: item[0])
                if distance > 0.15:
                    continue
                horizontal = points[:, [0, 2]] @ tangent
                extent_width = np.percentile(horizontal, 95) - np.percentile(horizontal, 5)
                extent_height = np.percentile(points[:, 1], 95) - np.percentile(points[:, 1], 5)
                area = float(extent_width * extent_height)
                if not 0.002 <= area <= 4:
                    continue
                if any(
                    region["surface_id"] == wall["id"]
                    and region["class"] == candidate["class"]
                    and np.linalg.norm(np.array(region["center_world"]) - center) < 0.3
                    for region in regions
                ):
                    continue
                floor = room.get("floor_level")
                regions.append(
                    {
                        "id": f"{wall['id']}:damage-{len(regions) + 1}",
                        "surface_id": wall["id"],
                        "class": candidate["class"],
                        "status": "review_required",
                        "classifier": "HSV discoloration / dark-line heuristic, not semantic recognition",
                        "frame_id": frame_id,
                        "pixel_box": candidate["pixel_box"],
                        "center_world": np.round(center, 5).tolist(),
                        "area": measurement(area, area * 0.75, "m2"),
                        "width": measurement(extent_width, max(0.05, extent_width * 0.5)),
                        "height": measurement(extent_height, max(0.05, extent_height * 0.5)),
                        "bottom_height_m": float(center[1] - floor) if floor is not None else None,
                    }
                )
    finally:
        video.release()
    return regions, [
        "Damage screen is a non-semantic heuristic: furniture, wood, shadows and patterns can trigger it.",
        "Damage extents are projected bounding rectangles, not verified segmented damaged area.",
        "Video frame-index alignment is assumed; desynchronization can misassign damage.",
    ]
