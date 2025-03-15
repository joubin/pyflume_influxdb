"""Custom exceptions for the pyflume_influxdb package."""


class FlumeError(Exception):
    """Base exception for Flume API errors."""
    pass


class FlumeAuthError(FlumeError):
    """Exception raised when authentication with the Flume API fails."""
    pass


class FlumeAPIError(FlumeError):
    """Exception raised when a Flume API request fails."""
    pass


class FlumeInfluxDBError(FlumeError):
    """Exception raised when an InfluxDB operation fails."""
    pass 