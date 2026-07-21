from __future__ import annotations

from alama_common.config import BaseServiceSettings
from pydantic import Field
from pydantic_settings import SettingsConfigDict


class AgentWorkerSettings(BaseServiceSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_WORKER_", extra="ignore")

    service_name: str = Field(default="agent-worker")
    task_queue: str = Field(default="agent-general")
    max_plan_steps: int = Field(default=20, ge=1, le=100)
    max_reflections: int = Field(default=5, ge=0, le=50)
    max_replans: int = Field(default=2, ge=0, le=20)
    planner_template: str = Field(default="planner.v1")
    coder_template: str = Field(default="coder.v1")
    tester_template: str = Field(default="tester.v1")
    reviewer_template: str = Field(default="reviewer.v1")
    security_template: str = Field(default="security.v1")
    poll_interval_seconds: float = Field(default=1.0, ge=0.1)
