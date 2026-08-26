import asyncio
import os

from regurolog_api.server import run as run_api
from regurolog_api.worker import run as run_worker


def main() -> None:
    process = os.getenv("REGUROLOG_PROCESS", "api").strip().lower()
    if process == "api":
        run_api()
        return
    if process == "worker":
        asyncio.run(run_worker())
        return
    raise RuntimeError("REGUROLOG_PROCESS faqat 'api' yoki 'worker' bo‘lishi mumkin")


if __name__ == "__main__":
    main()
