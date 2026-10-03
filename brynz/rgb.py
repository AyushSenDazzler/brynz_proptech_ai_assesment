import hashlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from brynz.geometry import measurement

MODEL_ID = "depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".heic", ".heif"}


def empty_room(room_id, reason):
    return {
        "id": room_id,
        "name": room_id,
        "polygon": [],
        "walls": [],
        "openings": [],
        "floor_area": measurement(unit="m2", reason=reason),
        "ceiling_height": measurement(reason=reason),
        "geometry_model": "No geometry inferred without sufficient evidence.",
    }


def sample_video(path, directory, count=64, max_side=960):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(path))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not capture.isOpened() or total < 1:
        capture.release()
        raise ValueError(f"Cannot decode video: {path}")
    names = []
    try:
        for index, frame in enumerate(np.linspace(0, total - 1, min(count, total), dtype=int)):
            capture.set(cv2.CAP_PROP_POS_FRAMES, int(frame))
            success, image = capture.read()
            if not success:
                continue
            scale = min(1, max_side / max(image.shape[:2]))
            image = cv2.resize(image, None, fx=scale, fy=scale)
            name = f"frame_{index:04}.jpg"
            if not cv2.imwrite(str(directory / name), image):
                raise OSError(f"Could not write frame {name}.")
            names.append(name)
    finally:
        capture.release()
    if not names:
        raise ValueError("Video contains no decodable frames.")
    return {"room-1": names}


def prepare_photos(path, directory):
    path, directory = Path(path), Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    direct = sorted(item for item in path.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES)
    groups = (
        {path.name: direct}
        if direct
        else {
            item.name: sorted(
                file for file in item.iterdir() if file.suffix.lower() in IMAGE_SUFFIXES
            )
            for item in sorted(path.iterdir())
            if item.is_dir()
        }
    )
    groups = {key: value for key, value in groups.items() if value}
    if not groups:
        raise ValueError("No photos found. Provide images or one image folder per room.")
    if any(
        file.suffix.lower() in {".heic", ".heif"} for files in groups.values() for file in files
    ):
        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()
        except ImportError as error:
            raise ValueError("HEIC requires uv sync --extra rgb.") from error
    converted = {}
    for group_index, (room, files) in enumerate(groups.items()):
        names = []
        for index, source in enumerate(files[:8]):
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.thumbnail((960, 960))
                name = f"room_{group_index:03}_image_{index:03}.jpg"
                image.save(directory / name, quality=95)
                names.append(name)
        converted[room] = names
    return converted


def fetch_model(directory):
    from huggingface_hub import snapshot_download

    return snapshot_download(
        MODEL_ID, local_dir=str(directory), allow_patterns=["*.json", "*.safetensors"]
    )


def _depth_model(directory):
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    torch.set_num_threads(4)
    torch.manual_seed(42)
    torch.use_deterministic_algorithms(True)
    processor = AutoImageProcessor.from_pretrained(directory, local_files_only=True, use_fast=False)
    model = AutoModelForDepthEstimation.from_pretrained(directory, local_files_only=True).eval()
    return processor, model


def _predict_depth(image_path, processor, model, cache, model_key, use_cache=True):
    import torch

    digest = hashlib.sha256(image_path.read_bytes() + model_key.encode()).hexdigest()
    cached = cache / f"{digest}.npz"
    if use_cache and cached.exists():
        return np.load(cached)["depth"], True
    with Image.open(image_path) as image:
        inputs = processor(images=image, return_tensors="pt")
        with torch.inference_mode():
            predicted = model(**inputs).predicted_depth
            depth = torch.nn.functional.interpolate(
                predicted[:, None], size=image.size[::-1], mode="bilinear", align_corners=False
            )
        depth = depth[0, 0].numpy().astype(np.float32)
    np.savez_compressed(cached, depth=depth)
    return depth, False


