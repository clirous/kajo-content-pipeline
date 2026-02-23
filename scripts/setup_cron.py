#!/usr/bin/env python3
"""Cron setup script for content pipeline daily trigger."""

import os
import sys
import subprocess
import json
from pathlib import Path

# Skill directory
SKILL_DIR = Path(__file__).parent.parent
CONFIG_FILE = SKILL_DIR / "assets" / "config.json"


def load_config() -> dict:
    """Load configuration."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def setup_cron(dry_run: bool = False) -> bool:
    """Set up daily cron job for content pipeline.

    Args:
        dry_run: If True, only print the command without executing

    Returns:
        True if successful, False otherwise
    """
    config = load_config()

    # Get config values
    research_channel = config.get("discord", {}).get("research_channel_id", "")
    cron_time = config.get("pipeline", {}).get("cron_time", "08:00")
    timezone = config.get("pipeline", {}).get("timezone", "Asia/Ho_Chi_Minh")

    # Parse cron time (HH:MM -> cron format)
    try:
        hour, minute = cron_time.split(":")
        cron_expr = f"{minute} {hour} * * *"
    except ValueError:
        print(f"Invalid cron_time format: {cron_time}, using default 08:00")
        cron_expr = "0 8 * * *"

    # Build openclaw cron command
    # Note: openclaw cron triggers the agent which reads SKILL.md based on message keywords
    cmd = [
        "openclaw", "cron", "add",
        "--name", "content-pipeline-daily",
        "--agent", "kajo",
        "--cron", cron_expr,
        "--tz", timezone,
        "--message", "Run content pipeline Stage 1: scrape viral wellness content for today. Keywords: pipeline, scrape, viral",
        "--session", "isolated"
    ]

    # Add channel if configured
    if research_channel and not research_channel.startswith("PLACEHOLDER"):
        cmd.extend([
            "--announce",
            "--channel", "discord",
            "--to", f"channel:{research_channel}"
        ])

    print("Cron setup command:")
    print(" ".join(cmd))
    print()

    if dry_run:
        print("[DRY RUN] Command not executed")
        return True

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print("✓ Cron job created successfully!")
            print(result.stdout)
            return True
        else:
            print(f"✗ Failed to create cron job: {result.stderr}")
            return False

    except FileNotFoundError:
        print("✗ openclaw CLI not found. Install openclaw to use cron scheduling.")
        return False
    except subprocess.TimeoutExpired:
        print("✗ Command timed out")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_cron(dry_run: bool = False) -> bool:
    """Test cron with one-shot trigger (fires in 2 minutes).

    Args:
        dry_run: If True, only print the command

    Returns:
        True if successful
    """
    config = load_config()
    research_channel = config.get("discord", {}).get("research_channel_id", "")

    cmd = [
        "openclaw", "cron", "add",
        "--name", "content-pipeline-test",
        "--agent", "kajo",
        "--at", "2m",  # Fire in 2 minutes
        "--message", "TEST: Run content pipeline Stage 1. Keywords: pipeline, scrape, viral",
        "--session", "isolated"
    ]

    if research_channel and not research_channel.startswith("PLACEHOLDER"):
        cmd.extend([
            "--announce",
            "--channel", "discord",
            "--to", f"channel:{research_channel}"
        ])

    print("Test cron command (fires in 2 minutes):")
    print(" ".join(cmd))
    print()

    if dry_run:
        print("[DRY RUN] Command not executed")
        return True

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✓ Test cron scheduled! Check Discord in 2 minutes.")
            return True
        else:
            print(f"✗ Failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("✗ openclaw CLI not found")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def show_cron_info():
    """Display cron configuration info."""
    config = load_config()

    print("=" * 50)
    print("Content Pipeline Cron Configuration")
    print("=" * 50)
    print(f"Schedule: {config.get('pipeline', {}).get('cron_time', '08:00')} daily")
    print(f"Timezone: {config.get('pipeline', {}).get('timezone', 'Asia/Ho_Chi_Minh')}")
    print(f"Channel:  {config.get('discord', {}).get('research_channel_id', 'not configured')}")
    print()
    print("To set up cron, run:")
    print("  python3 scripts/setup_cron.py --setup")
    print()
    print("To test (fires in 2 minutes):")
    print("  python3 scripts/setup_cron.py --test")
    print("=" * 50)


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Content Pipeline Cron Setup")
    parser.add_argument("--setup", action="store_true", help="Set up daily cron job")
    parser.add_argument("--test", action="store_true", help="Test with 2-minute one-shot trigger")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    parser.add_argument("--info", action="store_true", help="Show cron configuration info")
    args = parser.parse_args()

    if args.info or (not args.setup and not args.test):
        show_cron_info()
    elif args.setup:
        success = setup_cron(dry_run=args.dry_run)
        sys.exit(0 if success else 1)
    elif args.test:
        success = test_cron(dry_run=args.dry_run)
        sys.exit(0 if success else 1)
