"""Custom exceptions for TH-EVI model.

This module provides structured exception hierarchy for better error handling
and debugging across all model layers.
"""


class THEVIError(Exception):
    """Base exception for all TH-EVI errors."""
    pass


class AdoptionError(THEVIError):
    """Errors in EV adoption model."""
    pass


class InvalidYearError(AdoptionError):
    """Year parameter out of valid range."""
    
    def __init__(self, year: int, min_year: int = 2018, max_year: int = 2050):
        self.year = year
        self.min_year = min_year
        self.max_year = max_year
        super().__init__(
            f"Year {year} out of valid range [{min_year}, {max_year}]. "
            f"S-curve calibrated for years {min_year}-{max_year}."
        )


class ProvinceNotFoundError(AdoptionError):
    """Province not found in configuration."""
    
    def __init__(self, province: str, available_provinces: list[str] = None):
        self.province = province
        self.available_provinces = available_provinces or []
        msg = f"Province '{province}' not found in configuration."
        if self.available_provinces:
            msg += f" Available: {', '.join(self.available_provinces[:5])}"
        super().__init__(msg)


class LocationError(THEVIError):
    """Errors in location demand model."""
    pass


class InvalidCoordinatesError(LocationError):
    """Invalid latitude/longitude coordinates."""
    
    def __init__(self, lat: float, lon: float):
        self.lat = lat
        self.lon = lon
        super().__init__(
            f"Invalid coordinates: lat={lat}, lon={lon}. "
            f"Expected lat in [-90, 90] and lon in [-180, 180]."
        )


class UnknownLocationError(LocationError):
    """Location ID not found in landmark database."""
    
    def __init__(self, location_id: str, available_ids: list[str] = None):
        self.location_id = location_id
        self.available_ids = available_ids or []
        msg = f"Unknown location ID: '{location_id}'."
        if self.available_ids:
            msg += f" Available: {', '.join(self.available_ids[:5])}"
        super().__init__(msg)


class InvalidLocationTypeError(LocationError):
    """Invalid location type specified."""
    
    def __init__(self, location_type: str, valid_types: list[str] = None):
        self.location_type = location_type
        self.valid_types = valid_types or ["highway", "city_center", "destination", "suburban"]
        super().__init__(
            f"Invalid location type: '{location_type}'. "
            f"Valid types: {', '.join(self.valid_types)}"
        )


class SiteError(THEVIError):
    """Errors in site readiness and competition model."""
    pass


class InvalidStationSpecError(SiteError):
    """Invalid station specification parameters."""
    
    def __init__(self, field: str, value: any, reason: str = ""):
        self.field = field
        self.value = value
        self.reason = reason
        msg = f"Invalid station spec: {field}={value}"
        if reason:
            msg += f". {reason}"
        super().__init__(msg)


class InvalidReadinessScoreError(SiteError):
    """Site readiness score out of valid range [0, 1]."""
    
    def __init__(self, field: str, value: float):
        self.field = field
        self.value = value
        super().__init__(
            f"Invalid readiness score: {field}={value}. "
            f"Expected value in range [0.0, 1.0]."
        )


class InvalidStationFormatError(SiteError):
    """Unknown station format specified."""
    
    def __init__(self, format_name: str, valid_formats: list[str] = None):
        self.format_name = format_name
        self.valid_formats = valid_formats or [
            "highway_hub", "roadside_destination", "urban_hub",
            "mall_surface_lot", "community_mall", "inside_parking", "test_launch"
        ]
        super().__init__(
            f"Invalid station format: '{format_name}'. "
            f"Valid formats: {', '.join(self.valid_formats)}"
        )


class TemporalError(THEVIError):
    """Errors in temporal and queueing model."""
    pass


class InvalidQueueParametersError(TemporalError):
    """Invalid queueing model parameters."""
    
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Invalid queue parameters: {reason}")


class UnstableQueueError(TemporalError):
    """Queue is unstable (arrival rate exceeds service capacity)."""
    
    def __init__(self, arrival_rate: float, service_rate: float, plugs: int):
        self.arrival_rate = arrival_rate
        self.service_rate = service_rate
        self.plugs = plugs
        super().__init__(
            f"Queue unstable: arrival_rate={arrival_rate}/h exceeds "
            f"service capacity ({plugs} plugs × {service_rate}/h). "
            f"Increase number of plugs or reduce arrival rate."
        )


class InvalidStationTypeError(TemporalError):
    """Unknown station type for hourly profile."""
    
    def __init__(self, station_type: str, valid_types: list[str] = None):
        self.station_type = station_type
        self.valid_types = valid_types or ["highway", "destination", "urban_hub", "city_center"]
        super().__init__(
            f"Invalid station type: '{station_type}'. "
            f"Valid types: {', '.join(self.valid_types)}"
        )


class DataError(THEVIError):
    """Errors in data loading and parsing."""
    pass


class DataFileNotFoundError(DataError):
    """Required data file not found."""
    
    def __init__(self, filename: str, search_paths: list[str] = None):
        self.filename = filename
        self.search_paths = search_paths or []
        msg = f"Data file not found: '{filename}'."
        if self.search_paths:
            msg += f" Searched in: {', '.join(self.search_paths)}"
        super().__init__(msg)


class DataParsingError(DataError):
    """Error parsing data file."""
    
    def __init__(self, filename: str, reason: str):
        self.filename = filename
        self.reason = reason
        super().__init__(f"Error parsing '{filename}': {reason}")


class InsufficientDataError(DataError):
    """Insufficient data for requested operation."""
    
    def __init__(self, operation: str, required: int, available: int):
        self.operation = operation
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient data for {operation}: "
            f"required {required}, but only {available} available."
        )


class ValidationError(THEVIError):
    """Errors in validation process."""
    pass


class CalibrationError(ValidationError):
    """Error in model calibration."""
    
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Calibration error: {reason}")


class InsufficientGroundTruthError(ValidationError):
    """Not enough ground truth data for validation."""
    
    def __init__(self, n_points: int, n_params: int, recommended: int = 5):
        self.n_points = n_points
        self.n_params = n_params
        self.recommended = recommended
        super().__init__(
            f"Insufficient ground truth: {n_points} points for {n_params} parameters. "
            f"Need at least {recommended} points for reliable validation."
        )
