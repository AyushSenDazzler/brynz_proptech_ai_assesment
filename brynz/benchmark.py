import difflib
import hashlib
import json
from pathlib import Path

from brynz.output import write_json


def dimensions(result):
    found = {}
    for room in result["rooms"]:
        for key in ("ceiling_height", "floor_area"):
            found[f"{room['id']}:{key}"] = room[key]
        for wall in room["walls"]:
            found[wall["id"]] = wall["length"]
        for opening in room["openings"]:
            found[opening["id"]] = opening["width"]
    return found


def score(result, ground_truth):
    predicted = dimensions(result)
    truth = ground_truth.get("measurements", {})
    records = []
    for identifier, reference in truth.items():
        reference = reference if isinstance(reference, dict) else {"value": reference}
        expected = float(reference["value"])
        kind = reference.get("kind", "wall")
        estimate = predicted.get(identifier)
        observed = estimate is not None and estimate["value"] is not None
        tolerance = 0.015 if kind == "ceiling_height" else 0.02 if kind == "opening" else None
        if tolerance is None:
            tolerance = expected * (
                0.08 if result["tier"] == "photos" else 0.03 if result["tier"] == "video" else 0.02
            )
        error = abs(estimate["value"] - expected) if observed else None
        interval = estimate["interval"] if observed else None
        records.append(
            {
                "id": identifier,
                "kind": kind,
                "reference": expected,
                "estimate": estimate["value"] if observed else None,
                "absolute_error": error,
                "tolerance": tolerance,
                "within_tolerance": observed and error <= tolerance,
                "interval_contains_reference": bool(
                    interval and interval[0] <= expected <= interval[1]
                ),
            }
        )
    predicted_openings = {item["id"] for room in result["rooms"] for item in room["openings"]}
    true_openings = {item["id"] for item in records if item["kind"] == "opening"}
    phantom = sorted(predicted_openings - true_openings)
    opening_rows = [item for item in records if item["kind"] == "opening"]
    denominator = len(opening_rows) + len(phantom)
    opening_rate = (
        sum(item["within_tolerance"] for item in opening_rows) / denominator
        if denominator
        else None
    )
    coverage = (
        sum(item["interval_contains_reference"] for item in records) / len(records)
        if records
        else None
    )
    return {
        "measurements": records,
        "phantom_openings": phantom,
        "opening_success_rate": opening_rate,
        "opening_gate": "unscored"
        if opening_rate is None
        else "pass"
        if opening_rate >= 0.85
        else "fail",
        "interval_coverage": coverage,
        "calibration_status": "not established",
        "note": "LiDAR wall tolerance is a local 2% diagnostic; Round 1 gate was not supplied.",
    }


def repeatability(first, second, independent=False):
    if first["tier"] != second["tier"]:
        raise ValueError("Repeatability requires two captures at the same tier.")
    before, after = dimensions(first), dimensions(second)
    records = []
    for identifier in sorted(set(before) | set(after)):
        if identifier.endswith("floor_area"):
            continue
        left, right = before.get(identifier), after.get(identifier)
        observed = left and right and left["value"] is not None and right["value"] is not None
        delta = abs(left["value"] - right["value"]) if observed else None
        tolerance = (
            0.01
            if identifier.endswith("ceiling_height")
            else max(0.01, left["value"] * 0.005)
            if observed
            else None
        )
        records.append(
            {
                "id": identifier,
                "difference": delta,
                "tolerance": tolerance,
                "within_tolerance": bool(observed and delta <= tolerance),
            }
        )
    return {
        "independent_captures": independent,
        "measurements": records,
        "gate": "unscored"
        if not independent or not records
        else "pass"
        if all(item["within_tolerance"] for item in records)
        else "fail",
        "note": "Subsampling or partitioning one scan is not an independent repeat capture.",
    }


