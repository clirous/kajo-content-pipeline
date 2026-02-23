#!/usr/bin/env python3
"""Tests for Phase 5: Stage 4 Distribution."""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add paths for imports
SKILL_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(SKILL_DIR / "scripts" / "utils"))
sys.path.insert(0, str(SKILL_DIR / "tests"))

# Test imports
import state_manager as sm


class TestStage4Distribute(unittest.TestCase):
    """Tests for stage_4_distribute.py."""

    def setUp(self):
        """Set up test fixtures."""
        sm.reset_daily()

    def test_format_completion_message(self):
        """Test completion message formatting."""
        import stage_4_distribute

        msg = stage_4_distribute._format_completion_message(
            source_title="Test Paper",
            source_url="https://example.com/paper",
            total_cost=0.05,
            cost_breakdown={"apify": 0.02, "gemini": 0.02, "glm5": 0.01},
            thread_3="thread_123"
        )

        self.assertIn("Pipeline Complete", msg)
        self.assertIn("Test Paper", msg)
        self.assertIn("$0.05", msg)
        self.assertIn("Apify", msg)
        self.assertIn("Gemini", msg)

    def test_format_completion_message_zero_cost(self):
        """Test completion message with zero costs."""
        import stage_4_distribute

        msg = stage_4_distribute._format_completion_message(
            source_title="Test",
            source_url="https://example.com",
            total_cost=0.0,
            cost_breakdown={},
            thread_3=None
        )

        self.assertIn("$0.00", msg)

    @patch('stage_4_distribute._post_to_discord')
    @patch('stage_4_distribute.write_published_content')
    def test_run_stage_4_dry_run(self, mock_write, mock_discord):
        """Test dry run doesn't write to sheets."""
        import stage_4_distribute

        sm.advance_stage(4)
        sm.add_data(3, {
            "content": "Test content",
            "source_title": "Test Paper",
            "source_url": "https://example.com",
            "word_count": 100
        })

        result = stage_4_distribute.run_stage_4(dry_run=True)

        # Should not call external services
        mock_write.assert_not_called()
        mock_discord.assert_not_called()

        self.assertTrue(result["success"])

    def test_run_stage_4_wrong_stage(self):
        """Test Stage 4 fails when not at stage 4."""
        import stage_4_distribute

        # Should be at stage 1 by default
        result = stage_4_distribute.run_stage_4(dry_run=True)

        self.assertFalse(result["success"])
        self.assertIn("Expected stage 4", result["error"])

    @patch('stage_4_distribute._post_to_discord')
    @patch('stage_4_distribute.write_published_content')
    def test_run_stage_4_no_content(self, mock_write, mock_discord):
        """Test Stage 4 fails when no content from Stage 3."""
        import stage_4_distribute

        sm.advance_stage(4)
        # Don't add Stage 3 data

        result = stage_4_distribute.run_stage_4(dry_run=False)

        self.assertFalse(result["success"])
        self.assertIn("No generated content", result["error"])

    @patch('stage_4_distribute._post_to_discord')
    @patch('stage_4_distribute.write_published_content')
    def test_run_stage_4_sheet_write_fails(self, mock_write, mock_discord):
        """Test Stage 4 handles sheet write failure."""
        import stage_4_distribute

        sm.advance_stage(4)
        sm.add_data(3, {
            "content": "Test content",
            "source_title": "Test",
            "source_url": "https://example.com",
            "word_count": 100
        })

        mock_write.return_value = False

        result = stage_4_distribute.run_stage_4(dry_run=False)

        self.assertFalse(result["success"])
        self.assertIn("Google Sheets", result["error"])

    @patch('stage_4_distribute._post_to_discord')
    @patch('stage_4_distribute.write_published_content')
    @patch('stage_4_distribute._archive_completed_state')
    def test_run_stage_4_success(self, mock_archive, mock_write, mock_discord):
        """Test successful Stage 4 execution."""
        import stage_4_distribute

        sm.advance_stage(4)
        sm.add_data(3, {
            "content": "Test content here for distribution",
            "source_title": "Research Paper Title",
            "source_url": "https://example.com/paper",
            "word_count": 100
        })
        sm.set_thread_id(1, "thread_1")
        sm.set_thread_id(2, "thread_2")
        sm.set_thread_id(3, "thread_3")
        sm.record_cost("apify", 0.02)
        sm.record_cost("gemini", 0.02)

        mock_write.return_value = True
        mock_discord.return_value = "confirm_123"

        result = stage_4_distribute.run_stage_4(dry_run=False)

        self.assertTrue(result["success"])
        self.assertTrue(result["row_written"])
        self.assertEqual(result["total_cost"], 0.04)
        mock_archive.assert_called_once()

    @patch('stage_4_distribute._post_to_discord')
    @patch('stage_4_distribute.write_published_content')
    def test_run_stage_4_truncates_long_content(self, mock_write, mock_discord):
        """Test Stage 4 truncates content exceeding limit."""
        import stage_4_distribute

        sm.advance_stage(4)

        # Create very long content
        long_content = "x" * 50000
        sm.add_data(3, {
            "content": long_content,
            "source_title": "Test",
            "source_url": "https://example.com",
            "word_count": 10000
        })

        mock_write.return_value = True
        mock_discord.return_value = "confirm"

        result = stage_4_distribute.run_stage_4(dry_run=False)

        self.assertTrue(result["success"])
        # Check that write_published_content was called with truncated content
        call_args = mock_write.call_args[1]["content_data"]
        self.assertLess(len(call_args["content"]), 50000)


