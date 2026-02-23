#!/usr/bin/env python3
"""Stage 3: Content Generation - Generate Vietnamese wellness content from research."""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add skill directory to path
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "scripts" / "utils"))

# Import utility modules
import state_manager as sm
from glm5_client import call_glm5, build_generation_prompt
from paper_fetcher import fetch_paper, format_source_card
from sheets_client import get_next_paper_url
from discord_fmt import format_report_card, format_generated_content


def run_stage_3(dry_run: bool = False) -> Dict[str, Any]:
    """Execute Stage 3: Content Generation.

    Args:
        dry_run: If True, skip actual API calls and Discord posting

    Returns:
        Result dictionary with status, content, and metrics
    """
    result = {
        "success": False,
        "content": "",
        "source_title": "",
        "source_url": "",
        "word_count": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost": 0.0,
        "thread_id": None,
        "access_type": "full",
        "error": None
    }

    # Load configuration
    config = _load_config()

    # Check if at Stage 3
    current_stage = sm.get_current_stage()
    if current_stage != 3:
        result["error"] = f"Expected stage 3, currently at stage {current_stage}"
        sm.set_status("failed")
        return result

    # Set status to in_progress
    sm.set_status("in_progress")

    # Get Stage 2 data (patterns)
    patterns = sm.get_data(2)
    if not patterns:
        print("Warning: No patterns from Stage 2, using defaults")
        patterns = _get_default_patterns()

    # Get next paper URL
    if not dry_run:
        paper_url = get_next_paper_url()
        if not paper_url:
            result["error"] = "No paper URL available from research sheet"
            sm.set_status("failed")
            _post_error_to_discord(config, "No paper URLs in research sheet", dry_run)
            return result
        result["source_url"] = paper_url
        print(f"Paper URL: {paper_url}")
    else:
        print("[DRY RUN] Would fetch paper URL from sheets")
        result["source_url"] = "https://example.com/paper"
        paper_url = None

    # Fetch paper content
    if not dry_run and paper_url:
        print("Fetching paper content...")
        paper_data, access_type = fetch_paper(paper_url)
        result["access_type"] = access_type

        if paper_data.get("error"):
            print(f"Warning: Paper fetch error: {paper_data['error']}")
            # Continue with what we have

        result["source_title"] = paper_data.get("title", "Unknown Title")
        paper_content = paper_data.get("content", "")
        paper_quotes = paper_data.get("quotes", [])
        paper_abstract = paper_data.get("abstract", "")

        print(f"Title: {result['source_title']}")
        print(f"Access: {access_type}")
        print(f"Content length: {len(paper_content)} chars")
        print(f"Quotes found: {len(paper_quotes)}")
    else:
        result["source_title"] = "Sample Research Paper"
        paper_content = "Sample content for dry run."
        paper_quotes = [{"text": "Sample quote for testing.", "page": "1"}]
        paper_abstract = "Sample abstract."
        access_type = "full"

    # Build generation prompt
    findings = paper_content[:2000] if paper_content else paper_abstract

    system_prompt, user_prompt = build_generation_prompt(
        patterns=patterns,
        paper_title=result["source_title"],
        findings=findings,
        quotes=paper_quotes
    )

    # Call GLM5 for content generation
    if not dry_run:
        print("Calling GLM5 API...")
        generated_content, meta = call_glm5(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config
        )

        if meta.get("error"):
            result["error"] = f"GLM5 API error: {meta['error']}"
            sm.set_status("failed")
            _post_error_to_discord(config, meta["error"], dry_run)
            return result

        result["tokens_in"] = meta.get("tokens_in", 0)
        result["tokens_out"] = meta.get("tokens_out", 0)
        result["cost"] = meta.get("cost", 0.0)
        result["content"] = generated_content or ""
        result["word_count"] = len(result["content"].split())

        print(f"Generated {result['word_count']} words")
        print(f"Tokens: {result['tokens_in']} in / {result['tokens_out']} out")

        # Record cost
        sm.record_cost("glm5", result["cost"])
    else:
        print("[DRY RUN] Would call GLM5 API")
        result["content"] = _get_sample_content()
        result["word_count"] = len(result["content"].split())

    # Save generated content to state
    content_data = {
        "content": result["content"],
        "source_title": result["source_title"],
        "source_url": result["source_url"],
        "word_count": result["word_count"],
        "access_type": result["access_type"],
        "generated_at": datetime.now().isoformat()
    }
    sm.add_data(3, content_data)

    # Get best quote for source card
    best_quote = paper_quotes[0] if paper_quotes else {"text": "No quote available", "page": ""}

    # Format source card
    source_card = format_source_card(
        title=result["source_title"],
        quote=best_quote.get("text", ""),
        url=result["source_url"],
        page=best_quote.get("page", ""),
        access_type=access_type
    )

    # Build full Discord message
    discord_msg = format_generated_content(
        content=result["content"],
        source_title=result["source_title"],
        source_url=result["source_url"],
        word_count=result["word_count"]
    )

    # Add source card
    full_content = f"{result['content']}\n\n---\n{source_card}"

    # Add report card
    report_card = format_report_card(
        stage=3,
        model="GLM5",
        tokens_in=result["tokens_in"],
        tokens_out=result["tokens_out"],
        cost=result["cost"],
        status="awaiting approval"
    )

    # Add admin tag
    admin_id = config.get("discord", {}).get("admin_user_id", "")
    admin_tag = f"\n\n<@{admin_id}> — Approve to proceed to Distribution" if admin_id else ""

    full_message = f"{discord_msg}\n\n{source_card}\n\n{report_card}{admin_tag}"

    # Post to Discord
    discord_success = True
    if not dry_run:
        thread_id = _post_to_discord(config, full_message)
        if thread_id:
            result["thread_id"] = thread_id
            sm.set_thread_id(3, thread_id)
        else:
            discord_success = False
            print("Warning: Discord posting failed")
    else:
        print(f"[DRY RUN] Would post to Discord:\n{full_message[:500]}...")

    # Update status
    if discord_success:
        sm.set_status("awaiting_approval")
        result["success"] = True
    else:
        sm.set_status("discord_failed")
        result["success"] = True
        result["error"] = "Discord posting failed - content saved to state"

    return result


