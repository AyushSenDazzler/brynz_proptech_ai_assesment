import pytest

from brynz.output import _validate_intervals


def test_out_of_range_measurement_is_rejected():
    with pytest.raises(ValueError, match="outside"):
        _validate_intervals({"value": 2, "interval": [0, 1], "unit": "m", "status": "uncalibrated"})


def test_unknown_measurement_cannot_have_a_fake_interval():
    with pytest.raises(ValueError, match="Unknown"):
        _validate_intervals(
            {"value": None, "interval": [0, 1], "unit": "m", "status": "unobserved"}
        )
