#!/usr/bin/env python3
"""Gemini API client for pattern analysis."""

import os
import json
import re
import time
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import requests

# Constants
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds (exponential backoff)

# Load config
SKILL_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = SKILL_DIR / "assets" / "config.json"


def _load_config() -> dict:
    """Load configuration from config.json."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_api_key(config: Optional[dict] = None) -> str:
    """Get Gemini API key from config or environment."""
    if config is None:
        config = _load_config()

    key_ref = config.get("models", {}).get("gemini_api_key", "")

    # Handle ENV: prefix
    if key_ref.startswith("ENV:"):
        env_var = key_ref[4:]
        return os.environ.get(env_var, "")

    return key_ref


def call_gemini(
    prompt: str,
    model: Optional[str] = None,
    config: Optional[dict] = None,
    temperature: float = 0.3,
    max_output_tokens: int = 4096
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Call Gemini API to generate content.

    Args:
        prompt: The full prompt (system + user content)
        model: Model ID (default from config)
        config: Optional config override
        temperature: Sampling temperature
        max_output_tokens: Maximum output tokens

    Returns:
        Tuple of (response_text, metadata) where metadata includes:
        - tokens_in: Input token count
        - tokens_out: Output token count
        - cost: Estimated cost in USD
        - model: Model used
        - error: Error message if failed
    """
    metadata = {
        "tokens_in": 0,
        "tokens_out": 0,
        "cost": 0.0,
        "model": model or "unknown",
        "error": None
    }

    if config is None:
        config = _load_config()

    api_key = _get_api_key(config)
    if not api_key:
        metadata["error"] = "GEMINI_API_KEY not configured"
        return None, metadata

    model_id = model or config.get("models", {}).get("analysis", "gemini-2.5-flash")
    metadata["model"] = model_id

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent"

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_output_tokens
                    }
                },
                timeout=60
            )

            # Retry on server errors (5xx)
            if response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                print(f"Server error {response.status_code}, retrying in {delay}s...")
                time.sleep(delay)
                continue

            if response.status_code != 200:
                metadata["error"] = f"API error {response.status_code}: {response.text[:200]}"
                return None, metadata

            data = response.json()

            # Extract text from response
            candidates = data.get("candidates", [])
            if not candidates:
                metadata["error"] = "No candidates in response"
                return None, metadata

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                metadata["error"] = "No parts in candidate"
                return None, metadata

            text = parts[0].get("text", "")

            # Extract token usage from metadata
            usage_meta = data.get("usageMetadata", {})
            metadata["tokens_in"] = usage_meta.get("promptTokenCount", 0)
            metadata["tokens_out"] = usage_meta.get("candidatesTokenCount", 0)

            # Estimate cost (Gemini 2.5 Flash pricing)
            # Input: ~$0.000075/1K tokens, Output: ~$0.0003/1K tokens
            # TODO: Make pricing configurable when adding other Gemini models
            GEMINI_FLASH_INPUT_COST = 0.000075  # $/1K tokens
            GEMINI_FLASH_OUTPUT_COST = 0.0003   # $/1K tokens
            cost_in = (metadata["tokens_in"] / 1000) * GEMINI_FLASH_INPUT_COST
            cost_out = (metadata["tokens_out"] / 1000) * GEMINI_FLASH_OUTPUT_COST
            metadata["cost"] = cost_in + cost_out

            return text, metadata

        except requests.Timeout:
            last_error = "API request timed out"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                print(f"Timeout, retrying in {delay}s...")
                time.sleep(delay)
                continue
        except requests.ConnectionError as e:
            last_error = f"Connection error: {e}"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                print(f"Connection error, retrying in {delay}s...")
                time.sleep(delay)
                continue
        except (json.JSONDecodeError, KeyError) as e:
            metadata["error"] = f"Response parse error: {e}"
            return None, metadata
        except Exception as e:
            last_error = f"Unexpected error: {type(e).__name__}: {e}"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                print(f"Unexpected error, retrying in {delay}s...")
                time.sleep(delay)
                continue

    # All retries exhausted
    metadata["error"] = last_error or "All retries exhausted"
    return None, metadata


