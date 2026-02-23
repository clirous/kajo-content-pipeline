# Code Review: stage_1_scrape.py

## Scope
- **File reviewed:** `/Users/digitaly/.openclaw/agents/kajo/agent/skills/content-pipeline/scripts/stage_1_scrape.py`
- **Lines of code:** 315
- **Related modules:** `state_manager.py`, `apify_client.py`, `discord_fmt.py`, `config.json`
- **Review focus:** Phase 2 Stage 1 implementation - security, architecture, code quality, error handling, budget enforcement

---

## Overall Assessment

**Score: 7.5/10**

The implementation follows established patterns from Phase 1 utilities, integrates cleanly with `state_manager.py` and `apify_client.py`, and implements the core workflow correctly. However, there are several issues around error handling consistency, budget check placement, and potential runtime problems that need attention.

---

## Critical Issues (MUST FIX)

### 1. Budget Check Race Condition (Lines 88-91)
```python
# Check budget after Instagram
if not dry_run and all_posts:
    ig_cost = estimate_cost(ig_count, "instagram")
    if not sm.check_budget("apify", config):
```

**Problem:** `ig_cost` is calculated but never used. The budget check happens BEFORE cost is recorded, so if IG scraping already consumed budget, the check reads stale state.

**Fix:**
```python
if not dry_run and all_posts:
    ig_cost = estimate_cost(ig_count, "instagram")
    sm.record_cost("apify", ig_cost)  # Record cost BEFORE checking
    if not sm.check_budget("apify", config):
        print("Budget cap reached after Instagram, skipping Facebook")
```

### 2. Missing Error Recovery on Stage Mismatch (Lines 49-52)
```python
if current_stage != 1:
    result["error"] = f"Expected stage 1, currently at stage {current_stage}"
    return result
```

**Problem:** Returns early without setting status to `failed`. State remains in inconsistent state.

**Fix:**
```python
if current_stage != 1:
    result["error"] = f"Expected stage 1, currently at stage {current_stage}"
    sm.set_status("failed")
    return result
```

### 3. Status Not Set on Partial Failure (Line 169)
```python
sm.set_status("awaiting_approval")
result["success"] = True
```

**Problem:** Always sets `success=True` even if scraping returned 0 posts or Discord posting failed.

**Fix:** Add conditional:
```python
if result["posts"] or dry_run:
    sm.set_status("awaiting_approval")
    result["success"] = True
else:
    sm.set_status("failed")
    result["error"] = result.get("error") or "No posts found"
```

---

## Warnings (SHOULD FIX)

### 4. Unused Import (Line 8)
```python
from datetime import datetime
```
Used in `_post_to_discord` but imported at top level. Consider moving inside function or keeping for consistency.

### 5. Unused Function `_format_post_for_display` (Lines 255-276)
Entire function is defined but never called. Dead code violates YAGNI.

**Action:** Remove or document intended use.

### 6. Hardcoded Thread ID Placeholder (Line 215)
```python
return f"thread_{today}"
```

**Problem:** Returns fake thread ID instead of parsing actual ID from `openclaw` CLI output. This breaks Discord reply threading for Stage 2.

**Fix:** Parse actual thread ID from stdout or return `None` with warning:
```python
# Try to parse thread ID from output
import re
match = re.search(r'thread[:\s]+(\d+)', output, re.IGNORECASE)
if match:
    return match.group(1)
print("Warning: Could not parse thread ID from Discord response")
return None
```

### 7. Missing Validation for Empty Keywords (Lines 63-66)
```python
keywords_vi = config.get("keywords", {}).get("vi", [])
keywords_en = config.get("keywords", {}).get("en", [])
keywords = keywords_vi + keywords_en
```

**Problem:** If both lists are empty, scraping runs with no keywords, wasting API calls.

**Fix:**
```python
keywords = keywords_vi + keywords_en
if not keywords:
    result["error"] = "No keywords configured"
    sm.set_status("failed")
    return result
```

### 8. Inconsistent Error Return Pattern
`_post_to_discord` returns `None` on failure, but `_post_error_to_discord` has no return value. Main function doesn't check if error posting succeeded.

**Recommendation:** Either log failures or return bool to indicate success.

---

## Suggestions (NICE TO HAVE)

### 9. Type Hints Missing for `config` Parameter
Functions `_post_to_discord` and `_post_error_to_discord` use `config: dict` but should use `Dict[str, Any]` for consistency with other modules.

### 10. Magic Numbers in Output
Line 79: `keywords[:5]` appears twice. Consider extracting to constant:
```python
MAX_KEYWORDS_PER_RUN = 5
```

### 11. Add Retry Logic for Discord Posting
Discord API can be flaky. Consider adding 1 retry with backoff:
```python
for attempt in range(2):
    result = subprocess.run(...)
    if result.returncode == 0:
        break
    time.sleep(2 ** attempt)
```

### 12. Log File Output
All `print()` statements go to stdout. For cron execution, consider adding logging module with file handler.

---

## Positive Observations

1. **Clean integration** with Phase 1 utilities (`state_manager`, `apify_client`, `discord_fmt`)
2. **Proper use of ENV: prefix** for secrets via `_load_config()`
3. **Defensive programming** in `_post_to_discord` with timeout and FileNotFoundError handling
4. **Clear CLI interface** with `--dry-run` and `--show-state` options
5. **Consistent docstrings** following project standards
6. **Result dictionary structure** is well-designed with all required fields
7. **Deduplication logic** (lines 110-117) properly handles URL collisions

---

## Security Audit

| Check | Status | Notes |
|-------|--------|-------|
| Hardcoded secrets | PASS | Uses `ENV:APIFY_TOKEN` pattern |
| SQL/XSS injection | N/A | No user input to DB/HTML |
| Command injection | PASS | `subprocess.run` with list args |
| Input validation | WARN | Empty keywords not validated |
| Error message leakage | PASS | No secrets in error output |
| Timeout protection | PASS | 30s timeout on Discord calls |

---

## Compliance with Project Standards

| Standard | Status | Notes |
|----------|--------|-------|
| PEP 8 formatting | PASS | |
| Type hints | PARTIAL | Missing on helper functions |
| Docstrings | PASS | All public functions documented |
| Error handling pattern | PARTIAL | Missing status updates on failure |
| CLI interface pattern | PASS | Follows established pattern |
| Config access pattern | PASS | Uses `.get()` with defaults |

---

## Recommended Actions

1. **[HIGH]** Fix budget check race condition (record cost before checking)
2. **[HIGH]** Add `sm.set_status("failed")` on stage mismatch and empty results
3. **[MEDIUM]** Add validation for empty keywords before scraping
4. **[MEDIUM]** Remove unused `_format_post_for_display` function
5. **[MEDIUM]** Fix thread ID parsing to return actual Discord thread ID
6. **[LOW]** Add retry logic for Discord posting
7. **[LOW]** Consider logging module for cron execution

---

## Metrics

- **Type Coverage:** ~85% (missing on some helper functions)
- **Test Coverage:** Not available (no tests found)
- **Linting Issues:** Not run (no pylintrc found)
- **Complexity Score:** Low (good - straightforward flow)

---

## Unresolved Questions

1. Should `_post_error_to_discord` return success/failure status?
2. Is `openclaw` CLI expected to return thread ID in a specific format?
3. Should empty results (0 posts) be treated as success or failure?

---

*Review completed: 2026-02-23*
*Reviewer: code-reviewer subagent*
