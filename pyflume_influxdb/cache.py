"""Local caching for Flume data."""
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


class FlumeCache:
    """Cache for storing Flume device data locally."""

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        """Initialize the cache.
        
        Args:
            cache_dir: Directory to store cache files. If None, uses system temp dir.
        """
        if not cache_dir:
            cache_dir = os.path.join(os.path.expanduser("~"), ".pyflume_cache")
        
        os.makedirs(cache_dir, exist_ok=True)
        self.db_path = os.path.join(cache_dir, "flume_cache.db")
        
        # Initialize database
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flow_data (
                    device_id TEXT,
                    timestamp TEXT,
                    data TEXT,
                    PRIMARY KEY (device_id, timestamp)
                )
            """)
            conn.commit()

    def store(self, device_id: str, data: Dict[str, Any]) -> None:
        """Store flow data in the cache.
        
        Args:
            device_id: Device ID
            data: Flow data to store
        """
        if not isinstance(data, dict) or 'datetime' not in data:
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO flow_data (device_id, timestamp, data) VALUES (?, ?, ?)",
                (device_id, data['datetime'], str(data))
            )
            conn.commit()

    def get_recent(self, device_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent data for a device.
        
        Args:
            device_id: Device ID
            hours: Number of hours of data to retrieve
            
        Returns:
            List of flow data entries
        """
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM flow_data WHERE device_id = ? AND timestamp >= ? ORDER BY timestamp DESC",
                (device_id, cutoff)
            )
            rows = cursor.fetchall()
            
        # Convert string data back to dicts
        results = []
        for row in rows:
            try:
                data = eval(row[0])  # Safe since we control what goes in
                results.append(data)
            except (SyntaxError, ValueError):
                continue
                
        return results

    def cleanup(self, max_age_hours: int = 48) -> None:
        """Remove old entries from the cache.
        
        Args:
            max_age_hours: Maximum age of entries to keep in hours
        """
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM flow_data WHERE timestamp < ?",
                (cutoff,)
            )
            conn.commit() 