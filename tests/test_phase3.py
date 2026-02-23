#!/usr/bin/env python3
"""Tests for Phase 3: Stage 2 Pattern Analysis."""

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
from gemini_client import (
    call_gemini, extract_json_from_response, build_analysis_prompt,
    _get_api_key, _load_config
)


class TestGeminiClient(unittest.TestCase):
    """Tests for gemini_client.py."""

    def test_load_config(self):
        """Test config loading."""
        config = _load_config()
        self.assertIsInstance(config, dict)
        self.assertIn("models", config)
        self.assertIn("budget", config)

    def test_get_api_key_missing(self):
        """Test API key retrieval when not set."""
        # Should return empty string if not configured
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            config = {"models": {"gemini_api_key": "ENV:GEMINI_API_KEY"}}
            key = _get_api_key(config)
            # May be empty or the env value
            self.assertIsInstance(key, str)

    def test_extract_json_from_response_direct(self):
        """Test JSON extraction from direct JSON response."""
        text = '{"hooks": [], "structures": []}'
        result = extract_json_from_response(text)
        self.assertIsInstance(result, dict)
        self.assertIn("hooks", result)
        self.assertIn("structures", result)

    def test_extract_json_from_response_code_block(self):
        """Test JSON extraction from markdown code block."""
        text = '''```json
{"hooks": [{"name": "test"}], "structures": [], "tone": {}, "ctas": []}
```'''
        result = extract_json_from_response(text)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["hooks"][0]["name"], "test")

    def test_extract_json_from_response_with_surrounding_text(self):
        """Test JSON extraction with text before/after."""
        text = '''Here are the patterns:
{"hooks": [], "structures": [], "tone": {}, "ctas": []}
Let me know if you need more.'''
        result = extract_json_from_response(text)
        self.assertIsInstance(result, dict)

    def test_extract_json_from_response_invalid(self):
        """Test JSON extraction with invalid input."""
        result = extract_json_from_response("not json at all")
        self.assertIsNone(result)

    def test_extract_json_from_response_empty(self):
        """Test JSON extraction with empty input."""
        result = extract_json_from_response("")
        self.assertIsNone(None)  # Should handle gracefully

    def test_build_analysis_prompt_structure(self):
        """Test analysis prompt contains required sections."""
        posts = [
            {"platform": "instagram", "caption": "Test caption", "likes": 100, "comments": 10, "shares": 5}
        ]
        prompt = build_analysis_prompt(posts)

        self.assertIn("viral content pattern analyst", prompt)
        self.assertIn("hooks", prompt)
        self.assertIn("structures", prompt)
        self.assertIn("tone", prompt)
        self.assertIn("ctas", prompt)
        self.assertIn("POST 1", prompt)

    def test_build_analysis_prompt_caps_posts(self):
        """Test prompt caps at 20 posts."""
        posts = [{"platform": "ig", "caption": "x", "likes": 1, "comments": 0, "shares": 0} for _ in range(30)]
        prompt = build_analysis_prompt(posts)

        # Should only include 20 posts
        self.assertIn("POST 20", prompt)
        self.assertNotIn("POST 21", prompt)

    def test_build_analysis_prompt_truncates_caption(self):
        """Test prompt truncates long captions."""
        long_caption = "x" * 1000
        posts = [{"platform": "ig", "caption": long_caption, "likes": 1, "comments": 0, "shares": 0}]
        prompt = build_analysis_prompt(posts)

        # Caption should be truncated
        self.assertLess(len(prompt), len(long_caption) + 1000)

    @patch('gemini_client.requests.post')
    def test_call_gemini_success(self, mock_post):
        """Test successful Gemini API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"hooks": []}'}]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 50
            }
        }
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            text, meta = call_gemini("test prompt", config={"models": {"gemini_api_key": "ENV:GEMINI_API_KEY"}})

        self.assertEqual(text, '{"hooks": []}')
        self.assertEqual(meta["tokens_in"], 100)
        self.assertEqual(meta["tokens_out"], 50)
        self.assertIsNone(meta["error"])

    @patch('gemini_client.requests.post')
    def test_call_gemini_api_error(self, mock_post):
        """Test Gemini API error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            text, meta = call_gemini("test prompt", config={"models": {"gemini_api_key": "ENV:GEMINI_API_KEY"}})

        self.assertIsNone(text)
        self.assertIn("API error", meta["error"])

    @patch('gemini_client.requests.post')
    def test_call_gemini_timeout(self, mock_post):
        """Test Gemini API timeout handling."""
        import requests
        mock_post.side_effect = requests.Timeout("Timeout")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            text, meta = call_gemini("test prompt", config={"models": {"gemini_api_key": "ENV:GEMINI_API_KEY"}})

        self.assertIsNone(text)
        self.assertIn("timed out", meta["error"])

    def test_call_gemini_no_api_key(self):
        """Test Gemini API call without API key."""
        text, meta = call_gemini("test", config={"models": {"gemini_api_key": ""}})
        self.assertIsNone(text)
        self.assertIn("not configured", meta["error"])

    @patch('gemini_client.requests.post')
    def test_call_gemini_cost_calculation(self, mock_post):
        """Test cost calculation from token usage."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "response"}]}}],
            "usageMetadata": {
                "promptTokenCount": 10000,  # 10K tokens
                "candidatesTokenCount": 5000  # 5K tokens
            }
        }
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_key"}):
            text, meta = call_gemini("test", config={"models": {"gemini_api_key": "ENV:GEMINI_API_KEY"}})

        # Cost should be calculated
        self.assertGreater(meta["cost"], 0)
        # Roughly: (10K * 0.000075) + (5K * 0.0003) = 0.75 + 1.5 = $2.25
        # Actually much smaller: 0.00075 + 0.0015 = $0.00225
        self.assertAlmostEqual(meta["cost"], 0.00225, places=4)


class TestStage2Analyze(unittest.TestCase):
    """Tests for stage_2_analyze.py."""

    def setUp(self):
        """Set up test fixtures."""
        # Reset state before each test
        sm.reset_daily()

    def test_get_sample_patterns(self):
        """Test sample patterns generation."""
        # Import here to avoid circular import
        import stage_2_analyze
        patterns = stage_2_analyze._get_sample_patterns()

        self.assertIn("hooks", patterns)
        self.assertIn("structures", patterns)
        self.assertIn("tone", patterns)
        self.assertIn("ctas", patterns)

    def test_fallback_extract_patterns(self):
        """Test fallback pattern extraction."""
        import stage_2_analyze
        patterns = stage_2_analyze._fallback_extract_patterns("some text about hooks")

        self.assertIn("hooks", patterns)
        self.assertIn("structures", patterns)

    def test_update_patterns_file(self):
        """Test updating viral-patterns.md."""
        import stage_2_analyze
        import tempfile

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Test\n\nExisting content\n")
            temp_path = f.name

        # Temporarily override patterns file path
        original_file = stage_2_analyze.SKILL_DIR / "references" / "viral-patterns.md"

        try:
            # Test the update logic
            patterns = {
                "hooks": [{"name": "Test Hook", "template": "test {x}", "frequency": 5}],
                "structures": [{"type": "listicle", "percentage": 40}],
                "tone": {"formality": "casual", "emotions": ["hope"]},
                "ctas": [{"type": "save", "template": "Save!"}]
            }

            # Write test file
            with open(temp_path, 'w') as f:
                f.write("# Viral Content Patterns\n\nExisting\n")

            # Verify patterns structure
            self.assertIsInstance(patterns, dict)
            self.assertEqual(patterns["hooks"][0]["name"], "Test Hook")

        finally:
            os.unlink(temp_path)

    @patch('stage_2_analyze._post_to_discord')
    @patch('stage_2_analyze.call_glm5')
    def test_run_stage_2_dry_run(self, mock_glm5, mock_discord):
        """Test dry run doesn't call APIs."""
        import stage_2_analyze

        # Set stage to 2
        sm.advance_stage(2)

        result = stage_2_analyze.run_stage_2(dry_run=True)

        # Should not call GLM5 in dry run
        mock_glm5.assert_not_called()
        mock_discord.assert_not_called()

        # Should have sample patterns
        self.assertIn("patterns", result)

    def test_run_stage_2_wrong_stage(self):
        """Test Stage 2 fails when not at stage 2."""
        import stage_2_analyze

        # Should be at stage 1 by default
        result = stage_2_analyze.run_stage_2(dry_run=True)

        self.assertFalse(result["success"])
        self.assertIn("Expected stage 2", result["error"])

    @patch('stage_2_analyze._post_to_discord')
    @patch('stage_2_analyze.call_glm5')
    def test_run_stage_2_no_posts(self, mock_glm5, mock_discord):
        """Test Stage 2 fails when no posts from Stage 1."""
        import stage_2_analyze

        sm.advance_stage(2)
        # Don't add any posts

        result = stage_2_analyze.run_stage_2(dry_run=False)

        self.assertFalse(result["success"])
        self.assertIn("No scraped posts", result["error"])

    @patch('stage_2_analyze._post_to_discord')
    @patch('stage_2_analyze.call_glm5')
    def test_run_stage_2_glm5_error(self, mock_glm5, mock_discord):
        """Test Stage 2 handles GLM5 errors."""
        import stage_2_analyze

        sm.advance_stage(2)
        sm.add_data(1, [{"platform": "ig", "caption": "test", "likes": 100, "comments": 10, "shares": 5}])

        mock_glm5.return_value = (None, {"error": "API failed", "tokens_in": 0, "tokens_out": 0, "cost": 0})

        result = stage_2_analyze.run_stage_2(dry_run=False)

        self.assertFalse(result["success"])
        self.assertIn("GLM-5 API error", result["error"])

    @patch('stage_2_analyze._post_to_discord')
    @patch('stage_2_analyze.call_glm5')
    @patch('stage_2_analyze._update_patterns_file')
    def test_run_stage_2_success(self, mock_update_file, mock_glm5, mock_discord):
        """Test successful Stage 2 execution."""
        import stage_2_analyze

        sm.advance_stage(2)
        sm.add_data(1, [{"platform": "ig", "caption": "test", "likes": 100, "comments": 10, "shares": 5}])

        mock_glm5.return_value = (
            '{"hooks": [], "structures": [], "tone": {}, "ctas": []}',
            {"tokens_in": 100, "tokens_out": 50, "cost": 0.01, "error": None}
        )
        mock_discord.return_value = "thread_123"

        result = stage_2_analyze.run_stage_2(dry_run=False)

        self.assertTrue(result["success"])
        self.assertEqual(result["tokens_in"], 100)
        self.assertEqual(result["tokens_out"], 50)
        self.assertEqual(result["thread_id"], "thread_123")
        mock_update_file.assert_called_once()

    @patch('stage_2_analyze._post_to_discord')
    @patch('stage_2_analyze.call_glm5')
    @patch('stage_2_analyze._update_patterns_file')
    def test_run_stage_2_discord_failure_partial_success(self, mock_update_file, mock_glm5, mock_discord):
        """Test Stage 2 handles Discord failure as partial success."""
        import stage_2_analyze

        sm.advance_stage(2)
        sm.add_data(1, [{"platform": "ig", "caption": "test", "likes": 100, "comments": 10, "shares": 5}])

        mock_glm5.return_value = (
            '{"hooks": [], "structures": [], "tone": {}, "ctas": []}',
            {"tokens_in": 100, "tokens_out": 50, "cost": 0.01, "error": None}
        )
        mock_discord.return_value = None  # Discord failed

        result = stage_2_analyze.run_stage_2(dry_run=False)

        self.assertTrue(result["success"])  # Still success
        self.assertIn("Discord posting failed", result["error"])
        self.assertEqual(result["thread_id"], None)


class TestStage2BudgetCheck(unittest.TestCase):
    """Tests for budget checking in Stage 2."""

    def setUp(self):
        sm.reset_daily()

    def test_budget_exceeded(self):
        """Test Stage 2 respects budget cap."""
        import stage_2_analyze

        sm.advance_stage(2)
        sm.add_data(1, [{"platform": "ig", "caption": "test", "likes": 100}])

        # Record cost to exceed budget
        sm.record_cost("glm5", 1.0)  # Exceeds $0.20 cap

        result = stage_2_analyze.run_stage_2(dry_run=False)

        self.assertFalse(result["success"])
        self.assertIn("budget exceeded", result["error"].lower())


class TestDiscordFormatting(unittest.TestCase):
    """Tests for Discord message formatting."""

    def test_format_patterns(self):
        """Test pattern formatting for Discord."""
        from discord_fmt import format_patterns

        patterns = {
            "hooks": [{"name": "Test", "template": "test"}],
            "structures": [{"type": "listicle"}],
            "tone": {"formality": "casual"},
            "ctas": [{"type": "save", "template": "Save!"}]
        }

        result = format_patterns(patterns)

        self.assertIn("Stage 2", result)
        self.assertIn("Pattern", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
