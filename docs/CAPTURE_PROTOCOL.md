# Stock Capture Protocol

**Route 2. Proposed protocol; not physically tested by the author.**

## Prepare

Use an iPhone 15 or newer; LiDAR needs a LiDAR-equipped Pro model. Turn on room
lighting, open connecting doors and leave furniture in place. Record phone/app
versions. Use harmless removable props for staged damage, never real mold or leaks.

## Photos: Built-In Camera

Use the main 1x lens, not panorama or portrait mode. Take 6-8 ordinary stills per
room from different positions around its perimeter, overlapping views by about
half. Show every wall, floor/ceiling junction and doorway. Include one level wide
shot showing floor and ceiling together. Step between views; do not only rotate.
Photograph connectors as separate rooms and shared doors from both sides. Transfer
original images into one named folder per room under a property folder.

## Video: Built-In Camera

Use 1080p, 30 fps, main 1x lens, upright landscape orientation. Walk slowly with
overlapping views, 30-60 seconds per room. Show floor/ceiling junctions, walk through
all doors/connectors, and revisit the start. Avoid quick pans and stationary spins.
Transfer the original unedited MP4/MOV, not a messaging-app recompressed copy.

## LiDAR: Stray Scanner

Install Stray Scanner: https://apps.apple.com/us/app/stray-scanner/id1557051662

Start a new recording. Walk at roughly 0.2-0.4 m/s, 0.5-3 m from walls. Sweep from
floor to ceiling, pause at doors for two seconds, cross connectors and observe doors
from both sides. Return to the start. Allow 30-60 seconds per room and keep the
property in one recording. Transfer the entire raw export, including `depth/`,
`confidence/`, `odometry.csv`, `camera_matrix.csv`, `rgb.mp4` and `imu.csv`.

## Transfer and Run

Preserve original files via USB, iCloud or Files export; extract archives first.
Capture mirrors/glass with surrounding opaque frames from oblique views. Keep good
lighting, avoid moving people, lens changes and rapid motion. Glossy surfaces and
reflections can still cause failures. After setup from the README, run:

```bash
uv run --locked --extra rgb brynz run captures/property --out out/property
```

For video, supply the clip path; for photos, supply the room-folder parent. Inspect
JSON warnings and the plan. Partial/unknown output is not a completed survey.