"""Tests for the FlumeClient class."""

import json
from datetime import datetime, timedelta

import jwt
import pytest
import pytest_asyncio
from aioresponses import aioresponses

from pyflume_influxdb import FlumeClient
from pyflume_influxdb.models import (Device, Location, WaterUsageQuery,
                                   WaterUsageReading, UsageAlert, UsageAlertRule)


@pytest_asyncio.fixture
async def client(mock_aioresponse, mock_auth_response):
    """Create a FlumeClient instance for testing."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    
    client = FlumeClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        username="test_user",
        password="test_pass"
    )
    await client.connect()
    yield client
    await client.close()  # Ensure client is closed after test


@pytest.fixture
def mock_aioresponse():
    """Create a mock aiohttp response."""
    with aioresponses() as m:
        yield m


@pytest.fixture
def mock_auth_response():
    """Mock authentication response."""
    return {
        "data": [{
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoxMjM0fQ.4xWVw-VZwCXa_KBy95teBislSgy_gg1ppVp9zDuXvVY",
            "expires_in": 3600,
            "user_id": 1234
        }]
    }


@pytest.fixture
def mock_device_data():
    """Mock device data response."""
    return {
        "data": [{
            "id": "device1",
            "type": 2,
            "location_id": 1234,
            "user_id": 1234,
            "bridge_id": "bridge1",
            "oriented": True,
            "last_seen": "2025-03-15T02:23:16+00:00",
            "connected": True,
            "battery_level": "high"
        }]
    }


@pytest.fixture
def mock_location_data():
    """Mock location data response."""
    return {
        "data": [{
            "id": 1234,
            "user_id": 1234,
            "name": "Test Location",
            "primary_location": True,
            "address": "123 Test St",
            "address_2": "Unit 1",
            "city": "Test City",
            "state": "CA",
            "postal_code": "12345",
            "country": "USA",
            "tz": "America/Los_Angeles",
            "installation": "complete",
            "building_type": "residential"
        }]
    }


@pytest.fixture
def mock_water_usage_data():
    """Mock water usage data response."""
    return {
        "data": [[{
            "datetime": "2025-03-15T01:49:21.219368",
            "value": 1.5
        }]]
    }


@pytest.fixture
def mock_current_flow_data():
    """Mock current flow data response."""
    return {
        "data": [{
            "datetime": "2025-03-15T03:24:34.549021",
            "gpm": 2.5,
            "active": True
        }]
    }


@pytest.fixture
def mock_alert_rules_data():
    """Mock alert rules data response."""
    return {
        "data": [{
            "id": "rule1",
            "name": "High Flow Alert",
            "active": True,
            "flow_rate": 5.0,
            "duration": 15,
            "notify_every": 60
        }]
    }


@pytest.fixture
def mock_alerts_data():
    """Mock alerts data response."""
    return {
        "data": [{
            "id": 12345,
            "device_id": "device1",
            "triggered_datetime": "2025-03-15T03:24:34.549021",
            "flume_leak": True,
            "event_rule_name": "High Flow Alert",
            "query": {
                "request_id": "test",
                "bucket": "MIN",
                "since_datetime": "2025-03-15T03:24:34.549021",
                "units": "GALLONS"
            }
        }]
    }


@pytest.mark.asyncio
async def test_authentication(client, mock_aioresponse, mock_auth_response):
    """Test authentication."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )

    await client.connect()
    assert client.user_id == 1234


@pytest.mark.asyncio
async def test_get_devices(client, mock_aioresponse, mock_auth_response, mock_device_data):
    """Test getting devices."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.get(
        "https://api.flumetech.com/me/devices?limit=50&list_shared=false&location=false&offset=0&sort_direction=ASC&sort_field=id&user=false",
        payload=mock_device_data
    )

    await client.connect()
    devices = await client.get_devices()
    assert len(devices) == 1
    assert devices[0].id == "device1"


@pytest.mark.asyncio
async def test_get_device(client, mock_aioresponse, mock_auth_response, mock_device_data):
    """Test getting a specific device."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.get(
        "https://api.flumetech.com/users/1234/devices/device1?location=false&user=false",
        payload=mock_device_data
    )

    await client.connect()
    device = await client.get_device("device1")
    assert device.id == "device1"


