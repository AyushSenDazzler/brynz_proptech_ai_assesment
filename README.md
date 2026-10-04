# Brynz

CPU-first room-capture reconstruction prototype using Python and `uv`.

> **Submission status: incomplete.** LiDAR samples produce partial geometry. The
> tested photo and video samples produce no usable dimensions, including after the
> single-view fallback. Physical accuracy, calibrated intervals, and whole-property
> stitching have not been demonstrated. Successful execution is not a passing gate.

## Capture Access and Missing Results

The author does not have access to an iPhone. The Android scanning application the
author tried was available to install for free, but the scanning/export workflow
needed required a paid subscription. Its name/version and pricing evidence were not
supplied, and pricing was not independently verified; this is the author's experience, not a claim
about all Android scanning applications.

Consequently, the submission uses available sample sensor logs and derived RGB
inputs, not a self-captured iPhone benchmark. There are no matched laser/tape ground
truth, independent repeat captures, staged-damage measurements, or incumbent app
exports. Missing results are marked **unscored**, never zero error or passed.

**This does not waive the brief's mandatory captures or its free-tier incumbent
comparison.** It also does not explain away the implemented photo/video failures.
An evaluator with compatible captures can exercise every input route below, but
this prototype cannot promise a complete plan from any route.

## Requirements

- Windows CPU environment tested; Python 3.12 recommended.
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Internet for package and model downloads; inference runs locally afterward.
- Optional RGB dependencies include CPU PyTorch, COLMAP and HEIC support.
- Indoor metric-depth weights are approximately 99 MB; dependencies and raw data
  require additional disk space. GPU hardware is not required.

Setup on a clean machine in under 15 minutes is **not verified**. Network speed,
available memory and CPU performance affect setup and runtime.

## Install

Run from the extracted repository root. These commands work in PowerShell or Bash:

```bash
uv sync --locked --python 3.12 --extra rgb
uv run --locked --extra rgb brynz fetch-model
uv run --locked --extra rgb brynz --help
```

For LiDAR only, use `uv sync --locked --python 3.12`; model weights are unnecessary.
After setup, local weights are loaded with `local_files_only=True`. No inference
request is sent to the author's infrastructure.

## Test a Fresh Capture

Follow [the stock capture protocol](docs/CAPTURE_PROTOCOL.md). Inputs do not need
known dimensions or benchmark annotations to run. Ground truth is needed to score
their accuracy, not to generate outputs.

### LiDAR

Export a Stray Scanner recording and preserve its directory contents:

```text
captures/property-lidar/
  odometry.csv
  camera_matrix.csv
  rgb.mp4
  depth/000000.png ...
  confidence/000000.png ...
  imu.csv
```

```bash
uv run --locked --extra rgb brynz run captures/property-lidar --out out/fresh-lidar
```

One nested logger-export folder is accepted automatically. Poses, per-frame
intrinsics and millimetre depth are required for the normal path. The loader does
not accept generic OBJ/PLY meshes, app floor-plan exports or ZIP archives.

The default is a single rectangular candidate per capture. Experimental room
partitioning requires `--layout partition`; heuristic damage screening requires
`--damage`. Neither option establishes verified topology or damage accuracy.

### Video

Supply the original unedited walkthrough file, with no depth/pose sidecars:

```bash
uv run --locked --extra rgb brynz run captures/walkthrough.mp4 --out out/fresh-video --live
```

MP4, MOV and M4V are routed as video; decoding depends on the installed OpenCV
codec support. The walkthrough should have translated, overlapping views and
upright orientation. The pipeline samples at most 64 frames at a 960-pixel maximum
side. `--live` bypasses metric-depth cache reads, but does not guarantee successful
SfM or floor-plan recovery. The single-view fallback may also remain unobserved.

### Photos

Put 2-8 unposed stills in each room folder, including the connector:

```text
captures/property-photos/
  kitchen/01.jpg ...
  bedroom/01.jpg ...
  lounge/01.jpg ...
  hallway/01.jpg ...
```

```bash
uv run --locked --extra rgb brynz run captures/property-photos --out out/fresh-photos --live
```

JPG, PNG, HEIC and HEIF are supported; HEIC/HEIF require the RGB extra. EXIF
orientation is applied. All folders enter a joint SfM solve; room names are not
adjacency hints. More than eight images per folder are currently truncated.
Disconnected or failed rooms remain unknown rather than being placed arbitrarily.
The fallback reports only a candidate ceiling height when one view supports both
floor and ceiling; it does not fabricate walls, area or room adjacency.

### Inspect Results

Every accepted capture produces `result.json`, `plan.png`, `plan.svg` and
`timing.json`. A point cloud is saved as `cloud.npz` when available. RGB processing
also saves prepared images, SfM artifacts and local depth predictions.

```bash
uv run --locked --extra rgb python -c "import json; from pathlib import Path; p=Path('out/fresh-photos/result.json'); r=json.loads(p.read_text()); print(r['tier'], r['status']); print([(x['id'], len(x['walls']), x['floor_area']['value'], x['ceiling_height']['value']) for x in r['rooms']]); print(r['warnings'])"
```

