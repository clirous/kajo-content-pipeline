#!/usr/bin/env python3
"""GLM5 API client for Vietnamese content generation."""

import os
import json
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import requests

# Load config
SKILL_DIR = Path(__file__).parent.parent.parent
CONFIG_FILE = SKILL_DIR / "assets" / "config.json"

# Constants
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2


def _load_config() -> dict:
    """Load configuration from config.json."""
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_endpoint(config: Optional[dict] = None) -> str:
    """Get GLM5 API endpoint from config."""
    if config is None:
        config = _load_config()

    endpoint = config.get("models", {}).get("glm5_endpoint", "")

    # Handle ENV: prefix
    if endpoint.startswith("ENV:"):
        env_var = endpoint[4:]
        return os.environ.get(env_var, "")

    return endpoint


def _get_api_key(config: Optional[dict] = None) -> str:
    """Get GLM5 API key from config."""
    if config is None:
        config = _load_config()

    api_key = config.get("models", {}).get("glm5_api_key", "")

    # Handle ENV: prefix
    if api_key.startswith("ENV:"):
        env_var = api_key[4:]
        return os.environ.get(env_var, "")

    return api_key


def call_glm5(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    config: Optional[dict] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024
) -> Tuple[Optional[str], Dict[str, Any]]:
    """Call GLM5 API to generate Vietnamese content.

    Uses OpenAI-compatible chat completion format.

    Args:
        system_prompt: System context/instructions
        user_prompt: User content to process
        model: Model ID (default from config or "glm-5")
        config: Optional config override
        temperature: Sampling temperature (0-1)
        max_tokens: Maximum output tokens

    Returns:
        Tuple of (response_text, metadata) where metadata includes:
        - tokens_in: Input token count
        - tokens_out: Output token count
        - cost: Estimated cost in USD
        - model: Model used
        - error: Error message if failed
    """
    metadata = {
        "tokens_in": 0,
        "tokens_out": 0,
        "cost": 0.0,
        "model": model or "glm-5",
        "error": None
    }

    if config is None:
        config = _load_config()

    endpoint = _get_endpoint(config)
    if not endpoint:
        metadata["error"] = "GLM5_ENDPOINT not configured"
        return None, metadata

    api_key = _get_api_key(config)

    model_id = model or config.get("models", {}).get("generation", "glm-5")
    metadata["model"] = model_id

    # Build OpenAI-compatible request
    # Endpoint should be base URL, we append /chat/completions
    base_url = endpoint.rstrip("/")
    url = f"{base_url}/chat/completions"

    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    import time
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120  # Generation can take longer
            )

            # Retry on server errors
            if response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                print(f"Server error {response.status_code}, retrying in {delay}s...")
                time.sleep(delay)
                continue

            if response.status_code != 200:
                metadata["error"] = f"API error {response.status_code}: {response.text[:200]}"
                return None, metadata

            data = response.json()

            # Parse OpenAI-compatible response
            choices = data.get("choices", [])
            if not choices:
                metadata["error"] = "No choices in response"
                return None, metadata

            message = choices[0].get("message", {})
            text = message.get("content", "")

            # Extract token usage
            usage = data.get("usage", {})
            metadata["tokens_in"] = usage.get("prompt_tokens", 0)
            metadata["tokens_out"] = usage.get("completion_tokens", 0)

            # Estimate cost (GLM5 pricing varies by endpoint)
            # Using placeholder rates - adjust based on actual pricing
            GLM5_INPUT_COST = 0.0001   # $/1K tokens (placeholder)
            GLM5_OUTPUT_COST = 0.0002  # $/1K tokens (placeholder)
            cost_in = (metadata["tokens_in"] / 1000) * GLM5_INPUT_COST
            cost_out = (metadata["tokens_out"] / 1000) * GLM5_OUTPUT_COST
            metadata["cost"] = cost_in + cost_out

            return text, metadata

        except requests.Timeout:
            last_error = "API request timed out"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                print(f"Timeout, retrying in {delay}s...")
                time.sleep(delay)
                continue
        except requests.ConnectionError as e:
            last_error = f"Connection error: {e}"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                print(f"Connection error, retrying in {delay}s...")
                time.sleep(delay)
                continue
        except (json.JSONDecodeError, KeyError) as e:
            metadata["error"] = f"Response parse error: {e}"
            return None, metadata
        except Exception as e:
            last_error = f"Unexpected error: {type(e).__name__}: {e}"
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_BASE ** (attempt + 1)
                print(f"Unexpected error, retrying in {delay}s...")
                time.sleep(delay)
                continue

    metadata["error"] = last_error or "All retries exhausted"
    return None, metadata