def reconstruct_rgb(images, groups, workspace, model_dir, use_cache=True):
    import pycolmap
    from scipy.spatial.transform import Rotation

    workspace, model_dir = Path(workspace), Path(model_dir)
    if not (model_dir / "config.json").exists():
        raise ValueError(
            "Metric depth weights missing. Run uv run --extra rgb brynz fetch-model first."
        )
    database = workspace / "sfm.db"
    if database.exists():
        database.unlink()
    options = pycolmap.FeatureExtractionOptions()
    options.use_gpu = False
    options.num_threads = 4
    options.sift.max_num_features = 2048
    pycolmap.set_random_seed(42)
    pycolmap.extract_features(
        database,
        images,
        image_names=[name for names in groups.values() for name in names],
        camera_mode=pycolmap.CameraMode.SINGLE,
        reader_options=pycolmap.ImageReaderOptions(
            camera_model="PINHOLE", default_focal_length_factor=0.85
        ),
        extraction_options=options,
        device=pycolmap.Device.cpu,
    )
    matching = pycolmap.FeatureMatchingOptions()
    matching.use_gpu = False
    matching.num_threads = 4
    pycolmap.match_exhaustive(database, matching_options=matching, device=pycolmap.Device.cpu)
    mapper_options = pycolmap.IncrementalPipelineOptions()
    mapper_options.num_threads = 4
    mapper_options.mapper.random_seed = 42
    reconstructions = pycolmap.incremental_mapping(
        database, images, workspace / "sfm", options=mapper_options
    )
    if not reconstructions:
        raise ValueError(
            "Structure-from-motion failed: insufficient overlap or camera translation."
        )
    reconstruction = max(reconstructions.values(), key=lambda item: item.num_reg_images())
    processor, model = _depth_model(model_dir)
    model_key = hashlib.sha256((model_dir / "config.json").read_bytes())
    model_key.update((model_dir / "preprocessor_config.json").read_bytes())
    for weights in sorted(model_dir.glob("*.safetensors")):
        with weights.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                model_key.update(block)
    model_key = model_key.hexdigest()
    cache = workspace / "depth_cache"
    cache.mkdir(exist_ok=True)
    depths, ratios, registered = {}, [], {}
    cache_hits = 0
    for image in reconstruction.images.values():
        if not image.has_pose:
            continue
        depth, hit = _predict_depth(
            Path(images) / image.name, processor, model, cache, model_key, use_cache
        )
        cache_hits += int(hit)
        depths[image.name] = depth
        registered[image.name] = image
        pose = image.cam_from_world()
        for point in image.points2D:
            if not point.has_point3D():
                continue
            point_world = reconstruction.points3D[point.point3D_id].xyz
            camera_point = pose * point_world
            column, row = np.rint(point.xy).astype(int)
            if 0 <= row < depth.shape[0] and 0 <= column < depth.shape[1]:
                predicted = depth[row, column]
                if predicted > 0.2 and camera_point[2] > 0:
                    ratios.append(float(predicted / camera_point[2]))
    if len(ratios) < 30:
        raise ValueError("Not enough triangulated points to anchor learned metric scale.")
    scale = float(np.median(ratios))
    scatter = float(np.median(np.abs(np.asarray(ratios) - scale)) / scale)
    gravity = np.mean(
        [-image.cam_from_world().rotation.matrix()[1] for image in registered.values()], axis=0
    )
    if np.linalg.norm(gravity) < 0.25:
        raise ValueError("Camera orientation does not support a stable gravity prior.")
    gravity /= np.linalg.norm(gravity)
    gravity_rotation, _ = Rotation.align_vectors([[0, 1, 0]], [gravity])
    upright = gravity_rotation.as_matrix()
    clouds, observations = {}, {}
    for room_id, names in groups.items():
        parts, origins = [], []
        for name in names:
            if name not in registered:
                continue
            image, depth = registered[name], depths[name]
            camera = reconstruction.cameras[image.camera_id]
            rows, columns = np.indices(depth.shape)
            pixels = np.column_stack((columns[::8, ::8].ravel(), rows[::8, ::8].ravel()))
            normalized = camera.cam_from_img(pixels)
            distances = depth[::8, ::8].ravel()
            valid = np.isfinite(distances) & (distances > 0.2) & (distances < 10)
            valid &= np.all(np.isfinite(normalized), axis=1)
            camera_points = (
                np.column_stack((normalized, np.ones(len(normalized)))) * distances[:, None]
            )
            pose = image.cam_from_world()
            world = (camera_points[valid] - pose.translation * scale) @ pose.rotation.matrix()
            parts.append(world @ upright.T)
            origin = (-pose.translation * scale) @ pose.rotation.matrix() @ upright.T
            origins.append(origin)
        if parts:
            clouds[room_id] = np.concatenate(parts)
            observations[room_id] = (parts, np.asarray(origins))
    metadata = {
        "registered_images": len(registered),
        "input_images": sum(map(len, groups.values())),
        "sfm_components": len(reconstructions),
        "metric_scale": scale,
        "scale_mad_fraction": scatter,
        "scale_source": "learned indoor metric-depth prior",
        "gravity_source": "mean camera-up direction; assumes upright images and near-level capture",
        "model_id": MODEL_ID,
        "weights_sha256": model_key,
        "cache_hits": cache_hits,
        "warning": "Metric scale and gravity inferred, not measured; disconnected images omitted.",
    }
    return clouds, metadata, observations
