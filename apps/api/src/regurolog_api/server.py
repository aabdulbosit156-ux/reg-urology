import os

import uvicorn

from regurolog_api.config import Settings


def _port() -> int:
    raw_port = os.getenv("PORT", "8000")
    try:
        port = int(raw_port)
    except ValueError as error:
        raise RuntimeError("PORT butun son bo‘lishi kerak") from error
    if not 1 <= port <= 65_535:
        raise RuntimeError("PORT 1..65535 oralig‘ida bo‘lishi kerak")
    return port


def run() -> None:
    settings = Settings()
    uvicorn.run(
        "regurolog_api.main:app",
        host="0.0.0.0",  # noqa: S104 - container network binding
        port=_port(),
        access_log=False,
        proxy_headers=settings.trust_proxy_headers,
        forwarded_allow_ips="*" if settings.trust_proxy_headers else "127.0.0.1",
    )


if __name__ == "__main__":
    run()
