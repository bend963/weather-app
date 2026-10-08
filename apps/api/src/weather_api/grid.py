"""Map a coordinate to a cell of the forecast model grid.

WeatherNext forecasts are published on a regular 0.25° latitude/longitude grid.
Every saved location is snapped to the nearest grid node, and that node, not the
user's coordinate, is what forecasts are computed for. Many locations share one
node (about 28 km × 28 km at the equator, narrower east–west toward the poles),
so each node's forecast is ingested once no matter how many people saved a place
inside it.

The normalization is deterministic and provider-independent, so the mock and
WeatherNext providers produce identical grid identifiers and switching providers
needs no data migration.

TODO(weathernext): confirm the grid resolution and longitude convention of the
WeatherNext dataset we are granted (0–360 vs −180–180) once we can inspect it.
If it differs, change GRID_RESOLUTION_DEG / the identifier and add a migration.
"""

from dataclasses import dataclass
from decimal import Decimal

GRID_MODEL_NAME = "weathernext_0p25"
GRID_RESOLUTION_DEG = Decimal("0.25")


class InvalidCoordinate(ValueError):
    pass


@dataclass(frozen=True)
class GridCell:
    model_name: str
    identifier: str
    latitude: Decimal
    longitude: Decimal
    lat_index: int
    lon_index: int


def validate_coordinate(latitude: float, longitude: float) -> None:
    if not (-90 <= latitude <= 90):
        raise InvalidCoordinate("latitude must be between -90 and 90")
    if not (-180 <= longitude <= 180):
        raise InvalidCoordinate("longitude must be between -180 and 180")


def normalize_to_grid(latitude: float, longitude: float) -> GridCell:
    validate_coordinate(latitude, longitude)
    lat = Decimal(str(latitude))
    lon = Decimal(str(longitude))

    # Index of the nearest node. ROUND_HALF_UP via quantize keeps this stable
    # for points exactly between two nodes.
    lat_index = int((lat / GRID_RESOLUTION_DEG).quantize(Decimal(1), rounding="ROUND_HALF_UP"))
    # Longitude on [0, 360), so +180 and -180 land on the same node.
    lon_360 = lon % 360
    nodes_around = int(Decimal(360) / GRID_RESOLUTION_DEG)
    lon_index = (
        int((lon_360 / GRID_RESOLUTION_DEG).quantize(Decimal(1), rounding="ROUND_HALF_UP"))
        % nodes_around
    )

    node_lat = lat_index * GRID_RESOLUTION_DEG
    node_lon = lon_index * GRID_RESOLUTION_DEG
    if node_lon >= 180:
        node_lon -= 360

    return GridCell(
        model_name=GRID_MODEL_NAME,
        identifier=f"{lat_index}:{lon_index}",
        latitude=node_lat,
        longitude=node_lon,
        lat_index=lat_index,
        lon_index=lon_index,
    )
