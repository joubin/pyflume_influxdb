"""Example usage of the PyFlume InfluxDB library."""

import asyncio
import os
from datetime import datetime, timedelta

from pyflume_influxdb import FlumeClient
from pyflume_influxdb.models import WaterUsageQuery


async def main():
    """Demonstrate basic usage of the FlumeClient."""
    # Get credentials from environment variables
    client_id = os.getenv("FLUME_CLIENT_ID")
    client_secret = os.getenv("FLUME_CLIENT_SECRET")
    username = os.getenv("FLUME_USERNAME")
    password = os.getenv("FLUME_PASSWORD")
    
    # Optional InfluxDB configuration
    influxdb_url = os.getenv("INFLUXDB_URL")
    influxdb_token = os.getenv("INFLUXDB_TOKEN")
    influxdb_org = os.getenv("INFLUXDB_ORG")
    influxdb_bucket = os.getenv("INFLUXDB_BUCKET")
    
    if not all([client_id, client_secret, username, password]):
        raise ValueError("Missing required Flume credentials in environment variables")
    
    async with FlumeClient(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        influxdb_url=influxdb_url,
        influxdb_token=influxdb_token,
        influxdb_org=influxdb_org,
        influxdb_bucket=influxdb_bucket,
    ) as client:
        # Get all devices
        devices = await client.get_devices(include_location=True)
        print(f"\nFound {len(devices)} devices:")
        
        for device in devices:
            print(f"\nDevice: {device.id}")
            print(f"Type: {'Bridge' if device.type == 1 else 'Water Sensor'}")
            print(f"Status: {'Connected' if device.connected else 'Disconnected'}")
            print(f"Last seen: {device.last_seen}")
            
            if device.type == 2:  # Water sensor
                # Get current flow status
                flow = await client.get_current_flow(device.id)
                print(f"\nCurrent flow status:")
                print(f"Active: {flow['active']}")
                print(f"Flow rate: {flow['gpm']} GPM")
                print(f"As of: {flow['datetime']}")
                
                # Query last day's water usage
                now = datetime.now()
                yesterday = now - timedelta(days=1)
                
                queries = [
                    # Hourly data for the last day
                    WaterUsageQuery(
                        request_id="hourly",
                        bucket="HR",
                        since_datetime=yesterday.strftime("%Y-%m-%d %H:%M:%S"),
                        until_datetime=now.strftime("%Y-%m-%d %H:%M:%S"),
                        operation="SUM",
                        units="GALLONS",
                    ),
                    # Daily total
                    WaterUsageQuery(
                        request_id="daily",
                        bucket="DAY",
                        since_datetime=yesterday.strftime("%Y-%m-%d %H:%M:%S"),
                        until_datetime=now.strftime("%Y-%m-%d %H:%M:%S"),
                        operation="SUM",
                        units="GALLONS",
                    ),
                ]
                
                usage = await client.query_water_usage(device.id, queries)
                
                print("\nWater usage:")
                print("Hourly breakdown:")
                for reading in usage["hourly"]:
                    print(f"  {reading.datetime}: {reading.value:.1f} gallons")
                    
                if usage["daily"]:
                    daily_total = usage["daily"][0].value
                    print(f"\nTotal usage (24h): {daily_total:.1f} gallons")
                
                # Get alert rules
                rules = await client.get_alert_rules(device.id)
                print(f"\nAlert rules ({len(rules)}):")
                for rule in rules:
                    print(f"- {rule.name}: {rule.flow_rate} GPM for {rule.duration} minutes")
                
                # Get recent alerts
                alerts = await client.get_usage_alerts(
                    device_id=device.id,
                    sort_direction="DESC",
                    limit=5,
                )
                print(f"\nRecent alerts ({len(alerts)}):")
                for alert in alerts:
                    alert_type = "LEAK" if alert.flume_leak else "Flow"
                    print(
                        f"- [{alert_type}] {alert.triggered_datetime}: "
                        f"{alert.event_rule_name}"
                    )


if __name__ == "__main__":
    asyncio.run(main()) 