def build_generation_prompt(
    patterns: dict,
    paper_title: str,
    findings: str,
    quotes: list,
    tone: str = "warm, professional, accessible"
) -> Tuple[str, str]:
    """Build system and user prompts for content generation.

    Args:
        patterns: Viral patterns from Stage 2 analysis
        paper_title: Title of source paper
        findings: Key findings summary
        quotes: List of exact quotes with page refs
        tone: Tone guidelines

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = """Bạn là chuyên gia tạo nội dung sức khỏe bằng tiếng Việt cho phòng khám phục hồi chức năng Kajo.

GIỌNG VĂN (be Ngo):
- Thân thiện, gần gũi như bạn bè
- Có kiến thức chuyên môn về photobiomodulation
- Chia sẻ từ trải nghiệm thực tế
- KHÔNG áp đặt, chỉ gợi mở

NGÔN NGỮ:
- Dùng "bạn" / "mình"
- Câu ngắn (15-20 từ tối đa)
- Đoạn ngắn (2-3 câu)
- 2-3 emoji phù hợp
- Kết hợp tiếng Anh cho thuật ngữ chuyên môn (red light therapy, photobiomodulation)

QUAN TRỌNG:
- CHỈ sử dụng số liệu từ research được cung cấp
- KHÔNG bịa chi tiết hay thống kê
- LUÔN bao gồm source card cuối bài"""

    # Format patterns for prompt
    hooks_text = ""
    for hook in patterns.get("hooks", [])[:3]:
        hooks_text += f"- {hook.get('name', 'Hook')}: {hook.get('template', '')}\n"

    structures_text = ""
    for struct in patterns.get("structures", [])[:2]:
        structures_text += f"- {struct.get('type', 'Structure')}\n"

    ctas_text = ""
    for cta in patterns.get("ctas", [])[:2]:
        ctas_text += f"- {cta.get('type', 'CTA')}: {cta.get('template', '')}\n"

    # Format quotes
    quotes_text = ""
    for i, quote in enumerate(quotes[:3], 1):
        q = quote.get("text", "")
        page = quote.get("page", "")
        quotes_text += f'{i}. "{q}"'
        if page:
            quotes_text += f" (Trang {page})"
        quotes_text += "\n"

    user_prompt = f"""Tạo bài đăng Facebook/Instagram (~200-300 từ) dựa trên nghiên cứu sau:

TIÊU ĐỀ NGHIÊN CỨU: {paper_title}

TÓM TẮT FINDINGS:
{findings}

TRÍCH DẪN CHÍNH XÁC:
{quotes_text}

PATTERNS ĐỂ SỬ DỤNG:

Hook (chọn 1):
{hooks_text if hooks_text else "- Question: Bạn có biết...?\n- Statistic: [X]% người dùng..."}

Structure:
{structures_text if structures_text else "- Hook → Problem → Solution → CTA"}

CTA (chọn 1):
{ctas_text if ctas_text else "- Engage: Chia sẻ trải nghiệm bên dưới 👇\n- Save: Lưu bài để đọc sau"}

YÊU CẦU:
1. Hook thu hút trong 3-5 từ đầu
2. Sử dụng ít nhất 1 trích dẫn từ research
3. Ngôn ngữ đơn giản, dễ hiểu
4. CTA tự nhiên, không áp đặt
5. 2-3 emoji phù hợp
6. Độ dài 200-300 từ

OUTPUT FORMAT:
[Bài viết tiếng Việt]

---
📄 NGUỒN: {paper_title}
> "[Trích dẫn quan trọng nhất]"
🔗 [URL sẽ thêm sau]"""

    return system_prompt, user_prompt


# CLI interface
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: glm5_client.py <command> [args]")
        print("Commands: test, generate")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "test":
        print("Testing GLM5 client...")
        endpoint = _get_endpoint()
        if endpoint:
            print(f"Endpoint: {endpoint}")
            # Test simple call
            text, meta = call_glm5(
                "You are a helpful assistant.",
                "Say 'Xin chào' in Vietnamese."
            )
            if text:
                print(f"Response: {text}")
                print(f"Tokens: {meta['tokens_in']} in / {meta['tokens_out']} out")
            else:
                print(f"Error: {meta['error']}")
        else:
            print("No endpoint configured. Set GLM5_ENDPOINT environment variable.")

    elif cmd == "generate":
        # Test generation with sample data
        patterns = {
            "hooks": [{"name": "Question", "template": "Bạn có biết {fact}?"}],
            "structures": [{"type": "listicle"}],
            "ctas": [{"type": "Engage", "template": "Chia sẻ bên dưới 👇"}]
        }
        sys_prompt, user_prompt = build_generation_prompt(
            patterns=patterns,
            paper_title="Photobiomodulation in Pain Management",
            findings="Red light at 630nm reduces chronic pain by 47% in clinical trials.",
            quotes=[{"text": "Significant reduction observed after 8 weeks", "page": "12"}]
        )
        print("System prompt:")
        print(sys_prompt[:500])
        print("\nUser prompt:")
        print(user_prompt[:500])

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
