"""Matrix channel plugin.

Mirrors TypeScript: openclaw/extensions/matrix/index.ts
"""
from __future__ import annotations


def register(api) -> None:
    try:
        from openclaw.channels.matrix import MatrixChannel
        api.register_channel(MatrixChannel())
    except ImportError:
        import logging
        logging.getLogger(__name__).warning("Matrix channel unavailable")

plugin = {
    "id": "matrix",
    "name": "Matrix",
    "description": "Matrix protocol channel (matrix-nio).",
    "register": register,
}
