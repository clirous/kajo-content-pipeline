#!/usr/bin/env python3
"""Paper fetching and content extraction for research papers."""

import re
import json
import tempfile
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import requests

# Academic headers to avoid bot detection
ACADEMIC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Load config
SKILL_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = SKILL_DIR / "assets" / "config.json"


def _load_config() -> dict:
    """Load configuration from config.json."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_paper(url: str, timeout: int = 30) -> Tuple[Optional[Dict[str, Any]], str]:
    """Fetch and extract paper content from URL.

    Args:
        url: URL to research paper (HTML article or PDF)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (paper_data, access_type) where:
        - paper_data: dict with title, content, quotes, etc.
        - access_type: "full", "abstract_only", or "error"
    """
    result = {
        "url": url,
        "title": "",
        "content": "",
        "abstract": "",
        "quotes": [],
        "page_refs": {},
        "error": None
    }

    try:
        response = requests.get(url, headers=ACADEMIC_HEADERS, timeout=timeout, allow_redirects=True)

        # Check for paywall/access denied
        if response.status_code in (401, 403):
            # Try to extract abstract from meta tags
            abstract = _extract_abstract_from_html(response.text)
            result["abstract"] = abstract
            result["title"] = _extract_title_from_html(response.text)
            result["content"] = abstract
            return result, "abstract_only"

        if response.status_code != 200:
            result["error"] = f"HTTP {response.status_code}"
            return result, "error"

        # Detect content type
        content_type = response.headers.get("content-type", "").lower()

        if "pdf" in content_type or url.lower().endswith(".pdf"):
            # PDF file
            return _extract_pdf_content(response.content, url), "full"
        else:
            # HTML article
            return _extract_html_content(response.text, url), "full"

    except requests.Timeout:
        result["error"] = "Request timed out"
        return result, "error"
    except requests.ConnectionError as e:
        result["error"] = f"Connection error: {e}"
        return result, "error"
    except Exception as e:
        result["error"] = f"Error: {type(e).__name__}: {e}"
        return result, "error"


def _extract_html_content(html: str, url: str) -> Dict[str, Any]:
    """Extract content from HTML article.

    Args:
        html: Raw HTML content
        url: Source URL

    Returns:
        Paper data dictionary
    """
    result = {
        "url": url,
        "title": "",
        "content": "",
        "abstract": "",
        "quotes": [],
        "page_refs": {},
        "error": None
    }

    # Extract title
    result["title"] = _extract_title_from_html(html)

    # Extract abstract
    result["abstract"] = _extract_abstract_from_html(html)

    # Try to extract main content
    # Look for common article content patterns
    content = _extract_article_body(html)

    if content:
        result["content"] = content
        # Extract key quotes with section references
        result["quotes"] = _extract_quotes_from_text(content)
    else:
        # Fallback to abstract
        result["content"] = result["abstract"]

    return result


def _extract_pdf_content(pdf_bytes: bytes, url: str) -> Dict[str, Any]:
    """Extract content from PDF file.

    Args:
        pdf_bytes: Raw PDF bytes
        url: Source URL

    Returns:
        Paper data dictionary
    """
    result = {
        "url": url,
        "title": "",
        "content": "",
        "abstract": "",
        "quotes": [],
        "page_refs": {},
        "error": None
    }

    try:
        import pypdf
    except ImportError:
        result["error"] = "pypdf not installed. Run: pip install pypdf"
        return result

    try:
        # Write to temp file for pypdf
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            temp_path = f.name

        reader = pypdf.PdfReader(temp_path)

        # Extract text from all pages with page numbers
        full_text = ""
        page_texts = {}

        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            page_texts[i] = text
            full_text += f"\n--- Page {i} ---\n{text}"

        result["content"] = full_text.strip()

        # Try to extract title from first page
        if 1 in page_texts:
            first_page = page_texts[1]
            # Title is usually in first few lines
            lines = [l.strip() for l in first_page.split("\n") if l.strip()]
            if lines:
                result["title"] = lines[0][:200]  # First non-empty line, capped

        # Extract abstract (usually in first 1-2 pages)
        first_pages_text = page_texts.get(1, "") + page_texts.get(2, "")
        result["abstract"] = _extract_abstract_from_text(first_pages_text)

        # Extract quotes with page references
        result["quotes"] = _extract_quotes_from_pdf(page_texts)
        result["page_refs"] = page_texts

        # Cleanup temp file
        import os
        os.unlink(temp_path)

    except Exception as e:
        result["error"] = f"PDF extraction error: {type(e).__name__}: {e}"

    return result


def _extract_title_from_html(html: str) -> str:
    """Extract title from HTML."""
    # Try <title> tag
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        # Clean up common suffixes
        title = re.sub(r"\s*[\|\-–]\s*(PDF|Full Text|ResearchGate|PubMed).*", "", title, flags=re.IGNORECASE)
        return title[:200]

    # Try <h1>
    match = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:200]

    # Try meta og:title
    match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:200]

    return "Unknown Title"


def _extract_abstract_from_html(html: str) -> str:
    """Extract abstract from HTML meta tags or content."""
    # Try meta description
    match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try meta citation_abstract
    match = re.search(r'<meta[^>]*name=["\']citation_abstract["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Look for abstract section in content
    match = re.search(r'(?:abstract|summary)[\s:\-]*<\/[^>]+>([^<]{100,2000})', html, re.IGNORECASE)
    if match:
        text = re.sub(r"<[^>]+>", "", match.group(1))
        return text.strip()

    return ""


def _extract_abstract_from_text(text: str) -> str:
    """Extract abstract from plain text."""
    # Look for "Abstract" section
    patterns = [
        r"(?i)abstract[\s\n:]+(.{100,2000}?)(?=\n\n|Keywords|Introduction|1\.|1\s)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

    return ""


def _extract_article_body(html: str) -> str:
    """Extract main article body from HTML."""
    # Remove scripts, styles, nav, footer
    html = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Try to find article content
    patterns = [
        r'<article[^>]*>(.*?)</article>',
        r'<div[^>]*class=["\'][^"\']*article[^"\']*["\'][^>]*>(.*?)</div>',
        r'<div[^>]*class=["\'][^"\']*content[^"\']*["\'][^>]*>(.*?)</div>',
        r'<main[^>]*>(.*?)</main>',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            content_html = match.group(1)
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", content_html)
            # Clean up whitespace
            text = re.sub(r"\s+", " ", text)
            return text.strip()

    return ""


def _extract_quotes_from_text(text: str, max_quotes: int = 5) -> List[Dict[str, str]]:
    """Extract key quotes from text content.

    Args:
        text: Full text content
        max_quotes: Maximum quotes to extract

    Returns:
        List of quote dictionaries with text and optional page/section
    """
    quotes = []

    # Keywords for photobiomodulation research
    keywords = [
        "photobiomodulation", "red light", "near-infrared", "PBM",
        "wavelength", "therapy", "treatment", "significant", "reduction",
        "improvement", "clinical", "study", "patients", "results"
    ]

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 30 or len(sentence) > 300:
            continue

        # Check if sentence contains relevant keywords
        keyword_count = sum(1 for kw in keywords if kw.lower() in sentence.lower())

        if keyword_count >= 2:
            quotes.append({
                "text": sentence,
                "page": "",
                "section": ""
            })

            if len(quotes) >= max_quotes:
                break

    return quotes


def _extract_quotes_from_pdf(page_texts: Dict[int, str], max_quotes: int = 5) -> List[Dict[str, str]]:
    """Extract quotes from PDF with page references.

    Args:
        page_texts: Dictionary mapping page number to text
        max_quotes: Maximum quotes to extract

    Returns:
        List of quote dictionaries with page references
    """
    quotes = []

    # Combine all pages for keyword matching
    for page_num, text in page_texts.items():
        page_quotes = _extract_quotes_from_text(text, max_quotes=2)
        for q in page_quotes:
            q["page"] = str(page_num)
            quotes.append(q)

    # Sort by relevance (keyword density) and take top N
    def quote_score(q):
        text = q.get("text", "")
        keywords = ["significant", "reduction", "improvement", "clinical", "results"]
        return sum(1 for kw in keywords if kw.lower() in text.lower())

    quotes.sort(key=quote_score, reverse=True)
    return quotes[:max_quotes]


def format_source_card(
    title: str,
    quote: str,
    url: str,
    page: str = "",
    access_type: str = "full"
) -> str:
    """Format Vietnamese source card for Discord.

    Args:
        title: Paper title
        quote: Key quote
        url: Source URL
        page: Page number (optional)
        access_type: "full" or "abstract_only"

    Returns:
        Formatted source card string
    """
    page_str = f"\n📄 Trang: {page}" if page else ""
    access_note = "\n⚠️ Ghi chú: Abstract only — bài báo yêu cầu trả phí" if access_type == "abstract_only" else ""

    return f"""📄 NGUỒN: {title}
> "{quote}"
🔗 Link: {url}{page_str}{access_note}"""


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: paper_fetcher.py <command> [args]")
        print("Commands: fetch <url>, test")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "fetch" and len(sys.argv) > 2:
        url = sys.argv[2]
        print(f"Fetching: {url}")
        paper, access_type = fetch_paper(url)

        print(f"\nAccess: {access_type}")
        print(f"Title: {paper.get('title', 'N/A')}")
        print(f"Abstract: {paper.get('abstract', 'N/A')[:200]}...")
        print(f"Content length: {len(paper.get('content', ''))}")
        print(f"Quotes found: {len(paper.get('quotes', []))}")

        if paper.get("quotes"):
            print("\nTop quote:")
            q = paper["quotes"][0]
            print(f'  "{q.get("text", "")[:100]}..." (Page {q.get("page", "N/A")})')

        if paper.get("error"):
            print(f"\nError: {paper['error']}")

    elif cmd == "test":
        print("Testing paper fetcher...")
        # Test with a known open-access paper URL
        test_url = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC543292/"
        paper, access_type = fetch_paper(test_url)
        print(f"Access type: {access_type}")
        print(f"Title: {paper.get('title', 'N/A')}")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
