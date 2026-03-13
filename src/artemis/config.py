from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARTEMIS_", env_file=".env", env_file_encoding="utf-8")

    # Database — set database_url for a full override (docker-compose),
    # or set the individual db_* fields (K8s with password from Secret).
    database_url: str = ""
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "artemis"
    db_password: str = "artemis"
    db_name: str = "artemis"

    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "artemis-main"
    temporal_orchestration_queue: str = "artemis-orchestration"
    temporal_llm_queue: str = "artemis-llm"
    temporal_simulation_queue: str = "artemis-simulation"
    temporal_notification_queue: str = "artemis-notifications"

    # Keycloak
    keycloak_url: str = "http://localhost:8180"
    keycloak_realm: str = "artemis-sim"
    keycloak_client_id: str = "artemis-app"
    keycloak_client_secret: str = ""

    # Auth
    auth_disabled: bool = False
    session_secret: str = "artemis-dev-secret-change-in-production"

    # LLM
    llm_provider: str = "openai"  # openai | anthropic | local
    llm_model: str = "gpt-4"
    llm_base_url: str = ""
    llm_api_key: str = ""

    # App
    debug: bool = False
    base_url: str = "http://localhost:8000"
    cors_origins: str = ""  # comma-separated additional CORS origins
    verify_ssl: bool = True  # set False for internal/enterprise CAs

    @property
    def keycloak_issuer_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_openid_config_url(self) -> str:
        return f"{self.keycloak_issuer_url}/.well-known/openid-configuration"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_issuer_url}/protocol/openid-connect/certs"

    @property
    def keycloak_token_url(self) -> str:
        return f"{self.keycloak_issuer_url}/protocol/openid-connect/token"

    @property
    def keycloak_authorize_url(self) -> str:
        return f"{self.keycloak_issuer_url}/protocol/openid-connect/auth"

    @property
    def keycloak_logout_url(self) -> str:
        return f"{self.keycloak_issuer_url}/protocol/openid-connect/logout"


@lru_cache
def get_settings() -> Settings:
    return Settings()
