from pydantic import BaseModel, Field


class StormState(BaseModel):
    lat: float = Field(ge=0, le=35)
    lon: float = Field(ge=55, le=100)
    wind: float = Field(ge=0, le=200, description="max sustained wind, kt")
    pressure: float = Field(ge=850, le=1050, description="min central pressure, hPa")
    wind_trend: float = Field(0, description="wind change over the last 6 h, kt")
    pressure_trend: float = Field(0, description="pressure change over the last 6 h, hPa")
    radius_km: float | None = Field(None, gt=0, le=1500, description="exposure radius; defaults to server setting")


class Intensity(BaseModel):
    next_wind_kt: float
    delta_kt: float
    category: str


class DistrictImpact(BaseModel):
    state: str
    district: str
    lat: float
    lon: float
    population: int
    density: float
    distance_km: float
    affected: int
    low: int
    high: int
    density_capped: bool


class Forecast(BaseModel):
    intensity: Intensity
    radius_km: float
    districts_in_range: int
    districts: list[DistrictImpact]