def head_to_head(ours, theirs, ground_truth):
    own_rows = {item["id"]: item for item in score(ours, ground_truth)["measurements"]}
    other_rows = {item["id"]: item for item in score(theirs, ground_truth)["measurements"]}
    rows = []
    for identifier in sorted(set(own_rows) & set(other_rows)):
        own_error, their_error = (
            own_rows[identifier]["absolute_error"],
            other_rows[identifier]["absolute_error"],
        )
        if own_error is not None and their_error is not None:
            rows.append(
                {
                    "id": identifier,
                    "ours_error": own_error,
                    "incumbent_error": their_error,
                    "beat_or_tie": own_error <= their_error,
                }
            )
    fraction = sum(item["beat_or_tie"] for item in rows) / len(rows) if rows else None
    return {
        "dimensions": rows,
        "beat_or_tie_fraction": fraction,
        "gate": "unscored" if fraction is None else "pass" if fraction >= 0.7 else "fail",
    }


def benchmark(manifest_path, out):
    from brynz.cli import run_capture

    manifest_path, out = Path(manifest_path).resolve(), Path(out)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows, results = [], {}
    for capture in manifest["captures"]:
        identifier = capture["id"]
        path = (manifest_path.parent / capture["path"]).resolve()
        result = run_capture(path, out / identifier)
        results[identifier] = result
        row = {
            "id": identifier,
            "tier": result["tier"],
            "status": result["status"],
            "timing": json.loads((out / identifier / "timing.json").read_text()),
            "accuracy": {"status": "unscored", "reason": "No independent ground truth supplied."},
        }
        if capture.get("ground_truth"):
            truth = json.loads((manifest_path.parent / capture["ground_truth"]).read_text())
            row["accuracy"] = score(result, truth)
        rows.append(row)
    repeats = [
        repeatability(results[pair[0]], results[pair[1]], independent=True)
        for pair in manifest.get("repeat_pairs", [])
    ]
    report = {
        "captures": rows,
        "repeatability": repeats,
        "missing_requirements": manifest.get("missing_requirements", []),
        "assessment_ready": False,
    }
    write_json(out / "benchmark.json", report)
    return report


def _upright_from_poses(odometry_path):
    import csv

    import cv2
    import numpy as np
    from scipy.spatial.transform import Rotation

    with Path(odometry_path).open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream, skipinitialspace=True))

    def orient(frame, image):
        row = rows[min(frame, len(rows) - 1)]
        rotation = Rotation.from_quat([float(row[key]) for key in ("qx", "qy", "qz", "qw")])
        down = rotation.as_matrix().T @ np.array([0.0, -1.0, 0.0])
        if abs(down[0]) > abs(down[1]):
            return cv2.rotate(
                image, cv2.ROTATE_90_CLOCKWISE if down[0] > 0 else cv2.ROTATE_90_COUNTERCLOCKWISE
            )
        return image if down[1] > 0 else cv2.rotate(image, cv2.ROTATE_180)

    return orient


def derive_inputs(path, out):
    from brynz.rgb import sample_video

    path, out = Path(path), Path(out)
    nested = list(path.glob("*/odometry.csv")) if path.is_dir() else []
    if path.is_dir() and not (path / "odometry.csv").exists() and len(nested) == 1:
        path = nested[0].parent
    source = path / "rgb.mp4" if path.is_dir() else path
    odometry = path / "odometry.csv"
    orient = _upright_from_poses(odometry) if odometry.exists() else None
    names = sample_video(source, out / "photos" / "room-1", count=8, orient=orient)
    write_json(
        out / "derivation.json",
        {
            "source": str(source.resolve()),
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "photos": names,
            "video": str(source.resolve()),
            "orientation": "Stills rotated upright by 90-degree steps from logged gravity, as an iPhone "
            "EXIF orientation tag would; no depth or pose reaches the pipeline."
            if orient
            else "none",
            "note": "Derived samples, not independent iPhone photo captures.",
        },
    )
    return out / "photos"


