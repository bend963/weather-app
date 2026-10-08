import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/weather_test"
)
os.environ["ENVIRONMENT"] = "test"
os.environ["FORECAST_PROVIDER"] = "mock"
