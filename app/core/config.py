import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for local QASkills services."""

    memory_vault_path: str = "knowledge"
    document_index_path: str = ".qaskills/document_index.json"
    personal_seen_state_path: str = ".qaskills/personal_seen_state.json"
    provider_policy: str = "AUTO"
    local_llm_base_url: str = "http://localhost:1234/v1"
    local_llm_model: str = ""
    provider_probe_timeout_seconds: float = 1.5
    local_llm_timeout_seconds: float = 60.0
    local_llm_max_tokens: int = 512
    local_llm_health_timeout_seconds: float = 20.0
    local_llm_health_max_tokens: int = 8
    codex_command: str = "codex"
    codex_args: str = "exec --skip-git-repo-check"
    codex_timeout_seconds: float = 120.0
    jira_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_timeout_seconds: float = 15.0


def load_settings() -> Settings:
    """Load settings from environment with a portable sample Vault fallback."""

    load_dotenv(dotenv_path=_project_root() / ".env", override=False)

    return Settings(
        memory_vault_path=os.getenv(
            "QASKILLS_MEMORY_VAULT_PATH",
            Settings.memory_vault_path,
        ),
        document_index_path=os.getenv(
            "QASKILLS_DOCUMENT_INDEX_PATH",
            Settings.document_index_path,
        ),
        personal_seen_state_path=os.getenv(
            "QASKILLS_PERSONAL_SEEN_STATE_PATH",
            Settings.personal_seen_state_path,
        ),
        provider_policy=os.getenv(
            "QASKILLS_PROVIDER_POLICY",
            Settings.provider_policy,
        ),
        local_llm_base_url=os.getenv(
            "QASKILLS_LOCAL_LLM_BASE_URL",
            Settings.local_llm_base_url,
        ),
        local_llm_model=os.getenv(
            "QASKILLS_LOCAL_LLM_MODEL",
            Settings.local_llm_model,
        ),
        provider_probe_timeout_seconds=_float_env(
            "QASKILLS_PROVIDER_PROBE_TIMEOUT_SECONDS",
            Settings.provider_probe_timeout_seconds,
        ),
        local_llm_timeout_seconds=_float_env(
            "QASKILLS_LOCAL_LLM_TIMEOUT_SECONDS",
            Settings.local_llm_timeout_seconds,
        ),
        local_llm_max_tokens=_int_env(
            "QASKILLS_LOCAL_LLM_MAX_TOKENS",
            Settings.local_llm_max_tokens,
        ),
        local_llm_health_timeout_seconds=_float_env(
            "QASKILLS_LOCAL_LLM_HEALTH_TIMEOUT_SECONDS",
            Settings.local_llm_health_timeout_seconds,
        ),
        local_llm_health_max_tokens=_int_env(
            "QASKILLS_LOCAL_LLM_HEALTH_MAX_TOKENS",
            Settings.local_llm_health_max_tokens,
        ),
        codex_command=os.getenv(
            "QASKILLS_CODEX_COMMAND",
            Settings.codex_command,
        ),
        codex_args=os.getenv(
            "QASKILLS_CODEX_ARGS",
            Settings.codex_args,
        ),
        codex_timeout_seconds=_float_env(
            "QASKILLS_CODEX_TIMEOUT_SECONDS",
            Settings.codex_timeout_seconds,
        ),
        jira_url=os.getenv(
            "JIRA_URL",
            Settings.jira_url,
        ),
        jira_email=os.getenv(
            "JIRA_EMAIL",
            Settings.jira_email,
        ),
        jira_api_token=os.getenv(
            "JIRA_API_TOKEN",
            Settings.jira_api_token,
        ),
        jira_timeout_seconds=_float_env(
            "JIRA_TIMEOUT_SECONDS",
            Settings.jira_timeout_seconds,
        ),
    )


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)

    if not raw:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)

    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        return default

    try:
        return float(raw)
    except ValueError:
        return default


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]