class TestSheetsClientDistribution(unittest.TestCase):
    """Tests for sheets_client distribution functionality."""

    def setUp(self):
        sm.reset_daily()

    @patch('sheets_client._init_client')
    def test_write_published_content_new_worksheet(self, mock_init):
        """Test creating new worksheet for published content."""
        from sheets_client import write_published_content

        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        # Simulate WorksheetNotFound
        mock_gs = MagicMock()
        mock_gs.WorksheetNotFound = Exception
        mock_spreadsheet.worksheet.side_effect = mock_gs.WorksheetNotFound()
        mock_spreadsheet.add_worksheet.return_value = mock_worksheet

        mock_client.open_by_url.return_value = mock_spreadsheet
        mock_init.return_value = mock_client

        with patch('sheets_client._get_gspread', return_value=mock_gs):
            result = write_published_content(
                sheet_url="https://sheets.google.com/test",
                content_data={
                    "date": "2026-02-23",
                    "content": "Test content",
                    "source_title": "Test Paper",
                    "source_url": "https://example.com",
                    "word_count": 100,
                    "status": "published",
                    "total_cost": 0.05
                }
            )

        self.assertTrue(result)
        # Verify headers were added
        mock_worksheet.append_row.assert_called()

    @patch('sheets_client._init_client')
    def test_write_published_content_existing_worksheet(self, mock_init):
        """Test writing to existing worksheet."""
        from sheets_client import write_published_content

        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_client.open_by_url.return_value = mock_spreadsheet
        mock_init.return_value = mock_client

        result = write_published_content(
            sheet_url="https://sheets.google.com/test",
            content_data={
                "date": "2026-02-23",
                "content": "Test content",
                "source_title": "Test Paper",
                "source_url": "https://example.com",
                "word_count": 100,
                "total_cost": 0.05
            }
        )

        self.assertTrue(result)
        mock_worksheet.append_row.assert_called_once()

    def test_write_published_content_no_url(self):
        """Test write fails without URL."""
        from sheets_client import write_published_content

        result = write_published_content(
            sheet_url="PLACEHOLDER_URL",
            content_data={"content": "test"}
        )

        self.assertFalse(result)

    @patch('sheets_client._init_client')
    def test_write_published_content_includes_cost(self, mock_init):
        """Test that total_cost is included in row data."""
        from sheets_client import write_published_content

        mock_client = MagicMock()
        mock_spreadsheet = MagicMock()
        mock_worksheet = MagicMock()

        mock_spreadsheet.worksheet.return_value = mock_worksheet
        mock_client.open_by_url.return_value = mock_spreadsheet
        mock_init.return_value = mock_client

        result = write_published_content(
            sheet_url="https://sheets.google.com/test",
            content_data={
                "date": "2026-02-23",
                "content": "Test",
                "source_title": "Test",
                "source_url": "https://example.com",
                "word_count": 100,
                "total_cost": 0.1234
            }
        )

        self.assertTrue(result)
        # Verify the row includes cost
        call_args = mock_worksheet.append_row.call_args[0][0]
        self.assertIn(0.1234, call_args)


class TestStateManagerDistribution(unittest.TestCase):
    """Tests for state manager distribution functions."""

    def setUp(self):
        sm.reset_daily()

    def test_status_completed(self):
        """Test setting status to completed."""
        sm.set_status("completed")
        state = sm.load_state()
        self.assertEqual(state["status"], "completed")

    def test_cost_tracking_accumulates(self):
        """Test that costs accumulate correctly."""
        sm.record_cost("apify", 0.01)
        sm.record_cost("apify", 0.02)
        sm.record_cost("gemini", 0.03)

        state = sm.load_state()
        self.assertEqual(state["cost_tracking"]["apify"], 0.03)
        self.assertEqual(state["cost_tracking"]["gemini"], 0.03)

    def test_get_thread_id_returns_none_if_not_set(self):
        """Test get_thread_id returns None if not set."""
        thread = sm.get_thread_id(1)
        self.assertIsNone(thread)

    def test_set_and_get_thread_id(self):
        """Test setting and getting thread IDs."""
        sm.set_thread_id(1, "thread_abc")
        sm.set_thread_id(3, "thread_xyz")

        self.assertEqual(sm.get_thread_id(1), "thread_abc")
        self.assertEqual(sm.get_thread_id(3), "thread_xyz")


class TestDiscordFormatting(unittest.TestCase):
    """Tests for Discord formatting functions."""

    def test_format_distribution_confirm(self):
        """Test distribution confirmation formatting."""
        from discord_fmt import format_distribution_confirm

        result = format_distribution_confirm(
            sheet_url="https://sheets.google.com/test",
            content_preview="Test content preview here"
        )

        self.assertIn("Stage 4", result)
        self.assertIn("Google Sheets", result)
        self.assertIn("Pipeline", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
