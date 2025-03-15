"""Models for the Flume API."""
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, ConfigDict


class FlumeResponse(BaseModel):
    """Base response model for Flume API."""
    
    success: bool = Field(True, description="Whether the request was successful")
    code: int = Field(0, description="Response code")
    message: str = Field(..., description="Response message")
    http_code: int = Field(200, description="HTTP status code")
    http_message: str = Field("OK", description="HTTP status message")
    detailed: Optional[List[str]] = Field(None, description="Detailed error messages")
    count: int = Field(0, description="Number of items in data")
    pagination: Optional[Dict[str, Any]] = Field(None, description="Pagination information")


class Device(BaseModel):
    """Represents a Flume water sensor device."""
    
    id: str = Field(..., description="The unique identifier of the device")
    type: int = Field(..., description="Device type (1: Bridge, 2: Water Sensor)")
    location_id: Optional[int] = Field(None, description="ID of associated location")
    user_id: Optional[int] = Field(None, description="ID of device owner")
    bridge_id: Optional[str] = Field(None, description="ID of associated bridge device")
    oriented: bool = Field(True, description="Whether device is properly oriented")
    last_seen: datetime = Field(..., description="When the device was last seen")
    connected: bool = Field(True, description="Whether device is connected")
    battery_level: Optional[str] = Field(None, description="Battery level status")
    product: Optional[str] = Field(None, description="Product model")


class Location(BaseModel):
    """Represents a Flume device location."""
    
    id: int = Field(..., description="Location ID")
    user_id: int = Field(..., description="User ID")
    name: str = Field(..., description="Location name")
    primary_location: bool = Field(False, description="Whether this is primary location")
    address: Optional[str] = Field(None, description="Street address")
    address_2: Optional[str] = Field(None, description="Additional address info")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State")
    postal_code: Optional[str] = Field(None, description="Postal/ZIP code")
    country: Optional[str] = Field(None, description="Country")
    tz: str = Field(..., description="Timezone")
    installation: str = Field(..., description="Installation status")
    building_type: str = Field(..., description="Type of building")


class WaterUsageQuery(BaseModel):
    """Query parameters for water usage data."""
    
    request_id: str = Field(..., description="Unique identifier for the query")
    bucket: str = Field(..., description="Time bucket size")
    since_datetime: str = Field(..., description="Start time for query")
    until_datetime: Optional[str] = Field(None, description="End time for query")
    group_multiplier: Optional[int] = Field(None, description="Group multiplier")
    operation: Optional[str] = Field(None, description="Aggregation operation")
    sort_direction: Optional[str] = Field(None, description="Sort direction")
    units: str = Field("GALLONS", description="Units of measurement")
    types: List[str] = Field(default_factory=list, description="Water types to include")


class WaterUsageReading(BaseModel):
    """Individual water usage reading."""
    
    datetime: str = Field(..., description="Timestamp of reading")
    value: float = Field(..., description="Water usage value")


class UsageAlert(BaseModel):
    """Water usage alert."""
    
    id: int = Field(..., description="Alert ID")
    device_id: str = Field(..., description="Device ID")
    triggered_datetime: datetime = Field(..., description="When alert was triggered")
    flume_leak: bool = Field(False, description="Whether Flume detected this as a leak")
    query: WaterUsageQuery = Field(..., description="Query that triggered the alert")
    event_rule_name: str = Field(..., description="Name of the rule that triggered alert")


class UsageAlertRule(BaseModel):
    """Model for a usage alert rule."""

    id: Union[str, int]
    name: str
    active: bool
    flow_rate: float
    duration: int
    notify_every: int


class WaterUsage(BaseModel):
    """Represents water usage data from a Flume device."""
    
    device_id: str = Field(..., description="The ID of the device reporting usage")
    timestamp: datetime = Field(..., description="The timestamp of the measurement")
    value: float = Field(..., description="The water usage value in gallons")
    units: str = Field(default="gallons", description="The units of measurement")
    
    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    ) 