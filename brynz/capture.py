import csv
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation


def backproject(
    depth,
    intrinsics,
    rotation,
    translation,
    min_confidence=None,
    confidence=None,
    convention="opencv",
):
    height, width = depth.shape
    rows, columns = np.indices((height, width))
    valid = np.isfinite(depth) & (depth >= 0.2) & (depth <= 5.0)
    if confidence is not None and min_confidence is not None:
        valid &= confidence >= min_confidence
    fx, fy, cx, cy = intrinsics
    distance = depth[valid]
    camera = np.column_stack(
        ((columns[valid] - cx) * distance / fx, (rows[valid] - cy) * distance / fy, distance)
    )
    if convention == "legacy-arkit":
        camera[:, 1:] *= -1
    return camera @ rotation.T + translation


def load_stray(
    path, stride=10, pixel_stride=3, confidence_threshold=2, start=0, stop=None, convention="opencv"
):
    path = Path(path)
    with (path / "odometry.csv").open(newline="", encoding="utf-8-sig") as stream:
        records = list(csv.DictReader(stream, skipinitialspace=True))
    clouds, origins, frame_ids, warnings = [], [], [], []
    reference_width, reference_height = 1920.0, 1440.0
    video = cv2.VideoCapture(str(path / "rgb.mp4"))
    if video.isOpened():
        reference_width = video.get(cv2.CAP_PROP_FRAME_WIDTH)
        reference_height = video.get(cv2.CAP_PROP_FRAME_HEIGHT)
    else:
        warnings.append("RGB resolution unavailable; assumed 1920x1440 for intrinsics scaling.")
    video.release()
    for record in records[start:stop:stride]:
        frame_id = record["frame"].strip()
        depth_path = path / "depth" / f"{frame_id}.png"
        if not depth_path.exists():
            warnings.append(f"Missing depth frame {frame_id}.")
            continue
        with Image.open(depth_path) as image:
            depth = np.asarray(image, dtype=np.float64) / 1000.0
        height, width = depth.shape
        confidence_path = path / "confidence" / f"{frame_id}.png"
        confidence = None
        if confidence_path.exists():
            with Image.open(confidence_path) as image:
                confidence = np.asarray(image)[::pixel_stride, ::pixel_stride]
        elif "Confidence maps missing; depth is unfiltered." not in warnings:
            warnings.append("Confidence maps missing; depth is unfiltered.")
        rotation = Rotation.from_quat([float(record[key]) for key in ("qx", "qy", "qz", "qw")])
        translation = np.array([float(record[key]) for key in ("x", "y", "z")])
        intrinsics = np.array([float(record[key]) for key in ("fx", "fy", "cx", "cy")])
        intrinsics *= [
            width / reference_width,
            height / reference_height,
            width / reference_width,
            height / reference_height,
        ]
        intrinsics /= pixel_stride
        points = backproject(
            depth[::pixel_stride, ::pixel_stride],
            intrinsics,
            rotation.as_matrix(),
            translation,
            confidence_threshold,
            confidence,
            convention,
        )
        if len(points):
            clouds.append(points)
            origins.append(translation)
            frame_ids.append(frame_id)
    if not clouds:
        raise ValueError("No valid depth samples. Check the capture and confidence threshold.")
    return clouds, np.asarray(origins), frame_ids, warnings
