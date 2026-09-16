from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    anthropic_api_key: str | None = None
    intake_model: str = "claude-haiku-4-5"
    researcher_model: str = "claude-sonnet-5"
    verifier_model: str = "claude-opus-5"
    history_turns: int = 5
    pivot_language: str = "en"
    chunks_path: Path = ROOT / "data" / "chunks.jsonl"
