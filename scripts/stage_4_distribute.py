#!/usr/bin/env python3
"""Stage 4: Distribution - Push approved content to Google Sheets and confirm."""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add skill directory to path
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "scripts" / "utils"))

# Import utility modules
import state_manager as sm
from sheets_client import write_published_content
from discord_fmt import format_distribution_confirm


def run_stage_4(dry_run: bool = False) -> Dict[str, Any]:
    """Execute Stage 4: Distribution.

    Args:
        dry_run: If True, skip actual sheet writing and Discord posting

    Returns:
        Result dictionary with status and metrics
    """
    result = {
        "success": False,
        "sheet_url": "",
        "row_written": False,
        "total_cost": 0.0,
        "thread_id": None,
        "error": None
    }

    # Load configuration
    config = _load_config()

    # Check if at Stage 4
    current_stage = sm.get_current_stage()
    if current_stage != 4:
        result["error"] = f"Expected stage 4, currently at stage {current_stage}"
        sm.set_status("failed")
        return result

    # Set status to in_progress
    sm.set_status("in_progress")

    # Get Stage 3 data (generated content)
    content_data = sm.get_data(3)
    if not content_data:
        result["error"] = "No generated content found from Stage 3"
        sm.set_status("failed")
        _post_error_to_discord(config, "No content from Stage 3", dry_run)
        return result

    # Get thread IDs for reference
    thread_1 = sm.get_thread_id(1)
    thread_2 = sm.get_thread_id(2)
    thread_3 = sm.get_thread_id(3)

    # Calculate total pipeline cost
    state = sm.load_state()
    cost_tracking = state.get("cost_tracking", {})
    result["total_cost"] = sum(cost_tracking.values())

    # Prepare content for Sheets
    content_text = content_data.get("content", "")
    source_title = content_data.get("source_title", "")
    source_url = content_data.get("source_url", "")
    word_count = content_data.get("word_count", 0)

    # Truncate content if too long for Sheets (50K char limit)
    MAX_CONTENT_LENGTH = 45000
    if len(content_text) > MAX_CONTENT_LENGTH:
        content_text = content_text[:MAX_CONTENT_LENGTH] + "\n... [truncated]"
        print(f"Content truncated to {MAX_CONTENT_LENGTH} chars")

    # Write to Google Sheets
    sheet_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "content": content_text,
        "source_title": source_title,
        "source_url": source_url,
        "word_count": word_count,
        "thread_stage_1": thread_1 or "",
        "thread_stage_2": thread_2 or "",
        "thread_stage_3": thread_3 or "",
        "status": "published",
        "total_cost": result["total_cost"]
    }

    if not dry_run:
        print("Writing to Google Sheets...")
        sheet_success = write_published_content(content_data=sheet_data)

        if not sheet_success:
            result["error"] = "Failed to write to Google Sheets"
            sm.set_status("failed")
            _post_error_to_discord(config, "Google Sheets write failed", dry_run)
            return result

        result["row_written"] = True
        result["sheet_url"] = config.get("sheets", {}).get("research_sheet_url", "")
        print("Content published to Google Sheets")
    else:
        print("[DRY RUN] Would write to Google Sheets")
        result["row_written"] = True

    # Format Discord confirmation message
    discord_msg = _format_completion_message(
        source_title=source_title,
        source_url=source_url,
        total_cost=result["total_cost"],
        cost_breakdown=cost_tracking,
        thread_3=thread_3
    )

    # Post confirmation to Discord
    if not dry_run:
        confirm_thread = _post_to_discord(config, discord_msg, reply_to=thread_3)
        if confirm_thread:
            result["thread_id"] = confirm_thread
        else:
            print("Warning: Discord confirmation failed")
    else:
        print(f"[DRY RUN] Would post to Discord:\n{discord_msg[:500]}...")

    # Mark pipeline as complete
    sm.set_status("completed")

    # Archive state to history
    if not dry_run:
        _archive_completed_state()

    result["success"] = True
    print("Pipeline complete!")

    return result


