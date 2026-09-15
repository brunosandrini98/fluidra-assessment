from pool_qa.settings import ROOT, Settings

ENV_VARS = [
    "ANTHROPIC_API_KEY", "INTAKE_MODEL", "RESEARCHER_MODEL", "VERIFIER_MODEL",
    "HISTORY_TURNS", "PIVOT_LANGUAGE", "CHUNKS_PATH",
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