@pytest.mark.asyncio
async def test_get_locations(client, mock_aioresponse, mock_auth_response, mock_location_data):
    """Test getting locations."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.get(
        "https://api.flumetech.com/users/1234/locations?limit=50&list_shared=false&offset=0&sort_direction=ASC&sort_field=id",
        payload=mock_location_data
    )

    await client.connect()
    locations = await client.get_locations()
    assert len(locations) == 1
    assert locations[0].id == 1234


@pytest.mark.asyncio
async def test_get_location(client, mock_aioresponse, mock_auth_response, mock_location_data):
    """Test getting a specific location."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.get(
        "https://api.flumetech.com/users/1234/locations/1234",
        payload=mock_location_data
    )

    await client.connect()
    location = await client.get_location(1234)
    assert location.id == 1234


@pytest.mark.asyncio
async def test_query_water_usage(client, mock_aioresponse, mock_auth_response, mock_water_usage_data):
    """Test querying water usage data."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.post(
        "https://api.flumetech.com/users/1234/devices/device1/queries",
        payload=mock_water_usage_data
    )

    await client.connect()
    usage = await client.query_water_usage("device1", "MIN", "2025-03-15T01:49:21.219368")
    assert len(usage) == 1
    assert usage[0].value == 1.5


@pytest.mark.asyncio
async def test_get_current_flow(client, mock_aioresponse, mock_auth_response, mock_current_flow_data):
    """Test getting current flow status."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.get(
        "https://api.flumetech.com/me/devices/device1/query/active",
        payload={
            "data": [{
                "active": True,
                "gpm": 2.5,
                "datetime": "2025-03-15T03:24:34.549021"
            }]
        }
    )

    await client.connect()
    flow = await client.get_current_flow("device1")
    
    assert flow["active"] is True
    assert flow["gpm"] == 2.5
    assert flow["datetime"] == "2025-03-15T03:24:34.549021"


@pytest.mark.asyncio
async def test_get_usage_alerts(client, mock_aioresponse, mock_auth_response, mock_alerts_data):
    """Test getting usage alerts."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.get(
        "https://api.flumetech.com/users/1234/usage-alerts?limit=50&offset=0&sort_direction=ASC&sort_field=triggered_datetime",
        payload=mock_alerts_data
    )

    await client.connect()
    alerts = await client.get_usage_alerts()
    assert len(alerts) == 1
    assert alerts[0].id == 12345


@pytest.mark.asyncio
async def test_get_alert_rules(client, mock_aioresponse, mock_auth_response, mock_alert_rules_data):
    """Test getting alert rules."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.get(
        "https://api.flumetech.com/users/1234/devices/device1/rules/usage-alerts?limit=50&offset=0&sort_direction=ASC&sort_field=id",
        payload=mock_alert_rules_data
    )

    await client.connect()
    rules = await client.get_alert_rules("device1")
    assert len(rules) == 1
    assert rules[0].id == "rule1"


@pytest.mark.asyncio
async def test_get_alert_rule(client, mock_aioresponse, mock_auth_response, mock_alert_rules_data):
    """Test getting a specific alert rule."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )
    mock_aioresponse.get(
        "https://api.flumetech.com/users/1234/devices/device1/rules/usage-alerts/rule1",
        payload=mock_alert_rules_data
    )

    await client.connect()
    rule = await client.get_alert_rule("device1", "rule1")
    assert rule.id == "rule1"


@pytest.mark.asyncio
async def test_context_manager(client, mock_aioresponse, mock_auth_response):
    """Test the async context manager interface."""
    mock_aioresponse.post(
        "https://api.flumetech.com/oauth/token",
        payload=mock_auth_response
    )

    async with client as c:
        assert isinstance(c, FlumeClient)
        assert c._session is not None
        assert c.user_id == 1234 