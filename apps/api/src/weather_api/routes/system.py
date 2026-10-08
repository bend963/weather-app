from fastapi import APIRouter

from weather_api.schemas import Health

router = APIRouter()


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health(status="ok")