Change the output path above to inspect LiDAR or video. Exit code 0 means the
processing command completed; `partial` or `insufficient_evidence` is not an
accuracy or completeness pass. A JSON file and an unknown-state image are not a
usable floor plan. Unknown measurements are `null`, and numerical intervals are
explicitly **uncalibrated engineering bounds**.

## Reproduce the Submitted Evidence

Raw samples are distributed in the ZIP, not tracked in Git. Fetch weights first,
then derive **both** photo inputs before running the benchmark:

```bash
uv run --locked --extra rgb brynz derive single_room --out out/derived
uv run --locked --extra rgb brynz derive single_scan_with_ceiling --out out/derived-ceiling
uv run --locked --extra rgb brynz benchmark benchmark-manifest.json --out out/benchmark
uv run --locked --extra rgb brynz fixloop out/derived/photos --out out/fixloop
uv run --locked --extra rgb brynz fixloop out/derived-ceiling/photos --out out/fixloop-ceiling
uv run --locked --extra rgb brynz fixloop-axis single_room --out out/fixloop-axis
uv run --locked --extra rgb brynz ablation single_room --out out/ablation
uv run --locked --extra rgb brynz inventory single_room --out out/inventory/single-room
```

Original submitted summaries are committed under `evidence/`; new runs go under
`out/`. Timings and software/hardware-sensitive numerical details can differ.
Derived stills are not independent iPhone photo captures: logger poses are used
only to rotate those test stills upright, not passed to RGB reconstruction.

See [the benchmark report](docs/BENCHMARK_REPORT.md) for measured execution results
and [the fix-loop account](docs/FIX_LOOP.md) for the unchanged failing metric.

## Score New Measurements

Create a JSON manifest beside the referenced captures and ground-truth files:

```json
{
  "captures": [
    {"id": "lidar-a", "path": "property-lidar", "ground_truth": "truth.json"},
    {"id": "video-a", "path": "walkthrough.mp4", "ground_truth": "truth.json"},
    {"id": "photos-a", "path": "property-photos", "ground_truth": "truth.json"}
  ],
  "repeat_pairs": [],
  "missing_requirements": []
}
```

Example ground-truth structure; **these numbers are illustrative, not supplied
sample measurements**:

```json
{
  "measurements": {
    "room-1:wall-1": {"value": 4.12, "kind": "wall"},
    "room-1:ceiling_height": {"value": 2.62, "kind": "ceiling_height"},
    "room-1:wall-1:opening-1": {"value": 0.89, "kind": "opening"}
  }
}
```

```bash
uv run --locked --extra rgb brynz benchmark captures/manifest.json --out out/measured-benchmark
```

Manifest paths are relative to the manifest. Associate prediction IDs with physical
surfaces before scoring; there is no automatic GT identity matching. Add
`repeat_pairs` only for independently recorded same-tier scans, not reruns of a file.
The current scorer does not establish all assessment gates or automatically certify
readiness. The incumbent-comparison helper requires an app export manually
normalized to the local result structure; no export adapter or head-to-head CLI
is supplied. See [benchmark limitations](docs/BENCHMARK_REPORT.md).

## Documents and Deliverables

| Document | Purpose |
| --- | --- |
| [Capture protocol](docs/CAPTURE_PROTOCOL.md) | Proposed stock-app capture route |
| [Device matrix](docs/DEVICE_MATRIX.md) | Intended hardware and observed limitations |
| [Compliance matrix](docs/COMPLIANCE.md) | All eight deliverables and requirement statuses |
| [Benchmark report](docs/BENCHMARK_REPORT.md) | Timings, gates, repeatability and comparison gaps |
| [Fix loop](docs/FIX_LOOP.md) | Declaration, shipped change, evidence and post-mortem |
| [Technical report](docs/TECHNICAL_REPORT.md) | Architecture, error budget and failure modes |
| [Architecture](docs/ARCHITECTURE.md) | Implementation map and input/output boundaries |

`compliance.json`, `device-matrix.json`, declarations, post-mortem and `evidence/`
remain machine-readable source evidence, not unnecessary duplicates.

## Validate and Package

```bash
uv run --locked --extra rgb pytest -q
uv run --locked --extra rgb ruff check brynz tests
uv run --locked --extra rgb brynz report docs/TECHNICAL_REPORT.md --out out/report
uv run --locked --extra rgb brynz report docs/CAPTURE_PROTOCOL.md --out out/protocol
uv run --locked --extra rgb brynz bundle . --out out/submission
```

The technical PDF must stay within six pages and the capture protocol within one
page. The package includes source, docs, `.git`, raw samples and generated evidence;
it excludes `.venv` and model weights. Larger captures and historical outputs can
make the ZIP large. Avoid running the bundler during Git operations or capture runs.

After extraction on another computer:

```bash
git log --oneline
git remote add origin <repository-url>
git push -u origin main
git push origin --tags
```

If `origin` already exists, inspect it with `git remote -v` and use
`git remote set-url origin <repository-url>` if appropriate. Identity is configured
locally as `ayushkumar1959@gmail.com`; authentication to the remote is separate.
The initial completed prototype was organized into baseline commits afterward;
later declaration/fix commits were made in order. Commit count is not proof of a
long development history, and no assessment process-evidence pass is claimed.