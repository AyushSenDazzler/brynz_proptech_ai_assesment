# Architecture

## Processing Paths

| Stage | LiDAR | Photos and video | Owner |
| --- | --- | --- | --- |
| Routing | Direct or single nested Stray export | Clip extension or image folders | [cli.py](../brynz/cli.py) |
| Preparation | Confidence-filtered depth and per-frame intrinsics | EXIF-oriented photos; sampled video frames | [capture.py](../brynz/capture.py), [rgb.py](../brynz/rgb.py) |
| Coordinates | Exported OpenCV camera-to-world poses | CPU COLMAP SfM with bundle adjustment | [capture.py](../brynz/capture.py), [rgb.py](../brynz/rgb.py) |
| Metric scale | Depth in millimetres converted to metres | Learned indoor depth prior and median depth ratio | [rgb.py](../brynz/rgb.py) |
| Gravity | Logger world-Y assumption | Mean camera-up prior, not IMU gravity | [geometry.py](../brynz/geometry.py), [rgb.py](../brynz/rgb.py) |
| Drift | Bounded local fragment translation ICP | Bundle adjustment; no explicit global loop closure | [geometry.py](../brynz/geometry.py), [rgb.py](../brynz/rgb.py) |
| Room model | Default rectangular fit; opt-in floor watershed | Room clouds fitted in shared coordinates when supported | [geometry.py](../brynz/geometry.py), [stitch.py](../brynz/stitch.py) |
| Openings | Beyond-wall rays and occupancy gaps | Same candidate test if reconstruction succeeds | [openings.py](../brynz/openings.py) |
| Damage/scope | Opt-in RGB heuristics projected near fitted walls | Unsupported | [damage.py](../brynz/damage.py) |
| Failure fallback | Missing evidence stays null | Single-view ceiling height only if both planes supported | [rgb.py](../brynz/rgb.py) |
| Output | Validated local JSON, PNG/SVG, cloud, timing | Same contract; unknown-state plan on failure | [output.py](../brynz/output.py) |

These are separate input routes into shared geometric/output abstractions, not
three independently validated products. Multi-room placement, metric scale and
adjacency remain incomplete, especially for unposed photos.

## Evidence Boundaries

1. Raw capture files are preserved separately from generated results.
2. RGB processing never reads LiDAR depth or logger poses for geometry. The sample
   derivation utility uses poses only for upright image rotation; this is disclosed
   and is not independent native-camera capture.
3. Learned metric depth is a prior. Sparse RGB observations do not determine metric
   scale or hidden room adjacency uniquely.
4. Candidate measurements carry uncalibrated bounds; missing values are `null`.
5. Damage flags request review; concealed damage is not physically established.
6. The local schema is provisional, not the unavailable published Round 1 schema.

## Reproduction and Packaging

[benchmark.py](../brynz/benchmark.py) scores supplied ground truth, compares
independent same-tier outputs, derives test inputs, runs correction ablations and
packages artifacts. [uv.lock](../uv.lock) pins dependencies. Model weights are fetched
explicitly and loaded locally. Depth cache keys include image/model/configuration
hashes; `--live` bypasses cache reads. Byte-identical SfM JSON across machines is not
certified. The bundle preserves `.git`, docs and evidence, but excludes environments
and downloaded model weights.

The assessment asks for architecture within the technical report. This separate
file is a navigation aid, not a substitute for the report or validated algorithms.