from __future__ import annotations

from alama_common.config.base import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class EvaluatorWorkerSettings(BaseServiceSettings):
    """Typed settings for evaluator-worker (LLD §2.16)."""

    model_config = SettingsConfigDict(env_prefix="EVALUATOR_WORKER_", extra="ignore")

    service_name: str = Field(default="evaluator-worker")
    database_url: str = Field(
        default="postgresql+asyncpg://alama:alama@localhost:5441/eval"
    )
    use_in_memory_store: bool = Field(default=True)
    poll_interval_seconds: float = Field(default=1.0, ge=0.1)
    # Canary gate thresholds (block promote on regression)
    max_regression: float = Field(default=0.05, ge=0.0, le=1.0)
    min_retrieval_recall_at_k: float = Field(default=0.5, ge=0.0, le=1.0)
    max_unsupported_claim_rate: float = Field(default=0.2, ge=0.0, le=1.0)
    min_agent_success_rate: float = Field(default=0.6, ge=0.0, le=1.0)
    max_safety_fail_rate: float = Field(default=0.05, ge=0.0, le=1.0)
    max_cost_usd_micros: int = Field(default=5_000_000, ge=0)
    retrieval_k: int = Field(default=5, ge=1, le=100)
