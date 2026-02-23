# System Architecture - Content Pipeline

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTENT PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐│
│   │  Stage 1 │───►│  Stage 2 │───►│  Stage 3 │───►│  Stage 4 ││
│   │  Scrape  │    │ Analyze  │    │ Generate │    │Distribute││
│   └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘│
│        │               │               │               │       │
│        ▼               ▼               ▼               ▼       │
│   ┌─────────────────────────────────────────────────────────┐ │
│   │                   STATE MANAGER                         │ │
│   │              (pipeline_state.json)                      │ │
│   └─────────────────────────────────────────────────────────┘ │
│                              │                                 │
└──────────────────────────────┼─────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│    Discord    │    │ Google Sheets │    │    Apify      │
│  (Approval)   │    │  (Storage)    │    │  (Scraping)   │
└───────────────┘    └───────────────┘    └───────────────┘
```

## Pipeline Flow

### Stage 1: Viral Scraping

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Config    │────►│    Apify    │────►│   Filter    │
│  Keywords   │     │   Actors    │     │ Engagement  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  Top 10     │
                                        │  Posts      │
                                        └─────────────┘
```

**Input:** Keywords from config.json
**Process:**
1. Initialize Apify client with token
2. Call Instagram scraper with keywords
3. Call Facebook scraper with keywords
4. Normalize posts to standard format
5. Filter by engagement threshold (500+)
6. Sort by engagement, take top N

**Output:** List of top viral posts stored in state

### Stage 2: Pattern Analysis

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Scraped    │────►│    Prompt   │────►│   Gemini    │────►│   JSON      │
│   Posts     │     │   Builder   │     │   Flash     │     │  Extractor  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                                                           │
      │                                                           ▼
      │                                                   ┌─────────────┐
      │                                                   │  Patterns   │
      │                                                   │   Dict      │
      │                                                   └─────────────┘
      │                                                           │
      └───────────────────────────────────────────────────────────┼───────────────────
                                                                  ▼
                                                           ┌─────────────┐
                                                           │viral-patterns│
                                                           │     .md     │
                                                           └─────────────┘
```

**Input:** Scraped posts from Stage 1 (stored in state)
**Process:**
1. Retrieve posts from state (`sm.get_data(1)`)
2. Build analysis prompt with Vietnamese wellness focus
3. Call Gemini 2.5 Flash via `gemini_client.call_gemini()`
4. Extract JSON from response (handles markdown code blocks)
5. Fallback to regex extraction if JSON parse fails
6. Update `references/viral-patterns.md` with new patterns
7. Record token usage and cost
8. Post to Discord for approval

**Output:** Pattern dict stored in state (`sm.add_data(2, patterns)`)

**Pattern Schema:**
```python
{
    "hooks": [{"name", "template", "example", "frequency"}],
    "structures": [{"type", "sections", "avg_length", "percentage"}],
    "tone": {"formality", "emotions", "expressions"},
    "ctas": [{"type", "template", "placement"}]
}
```

**Error Handling:**
- Budget exceeded: Abort with error message
- Gemini API error: Post error to Discord
- JSON parse failure: Use regex fallback extractor
- Discord failure: Mark partial success, data still saved

### Stage 3: Content Generation

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Sheets    │────►│    Paper    │────►│    GLM5     │────►│ Vietnamese  │
│    URL      │     │   Fetcher   │     │    Model    │     │   Content   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │                    │                    │
                          │                    │                    ▼
                          │                    │            ┌─────────────┐
                          │                    │            │   Source    │
                          │                    │            │    Card     │
                          │                    │            └─────────────┘
                          │                    │                    │
                          ▼                    ▼                    ▼
                   ┌─────────────────────────────────────────────────────┐
                   │              DISCORD FORUM POST                      │
                   │  (Content + Source + Report Card + Admin Tag)        │
                   └─────────────────────────────────────────────────────┘
```

**Input:** Research paper URL from Sheets + patterns from Stage 2
**Process:**
1. Check at Stage 3 (`sm.get_current_stage() == 3`)
2. Get patterns from Stage 2 (`sm.get_data(2)`)
3. Read next paper URL from Sheets (round-robin via `get_next_paper_url()`)
4. Fetch paper content via Paper Fetcher (`fetch_paper(url)`)
5. Extract quotes and findings
6. Build generation prompt with patterns
7. Call GLM5 endpoint (`call_glm5()`)
8. Format source card with quote and URL
9. Post to Discord #content-creation forum
10. Store content data in state (`sm.add_data(3, content_data)`)

**Output:** Vietnamese content draft (200-300 words) with source citation

**Paper Fetcher Details:**
- Handles HTML articles and PDF files
- Detects paywalls (returns abstract-only for 401/403)
- Extracts key quotes with keyword filtering
- Tracks page references for PDFs
- Access types: `full`, `abstract_only`, `error`

**GLM5 Prompt Structure:**
```
System: Vietnamese persona "be Ngo" - warm, friendly, expert but accessible
User: Paper title + findings + quotes + patterns to use
Output: 200-300 word Vietnamese social media post
```

**Error Handling:**
- No paper URL: Post error to Discord, halt pipeline
- Paper fetch error: Continue with available data (abstract)
- GLM5 API error: Post error to Discord, mark failed
- Discord failure: Mark partial success, content saved to state

### Stage 4: Distribution

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Generated   │────►│   Google    │────►│   Discord   │
│  Content    │     │   Sheets    │     │  Confirm    │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Input:** Generated content from Stage 3
**Process:**
1. Write to "Published Content" worksheet
2. Include metadata row
3. Post confirmation to Discord

**Output:** Sheet URL + Discord message

## Component Details

### State Manager

