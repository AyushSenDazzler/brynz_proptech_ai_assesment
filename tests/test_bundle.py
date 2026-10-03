from zipfile import ZipFile

from brynz.benchmark import bundle


def test_bundle_contains_evidence_but_not_environment_or_weights(tmp_path):
    for relative in [
        "pyproject.toml",
        "uv.lock",
        "brynz/cli.py",
        "single_room/odometry.csv",
        "out/benchmark/benchmark.json",
        "models/model.safetensors",
        ".venv/python.exe",
    ]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    report = bundle(tmp_path, tmp_path / "out/submission")
    with ZipFile(report["output"]) as archive:
        names = set(archive.namelist())
        assert "pyproject.toml" in names
        assert "single_room/odometry.csv" in names
        assert "out/benchmark/benchmark.json" in names
        assert not any(name.startswith(("models/", ".venv/")) for name in names)
        assert archive.testzip() is None
