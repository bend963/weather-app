from fastapi import APIRouter, Depends, Query, Request

from weather_api import schemas
from weather_api.config import get_settings
from weather_api.errors import ApiError
from weather_api.geocoding import GeocodingProvider, GeocodingUnavailable, get_geocoder
from weather_api.ratelimit import RateLimiter

router = APIRouter(prefix="/api/v1/geocode", tags=["geocode"])

search_limiter = RateLimiter(get_settings().search_rate_per_minute, 60)


def _client_key(request: Request) -> str:
    # Cloud Run / Vercel put the original client first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


@router.get("/search", response_model=list[schemas.Place])
def search(
    request: Request,
    q: str = Query(min_length=2, max_length=120),
    geocoder: GeocodingProvider = Depends(get_geocoder),
) -> list[schemas.Place]:
    search_limiter.check(_client_key(request))
    try:
        return [schemas.Place(**p.__dict__) for p in geocoder.search_locations(q)]
    except GeocodingUnavailable as exc:
        raise ApiError(
            503, "geocoding_unavailable", "Location search is unavailable right now."
        ) from exc


@router.get("/reverse", response_model=schemas.Place | None)
def reverse(
    request: Request,
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    geocoder: GeocodingProvider = Depends(get_geocoder),
) -> schemas.Place | None:
    search_limiter.check(_client_key(request))
    try:
        place = geocoder.reverse_geocode(lat, lon)
    except GeocodingUnavailable as exc:
        raise ApiError(
            503, "geocoding_unavailable", "Location search is unavailable right now."
        ) from exc
    return schemas.Place(**place.__dict__) if place else None
