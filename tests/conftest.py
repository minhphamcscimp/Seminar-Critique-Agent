"""Shared test setup."""
import pytest

from seminar_critique.security.audit import AUDIT_PATH_ENV


@pytest.fixture(autouse=True)
def _audit_log_in_tmp(monkeypatch, tmp_path):
    """Keep the tool audit log of every test out of the repository's traces/."""
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv(AUDIT_PATH_ENV, str(path))
    return path
