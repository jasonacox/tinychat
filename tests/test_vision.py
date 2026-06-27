"""Tests for vision/multimodal content support in chat schema."""

import pytest
from pydantic import ValidationError

from app.api.schemas.chat import ChatRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A minimal valid base64-encoded 1x1 white PNG (truncated for brevity)
TINY_PNG_B64 = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4"
    "2mP8/58BAwAI/AL+hc2rNAAAAABJRU5ErkJggg=="
)


def _make_request(**overrides):
    """Build a minimal valid ChatRequest dict with sensible defaults."""
    data = {
        "messages": [{"role": "user", "content": "hello"}],
        "model": None,
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Tests: multimodal content (vision)
# ---------------------------------------------------------------------------


class TestMultimodalContent:
    """Tests that the chat schema accepts OpenAI-style multimodal content arrays."""

    def test_content_array_with_text_and_image_url(self):
        """Schema accepts a content array containing text + image_url parts."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What is in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": TINY_PNG_B64},
                    },
                ],
            }
        ]
        req = ChatRequest(**_make_request(messages=messages))
        assert req.messages == messages

    def test_content_array_text_only(self):
        """Schema accepts a content array with only text parts."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "Just text in an array"}],
            }
        ]
        req = ChatRequest(**_make_request(messages=messages))
        assert req.messages == messages

    def test_content_array_with_https_image_url(self):
        """Schema accepts an https image URL (not just data URIs)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/photo.jpg"},
                    },
                ],
            }
        ]
        req = ChatRequest(**_make_request(messages=messages))
        assert req.messages[0]["content"][1]["image_url"]["url"] == "https://example.com/photo.jpg"

    def test_content_array_rejects_invalid_image_url_scheme(self):
        """Schema rejects image URLs that aren't data URI or HTTP(S)."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": "ftp://evil.com/img.png"},
                    },
                ],
            }
        ]
        with pytest.raises(ValidationError, match="data URI or HTTP"):
            ChatRequest(**_make_request(messages=messages))

    def test_content_array_rejects_missing_url(self):
        """Schema rejects image_url part missing the url field."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {}},
                ],
            }
        ]
        with pytest.raises(ValidationError, match="image_url.url"):
            ChatRequest(**_make_request(messages=messages))

    def test_content_array_rejects_unknown_type(self):
        """Schema rejects content parts with an unknown type."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "video", "url": "https://example.com/v.mp4"}],
            }
        ]
        with pytest.raises(ValidationError, match="Unknown content part type"):
            ChatRequest(**_make_request(messages=messages))

    def test_image_request_does_not_crash_validation(self):
        """Full multimodal request passes validation without exceptions."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What do you see?"},
                    {
                        "type": "image_url",
                        "image_url": {"url": TINY_PNG_B64},
                    },
                ],
            }
        ]
        # Should not raise
        req = ChatRequest(**_make_request(messages=messages))
        assert len(req.messages) == 1
        assert len(req.messages[0]["content"]) == 2


# ---------------------------------------------------------------------------
# Tests: backwards compatibility (plain string content)
# ---------------------------------------------------------------------------


class TestPlainStringContent:
    """Ensure plain string content still works (backwards compat)."""

    def test_plain_string_content(self):
        """Schema accepts a plain string as message content."""
        messages = [{"role": "user", "content": "Hello, world!"}]
        req = ChatRequest(**_make_request(messages=messages))
        assert req.messages[0]["content"] == "Hello, world!"

    def test_multi_turn_plain_string(self):
        """Schema accepts multi-turn conversation with string content."""
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
            {"role": "user", "content": "How are you?"},
        ]
        req = ChatRequest(**_make_request(messages=messages))
        assert len(req.messages) == 4

    def test_rejects_invalid_content_type(self):
        """Schema rejects content that is neither string nor list."""
        messages = [{"role": "user", "content": 12345}]
        with pytest.raises(ValidationError, match="string or array"):
            ChatRequest(**_make_request(messages=messages))
