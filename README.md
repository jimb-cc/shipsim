# AIS Ship Movement Simulator

A Python application that simulates the movements of ships at sea and produces a stream of AIS (Automatic Identification System) data in JSON format with embedded NMEA sentences.

## Features

- Simulates 10-50 ships with realistic movement patterns
- Random walk movement model with configurable parameters
- Generates AIS Position Reports (Message Types 1, 2, 3)
- Outputs JSON format with decoded fields AND embedded NMEA !AIVDM sentences
- Configurable simulation parameters (number of ships, location, update interval)
- Real-time streaming output

## Requirements

- Python 3.6 or higher
- No external dependencies (uses only Python standard library)

## Installation

No installation required! Just download the script and run it:

```bash
chmod +x ship_simulator.py
```

## Usage

### Basic Usage

Run with default settings (20 ships in San Francisco Bay area):

```bash
python ship_simulator.py
```

### Custom Configuration

```bash
# Simulate 30 ships with 5-second updates
python ship_simulator.py --num-ships 30 --interval 5

# Run for 60 seconds in a specific location (New York Harbor)
python ship_simulator.py --lat 40.7 --lon -74.0 --duration 60

# Larger area with more ships
python ship_simulator.py -n 50 -r 100 --lat 51.5 --lon 0.0
```

### Command Line Options

```
-n, --num-ships NUM    Number of ships to simulate (default: 20)
-i, --interval SEC     Update interval in seconds (default: 10.0)
-d, --duration SEC     Simulation duration in seconds (default: infinite)
--lat DEGREES          Center latitude (default: 37.8)
--lon DEGREES          Center longitude (default: -122.4)
-r, --radius NM        Spawning radius in nautical miles (default: 50)
```

## Output Format

Each ship generates JSON messages with the following structure:

```json
{
  "timestamp": "2025-10-28T12:34:56.789Z",
  "message_type": 1,
  "mmsi": 366123456,
  "ship_name": "SHIP-001",
  "position": {
    "latitude": 37.825432,
    "longitude": -122.387654
  },
  "navigation": {
    "status": 0,
    "speed_knots": 12.3,
    "course": 145.2,
    "heading": 146.0
  },
  "nmea_sentence": "!AIVDM,1,1,,A,13HOI:0P0000VOHLCnHQKwvL05Ip,0*23"
}
```

### Field Descriptions

- **timestamp**: UTC timestamp in ISO 8601 format
- **message_type**: AIS message type (1, 2, or 3 for position reports)
- **mmsi**: Maritime Mobile Service Identity (unique 9-digit ship identifier)
- **ship_name**: Simulated ship name
- **position**: Current latitude and longitude
- **navigation**: Current navigation status, speed, course, and heading
- **nmea_sentence**: Raw NMEA !AIVDM sentence (standard maritime format)

### Navigation Status Codes

- 0: Under way using engine
- 1: At anchor
- 2: Not under command
- 3: Restricted maneuverability
- 5: Moored

## Examples

### Stream to File

```bash
python ship_simulator.py -n 25 -i 5 > ais_data.json
```

### Run for Specific Duration

```bash
# Generate 5 minutes of data with 3-second updates
python ship_simulator.py --duration 300 --interval 3
```

### Pipe to Another Tool

```bash
# Process AIS data with jq
python ship_simulator.py -n 10 | jq '.position'

# Filter specific ships
python ship_simulator.py | grep "SHIP-001"
```

### Use in Python Scripts

```python
from ship_simulator import ShipSimulator
import json

# Create simulator
sim = ShipSimulator(num_ships=15, center_lat=40.7, center_lon=-74.0)

# Get single snapshot of all ship positions
messages = sim.generate_ais_messages()
for msg in messages:
    print(json.dumps(msg, indent=2))

# Update positions and get new snapshot
sim.update_all_ships(time_delta=10.0)
messages = sim.generate_ais_messages()
```

## Architecture

The simulator consists of three main components:

### 1. Ship Class
- Maintains ship state (position, heading, speed, MMSI)
- Implements random walk movement model
- Generates realistic course and speed changes
- Keeps ships within valid coordinate bounds

### 2. AISEncoder Class
- Encodes ship data into AIS binary format
- Converts to 6-bit ASCII payload
- Generates NMEA !AIVDM sentences with checksums
- Handles AIS Position Report messages (Types 1, 2, 3)

### 3. ShipSimulator Class
- Manages fleet of ships
- Coordinates position updates
- Generates AIS messages for all ships
- Provides streaming output interface

## Movement Model

Ships use a random walk algorithm:
- Heading changes randomly with occasional course adjustments (-5 to +5 degrees)
- Speed varies realistically between 3 and 20 knots
- Position updates based on speed and heading using spherical earth calculations
- Ships stay within reasonable latitude bounds (-85 to 85 degrees)

## Technical Notes

### NMEA Sentence Format

The generated NMEA sentences follow the !AIVDM format:
```
!AIVDM,1,1,,A,<payload>,0*<checksum>
```

Where:
- Sentence count: 1 (single sentence message)
- Sentence number: 1
- Message ID: empty (sequential messages)
- Channel: A or B
- Payload: 6-bit ASCII encoded AIS data
- Fill bits: 0
- Checksum: XOR of all characters between ! and *

### Coordinate System

- Latitude: -90 (South) to +90 (North)
- Longitude: -180 (West) to +180 (East)
- Distances calculated using nautical miles (1 nm = 1/60 degree latitude)

## Stopping the Simulator

Press `Ctrl+C` to stop the simulation gracefully.

## License

This is a demonstration/educational tool. Use freely for testing and development purposes.

## Future Enhancements

Potential improvements:
- More AIS message types (static data, voyage data)
- Collision avoidance behavior
- Port/harbor awareness
- Weather effects on movement
- AIS message variations based on ship type
- Support for additional output formats (CSV, binary)
