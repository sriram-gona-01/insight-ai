from pathlib import Path

import pytest

from insight.config import Settings


def test_data_dir_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    assert Settings(_env_file=None).data_dir == Path("data")


def test_data_dir_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", "/tmp/insight-test")
    assert Settings(_env_file=None).data_dir == Path("/tmp/insight-test")


def test_data_dir_from_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("DATA_DIR=/srv/insight\n")
    assert Settings(_env_file=env_file).data_dir == Path("/srv/insight")
