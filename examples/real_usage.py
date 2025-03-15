"""Real-world usage example of the PyFlume InfluxDB library."""

import asyncio
import os
from datetime import datetime, timedelta

from pyflume_influxdb import FlumeClient


async def monitor_device(client, device):
    """Monitor a single device's water usage and flow data."""
    print(f"\nMonitoring Device ID: {device.id}")
    print(f"Type: {'Bridge' if device.type == 1 else 'Water Sensor'}")
    print(f"Status: {'Connected' if device.connected else 'Disconnected'}")
    print(f"Last seen: {device.last_seen}")
    print(f"Battery: {device.battery_level}")

    if device.type != 2:  # Skip if not a water sensor
        return

    last_alert_time = None

    try:
        while True:
            # Get current flow status and store in InfluxDB
            current_flow = await client.get_current_flow(device.id)
            if client._write_api:  # Only write if InfluxDB is configured
                await client.write_to_influxdb(device.id, current_flow)
                print("✅ Data stored in InfluxDB")
            
            print(f"\n🚰 Flow Status @ {current_flow['datetime']}")
            print(f"Active: {'Yes' if current_flow['active'] else 'No'}")
            print(f"Flow rate: {current_flow['gpm']:.2f} GPM")

            # Check for new alerts every minute
            current_time = datetime.fromisoformat(current_flow['datetime'].replace(' ', 'T'))
            if last_alert_time is None or (current_time - last_alert_time) > timedelta(minutes=1):
                alerts = await client.get_usage_alerts(
                    device_id=device.id,
                    sort_direction="DESC",
                    limit=5
                )
                
                if alerts:
                    print("\n🚨 Recent Alerts:")
                    for alert in alerts:
                        alert_type = "LEAK" if alert.flume_leak else "Flow"
                        print(f"- [{alert_type}] {alert.triggered_datetime}: {alert.event_rule_name}")
                
                last_alert_time = current_time

            await asyncio.sleep(10)  # Wait 30 seconds before next check to respect API limits

    except asyncio.CancelledError:
        print(f"\nStopped monitoring device {device.id}")
    except Exception as e:
        print(f"\nError monitoring device {device.id}: {e}")


async def main():
    """Run real-world example using actual Flume API credentials."""
    # Get credentials from environment variables
    client_id = os.getenv("FLUME_CLIENT_ID")
    client_secret = os.getenv("FLUME_CLIENT_SECRET")
    username = os.getenv("FLUME_USERNAME")
    password = os.getenv("FLUME_PASSWORD")
    
    if not all([client_id, client_secret, username, password]):
        raise ValueError(
            "Missing required Flume credentials in environment variables. "
            "Please ensure FLUME_CLIENT_ID, FLUME_CLIENT_SECRET, FLUME_USERNAME, "
            "and FLUME_PASSWORD are set."
        )
    
    print("\n🌊 PyFlume InfluxDB Real-Time Monitoring")
    print("=====================================")
    
    async with FlumeClient(
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
    ) as client:
        # List all devices
        print("\n📱 Fetching devices...")
        devices = await client.get_devices(location=True)
        print(f"Found {len(devices)} devices")
        
        if not client._write_api:
            print("\n⚠️  Warning: InfluxDB is not configured. Data will only be displayed.")
        else:
            print("\n✅ InfluxDB is configured. Data will be stored.")
        
        # Create monitoring tasks for each device
        tasks = [monitor_device(client, device) for device in devices]
        
        try:
            # Run all monitoring tasks concurrently
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user") 