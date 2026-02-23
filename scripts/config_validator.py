#!/usr/bin/env python3
"""Configuration validation for content-pipeline skill."""

import os
import json
from pathlib import Path
from typing import List, Tuple

SKILL_DIR = Path(__file__).parent.parent
CONFIG_FILE = SKILL_DIR / "assets" / "config.json"


def validate_config(config_path: str = None) -> Tuple[bool, List[str], List[str]]:
    """Validate configuration file for required values and placeholders.

    Args:
        config_path: Optional path to config file

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    if config_path is None:
        config_path = CONFIG_FILE

    # Check config file exists
    if not Path(config_path).exists():
        errors.append(f"Config file not found: {config_path}")
        return False, errors, warnings

    # Load config
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON in config file: {e}")
        return False, errors, warnings

    # Check for placeholder values
    placeholders = _find_placeholders(config)
    for path, value in placeholders:
        warnings.append(f"Placeholder value at {path}: '{value}'")

    # Check required environment variables
    env_checks = _check_env_vars(config)
    for var, is_set in env_checks.items():
        if not is_set:
            warnings.append(f"Environment variable not set: {var}")

    # Validate structure
    required_sections = ["apify", "keywords", "thresholds", "discord", "sheets", "models", "budget"]
    for section in required_sections:
        if section not in config:
            errors.append(f"Missing required section: {section}")

    # Validate specific values
    if "thresholds" in config:
        if config["thresholds"].get("viral", 0) < 1:
            errors.append("viral threshold must be positive")
        if config["thresholds"].get("micro_viral", 0) < 1:
            errors.append("micro_viral threshold must be positive")

    if "budget" in config:
        if config["budget"].get("daily_apify_cap_usd", 0) < 0:
            errors.append("daily_apify_cap_usd must be non-negative")
        if config["budget"].get("daily_gemini_cap_usd", 0) < 0:
            errors.append("daily_gemini_cap_usd must be non-negative")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def _find_placeholders(obj, path: str = "config") -> List[Tuple[str, str]]:
    """Recursively find placeholder values in config."""
    placeholders = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}"
            if isinstance(value, str) and value.startswith("PLACEHOLDER"):
                placeholders.append((current_path, value))
            elif isinstance(value, (dict, list)):
                placeholders.extend(_find_placeholders(value, current_path))

    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            current_path = f"{path}[{i}]"
            if isinstance(item, str) and item.startswith("PLACEHOLDER"):
                placeholders.append((current_path, item))
            elif isinstance(item, (dict, list)):
                placeholders.extend(_find_placeholders(item, current_path))

    return placeholders


def _check_env_vars(config: dict) -> dict:
    """Check if referenced environment variables are set."""
    env_vars = {}

    def scan_for_env_refs(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and value.startswith("ENV:"):
                    var_name = value[4:]
                    env_vars[var_name] = bool(os.environ.get(var_name))
                elif isinstance(value, (dict, list)):
                    scan_for_env_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                scan_for_env_refs(item)

    scan_for_env_refs(config)
    return env_vars


def print_validation_report():
    """Print validation report to stdout."""
    print("="*60)
    print("Content Pipeline Configuration Validation")
    print("="*60)

    is_valid, errors, warnings = validate_config()

    print(f"\nConfig file: {CONFIG_FILE}")
    print(f"Status: {'✅ VALID' if is_valid else '❌ INVALID'}")

    if errors:
        print(f"\n❌ Errors ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")

    if warnings:
        print(f"\n⚠️  Warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")

    if not errors and not warnings:
        print("\n✅ No issues found. Configuration is complete.")

    print("\n" + "="*60)
    return is_valid


if __name__ == "__main__":
    import sys
    is_valid = print_validation_report()
    sys.exit(0 if is_valid else 1)
