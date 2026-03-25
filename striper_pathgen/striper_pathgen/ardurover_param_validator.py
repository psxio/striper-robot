"""Validation helpers for the checked-in ArduRover parameter baseline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


LOCKED_NUMERIC_PARAMS = {
    "FRAME_TYPE": "2",
    "GPS_TYPE": "25",
    "GPS_TYPE2": "25",
    "SERIAL5_PROTOCOL": "5",
    "EK3_SRC1_YAW": "2",
    "COMPASS_ENABLE": "0",
    "SPRAY_ENABLE": "0",
    "SCR_ENABLE": "1",
    "FENCE_ENABLE": "1",
    "WP_SPEED": "0.50",
    "CRUISE_SPEED": "1.00",
}

REQUIRED_NUMERIC_PARAMS = {
    *LOCKED_NUMERIC_PARAMS.keys(),
    "RELAY1_PIN",
    "RELAY2_PIN",
    "BATT_LOW_VOLT",
    "BATT_CRT_VOLT",
    "BATT_ARM_VOLT",
    "GPS_MB1_OFS_Y",
    "AVOID_ENABLE",
}


@dataclass(slots=True)
class ValidationResult:
    errors: list[str]
    warnings: list[str]
    stats: dict[str, int]

    @property
    def ok(self) -> bool:
        return not self.errors


def _parse_numeric_params(content: str) -> tuple[dict[str, float], list[str], list[str], int]:
    params: dict[str, float] = {}
    errors: list[str] = []
    warnings: list[str] = []
    parsed_parameters = 0

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "," not in line:
            errors.append(f"Line {line_number}: parameter line must contain a comma")
            continue

        name, raw_value = line.split(",", 1)
        name = name.strip()
        raw_value = raw_value.strip()

        if not name:
            errors.append(f"Line {line_number}: parameter name is empty")
            continue

        if not raw_value:
            errors.append(f"Line {line_number}: parameter {name} is missing a value")
            continue

        try:
            numeric_value = float(raw_value)
        except ValueError:
            errors.append(f"Parameter {name} must have a numeric value, got {raw_value!r}")
            continue

        if name in params:
            warnings.append(f"Parameter {name} is duplicated; using the last value")

        params[name] = numeric_value
        parsed_parameters += 1

    return params, errors, warnings, parsed_parameters


def _validate_required_params(params: dict[str, float], errors: list[str]) -> None:
    for name in sorted(REQUIRED_NUMERIC_PARAMS):
        if name not in params:
            errors.append(f"Missing required parameter {name}")

    for name, expected in LOCKED_NUMERIC_PARAMS.items():
        if name not in params:
            continue

        expected_value = float(expected)
        if params[name] != expected_value:
            errors.append(
                f"Parameter {name}={_format_numeric(params[name])} does not match expected {expected}"
            )


def _validate_consistency(params: dict[str, float], errors: list[str]) -> None:
    if {"BATT_ARM_VOLT", "BATT_LOW_VOLT", "BATT_CRT_VOLT"}.issubset(params):
        arm_voltage = params["BATT_ARM_VOLT"]
        low_voltage = params["BATT_LOW_VOLT"]
        critical_voltage = params["BATT_CRT_VOLT"]
        if not (arm_voltage > low_voltage > critical_voltage):
            errors.append(
                "Battery thresholds must satisfy BATT_ARM_VOLT > BATT_LOW_VOLT > BATT_CRT_VOLT"
            )

    if {"RELAY1_PIN", "RELAY2_PIN"}.issubset(params):
        if params["RELAY1_PIN"] == params["RELAY2_PIN"]:
            errors.append(
                "RELAY1_PIN and RELAY2_PIN must be different to avoid paint and pump conflicts"
            )

    if "GPS_MB1_OFS_Y" in params and params["GPS_MB1_OFS_Y"] <= 0:
        errors.append("GPS_MB1_OFS_Y must be greater than 0 for a valid moving-baseline separation")

    if {"CRUISE_SPEED", "WP_SPEED"}.issubset(params):
        if params["CRUISE_SPEED"] <= params["WP_SPEED"]:
            errors.append("CRUISE_SPEED must be greater than WP_SPEED for transit-versus-paint speed separation")


def _format_numeric(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def validate_ardurover_params(content: str) -> ValidationResult:
    """Validate ArduRover parameter file content from a string."""
    params, errors, warnings, parsed_parameters = _parse_numeric_params(content)
    _validate_required_params(params, errors)
    _validate_consistency(params, errors)

    return ValidationResult(
        errors=errors,
        warnings=warnings,
        stats={
            "parsed_parameters": parsed_parameters,
            "required_parameters": len(REQUIRED_NUMERIC_PARAMS),
            "warning_count": len(warnings),
            "error_count": len(errors),
        },
    )


def validate_ardurover_params_file(path: str | Path) -> ValidationResult:
    """Validate an ArduRover parameter file from disk."""
    param_path = Path(path)
    if not param_path.is_file():
        raise FileNotFoundError(param_path)

    return validate_ardurover_params(param_path.read_text(encoding="utf-8"))
