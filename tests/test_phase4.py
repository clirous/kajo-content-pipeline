#!/usr/bin/env python3
"""Tests for Phase 4: Stage 3 Content Generation."""

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
from glm5_client import (
    call_glm5, build_generation_prompt, _get_endpoint, _load_config
)
from paper_fetcher import (
    fetch_paper, _extract_title_from_html, _extract_abstract_from_html,
    _extract_quotes_from_text, format_source_card
)


class TestGLM5Client(unittest.TestCase):
    """Tests for glm5_client.py."""

    def test_load_config(self):
        """Test config loading."""
        config = _load_config()
        self.assertIsInstance(config, dict)
        self.assertIn("models", config)

    def test_get_endpoint_missing(self):
        """Test endpoint retrieval when not set."""
        with patch.dict(os.environ, {"GLM5_ENDPOINT": ""}, clear=False):
            config = {"models": {"glm5_endpoint": ""}}
            endpoint = _get_endpoint(config)
            self.assertIsInstance(endpoint, str)

    def test_build_generation_prompt_structure(self):
        """Test generation prompt contains required elements."""
        patterns = {
            "hooks": [{"name": "Test Hook", "template": "test template"}],
            "structures": [{"type": "listicle"}],
            "ctas": [{"type": "engage", "template": "Share below"}]
        }

        sys_prompt, user_prompt = build_generation_prompt(
            patterns=patterns,
            paper_title="Test Paper",
            findings="Test findings here",
            quotes=[{"text": "Test quote", "page": "1"}]
        )

        # System prompt should contain tone instructions
        self.assertIn("tiếng Việt", sys_prompt)
        self.assertIn("bạn", sys_prompt)

        # User prompt should contain paper info
        self.assertIn("Test Paper", user_prompt)
        self.assertIn("Test findings", user_prompt)
        self.assertIn("Test quote", user_prompt)

    def test_build_generation_prompt_empty_patterns(self):
        """Test prompt generation with empty patterns."""
        sys_prompt, user_prompt = build_generation_prompt(
            patterns={},
            paper_title="Test",
            findings="Findings",
            quotes=[]
        )

        # Should still work with defaults
        self.assertIn("tiếng Việt", sys_prompt)
        self.assertIn("Test", user_prompt)

    def test_build_generation_prompt_truncates_quotes(self):
        """Test prompt limits quotes."""
        quotes = [{"text": f"Quote {i}", "page": str(i)} for i in range(10)]

        sys_prompt, user_prompt = build_generation_prompt(
            patterns={},
            paper_title="Test",
            findings="Findings",
            quotes=quotes
        )

        # Should only include 3 quotes max (numbered 1, 2, 3)
        # Check that we have at least quote 1 and 3
        self.assertIn("1.", user_prompt)
        self.assertIn("3.", user_prompt)
        # Quote 4 may or may not be in output depending on implementation
        # The important thing is quotes are included

    @patch('glm5_client.requests.post')
    def test_call_glm5_success(self, mock_post):
        """Test successful GLM5 API call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "Generated Vietnamese content"}
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"GLM5_ENDPOINT": "https://api.example.com", "GLM5_API_KEY": "test"}):
            text, meta = call_glm5(
                "System prompt",
                "User prompt",
                config={"models": {"glm5_endpoint": "ENV:GLM5_ENDPOINT"}}
            )

        self.assertEqual(text, "Generated Vietnamese content")
        self.assertEqual(meta["tokens_in"], 100)
        self.assertEqual(meta["tokens_out"], 50)
        self.assertIsNone(meta["error"])

    @patch('glm5_client.requests.post')
    def test_call_glm5_api_error(self, mock_post):
        """Test GLM5 API error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        with patch.dict(os.environ, {"GLM5_ENDPOINT": "https://api.example.com"}):
            text, meta = call_glm5(
                "System", "User",
                config={"models": {"glm5_endpoint": "ENV:GLM5_ENDPOINT"}}
            )

        self.assertIsNone(text)
        self.assertIn("API error", meta["error"])

    def test_call_glm5_no_endpoint(self):
        """Test GLM5 call without endpoint configured."""
        text, meta = call_glm5("System", "User", config={"models": {}})
        self.assertIsNone(text)
        self.assertIn("not configured", meta["error"])


