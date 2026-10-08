"""Anonymous visitor identity.

The weather_visitor cookie holds only an opaque id: "<visitor uuid>.<signature>".
The HMAC signature (keyed by COOKIE_SECRET) means a client cannot invent or
alter an id; a tampered or unknown cookie is treated as no cookie. Preferences
and saved locations live in Postgres, never in the cookie.

Ownership is always derived from this cookie server-side. Request bodies never
carry a visitor id.
"""

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from weather_api.config import Settings, get_settings
from weather_api.db import get_db
from weather_api.models import SavedLocation, Visitor, VisitorPreferences

COOKIE_NAME = "weather_visitor"
COOKIE_MAX_AGE = 365 * 24 * 3600
# last_seen_at (and the cookie's expiry) is refreshed at most this often.
TOUCH_INTERVAL = timedelta(hours=12)


@dataclass(frozen=True)
class Owner:
    """Who owns saved resources. Exactly one of the ids is set.

    v1 only has visitors; when accounts arrive, an authenticated request
    resolves to Owner(user_id=...) and every query below keeps working.
    """

    visitor_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None

    def owns(self):  # type: ignore[no-untyped-def]
        """SQL filter matching saved_locations owned by this owner."""
        if self.user_id is not None:
            return SavedLocation.user_id == self.user_id
        return SavedLocation.visitor_id == self.visitor_id

    def columns(self) -> dict[str, uuid.UUID | None]:
        return {"visitor_id": self.visitor_id, "user_id": self.user_id}


def _sign(visitor_id: str, secret: str) -> str:
    mac = hmac.new(secret.encode(), visitor_id.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()


def encode_cookie(visitor_id: uuid.UUID, secret: str) -> str:
    vid = str(visitor_id)
    return f"{vid}.{_sign(vid, secret)}"


def decode_cookie(value: str | None, secret: str) -> uuid.UUID | None:
    if not value or "." not in value:
        return None
    vid, signature = value.split(".", 1)
    if not hmac.compare_digest(signature, _sign(vid, secret)):
        return None
    try:
        return uuid.UUID(vid)
    except ValueError:
        return None


def _set_cookie(response: Response, visitor_id: uuid.UUID, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME,
        encode_cookie(visitor_id, settings.cookie_secret),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def create_visitor(session: Session) -> Visitor:
    visitor = Visitor()
    visitor.preferences = VisitorPreferences()
    session.add(visitor)
    session.flush()
    return visitor


def _load(request: Request, session: Session, settings: Settings) -> Visitor | None:
    visitor_id = decode_cookie(request.cookies.get(COOKIE_NAME), settings.cookie_secret)
    if visitor_id is None:
        return None
    return session.get(Visitor, visitor_id)


def _touch(visitor: Visitor, session: Session, response: Response, settings: Settings) -> None:
    now = datetime.now(UTC)
    if now - visitor.last_seen_at > TOUCH_INTERVAL:
        session.execute(update(Visitor).where(Visitor.id == visitor.id).values(last_seen_at=now))
        session.commit()
        _set_cookie(response, visitor.id, settings)  # roll the one-year expiry forward


def current_visitor(
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Visitor:
    """The caller's visitor, created (and cookie issued) on first contact."""
    visitor = _load(request, session, settings)
    if visitor is None:
        visitor = create_visitor(session)
        session.commit()
        _set_cookie(response, visitor.id, settings)
    else:
        _touch(visitor, session, response, settings)
    return visitor


def optional_visitor(
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Visitor | None:
    """The caller's visitor if they have one. Never creates rows (cheap for bots)."""
    visitor = _load(request, session, settings)
    if visitor is not None:
        _touch(visitor, session, response, settings)
    return visitor


def owner_of(visitor: Visitor | None) -> Owner | None:
    return Owner(visitor_id=visitor.id) if visitor else None


def visitor_preferences(session: Session, visitor: Visitor) -> VisitorPreferences:
    prefs = session.scalars(
        select(VisitorPreferences).where(VisitorPreferences.visitor_id == visitor.id)
    ).first()
    if prefs is None:  # visitors created before preferences existed
        prefs = VisitorPreferences(visitor_id=visitor.id)
        session.add(prefs)
        session.commit()
    return prefs
