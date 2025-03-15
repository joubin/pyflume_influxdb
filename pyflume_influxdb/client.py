"""Client for interacting with the Flume API.

The client uses two main endpoints:
- BASE_URL: https://api.flumetech.com for general API requests
- AUTH_URL: https://api.flumetech.com/oauth/token for authentication
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
import os
import logging
import logging.handlers
import sys

import aiohttp
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

from .exceptions import FlumeAuthError, FlumeAPIError, FlumeInfluxDBError
from .models import (Device, FlumeResponse, Location, UsageAlert, UsageAlertRule,
                    WaterUsageQuery, WaterUsageReading)
from .cache import FlumeCache

# Set up logging
def setup_logging():
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Configure main logger
    main_logger = logging.getLogger('flume.main')
    main_logger.setLevel(logging.INFO)
    main_handler = logging.FileHandler('logs/main.log')
    main_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    main_logger.addHandler(main_handler)
    
    # Add stdout handler to main logger
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    main_logger.addHandler(stdout_handler)
    
    # Configure debug logger
    debug_logger = logging.getLogger('flume.debug')
    debug_logger.setLevel(logging.DEBUG)
    debug_handler = logging.FileHandler('logs/debug.log')
    debug_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    debug_logger.addHandler(debug_handler)
    
    # Configure warning logger
    warning_logger = logging.getLogger('flume.warning')
    warning_logger.setLevel(logging.WARNING)
    warning_handler = logging.FileHandler('logs/warning.log')
    warning_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    warning_logger.addHandler(warning_handler)

setup_logging()

# Get logger instances
main_logger = logging.getLogger('flume.main')
debug_logger = logging.getLogger('flume.debug')
warning_logger = logging.getLogger('flume.warning')

class FlumeClient:
    """Client for interacting with the Flume API."""

    BASE_URL = "https://api.flumetech.com"
    AUTH_URL = "https://api.flumetech.com/oauth/token"
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        influxdb_url: Optional[str] = None,
        influxdb_token: Optional[str] = None,
        influxdb_org: Optional[str] = None,
        influxdb_bucket: Optional[str] = None,
        influxdb_measurement: str = "water_usage",
        cache_dir: Optional[str] = None,
    ) -> None:
        """Initialize the Flume client.
        
        Args:
            client_id: Flume API client ID
            client_secret: Flume API client secret
            username: Flume account username
            password: Flume account password
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
        self._session: Optional[aiohttp.ClientSession] = None
        self._access_token: Optional[str] = None
        self._user_id: Optional[int] = None
        self._influxdb_client: Optional[InfluxDBClient] = None
        self._write_api = None
        self.cache = FlumeCache(cache_dir) if cache_dir else None

        # InfluxDB configuration
        self.influxdb_url = influxdb_url
        self.influxdb_token = influxdb_token
        self.influxdb_org = influxdb_org
        self.influxdb_bucket = influxdb_bucket
        self.influxdb_measurement = influxdb_measurement

        # Initialize InfluxDB client if all required parameters are provided
        if all([influxdb_url, influxdb_token, influxdb_org, influxdb_bucket]):
            self._influxdb_client = InfluxDBClient(
                url=influxdb_url,
                token=influxdb_token,
                org=influxdb_org
            )
            self._write_api = self._influxdb_client.write_api(write_options=SYNCHRONOUS)
    
    @property
    def user_id(self) -> Optional[int]:
        """Get the authenticated user ID."""
        return self._user_id
    
    async def __aenter__(self):
        """Set up the client session."""
        self._session = aiohttp.ClientSession()
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

        debug_logger.debug("=== AUTH REQUEST ===")
        debug_logger.debug(f"URL: {self.AUTH_URL}")
        debug_logger.debug(f"Data: {auth_data}")

        async with self._session.post(self.AUTH_URL, json=auth_data) as response:
            debug_logger.debug("=== AUTH RESPONSE ===")
            debug_logger.debug(f"Status: {response.status}")
            debug_logger.debug(f"Headers: {response.headers}")
            response_text = await response.text()
            debug_logger.debug(f"Body: {response_text}")

            if response.status != 200:
                warning_logger.error("Failed to authenticate with Flume API")
                raise FlumeAuthError("Failed to authenticate with Flume API")
            
            try:
                data = await response.json()
                debug_logger.debug(f"Parsed JSON: {data}")
                auth_data = data.get("data", [{}])[0]
                self._access_token = auth_data.get("access_token")
                
                if not self._access_token:
                    warning_logger.error("Missing access token in auth response")
                    raise FlumeAuthError("Missing access token in auth response")
                
                # Decode the JWT token to get the user ID
                token_parts = self._access_token.split('.')
                if len(token_parts) != 3:
                    warning_logger.error("Invalid JWT token format")
                    raise FlumeAuthError("Invalid JWT token format")
                
                import base64
                import json
                
                # Add padding if needed
                padding = '=' * (4 - len(token_parts[1]) % 4)
                payload = base64.b64decode(token_parts[1] + padding).decode('utf-8')
                token_data = json.loads(payload)
                
                self._user_id = token_data.get('user_id')
                if not self._user_id:
                    warning_logger.error("Missing user ID in JWT token")
                    raise FlumeAuthError("Missing user ID in JWT token")
                
                debug_logger.debug(f"Decoded JWT payload: {token_data}")
                debug_logger.debug(f"User ID: {self._user_id}")
                
            except Exception as e:
                warning_logger.error(f"Error parsing auth response: {e}")
                raise FlumeAuthError(f"Failed to parse auth response: {e}")
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the Flume API."""
        if not self._session:
            raise FlumeAuthError("Client not connected. Call connect() first.")

        if not self._access_token:
            await self.authenticate()

        # Convert boolean values to strings in params
        if params:
            params = {k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items()}

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }

        url = f"{self.BASE_URL}{endpoint}"
        debug_logger.debug("=== REQUEST DETAILS ===")
        debug_logger.debug(f"URL: {url}")
        debug_logger.debug(f"Method: {method}")
        debug_logger.debug(f"Headers: {headers}")
        debug_logger.debug(f"Params: {params}")
        debug_logger.debug(f"Body: {json}")

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json
            ) as response:
                debug_logger.debug("=== RESPONSE DETAILS ===")
                debug_logger.debug(f"Status: {response.status}")
                debug_logger.debug(f"Headers: {response.headers}")
                
                response_text = await response.text()
                debug_logger.debug(f"Body: {response_text}")

                if response.status == 401:
                    main_logger.info("Access token expired, re-authenticating...")
                    await self.authenticate()
                    headers["Authorization"] = f"Bearer {self._access_token}"
                    async with self._session.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        json=json
                    ) as retry_response:
                        retry_response_text = await retry_response.text()
                        if retry_response.status != 200:
                            warning_logger.error(f"API request failed after re-auth: {retry_response.status}")
                            raise FlumeAPIError(f"API request failed: {retry_response.status}\nResponse: {retry_response_text}")
                        return await retry_response.json()

                if response.status != 200:
                    warning_logger.error(f"API request failed: {response.status}")
                    raise FlumeAPIError(f"API request failed: {response.status}\nResponse: {response_text}")

                return await response.json()

        except aiohttp.ClientError as e:
            warning_logger.error(f"Request failed: {str(e)}")
            raise FlumeAPIError(f"Request failed: {str(e)}")
    
    async def get_devices(self, **kwargs) -> List[Device]:
        """Get all devices associated with the user.
        
        Args:
            include_location: Whether to include location data (default: False)
            include_user: Whether to include user data (default: False)
            limit: Maximum number of devices to return (default: 50)
            offset: Number of devices to skip (default: 0)
            sort_field: Field to sort by (default: "id")
            sort_direction: Sort direction (default: "ASC")
            list_shared: Whether to include shared devices (default: False)
            
        Returns:
            List of Device objects
        """
        params = {
            "limit": kwargs.get("limit", 50),
            "offset": kwargs.get("offset", 0),
            "sort_field": kwargs.get("sort_field", "id"),
            "sort_direction": kwargs.get("sort_direction", "ASC"),
            "location": kwargs.get("include_location", False),
            "user": kwargs.get("include_user", False),
            "list_shared": kwargs.get("list_shared", False),
        }
        response = await self._request("GET", "/me/devices", params=params)
        return [Device(**device) for device in response["data"]]
    
    async def get_device(self, device_id: str, **kwargs) -> Device:
        """Get a specific device by ID."""
        params = {
            "user": kwargs.get("include_user", False),
            "location": kwargs.get("include_location", False),
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
            "list_shared": kwargs.get("list_shared", False),
        }
        response = await self._request("GET", f"/users/{self.user_id}/locations", params=params)
        return [Location(**location) for location in response["data"]]
    
    async def get_location(self, location_id: int) -> Location:
        """Get a specific location by ID."""
        response = await self._request("GET", f"/users/{self.user_id}/locations/{location_id}")
        return Location(**response["data"][0])
    
    async def query_water_usage(
        self,
        device_id: str,
        queries: Union[List[WaterUsageQuery], str],
        since_datetime: Optional[str] = None,
        until_datetime: Optional[str] = None,
        operation: str = "SUM",
        units: str = "GALLONS"
    ) -> Union[List[List[WaterUsageReading]], List[WaterUsageReading]]:
        """Query water usage data for a device.
        
        This method accepts either a list of WaterUsageQuery objects or
        simple parameters for a single query.
        
        Args:
            device_id: Device ID
            queries: Either a list of WaterUsageQuery objects or a bucket string
            since_datetime: Start time (only used if queries is a string)
            until_datetime: End time (only used if queries is a string)
            operation: Aggregation operation (only used if queries is a string)
            units: Units for the data (only used if queries is a string)
            
        Returns:
            List of water usage readings
        """
        if isinstance(queries, str):
            # Simple query mode
            query = WaterUsageQuery(
                request_id="usage_query",
                bucket=queries,
                since_datetime=since_datetime,
                until_datetime=until_datetime,
                operation=operation,
                units=units
            )
            queries = [query]
        elif not isinstance(queries, list):
            raise ValueError("queries must be either a string or list of WaterUsageQuery")

        response = await self._request(
            "POST",
            f"/users/{self.user_id}/devices/{device_id}/queries",
            json={"queries": [query.model_dump() for query in queries]},
        )

        readings = []
        for query_data in response["data"]:
            query_readings = [WaterUsageReading(**reading) for reading in query_data]
            readings.append(query_readings)
        
        # If single query, return flat list
        return readings[0] if len(readings) == 1 else readings
    
    async def get_current_flow(self, device_id: str) -> Dict[str, Any]:
        """Get the current flow status for a device.

        Args:
            device_id: The ID of the device to get flow status for.

        Returns:
            Dict containing the current flow status with keys:
            - active (bool): Whether water is currently flowing
            - gpm (float): Current flow rate in gallons per minute
            - datetime (str): Timestamp of the reading
        """
        endpoint = f"/me/devices/{device_id}/query/active"
        try:
            response = await self._request("GET", endpoint)
            if not response.get("data"):
                raise FlumeAPIError("No data returned from current flow query")
            return response["data"][0]
        except Exception as e:
            warning_logger.error(f"Failed to get current flow for device {device_id}: {str(e)}")
            raise
    
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
    
    async def write_to_influxdb(
        self,
        device_id: str,
        flow_data: Dict[str, Any],
        measurement: Optional[str] = None
    ) -> None:
        """Write flow data to InfluxDB.
        
        Args:
            device_id: Device ID
            flow_data: Flow data from get_current_flow
            measurement: Optional override for measurement name
        """
        if not self._write_api:
            raise FlumeInfluxDBError("InfluxDB client not initialized")

        # Store in cache if available
        if self.cache:
            self.cache.store(device_id, datetime.fromisoformat(flow_data["datetime"]), flow_data)

        measurement = measurement or self.influxdb_measurement
        timestamp = datetime.fromisoformat(flow_data['datetime'].replace(' ', 'T'))

        point = Point(measurement) \
            .tag("device_id", device_id) \
            .field("flow_rate", float(flow_data['gpm'])) \
            .field("active", flow_data['active']) \
            .time(timestamp)

        try:
            print(f"Writing to InfluxDB: {point}")
            self._write_api.write(
                bucket=self.influxdb_bucket,
                org=self.influxdb_org,
                record=point
            )
        except Exception as e:
            warning_logger.error(f"Failed to write to InfluxDB: {e}")
            # Data is still in cache even if InfluxDB write fails

    async def monitor_and_store(
        self,
        device_id: str,
        interval: int = 30
    ) -> None:
        """Monitor device flow and store data in InfluxDB."""
        if not self._write_api:
            warning_logger.error("InfluxDB client not initialized")
            raise FlumeInfluxDBError("InfluxDB client not initialized")

        main_logger.info(f"Starting monitoring for device {device_id}")
        while True:
            try:
                flow_data = await self.get_current_flow(device_id)
                await self.write_to_influxdb(device_id, flow_data)
                debug_logger.debug(f"Successfully wrote flow data for device {device_id}")
                await asyncio.sleep(interval)
            except Exception as e:
                warning_logger.error(f"Error monitoring device {device_id}: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def close(self) -> None:
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None

        if self._influxdb_client:
            self._influxdb_client.close()
            self._influxdb_client = None 