"""Tests for InfluxDB integration."""

import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from influxdb_client import Point

from pyflume_influxdb import FlumeClient


@pytest.fixture
def mock_influxdb():
    """Mock InfluxDB client."""
    with patch('influxdb_client.InfluxDBClient') as mock_client:
        mock_write_api = MagicMock()
        mock_client.return_value.write_api.return_value = mock_write_api
        yield mock_client


@pytest.fixture
def mock_env_vars():
    """Set up test environment variables."""
    os.environ.update({
        'INFLUXDB_URL': 'http://test:8086',
        'INFLUXDB_TOKEN': 'test_token',
        'INFLUXDB_ORG': 'test_org',
        'INFLUXDB_BUCKET': 'test_bucket',
        'INFLUXDB_MEASUREMENT': 'test_measurement'
    })
    yield
    for key in ['INFLUXDB_URL', 'INFLUXDB_TOKEN', 'INFLUXDB_ORG', 'INFLUXDB_BUCKET', 'INFLUXDB_MEASUREMENT']:
        os.environ.pop(key, None)


async def test_influxdb_initialization(mock_env_vars):
    """Test InfluxDB client initialization from environment variables."""
    async with FlumeClient(
        client_id="test",
        client_secret="test",
        username="test",
        password="test"
    ) as client:
        assert client.influxdb_url == 'http://test:8086'
        assert client.influxdb_token == 'test_token'
        assert client.influxdb_org == 'test_org'
        assert client.influxdb_bucket == 'test_bucket'
        assert client.influxdb_measurement == 'test_measurement'


async def test_write_to_influxdb(mock_influxdb, mock_env_vars):
    """Test writing flow data to InfluxDB."""
    flow_data = {
        'datetime': '2024-03-15 10:00:00',
        'gpm': 1.5,
        'active': True
    }

    async with FlumeClient(
        client_id="test",
        client_secret="test",
        username="test",
        password="test"
    ) as client:
        await client.write_to_influxdb('test_device', flow_data)

        # Verify write_api was called with correct Point
        write_api = mock_influxdb.return_value.write_api.return_value
        assert write_api.write.called
        
        call_args = write_api.write.call_args
        point = call_args[1]['record']
        
        assert isinstance(point, Point)
        assert point._tags['device_id'] == 'test_device'
        assert point._fields['flow_rate'] == 1.5
        assert point._fields['active'] is True


@pytest.mark.asyncio
async def test_monitor_and_store(mock_influxdb, mock_env_vars):
    """Test monitoring and storing flow data."""
    mock_flow_data = {
        'datetime': '2024-03-15 10:00:00',
        'gpm': 1.5,
        'active': True
    }

    async with FlumeClient(
        client_id="test",
        client_secret="test",
        username="test",
        password="test"
    ) as client:
        # Mock get_current_flow
        client.get_current_flow = AsyncMock(return_value=mock_flow_data)
        
        # Start monitoring (will run indefinitely, so we'll mock asyncio.sleep)
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [None, Exception("Stop monitoring")]  # Run twice then stop
            
            try:
                await client.monitor_and_store('test_device')
            except Exception as e:
                assert str(e) == "Stop monitoring"

        # Verify write_api was called twice
        write_api = mock_influxdb.return_value.write_api.return_value
        assert write_api.write.call_count == 2


@pytest.mark.asyncio
async def test_influxdb_not_configured():
    """Test error handling when InfluxDB is not configured."""
    async with FlumeClient(
        client_id="test",
        client_secret="test",
        username="test",
        password="test"
    ) as client:
        with pytest.raises(ValueError, match="InfluxDB is not configured"):
            await client.write_to_influxdb('test_device', {})

        with pytest.raises(ValueError, match="InfluxDB is not configured"):
            await client.monitor_and_store('test_device') 