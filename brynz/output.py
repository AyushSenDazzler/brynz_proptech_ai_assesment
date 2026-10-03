import json
from pathlib import Path

import jsonschema
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def render_report(path, out):
    import textwrap

    from matplotlib.backends.backend_pdf import PdfPages

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    lines = []
    for paragraph in Path(path).read_text(encoding="utf-8").splitlines():
        lines.extend(textwrap.wrap(paragraph, width=92) or [""])
    count = max(1, int(np.ceil(len(lines) / 58)))
    if count > 6:
        raise ValueError("Technical report exceeds the six-page limit.")
    target = out / "report.pdf"
    with PdfPages(target) as document:
        for page in range(count):
            figure = plt.figure(figsize=(8.27, 11.69))
            figure.text(
                0.06,
                0.94,
                "\n".join(lines[page * 58 : (page + 1) * 58]),
                va="top",
                family="monospace",
                fontsize=9,
                linespacing=1.25,
            )
            figure.text(0.5, 0.035, f"{page + 1} / {count}", ha="center", fontsize=9)
            document.savefig(figure)
            plt.close(figure)
    return {"output": str(target), "pages": count}


def validate(result):
    schema = json.loads((Path(__file__).parent / "output.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(result, schema)
    rooms = {room["id"] for room in result["rooms"]}
    surfaces = {wall["id"] for room in result["rooms"] for wall in room["walls"]}
    if len(rooms) != len(result["rooms"]):
        raise ValueError("Duplicate room identifiers.")
    for room in result["rooms"]:
        for opening in room["openings"]:
            if opening["surface_id"] not in surfaces:
                raise ValueError("Opening references an unknown wall.")
    for region in result["damage_regions"]:
        if region["surface_id"] not in surfaces:
            raise ValueError("Damage references an unknown surface.")
    for item in result["scope_items"] + result["concealed_flags"]:
        if item["surface_id"] not in surfaces:
            raise ValueError("Scope or flag references an unknown surface.")
    for relation in result["adjacency"]:
        if not all(identifier in rooms for identifier in relation["rooms"]):
            raise ValueError("Adjacency references an unknown room.")
    _validate_intervals(result)


def _validate_intervals(value):
    if isinstance(value, dict):
        if {"value", "interval", "unit", "status"}.issubset(value):
            if value["value"] is not None:
                interval = value["interval"]
                if interval is None or not interval[0] <= value["value"] <= interval[1]:
                    raise ValueError("Measurement is outside its reported interval.")
            elif value["interval"] is not None:
                raise ValueError("Unknown measurements must not have numeric intervals.")
        for child in value.values():
            _validate_intervals(child)
    elif isinstance(value, list):
        for child in value:
            _validate_intervals(child)


def render(result, out, cloud=None):
    figure, axes = plt.subplots(figsize=(10, 8))
    axes.set_aspect("equal")
    if cloud is not None and len(cloud):
        selected = cloud[:: max(1, len(cloud) // 30000)]
        axes.scatter(selected[:, 0], selected[:, 2], s=0.4, c="#b8c4c1", alpha=0.3)
    observed = False
    for room in result["rooms"]:
        polygon = np.asarray(room["polygon"])
        if not len(polygon):
            continue
        observed = True
        closed = np.vstack((polygon, polygon[0]))
        axes.fill(polygon[:, 0], polygon[:, 1], color="#d8ede5", alpha=0.35)
        axes.plot(closed[:, 0], closed[:, 1], color="#154b3a", linewidth=2)
        center = polygon.mean(axis=0)
        area = room["floor_area"]["value"]
        axes.text(*center, f"{room['name']}\n{area:.2f} m2", ha="center", va="center")
        for wall in room["walls"]:
            midpoint = (np.asarray(wall["start"]) + np.asarray(wall["end"])) / 2
            value = wall["length"]
            axes.annotate(
                f"{value['value']:.2f} m\n[{value['interval'][0]:.2f}, {value['interval'][1]:.2f}]",
                midpoint,
                xytext=(8, 8),
                textcoords="offset points",
                fontsize=8,
                backgroundcolor="white",
            )
    if not observed:
        axes.text(
            0.5,
            0.5,
            "Insufficient metric evidence\nNo room footprint inferred",
            transform=axes.transAxes,
            ha="center",
            va="center",
        )
    axes.set(
        xlabel="World X (m)",
        ylabel="World Z (m)",
        title=f"{result['tier'].upper()} | {result['status']} | intervals uncalibrated",
    )
    axes.grid(alpha=0.12)
    figure.tight_layout()
    figure.savefig(Path(out) / "plan.png", dpi=150)
    figure.savefig(Path(out) / "plan.svg")
    plt.close(figure)
