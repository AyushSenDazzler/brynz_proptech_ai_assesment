# Brynz Technical Report

**Prototype, not assessment-ready.** Detailed navigation: README, architecture,
benchmark and compliance documents. All accuracy claims below are unverified.

## 1. Architecture and Tier Design

Python 3.12 and `uv.lock`; CPU only. Stray depth, per-frame intrinsics and exported
OpenCV poses feed a point-cloud backend. Photos/video use CPU COLMAP SIFT, exhaustive
matching, bundle adjustment and Depth Anything V2 Metric Indoor Small (approximately
24.8M parameters / 99 MB). Video preparation is capped at 64 frames and 960 pixels
on the long side; photos at eight per folder. There is no remote inference.

Learned metric depth and a median sparse/depth ratio set RGB scale; this is not
physically measured scale. Mean camera-up is a gravity prior, not IMU gravity.
Photo folders enter a joint SfM solve. Disconnected/failed observations remain
unknown, not arbitrarily stitched. A single-view fallback reports only ceiling
height when a photo supports both planes; it produces no walls or adjacency.

Architecture ownership: `capture.py`/`rgb.py` ingest, `geometry.py` estimates,
`stitch.py` proposes topology, `openings.py` tests rays, `damage.py` proposes review
regions, `output.py` validates/renders, `benchmark.py` reproduces/scores/packages.

## 2. Geometry, Drift and Output

Depth millimetres become metres. Confidence below 2 and ranges outside 0.2-5 m are
discarded. Default sampling uses every tenth frame and every third pixel; 2.5 cm
voxelization and deterministic RANSAC bound fitting work. Supported wall-axis peaks
form a candidate Manhattan rectangle. Floor and ceiling must both have plane
support to report height. Alcoves/irregular walls are not reliably represented.

Rectangle is the default. `--layout partition` enables observed-floor watershed
room candidates only with enclosing-wall support. Raster boundaries are not
precision walls; adjacency and non-overlap are unvalidated on real properties.

Drift correction uses 15-sampled-frame fragments, nearest neighbours and robust
translations bounded to 15 cm. It is local translation-only ICP, not global loop
closure. The same offsets apply to clouds and camera origins. Sample footprint:
20.86431 m2 on, 20.74179 m2 off. No GT establishes which result is more accurate;
this is not the required measured multi-room ablation.

Openings require beyond-wall rays with low occupancy at the crossing. Gaps alone
are insufficient. Candidate extent has an >=8 cm bound; this does not demonstrate
the <=2 cm detection/width gate. Mirrors can create false beyond-wall evidence.

Schema-validated JSON, PNG/SVG plans, clouds and timing are emitted. The schema is
local/provisional: published Round 1 schema unavailable. Null values are unobserved,
not zero. Exit code 0 or an unknown-state plan is not a completed property survey.

## 3. Damage, Concealed Rules and Scope

Damage is off by default; `--damage` enables LiDAR-only HSV discoloration and dark
line candidates on ten frames. It is not semantic damage recognition. A prior run
flagged 14 candidates on a room with no known staged damage. Furniture, wood,
patterns and shadows can trigger it. Depth projects regions near fitted walls;
metric extent is a bounding rectangle, not verified damaged area. Sync and
deduplication are approximate. RGB-only damage projection is unsupported.

All regions require review. Concealed-moisture flags retain the fired rule and
do not prove a hidden leak. Scope requests inspection with surface-linked area
quantities; final repair line items and validated damage classes are incomplete.

## 4. Error Budget and Calibration

LiDAR rectangular walls carry >=4 cm / approximately 2% engineering bounds;
watershed/raster bounds are larger. Height bounds are >=3 cm plus plane residuals.
Device bias, tracking drift, occlusion, intrinsics, furniture and layout assumptions
are not fully propagated. Logged lens distortion is not corrected.

RGB bounds include >=12% video / >=25% photos plus scale dispersion; single-view
height uses at least 25% bounds. These are uncalibrated engineering intervals, not
95% confidence intervals. Learned depth, assumed focal length and gravity can be
wrong together. Held-out physical calibration is missing; descriptive interval
coverage and LiDAR pseudo-reference comparisons cannot establish it.

## 5. Benchmark and Fix Loop

Samples: `single_room`, nested floor-only and ceiling-inclusive scans. RGB inputs
are video/derived stills, not independent native-camera captures. Poses rotate test
stills upright only; RGB reconstruction receives no logger depth or poses.

Committed execution times: LiDAR 6.355 / 16.996 / 32.928 seconds; video 241.289;
photos 23.750 / 24.596. Hardware/caching affect new runs. Both RGB paths produce no
dimension. The ceiling-inclusive LiDAR sample gives 2.33231 m with uncalibrated
[2.23666, 2.42795] m bounds. All physical accuracy rows are unscored.

Required three-room benchmark, staged damage, independent repeats, laser/tape GT
and incumbent exports are absent. Repeatability helper checks independent same-tier
measurements; same-file deterministic reruns are not capture repeatability.

Fallback declaration preceded code at `fix-before`; shipped code is `fix-after`.
Diagnostic: photo rooms with any dimension, 0 of 1. Conditional prediction: 1 of 1
if a still shows both planes, otherwise 0. All three runs stayed 0 -> 0. The target
failed. Post-mortem: discarded depth was only part of the issue; cross-view scale,
gravity and a supported plane pair are missing. This is not a full property-stitch
gate or successful accuracy delta. Reproducible before/after JSON, plans and diffs
are retained. A separate retrospective camera-axis correction recovers 0 -> 4 walls.

## 6. Devices, Access, Failures and Reproduction

Intended: iPhone 15+ photos/video; LiDAR-equipped Pro models for Stray logs. Physical
phone support, protocol usability and <15-minute clean setup are unverified.
The author has no iPhone. The Android app tried was free to install but required a
subscription for the needed scanning/export workflow; app/version/pricing evidence
were not supplied and pricing is not independently verified. Sample logs replace self-captures.
This explains unavailable device evidence, not software failures or an exemption
from required free-tier incumbent comparison, GT or benchmark composition.

Poor overlap, pure rotation, repeated textures and narrow views fail SfM. Sparse
photos do not determine hidden topology or metric scale uniquely. Mirrors/glass,
gloss, low light and furniture can corrupt depth, planes and openings. Confidence
filtering is insufficient. Watershed can split furniture or merge wide doorways.
Damage heuristics require review. No +/-8% photo or +/-3% video claim is supported.

Weights are fetched explicitly, loaded locally and depth predictions cached by
image/model/config hashes. `--live` bypasses reads. Cross-machine bit-identical SfM
JSON is uncertified; local deterministic LiDAR reruns were tested. Source, `.git`,
docs, evidence, raw samples and `uv.lock` are bundled; environments/weights excluded.
Initial completed work was organized into baseline commits afterward; subsequent
declaration/fix commits were ordered. Commit quantity is not a long process history.

Model: `depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf`, fine-tuned on
Hypersim. Model card and redistribution terms should be checked before sharing
weights. Upstream Small architecture: Apache-2.0; COLMAP: BSD; Stray source: MIT.
Supplied capture provenance/licensing is unknown; no capture ownership is claimed.