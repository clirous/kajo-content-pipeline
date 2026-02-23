#!/usr/bin/env python3
"""Google Sheets wrapper for research URLs and published content."""

import os
import json
from typing import List, Optional, Dict, Any
from pathlib import Path

# Lazy import for gspread - only imported when needed
_gspread = None


def _get_gspread():
    """Lazy load gspread module."""
    global _gspread
    if _gspread is None:
        try:
            import gspread as _gs
            _gspread = _gs
        except ImportError:
            pass
    return _gspread

# Load config
SKILL_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = SKILL_DIR / "assets" / "config.json"


def _load_config() -> dict:
    """Load configuration from config.json."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_service_account_path(config: Optional[dict] = None) -> str:
    """Get Google service account JSON path from config or environment."""
    if config is None:
        config = _load_config()

    path_ref = config.get("sheets", {}).get("service_account_path", "")

    # Handle ENV: prefix
    if path_ref.startswith("ENV:"):
        env_var = path_ref[4:]
        return os.environ.get(env_var, "")

    return path_ref


def _init_client():
    """Initialize gspread client. Returns None if not configured."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        config = _load_config()
        sa_path = _get_service_account_path(config)

        if not sa_path or not os.path.exists(sa_path):
            print("Warning: Google service account file not found.")
            return None

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        credentials = Credentials.from_service_account_file(sa_path, scopes=scopes)
        return gspread.authorize(credentials)

    except ImportError:
        print("Warning: gspread not installed. Run: pip install gspread google-auth")
        return None
    except Exception as e:
        print(f"Warning: Failed to initialize gspread: {e}")
        return None


def get_research_urls(
    sheet_url: Optional[str] = None,
    column: str = "U"
) -> List[str]:
    """Read paper URLs from specified column in research sheet.

    Args:
        sheet_url: URL to research papers sheet (uses config if not provided)
        column: Column letter containing URLs (default: U)

    Returns:
        List of URLs from the column
    """
    config = _load_config()
    if sheet_url is None:
        sheet_url = config.get("sheets", {}).get("research_sheet_url", "")

    if not sheet_url or sheet_url == "PLACEHOLDER_RESEARCH_SHEET_URL":
        print("Warning: Research sheet URL not configured.")
        return []

    client = _init_client()
    if client is None:
        return []

    try:
        spreadsheet = client.open_by_url(sheet_url)
        worksheet = spreadsheet.sheet1  # Use first sheet

        # Get all values in the column
        col_index = _column_to_index(column)
        col_values = worksheet.col_values(col_index)

        # Filter out empty values and headers
        urls = [
            url.strip()
            for url in col_values
            if url.strip() and url.strip().startswith("http")
        ]

        return urls

    except Exception as e:
        print(f"Failed to read research URLs: {e}")
        return []


def get_next_paper_url(
    sheet_url: Optional[str] = None,
    column: str = "U",
    state_file: Optional[Path] = None
) -> Optional[str]:
    """Get next paper URL using round-robin rotation.

    Args:
        sheet_url: URL to research papers sheet
        column: Column letter containing URLs
        state_file: Path to state file for tracking index

    Returns:
        Next URL in rotation, or None if no URLs available
    """
    urls = get_research_urls(sheet_url, column)
    if not urls:
        return None

    # Load or initialize paper index
    if state_file is None:
        state_file = SKILL_DIR / "pipeline_state.json"

    current_index = 0
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                current_index = state.get("paper_index", 0)
        except (json.JSONDecodeError, KeyError, IOError) as e:
            print(f"Warning: Could not read paper index from state: {e}")

    # Get URL at current index
    url = urls[current_index % len(urls)]

    # Update index for next time
    next_index = (current_index + 1) % len(urls)
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            state["paper_index"] = next_index
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except (json.JSONDecodeError, KeyError, IOError) as e:
            print(f"Warning: Could not update paper index in state: {e}")

    return url


def write_published_content(
    sheet_url: Optional[str] = None,
    content_data: Dict[str, Any] = None,
    worksheet_name: str = "Published Content"
) -> bool:
    """Write published content to Google Sheets.

    Args:
        sheet_url: URL to research sheet (uses config if not provided)
        content_data: Dictionary with content, source, date, etc.
        worksheet_name: Name of worksheet to write to

    Returns:
        True if successful, False otherwise
    """
    config = _load_config()
    if sheet_url is None:
        sheet_url = config.get("sheets", {}).get("research_sheet_url", "")

    if not sheet_url or sheet_url == "PLACEHOLDER_RESEARCH_SHEET_URL":
        print("Warning: Research sheet URL not configured.")
        return False

    client = _init_client()
    if client is None:
        return False

    # Early validation
    if content_data is None:
        print("Error: content_data is None")
        return False

    try:
        spreadsheet = client.open_by_url(sheet_url)

        # Get or create worksheet
        gs = _get_gspread()
        WorksheetNotFound = gs.WorksheetNotFound if gs else Exception
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
        except WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=worksheet_name,
                rows=1000,
                cols=10
            )
            # Add headers
            worksheet.append_row([
                "Date",
                "Content",
                "Source Title",
                "Source URL",
                "Word Count",
                "Stage 1 Thread",
                "Stage 2 Thread",
                "Stage 3 Thread",
                "Status",
                "Total Cost"
            ])

        # Prepare row data
        row = [
            content_data.get("date", ""),
            content_data.get("content", ""),
            content_data.get("source_title", ""),
            content_data.get("source_url", ""),
            content_data.get("word_count", 0),
            content_data.get("thread_stage_1", ""),
            content_data.get("thread_stage_2", ""),
            content_data.get("thread_stage_3", ""),
            content_data.get("status", "published"),
            content_data.get("total_cost", 0.0)
        ]

        worksheet.append_row(row)
        return True

    except (IOError, OSError) as e:
        print(f"Failed to write to sheet (IO error): {e}")
        return False
    except (KeyError, TypeError) as e:
        print(f"Failed to write to sheet (data error): {e}")
        return False
    except Exception as e:
        # Catch-all for gspread API errors, but log type
        print(f"Failed to write to sheet ({type(e).__name__}): {e}")
        return False


def _column_to_index(column: str) -> int:
    """Convert column letter to 1-based index (A=1, B=2, ..., Z=26, AA=27)."""
    result = 0
    for char in column.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: sheets_client.py <command> [args]")
        print("Commands: urls, next-url, test")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "urls":
        urls = get_research_urls()
        print(f"Found {len(urls)} URLs")
        for url in urls[:5]:
            print(f"  - {url}")

    elif cmd == "next-url":
        url = get_next_paper_url()
        if url:
            print(f"Next URL: {url}")
        else:
            print("No URLs available")

    elif cmd == "test":
        print("Testing Sheets client...")
        client = _init_client()
        if client:
            print("Client initialized successfully")
            config = _load_config()
            sheet_url = config.get("sheets", {}).get("research_sheet_url", "")
            if sheet_url and sheet_url != "PLACEHOLDER_RESEARCH_SHEET_URL":
                print(f"Sheet URL configured: {sheet_url[:50]}...")
            else:
                print("Sheet URL not configured")
        else:
            print("Failed to initialize client")

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
