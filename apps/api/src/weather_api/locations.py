"""Saved locations and their mapping onto shared grid points."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from weather_api.errors import ApiError, not_found
from weather_api.grid import InvalidCoordinate, normalize_to_grid, validate_coordinate
from weather_api.models import SavedLocation, WeatherGridPoint
from weather_api.timezones import timezone_for
from weather_api.visitors import Owner

# Coordinates are stored to 6 decimal places (~0.1 m), which is what NUMERIC(9,6) holds.
_SIX_PLACES = Decimal("0.000001")


def get_or_create_grid_point(
    session: Session, latitude: float, longitude: float
) -> WeatherGridPoint:
    """Return the shared grid point for a coordinate, creating it once.

    Concurrent requests for the same cell are safe: the unique constraint on
    (model_name, model_grid_identifier) makes the insert an upsert, and
    reusing a point reactivates it and records that it was requested.
    """
    cell = normalize_to_grid(latitude, longitude)
    # The grid node can sit offshore of a coastal location, where only a fixed
    # "Etc/GMT" offset exists; prefer the location's real zone in that case so
    # daily summaries follow local daylight saving time.
    tz = timezone_for(float(cell.latitude), float(cell.longitude))
    if tz.startswith("Etc/") or tz == "UTC":
        tz = timezone_for(latitude, longitude)

    stmt = (
        insert(WeatherGridPoint)
        .values(
            latitude=cell.latitude,
            longitude=cell.longitude,
            model_name=cell.model_name,
            model_grid_identifier=cell.identifier,
            timezone=tz,
        )
        .on_conflict_do_update(
            constraint="uq_grid_points_identifier",
            set_={"active": True, "last_requested_at": func.now()},
        )
        .returning(WeatherGridPoint.id)
    )
    grid_point_id = session.execute(stmt).scalar_one()
    return session.get_one(WeatherGridPoint, grid_point_id)


def list_locations(session: Session, owner: Owner) -> list[SavedLocation]:
    return list(
        session.scalars(
            select(SavedLocation)
            .where(owner.owns())
            .order_by(SavedLocation.is_default.desc(), SavedLocation.created_at, SavedLocation.id)
        )
    )


def get_location(session: Session, owner: Owner, location_id: uuid.UUID) -> SavedLocation:
    """Fetch a location only if this owner owns it.

    Someone else's location is reported as not found, so ids can't be probed.
    """
    location = session.scalars(
        select(SavedLocation).where(SavedLocation.id == location_id, owner.owns())
    ).first()
    if location is None:
        raise not_found()
    return location


def create_location(
    session: Session,
    owner: Owner,
    *,
    name: str,
    latitude: float,
    longitude: float,
    max_locations: int,
) -> SavedLocation:
    try:
        validate_coordinate(latitude, longitude)
    except InvalidCoordinate as exc:
        raise ApiError(422, "invalid_coordinate", str(exc)) from exc

    existing = session.scalar(select(func.count()).select_from(SavedLocation).where(owner.owns()))
    if (existing or 0) >= max_locations:
        raise ApiError(409, "too_many_locations", f"You can save up to {max_locations} locations.")

    grid_point = get_or_create_grid_point(session, latitude, longitude)
    location = SavedLocation(
        **owner.columns(),
        weather_grid_point_id=grid_point.id,
        name=name.strip(),
        latitude=Decimal(str(latitude)).quantize(_SIX_PLACES),
        longitude=Decimal(str(longitude)).quantize(_SIX_PLACES),
        timezone=timezone_for(latitude, longitude),
        is_default=existing == 0,  # the first location becomes the default
    )
    session.add(location)
    session.commit()
    return location


def update_location(
    session: Session,
    owner: Owner,
    location_id: uuid.UUID,
    *,
    name: str | None = None,
    is_default: bool | None = None,
) -> SavedLocation:
    location = get_location(session, owner, location_id)
    if name is not None:
        location.name = name.strip()
    if is_default is True and not location.is_default:
        # Clear the old default first: the partial unique index allows only one.
        session.execute(
            update(SavedLocation)
            .where(owner.owns(), SavedLocation.is_default)
            .values(is_default=False)
        )
        location.is_default = True
    # Unsetting the default directly is ignored: an owner with locations always
    # has a default. Choose another location as default instead.
    session.commit()
    session.refresh(location)
    return location


def delete_location(session: Session, owner: Owner, location_id: uuid.UUID) -> None:
    location = get_location(session, owner, location_id)
    was_default = location.is_default
    grid_point_id = location.weather_grid_point_id
    session.delete(location)
    session.flush()
    if was_default:
        replacement = session.scalars(
            select(SavedLocation)
            .where(owner.owns())
            .order_by(SavedLocation.created_at, SavedLocation.id)
            .limit(1)
        ).first()
        if replacement is not None:
            replacement.is_default = True
    # The grid point stays active for a grace period (see
    # deactivate_unused_grid_points); stamping it starts that clock.
    session.execute(
        update(WeatherGridPoint)
        .where(WeatherGridPoint.id == grid_point_id)
        .values(last_requested_at=func.now())
    )
    session.commit()


def mark_grid_point_requested(session: Session, grid_point: WeatherGridPoint) -> None:
    """Keep a viewed grid point fresh, at most once an hour."""
    if datetime.now(UTC) - grid_point.last_requested_at > timedelta(hours=1):
        session.execute(
            update(WeatherGridPoint)
            .where(WeatherGridPoint.id == grid_point.id)
            .values(last_requested_at=func.now(), active=True)
        )
        session.commit()
