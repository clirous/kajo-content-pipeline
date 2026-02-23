#!/usr/bin/env python3
"""Stage 2: Pattern Analysis - Extract viral content patterns using GLM-5."""

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
from glm5_client import (
    call_glm5, build_generation_prompt
)
from discord_fmt import format_patterns, format_report_card


def build_analysis_prompt(posts: list) -> tuple:
    """Build pattern analysis prompt for viral posts using GLM-5.

    Args:
        posts: List of scraped post dictionaries

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # Format posts for analysis
    posts_text = ""
    for i, post in enumerate(posts[:20], 1):
        platform = post.get("platform", "unknown")
        caption = post.get("caption", "")[:500]
        likes = post.get("likes", 0)
        comments = post.get("comments", 0)
        shares = post.get("shares", 0)
        total_engagement = likes + comments + shares

        posts_text += f"""
---
POST {i} [{platform}] - {total_engagement:,} total engagement
Likes: {likes:,} | Comments: {comments:,} | Shares: {shares:,}
Caption:
{caption}
"""

    system_prompt = """You are a viral content pattern analyst specializing in Vietnamese wellness/health content.

Analyze the provided posts and extract engagement patterns.

Output ONLY valid JSON (no markdown, no extra text) with this exact schema:
{
  "hooks": [
    {"name": "Hook Type Name", "template": "Pattern template", "example": "Actual example from posts", "frequency": N}
  ],
  "structures": [
    {"type": "Structure type", "sections": ["section1", "section2"], "avg_length": N, "percentage": N}
  ],
  "tone": {
    "formality": "casual/formal/mixed",
    "emotions": ["emotion1", "emotion2"],
    "expressions": ["Vietnamese expression 1", "expression 2"]
  },
  "ctas": [
    {"type": "CTA type", "template": "CTA template", "placement": "end/middle"}
  ]
}

Focus on:
1. HOOK FORMULAS - Opening patterns (question, stat, story, problem, contrast)
2. STRUCTURE TEMPLATES - Post organization (listicle, story, Q&A, before/after)
3. TONE MARKERS - Vietnamese language patterns and emotional style
4. CTA PATTERNS - How posts drive engagement (save, share, comment)"""

    user_prompt = f"""Analyze these {len(posts[:20])} viral posts and extract patterns:

{posts_text}

