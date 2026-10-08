"""Write the API's OpenAPI schema to a file (used to generate TypeScript types).

uv run python scripts/export_openapi.py packages/api-types/openapi.json
"""

import json
import sys
from pathlib import Path

from weather_api.app import create_app

out = Path(sys.argv[1] if len(sys.argv) > 1 else "openapi.json")
out.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")
print(f"wrote {out}")
