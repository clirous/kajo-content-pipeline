# Codebase Summary - Content Pipeline

## Overview

Automated 4-stage content pipeline transforming photobiomodulation research into Vietnamese social media content. Phase 6 completes the pipeline with cron scheduling and bilingual approval flow.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| Scraping | Apify (Instagram/Facebook actors) |
| Analysis | Google Gemini 2.5 Flash |
| Generation | GLM5 (OpenAI-compatible API) |
| Paper Fetch | requests, pypdf |
| Storage | Google Sheets (gspread) |
| State | JSON files |
| Notifications | Discord (via openclaw CLI) |
| Scheduling | openclaw CLI cron |

## Implemented Components (Phase 6 - Complete)

### Core Scripts

| File | LOC | Purpose |
|------|-----|---------|
| `scripts/state_manager.py` | 381 | Pipeline state, daily reset, cost tracking, keyword detection |
| `scripts/setup_cron.py` | 191 | Cron job setup via openclaw CLI (daily trigger) |
| `scripts/config_validator.py` | 150 | Configuration validation, placeholder detection |
| `scripts/stage_1_scrape.py` | 328 | Stage 1: Apify scraping with Discord notification |
| `scripts/stage_2_analyze.py` | 439 | Stage 2: Gemini pattern analysis with viral-patterns.md update |
| `scripts/stage_3_generate.py` | 375 | Stage 3: GLM5 content generation with paper fetching |
| `scripts/stage_4_distribute.py` | 314 | Stage 4: Distribution to Google Sheets with Discord confirmation |
| `scripts/utils/apify_client.py` | 315 | Apify API wrapper for IG/FB scraping |
| `scripts/utils/sheets_client.py` | 314 | Google Sheets wrapper for URL/content storage with distribution |
| `scripts/utils/discord_fmt.py` | 267 | Discord message formatting utilities |
| `scripts/utils/gemini_client.py` | 366 | Gemini API client for pattern analysis |
| `scripts/utils/glm5_client.py` | 346 | GLM5 API client for Vietnamese content generation |
| `scripts/utils/paper_fetcher.py` | 425 | Paper fetching and content extraction (HTML/PDF) |

### Tests

| File | Purpose |
|------|---------|
| `tests/test_phase3.py` | Unit tests for Stage 2 analysis and Gemini client |
| `tests/test_phase4.py` | Unit tests for Stage 3 generation, GLM5 client, paper fetcher |
| `tests/test_phase5.py` | Unit tests for Stage 4 distribution, sheets client, cost tracking |
| `tests/test_phase6.py` | Unit tests for cron setup, keyword detection, state transitions |

### Configuration

| File | Purpose |
|------|---------|
| `assets/config.json` | Pipeline configuration (keywords, thresholds, budgets, channel IDs) |

### Reference Documentation

| File | Purpose |
|------|---------|
| `references/viral-patterns.md` | Viral content pattern library (auto-updated by Stage 2) |
| `references/prompt-templates.md` | Vietnamese content generation prompts and guidelines |

## Key Functions

### State Manager

```python
load_state() -> dict              # Load state, reset if new day
save_state(state)                 # Persist state
reset_daily() -> dict             # Fresh state, archive old
advance_stage(n) -> dict          # Move to stage n
set_status(status) -> dict        # Set pipeline status
record_cost(service, amount)       # Track spending
add_data(stage, data) -> dict     # Store stage output
get_data(stage) -> Any            # Retrieve stored data
check_budget(service) -> bool     # Verify budget available
get_current_stage() -> int        # Get current stage number
set_thread_id(stage, thread_id)   # Store Discord thread ID
is_today_started() -> bool        # Check if pipeline started today
get_status() -> str               # Get current pipeline status
set_feedback(feedback) -> dict    # Store user feedback
get_feedback() -> str             # Get stored feedback
clear_feedback() -> dict          # Clear feedback after re-run
mark_awaiting_approval() -> dict  # Mark stage awaiting approval
mark_failed(error_msg) -> dict    # Mark pipeline as failed
is_approval_keyword(message) -> bool   # Detect approval (EN/VI)
is_rejection_keyword(message) -> bool  # Detect revision request
is_skip_keyword(message) -> bool       # Detect skip request
is_stop_keyword(message) -> bool       # Detect stop request
```

### Gemini Client

```python
call_gemini(prompt, model, config, temperature, max_output_tokens) -> Tuple[str, dict]
extract_json_from_response(text) -> dict
build_analysis_prompt(posts) -> str
_get_api_key(config) -> str
_load_config() -> dict
```

### GLM5 Client

