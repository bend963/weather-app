"""Drop and recreate the public schema of DATABASE_URL. For disposable test databases only.

Refuses to run unless the database name ends in _test or _e2e.
"""

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from weather_api.config import get_settings

url = make_url(get_settings().database_url)
if not (url.database or "").endswith(("_test", "_e2e")):
    sys.exit(f"refusing to reset database {url.database!r}: name must end in _test or _e2e")
engine = create_engine(url)
with engine.begin() as conn:
    conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"))
print(f"reset {url.database}")
