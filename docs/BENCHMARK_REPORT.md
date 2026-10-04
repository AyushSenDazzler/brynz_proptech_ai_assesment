# Benchmark Report

## Summary

**No physical accuracy gate is verified.** The committed benchmark is execution
evidence from sample logs and derived RGB inputs, not the required self-captured
multi-room benchmark. There is no matched laser/tape ground truth.

## Submitted Runs

Source: [evidence/benchmark.json](../evidence/benchmark.json). Times below describe
the stored run, not a runtime guarantee; caching and hardware affect new runs.

| Capture | Tier | Output status | Seconds | Accuracy |
| --- | --- | --- | ---: | --- |
| Original room | LiDAR | Partial rectangular geometry | 6.355 | Unscored |
| Floor-only scan | LiDAR | Insufficient evidence | 16.996 | Unscored |
| Original room clip | Video | Insufficient evidence | 241.289 | Unscored |
| Original room derived stills | Photos | Insufficient evidence | 23.750 | Unscored |
| Ceiling-inclusive scan | LiDAR | Partial rectangular geometry | 32.928 | Unscored |
| Ceiling-scan derived stills | Photos | Insufficient evidence | 24.596 | Unscored |

The ceiling-inclusive LiDAR sample estimates **2.33231 m**, with uncalibrated bounds
**[2.23666, 2.42795] m**. There is no measured reference to establish bias or accuracy.
Both tested RGB paths produce no usable dimensions, even with the fallback.

## Required Gates

| Gate | Available evidence | Status |
| --- | --- | --- |
| Openings: <=2 cm on >=85%, including missed/phantom detections | Candidate ray-supported openings; no labelled GT | Unverified; bounds are wider than the target |
| Ceiling: <=1.5 cm per room; repeat spread <=1 cm | One candidate ceiling height; no physical reference or independent repeat | Unverified |
| Wall repeatability: 1 cm or 0.5% per wall | Same-file deterministic replay is not an independent capture | Unscored |
| Multi-room drift ablation | Local correction on/off for a sample, not a measured multi-room property | Partial diagnostic only |
| Photo property stitch: correct adjacency, no overlaps, footprint +/-8% | No reconstructed photo footprint | Not satisfied |
| Photo walls +/-8%; video walls +/-3% | No sample RGB wall results | Not satisfied |
| Calibrated intervals at all tiers | Engineering bounds only | Not satisfied |

### Repeatability Table

| Same room, same tier | Capture A | Capture B | Wall spread | Height spread | Verdict |
| --- | --- | --- | --- | --- | --- |
| No independent pair available | Not supplied | Not supplied | Not computed | Not computed | Unscored |

Repeated processing of one file tests software determinism, not the brief's
capture-repeatability requirement. Repeatable-but-biased versus unrepeatable cannot
be diagnosed without independent scans and measured ground truth.

### Incumbent Head-to-Head Table

| Required rooms | App/version/export | Our error | Their error | Beat/tie fraction |
| --- | --- | --- | --- | --- |
| Two measured benchmark rooms | Not supplied | Unscored | Unscored | Not computed |

No app/version, export or measured comparison exists. The free-tier comparison
remains mandatory; cost is not an accepted exception in the brief.

### Drift Diagnostic

Source: [evidence/ablation.json](../evidence/ablation.json).

| Local translation correction | Original-room footprint |
| --- | ---: |
| On | 20.86431 m2 |
| Off | 20.74179 m2 |

A changed footprint does not prove improved accuracy. There is no GT footprint or
multi-room property against which to score this correction. It is translation-only
local ICP, not a global pose-graph solution.

## Scorer Limitations

- GT associations use exact measurement IDs; opening/room identity matching is not
  automatic. Candidate component IDs need physical association before scoring.
- Opening misses and phantom IDs are penalized in the local score; association errors
  can still make that score misleading.
- The local LiDAR wall tolerance is a 2% diagnostic because Round 1's wall gate was
  not supplied. It is not a published assessment threshold.
- Interval coverage is descriptive; it is not held-out confidence calibration.
- The harness does not fully score adjacency, overlaps, footprint error, damage,
  calibrated coverage or all ceiling/repeatability requirements.
- `assessment_ready` remains false; supplying a manifest does not automatically
  certify this implementation.

## Missing Benchmark Composition

Three rooms plus connector at every tier, two staged damage classes, independent
same-tier repeats, physical measurements and incumbent exports are missing.
The author lacks an iPhone and encountered a subscription-gated Android export
workflow; [the access disclosure](../README.md#capture-access-and-missing-results)
explains why self-captured device evidence is unavailable. This is not a waiver or
the cause of the software's RGB reconstruction failures.

## Reproduce or Add New Data

Use [the README's three input routes](../README.md#test-a-fresh-capture). Generate
both derived photo sets before the bundled manifest. To score fresh captures,
provide matched measured GT using [the manifest instructions](../README.md#score-new-measurements).
Preserve the original submitted evidence; new output belongs under `out/`.