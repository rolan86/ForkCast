"""Tests for classify_api_error() utility."""
from unittest.mock import MagicMock
import anthropic
from forkcast.llm.errors import classify_api_error


class TestClassifyApiError:
    def test_rate_limit_error(self):
        exc = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body={"error": {"type": "rate_limit_error", "message": "rate limited"}},
        )
        result = classify_api_error(exc)
        assert result["error_type"] == "rate_limited"
        assert result["resumable"] is True

    def test_auth_error(self):
        exc = anthropic.AuthenticationError(
            message="invalid api key",
            response=MagicMock(status_code=401),
            body={"error": {"type": "authentication_error", "message": "invalid api key"}},
        )
        result = classify_api_error(exc)
        assert result["error_type"] == "auth_error"
        assert result["resumable"] is False

    def test_credits_exhausted(self):
        exc = anthropic.BadRequestError(
            message="billing error: credit balance is too low",
            response=MagicMock(status_code=400),
            body={"error": {"type": "invalid_request_error", "message": "credit balance is too low"}},
        )
        result = classify_api_error(exc)
        assert result["error_type"] == "credits_exhausted"
        assert result["resumable"] is True

    def test_context_too_long(self):
        exc = anthropic.BadRequestError(
            message="max_tokens exceeded",
            response=MagicMock(status_code=400),
            body={"error": {"type": "invalid_request_error", "message": "max_tokens: prompt is too long"}},
        )
        result = classify_api_error(exc)
        assert result["error_type"] == "context_error"
        assert result["resumable"] is False

    def test_network_error(self):
        result = classify_api_error(ConnectionError("connection refused"))
        assert result["error_type"] == "network_error"
        assert result["resumable"] is True

    def test_timeout_error(self):
        result = classify_api_error(TimeoutError("timed out"))
        assert result["error_type"] == "network_error"
        assert result["resumable"] is True

    def test_unknown_error(self):
        result = classify_api_error(RuntimeError("something weird"))
        assert result["error_type"] == "unknown"
        assert result["resumable"] is True
        assert "something weird" in result["message"]

    def test_result_has_all_required_fields(self):
        result = classify_api_error(RuntimeError("test"))
        assert "error_type" in result
        assert "message" in result
        assert "resumable" in result
