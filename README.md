# PyFlume InfluxDB Integration

A Python library for integrating Flume Smart Water Monitor data with InfluxDB. This library provides a robust client for interacting with the Flume API and storing water usage data in InfluxDB for monitoring and analysis.

## Architecture

```plantuml
@startuml
!theme plain
skinparam componentStyle rectangle

package "PyFlume InfluxDB" {
  [FlumeClient] as client
  [Models] as models
  interface "Flume API" as api
  database "InfluxDB" as influx
}

package "External Services" {
  [Flume Cloud] as flume
  [InfluxDB Server] as influxdb
}

actor User

User --> client : uses
client --> models : uses
client --> api : calls
api --> flume : requests
client --> influx : writes
influx --> influxdb : stores

note right of client
  Handles authentication,
  API requests, and data
  transformation
end note

note right of models
  Defines data structures
  for devices, notifications,
  and water usage
end note
@enduml
```

## Features

- **Authentication**: OAuth2 authentication with the Flume API
- **Device Management**: List and manage Flume devices
- **Real-time Monitoring**: Track water usage and flow rates
- **Alert Management**: Access and manage usage alerts and notifications
- **Data Storage**: Store water usage data in InfluxDB (optional)

## Component Overview

### Core Components

```plantuml
@startuml
!theme plain
skinparam classAttributeIconSize 0

class FlumeClient {
  +client_id: str
  +client_secret: str
  +username: str
  +password: str
  +base_url: str
  --
  +get_devices()
  +get_current_flow()
  +get_usage_alerts()
  +get_notifications()
  +get_device_info()
}

class Device {
  +id: str
  +type: int
  +location: Location
  +connected: bool
  +last_seen: datetime
  +battery_level: str
}

class Location {
  +id: str
  +name: str
  +timezone: str
}

class Alert {
  +id: str
  +device_id: str
  +triggered_datetime: datetime
  +event_rule_name: str
  +flume_leak: bool
}

FlumeClient --> Device : manages
Device --> Location : has
FlumeClient --> Alert : monitors
@enduml
```

## Installation

```bash
pip install pyflume-influxdb
```

## Configuration

The library requires the following environment variables:

```bash
FLUME_CLIENT_ID=your_client_id
FLUME_CLIENT_SECRET=your_client_secret
FLUME_USERNAME=your_username
FLUME_PASSWORD=your_password
```

[Detailed Documentation](https://flumetech.readme.io/reference/accessing-the-api)

## Usage

### Basic Usage

```python
from pyflume_influxdb import FlumeClient

async with FlumeClient(
    client_id="your_client_id",
    client_secret="your_client_secret",
    username="your_username",
    password="your_password"
) as client:
    # Get all devices
    devices = await client.get_devices()
    
    # Get current flow for a device
    flow = await client.get_current_flow(device_id)
    
    # Get recent alerts
    alerts = await client.get_usage_alerts(device_id)
```

### Real-time Monitoring

The library includes a real-time monitoring example that demonstrates continuous water usage tracking:

```plantuml
@startuml
!theme plain

participant User
participant "FlumeClient" as Client
participant "Flume API" as API
participant "Device" as Device

User -> Client: Start monitoring
activate Client

loop Every 30 seconds
    Client -> API: Get current flow
    activate API
    API --> Client: Flow data
    deactivate API
    
    Client -> User: Display flow status
    
    alt Every minute
        Client -> API: Get usage alerts
        activate API
        API --> Client: Alert data
        deactivate API
        
        opt If alerts exist
            Client -> User: Display alerts
        end
    end
end

@enduml
```

## API Rate Limits

- The Flume API has a rate limit of 120 calls per hour
- The monitoring script respects this by:
  - Checking flow status every 30 seconds
  - Checking alerts every minute

## Development

### Project Structure

```plantuml
@startuml
!theme plain
skinparam packageStyle rectangle

package "pyflume_influxdb" {
  [client.py] as Client
  [models.py] as Models
  [__init__.py] as Init
}

package "tests" {
  [test_client.py] as TestClient
}

package "examples" {
  [real_usage.py] as Example
}

[pyproject.toml] as Config
[swagger.json] as Swagger
[Dockerfile] as Docker

Client --> Models
TestClient --> Client
Example --> Client
Client ..> Swagger : references
Config ..> Client : configures

note right of Client
  Main implementation of
  the Flume API client
end note

note right of Models
  Data models and type
  definitions
end note

note right of TestClient
  Comprehensive test suite
  with mocked responses
end note
@enduml
```

### Testing

The project includes a comprehensive test suite:

```bash
# Run tests in Docker
docker build -t pyflume-test .
docker run -it --rm -v $(pwd)/.env:/app/.env pyflume-test
```

## Error Handling

The client implements robust error handling for common scenarios:

```plantuml
@startuml
!theme plain
skinparam activityDiamondBackgroundColor white

start
:API Request;

if (Authentication Valid?) then (yes)
  if (Rate Limit Exceeded?) then (yes)
    :Raise RateLimitError;
    stop
  else (no)
    if (API Response Valid?) then (yes)
      :Process Response;
    else (no)
      :Raise APIError;
      stop
    endif
  endif
else (no)
  :Raise AuthenticationError;
  stop
endif

:Return Response;
stop
@enduml
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Acknowledgments

- Flume API Documentation
- InfluxDB Python Client
- aiohttp Library 