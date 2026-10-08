import pytest
from weather_api.units import (
    cardinal_direction,
    convert_precipitation,
    convert_temperature,
    convert_temperature_delta,
    convert_wind,
)


def test_temperature():
    assert convert_temperature(0, "F") == 32
    assert convert_temperature(25.6, "F") == 78.1
    assert convert_temperature(-40, "F") == -40
    assert convert_temperature(21.04, "C") == 21.0
    assert convert_temperature(None, "F") is None
    assert convert_temperature_delta(5, "F") == 9


def test_precipitation():
    assert convert_precipitation(25.4, "in") == 1.0
    assert convert_precipitation(4.6, "in") == 0.18
    assert convert_precipitation(4.64, "mm") == 4.6


def test_wind():
    assert convert_wind(10, "mph") == pytest.approx(22.4)
    assert convert_wind(10, "kmh") == 36
    assert convert_wind(10, "kt") == pytest.approx(19.4)
    assert convert_wind(3.6, "mps") == 3.6


@pytest.mark.parametrize(
    "deg,label", [(0, "N"), (11, "N"), (12, "NNE"), (45, "NE"), (180, "S"), (350, "N"), (270, "W")]
)
def test_cardinal(deg, label):
    assert cardinal_direction(deg) == label