Central state persistence layer. Handles:
- Daily reset logic
- Stage tracking
- Cost tracking
- Data storage between stages
- History archival

**File:** `scripts/state_manager.py`
**State File:** `pipeline_state.json`
**History:** `history/state_YYYY-MM-DD.json`

### Apify Client

Wrapper for Apify API operations.

**File:** `scripts/utils/apify_client.py`
**Functions:**
| Function | Purpose |
|----------|---------|
| `scrape_instagram()` | Scrape IG posts |
| `scrape_facebook()` | Scrape FB posts |
| `filter_by_engagement()` | Filter by threshold |
| `get_top_posts()` | Get top N posts |
| `estimate_cost()` | Calculate cost |

### Sheets Client

Wrapper for Google Sheets operations.

**File:** `scripts/utils/sheets_client.py`
**Functions:**
| Function | Purpose |
|----------|---------|
| `get_research_urls()` | Read URLs from column |
| `get_next_paper_url()` | Round-robin URL selection |
| `write_published_content()` | Write content row |

### Discord Formatter

Format messages for Discord.

**File:** `scripts/utils/discord_fmt.py`
**Functions:**
| Function | Purpose |
|----------|---------|
| `format_report_card()` | Stage completion report |
| `format_source_card()` | Source citation card |
| `format_scraped_results()` | Scraping summary |
| `format_patterns()` | Pattern analysis summary |
| `format_generated_content()` | Content preview |
| `format_distribution_confirm()` | Distribution confirmation |

### Gemini Client

Wrapper for Google Gemini API operations.

**File:** `scripts/utils/gemini_client.py`
**Functions:**
| Function | Purpose |
|----------|---------|
| `call_gemini()` | Call Gemini API with retry logic |
| `extract_json_from_response()` | Parse JSON from markdown response |
| `build_analysis_prompt()` | Format viral posts for analysis |
| `_get_api_key()` | Get API key from config/ENV |

**Features:**
- 3 retries with exponential backoff
- Handles markdown code blocks (```json)
- Token usage tracking
- Cost estimation (Gemini 2.5 Flash pricing)
- Budget enforcement

**Cost Model:**
- Input: $0.000075/1K tokens
- Output: $0.0003/1K tokens

### GLM5 Client

Wrapper for GLM5 API operations (OpenAI-compatible).

**File:** `scripts/utils/glm5_client.py`
**Functions:**
| Function | Purpose |
|----------|---------|
| `call_glm5()` | Call GLM5 API with retry logic |
| `build_generation_prompt()` | Build Vietnamese content prompts |
| `_get_endpoint()` | Get endpoint from config/ENV |
| `_get_api_key()` | Get API key from ENV |

**Features:**
- OpenAI-compatible chat completion format
- 3 retries with exponential backoff
- Token usage tracking
- Cost estimation (placeholder rates)
- Vietnamese "be Ngo" persona prompting

**Cost Model:**
- Input: $0.0001/1K tokens (placeholder)
- Output: $0.0002/1K tokens (placeholder)

### Paper Fetcher

Paper content extraction from URLs.

**File:** `scripts/utils/paper_fetcher.py`
**Functions:**
| Function | Purpose |
|----------|---------|
| `fetch_paper()` | Fetch and extract paper content |
| `format_source_card()` | Format Vietnamese source card |
| `_extract_html_content()` | Extract from HTML article |
| `_extract_pdf_content()` | Extract from PDF file |
| `_extract_quotes_from_text()` | Extract key quotes |
| `_extract_quotes_from_pdf()` | Extract quotes with page refs |

**Features:**
- Dual-mode: HTML articles and PDF files
- Paywall detection (401/403 -> abstract only)
- Quote extraction with keyword filtering
- Page reference tracking
- Academic headers for bot avoidance

**Access Types:**
- `full` - Complete paper content
- `abstract_only` - Paywalled, abstract only
- `error` - Fetch failed

### Config Validator

Validate configuration completeness.

**File:** `scripts/config_validator.py`
**Checks:**
- Required sections present
- No placeholder values
- Environment variables set
- Valid threshold values
- Non-negative budgets

## Data Models

### Normalized Post

```python
{
    "platform": "instagram" | "facebook",
    "url": str,
    "caption": str,
    "likes": int,
    "comments": int,
    "shares": int,
    "timestamp": str,
    "author": str,
    "media_type": str,
    "hashtags": list,
    "raw": dict  # Original response
}
```

### Paper Data

```python
{
    "url": str,              # Source URL
    "title": str,            # Paper title
    "content": str,          # Full text content
    "abstract": str,         # Abstract text
    "quotes": [              # Extracted quotes
        {"text": str, "page": str, "section": str}
    ],
    "page_refs": {int: str}, # Page number -> text
    "error": str | None      # Error if fetch failed
}
```

### Generated Content

```python
{
    "content": str,          # Vietnamese content
    "source_title": str,     # Paper title
    "source_url": str,       # Paper URL
    "word_count": int,       # Content length
    "access_type": str,      # "full" | "abstract_only"
    "tokens_in": int,        # Input tokens
    "tokens_out": int,       # Output tokens
    "cost": float,           # Generation cost
    "thread_id": str,        # Discord thread ID
    "error": str | None      # Error if failed
}
```

## Error Handling Strategy

1. **API Failures:** Log error, return empty/default, continue
2. **Budget Exceeded:** Abort API call, log warning
3. **Missing Config:** Use defaults, log warning
4. **State Corruption:** Reset to default, archive corrupted file

## Security

- **No secrets in code:** All credentials via ENV variables
- **ENV: prefix:** Config values reference environment variables
- **Service account:** Google auth via service account JSON (path in ENV)

---

*Last updated: 2026-02-23*
*Phase: 4 - Stage 3 Content Generation Complete*
