import pytest
from regurolog_api import process, server


@pytest.mark.parametrize("value", ["not-a-port", "0", "65536"])
def test_server_rejects_invalid_port(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("PORT", value)

    with pytest.raises(RuntimeError, match="PORT"):
        server._port()


def test_server_uses_default_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PORT", raising=False)

    assert server._port() == 8000


def test_process_dispatches_api(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setenv("REGUROLOG_PROCESS", "api")
    monkeypatch.setattr(process, "run_api", lambda: calls.append("api"))

    process.main()

    assert calls == ["api"]


def test_process_dispatches_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    async def fake_worker() -> None:
        calls.append("worker")

    monkeypatch.setenv("REGUROLOG_PROCESS", "worker")
    monkeypatch.setattr(process, "run_worker", fake_worker)

    process.main()

    assert calls == ["worker"]


def test_process_rejects_unknown_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGUROLOG_PROCESS", "scheduler")

    with pytest.raises(RuntimeError, match="REGUROLOG_PROCESS"):
        process.main()