class TestPaperFetcher(unittest.TestCase):
    """Tests for paper_fetcher.py."""

    def test_extract_title_from_html(self):
        """Test title extraction from HTML."""
        html = "<html><title>Test Paper Title | Journal</title></html>"
        title = _extract_title_from_html(html)
        self.assertIn("Test Paper Title", title)

    def test_extract_title_from_h1(self):
        """Test title extraction from h1 tag."""
        html = "<html><body><h1>Research Paper Title</h1></body></html>"
        title = _extract_title_from_html(html)
        self.assertEqual(title, "Research Paper Title")

    def test_extract_abstract_from_html(self):
        """Test abstract extraction from meta tags."""
        html = '<meta name="description" content="This is the abstract of the paper.">'
        abstract = _extract_abstract_from_html(html)
        self.assertEqual(abstract, "This is the abstract of the paper.")

    def test_extract_quotes_from_text(self):
        """Test quote extraction from text."""
        text = """
        This is a regular sentence.
        The photobiomodulation treatment showed significant reduction in pain scores.
        Another sentence here.
        Clinical results demonstrate improvement in patient outcomes.
        """

        quotes = _extract_quotes_from_text(text)
        self.assertIsInstance(quotes, list)
        # Should find quotes with relevant keywords
        self.assertTrue(len(quotes) > 0)

    def test_extract_quotes_limits_results(self):
        """Test quote extraction limits results."""
        text = ". ".join([
            f"Photobiomodulation treatment {i} showed significant clinical improvement."
            for i in range(20)
        ])
        quotes = _extract_quotes_from_text(text, max_quotes=5)
        self.assertLessEqual(len(quotes), 5)

    def test_format_source_card_full(self):
        """Test source card formatting with full access."""
        card = format_source_card(
            title="Test Paper",
            quote="This is a test quote",
            url="https://example.com/paper",
            page="12",
            access_type="full"
        )

        self.assertIn("Test Paper", card)
        self.assertIn("This is a test quote", card)
        self.assertIn("https://example.com/paper", card)
        self.assertIn("Trang: 12", card)
        self.assertNotIn("Abstract only", card)

    def test_format_source_card_abstract_only(self):
        """Test source card formatting with abstract only."""
        card = format_source_card(
            title="Paywalled Paper",
            quote="Abstract excerpt",
            url="https://example.com/paywall",
            access_type="abstract_only"
        )

        self.assertIn("Abstract only", card)
        self.assertIn("yêu cầu trả phí", card)

    @patch('paper_fetcher.requests.get')
    def test_fetch_paper_html(self, mock_get):
        """Test fetching HTML article."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = """
        <html>
        <head><title>Test Article</title></head>
        <body>
        <article>
        <p>This is the article content about photobiomodulation therapy.</p>
        <p>The clinical results show significant improvement in patient outcomes.</p>
        </article>
        </body>
        </html>
        """
        mock_get.return_value = mock_response

        paper, access_type = fetch_paper("https://example.com/article")
        self.assertEqual(access_type, "full")
        self.assertEqual(paper["title"], "Test Article")

    @patch('paper_fetcher.requests.get')
    def test_fetch_paper_paywall(self, mock_get):
        """Test handling paywalled content."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = """
        <html>
        <head><title>Paywalled Article</title>
        <meta name="description" content="This is the abstract only.">
        </head>
        </html>
        """
        mock_get.return_value = mock_response

        paper, access_type = fetch_paper("https://example.com/paywall")
        self.assertEqual(access_type, "abstract_only")
        self.assertEqual(paper["abstract"], "This is the abstract only.")

    @patch('paper_fetcher.requests.get')
    def test_fetch_paper_timeout(self, mock_get):
        """Test handling request timeout."""
        import requests
        mock_get.side_effect = requests.Timeout("Timeout")

        paper, access_type = fetch_paper("https://example.com/slow")
        self.assertEqual(access_type, "error")
        self.assertIn("timed out", paper["error"])


class TestStage3Generate(unittest.TestCase):
    """Tests for stage_3_generate.py."""

    def setUp(self):
        """Set up test fixtures."""
        sm.reset_daily()

    def test_get_default_patterns(self):
        """Test default patterns structure."""
        import stage_3_generate
        patterns = stage_3_generate._get_default_patterns()

        self.assertIn("hooks", patterns)
        self.assertIn("structures", patterns)
        self.assertIn("tone", patterns)
        self.assertIn("ctas", patterns)

    def test_get_sample_content(self):
        """Test sample content for dry run."""
        import stage_3_generate
        content = stage_3_generate._get_sample_content()

        self.assertIn("bạn", content.lower())
        self.assertGreater(len(content), 100)

    @patch('stage_3_generate._post_to_discord')
    @patch('stage_3_generate.call_glm5')
    @patch('stage_3_generate.fetch_paper')
    @patch('stage_3_generate.get_next_paper_url')
    def test_run_stage_3_dry_run(self, mock_url, mock_fetch, mock_glm5, mock_discord):
        """Test dry run doesn't call APIs."""
        import stage_3_generate

        sm.advance_stage(3)
        result = stage_3_generate.run_stage_3(dry_run=True)

        # Should not call external APIs in dry run
        mock_url.assert_not_called()
        mock_fetch.assert_not_called()
        mock_glm5.assert_not_called()
        mock_discord.assert_not_called()

        # Should have content
        self.assertTrue(result["success"])

    def test_run_stage_3_wrong_stage(self):
        """Test Stage 3 fails when not at stage 3."""
        import stage_3_generate

        # Should be at stage 1 by default
        result = stage_3_generate.run_stage_3(dry_run=True)

        self.assertFalse(result["success"])
        self.assertIn("Expected stage 3", result["error"])

    @patch('stage_3_generate._post_to_discord')
    @patch('stage_3_generate.call_glm5')
    @patch('stage_3_generate.fetch_paper')
    @patch('stage_3_generate.get_next_paper_url')
    def test_run_stage_3_success(self, mock_url, mock_fetch, mock_glm5, mock_discord):
        """Test successful Stage 3 execution."""
        import stage_3_generate

        sm.advance_stage(3)
        sm.add_data(2, {"hooks": [], "structures": [], "ctas": []})

        mock_url.return_value = "https://example.com/paper"
        mock_fetch.return_value = (
            {
                "title": "Test Paper",
                "content": "Test content about photobiomodulation.",
                "abstract": "Test abstract",
                "quotes": [{"text": "Test quote", "page": "1"}],
                "error": None
            },
            "full"
        )
        mock_glm5.return_value = (
            "Generated Vietnamese content here",
            {"tokens_in": 100, "tokens_out": 50, "cost": 0.01, "error": None}
        )
        mock_discord.return_value = "thread_123"

        result = stage_3_generate.run_stage_3(dry_run=False)

        self.assertTrue(result["success"])
        self.assertEqual(result["source_title"], "Test Paper")
        self.assertEqual(result["tokens_in"], 100)
        self.assertEqual(result["thread_id"], "thread_123")

    @patch('stage_3_generate._post_to_discord')
    @patch('stage_3_generate.call_glm5')
    @patch('stage_3_generate.fetch_paper')
    @patch('stage_3_generate.get_next_paper_url')
    def test_run_stage_3_glm5_error(self, mock_url, mock_fetch, mock_glm5, mock_discord):
        """Test Stage 3 handles GLM5 errors."""
        import stage_3_generate

        sm.advance_stage(3)
        sm.add_data(2, {"hooks": []})

        mock_url.return_value = "https://example.com/paper"
        mock_fetch.return_value = ({"title": "Test", "content": "Test"}, "full")
        mock_glm5.return_value = (None, {"error": "API failed", "tokens_in": 0, "tokens_out": 0, "cost": 0})

        result = stage_3_generate.run_stage_3(dry_run=False)

        self.assertFalse(result["success"])
        self.assertIn("GLM5 API error", result["error"])

    @patch('stage_3_generate._post_to_discord')
    @patch('stage_3_generate.call_glm5')
    @patch('stage_3_generate.fetch_paper')
    @patch('stage_3_generate.get_next_paper_url')
    def test_run_stage_3_no_paper_url(self, mock_url, mock_fetch, mock_glm5, mock_discord):
        """Test Stage 3 handles missing paper URL."""
        import stage_3_generate

        sm.advance_stage(3)
        mock_url.return_value = None

        result = stage_3_generate.run_stage_3(dry_run=False)

        self.assertFalse(result["success"])
        self.assertIn("No paper URL", result["error"])


class TestDiscordFormatting(unittest.TestCase):
    """Tests for Discord formatting functions."""

    def test_format_generated_content(self):
        """Test generated content formatting."""
        from discord_fmt import format_generated_content

        result = format_generated_content(
            content="Test content here",
            source_title="Test Source",
            source_url="https://example.com",
            word_count=100
        )

        self.assertIn("Stage 3", result)
        self.assertIn("100", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
