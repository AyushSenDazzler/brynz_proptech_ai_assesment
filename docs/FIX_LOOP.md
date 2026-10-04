# Fix Loop

## Declaration

[fix-declaration.json](../fix-declaration.json) was committed before the fallback
code, at tag `fix-before`. Its local diagnostic was **rooms with any dimension at
the photo tier: 0 of 1**. This is a completeness proxy, not the brief's full
whole-property stitch/accuracy gate.

**Hypothesis:** SfM failure discards otherwise usable single-image metric depth.
**Shipped fix:** back-project per-image learned depth with a focal-length prior;
report candidate ceiling height only if floor and ceiling planes are both supported
and sufficiently parallel. Footprint and adjacency remain unknown.

**Declared prediction:** 1 of 1 rooms measured if a still shows both floor and
ceiling; otherwise 0 of 1. This conditional forecast was not a firm accuracy
prediction. The success target was not achieved.

## Results

| Run | Evidence | Before | After | Observation |
| --- | --- | --- | --- | --- |
| Initial sensor-oriented stills | [Run 1](../evidence/fixloop-run1-sideways-stills/summary.json) | 0 of 1 | 0 of 1 | Sideways image orientation also affected the gravity assumption |
| Upright original-room stills | [Run 2](../evidence/fixloop/summary.json) | 0 of 1 | 0 of 1 | No supported floor/ceiling pair in one view |
| Upright ceiling-scan stills | [Run 3](../evidence/fixloop-ceiling/summary.json) | 0 of 1 | 0 of 1 | Same failure despite a candidate LiDAR ceiling in the continuous scan |

**The failing diagnostic did not improve.** Shipping code and an honest
post-mortem is not a successful gate delta or a promise of fix-loop credit.

## Post-Mortem

The root-cause hypothesis was incomplete. Per-view depth was being discarded, but
the derived close-range/tilted views did not supply a supported floor/ceiling pair
in any one frame. The fallback cannot recover unobserved surfaces or cross-view
scale. The proposed capture protocol now asks for a level wide view containing both
surfaces, but its effectiveness has not been physically tested.

See [fix-postmortem.json](../fix-postmortem.json). No thresholds were relaxed merely
to turn the diagnostic into a pass, and no physical accuracy result is claimed.

## Regenerate

```bash
uv run --locked --extra rgb brynz derive single_room --out out/derived
uv run --locked --extra rgb brynz derive single_scan_with_ceiling --out out/derived-ceiling
uv run --locked --extra rgb brynz fixloop out/derived/photos --out out/fixloop
uv run --locked --extra rgb brynz fixloop out/derived-ceiling/photos --out out/fixloop-ceiling
git diff fix-before fix-after
```

The fix-loop command holds the input fixed, toggling the fallback in the current
code. It is a same-code ablation, not an automatic checkout of historical commits.
Each run saves before/after JSON, rendered plans and `results.diff`. Git tags give
the historical declaration/code comparison. Current upright derivation differs
from the initial sensor-oriented sample; the first failed run is retained separately.

## Earlier Axis Correction

[fix-declaration-axis-retrospective.json](../fix-declaration-axis-retrospective.json)
describes a separate retrospective loader correction. Exported Stray poses already
use OpenCV camera coordinates; raw ARKit sign flips corrupt fusion. The isolated
rectangle fit recovers 0 walls before and 4 after. This is not a pre-declared measured
assessment gate.

```bash
uv run --locked --extra rgb brynz fixloop-axis single_room --out out/fixloop-axis
```

[Axis evidence](../evidence/fixloop-axis/summary.json) and
[fix-source.diff](../fix-source.diff) remain preserved. The old saved axis summary
names `fix-declaration.json`, its filename at that time; the renamed retrospective
declaration above is the correct current source.