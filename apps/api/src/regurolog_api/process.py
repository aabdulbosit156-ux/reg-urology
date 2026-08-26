import asyncio
import os

from regurolog_api.server import run as run_api
from regurolog_api.worker import run as run_worker


def main() -> None:
    process = os.getenv("REGUROLOG_PROCESS", "all").strip().lower()
    # "all" (default) runs the API which also serves the frontend and co-hosts the
    # worker loop in-process; "api" runs the API alone; "worker" runs only the loop.
    if process in {"all", "api"}:
        run_api()
        return
    if process == "worker":
        asyncio.run(run_worker())
        return
    raise RuntimeError("REGUROLOG_PROCESS faqat 'all', 'api' yoki 'worker' bo‘lishi mumkin")


if __name__ == "__main__":
    main()
