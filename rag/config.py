"""Environment-driven settings."""

import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # .env loading is optional; env vars still work


def _env(key: str, default: str) -> str:
    return os.getenv(key, default)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env_path(key: str, *parts: str) -> str:
    """Path setting: env var wins; default is relative to the project root."""
    value = os.getenv(key)
    if value:
        return value
    return os.path.join(PROJECT_ROOT, *parts)


@dataclass
class Settings:
    deepseek_api_key: str = field(default_factory=lambda: _env("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = field(default_factory=lambda: _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    deepseek_model: str = field(default_factory=lambda: _env("DEEPSEEK_MODEL", "deepseek-chat"))

    embedding_api_key: str = field(default_factory=lambda: _env("EMBEDDING_API_KEY", ""))
    embedding_base_url: str = field(default_factory=lambda: _env("EMBEDDING_BASE_URL", "https://api.siliconflow.cn/v1"))
    embedding_model: str = field(default_factory=lambda: _env("EMBEDDING_MODEL", "BAAI/bge-m3"))
    embedding_dim: int = field(default_factory=lambda: int(_env("EMBEDDING_DIM", "1024")))

    top_k: int = field(default_factory=lambda: int(_env("TOP_K", "6")))
    input_price_per_m: float = field(default_factory=lambda: float(_env("INPUT_PRICE_PER_M", "0.27")))
    output_price_per_m: float = field(default_factory=lambda: float(_env("OUTPUT_PRICE_PER_M", "1.10")))

    chroma_dir: str = field(default_factory=lambda: _env("CHROMA_DIR", "storage/chroma"))
    chunks_json: str = field(default_factory=lambda: _env("CHUNKS_JSON", "storage/chunks.json"))
    data_dirs: str = field(default_factory=lambda: _env("DATA_DIRS", "data"))
    rerank_provider: str = field(default_factory=lambda: _env("RERANK_PROVIDER", "api"))
    rerank_model: str = field(default_factory=lambda: _env("RERANK_MODEL", "BAAI/bge-reranker-v2-m3"))
    rerank_api_key: str = field(default_factory=lambda: _env("RERANK_API_KEY", ""))
    rerank_base_url: str = field(default_factory=lambda: _env("RERANK_BASE_URL", "https://api.siliconflow.cn/v1"))

    # --- personal data locations (template defaults are project-relative) ---
    tracker_xlsx: str = field(default_factory=lambda: _env_path("TRACKER_XLSX", "data", "tracker.xlsx"))
    cv_dir: str = field(default_factory=lambda: _env_path("CV_DIR", "cv"))
    cv_v1: str = field(default_factory=lambda: _env_path("CV_V1", "cv", "cv_v1.docx"))
    cv_v2: str = field(default_factory=lambda: _env_path("CV_V2", "cv", "cv_v2.docx"))
    output_dir: str = field(default_factory=lambda: _env_path("OUTPUT_DIR", "output"))
    nus_mail_dir: str = field(default_factory=lambda: _env_path("NUS_MAIL_DIR", "data", "nus_emails"))
    candidate_summary: str = field(default_factory=lambda: _env_path("CANDIDATE_SUMMARY", "data", "candidate_summary.md"))
    push_enabled: str = field(default_factory=lambda: _env("PUSH_ENABLED", "false"))
    push_channel: str = field(default_factory=lambda: _env("PUSH_CHANNEL", "email"))


settings = Settings()
