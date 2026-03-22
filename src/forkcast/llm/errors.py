"""Classify Anthropic API errors into typed, user-friendly error info."""

import anthropic


def classify_api_error(exc: Exception) -> dict:
    """Map an exception to a structured error dict for SSE/UI consumption."""
    if isinstance(exc, anthropic.RateLimitError):
        return {
            "error_type": "rate_limited",
            "message": "Claude API rate limit sustained after retries. Wait a few minutes and resume.",
            "resumable": True,
        }

    if isinstance(exc, anthropic.AuthenticationError):
        return {
            "error_type": "auth_error",
            "message": "API key invalid or expired. Check .env and restart server.",
            "resumable": False,
        }

    if isinstance(exc, anthropic.BadRequestError):
        body_msg = ""
        if hasattr(exc, "body") and isinstance(exc.body, dict):
            err = exc.body.get("error", {})
            body_msg = err.get("message", "").lower() if isinstance(err, dict) else ""

        if "credit" in body_msg or "billing" in body_msg:
            return {
                "error_type": "credits_exhausted",
                "message": "API credits exhausted. Add credits at console.anthropic.com, then resume.",
                "resumable": True,
            }

        if "max_tokens" in body_msg or "too long" in body_msg or "too many tokens" in body_msg:
            return {
                "error_type": "context_error",
                "message": "Input too large for model. Try a different model.",
                "resumable": False,
            }

    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return {
            "error_type": "network_error",
            "message": "Connection to Claude API lost. Check network and resume.",
            "resumable": True,
        }

    return {
        "error_type": "unknown",
        "message": f"Unexpected error: {exc}",
        "resumable": True,
    }
