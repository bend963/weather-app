from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from weather_api import schemas
from weather_api.db import get_db
from weather_api.locations import list_locations
from weather_api.models import Visitor
from weather_api.visitors import Owner, current_visitor, visitor_preferences

router = APIRouter(prefix="/api/v1", tags=["visitor"])


def _me(session: Session, visitor: Visitor) -> schemas.Me:
    locations = list_locations(session, Owner(visitor_id=visitor.id))
    default = next((loc for loc in locations if loc.is_default), None)
    return schemas.Me(
        visitor=schemas.VisitorProfile(created_at=visitor.created_at),
        preferences=schemas.Preferences.model_validate(visitor_preferences(session, visitor)),
        location_count=len(locations),
        default_location_id=default.id if default else None,
    )


@router.get("/me", response_model=schemas.Me)
def get_me(
    visitor: Visitor = Depends(current_visitor), session: Session = Depends(get_db)
) -> schemas.Me:
    """The anonymous visitor's profile. The first call issues the visitor cookie."""
    return _me(session, visitor)


@router.patch("/me/preferences", response_model=schemas.Preferences)
def update_preferences(
    body: schemas.PreferencesUpdate,
    visitor: Visitor = Depends(current_visitor),
    session: Session = Depends(get_db),
) -> schemas.Preferences:
    prefs = visitor_preferences(session, visitor)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(prefs, field, value)
    session.commit()
    session.refresh(prefs)
    return schemas.Preferences.model_validate(prefs)
