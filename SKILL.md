---
name: content-pipeline
description: >
  Automated 4-stage content pipeline for Kajo wellness content from photobiomodulation research.
  (1) Scrape viral posts via Apify, (2) Analyze patterns with Gemini, (3) Generate Vietnamese
  content with GLM5, (4) Distribute to Sheets. Use when user says "run pipeline", "scrape content",
  "analyze patterns", "generate content", "distribute post", "start pipeline", or approves a
  stage in Discord forum. Also triggered by daily cron. Keywords: pipeline, scrape, viral,
  photobiomodulation, red light therapy, wellness, Vietnamese content, Instagram, Facebook.
---

# Content Pipeline

Automated content creation from photobiomodulation research papers. 4-stage pipeline with Discord approval gates.

## Architecture

```
Cron 8AM VN ──► Stage 1: Scrape ──► Discord #research (await ✅)
                                        │
                                  user approves
                                        ▼
                                Stage 2: Analyze ──► Discord #research (await ✅)
                                        │
                                  user approves
                                        ▼
                                Stage 3: Generate ──► Discord #content-creation (await ✅)
                                        │
                                  user approves
                                        ▼
                                Stage 4: Distribute ──► Google Sheet + Discord confirm
```

## Files

```
content-pipeline/
├── SKILL.md                    # This file
├── scripts/
│   ├── stage_1_scrape.py       # Apify scraping
│   ├── stage_2_analyze.py      # Gemini pattern analysis
│   ├── stage_3_generate.py     # GLM5 content generation
│   ├── stage_4_distribute.py   # Google Sheet distribution
│   ├── state_manager.py        # Pipeline state (JSON)
│   └── utils/
│       ├── apify_client.py     # Apify wrapper
│       ├── discord_fmt.py      # Report card + source card formatting
│       └── sheets_client.py    # gspread wrapper
├── references/
│   ├── viral-patterns.md       # Stored viral patterns (grows over time)
│   └── prompt-templates.md     # Content generation prompts
└── assets/
    └── config.json             # Keywords, thresholds, channel IDs
```

## Usage

### Run Full Pipeline
```bash
python scripts/stage_1_scrape.py  # Start from Stage 1
```

### Run Specific Stage
```bash
python scripts/state_manager.py get-stage  # Check current stage
python scripts/stage_2_analyze.py          # Run Stage 2
```

### State Management
```bash
python scripts/state_manager.py reset      # Reset daily state
python scripts/state_manager.py advance 2  # Advance to stage 2
```

## Stages

### Stage 1: Viral Scraping
- **Input**: Keywords from config.json
- **Action**: Scrape FB/IG via Apify, filter by engagement (500+ interactions)
- **Output**: Top 10 viral posts stored in state
- **Script**: `scripts/stage_1_scrape.py`

### Stage 2: Pattern Analysis
- **Input**: Scraped posts from Stage 1
- **Action**: Gemini analyzes hooks, structure, tone, CTAs
- **Output**: Pattern summary, update viral-patterns.md
- **Script**: `scripts/stage_2_analyze.py`

### Stage 3: Content Generation
- **Input**: Research paper (URL from Sheets column U), patterns from Stage 2
- **Action**: GLM5 generates Vietnamese content with source citation
- **Output**: Draft post with source card
- **Script**: `scripts/stage_3_generate.py`

### Stage 4: Distribution
- **Input**: Generated content from Stage 3
- **Action**: Write to "Published Content" sheet, post confirmation to Discord
- **Output**: Sheet URL + Discord message
- **Script**: `scripts/stage_4_distribute.py`

## Configuration

See `assets/config.json` for:
- Apify token and actor IDs
- Keywords (Vietnamese + English)
- Engagement thresholds (viral=5000, micro_viral=500)
- Discord channel IDs
- Google Sheet URLs
- Model selections (Gemini, GLM5)
- Budget caps (daily/monthly)

## State File

`pipeline_state.json` tracks:
- Current stage and status
- Thread IDs for Discord approval
- Data from each stage (scraped posts, patterns, content)
- Cost tracking per service
- History log

## References

- **Viral Patterns**: `references/viral-patterns.md` — Growing library of successful content patterns
- **Prompt Templates**: `references/prompt-templates.md` — Vietnamese content generation prompts

## Cost Budget

| Service | Daily Cap | Monthly Est |
|---------|-----------|-------------|
| Apify   | $0.50     | $5-10       |
| Gemini  | $0.10     | $1-3        |
| GLM5    | User endpoint | —       |

## Error Handling

- Stage failures: Save error to state, post to Discord, await manual intervention
- API limits: Check budget before API calls, abort if exceeded
- Missing data: Use defaults from config, log warning

## Pipeline Triggers

### Cron Trigger (Daily 8AM VN)

When you receive "Run content pipeline Stage 1" or similar trigger from cron:

1. Check `pipeline_state.json` — if today already has a running pipeline, report status to user
2. If no pipeline today: reset state with `python3 scripts/state_manager.py reset`
3. Run Stage 1: `python3 scripts/stage_1_scrape.py`
4. Report results to Discord #research channel

### Approval Trigger

When you receive a message in #research or #content-creation forums that references pipeline content:

1. Read `pipeline_state.json` to determine current stage and status
2. Check if message is from authorized user (admin_user_id in config.json)
3. Detect message intent:

**Approval Keywords** (proceed to next stage):
- English: approve, ok, lgtm, yes, good, proceed, continue, ✅, 👍
- Vietnamese: duyệt, đồng ý, ok, được, tốt, tiếp tục, ✅

**Rejection Keywords** (modify and retry):
- English: redo, try again, revise, fix, change, update
- Vietnamese: làm lại, sửa, chỉnh, cập nhật

**Skip Keywords** (skip current item):
- English: skip, next, pass
- Vietnamese: bỏ qua, tiếp, kế tiếp

**Stop Keywords** (pause pipeline):
- English: stop, pause, halt, cancel
- Vietnamese: dừng, tạm dừng, hủy

### Stage Transitions

When user approves:

```
Stage 1 approved → python3 scripts/stage_2_analyze.py
Stage 2 approved → python3 scripts/stage_3_generate.py
Stage 3 approved → python3 scripts/stage_4_distribute.py
Stage 4 complete → Pipeline finished, await tomorrow's cron
```

### Feedback Handling

When user provides specific feedback (not simple approval):

1. Save feedback to state: `set_feedback(feedback_text)`
2. Re-run current stage with feedback as additional context
3. Example: "Thêm thông tin về liều lượng" → re-run Stage 3 with instruction to include dosage info

### Error Recovery

If state shows a failed stage:

1. Report the error to user with details from state
2. Offer options:
   - **Retry**: Re-run failed stage script
   - **Skip**: Advance past failed stage (if applicable)
   - **Abort**: Mark pipeline as paused, await manual fix
3. On retry: Check budget limits before re-running

### State Check Commands

```bash
# Check current stage
python3 scripts/state_manager.py get-stage

# View full state
python3 scripts/state_manager.py show

# Manual advance (admin only)
python3 scripts/state_manager.py advance 2

# Reset for new day
python3 scripts/state_manager.py reset
```

## Quick Reference

| Trigger | Action |
|---------|--------|
| Daily cron 8AM | Run Stage 1 (scrape) |
| User says "approve/duyệt" | Advance to next stage |
| User gives feedback | Re-run stage with feedback |
| User says "skip/bỏ qua" | Skip current item, continue |
| User says "stop/dừng" | Pause pipeline |
| Stage fails | Report error, offer retry/skip |
