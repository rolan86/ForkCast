"""Capabilities endpoint — reports available engines and models."""
from fastapi import APIRouter
from forkcast.api.responses import success
from forkcast.config import AVAILABLE_MODELS

router = APIRouter(prefix="/api", tags=["capabilities"])


def _check_oasis() -> dict:
    result = {"agent_modes": ["llm", "native"]}
    try:
        import oasis  # noqa: F401
        result["available"] = True
    except ImportError:
        result["available"] = False
        result["reason"] = "camel-oasis not installed"
    return result


@router.get("/capabilities")
async def get_capabilities():
    return success({
        "engines": {
            "claude": {"available": True},
            "oasis": _check_oasis(),
        },
        "models": AVAILABLE_MODELS,
    })
