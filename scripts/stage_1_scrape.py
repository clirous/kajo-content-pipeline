#!/usr/bin/env python3
"""Stage 1: Viral Scraping - Daily Apify scraping of wellness posts from IG/FB."""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add skill directory to path
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "scripts" / "utils"))

# Import utility modules
import state_manager as sm
from apify_scraper import (
    scrape_instagram, scrape_facebook, filter_by_engagement,
    get_top_posts, estimate_cost, _load_config
)
from discord_fmt import format_scraped_results, format_report_card


def run_stage_1(dry_run: bool = False) -> Dict[str, Any]:
    """Execute Stage 1: Viral Scraping.

    Args:
        dry_run: If True, skip actual scraping and Discord posting

    Returns:
        Result dictionary with status, posts, and metrics
    """
    result = {
        "success": False,
        "posts": [],
        "total_scraped": 0,
        "filtered_count": 0,
        "cost": 0.0,
        "thread_id": None,
        "error": None
    }

    # Load configuration
    config = _load_config()

    # Check if already at Stage 1
    current_stage = sm.get_current_stage()
    if current_stage != 1:
        result["error"] = f"Expected stage 1, currently at stage {current_stage}"
        sm.set_status("failed")
        return result

    # Check budget before starting
    if not sm.check_budget("apify", config):
        result["error"] = "Daily Apify budget exceeded"
        _post_error_to_discord(config, "Budget exceeded", dry_run)
        return result

    # Set status to in_progress
    sm.set_status("in_progress")

    # Get keywords from config (mix VN and EN)
    keywords_vi = config.get("keywords", {}).get("vi", [])
    keywords_en = config.get("keywords", {}).get("en", [])
    keywords = keywords_vi + keywords_en

    # Get scraping parameters
    max_results = config.get("apify", {}).get("max_results_per_run", 100)
    threshold = config.get("thresholds", {}).get("micro_viral", 500)
    max_posts = config.get("pipeline", {}).get("max_posts_per_scrape", 10)

    all_posts = []
    ig_count = 0
    fb_count = 0

    # Scrape Instagram
    if not dry_run:
        print(f"Scraping Instagram for: {keywords[:5]}")
        ig_posts = scrape_instagram(keywords, max_results, config)
        ig_count = len(ig_posts)
        all_posts.extend(ig_posts)
        print(f"  Found {ig_count} Instagram posts")
    else:
        print("[DRY RUN] Would scrape Instagram")

    # Check budget after Instagram - record cost and check remaining budget
    if not dry_run and ig_count > 0:
        ig_cost = estimate_cost(ig_count, "instagram")
        sm.record_cost("apify", ig_cost)
        if not sm.check_budget("apify", config):
            print("Budget cap reached after Instagram, skipping Facebook")
        else:
            # Scrape Facebook
            print(f"Scraping Facebook for: {keywords[:5]}")
            fb_posts = scrape_facebook(keywords, max_results, config)
            fb_count = len(fb_posts)
            all_posts.extend(fb_posts)
            print(f"  Found {fb_count} Facebook posts")

    result["total_scraped"] = len(all_posts)

    # Filter by engagement threshold
    filtered_posts = filter_by_engagement(all_posts, threshold)
    result["filtered_count"] = len(filtered_posts)
    print(f"Filtered to {len(filtered_posts)} posts with {threshold}+ engagement")

    # Get top N posts
    top_posts = get_top_posts(filtered_posts, max_posts)

    # Deduplicate by URL
    seen_urls = set()
    unique_posts = []
    for post in top_posts:
        url = post.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_posts.append(post)

    result["posts"] = unique_posts
    print(f"Final: {len(unique_posts)} unique viral posts")

    # Calculate cost
    total_cost = estimate_cost(result["total_scraped"], "mixed")
    result["cost"] = total_cost

    # Record cost in state
    if not dry_run:
        sm.record_cost("apify", total_cost)

    # Save posts to state for Stage 2
    sm.add_data(1, unique_posts)

    # Format Discord message
    platform_str = "mixed" if ig_count > 0 and fb_count > 0 else ("instagram" if ig_count > 0 else "facebook")
    discord_msg = format_scraped_results(
        unique_posts,
        result["total_scraped"],
        result["filtered_count"],
        platform_str
    )

    # Add report card
    report_card = format_report_card(
        stage=1,
        model="Apify Scraping",
        tokens_in=0,
        tokens_out=0,
        cost=total_cost,
        status="awaiting approval"
    )

    # Add admin tag
    admin_id = config.get("discord", {}).get("admin_user_id", "")
    admin_tag = f"\n\n<@{admin_id}> — Approve to proceed to Pattern Analysis" if admin_id else ""

    full_message = f"{discord_msg}\n\n{report_card}{admin_tag}"

    # Post to Discord
    discord_success = True
    if not dry_run:
        thread_id = _post_to_discord(config, full_message)
        if thread_id:
            result["thread_id"] = thread_id
            sm.set_thread_id(1, thread_id)
        else:
            # Discord posting failed but we have results - still mark as partial success
            discord_success = False
            print("Warning: Discord posting failed")
    else:
        print(f"[DRY RUN] Would post to Discord:\n{full_message[:500]}...")

    # Update status and result
    if discord_success:
        sm.set_status("awaiting_approval")
        result["success"] = True
    else:
        # Partial success - data saved but Discord failed
        sm.set_status("discord_failed")
        result["success"] = True  # Still success since data was scraped
        result["error"] = "Discord posting failed - data saved to state"

    return result


