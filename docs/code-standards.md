# Code Standards - Content Pipeline

## Project Structure

```
content-pipeline/
├── SKILL.md                    # OpenClaw skill definition
├── docs/                       # Documentation
│   ├── project-overview-pdr.md
│   ├── code-standards.md
│   └── system-architecture.md
├── scripts/
│   ├── stage_1_scrape.py       # Stage 1: Apify scraping
│   ├── stage_2_analyze.py      # Stage 2: Gemini analysis
│   ├── stage_3_generate.py     # Stage 3: GLM5 generation
│   ├── stage_4_distribute.py   # Stage 4: Sheets distribution
│   ├── state_manager.py        # State persistence
│   ├── config_validator.py     # Config validation
│   └── utils/
│       ├── apify_client.py     # Apify wrapper
│       ├── discord_fmt.py      # Discord formatting
│       └── sheets_client.py    # gspread wrapper
├── references/
│   ├── viral-patterns.md       # Viral content patterns
│   └── prompt-templates.md     # Content generation prompts
├── assets/
│   └── config.json             # Pipeline configuration
├── history/                    # Archived state files
└── pipeline_state.json         # Current pipeline state
```

## Coding Conventions

### Python Style

- **Python 3.8+** compatibility
- **PEP 8** formatting
- **Type hints** for function signatures
- **Docstrings** for all public functions

### Function Documentation

```python
def function_name(param: Type) -> ReturnType:
    """Brief description of function.

    Args:
        param: Description of parameter

    Returns:
        Description of return value
    """
```

### Error Handling

```python
# Specific exceptions first, general last
try:
    result = api_call()
except ConnectionError as e:
    print(f"Connection error: {e}")
    return default_value
except TimeoutError as e:
    print(f"Timeout: {e}")
    return default_value
except ValueError as e:
    print(f"Invalid response: {e}")
    return default_value
except Exception as e:
    print(f"Unexpected error: {type(e).__name__}: {e}")
    return default_value
```

### Configuration Access

```python
# Use ENV: prefix for sensitive values
token_ref = config.get("apify", {}).get("token", "")
if token_ref.startswith("ENV:"):
    env_var = token_ref[4:]
    return os.environ.get(env_var, "")
```

### CLI Interface Pattern

```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: script.py <command> [args]")
        print("Commands: cmd1, cmd2, test")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "cmd1":
        # handle command
        pass
    elif cmd == "test":
        # test mode
        pass
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
```

## State Management

### State Structure

```json
{
  "current_date": "2026-02-22",
  "stage": 1,
  "status": "pending",
  "thread_ids": {
    "stage_1": null,
    "stage_2": null,
    "stage_3": null,
    "stage_4": null
  },
  "data": {
    "scraped_posts": [],
    "patterns": {},
    "generated_content": null,
    "distributed": false
  },
  "cost_tracking": {
    "apify": 0.0,
    "gemini": 0.0,
    "glm5": 0.0
  },
  "history": []
}
```

### State Operations

| Function | Purpose |
|----------|---------|
| `load_state()` | Load current state, reset if new day |
| `save_state(state)` | Persist state to file |
| `reset_daily()` | Create fresh state, archive old |
| `advance_stage(n)` | Move to stage n |
| `set_status(status)` | Set pipeline status |
| `record_cost(service, amount)` | Track spending |
| `add_data(stage, data)` | Store stage output |
| `get_data(stage)` | Retrieve stored data |
| `check_budget(service)` | Verify budget available |

## Configuration Schema

### config.json Structure

```json
{
  "apify": {
    "token": "ENV:APIFY_TOKEN",
    "actors": { "instagram": "...", "facebook": "..." },
    "max_results_per_run": 100,
    "proxy": { "useApifyProxy": true }
  },
  "keywords": {
    "vi": ["suc khoe", "lieu phap anh sang"],
    "en": ["wellness", "red light therapy"]
  },
  "thresholds": {
    "viral": 5000,
    "micro_viral": 500,
    "engagement_rate_min": 0.03
  },
  "discord": {
    "research_channel_id": "...",
    "content_channel_id": "...",
    "admin_user_id": "..."
  },
  "sheets": {
    "research_sheet_url": "...",
    "research_column": "U",
    "output_sheet_name": "Published Content",
    "service_account_path": "ENV:GOOGLE_SERVICE_ACCOUNT_PATH"
  },
  "models": {
    "analysis": "gemini-2.5-flash",
    "generation": "glm5",
    "gemini_api_key": "ENV:GEMINI_API_KEY",
    "glm5_endpoint": "ENV:GLM5_ENDPOINT"
  },
  "budget": {
    "daily_apify_cap_usd": 0.50,
    "daily_gemini_cap_usd": 0.10,
    "monthly_apify_cap_usd": 10.00,
    "monthly_gemini_cap_usd": 3.00
  },
  "pipeline": {
    "cron_time": "08:00",
    "timezone": "Asia/Ho_Chi_Minh",
    "max_posts_per_scrape": 10,
    "approval_timeout_hours": 24
  }
}
```

## Required Environment Variables

| Variable | Purpose |
|----------|---------|
| `APIFY_TOKEN` | Apify API authentication |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GLM5_ENDPOINT` | GLM5 API endpoint URL |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | Path to service account JSON |

## Testing

### Validation Commands

```bash
# Validate configuration
python scripts/config_validator.py

# Test Apify client
python scripts/utils/apify_client.py test

# Test Sheets client
python scripts/utils/sheets_client.py test

# Check current state
python scripts/state_manager.py show
```

---

*Last updated: 2026-02-22*
