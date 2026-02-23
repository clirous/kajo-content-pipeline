#!/usr/bin/env python3
"""Apify API wrapper for Instagram and Facebook scraping."""

import os
import json
from typing import List, Optional, Dict, Any
from pathlib import Path

# Load config
SKILL_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = SKILL_DIR / "assets" / "config.json"


def _load_config() -> dict:
    """Load configuration from config.json."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_token(config: Optional[dict] = None) -> str:
    """Get Apify token from config or environment."""
    if config is None:
        config = _load_config()

    token_ref = config.get("apify", {}).get("token", "")

    # Handle ENV: prefix
    if token_ref.startswith("ENV:"):
        env_var = token_ref[4:]
        return os.environ.get(env_var, "")

    return token_ref


def _init_client():
    """Initialize Apify client. Returns None if not installed or misconfigured."""
    try:
        from apify_client import ApifyClient

        token = _get_token()
        if not token:
            print("Warning: APIFY_TOKEN not configured. Set environment variable.")
            return None

        return ApifyClient(token)

    except ImportError:
        print("Warning: apify-client not installed. Run: pip install apify-client")
        return None


def scrape_instagram(
    keywords: List[str],
    max_results: int = 100,
    config: Optional[dict] = None
) -> List[dict]:
    """Scrape Instagram posts matching keywords.

    Args:
        keywords: Search keywords
        max_results: Maximum results to return
        config: Optional config override

    Returns:
        List of post dictionaries with engagement data
    """
    if config is None:
        config = _load_config()

    client = _init_client()
    if client is None:
        return []

    actor_id = config.get("apify", {}).get("actors", {}).get(
        "instagram", "apify/instagram-search-scraper"
    )

    # Build search queries from keywords
    search_queries = keywords[:5]  # Limit to 5 queries per run

    try:
        run = client.actor(actor_id).call(
            run_input={
                "searchQueries": search_queries,
                "resultsLimit": max_results,
                "proxyConfiguration": config.get("apify", {}).get("proxy", {"useApifyProxy": True})
            }
        )

        posts = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            posts.append(_normalize_instagram_post(item))

        return posts

    except ConnectionError as e:
        print(f"Instagram scraping connection error: {e}")
        return []
    except TimeoutError as e:
        print(f"Instagram scraping timeout: {e}")
        return []
    except ValueError as e:
        print(f"Instagram scraping invalid response: {e}")
        return []
    except Exception as e:
        print(f"Instagram scraping failed unexpectedly: {type(e).__name__}: {e}")
        return []


def scrape_facebook(
    keywords: List[str],
    max_results: int = 100,
    config: Optional[dict] = None
) -> List[dict]:
    """Scrape Facebook posts matching keywords.

    Args:
        keywords: Search keywords
        max_results: Maximum results to return
        config: Optional config override

    Returns:
        List of post dictionaries with engagement data
    """
    if config is None:
        config = _load_config()

    client = _init_client()
    if client is None:
        return []

    actor_id = config.get("apify", {}).get("actors", {}).get(
        "facebook", "apify/facebook-posts-scraper"
    )

    try:
        # Facebook scraper uses different input format
        run = client.actor(actor_id).call(
            run_input={
                "searchQueries": [{"searchQuery": kw} for kw in keywords[:5]],
                "resultsLimit": max_results,
                "proxyConfiguration": config.get("apify", {}).get("proxy", {"useApifyProxy": True})
            }
        )

        posts = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            posts.append(_normalize_facebook_post(item))

        return posts

    except ConnectionError as e:
        print(f"Facebook scraping connection error: {e}")
        return []
    except TimeoutError as e:
        print(f"Facebook scraping timeout: {e}")
        return []
    except ValueError as e:
        print(f"Facebook scraping invalid response: {e}")
        return []
    except Exception as e:
        print(f"Facebook scraping failed unexpectedly: {type(e).__name__}: {e}")
        return []


def _normalize_instagram_post(raw: dict) -> dict:
    """Normalize Instagram post to standard format."""
    return {
        "platform": "instagram",
        "url": raw.get("url", ""),
        "caption": raw.get("caption", ""),
        "likes": raw.get("likesCount", 0) or 0,
        "comments": raw.get("commentsCount", 0) or 0,
        "shares": 0,  # Instagram doesn't show shares publicly
        "timestamp": raw.get("timestamp", ""),
        "author": raw.get("ownerUsername", ""),
        "media_type": raw.get("type", "image"),
        "hashtags": raw.get("hashtags", []),
        "raw": raw
    }


def _normalize_facebook_post(raw: dict) -> dict:
    """Normalize Facebook post to standard format."""
    return {
        "platform": "facebook",
        "url": raw.get("postUrl", raw.get("url", "")),
        "caption": raw.get("text", raw.get("message", "")),
        "likes": raw.get("likesCount", raw.get("reactions", 0)) or 0,
        "comments": raw.get("commentsCount", 0) or 0,
        "shares": raw.get("sharesCount", 0) or 0,
        "timestamp": raw.get("time", raw.get("timestamp", "")),
        "author": raw.get("username", raw.get("from", {}).get("name", "")),
        "media_type": "post",
        "hashtags": [],  # Extract from text if needed
        "raw": raw
    }


def filter_by_engagement(
    posts: List[dict],
    threshold: int = 500,
    engagement_rate_min: float = 0.0
) -> List[dict]:
    """Filter posts by engagement threshold.

    Args:
        posts: List of normalized posts
        threshold: Minimum total engagement (likes + comments + shares)
        engagement_rate_min: Minimum engagement rate (if followers known)

    Returns:
        Filtered list of posts meeting criteria
    """
    filtered = []

    for post in posts:
        total_engagement = (
            post.get("likes", 0) +
            post.get("comments", 0) +
            post.get("shares", 0)
        )

        if total_engagement >= threshold:
            filtered.append(post)

    # Sort by engagement descending
    filtered.sort(
        key=lambda p: p.get("likes", 0) + p.get("comments", 0) + p.get("shares", 0),
        reverse=True
    )

    return filtered


def get_top_posts(posts: List[dict], limit: int = 10) -> List[dict]:
    """Get top N posts by engagement.

    Args:
        posts: List of normalized posts
        limit: Maximum posts to return

    Returns:
        Top posts sorted by engagement
    """
    sorted_posts = sorted(
        posts,
        key=lambda p: p.get("likes", 0) + p.get("comments", 0) + p.get("shares", 0),
        reverse=True
    )
    return sorted_posts[:limit]


def estimate_cost(posts_count: int, platform: str = "mixed") -> float:
    """Estimate Apify cost for scraping.

    Args:
        posts_count: Number of posts scraped
        platform: Platform scraped

    Returns:
        Estimated cost in USD
    """
    # Rough estimates based on Apify pricing
    cost_per_post = {
        "instagram": 0.002,  # ~$2 per 1000 posts
        "facebook": 0.003,  # ~$3 per 1000 posts
        "mixed": 0.0025
    }

    rate = cost_per_post.get(platform, 0.0025)
    return posts_count * rate


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: apify_client.py <command> [args]")
        print("Commands: scrape-ig, scrape-fb, test")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "scrape-ig":
        config = _load_config()
        keywords = config.get("keywords", {}).get("en", ["wellness"])
        posts = scrape_instagram(keywords, max_results=10)
        print(f"Found {len(posts)} Instagram posts")
        for p in posts[:3]:
            print(f"  - {p['likes']} likes: {p['caption'][:50]}...")

    elif cmd == "scrape-fb":
        config = _load_config()
        keywords = config.get("keywords", {}).get("en", ["wellness"])
        posts = scrape_facebook(keywords, max_results=10)
        print(f"Found {len(posts)} Facebook posts")
        for p in posts[:3]:
            print(f"  - {p['likes']} likes: {p['caption'][:50]}...")

    elif cmd == "test":
        print("Testing Apify client...")
        token = _get_token()
        if token:
            print(f"Token found: {token[:10]}...")
            client = _init_client()
            print(f"Client initialized: {client is not None}")
        else:
            print("No token found. Set APIFY_TOKEN environment variable.")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