def _load_config() -> dict:
    """Load configuration from config.json."""
    config_file = SKILL_DIR / "assets" / "config.json"
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _format_completion_message(
    source_title: str,
    source_url: str,
    total_cost: float,
    cost_breakdown: dict,
    thread_3: Optional[str]
) -> str:
    """Format final pipeline completion message for Discord."""

    # Format cost breakdown
    cost_lines = []
    for service, cost in cost_breakdown.items():
        if cost > 0:
            cost_lines.append(f"  - {service.title()}: ${cost:.4f}")
    cost_text = "\n".join(cost_lines) if cost_lines else "  - No costs recorded"

    return f"""## ✅ Pipeline Complete — {datetime.now().strftime("%Y-%m-%d")}

Content published to Google Sheet!

📊 **Final Pipeline Report**
- Stage: 4/4 (Distribution) ✅
- Total Pipeline Cost: ${total_cost:.4f}
{cost_text}
- Source: "{source_title}"
- Status: Complete ✅

---
*Next pipeline run: tomorrow 8:00 AM (VN time)*"""


def _post_to_discord(config: dict, message: str, reply_to: Optional[str] = None) -> Optional[str]:
    """Post message to Discord #content-creation forum.

    Args:
        config: Configuration dictionary
        message: Message content to post
        reply_to: Optional thread ID to reply to

    Returns:
        Thread ID if successful, None otherwise
    """
    channel_id = config.get("discord", {}).get("content_channel_id", "")

    if not channel_id or channel_id.startswith("PLACEHOLDER"):
        print("Warning: Discord content_channel_id not configured")
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    thread_title = f"Pipeline Complete — {today}"

    try:
        cmd = [
            "openclaw", "message", "send",
            "--channel", channel_id,
            "--content", message,
            "--thread-title", thread_title
        ]

        # Add reply-to if specified
        if reply_to:
            cmd.extend(["--reply-to", reply_to])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print(f"Posted to Discord: {thread_title}")
            # TODO: Parse actual thread ID from openclaw message send output
            # Current openclaw CLI doesn't return thread ID in stdout
            # Using date-based placeholder; update when API provides thread ID
            return f"confirm_{today}"
        else:
            print(f"Discord post failed: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        print("Discord post timed out")
        return None
    except FileNotFoundError:
        print("openclaw CLI not found")
        return None
    except Exception as e:
        print(f"Discord post error: {e}")
        return None


def _post_error_to_discord(config: dict, error_msg: str, dry_run: bool = False) -> None:
    """Post error message to Discord."""
    if dry_run:
        print(f"[DRY RUN] Would post error: {error_msg}")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    message = f"""## ❌ Stage 4 Error — {today}

**Error:** {error_msg}

Pipeline halted. Manual intervention required.

---"""

    _post_to_discord(config, message)


def _archive_completed_state() -> None:
    """Archive completed state to history file."""
    state = sm.load_state()

    # Save to history with completion timestamp
    history_file = SKILL_DIR / "history" / f"pipeline_{state.get('current_date', 'unknown')}_complete.json"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    # Add completion timestamp
    state["completed_at"] = datetime.now().isoformat()

    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    print(f"State archived to: {history_file}")


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 4: Distribution")
    parser.add_argument("--dry-run", action="store_true", help="Run without actual sheet writing or posting")
    parser.add_argument("--show-state", action="store_true", help="Show current state and exit")
    args = parser.parse_args()

    if args.show_state:
        state = sm.load_state()
        print(json.dumps(state, indent=2, ensure_ascii=False))
        sys.exit(0)

    print("="*60)
    print("Stage 4: Distribution")
    print("="*60)
    print()

    result = run_stage_4(dry_run=args.dry_run)

    print()
    print("="*60)
    print("Results:")
    print(f"  Success: {result['success']}")
    print(f"  Sheet written: {result['row_written']}")
    print(f"  Total cost: ${result['total_cost']:.4f}")
    if result['error']:
        print(f"  Error: {result['error']}")
    if result['thread_id']:
        print(f"  Thread ID: {result['thread_id']}")
    print("="*60)

    sys.exit(0 if result['success'] else 1)