```python
call_glm5(system_prompt, user_prompt, model, config, temperature, max_tokens) -> Tuple[str, dict]
build_generation_prompt(patterns, paper_title, findings, quotes, tone) -> Tuple[str, str]
_get_endpoint(config) -> str      # Get GLM5 endpoint from config/ENV
_get_api_key(config) -> str       # Get GLM5 API key from ENV
_load_config() -> dict
```

### Paper Fetcher

```python
fetch_paper(url, timeout) -> Tuple[dict, str]  # Returns (paper_data, access_type)
format_source_card(title, quote, url, page, access_type) -> str
_extract_html_content(html, url) -> dict
_extract_pdf_content(pdf_bytes, url) -> dict
_extract_quotes_from_text(text, max_quotes) -> List[dict]
_extract_quotes_from_pdf(page_texts, max_quotes) -> List[dict]
```

### Stage 2 Analysis

```python
run_stage_2(dry_run) -> dict           # Execute Stage 2 pipeline
_fallback_extract_patterns(text) -> dict  # Regex fallback if JSON parse fails
_update_patterns_file(patterns, count)    # Append to viral-patterns.md
_get_sample_patterns() -> dict            # Dry run sample data
_post_to_discord(config, message) -> str  # Post to Discord forum
```

### Stage 3 Generation

```python
run_stage_3(dry_run) -> dict            # Execute Stage 3 pipeline
_load_config() -> dict                  # Load config.json
_post_to_discord(config, message) -> str  # Post to Discord forum
_post_error_to_discord(config, error_msg, dry_run) -> None
_get_default_patterns() -> dict         # Fallback patterns if Stage 2 missing
_get_sample_content() -> str            # Dry run sample content
```

### Stage 4 Distribution

```python
run_stage_4(dry_run) -> dict            # Execute Stage 4 pipeline
_format_completion_message(source_title, source_url, total_cost, cost_breakdown, thread_3) -> str
_post_to_discord(config, message, reply_to) -> str  # Post with reply support
_post_error_to_discord(config, error_msg, dry_run) -> None
_archive_completed_state() -> None      # Save completed state to history/
```

### Apify Client

```python
scrape_instagram(keywords, max_results) -> List[dict]
scrape_facebook(keywords, max_results) -> List[dict]
filter_by_engagement(posts, threshold) -> List[dict]
get_top_posts(posts, limit) -> List[dict]
estimate_cost(posts_count, platform) -> float
```

### Sheets Client

```python
get_research_urls(sheet_url, column) -> List[str]
get_next_paper_url(sheet_url, column, state_file) -> str
write_published_content(sheet_url, content_data, worksheet_name) -> bool
_init_client() -> gspread.Client       # Lazy gspread initialization
_get_service_account_path(config) -> str  # Resolve ENV: prefix paths
```

### Discord Formatter

```python
format_report_card(stage, model, tokens, cost, status) -> str
format_source_card(title, quote, url, page) -> str
format_scraped_results(posts, total, filtered, platform) -> str
format_patterns(patterns) -> str
format_generated_content(content, source, url, words) -> str
format_distribution_confirm(sheet_url, preview) -> str
```

### Cron Setup

```python
setup_cron(dry_run) -> bool       # Create daily cron job via openclaw CLI
test_cron(dry_run) -> bool        # Test with 2-minute one-shot trigger
show_cron_info() -> None          # Display cron configuration
load_config() -> dict             # Load config.json
```

## Data Flow

```
1. Config (config.json)
   └──> Keywords, thresholds, credentials

2. State (pipeline_state.json)
   └──> Stage tracking, data storage, costs

3. Stage 1 (stage_1_scrape.py)
   └──> Apify -> Filter -> Top Posts -> State -> Discord

4. Stage 2 (stage_2_analyze.py)
   └──> State Posts -> Gemini -> Patterns -> viral-patterns.md -> Discord

5. Stage 3 (stage_3_generate.py)
   └──> Sheets URL -> Paper Fetcher -> GLM5 -> Content -> Discord

6. Stage 4 (stage_4_distribute.py)
   └──> Stage 3 Content -> Google Sheets -> Discord Confirmation -> Archive

7. External APIs
   └──> Apify (scraping) -> Gemini (analysis) -> GLM5 (generation)
   └──> Paper Fetcher (HTML/PDF extraction)
   └──> Google Sheets (input/output/distribution)
   └──> Discord (approvals/notifications/completion)
```

## Configuration Schema

```json
{
  "apify": { "token", "actors", "max_results", "proxy" },
  "keywords": { "vi": [...], "en": [...] },
  "thresholds": { "viral", "micro_viral", "engagement_rate_min" },
  "discord": { "research_channel_id", "content_channel_id", "admin_user_id" },
  "sheets": { "research_sheet_url", "research_column", "output_sheet_name", "service_account_path" },
  "models": { "analysis", "generation", "gemini_api_key", "glm5_endpoint" },
  "budget": { "daily_apify_cap", "daily_gemini_cap", "monthly_caps" },
  "pipeline": { "cron_time", "timezone", "max_posts", "approval_timeout" }
}
```

