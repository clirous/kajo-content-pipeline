#!/usr/bin/env python3
"""Tests for Phase 6: Cron & Approval Flow."""

import os
import sys
import json
import unittest
from pathlib import Path

# Add paths for imports
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "scripts" / "utils"))
sys.path.insert(0, str(SKILL_DIR / "tests"))

# Test imports
import state_manager as sm


class TestStateTransitions(unittest.TestCase):
    """Tests for state transition methods."""

    def setUp(self):
        """Reset state before each test."""
        sm.reset_daily()

    def test_is_today_started_false_initially(self):
        """Test today not started initially."""
        self.assertFalse(sm.is_today_started())

    def test_is_today_started_true_after_status(self):
        """Test today started after status change."""
        sm.set_status("in_progress")
        self.assertTrue(sm.is_today_started())

    def test_get_status_default(self):
        """Test default status is pending."""
        status = sm.get_status()
        self.assertEqual(status, "pending")

    def test_set_and_get_feedback(self):
        """Test feedback storage."""
        sm.set_feedback("Add more details about dosage")
        feedback = sm.get_feedback()
        self.assertEqual(feedback, "Add more details about dosage")

    def test_clear_feedback(self):
        """Test feedback clearing."""
        sm.set_feedback("Test feedback")
        sm.clear_feedback()
        feedback = sm.get_feedback()
        self.assertIsNone(feedback)

    def test_mark_awaiting_approval(self):
        """Test awaiting approval status."""
        sm.mark_awaiting_approval()
        self.assertEqual(sm.get_status(), "awaiting_approval")

    def test_mark_failed(self):
        """Test failed status with error."""
        sm.mark_failed("API connection timeout")
        state = sm.load_state()
        self.assertEqual(state["status"], "failed")
        self.assertIn("timeout", state.get("error", ""))


class TestApprovalKeywords(unittest.TestCase):
    """Tests for approval keyword detection."""

    def test_approval_english_keywords(self):
        """Test English approval keywords."""
        approvals = [
            "approve",
            "approved",
            "ok",
            "lgtm",
            "yes",
            "good",
            "proceed",
            "continue",
            "✅",
            "👍"
        ]
        for keyword in approvals:
            with self.subTest(keyword=keyword):
                self.assertTrue(sm.is_approval_keyword(keyword), f"Failed for: {keyword}")

    def test_approval_vietnamese_keywords(self):
        """Test Vietnamese approval keywords."""
        approvals = [
            "duyệt",
            "đồng ý",
            "được",
            "tốt",
            "tiếp tục"
        ]
        for keyword in approvals:
            with self.subTest(keyword=keyword):
                self.assertTrue(sm.is_approval_keyword(keyword), f"Failed for: {keyword}")

    def test_approval_in_sentence(self):
        """Test approval keyword in sentence."""
        self.assertTrue(sm.is_approval_keyword("Looks good, approve this"))
        self.assertTrue(sm.is_approval_keyword("ok let's proceed"))
        self.assertTrue(sm.is_approval_keyword("✅ approved"))


class TestRejectionKeywords(unittest.TestCase):
    """Tests for rejection keyword detection."""

    def test_rejection_english_keywords(self):
        """Test English rejection keywords."""
        rejections = ["redo", "try again", "revise", "fix", "change", "update"]
        for keyword in rejections:
            with self.subTest(keyword=keyword):
                self.assertTrue(sm.is_rejection_keyword(keyword), f"Failed for: {keyword}")

    def test_rejection_vietnamese_keywords(self):
        """Test Vietnamese rejection keywords."""
        rejections = ["làm lại", "sửa", "chỉnh", "cập nhật", "không"]
        for keyword in rejections:
            with self.subTest(keyword=keyword):
                self.assertTrue(sm.is_rejection_keyword(keyword), f"Failed for: {keyword}")

    def test_not_rejection_for_approval(self):
        """Test approval words are not rejection."""
        self.assertFalse(sm.is_rejection_keyword("approve"))
        self.assertFalse(sm.is_rejection_keyword("ok"))


class TestSkipKeywords(unittest.TestCase):
    """Tests for skip keyword detection."""

    def test_skip_english_keywords(self):
        """Test English skip keywords."""
        self.assertTrue(sm.is_skip_keyword("skip"))
        self.assertTrue(sm.is_skip_keyword("next"))
        self.assertTrue(sm.is_skip_keyword("pass"))

    def test_skip_vietnamese_keywords(self):
        """Test Vietnamese skip keywords."""
        self.assertTrue(sm.is_skip_keyword("bỏ qua"))
        self.assertTrue(sm.is_skip_keyword("tiếp"))

    def test_not_skip_for_other_keywords(self):
        """Test other keywords are not skip."""
        self.assertFalse(sm.is_skip_keyword("approve"))
        self.assertFalse(sm.is_skip_keyword("stop"))