def _post_to_discord(config: dict, message: str) -> Optional[str]:
    """Post message to Discord #research forum.

    Args:
        config: Configuration dictionary
        message: Message content to post

    Returns:
        Thread ID if successful, None otherwise
    """
    channel_id = config.get("discord", {}).get("research_channel_id", "")

    if not channel_id or channel_id.startswith("PLACEHOLDER"):
        print("Warning: Discord research_channel_id not configured")
        return None

    # Create thread title with date
    today = datetime.now().strftime("%Y-%m-%d")
    thread_title = f"Viral Scraping — {today}"

    try:
        # Use openclaw message send command
        cmd = [
            "openclaw", "message", "send",
            "--channel", channel_id,
            "--content", message,
            "--thread-title", thread_title
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            # Parse thread ID from output if available
            output = result.stdout.strip()
            print(f"Posted to Discord: {thread_title}")
            # Return a placeholder thread ID (actual ID would come from API response)
            return f"thread_{today}"
        else:
            print(f"Discord post failed: {result.stderr}")
            return None

    except subprocess.TimeoutExpired:
        print("Discord post timed out")
        return None
    except FileNotFoundError:
        print("openclaw CLI not found. Install openclaw to enable Discord posting.")
        return None
    except Exception as e:
        print(f"Discord post error: {e}")
        return None


def _post_error_to_discord(config: dict, error_msg: str, dry_run: bool = False) -> None:
    """Post error message to Discord.

    Args:
        config: Configuration dictionary
        error_msg: Error message to post
        dry_run: If True, skip actual posting
    """
    if dry_run:
        print(f"[DRY RUN] Would post error: {error_msg}")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    message = f"""## ❌ Stage 1 Error — {today}

**Error:** {error_msg}

Pipeline halted. Manual intervention required.

---"""

    _post_to_discord(config, message)


def _format_post_for_display(post: dict) -> str:
    """Format a single post for display.

    Args:
        post: Post dictionary

    Returns:
        Formatted string
    """
    platform = post.get("platform", "unknown")
    platform_emoji = "📱" if platform == "instagram" else "📘" if platform == "facebook" else "📱"
    author = post.get("author", "unknown")
    likes = post.get("likes", 0)
    comments = post.get("comments", 0)
    shares = post.get("shares", 0)
    url = post.get("url", "")
    caption = post.get("caption", "")[:100]

    return f"""{platform_emoji} **{author}**
❤️ {likes:,} | 💬 {comments:,} | 🔄 {shares:,}
> {caption}...
🔗 {url}"""


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 1: Viral Scraping")
    parser.add_argument("--dry-run", action="store_true", help="Run without actual scraping or posting")
    parser.add_argument("--show-state", action="store_true", help="Show current state and exit")
    args = parser.parse_args()

    if args.show_state:
        state = sm.load_state()
        print(json.dumps(state, indent=2, ensure_ascii=False))
        sys.exit(0)

    print("="*60)
    print("Stage 1: Viral Scraping")
    print("="*60)
    print()

    result = run_stage_1(dry_run=args.dry_run)

    print()
    print("="*60)
    print("Results:")
    print(f"  Success: {result['success']}")
    print(f"  Total scraped: {result['total_scraped']}")
    print(f"  Filtered: {result['filtered_count']}")
    print(f"  Final posts: {len(result['posts'])}")
    print(f"  Cost: ${result['cost']:.4f}")
    if result['error']:
        print(f"  Error: {result['error']}")
    if result['thread_id']:
        print(f"  Thread ID: {result['thread_id']}")
    print("="*60)

    sys.exit(0 if result['success'] else 1)
