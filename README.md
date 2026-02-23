# Content Pipeline Skill

Automated 4-stage content pipeline for Kajo wellness content from photobiomodulation research.

## Quick Start

```bash
# Validate configuration
python scripts/config_validator.py

# Check current state
python scripts/state_manager.py show

# Test Apify connection
python scripts/utils/apify_client.py test

# Test Google Sheets connection
python scripts/utils/sheets_client.py test
```

## Architecture

```
Cron 8AM VN -> Stage 1: Scrape -> Discord (await approval)
                                      |
                                 user approves
                                      v
                                Stage 2: Analyze -> Discord (await approval)
                                      |
                                 user approves
                                      v
                                Stage 3: Generate -> Discord (await approval)
                                      |
                                 user approves
                                      v
                                Stage 4: Distribute -> Google Sheet + Discord
```

## Project Structure

```
content-pipeline/
├── SKILL.md                    # OpenClaw skill definition
├── README.md                   # This file
├── docs/                       # Documentation
│   ├── project-overview-pdr.md # Requirements & milestones
│   ├── code-standards.md       # Coding conventions
│   ├── codebase-summary.md     # Codebase overview
│   └── system-architecture.md  # Architecture details
├── scripts/
│   ├── stage_1_scrape.py       # Stage 1: Apify scraping
│   ├── stage_2_analyze.py      # Stage 2: Gemini analysis
│   ├── stage_3_generate.py     # Stage 3: GLM5 generation
│   ├── stage_4_distribute.py   # Stage 4: Sheets distribution (planned)
│   ├── state_manager.py        # State persistence
│   ├── config_validator.py     # Config validation
│   └── utils/
│       ├── apify_client.py     # Apify wrapper
│       ├── discord_fmt.py      # Discord formatting
│       ├── gemini_client.py    # Gemini API client
│       ├── glm5_client.py      # GLM5 API client
│       ├── paper_fetcher.py    # Paper fetching (HTML/PDF)
│       └── sheets_client.py    # gspread wrapper
├── tests/
│   ├── test_phase3.py          # Unit tests for Stage 2
│   └── test_phase4.py          # Unit tests for Stage 3
├── references/
│   ├── viral-patterns.md       # Viral content patterns (auto-updated)
│   └── prompt-templates.md     # Content generation prompts
├── assets/
│   └── config.json             # Pipeline configuration
├── history/                    # Archived state files
└── pipeline_state.json         # Current pipeline state
```

## Configuration

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `APIFY_TOKEN` | Apify API token |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GLM5_ENDPOINT` | GLM5 API endpoint URL |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Path to Google service account JSON |

### Configuration File

See `assets/config.json` for:
- Keywords (Vietnamese + English)
- Engagement thresholds
- Discord channel IDs
- Google Sheet URLs
- Model selections
- Budget caps

## Stages

### Stage 1: Viral Scraping
- Scrape FB/IG via Apify
- Filter by engagement (500+ interactions)
- Output: Top 10 viral posts

### Stage 2: Pattern Analysis
- Analyze with Gemini 2.5 Flash
- Extract hooks, structures, tones, CTAs
- Auto-update viral-patterns.md
- Budget enforcement ($0.10/day cap)
- Retry logic with exponential backoff

### Stage 3: Content Generation
- Fetch paper URL from Google Sheets
- Extract content from HTML articles or PDFs
- Handle paywalled content (abstract only)
- Generate Vietnamese content with GLM5
- Include source citation card with quote/page
- Track token usage and cost

### Stage 4: Distribution
- Write to Google Sheets
- Post confirmation to Discord

## State Management

```bash
# Check current stage
python scripts/state_manager.py get-stage

# View full state
python scripts/state_manager.py show

# Reset daily state
python scripts/state_manager.py reset

# Advance to stage
python scripts/state_manager.py advance 2
```

## Cost Budget

| Service | Daily Cap | Monthly Est |
|---------|-----------|-------------|
| Apify   | $0.50     | $5-10       |
| Gemini  | $0.10     | $1-3        |
| GLM5    | User endpoint | --      |

## Documentation

- [Project Overview & PDR](./docs/project-overview-pdr.md)
- [Code Standards](./docs/code-standards.md)
- [System Architecture](./docs/system-architecture.md)
- [Viral Patterns Reference](./references/viral-patterns.md)
- [Prompt Templates](./references/prompt-templates.md)

## Phase 4 Status

- [x] State management system
- [x] Configuration validation
- [x] Apify client wrapper
- [x] Google Sheets client wrapper
- [x] Discord formatting utilities
- [x] Reference documentation
- [x] Stage 1: Viral Scraping
- [x] Stage 2: Pattern Analysis with Gemini
- [x] Gemini client with retry logic
- [x] viral-patterns.md auto-update
- [x] Unit tests for Phase 3
- [x] Stage 3: Content Generation
- [x] GLM5 client with OpenAI-compatible format
- [x] Paper fetcher (HTML/PDF extraction)
- [x] Unit tests for Phase 4
- [ ] Stage 4: Distribution (Phase 5)

---

*Last updated: 2026-02-23*
