from datetime import UTC, datetime


def get_now() -> datetime:
    """Current time; a FastAPI dependency so tests can freeze it."""
    return datetime.now(UTC)
