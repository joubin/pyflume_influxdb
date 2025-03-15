"""Local caching for Flume data."""
import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


class FlumeCache:
    """Local cache for Flume data using SQLite."""

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize the cache.
        
        Args:
            cache_dir: Directory to store cache files. Defaults to ~/.pyflume_cache
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.pyflume_cache")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.db_path = self.cache_dir / "cache.db"
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table for flow data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS flow_data (
                device_id TEXT,
                timestamp TEXT,
                data TEXT,
                PRIMARY KEY (device_id, timestamp)
            )
        """)
        
        conn.commit()
        conn.close()

    def store(self, device_id: str, timestamp: datetime, data: Dict[str, Any]) -> None:
        """Store flow data in the cache.
        
        Args:
            device_id: Device ID
            timestamp: Timestamp of the data
            data: Flow data to store
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "INSERT OR REPLACE INTO flow_data (device_id, timestamp, data) VALUES (?, ?, ?)",
            (device_id, timestamp.isoformat(), json.dumps(data))
        )
        
        conn.commit()
        conn.close()

    def get(self, device_id: str, timestamp: datetime) -> Optional[Dict[str, Any]]:
        """Get flow data from the cache.
        
        Args:
            device_id: Device ID
            timestamp: Timestamp of the data
            
        Returns:
            Flow data if found, None otherwise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT data FROM flow_data WHERE device_id = ? AND timestamp = ?",
            (device_id, timestamp.isoformat())
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return None

    def get_recent(self, device_id: str, hours: int = 24) -> List[Tuple[datetime, Dict[str, Any]]]:
        """Get recent flow data for a device.
        
        Args:
            device_id: Device ID
            hours: Number of hours of data to retrieve
            
        Returns:
            List of (timestamp, data) tuples, ordered by timestamp descending
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute(
            """
            SELECT timestamp, data 
            FROM flow_data 
            WHERE device_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            """,
            (device_id, cutoff)
        )
        
        results = []
        for row in cursor.fetchall():
            timestamp = datetime.fromisoformat(row[0])
            data = json.loads(row[1])
            results.append((timestamp, data))
        
        conn.close()
        return results

    def cleanup(self, max_age_hours: int = 24) -> None:
        """Remove old entries from the cache.
        
        Args:
            max_age_hours: Maximum age of entries to keep in hours
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        
        cursor.execute(
            "DELETE FROM flow_data WHERE timestamp < ?",
            (cutoff,)
        )
        
        conn.commit()
        conn.close() 