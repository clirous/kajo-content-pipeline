#!/usr/bin/env python3
"""Discord formatting utilities for content pipeline reports."""

from typing import List, Optional


def format_report_card(
    stage: int,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost: float,
    status: str = "completed"
) -> str:
    """Format pipeline stage report card for Discord.

    Args:
        stage: Pipeline stage number (1-4)
        model: Model used for this stage
        tokens_in: Input tokens consumed
        tokens_out: Output tokens generated
        cost: Cost in USD
        status: Stage status (completed, failed, pending)

    Returns:
        Formatted Discord message string
    """
    # Defensive: ensure valid types
    stage = max(1, min(4, int(stage) if stage else 1))
    model = model or "unknown"
    tokens_in = max(0, int(tokens_in) if tokens_in else 0)
    tokens_out = max(0, int(tokens_out) if tokens_out else 0)
    cost = max(0.0, float(cost) if cost else 0.0)
    status = status or "pending"

    stage_names = {
        1: "Viral Scraping",
        2: "Pattern Analysis",
        3: "Content Generation",
        4: "Distribution"
    }

    status_emoji = {
        "completed": "✅",
        "failed": "❌",
        "pending": "⏳",
        "in_progress": "🔄"
    }

    stage_name = stage_names.get(stage, f"Stage {stage}")
    emoji = status_emoji.get(status, "❓")

    return f"""## {emoji} Stage {stage}: {stage_name}

**Model:** {model}
**Tokens:** {tokens_in:,} in → {tokens_out:,} out
**Cost:** ${cost:.4f}
**Status:** {status}

---
*Reply with `✅` to approve and advance to Stage {stage + 1 if stage < 4 else 'Complete'}*"""


def format_source_card(
    title: str,
    quote: str,
    url: str,
    page: Optional[int] = None
) -> str:
    """Format Vietnamese source citation card for Discord.

    Args:
        title: Paper/article title
        quote: Relevant quote or finding
        url: Source URL
        page: Optional page number

    Returns:
        Formatted Discord embed-style source card
    """
    # Defensive: handle None/empty inputs
    title = title or "Untitled Source"
    quote = quote or "No quote available"
    url = url or "#"

    page_str = f" (trang {page})" if page else ""

    return f"""### 📄 Nguồn: {title}

> {quote}

🔗 **Link:** {url}
📖 **Vị trí:** Báo cáo nghiên cứu{page_str}

---
*Source verified for content accuracy*"""


def format_scraped_results(
    posts: List[dict],
    total_found: int,
    filtered_count: int,
    platform: str = "mixed"
) -> str:
    """Summarize scraping results for Discord.

    Args:
        posts: List of scraped post data
        total_found: Total posts found before filtering
        filtered_count: Posts passing engagement threshold
        platform: Platform scraped (instagram, facebook, mixed)

    Returns:
        Formatted Discord summary message
    """
    platform_emoji = {
        "instagram": "📸",
        "facebook": "📘",
        "mixed": "📱"
    }
    emoji = platform_emoji.get(platform, "📱")

    # Calculate engagement stats
    if posts:
        avg_likes = sum(p.get("likes", 0) for p in posts) / len(posts)
        avg_comments = sum(p.get("comments", 0) for p in posts) / len(posts)
        top_post = max(posts, key=lambda p: p.get("likes", 0) + p.get("comments", 0))
    else:
        avg_likes = avg_comments = 0
        top_post = {}

    top_engagement = top_post.get("likes", 0) + top_post.get("comments", 0)

    return f"""## {emoji} Stage 1: Kết Quả Cào Dữ Liệu

**Nền tảng:** {platform.title()}
**Tổng tìm thấy:** {total_found:,}
**Đạt ngưỡng viral (500+):** {filtered_count}

### Thống Kê
- **TB lượt thích:** {avg_likes:,.0f}
- **TB bình luận:** {avg_comments:,.0f}
- **Top bài:** {top_engagement:,} tương tác

### Top {min(len(posts), 5)} Bài Viral
{_format_top_posts(posts[:5])}

---
*Reply `✅` để tiếp tục Stage 2: Phân Tích Pattern*"""


def _format_top_posts(posts: List[dict]) -> str:
    """Format top posts list."""
    if not posts:
        return "_(No posts to display)_"

    lines = []
    for i, post in enumerate(posts, 1):
        engagement = post.get("likes", 0) + post.get("comments", 0) + post.get("shares", 0)
        platform = post.get("platform", "unknown")
        url = post.get("url", "")
        lines.append(f"{i}. **{engagement:,}** tương tác [{platform}] {url[:50]}...")

    return "\n".join(lines)


def format_patterns(patterns: dict) -> str:
    """Summarize pattern analysis results for Discord.

    Args:
        patterns: Extracted patterns dictionary

    Returns:
        Formatted Discord pattern summary
    """
    hooks = patterns.get("hooks", [])
    structures = patterns.get("structures", [])
    tones = patterns.get("tones", [])
    ctas = patterns.get("ctas", [])

    return f"""## 🔍 Stage 2: Phân Tích Pattern

### 🎣 Hooks Hiệu Quả
{_format_list(hooks[:5], "hook")}

### 📐 Cấu Trúc Bài Viết
{_format_list(structures[:3], "structure")}

### 🎯 Tone & Giọng Văn
{_format_list(tones[:3], "tone")}

### 📢 Call-to-Action
{_format_list(ctas[:3], "cta")}

---
*Patterns đã được cập nhật vào references/viral-patterns.md*
*Reply `✅` để tiếp tục Stage 3: Tạo Nội Dung*"""


def _format_list(items: List[str], item_type: str) -> str:
    """Format a list of items for Discord."""
    if not items:
        return "_(Chưa có dữ liệu)_"
    return "\n".join(f"- {item}" for item in items)


def format_generated_content(
    content: str,
    source_title: str,
    source_url: str,
    word_count: int
) -> str:
    """Format generated content for Discord review.

    Args:
        content: Generated Vietnamese content
        source_title: Title of source paper
        source_url: URL to source paper
        word_count: Word count of content

    Returns:
        Formatted Discord content preview
    """
    # Truncate for Discord preview (max 2000 chars)
    preview = content[:1500] + "..." if len(content) > 1500 else content

    return f"""## ✍️ Stage 3: Nội Dung Đã Tạo

### Preview
{preview}

---
**📊 Thống kê:** {word_count} từ
**📄 Nguồn:** [{source_title}]({source_url})

---
*Reply `✅` để đăng lên Google Sheets*
*Reply `✏️` để chỉnh sửa*
*Reply `❌` để từ chối*"""


def format_distribution_confirm(
    sheet_url: str,
    content_preview: str
) -> str:
    """Format distribution confirmation for Discord.

    Args:
        sheet_url: URL to published content sheet
        content_preview: Short preview of published content

    Returns:
        Formatted Discord confirmation
    """
    return f"""## ✅ Stage 4: Đã Phân Phối

**Nội dung đã được đăng lên Google Sheets**

📋 **Sheet:** [Published Content]({sheet_url})

### Preview
{content_preview[:500]}...

---
🎉 **Pipeline hoàn thành!**
*Sẵn sàng cho ngày mai lúc 8:00 AM VN*"""
