"""Runtime adapter selection."""
from .db import is_production_mode

if is_production_mode():
    from .production_api import app
else:
    from .legacy_api import app

__all__ = ["app"]