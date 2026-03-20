"""Standardized API response helpers."""

from typing import Any

from fastapi.responses import JSONResponse


def success(data: Any = None, status_code: int = 200) -> JSONResponse:
    """Return a success response with the standard envelope."""
    return JSONResponse(content={"success": True, "data": data}, status_code=status_code)


def error(message: str, status_code: int = 400) -> JSONResponse:
    """Return an error response with the standard envelope."""
    return JSONResponse(
        content={"success": False, "error": message}, status_code=status_code
    )
