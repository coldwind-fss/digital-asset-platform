"""Public HTTP ports exposed by the governance context."""

from app.modules.governance.api.routes import router

__all__ = ["router"]