def fixloop_axis(path, out):
    from brynz.cli import run_capture

    out = Path(out)
    before = run_capture(
        path, out / "before", drift=False, convention="legacy-arkit", partition=False
    )
    after = run_capture(path, out / "after", drift=False, convention="opencv", partition=False)
    before_text, after_text = (
        json.dumps(before, indent=2).splitlines(),
        json.dumps(after, indent=2).splitlines(),
    )
    diff = "\n".join(
        difflib.unified_diff(
            before_text, after_text, fromfile="before/result.json", tofile="after/result.json"
        )
    )
    (out / "results.diff").write_text(diff + "\n", encoding="utf-8")
    summary = {
        "before": {
            "walls": sum(len(room["walls"]) for room in before["rooms"]),
            "status": before["status"],
        },
        "after": {
            "walls": sum(len(room["walls"]) for room in after["rooms"]),
            "status": after["status"],
        },
        "root_cause": "Stray export uses OpenCV camera axes; raw ARKit sign flips corrupt fusion.",
        "assessment_gate_delta": "unscored: no physical ground truth or prior scored gate available",
        "reproduction": "Same code, data, sampling, rectangle layout, and disabled drift; only camera convention changes.",
        "declaration": "fix-declaration-axis-retrospective.json",
        "prediction": "4 enclosing walls after correction, 0 before",
    }
    write_json(out / "summary.json", summary)
    return summary


def _measured_rooms(result):
    return sum(
        1
        for room in result["rooms"]
        if room["polygon"] or room["ceiling_height"]["value"] is not None
    )


def fixloop(path, out):
    from brynz.cli import run_capture

    out = Path(out)
    before = run_capture(path, out / "before", fallback=False)
    after = run_capture(path, out / "after", fallback=True)
    diff = "\n".join(
        difflib.unified_diff(
            json.dumps(before, indent=2).splitlines(),
            json.dumps(after, indent=2).splitlines(),
            fromfile="before/result.json",
            tofile="after/result.json",
        )
    )
    (out / "results.diff").write_text(diff + "\n", encoding="utf-8")
    total = len(after["rooms"])
    summary = {
        "gate": "Photo-tier any picture in, results out",
        "metric": "rooms with at least one non-null dimension",
        "before": f"{_measured_rooms(before)} of {len(before['rooms'])}",
        "after": f"{_measured_rooms(after)} of {total}",
        "after_ceiling_heights": {room["id"]: room["ceiling_height"] for room in after["rooms"]},
        "footprint_recovered_after": any(room["polygon"] for room in after["rooms"]),
        "accuracy": "unscored: no physical ground truth",
        "declaration": "fix-declaration.json",
    }
    write_json(out / "summary.json", summary)
    return summary


def ablation(path, out):
    from brynz.cli import run_capture

    out = Path(out)
    corrected = run_capture(path, out / "on", drift=True)
    raw = run_capture(path, out / "off", drift=False)
    report = {
        "on": dimensions(corrected),
        "off": dimensions(raw),
        "drift": corrected["drift"],
        "accuracy_delta": "unscored: no ground truth",
    }
    write_json(out / "ablation.json", report)
    return report


def inventory(path, out):
    path, out = Path(path).resolve(), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        if out.resolve() == file.parent or out.resolve() in file.parents:
            continue
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
        records.append(
            {
                "path": file.relative_to(path).as_posix(),
                "bytes": file.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
    report = {
        "root": str(path),
        "files": records,
        "total_bytes": sum(item["bytes"] for item in records),
    }
    write_json(out / "inventory.json", report)
    return {
        "output": str(out / "inventory.json"),
        "files": len(records),
        "bytes": report["total_bytes"],
    }


def bundle(path, out):
    from zipfile import ZIP_DEFLATED, ZipFile

    path, out = Path(path).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    directories = [path / "brynz", path / "tests", path / "docs", path / "evidence", path / ".git"]
    directories.extend(
        item
        for item in path.iterdir()
        if item.is_dir() and (item.name == "single_room" or item.name.startswith("single_scan_"))
    )
    if (path / "out").is_dir():
        directories.extend(item for item in (path / "out").iterdir() if item.is_dir())
    files = [item for item in path.iterdir() if item.is_file()]
    for directory in directories:
        if directory.exists():
            files.extend(
                file
                for file in directory.rglob("*")
                if file.is_file() and "__pycache__" not in file.parts and out not in file.parents
            )
    target = out / "brynz-submission.zip"
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=3) as archive:
        for file in sorted(set(files)):
            archive.write(file, file.relative_to(path).as_posix())
    return {
        "output": str(target),
        "files": len(set(files)),
        "bytes": target.stat().st_size,
        "contains_git_history": any(file.is_relative_to(path / ".git") for file in files),
        "weights": "Fetch locally with uv run --extra rgb brynz fetch-model",
        "assessment_ready": False,
    }
