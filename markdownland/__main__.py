"""Entry point: `python -m markdownland` starts the server on Granian (ASGI)."""

import os

from granian import Granian
from granian.constants import Interfaces


def main() -> None:
    Granian(
        "markdownland.app:api",
        address=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        interface=Interfaces.ASGI,
        workers=int(os.environ.get("WEB_CONCURRENCY", "1")),
        reload=os.environ.get("RELOAD", "").lower() in {"1", "true", "yes"},
    ).serve()


if __name__ == "__main__":
    main()