def _load_config() -> dict:
    """Load configuration from config.json."""
    config_file = SKILL_DIR / "assets" / "config.json"
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _post_to_discord(config: dict, message: str) -> Optional[str]:
    """Post message to Discord #content-creation forum.

    Args:
        config: Configuration dictionary
        message: Message content to post

    Returns:
        Thread ID if successful, None otherwise
    """
    channel_id = config.get("discord", {}).get("content_channel_id", "")

    if not channel_id or channel_id.startswith("PLACEHOLDER"):
        print("Warning: Discord content_channel_id not configured")
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    thread_title = f"Content Draft — {today}"

    try:
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
            print(f"Posted to Discord: {thread_title}")
            # TODO: Parse actual thread ID from openclaw API response
            return f"thread_{today}"
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
    message = f"""## ❌ Stage 3 Error — {today}

**Error:** {error_msg}

Pipeline halted. Manual intervention required.

---"""

    _post_to_discord(config, message)


def _get_default_patterns() -> dict:
    """Get default patterns when Stage 2 data is missing."""
    return {
        "hooks": [
            {"name": "Question", "template": "Bạn có biết {fact}?", "frequency": 1}
        ],
        "structures": [
            {"type": "educational", "sections": ["hook", "content", "cta"], "percentage": 50}
        ],
        "tone": {
            "formality": "casual-warm",
            "emotions": ["curiosity", "hope"],
            "expressions": ["bạn", "mình", "nha"]
        },
        "ctas": [
            {"type": "engage", "template": "Chia sẻ trải nghiệm bên dưới 👇", "placement": "end"}
        ]
    }


def _get_sample_content() -> str:
    """Get sample content for dry run."""
    return """🤔 Bạn có biết ánh sáng đỏ có thể giúp giảm đau mạn tính?

Nghiên cứu mới cho thấy liệu pháp photobiomodulation (ánh sáng đỏ) giúp giảm đáng kể các triệu chứng đau cơ xương khớp.

Cụ thể:
✅ Hiệu quả giảm đau được chứng minh lâm sàng
✅ Không tác dụng phụ đáng kể
✅ Phù hợp với nhiều đối tượng

Tại Kajo, chúng mình đã đầu tư thiết bị red light therapy hiện đại để mang đến giải pháp phục hồi tối ưu cho bạn 🌟

💬 Bạn đã từng nghe về liệu pháp ánh sáng đỏ chưa? Chia sẻ cùng mình nha!"""


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 3: Content Generation")
    parser.add_argument("--dry-run", action="store_true", help="Run without actual API calls or posting")
    parser.add_argument("--show-state", action="store_true", help="Show current state and exit")
    args = parser.parse_args()

    if args.show_state:
        state = sm.load_state()
        print(json.dumps(state, indent=2, ensure_ascii=False))
        sys.exit(0)

    print("="*60)
    print("Stage 3: Content Generation")
    print("="*60)
    print()

    result = run_stage_3(dry_run=args.dry_run)

    print()
    print("="*60)
    print("Results:")
    print(f"  Success: {result['success']}")
    print(f"  Source: {result['source_title']}")
    print(f"  Word count: {result['word_count']}")
    print(f"  Tokens: {result['tokens_in']} in / {result['tokens_out']} out")
    print(f"  Cost: ${result['cost']:.4f}")
    print(f"  Access: {result['access_type']}")
    if result['error']:
        print(f"  Error: {result['error']}")
    if result['thread_id']:
        print(f"  Thread ID: {result['thread_id']}")
    print("="*60)

    sys.exit(0 if result['success'] else 1)