Extract the patterns and output JSON now:"""

    return system_prompt, user_prompt


def extract_json_from_response(text: str) -> Optional[dict]:
    """Extract JSON from GLM-5 response text."""
    if not text:
        return None

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    import re
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(code_block_pattern, text)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try finding balanced JSON object
    depth = 0
    start_idx = None
    for i, char in enumerate(text):
        if char == '{':
            if depth == 0:
                start_idx = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start_idx is not None:
                try:
                    return json.loads(text[start_idx:i+1])
                except json.JSONDecodeError:
                    start_idx = None
                    continue

    return None


def run_stage_2(dry_run: bool = False) -> Dict[str, Any]:
    """Execute Stage 2: Pattern Analysis.

    Args:
        dry_run: If True, skip actual GLM-5 call and Discord posting

    Returns:
        Result dictionary with status, patterns, and metrics
    """
    result = {
        "success": False,
        "patterns": {},
        "posts_analyzed": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "cost": 0.0,
        "thread_id": None,
        "error": None
    }

    # Load configuration
    config = _load_config()

    # Check if at Stage 2
    current_stage = sm.get_current_stage()
    if current_stage != 2:
        result["error"] = f"Expected stage 2, currently at stage {current_stage}"
        sm.set_status("failed")
        return result

    # Check budget before starting
    if not sm.check_budget("glm5", config):
        result["error"] = "Daily GLM-5 budget exceeded"
        _post_error_to_discord(config, "Budget exceeded", dry_run)
        return result

    # Set status to in_progress
    sm.set_status("in_progress")

    # Get Stage 1 data (scraped posts)
    scraped_posts = sm.get_data(1)
    if not scraped_posts:
        result["error"] = "No scraped posts found from Stage 1"
        sm.set_status("failed")
        return result

    result["posts_analyzed"] = len(scraped_posts)
    print(f"Analyzing {len(scraped_posts)} viral posts...")

    # Build analysis prompt
    system_prompt, user_prompt = build_analysis_prompt(scraped_posts)

    # Call GLM-5 for pattern analysis
    if not dry_run:
        print("Calling GLM-5 API for pattern analysis...")
        response_text, meta = call_glm5(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config,
            temperature=0.3,  # Lower temperature for factual extraction
            max_tokens=4096
        )

        if meta.get("error"):
            result["error"] = f"GLM-5 API error: {meta['error']}"
            sm.set_status("failed")
            _post_error_to_discord(config, meta["error"], dry_run)
            return result

        result["tokens_in"] = meta.get("tokens_in", 0)
        result["tokens_out"] = meta.get("tokens_out", 0)
        result["cost"] = meta.get("cost", 0.0)

        # Extract patterns from response
        patterns = extract_json_from_response(response_text)
        if not patterns:
            print("Warning: Could not parse JSON, attempting fallback extraction")
            patterns = _fallback_extract_patterns(response_text)

        result["patterns"] = patterns
        print(f"Extracted patterns: {list(patterns.keys())}")

        # Record cost
        sm.record_cost("glm5", result["cost"])
    else:
        print("[DRY RUN] Would call GLM-5 API")
        # Use sample patterns for dry run
        result["patterns"] = _get_sample_patterns()

    # Save patterns to state
    sm.add_data(2, result["patterns"])

    # Update viral-patterns.md
    if not dry_run:
        _update_patterns_file(result["patterns"], result["posts_analyzed"])
        print("Updated viral-patterns.md")

    # Format Discord message
    discord_msg = format_patterns(result["patterns"])

    # Add report card
    report_card = format_report_card(
        stage=2,
        model="glm-5",
        tokens_in=result["tokens_in"],
        tokens_out=result["tokens_out"],
        cost=result["cost"],
        status="awaiting approval"
    )

    # Add admin tag
    admin_id = config.get("discord", {}).get("admin_user_id", "")
    admin_tag = f"\n\n<@{admin_id}> — Approve to proceed to Content Generation" if admin_id else ""

    full_message = f"{discord_msg}\n\n{report_card}{admin_tag}"

    # Post to Discord
    discord_success = True
    if not dry_run:
        thread_id = _post_to_discord(config, full_message)
        if thread_id:
            result["thread_id"] = thread_id
            sm.set_thread_id(2, thread_id)
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
        result["error"] = "Discord posting failed - patterns saved to state"

    return result


def _load_config() -> dict:
    """Load configuration from config.json."""
    config_file = SKILL_DIR / "assets" / "config.json"
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


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

    today = datetime.now().strftime("%Y-%m-%d")
    thread_title = f"Pattern Analysis — {today}"

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
            # Currently returning placeholder; real ID needed for thread tracking
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
    message = f"""## ❌ Stage 2 Error — {today}

**Error:** {error_msg}

Pipeline halted. Manual intervention required.

---"""

    _post_to_discord(config, message)


def _update_patterns_file(patterns: dict, posts_count: int) -> None:
    """Update viral-patterns.md with new patterns.

    Args:
        patterns: Extracted patterns dictionary
        posts_count: Number of posts analyzed
    """
    patterns_file = SKILL_DIR / "references" / "viral-patterns.md"
    patterns_file.parent.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")

    # Read existing content
    existing = ""
    if patterns_file.exists():
        with open(patterns_file, "r", encoding="utf-8") as f:
            existing = f.read()

    # Build new section
    new_section = f"""
## Analysis: {today}

*Analyzed {posts_count} viral posts*