## State Schema

```json
{
  "current_date": "ISO date",
  "stage": 1-4,
  "status": "pending|in_progress|awaiting_approval|completed|failed",
  "thread_ids": { "stage_1": "...", "stage_2": "...", ... },
  "data": {
    "stage_1": [...scraped posts...],
    "stage_2": {...patterns...},
    "stage_3": {...content...},
    "stage_4": {...distribution...}
  },
  "cost_tracking": { "apify": 0.0, "gemini": 0.0, "glm5": 0.0 },
  "history": [{ "timestamp", "action", ... }]
}
```

## Pipeline Complete

All 4 stages implemented with full automation. Phase 6 adds cron scheduling and bilingual approval flow.

## Dependencies

```
apify-client      # Apify API
gspread           # Google Sheets
google-auth       # Google authentication
requests          # HTTP client for Gemini/GLM5 APIs
pypdf             # PDF text extraction
```

## Cost Model

| Service | Rate | Daily Cap |
|---------|------|-----------|
| Apify IG | $0.002/post | $0.50 |
| Apify FB | $0.003/post | $0.50 |
| Gemini Flash | $0.000075/1K input, $0.0003/1K output | $0.10 |
| GLM5 | User endpoint (placeholder: $0.0001/1K in, $0.0002/1K out) | -- |

## GLM5 Client Features

- OpenAI-compatible chat completion format
- Retry logic with exponential backoff (3 retries)
- Token usage and cost tracking
- Budget enforcement before API calls
- Vietnamese prompt building for "be Ngo" persona
- Pattern integration from Stage 2

## Paper Fetcher Features

- Dual-mode extraction: HTML articles and PDF files
- Paywall detection (returns abstract-only when 401/403)
- Quote extraction with keyword filtering
- Page reference tracking for PDFs
- Source card formatting in Vietnamese

## Stage 3 Generation Features

- Paper URL fetching from Google Sheets (round-robin)
- Pattern integration from Stage 2
- Vietnamese content generation via GLM5
- Source card with quote and URL citation
- Discord posting with admin approval tag
- Cost tracking per generation call

## Stage 4 Distribution Features

- Content writing to Google Sheets "Published Content" worksheet
- Thread ID linking across all stages (Stage 1, 2, 3)
- Total pipeline cost aggregation and reporting
- Content truncation for Sheets (45K char limit)
- Discord completion message with cost breakdown
- State archival to `history/pipeline_{date}_complete.json`
- Reply-to threading for Discord confirmation

## Sheets Client Distribution Features

- `write_published_content()` with auto-worksheet creation
- Row fields: date, content, source_title, source_url, word_count, thread IDs, status, total_cost
- Worksheet headers auto-created on first write
- Lazy gspread initialization
- ENV: prefix support for service account path

## Phase 6: Cron & Approval Flow

### Cron Scheduling
- Daily trigger at 8AM Vietnam (configurable via config.json)
- Uses `openclaw cron add` CLI command
- Announces to Discord #research channel when triggered
- Test mode: 2-minute one-shot trigger for validation

### Keyword Detection (Bilingual EN/VI)
| Intent | English | Vietnamese |
|--------|---------|------------|
| Approval | approve, ok, lgtm, yes, good, proceed, continue, done, next | duyet, dong y, duoc, tot, tiep tuc, xong |
| Rejection | redo, try again, revise, fix, change, update, edit | lam lai, sua, chinh, cap nhat |
| Skip | skip, next, pass | bo qua, tiep, ke tiep |
| Stop | stop, pause, halt, cancel, abort | dung, tam dung, huy, ngung |

### State Transitions
- `is_today_started()` - Check if pipeline already running today
- `mark_awaiting_approval()` - Set status for approval gate
- `mark_failed(error)` - Record failure with error message
- `set_feedback()` / `get_feedback()` / `clear_feedback()` - Feedback handling for re-runs

### CLI Commands
```bash
# State management
python3 scripts/state_manager.py started           # Check if today started
python3 scripts/state_manager.py feedback <text>   # Save feedback
python3 scripts/state_manager.py check-keyword <msg>  # Detect keyword type

# Cron setup
python3 scripts/setup_cron.py --info               # Show cron config
python3 scripts/setup_cron.py --setup              # Create daily cron
python3 scripts/setup_cron.py --test               # Test with 2-min trigger
python3 scripts/setup_cron.py --setup --dry-run    # Preview cron command
```

---

*Generated: 2026-02-23*
*Phase: 6 - Pipeline Complete (All 4 Stages + Cron + Approval Flow)*