def extract_json_from_response(text: str) -> Optional[dict]:
    """Extract JSON from Gemini response text.

    Gemini may wrap JSON in markdown code blocks or add text before/after.
    This function extracts the JSON object.

    Args:
        text: Raw response text

    Returns:
        Parsed JSON dict or None if parsing fails
    """
    if not text:
        return None

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code block
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(code_block_pattern, text)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try finding balanced JSON object (non-greedy)
    # Look for JSON starting with { and ending with }
    # Use a more specific pattern that matches balanced braces
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
                # Found balanced JSON object
                try:
                    return json.loads(text[start_idx:i+1])
                except json.JSONDecodeError:
                    start_idx = None
                    continue

    return None


def build_analysis_prompt(posts: list) -> str:
    """Build pattern analysis prompt for viral posts.

    Args:
        posts: List of scraped post dictionaries

    Returns:
        Full prompt string for Gemini
    """
    # Filter out posts with empty captions (waste tokens)
    valid_posts = [
        p for p in posts
        if p.get("caption", "").strip()
    ]

    # Log if filtering occurs
    if len(valid_posts) < len(posts):
        print(f"Filtered {len(posts) - len(valid_posts)} posts with empty captions")

    # Cap at 20 posts for token efficiency
    MAX_POSTS = 20
    if len(valid_posts) > MAX_POSTS:
        print(f"Capping analysis at {MAX_POSTS} posts (from {len(valid_posts)})")
        valid_posts = valid_posts[:MAX_POSTS]

    if not valid_posts:
        # Return minimal prompt if no valid posts
        return """You are a viral content pattern analyst.
No valid posts to analyze. Return empty JSON: {"hooks": [], "structures": [], "tone": {}, "ctas": []}"""

    # Format posts for analysis
    posts_text = ""
    for i, post in enumerate(valid_posts, 1):
        platform = post.get("platform", "unknown")
        caption = post.get("caption", "")[:500]  # Truncate long captions
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

    prompt = f"""You are a viral content pattern analyst specializing in Vietnamese wellness/health content.

Analyze these {len(valid_posts)} viral posts and extract engagement patterns.

Output ONLY valid JSON (no markdown, no extra text) with this exact schema:
{{
  "hooks": [
    {{"name": "Hook Type Name", "template": "Pattern template with {{placeholder}}", "example": "Actual example from posts", "frequency": N}}
  ],
  "structures": [
    {{"type": "Structure type", "sections": ["section1", "section2"], "avg_length": N, "percentage": N}}
  ],
  "tone": {{
    "formality": "casual/formal/mixed",
    "emotions": ["emotion1", "emotion2"],
    "expressions": ["Vietnamese expression 1", "expression 2"]
  }},
  "ctas": [
    {{"type": "CTA type", "template": "CTA template", "placement": "end/middle"}}
  ]
}}

Posts to analyze:
{posts_text}

Extract patterns focusing on:
1. HOOK FORMULAS - Opening patterns that grab attention (question, stat, story, problem, contrast)
2. STRUCTURE TEMPLATES - How posts are organized (listicle, story, Q&A, before/after)
3. TONE MARKERS - Vietnamese language patterns and emotional style
4. CTA PATTERNS - How posts drive engagement (save, share, comment)

Output JSON now:"""

    return prompt


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: gemini_client.py <command> [args]")
        print("Commands: test, analyze <json_file>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "test":
        print("Testing Gemini client...")
        api_key = _get_api_key()
        if api_key:
            print(f"API key found: {api_key[:10]}...")
            # Simple test call
            text, meta = call_gemini("Say 'hello' in Vietnamese.")
            if text:
                print(f"Response: {text}")
                print(f"Tokens: {meta['tokens_in']} in / {meta['tokens_out']} out")
                print(f"Cost: ${meta['cost']:.6f}")
            else:
                print(f"Error: {meta['error']}")
        else:
            print("No API key found. Set GEMINI_API_KEY environment variable.")

    elif cmd == "analyze" and len(sys.argv) > 2:
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            posts = json.load(f)

        prompt = build_analysis_prompt(posts)
        print(f"Prompt length: {len(prompt)} chars")
        print("Calling Gemini...")

        text, meta = call_gemini(prompt)
        if text:
            print(f"\nResponse:\n{text[:500]}...")
            print(f"\nTokens: {meta['tokens_in']} in / {meta['tokens_out']} out")
            print(f"Cost: ${meta['cost']:.6f}")

            patterns = extract_json_from_response(text)
            if patterns:
                print("\nParsed patterns:")
                print(json.dumps(patterns, indent=2, ensure_ascii=False)[:1000])
            else:
                print("\nFailed to parse JSON from response")
        else:
            print(f"Error: {meta['error']}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