"""

    # Add hooks
    hooks = patterns.get("hooks", [])
    if hooks:
        new_section += "### Hooks Found\n\n"
        for hook in hooks[:5]:
            name = hook.get("name", "Unknown")
            template = hook.get("template", "")
            freq = hook.get("frequency", 0)
            new_section += f"- **{name}** ({freq}x): `{template}`\n"
        new_section += "\n"

    # Add structures
    structures = patterns.get("structures", [])
    if structures:
        new_section += "### Structures Found\n\n"
        for struct in structures[:3]:
            stype = struct.get("type", "Unknown")
            pct = struct.get("percentage", 0)
            new_section += f"- **{stype}** ({pct}%)\n"
        new_section += "\n"

    # Add tone
    tone = patterns.get("tone", {})
    if tone:
        formality = tone.get("formality", "unknown")
        emotions = tone.get("emotions", [])
        new_section += f"### Tone: {formality}\n\n"
        if emotions:
            new_section += f"Emotions: {', '.join(emotions[:5])}\n\n"

    # Add CTAs
    ctas = patterns.get("ctas", [])
    if ctas:
        new_section += "### CTAs Found\n\n"
        for cta in ctas[:3]:
            ctype = cta.get("type", "Unknown")
            template = cta.get("template", "")
            new_section += f"- **{ctype}**: `{template}`\n"
        new_section += "\n"

    # Update "Last updated" line
    if "Last updated:" in existing:
        existing = existing.replace(
            existing[existing.find("Last updated:"):].split("\n")[0],
            f"Last updated: {today}"
        )
    else:
        new_section += "---\n\n*Last updated: {today}*\n"

    # Append to file
    with open(patterns_file, "w", encoding="utf-8") as f:
        f.write(existing + new_section)


def _fallback_extract_patterns(text: str) -> dict:
    """Fallback pattern extraction when JSON parsing fails.

    Uses regex to extract key patterns from unstructured text.

    Args:
        text: Raw response text

    Returns:
        Basic patterns dict extracted via regex
    """
    import re

    patterns = {
        "hooks": [],
        "structures": [],
        "tone": {"formality": "unknown", "emotions": [], "expressions": []},
        "ctas": []
    }

    if not text:
        return patterns

    # Extract hooks - look for quoted patterns or "Hook:" prefixes
    hook_patterns = re.findall(r'(?:hook|hook formula)[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
    for i, hook in enumerate(hook_patterns[:5]):
        patterns["hooks"].append({
            "name": f"Hook {i+1}",
            "template": hook,
            "frequency": 1
        })

    # Extract structure types
    structure_types = re.findall(r'(listicle|story|q&a|before.after)', text, re.IGNORECASE)
    for stype in set(structure_types[:3]):
        patterns["structures"].append({
            "type": stype.lower(),
            "sections": [],
            "percentage": 0
        })

    # Extract CTAs
    cta_patterns = re.findall(r'(?:cta|call.to.action)[:\s]+["\']([^"\']+)["\']', text, re.IGNORECASE)
    for i, cta in enumerate(cta_patterns[:3]):
        patterns["ctas"].append({
            "type": f"CTA {i+1}",
            "template": cta,
            "placement": "end"
        })

    # Default tone if nothing found
    if not patterns["tone"]["formality"] or patterns["tone"]["formality"] == "unknown":
        if any(w in text.lower() for w in ["casual", "thân thiện", "bạn", "mình"]):
            patterns["tone"]["formality"] = "casual"
        elif any(w in text.lower() for w in ["formal", "chuyên nghiệp"]):
            patterns["tone"]["formality"] = "formal"
        else:
            patterns["tone"]["formality"] = "mixed"

    return patterns


def _get_sample_patterns() -> dict:
    """Get sample patterns for dry run."""
    return {
        "hooks": [
            {"name": "Question Hook", "template": "Bạn có biết {fact}?", "frequency": 5},
            {"name": "Statistic Hook", "template": "{num}% người Việt {action}", "frequency": 3}
        ],
        "structures": [
            {"type": "listicle", "sections": ["hook", "items", "cta"], "percentage": 40},
            {"type": "story", "sections": ["problem", "solution", "result"], "percentage": 30}
        ],
        "tone": {
            "formality": "casual-warm",
            "emotions": ["curiosity", "hope"],
            "expressions": ["bạn", "mình", "nha"]
        },
        "ctas": [
            {"type": "save", "template": "Lưu lại để đọc sau nha!", "placement": "end"},
            {"type": "share", "template": "Tag người cần biết điều này", "placement": "end"}
        ]
    }


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stage 2: Pattern Analysis")
    parser.add_argument("--dry-run", action="store_true", help="Run without actual API calls or posting")
    parser.add_argument("--show-state", action="store_true", help="Show current state and exit")
    args = parser.parse_args()

    if args.show_state:
        state = sm.load_state()
        print(json.dumps(state, indent=2, ensure_ascii=False))
        sys.exit(0)

    print("="*60)
    print("Stage 2: Pattern Analysis")
    print("="*60)
    print()

    result = run_stage_2(dry_run=args.dry_run)

    print()
    print("="*60)
    print("Results:")
    print(f"  Success: {result['success']}")
    print(f"  Posts analyzed: {result['posts_analyzed']}")
    print(f"  Tokens: {result['tokens_in']} in / {result['tokens_out']} out")
    print(f"  Cost: ${result['cost']:.4f}")
    if result['error']:
        print(f"  Error: {result['error']}")
    if result['thread_id']:
        print(f"  Thread ID: {result['thread_id']}")
    print("="*60)

    sys.exit(0 if result['success'] else 1)
