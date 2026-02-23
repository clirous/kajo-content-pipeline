# Content Pipeline - Project Overview & PDR

## Overview

Automated 4-stage content pipeline for Kajo wellness content. Transforms photobiomodulation research papers into engaging Vietnamese social media content through viral pattern analysis and AI-powered generation.

**Owner:** Kajo Agent (OpenClaw)
**Phase:** Phase 1 - Core Pipeline Infrastructure
**Status:** Active Development

---

## Product Development Requirements

### Functional Requirements

#### FR-1: Viral Content Scraping (Stage 1)
- **FR-1.1** System shall scrape Instagram posts using Apify `instagram-search-scraper` actor
- **FR-1.2** System shall scrape Facebook posts using Apify `facebook-posts-scraper` actor
- **FR-1.3** System shall filter posts by engagement threshold (default: 500+ interactions)
- **FR-1.4** System shall return top N posts sorted by engagement (configurable, default: 10)
- **FR-1.5** System shall normalize post data to standard format across platforms

#### FR-2: Pattern Analysis (Stage 2)
- **FR-2.1** System shall analyze scraped posts using Gemini 2.5 Flash
- **FR-2.2** System shall extract hook patterns, content structures, tones, and CTAs
- **FR-2.3** System shall update viral-patterns.md reference with new findings
- **FR-2.4** System shall calculate token usage and cost per analysis

#### FR-3: Content Generation (Stage 3)
- **FR-3.1** System shall read research paper URLs from Google Sheets (column U)
- **FR-3.2** System shall fetch paper content from URLs (HTML articles and PDF files)
- **FR-3.3** System shall detect paywalled content and extract abstract only
- **FR-3.4** System shall extract key quotes with page references from papers
- **FR-3.5** System shall generate Vietnamese content using GLM5 model
- **FR-3.6** System shall apply extracted patterns from Stage 2
- **FR-3.7** System shall include source citation card with title, quote, URL, page
- **FR-3.8** Content shall be 200-300 words following be Ngo persona
- **FR-3.9** System shall track token usage and cost per generation

#### FR-4: Distribution (Stage 4)
- **FR-4.1** System shall write generated content to Google Sheets "Published Content" worksheet
- **FR-4.2** System shall include metadata: date, content, source, word count, thread IDs
- **FR-4.3** System shall post confirmation to Discord channel

#### FR-5: State Management
- **FR-5.1** System shall persist pipeline state in `pipeline_state.json`
- **FR-5.2** System shall auto-reset state daily (based on date change)
- **FR-5.3** System shall archive previous day state to history folder
- **FR-5.4** System shall track costs per service (Apify, Gemini, GLM5)

#### FR-6: Discord Integration
- **FR-6.1** System shall post stage reports to designated Discord channels
- **FR-6.2** System shall await user approval (emoji reaction) before advancing
- **FR-6.3** System shall support approval timeout (default: 24 hours)

#### FR-7: Budget Control
- **FR-7.1** System shall enforce daily spending caps per service
- **FR-7.2** System shall abort API calls if budget exceeded
- **FR-7.3** Default caps: Apify $0.50/day, Gemini $0.10/day

### Non-Functional Requirements

#### NFR-1: Performance
- **NFR-1.1** Scraping shall complete within 2 minutes
- **NFR-1.2** Pattern analysis shall complete within 30 seconds
- **NFR-1.3** Paper fetching shall complete within 30 seconds
- **NFR-1.4** Content generation shall complete within 2 minutes

#### NFR-2: Reliability
- **NFR-2.1** System shall handle API failures gracefully with error logging
- **NFR-2.2** System shall preserve state on failure for manual recovery
- **NFR-2.3** System shall validate configuration before execution

#### NFR-3: Maintainability
- **NFR-3.1** All configuration in single `config.json` file
- **NFR-3.2** Modular utilities for external services (Apify, Sheets, Discord)
- **NFR-3.3** CLI interfaces for all scripts

#### NFR-4: Cost Efficiency
- **NFR-4.1** Daily operational cost shall not exceed $1.00
- **NFR-4.2** Monthly operational cost shall not exceed $20.00

---

## Technical Constraints

1. **Python 3.8+** - All scripts written in Python
2. **External APIs** - Apify, Google Sheets, Discord, Gemini, GLM5
3. **Environment Variables** - Sensitive credentials via ENV variables
4. **JSON State** - File-based state persistence (no database)

---

## Dependencies

| Package | Purpose |
|---------|---------|
| apify-client | Apify API integration |
| gspread | Google Sheets integration |
| google-auth | Google authentication |
| google-genai | Gemini API |
| requests | HTTP client for Gemini/GLM5 APIs |
| pypdf | PDF text extraction |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Pipeline completion rate | >90% |
| Daily cost | <$1.00 |
| Content quality approval | >80% |
| Time to complete full pipeline | <5 minutes |

---

## Milestones

### Phase 1: Core Infrastructure (Complete)
- [x] State management system
- [x] Configuration validation
- [x] Apify client wrapper
- [x] Google Sheets client wrapper
- [x] Discord formatting utilities
- [x] Reference documentation (patterns, templates)

### Phase 2: Stage 1-2 Scripts (Complete)
- [x] Stage 1: scrape.py - Apify scraping with Discord notification
- [x] Stage 2: analyze.py - Gemini pattern analysis
- [x] Gemini client utility with retry logic
- [x] viral-patterns.md auto-update
- [x] Unit tests for Stage 2

### Phase 3: Stage 3 Content Generation (Complete)
- [x] GLM5 client utility with OpenAI-compatible format
- [x] Paper fetcher utility (HTML/PDF extraction)
- [x] Stage 3: generate.py - GLM5 content generation
- [x] Source card formatting with Vietnamese citation
- [x] Unit tests for Stage 3 (test_phase4.py)

### Phase 4: Distribution (Planned)
- [ ] Stage 4: distribute.py - Google Sheets distribution

### Phase 5: Integration (Planned)
- [ ] Discord bot integration
- [ ] Cron scheduling
- [ ] Error notifications
- [ ] Monitoring dashboard

---

*Last updated: 2026-02-23*
*Phase: 4 - Stage 3 Content Generation Complete*
