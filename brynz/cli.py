import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

from brynz.capture import load_stray
from brynz.geometry import align_fragments, reconstruct
from brynz.output import render, validate, write_json


def run_capture(
    path,
    out,
    stride=10,
    pixel_stride=3,
    drift=True,
    estimator="robust",
    start=0,
    stop=None,
    convention="opencv",
    model_dir=Path("models/metric-small"),
    live=False,
    partition=True,
):
    path, out = Path(path), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    if not (path / "odometry.csv").exists():
        candidates = list(path.glob("*/odometry.csv")) if path.is_dir() else []
        if len(candidates) == 1:
            path = candidates[0].parent
        else:
            return run_rgb_capture(path, out, model_dir, live, started)
    clouds, origins, frame_ids, warnings = load_stray(
        path, stride, pixel_stride, start=start, stop=stop, convention=convention
    )
    corrected, drift_report = align_fragments(clouds, drift)
    frame_offsets = {}
    if "fragment_translations_m" in drift_report:
        shifts = np.asarray(drift_report["fragment_translations_m"])[np.arange(len(origins)) // 15]
        frame_offsets = dict(zip(frame_ids, shifts, strict=True))
        origins = origins + shifts
    room, cloud, geometry_warnings = reconstruct(np.concatenate(corrected), estimator=estimator)
    from brynz.openings import detect_openings

    room["openings"] = detect_openings(room, corrected, origins)
    geometry_warnings = [
        warning
        for warning in geometry_warnings
        if not warning.startswith("Opening detection unavailable")
    ]
    geometry_warnings.append(
        "Openings are unverified geometry candidates; absence does not establish no openings."
    )
    from brynz.damage import rules_and_scope, scan_lidar_damage

    regions, damage_warnings = scan_lidar_damage(path, room, frame_ids, convention, frame_offsets)
    flags, scope = rules_and_scope(regions)
    from brynz.stitch import segment_floor

    segmented, adjacency, partition_warnings = (
        segment_floor(cloud, room)
        if partition
        else ([], [], ["Watershed disabled; isolated rectangular layout."])
    )
    rooms = segmented if len(segmented) >= 2 else [room]
    if len(segmented) >= 2:
        regions, flags, scope = [], [], []
        for candidate_room in rooms:
            candidate_room["openings"] = detect_openings(candidate_room, corrected, origins)
            projected, messages = scan_lidar_damage(
                path, candidate_room, frame_ids, convention, frame_offsets
            )
            regions.extend(projected)
            damage_warnings.extend(messages)
        flags, scope = rules_and_scope(regions)
    result = {
        "schema_version": "brynz-local-0.1",
        "tier": "lidar",
        "status": "partial" if room["polygon"] else "insufficient_evidence",
        "rooms": rooms,
        "adjacency": adjacency if len(segmented) >= 2 else [],
        "damage_regions": regions,
        "concealed_flags": flags,
        "scope_items": scope,
        "drift": drift_report,
        "warnings": warnings
        + geometry_warnings
        + damage_warnings
        + partition_warnings
        + [
            "Intervals are engineering bounds, not calibrated confidence intervals.",
            "Multi-room partitions and damage screen are heuristic and unverified.",
            "Output uses a provisional local schema; published Round 1 schema not supplied.",
        ],
        "provenance": {
            "input": str(path.resolve()),
            "sampled_frames": len(frame_ids),
            "points": len(cloud),
            "frame_stride": stride,
            "pixel_stride": pixel_stride,
            "frame_range": [start, stop],
            "estimator": estimator,
            "camera_convention": convention,
            "layout": "partition" if partition else "rectangle",
            "odometry_sha256": hashlib.sha256((path / "odometry.csv").read_bytes()).hexdigest(),
            "calibration": "unverified",
            "model_weights": "none",
        },
    }
    validate(result)
    write_json(out / "result.json", result)
    render(result, out, cloud)
    np.savez_compressed(out / "cloud.npz", points=cloud, camera_origins=origins)
    write_json(out / "timing.json", {"elapsed_seconds": round(time.perf_counter() - started, 3)})
    return result


def run_rgb_capture(path, out, model_dir, live, started):
    from brynz.rgb import empty_room, prepare_photos, reconstruct_rgb, sample_video

    tier = "video" if path.suffix.lower() in {".mp4", ".mov", ".m4v"} else "photos"
    images = out / "images"
    groups = sample_video(path, images) if tier == "video" else prepare_photos(path, images)
    rooms, clouds, warnings, provenance = [], [], [], {}
    try:
        reconstructed, provenance, observations = reconstruct_rgb(
            images, groups, out, model_dir, not live
        )
        for room_id in groups:
            if room_id not in reconstructed:
                rooms.append(
                    empty_room(room_id, "No images registered in the shared reconstruction.")
                )
                continue
            room, cloud, messages = reconstruct(reconstructed[room_id], room_id)
            from brynz.openings import detect_openings

            room["openings"] = detect_openings(room, *observations[room_id])
            uncertainty = max(
                0.12 if tier == "video" else 0.25, provenance["scale_mad_fraction"] * 3
            )
            from brynz.geometry import measurement

            for item in [room["ceiling_height"], room["floor_area"]] + [
                wall["length"] for wall in room["walls"]
            ]:
                if item["value"] is not None:
                    item.update(
                        measurement(
                            item["value"],
                            item["value"] * uncertainty * (2 if item["unit"] == "m2" else 1),
                            item["unit"],
                        )
                    )
            rooms.append(room)
            clouds.append(cloud)
            warnings.extend(messages)
    except ImportError as error:
        warnings.append(f"RGB dependency unavailable: {error}. Install uv sync --extra rgb.")
    except (ValueError, RuntimeError, OSError) as error:
        warnings.append(str(error))
    if not rooms:
        rooms = [
            empty_room(room_id, warnings[-1] if warnings else "Reconstruction failed.")
            for room_id in groups
        ]
    from brynz.stitch import room_adjacency

    adjacency, overlaps = room_adjacency(rooms)
    if overlaps:
        warnings.append(
            f"Room overlaps unresolved: {overlaps}. Whole-property stitch gate not satisfied."
        )
    result = {
        "schema_version": "brynz-local-0.1",
        "tier": tier,
        "status": "partial" if any(room["polygon"] for room in rooms) else "insufficient_evidence",
        "rooms": rooms,
        "adjacency": adjacency,
        "damage_regions": [],
        "concealed_flags": [],
        "scope_items": [],
        "drift": {"method": "SfM bundle adjustment", "warning": "No explicit loop closure."},
        "provenance": {"input": str(path.resolve()), "calibration": "unverified", **provenance},
        "warnings": warnings
        + [
            "RGB measurements depend on a learned scale prior and inferred gravity.",
            "Intervals uncalibrated; no photo/video accuracy gate claimed.",
            "Shared SfM may place rooms but adjacency and non-overlap are not guaranteed.",
            "RGB damage screening unavailable; geometric openings are unverified candidates.",
        ],
    }
    validate(result)
    write_json(out / "result.json", result)
    cloud = np.concatenate(clouds) if clouds else None
    render(result, out, cloud)
    if cloud is not None:
        np.savez_compressed(out / "cloud.npz", points=cloud)
    write_json(out / "timing.json", {"elapsed_seconds": round(time.perf_counter() - started, 3)})
    return result


def main():
    parser = argparse.ArgumentParser(prog="brynz")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Process a capture into JSON and a rendered plan")
    run.add_argument("path", type=Path)
    run.add_argument("--out", type=Path, default=Path("out/capture"))
    run.add_argument("--stride", type=int, default=10)
    run.add_argument("--pixel-stride", type=int, default=3)
    run.add_argument("--no-drift-correction", action="store_true")
    run.add_argument("--estimator", choices=["baseline", "robust"], default="robust")
    run.add_argument("--start", type=int, default=0)
    run.add_argument("--stop", type=int)
    run.add_argument("--camera-convention", choices=["opencv", "legacy-arkit"], default="opencv")
    run.add_argument("--model-dir", type=Path, default=Path("models/metric-small"))
    run.add_argument("--live", action="store_true", help="Bypass depth cache")
    run.add_argument("--layout", choices=["partition", "rectangle"], default="partition")
    fetch = commands.add_parser("fetch-model", help="Download optional CPU metric depth weights")
    fetch.add_argument("--out", type=Path, default=Path("models/metric-small"))
    for command in ["benchmark", "derive", "fixloop", "ablation", "inventory", "report", "bundle"]:
        helper = commands.add_parser(command)
        helper.add_argument("path", type=Path)
        helper.add_argument("--out", type=Path, default=Path("out") / command)
    args = parser.parse_args()
    if args.command in {
        "benchmark",
        "derive",
        "fixloop",
        "ablation",
        "inventory",
        "report",
        "bundle",
    }:
        from brynz.benchmark import ablation, benchmark, bundle, derive_inputs, fixloop, inventory
        from brynz.output import render_report

        actions = {
            "benchmark": benchmark,
            "derive": derive_inputs,
            "fixloop": fixloop,
            "ablation": ablation,
            "inventory": inventory,
            "report": render_report,
            "bundle": bundle,
        }
        try:
            report = actions[args.command](args.path, args.out)
        except (ValueError, OSError) as error:
            print(f"brynz: {error}", file=sys.stderr)
            return 2
        print(json.dumps(report, indent=2, default=str))
        return 0
    if args.command == "fetch-model":
        from brynz.rgb import fetch_model

        print(fetch_model(args.out))
        return 0
    if args.stride < 1 or args.pixel_stride < 1:
        parser.error("Strides must be positive.")
    try:
        result = run_capture(
            args.path,
            args.out,
            args.stride,
            args.pixel_stride,
            not args.no_drift_correction,
            args.estimator,
            args.start,
            args.stop,
            args.camera_convention,
            args.model_dir,
            args.live,
            args.layout == "partition",
        )
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"brynz: {error}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(args.out / "result.json"),
                "rooms": len(result["rooms"]),
            },
            indent=2,
        )
    )
    return 0
