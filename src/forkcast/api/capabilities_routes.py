"""Capabilities endpoint — reports available engines and models."""
from fastapi import APIRouter
from forkcast.api.responses import success
from forkcast.config import get_settings, get_available_models

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
    settings = get_settings()
    return success({
        "engines": {
            "claude": {"available": True},
            "oasis": _check_oasis(),
        },
        "models": get_available_models(settings),
        "integrators": {
            "methods": [
                {
                    "id": "euler",
                    "name": "Euler",
                    "description": "Fastest. Single evaluation per step. Best for most simulations.",
                    "params": [],
                },
                {
                    "id": "rk",
                    "name": "Runge-Kutta",
                    "description": "Higher accuracy. Choose order 2/4/6/8 — higher = more accurate but slower.",
                    "params": ["order"],
                },
                {
                    "id": "adaptive",
                    "name": "Adaptive Convergence",
                    "description": "Auto-increases order until result stabilizes within tolerance. Most accurate but most expensive.",
                    "params": ["tolerance", "max_order"],
                },
            ],
        },
    })
