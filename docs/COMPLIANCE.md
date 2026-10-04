# Compliance Matrix

**Assessment-ready: no.** Files, a ZIP and passing unit tests do not establish
the brief's measurement or walk-in gates. The access limitation is disclosed in
[the README](../README.md#capture-access-and-missing-results), not treated as a waiver.

## Eight Deliverables

| Requirement | File | Artifact | Status |
| --- | --- | --- | --- |
| 1. Compliance matrix | This document; [JSON ledger](../compliance.json) | Requirement-to-file mapping | Present; numerous requirements unresolved |
| 2. Capture route and device matrix | [Protocol](CAPTURE_PROTOCOL.md), [devices](DEVICE_MATRIX.md) | Verified one-page PDF of proposed stock route | Documented; physical trial absent |
| 3. Repo and README; clean setup under 15 min; one command per capture | [README](../README.md), `uv.lock`, `brynz/cli.py` | Local code and three input commands | Present; setup timing unverified; RGB results incomplete |
| 4. Reproduction bundle | `brynz/benchmark.py` | `out/submission/brynz-submission.zip` | Source, Git, docs, samples and evidence included; weights fetched separately |
| 5. Benchmark report, all tiers, repeats, head-to-head, timing | [Benchmark report](BENCHMARK_REPORT.md), `evidence/benchmark.json` | Execution table and explicit missing-result tables | Partial; physical accuracy/repeats/comparison missing |
| 6. Fix-loop bundle | [Fix loop](FIX_LOOP.md), declarations, post-mortem, `evidence/fixloop*` | Before/after outputs and diffs; Git tags | Shipped/regenerable; failing metric did not improve |
| 7. Technical report, <=6 pages | [Technical report](TECHNICAL_REPORT.md) | `out/report/report.pdf` | Verified three-page PDF; includes architecture and limitations |
| 8. Raw benchmark data, GT and app exports | Sample folders in ZIP | Sensor logs and derived RGB only | Partial; required self-captures, GT and app exports absent |

## Product and Accuracy Gates

| Requirement | Owning file | Artifact | Status |
| --- | --- | --- | --- |
| Dimensioned room walls, ceiling and area | `brynz/geometry.py` | Result JSON and plan | Partial LiDAR rectangle; incomplete surfaces |
| Opening widths <=2 cm on >=85%, misses/phantoms scored | `brynz/openings.py` | Ray-supported candidates | No labelled GT; engineering bounds too wide to demonstrate gate |
| Ceiling <=1.5 cm; repeat spread <=1 cm | `brynz/geometry.py` | Candidate height in ceiling-inclusive sample | Unverified bias/spread |
| Same-tier independent wall repeatability | `brynz/benchmark.py` | Repeatability helper | No independent repeat captures |
| Whole-property plan with correct adjacency | `brynz/stitch.py` | Candidate partitions/relations | Not satisfied or validated on real multi-room property |
| Photo folders stitch without overlaps; footprint +/-8% | `brynz/rgb.py` | Joint SfM plus diagnostics | No photo footprint in tested inputs |
| Photo walls +/-8%; video +/-3% | `brynz/rgb.py` | Learned-scale frontend | No sample wall results; unverified |
| Calibrated confidence intervals | `brynz/geometry.py` | Labelled engineering bounds | Not satisfied; no physical calibration |
| Multi-room drift correction and footprint ablation | `brynz/geometry.py` | `evidence/ablation.json` | Local sample correction only; required multi-room validation absent |
| Surface damage classes and metric extent | `brynz/damage.py` | Opt-in candidate rectangles | Heuristic/unvalidated; RGB unsupported |
| Concealed flags with fired rule | `brynz/damage.py` | Review-only moisture flags | Partial; not evidence of concealed damage |
| Surface-keyed repair scope | `brynz/damage.py` | Inspection quantities | Not final repair line items |
| Published output schema | `brynz/output.schema.json` | Validated provisional local JSON | Published Round 1 schema not supplied |
| Rendered plan from every tier | `brynz/output.py` | PNG/SVG or unknown-state image | Renderer runs; unknown-state images do not satisfy plan recovery |
| Mirrors, glass, glossy surfaces and low light | Technical report and protocol | Failure-mode disclosure | Not empirically benchmarked |
| Cold unseen walk-in at any tier | `brynz/cli.py` | Live local routes | Not ready: RGB geometry and metric/topology gates unresolved |

## Benchmark Composition and Process

Three rooms plus connector at all tiers, two staged damage classes, matched tape/
laser measurements, independent repeats and two-room incumbent exports are absent.
Derived stills are not independent capture evidence. The free-app comparison remains
required; subscription access is not an accepted cost exception.

The local repo has real current-date commits and tags. The initial completed
prototype was divided into baseline commits after implementation; later edits were
committed as made. This does not establish the long development history the brief
asks reviewers to assess. `.git` is preserved in the ZIP; no process-score claim is made.

## Reproduction Notes

Use [the ordered README commands](../README.md#reproduce-the-submitted-evidence).
Generate both photo inputs before benchmarking. PDF page counts refer to the current
rendered files, not old report versions; packaging must happen after final commits.
JSON ledgers and committed evidence remain available for machine-readable inspection.