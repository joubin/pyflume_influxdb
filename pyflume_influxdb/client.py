"""Client for interacting with the Flume API.

The client uses two main endpoints:
- BASE_URL: https://api.flumewater.com for general API requests
- AUTH_URL: https://api.flumetech.com/oauth/token for authentication
"""

import asyncio
import jwt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
import os

import aiohttp
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from .exceptions import FlumeAuthError, FlumeAPIError, FlumeInfluxDBError
from .models import (Device, FlumeResponse, Location, UsageAlert, UsageAlertRule,
                    WaterUsageQuery, WaterUsageReading)
from .cache import FlumeCache


class FlumeClient:
    """Client for interacting with the Flume API."""

    BASE_URL = "https://api.flumewater.com"
    AUTH_URL = "https://api.flumetech.com/oauth/token"
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        base_url: str = "https://api.flumewater.com",
        influxdb_url: Optional[str] = None,
        influxdb_token: Optional[str] = None,
        influxdb_org: Optional[str] = None,
        influxdb_bucket: Optional[str] = None,
        influxdb_measurement: Optional[str] = None,
        cache_dir: Optional[str] = None,
    ) -> None:
        """Initialize the Flume client.
        
        Args:
            client_id: Flume API client ID
            client_secret: Flume API client secret
            username: Flume account username
            password: Flume account password
            base_url: Base URL for Flume API
            influxdb_url: InfluxDB server URL
            influxdb_token: InfluxDB authentication token
            influxdb_org: InfluxDB organization
            influxdb_bucket: InfluxDB bucket name
            influxdb_measurement: InfluxDB measurement name
            cache_dir: Directory for local cache (optional)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._access_token: Optional[str] = None
        self._user_id: Optional[str] = None
        self._influxdb_client = None
        self.cache = FlumeCache(cache_dir) if cache_dir else None

        # InfluxDB configuration
        self.influxdb_url = influxdb_url
        self.influxdb_token = influxdb_token
        self.influxdb_org = influxdb_org
        self.influxdb_bucket = influxdb_bucket
        self.influxdb_measurement = influxdb_measurement or "water_usage"
    
    @property
    def user_id(self) -> Optional[str]:
        """Get the authenticated user ID."""
        return self._user_id
    
    async def __aenter__(self):
        """Set up the client session."""
        self._session = aiohttp.ClientSession()
        if self.influxdb_url and self.influxdb_token:
            self._influxdb_client = InfluxDBClient(
                url=self.influxdb_url,
                token=self.influxdb_token,
                org=self.influxdb_org
            )
            self._write_api = self._influxdb_client.write_api(write_options=SYNCHRONOUS)
        await self.authenticate()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up the client session."""
        if self._session:
            await self._session.close()
        if self._influxdb_client:
            self._influxdb_client.close()
    
    async def connect(self) -> None:
        """Connect to the Flume API and authenticate."""
        await self.authenticate()
    
    async def authenticate(self) -> None:
        """Authenticate with the Flume API."""
        if not self._session:
            self._session = aiohttp.ClientSession()

        auth_data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password
        }

        async with self._session.post(f"{self.base_url}/oauth/token", json=auth_data) as response:
            if response.status != 200:
                raise FlumeAuthError("Failed to authenticate with Flume API")
            
            data = await response.json()
            self._access_token = data.get("data", [{}])[0].get("access_token")
            self._user_id = data.get("data", [{}])[0].get("user_id")
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the Flume API."""
        if not self._session:
            raise RuntimeError("Client not connected. Call connect() first.")

        if not self._access_token:
            await self.authenticate()

        # Convert boolean values to strings in params
        if params:
            params = {k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items()}

        async with self._session.request(
            method,
            f"{self.base_url}{endpoint}",
            headers={"Authorization": f"Bearer {self._access_token}"},
            params=params,
            json=json,
        ) as response:
            if response.status == 401:
                # Token expired, re-authenticate and retry
                await self.authenticate()
                return await self._request(method, endpoint, params, json)

            response.raise_for_status()
            return await response.json()
    
    async def get_devices(self, **kwargs) -> List[Device]:
        """Get all devices associated with the user."""
        params = {
            "limit": kwargs.get("limit", 50),
            "offset": kwargs.get("offset", 0),
            "sort_field": kwargs.get("sort_field", "id"),
            "sort_direction": kwargs.get("sort_direction", "ASC"),
            "user": str(kwargs.get("user", False)).lower(),
            "location": str(kwargs.get("location", False)).lower(),
            "list_shared": str(kwargs.get("list_shared", False)).lower(),
        }
        response = await self._request("GET", f"/users/{self.user_id}/devices", params=params)
        return [Device(**device) for device in response["data"]]
    
    async def get_device(self, device_id: str, **kwargs) -> Device:
        """Get a specific device by ID."""
        params = {
            "user": str(kwargs.get("user", False)).lower(),
            "location": str(kwargs.get("location", False)).lower(),
        }
        response = await self._request(
            "GET", f"/users/{self.user_id}/devices/{device_id}", params=params
        )
        return Device(**response["data"][0])
    
    async def get_locations(self, **kwargs) -> List[Location]:
        """Get all locations associated with the user."""
        params = {
            "limit": kwargs.get("limit", 50),
            "offset": kwargs.get("offset", 0),
            "sort_field": kwargs.get("sort_field", "id"),
            "sort_direction": kwargs.get("sort_direction", "ASC"),
            "list_shared": str(kwargs.get("list_shared", False)).lower(),
        }
        response = await self._request("GET", f"/users/{self.user_id}/locations", params=params)
        return [Location(**location) for location in response["data"]]
    
    async def get_location(self, location_id: int) -> Location:
        """Get a specific location by ID."""
        response = await self._request("GET", f"/users/{self.user_id}/locations/{location_id}")
        return Location(**response["data"][0])
    
    async def query_water_usage(
        self, device_id: str, queries: List[WaterUsageQuery]
    ) -> List[List[WaterUsageReading]]:
        """Query water usage data for a device."""
        response = await self._request(
            "POST",
            f"/users/{self.user_id}/devices/{device_id}/queries",
            json={"queries": [query.model_dump() for query in queries]},
        )
        readings = []
        for query_data in response["data"]:
            query_readings = [WaterUsageReading(**reading) for reading in query_data]
            readings.append(query_readings)
        return readings
    
    async def get_current_flow(self, device_id: str) -> Dict[str, Any]:
        """Get current flow status for a device."""
        try:
            response = await self._request(
                "GET", f"/users/{self.user_id}/devices/{device_id}/query/active"
            )
            flow_data = response["data"][0]
            
            # Store in cache
            self.cache.store(device_id, flow_data)
            
            return flow_data
        except Exception as e:
            # Try to get from cache if API fails
            cached_data = self.cache.get_recent(device_id)
            if cached_data:
                return cached_data[0]  # Return most recent cached data
            raise e  # Re-raise if no cached data available
    
    async def get_usage_alerts(self, **kwargs) -> List[UsageAlert]:
        """Get all usage alerts for the user."""
        params = {
            "limit": kwargs.get("limit", 50),
            "offset": kwargs.get("offset", 0),
            "sort_field": kwargs.get("sort_field", "triggered_datetime"),
            "sort_direction": kwargs.get("sort_direction", "ASC"),
        }
        if "device_id" in kwargs:
            params["device_id"] = kwargs["device_id"]
        response = await self._request("GET", f"/users/{self.user_id}/usage-alerts", params=params)
        return [UsageAlert(**alert) for alert in response["data"]]
    
    async def get_alert_rules(self, device_id: str, **kwargs) -> List[UsageAlertRule]:
        """Get all alert rules for a device."""
        params = {
            "limit": kwargs.get("limit", 50),
            "offset": kwargs.get("offset", 0),
            "sort_field": kwargs.get("sort_field", "id"),
            "sort_direction": kwargs.get("sort_direction", "ASC"),
        }
        response = await self._request(
            "GET",
            f"/users/{self.user_id}/devices/{device_id}/rules/usage-alerts",
            params=params,
        )
        return [UsageAlertRule(**rule) for rule in response["data"]]
    
    async def get_alert_rule(self, device_id: str, rule_id: str) -> UsageAlertRule:
        """Get a specific alert rule by ID."""
        response = await self._request(
            "GET",
            f"/users/{self.user_id}/devices/{device_id}/rules/usage-alerts/{rule_id}",
        )
        return UsageAlertRule(**response["data"][0])
    
    def _write_to_influxdb(self, reading: WaterUsageReading, device_id: str) -> None:
        """Write water usage data to InfluxDB.
        
        Args:
            reading: Water usage reading
            device_id: Device ID
        """
        if not self._write_api:
            return
            
        point = Point("water_usage") \
            .tag("device_id", device_id) \
            .field("value", reading.value) \
            .time(datetime.fromisoformat(reading.datetime))
            
        self._write_api.write(
            bucket=self.influxdb_bucket,
            org=self.influxdb_org,
            record=point
        )

    async def write_to_influxdb(
        self,
        device_id: str,
        flow_data: Dict[str, Any],
        measurement: Optional[str] = None
    ) -> None:
        """Write flow data to InfluxDB.
        
        Args:
            device_id: Flume device ID
            flow_data: Flow data from get_current_flow
            measurement: Optional override for measurement name
        """
        if not self._write_api:
            raise ValueError("InfluxDB is not configured")

        # Store in cache
        self.cache.store(device_id, flow_data)

        measurement = measurement or self.influxdb_measurement
        timestamp = datetime.fromisoformat(flow_data['datetime'].replace(' ', 'T'))

        point = Point(measurement) \
            .tag("device_id", device_id) \
            .field("flow_rate", float(flow_data['gpm'])) \
            .field("active", flow_data['active']) \
            .time(timestamp)

        try:
            self._write_api.write(
                bucket=self.influxdb_bucket,
                org=self.influxdb_org,
                record=point
            )
        except Exception as e:
            print(f"Failed to write to InfluxDB: {e}")
            # Data is still in cache even if InfluxDB write fails

    async def monitor_and_store(
        self,
        device_id: str,
        interval: int = 30
    ) -> None:
        """Monitor device flow and store data in InfluxDB.
        
        Args:
            device_id: Flume device ID
            interval: Polling interval in seconds
        """
        if not self._write_api:
            raise ValueError("InfluxDB is not configured")

        while True:
            try:
                flow_data = await self.get_current_flow(device_id)
                await self.write_to_influxdb(device_id, flow_data)
                await asyncio.sleep(interval)
            except Exception as e:
                print(f"Error monitoring device {device_id}: {e}")
                await asyncio.sleep(5)  # Wait before retrying 