from pathlib import Path

import pytest
from typer.testing import CliRunner

from insight import __version__
from insight.cli import app

runner = CliRunner()


def test_help_lists_version_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output


def test_version_prints_version_and_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", "/tmp/insight-test")
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"insight-ai {__version__}" in result.output
    assert "/tmp/insight-test" in result.output
