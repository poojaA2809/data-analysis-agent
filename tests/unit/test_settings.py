"""Settings + provider auto-detection — no LLM key required."""
import pytest


def test_auto_detects_anthropic(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "")
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "")
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")

    import config.settings as m
    m._settings = None
    s = m.get_settings()
    assert s.anthropic_api_key == "sk-ant-fake"
    assert s.gemini_api_key == ""


def test_defaults_for_agent_bounds(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    import config.settings as m
    m._settings = None
    s = m.get_settings()
    assert s.max_steps == 4
    assert s.exec_timeout == 25


def test_agent_bounds_overridable(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("AGENT_MAX_STEPS", "2")
    monkeypatch.setenv("AGENT_EXEC_TIMEOUT", "10")
    import config.settings as m
    m._settings = None
    s = m.get_settings()
    assert s.max_steps == 2
    assert s.exec_timeout == 10


def test_provider_raises_with_no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENT_ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("AGENT_GEMINI_API_KEY", "")
    monkeypatch.setenv("AGENT_LLM_PROVIDER", "")
    monkeypatch.setenv("AGENT_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")

    import config.settings as m
    m._settings = None

    from llm.client import _make_provider
    with pytest.raises(RuntimeError, match="No LLM provider configured"):
        _make_provider()
