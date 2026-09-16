from pool_qa.settings import ROOT, Settings

ENV_VARS = [
    "ANTHROPIC_API_KEY", "INTAKE_MODEL", "RESEARCHER_MODEL", "VERIFIER_MODEL",
    "HISTORY_TURNS", "PIVOT_LANGUAGE", "CHUNKS_PATH",
    "SEARCH_K", "MAX_SEARCH_CALLS", "LLM_TIMEOUT_S", "LLM_MAX_RETRIES", "REQUEST_DEADLINE_S",
]


def clean_settings(monkeypatch) -> Settings:
    for var in ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return Settings(_env_file=None)


def test_defaults(monkeypatch):
    s = clean_settings(monkeypatch)
    assert s.intake_model == "claude-haiku-4-5"
    assert s.researcher_model == "claude-sonnet-5"
    assert s.verifier_model == "claude-opus-5"
    assert s.history_turns == 5
    assert s.pivot_language == "en"
    assert s.chunks_path == ROOT / "data" / "chunks.jsonl"
    assert s.anthropic_api_key is None


def test_env_override(monkeypatch):
    clean_settings(monkeypatch)
    monkeypatch.setenv("RESEARCHER_MODEL", "some-other-model")
    assert Settings(_env_file=None).researcher_model == "some-other-model"


def test_runtime_limit_defaults(monkeypatch):
    s = clean_settings(monkeypatch)
    assert s.search_k == 5
    assert s.max_search_calls == 3
    assert s.llm_timeout_s == 60
    assert s.llm_max_retries == 2
    assert s.request_deadline_s == 180


def test_runtime_limit_env_override(monkeypatch):
    clean_settings(monkeypatch)
    monkeypatch.setenv("MAX_SEARCH_CALLS", "1")
    monkeypatch.setenv("REQUEST_DEADLINE_S", "5")
    s = Settings(_env_file=None)
    assert s.max_search_calls == 1
    assert s.request_deadline_s == 5
