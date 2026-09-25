import os


class Settings:
    """
    Centralized configuration, read entirely from the environment.

    IMPORTANT: The trust threshold and database location live here, never in
    the LLM's prompt or context. The agent has no visibility into these values.
    """

    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql://postgres:postgres@db:5432/agent_harness"
    )
    TRUST_THRESHOLD: int = int(os.environ.get("TRUST_THRESHOLD", "3"))
    MOCK_LLM_ENABLED: bool = os.environ.get("MOCK_LLM_ENABLED", "true").lower() == "true"
    API_PORT: int = int(os.environ.get("API_PORT", "8000"))


settings = Settings()