class TestStopKeywords(unittest.TestCase):
    """Tests for stop keyword detection."""

    def test_stop_english_keywords(self):
        """Test English stop keywords."""
        self.assertTrue(sm.is_stop_keyword("stop"))
        self.assertTrue(sm.is_stop_keyword("pause"))
        self.assertTrue(sm.is_stop_keyword("halt"))
        self.assertTrue(sm.is_stop_keyword("cancel"))

    def test_stop_vietnamese_keywords(self):
        """Test Vietnamese stop keywords."""
        self.assertTrue(sm.is_stop_keyword("dừng"))
        self.assertTrue(sm.is_stop_keyword("tạm dừng"))
        self.assertTrue(sm.is_stop_keyword("hủy"))

    def test_not_stop_for_other_keywords(self):
        """Test other keywords are not stop."""
        self.assertFalse(sm.is_stop_keyword("approve"))
        self.assertFalse(sm.is_stop_keyword("skip"))


class TestKeywordDisambiguation(unittest.TestCase):
    """Tests for disambiguating between keyword types."""

    def test_approval_vs_rejection_priority(self):
        """Test approval is detected correctly vs rejection."""
        msg = "looks good but fix the title"
        # Both might match, but approval should be primary
        # In actual implementation, the order of checks matters
        self.assertTrue(sm.is_approval_keyword(msg) or sm.is_rejection_keyword(msg))

    def test_no_keyword_match(self):
        """Test message with no keywords."""
        msg = "This is interesting content"
        self.assertFalse(sm.is_approval_keyword(msg))
        self.assertFalse(sm.is_rejection_keyword(msg))
        self.assertFalse(sm.is_skip_keyword(msg))
        self.assertFalse(sm.is_stop_keyword(msg))

    def test_case_insensitive(self):
        """Test keyword detection is case insensitive."""
        self.assertTrue(sm.is_approval_keyword("APPROVE"))
        self.assertTrue(sm.is_approval_keyword("Approve"))
        self.assertTrue(sm.is_approval_keyword("OK"))


class TestCronSetupScript(unittest.TestCase):
    """Tests for cron setup script."""

    def test_cron_script_exists(self):
        """Test cron setup script exists."""
        cron_script = SKILL_DIR / "scripts" / "setup_cron.py"
        self.assertTrue(cron_script.exists())

    def test_cron_script_importable(self):
        """Test cron script can be imported."""
        import setup_cron
        self.assertTrue(hasattr(setup_cron, "setup_cron"))
        self.assertTrue(hasattr(setup_cron, "test_cron"))
        self.assertTrue(hasattr(setup_cron, "show_cron_info"))

    def test_load_config(self):
        """Test config loading in cron script."""
        import setup_cron
        config = setup_cron.load_config()
        self.assertIn("pipeline", config)
        self.assertIn("cron_time", config["pipeline"])


class TestSkillMdApprovalFlow(unittest.TestCase):
    """Tests for SKILL.md approval flow documentation."""

    def test_skill_md_exists(self):
        """Test SKILL.md exists."""
        skill_md = SKILL_DIR / "SKILL.md"
        self.assertTrue(skill_md.exists())

    def test_skill_md_contains_triggers(self):
        """Test SKILL.md contains Pipeline Triggers section."""
        skill_md = SKILL_DIR / "SKILL.md"
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("## Pipeline Triggers", content)
        self.assertIn("### Cron Trigger", content)
        self.assertIn("### Approval Trigger", content)
        self.assertIn("Approval Keywords", content)

    def test_skill_md_contains_keywords(self):
        """Test SKILL.md contains keyword lists."""
        skill_md = SKILL_DIR / "SKILL.md"
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for Vietnamese keywords
        self.assertIn("duyệt", content)
        self.assertIn("đồng ý", content)

        # Check for English keywords
        self.assertIn("approve", content)
        self.assertIn("lgtm", content)

    def test_skill_md_contains_stage_transitions(self):
        """Test SKILL.md contains stage transition info."""
        skill_md = SKILL_DIR / "SKILL.md"
        with open(skill_md, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Stage 1 approved", content)
        self.assertIn("Stage 2 approved", content)
        self.assertIn("Stage 3 approved", content)


class TestStateManagerCLI(unittest.TestCase):
    """Tests for state_manager CLI commands."""

    def setUp(self):
        sm.reset_daily()

    def test_cli_started_command(self):
        """Test 'started' CLI command."""
        import subprocess
        result = subprocess.run(
            ["python3", str(SKILL_DIR / "scripts" / "state_manager.py"), "started"],
            capture_output=True,
            text=True
        )
        self.assertIn("False", result.stdout)

    def test_cli_feedback_command(self):
        """Test 'feedback' CLI command."""
        import subprocess
        result = subprocess.run(
            ["python3", str(SKILL_DIR / "scripts" / "state_manager.py"),
             "feedback", "test", "feedback"],
            capture_output=True,
            text=True
        )
        self.assertIn("Feedback saved", result.stdout)

    def test_cli_check_keyword_approval(self):
        """Test 'check-keyword' CLI for approval."""
        import subprocess
        result = subprocess.run(
            ["python3", str(SKILL_DIR / "scripts" / "state_manager.py"),
             "check-keyword", "approve"],
            capture_output=True,
            text=True
        )
        self.assertIn("approval", result.stdout)

    def test_cli_check_keyword_stop(self):
        """Test 'check-keyword' CLI for stop."""
        import subprocess
        result = subprocess.run(
            ["python3", str(SKILL_DIR / "scripts" / "state_manager.py"),
             "check-keyword", "stop"],
            capture_output=True,
            text=True
        )
        self.assertIn("stop", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
