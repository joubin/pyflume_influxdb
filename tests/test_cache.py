"""Tests for the cache module."""
import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from pyflume_influxdb.cache import FlumeCache


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary directory for cache testing."""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def cache(temp_cache_dir):
    """Create a cache instance for testing."""
    return FlumeCache(temp_cache_dir)


def test_cache_initialization(temp_cache_dir):
    """Test that the cache initializes correctly."""
    cache = FlumeCache(temp_cache_dir)
    
    # Check that the cache directory exists
    assert os.path.exists(temp_cache_dir)
    
    # Check that the database file exists
    db_path = os.path.join(temp_cache_dir, "cache.db")
    assert os.path.exists(db_path)
    
    # Check that the table exists
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flow_data'")
    assert cursor.fetchone() is not None
    conn.close()


def test_store_and_retrieve(cache):
    """Test storing and retrieving data from the cache."""
    device_id = "test_device"
    timestamp = datetime.now()
    data = {"gpm": 1.5, "active": True}
    
    # Store data
    cache.store(device_id, timestamp, data)
    
    # Retrieve data
    retrieved_data = cache.get(device_id, timestamp)
    assert retrieved_data is not None
    assert retrieved_data["gpm"] == data["gpm"]
    assert retrieved_data["active"] == data["active"]


def test_get_recent_data(cache):
    """Test retrieving recent data from the cache."""
    device_id = "test_device"
    now = datetime.now()
    
    # Store multiple data points
    data_points = [
        (now - timedelta(minutes=i), {"gpm": i * 0.5, "active": True})
        for i in range(5)
    ]
    
    for timestamp, data in data_points:
        cache.store(device_id, timestamp, data)
    
    # Get recent data
    recent_data = cache.get_recent(device_id, hours=1)
    assert len(recent_data) == 5
    
    # Check that data is ordered by timestamp
    timestamps = [entry[0] for entry in recent_data]
    assert timestamps == sorted(timestamps, reverse=True)


def test_cleanup_old_data(cache):
    """Test cleaning up old data from the cache."""
    device_id = "test_device"
    now = datetime.now()
    
    # Store some old and new data
    old_timestamp = now - timedelta(days=2)
    new_timestamp = now - timedelta(minutes=30)
    
    cache.store(device_id, old_timestamp, {"gpm": 1.0, "active": False})
    cache.store(device_id, new_timestamp, {"gpm": 2.0, "active": True})
    
    # Clean up data older than 1 day
    cache.cleanup(max_age_hours=24)
    
    # Check that old data is gone but new data remains
    assert cache.get(device_id, old_timestamp) is None
    assert cache.get(device_id, new_timestamp) is not None


def test_cache_handles_missing_data(cache):
    """Test that the cache handles missing data gracefully."""
    device_id = "nonexistent_device"
    timestamp = datetime.now()
    
    # Try to get nonexistent data
    assert cache.get(device_id, timestamp) is None
    assert len(cache.get_recent(device_id, hours=1)) == 0


def test_cache_handles_multiple_devices(cache):
    """Test that the cache can handle data from multiple devices."""
    devices = ["device1", "device2"]
    timestamp = datetime.now()
    
    # Store data for multiple devices
    for device_id in devices:
        cache.store(device_id, timestamp, {"gpm": 1.0, "active": True})
    
    # Check that data for each device can be retrieved
    for device_id in devices:
        data = cache.get(device_id, timestamp)
        assert data is not None
        assert data["gpm"] == 1.0
        assert data["active"] is True 