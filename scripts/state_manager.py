#!/usr/bin/env python3
"""Pipeline state manager for tracking content pipeline progress across sessions."""

import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Any, Optional

# State file location (relative to this script)
SKILL_DIR = Path(__file__).parent.parent
STATE_FILE = SKILL_DIR / "pipeline_state.json"
CONFIG_FILE = SKILL_DIR / "assets" / "config.json"


def _get_default_state() -> dict:
    """Return default state structure for a new day."""
    return {
        "current_date": date.today().isoformat(),
        "stage": 1,
        "status": "pending",
        "thread_ids": {
            "stage_1": None,
            "stage_2": None,
            "stage_3": None,
            "stage_4": None
        },
        "data": {
            "scraped_posts": [],
            "patterns": {},
            "generated_content": None,
            "distributed": False
        },
        "cost_tracking": {
            "apify": 0.0,
            "gemini": 0.0,
            "glm5": 0.0
        },
        "history": []
    }


def load_state() -> dict:
    """Load pipeline state from file. Create default if not exists."""
    if not STATE_FILE.exists():
        return _get_default_state()

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    # Reset if it's a new day
    if state.get("current_date") != date.today().isoformat():
        return reset_daily()

    return state


def save_state(state: dict) -> None:
    """Save pipeline state to file."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _read_state_file() -> Optional[dict]:
    """Read state file directly without triggering reset. Returns None if not exists."""
    if not STATE_FILE.exists():
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def reset_daily() -> dict:
    """Create fresh state for new day. Archive previous state to history."""
    # Read old state directly without triggering recursion
    old_state = _read_state_file()

    if old_state is not None:
        # Archive completed state to history if any progress was made
        if old_state.get("stage", 1) > 1 or old_state.get("status") != "pending":
            history_file = SKILL_DIR / "history" / f"state_{old_state['current_date']}.json"
            history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(old_state, f, indent=2, ensure_ascii=False)

    new_state = _get_default_state()
    save_state(new_state)
    return new_state


def advance_stage(stage_num: int) -> dict:
    """Update stage and set status to pending."""
    state = load_state()
    old_stage = state["stage"]

    if stage_num <= old_stage:
        raise ValueError(f"Cannot advance to stage {stage_num}, already at stage {old_stage}")

    state["stage"] = stage_num
    state["status"] = "pending"
    state["history"].append({
        "timestamp": datetime.now().isoformat(),
        "action": f"advanced_to_stage_{stage_num}",
        "from_stage": old_stage
    })
    save_state(state)
    return state


def get_current_stage() -> int:
    """Return current pipeline stage (1-4)."""
    state = load_state()
    return state.get("stage", 1)


def set_status(status: str) -> dict:
    """Set pipeline status (pending, in_progress, completed, failed)."""
    state = load_state()
    state["status"] = status
    state["history"].append({
        "timestamp": datetime.now().isoformat(),
        "action": f"status_set_{status}"
    })
    save_state(state)
    return state


def record_cost(service: str, amount: float) -> dict:
    """Track spending for a service."""
    state = load_state()
    if service not in state["cost_tracking"]:
        state["cost_tracking"][service] = 0.0
    state["cost_tracking"][service] += amount
    state["history"].append({
        "timestamp": datetime.now().isoformat(),
        "action": f"cost_recorded",
        "service": service,
        "amount": amount
    })
    save_state(state)
    return state


def add_data(stage: int, data: Any) -> dict:
    """Store stage output for use by next stage."""
    state = load_state()

    if stage == 1:
        state["data"]["scraped_posts"] = data
    elif stage == 2:
        state["data"]["patterns"] = data
    elif stage == 3:
        state["data"]["generated_content"] = data
    elif stage == 4:
        state["data"]["distributed"] = data

    state["history"].append({
        "timestamp": datetime.now().isoformat(),
        "action": f"data_added_stage_{stage}",
        "data_type": type(data).__name__
    })
    save_state(state)
    return state


def get_data(stage: int) -> Any:
    """Get stored data from a specific stage."""
    state = load_state()

    if stage == 1:
        return state["data"].get("scraped_posts", [])
    elif stage == 2:
        return state["data"].get("patterns", {})
    elif stage == 3:
        return state["data"].get("generated_content")
    elif stage == 4:
        return state["data"].get("distributed", False)
    return None


def set_thread_id(stage: int, thread_id: str) -> dict:
    """Store Discord thread ID for a stage."""
    state = load_state()
    state["thread_ids"][f"stage_{stage}"] = thread_id
    save_state(state)
    return state


def get_thread_id(stage: int) -> Optional[str]:
    """Get Discord thread ID for a stage."""
    state = load_state()
    return state["thread_ids"].get(f"stage_{stage}")


def is_today_started() -> bool:
    """Check if pipeline has already started today."""
    state = load_state()
    return state.get("status") not in ("pending", None)


def get_status() -> str:
    """Get current pipeline status."""
    state = load_state()
    return state.get("status", "pending")


def set_feedback(feedback: str) -> dict:
    """Store user feedback for current stage re-run."""
    state = load_state()
    state["feedback"] = feedback
    state["history"].append({
        "timestamp": datetime.now().isoformat(),
        "action": "feedback_set",
        "feedback": feedback[:100]  # Truncate for log
    })
    save_state(state)
    return state


def get_feedback() -> Optional[str]:
    """Get stored feedback for current stage."""
    state = load_state()
    return state.get("feedback")


def clear_feedback() -> dict:
    """Clear stored feedback after re-run."""
    state = load_state()
    if "feedback" in state:
        del state["feedback"]
    save_state(state)
    return state


def mark_awaiting_approval() -> dict:
    """Mark current stage as awaiting approval."""
    return set_status("awaiting_approval")


def mark_failed(error_msg: str) -> dict:
    """Mark pipeline as failed with error message."""
    state = load_state()
    state["status"] = "failed"
    state["error"] = error_msg
    state["history"].append({
        "timestamp": datetime.now().isoformat(),
        "action": "marked_failed",
        "error": error_msg[:100]
    })
    save_state(state)
    return state


def is_approval_keyword(message: str) -> bool:
    """Check if message contains approval keywords."""
    message_lower = message.lower().strip()
    approval_keywords = [
        # English
        "approve", "approved", "ok", "lgtm", "yes", "good", "proceed",
        "continue", "go ahead", "done", "next",
        # Vietnamese
        "duyệt", "đồng ý", "được", "tốt", "tiếp tục", "xong",
        # Emoji
        "✅", "👍", "👌"
    ]
    return any(kw in message_lower for kw in approval_keywords)


def is_rejection_keyword(message: str) -> bool:
    """Check if message contains rejection/revision keywords."""
    message_lower = message.lower().strip()
    rejection_keywords = [
        # English
        "redo", "try again", "revise", "fix", "change", "update", "edit",
        "no", "not", "wrong", "issue", "problem",
        # Vietnamese
        "làm lại", "sửa", "chỉnh", "cập nhật", "không", "sai"
    ]
    return any(kw in message_lower for kw in rejection_keywords)


def is_skip_keyword(message: str) -> bool:
    """Check if message contains skip keywords."""
    message_lower = message.lower().strip()
    skip_keywords = [
        # English
        "skip", "next", "pass",
        # Vietnamese
        "bỏ qua", "tiếp", "kế tiếp"
    ]
    return any(kw in message_lower for kw in skip_keywords)


def is_stop_keyword(message: str) -> bool:
    """Check if message contains stop keywords."""
    message_lower = message.lower().strip()
    stop_keywords = [
        # English
        "stop", "pause", "halt", "cancel", "abort",
        # Vietnamese
        "dừng", "tạm dừng", "hủy", "ngừng"
    ]
    return any(kw in message_lower for kw in stop_keywords)


def check_budget(service: str, config: Optional[dict] = None) -> bool:
    """Check if budget allows another API call for service."""
    if config is None:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

    state = load_state()
    budget = config.get("budget", {})
    current_cost = state["cost_tracking"].get(service, 0.0)

    if service == "apify":
        daily_cap = budget.get("daily_apify_cap_usd", 0.50)
    elif service == "gemini":
        daily_cap = budget.get("daily_gemini_cap_usd", 0.10)
    elif service == "glm5":
        daily_cap = budget.get("daily_glm5_cap_usd", 0.20)
    else:
        return True  # Unknown service, allow

    return current_cost < daily_cap


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: state_manager.py <command> [args]")
        print("Commands: get-stage, reset, advance <num>, status <status>, show")
        print("          started, feedback <text>, clear-feedback, check-keyword <msg>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "get-stage":
        print(get_current_stage())
    elif cmd == "reset":
        state = reset_daily()
        print(f"Reset state for {state['current_date']}")
    elif cmd == "advance" and len(sys.argv) > 2:
        stage = int(sys.argv[2])
        state = advance_stage(stage)
        print(f"Advanced to stage {state['stage']}")
    elif cmd == "status" and len(sys.argv) > 2:
        status = sys.argv[2]
        state = set_status(status)
        print(f"Status set to {state['status']}")
    elif cmd == "show":
        state = load_state()
        print(json.dumps(state, indent=2, ensure_ascii=False))
    elif cmd == "started":
        print(is_today_started())
    elif cmd == "feedback" and len(sys.argv) > 2:
        feedback = " ".join(sys.argv[2:])
        state = set_feedback(feedback)
        print(f"Feedback saved: {feedback[:50]}...")
    elif cmd == "clear-feedback":
        state = clear_feedback()
        print("Feedback cleared")
    elif cmd == "check-keyword" and len(sys.argv) > 2:
        msg = " ".join(sys.argv[2:])
        if is_approval_keyword(msg):
            print("approval")
        elif is_rejection_keyword(msg):
            print("rejection")
        elif is_skip_keyword(msg):
            print("skip")
        elif is_stop_keyword(msg):
            print("stop")
        else:
            print("unknown")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
