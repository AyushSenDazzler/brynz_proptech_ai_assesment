import pytest

from brynz.output import _validate_intervals


def test_markdown_pdf_lines_preserve_content_without_markup(tmp_path):
    from brynz.output import _report_lines

    path = tmp_path / "report.md"
    path.write_text(
        "# Report\n\n**Partial** [result](result.json).\n\n```bash\nuv run brynz\n```\n",
        encoding="utf-8",
    )
    lines = _report_lines(path)
    assert ("Report", "heading") in lines
    assert ("Partial result.", "body") in lines
    assert ("uv run brynz", "code") in lines


def test_markdown_pdf_has_six_page_limit(tmp_path):
    from brynz.output import render_report

    path = tmp_path / "long.md"
    path.write_text("# Report\n\n" + "Long report paragraph.\n\n" * 200, encoding="utf-8")
    with pytest.raises(ValueError, match="six-page"):
        render_report(path, tmp_path / "out")


def test_out_of_range_measurement_is_rejected():
    with pytest.raises(ValueError, match="outside"):
        _validate_intervals({"value": 2, "interval": [0, 1], "unit": "m", "status": "uncalibrated"})


def test_unknown_measurement_cannot_have_a_fake_interval():
    with pytest.raises(ValueError, match="Unknown"):
        _validate_intervals(
            {"value": None, "interval": [0, 1], "unit": "m", "status": "unobserved"}
        )
