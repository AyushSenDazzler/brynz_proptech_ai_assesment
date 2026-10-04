# Device Matrix

## Intended Capture Hardware

| Tier | Intended hardware | Input | Observed result | Accuracy status |
| --- | --- | --- | --- | --- |
| Photos | iPhone 15+ including non-Pro | 2-8 unposed stills per room | Derived sample stills recover no dimension; fallback finds no qualifying view | Photo +/-8% wall and footprint gates unverified; no calibrated intervals |
| Video | iPhone 15+ including non-Pro | Original translated walkthrough | A subset of frames registers; no room dimensions in the tested clip | Video +/-3% gate unverified |
| LiDAR | LiDAR-equipped iPhone Pro/Pro Max | Stray depth, confidence, poses, intrinsics and RGB | Partial rectangular plans; ceiling-inclusive sample estimates 2.33231 m height | No physical GT; width/height bounds do not demonstrate centimetre gates |

Physical phone compatibility, installation time and protocol usability have not
been tested by the author. This is an intended-support matrix, not a certification.

## Compute

- Windows CPU, Python 3.12 and `uv` tested.
- Four threads configured for CPU SfM and metric-depth inference.
- Approximately 99 MB indoor metric-depth weights; GPU not required.
- Package/weight downloads occur during setup; inference loads local files.
- Clean-machine setup within 15 minutes and cross-platform behavior are unverified.

## Access Disclosure

The author has no iPhone. The Android scanning application tried was free to install
but required a subscription for the needed scanning/export workflow. App identity,
version and pricing evidence were not supplied; pricing is not independently verified. Android capture
compatibility is not claimed, and Android data does not satisfy an iPhone benchmark.
This explains the access limitation, not the algorithm's RGB failures or an exemption
from the brief's required captures and incumbent comparison.

Machine-readable counterpart: [device-matrix.json](../device-matrix.json).