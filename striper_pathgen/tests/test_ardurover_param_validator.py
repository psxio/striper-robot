"""Tests for the ArduRover parameter validator."""

from __future__ import annotations

from pathlib import Path

import pytest

from striper_pathgen.ardurover_param_validator import (
    validate_ardurover_params,
    validate_ardurover_params_file,
)


_ROOT = Path(__file__).resolve().parents[2]
_BASELINE_PARAM_FILE = _ROOT / "ardurover" / "params" / "striper.param"


def _replace_param(content: str, name: str, value: str) -> str:
    needle = f"{name},"
    for line in content.splitlines():
        if line.startswith(needle):
            return content.replace(line, f"{name},{value}", 1)
    raise AssertionError(f"Parameter {name} not found in test fixture")


def _remove_param(content: str, name: str) -> str:
    lines = [line for line in content.splitlines() if not line.startswith(f"{name},")]
    return "\n".join(lines) + "\n"


def _load_baseline() -> str:
    return _BASELINE_PARAM_FILE.read_text(encoding="utf-8")


class TestBaselineValidation:
    def test_checked_in_param_file_passes(self):
        result = validate_ardurover_params_file(_BASELINE_PARAM_FILE)
        assert result.ok, f"Expected baseline file to pass, got: {result.errors}"
        assert result.stats["parsed_parameters"] > 0
        assert result.stats["required_parameters"] >= 10

    def test_validate_from_string_matches_file_validation(self):
        content = _load_baseline()
        result = validate_ardurover_params(content)
        assert result.ok
        assert result.stats["parsed_parameters"] > 0


class TestRequiredParameterChecks:
    def test_missing_required_parameter_fails(self):
        content = _remove_param(_load_baseline(), "GPS_TYPE2")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("GPS_TYPE2" in error for error in result.errors)

    def test_wrong_locked_value_fails(self):
        content = _replace_param(_load_baseline(), "GPS_TYPE", "1")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("GPS_TYPE" in error and "expected 25" in error for error in result.errors)

    def test_wrong_serial_mapping_fails(self):
        content = _replace_param(_load_baseline(), "SERIAL5_PROTOCOL", "2")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("SERIAL5_PROTOCOL" in error for error in result.errors)

    def test_wrong_yaw_source_fails(self):
        content = _replace_param(_load_baseline(), "EK3_SRC1_YAW", "8")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("EK3_SRC1_YAW" in error for error in result.errors)

    def test_compass_enabled_fails(self):
        content = _replace_param(_load_baseline(), "COMPASS_ENABLE", "1")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("COMPASS_ENABLE" in error for error in result.errors)


class TestSafetyConsistencyChecks:
    def test_battery_threshold_order_is_enforced(self):
        content = _replace_param(_load_baseline(), "BATT_ARM_VOLT", "32.0")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("BATT_ARM_VOLT" in error for error in result.errors)

    def test_relay_pin_conflict_is_rejected(self):
        content = _replace_param(_load_baseline(), "RELAY2_PIN", "54")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("RELAY1_PIN" in error and "RELAY2_PIN" in error for error in result.errors)

    def test_negative_moving_baseline_offset_is_rejected(self):
        content = _replace_param(_load_baseline(), "GPS_MB1_OFS_Y", "0")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("GPS_MB1_OFS_Y" in error for error in result.errors)


class TestParsingBehavior:
    def test_duplicate_parameters_warn(self):
        content = _load_baseline() + "GPS_TYPE,25\n"
        result = validate_ardurover_params(content)
        assert result.ok
        assert any("GPS_TYPE" in warning and "duplicate" in warning.lower() for warning in result.warnings)

    def test_invalid_parameter_line_fails(self):
        content = _load_baseline() + "THIS IS NOT A PARAM LINE\n"
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("Line" in error and "comma" in error.lower() for error in result.errors)

    def test_non_numeric_value_fails(self):
        content = _replace_param(_load_baseline(), "FRAME_TYPE", "two")
        result = validate_ardurover_params(content)
        assert not result.ok
        assert any("FRAME_TYPE" in error and "numeric" in error.lower() for error in result.errors)


def test_missing_file_raises_file_not_found():
    missing_path = _ROOT / "ardurover" / "params" / "does_not_exist.param"
    with pytest.raises(FileNotFoundError):
        validate_ardurover_params_file(missing_path)