# AIS Ship Movement Simulator

A Python application that simulates the movements of ships at sea and produces a stream of AIS (Automatic Identification System) data in JSON format with embedded NMEA sentences.

## Features

- Simulates multiple ships with realistic movement patterns
- Random walk movement model with configurable parameters
- Generates AIS Position Reports (Message Types 1, 2, 3)
- Outputs JSON format with decoded fields AND embedded NMEA !AIVDM sentences
- **GeoJSON polygon-based geofencing** with edge avoidance behavior
- **MongoDB-stored configuration** for easy fleet management
- Custom bounding polygons via geojson.io
- Real-time streaming output
- **MongoDB integration** for data storage with geospatial indexing
- Realistic ship name generation (10,000+ unique combinations)
- Stationary ship behavior (anchored/moored vessels)

## Requirements

- Python 3.6 or higher
- `pymongo` library for MongoDB support
- MongoDB instance (local, authenticated, or MongoDB Atlas)

## Installation

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
pip install pymongo
```

2. Make the script executable:

```bash
chmod +x ship_simulator.py
```

## Usage

### Quick Start

The simulator requires a MongoDB connection. On first run, it will automatically create:
- Default configuration in `shipsim.config` collection
- Default "firth_of_clyde" bounding polygon in `shipsim.bounding_poly` collection
- 2dsphere geospatial index on the `shipsim.ais` collection

Run with a local MongoDB instance:

```bash
# Using environment variable (recommended)
export MONGODB_URI="mongodb://localhost:27017/shipsim"
python ship_simulator.py

# Or pass URI directly
python ship_simulator.py --mongodb-uri "mongodb://localhost:27017/shipsim"
```

Run with authentication:

```bash
# Local authenticated instance
python ship_simulator.py --mongodb-uri "mongodb://username:password@localhost:27017/shipsim?authSource=admin"

# MongoDB Atlas
python ship_simulator.py --mongodb-uri "mongodb+srv://username:password@cluster.mongodb.net/shipsim"
```

### Command Line Options

```
--mongodb-uri URI        MongoDB connection string (can also use MONGODB_URI env var)
--collection NAME        Collection name for AIS data (default: ais)
-d, --duration SEC       Simulation duration in seconds (default: infinite)
```

**All other configuration (number of ships, update interval, bounding polygon, etc.) is stored in the MongoDB `config` collection and can be modified there.**

## Configuration

All simulator configuration is stored in MongoDB's `shipsim.config` collection. The default configuration is:

```json
{
  "num_ships": 20,
  "interval": 10.0,
  "bounding_poly_name": "firth_of_clyde",
  "output_stdout": true
}
```

To change configuration, update the document in MongoDB:

```bash
mongosh "mongodb://localhost:27017/shipsim"
db.config.updateOne({}, {$set: {num_ships: 50, interval: 5.0}})
```

Or using MongoDB Compass, edit the configuration document directly.

### Configuration Fields

- **num_ships**: Number of ships to simulate (default: 20)
- **interval**: Update interval in seconds (default: 10.0)
- **bounding_poly_name**: Name of polygon from `bounding_poly` collection (default: "firth_of_clyde")
- **output_stdout**: Whether to print AIS messages to console (default: true)

## Creating Custom Bounding Polygons

The simulator uses GeoJSON polygons to define where ships can operate. Ships spawn randomly within the polygon and automatically steer away from edges.

### Using geojson.io to Create Polygons

1. **Visit geojson.io**: Open [https://geojson.io/](https://geojson.io/) in your browser

2. **Draw Your Polygon**:
   - Zoom to your desired location on the map
   - Click the polygon tool (pentagon icon) on the right
   - Click around the map to define your boundary
   - Close the polygon by clicking on the starting point
   - The right panel shows the GeoJSON automatically

3. **Add the Name Property**:
   - In the right panel, locate the `"properties"` object
   - Add a `"name"` field with your chosen identifier
   - Example:
   ```json
   {
     "type": "Feature",
     "properties": {
       "name": "new_york_harbor"
     },
     "geometry": {
       "type": "Polygon",
       "coordinates": [[...]]
     }
   }
   ```

4. **Wrap in FeatureCollection** (if not already):
   - The polygon must be inside a FeatureCollection
   - geojson.io usually does this automatically
   - Format should be:
   ```json
   {
     "type": "FeatureCollection",
     "features": [
       {
         "type": "Feature",
         "properties": {"name": "your_polygon_name"},
         "geometry": {
           "type": "Polygon",
           "coordinates": [[...]]
         }
       }
     ]
   }
   ```

5. **Insert into MongoDB**:

   **Option A: Using MongoDB Compass**
   - Connect to your MongoDB instance
   - Navigate to the `shipsim` database
   - Open the `bounding_poly` collection
   - Click "Add Data" → "Insert Document"
   - Paste your GeoJSON (with the name property added)
   - Click "Insert"

   **Option B: Using mongosh**
   ```bash
   mongosh "mongodb://localhost:27017/shipsim"
   db.bounding_poly.insertOne({
     "type": "FeatureCollection",
     "features": [{
       "type": "Feature",
       "properties": {"name": "new_york_harbor"},
       "geometry": {
         "type": "Polygon",
         "coordinates": [
           [
             [-74.05, 40.70],
             [-74.05, 40.75],
             [-73.95, 40.75],
             [-73.95, 40.70],
             [-74.05, 40.70]
           ]
         ]
       }
     }]
   })
   ```

6. **Update Configuration to Use Your Polygon**:
   ```bash
   db.config.updateOne({}, {$set: {bounding_poly_name: "new_york_harbor"}})
   ```

7. **Restart the Simulator**: The new polygon will be loaded automatically

### Polygon Best Practices

- **Close the polygon**: First and last coordinate must be identical
- **Avoid self-intersections**: Polygon edges shouldn't cross
- **Use reasonable sizes**: Very large polygons (>100nm) may have sparse ship distributions
- **Coordinate order**: GeoJSON uses [longitude, latitude], not [latitude, longitude]
- **Edge buffer**: Ships will stay at least 5-10nm from polygon edges when possible

## MongoDB Integration

The simulator stores AIS data in MongoDB with automatic geospatial indexing.

### MongoDB Data Structure

Data is stored with GeoJSON location format for geospatial queries:

```json
{
  "timestamp": "2025-10-28T12:34:56.789Z",
  "message_type": 1,
  "mmsi": 366123456,
  "ship_name": "Atlantic Trader",
  "location": {
    "type": "Point",
    "coordinates": [-122.387654, 37.825432]
  },
  "navigation": {
    "status": "under way using engine",
    "speed_knots": 12.3,
    "course": 145.2,
    "heading": 146.0
  },
  "nmea_sentence": "!AIVDM,1,1,,A,13HOI:0P0000VOHLCnHQKwvL05Ip,0*23"
}
```

**Note:** The `location` field uses GeoJSON format with a 2dsphere index automatically created for efficient geospatial queries.

### Querying MongoDB Data

Example queries using MongoDB shell:

```javascript
// Find all ships within 10km of a point
db.ais.find({
  location: {
    $near: {
      $geometry: { type: "Point", coordinates: [-122.4, 37.8] },
      $maxDistance: 10000
    }
  }
})

// Find ships by name
db.ais.find({ ship_name: "Atlantic Trader" })

// Find ships above 15 knots
db.ais.find({ "navigation.speed_knots": { $gt: 15 } })

// Get latest position for each ship
db.ais.aggregate([
  { $sort: { timestamp: -1 } },
  { $group: { _id: "$mmsi", latest: { $first: "$$ROOT" } } }
])
```

### MongoDB Collections

The simulator uses three collections:

1. **ais**: Ship position data with geospatial index
2. **config**: Simulator configuration (single document)
3. **bounding_poly**: GeoJSON polygons defining simulation boundaries

### Troubleshooting MongoDB Connection

**Problem: "Authentication failed" error**

Solution: Include authentication database in your connection URI:

```bash
# If your user is in the admin database
python ship_simulator.py --mongodb-uri "mongodb://username:password@localhost:27017/shipsim?authSource=admin"
```

**Problem: No data appearing in MongoDB**

1. Check that you see these messages when running the simulator:
   - `✓ Connected to MongoDB`
   - `✓ Created geospatial index on shipsim.ais.location`
   - `✓ Stored X messages to MongoDB` (appears when you stop with Ctrl+C)

2. Verify data is being written:
   ```bash
   mongosh "mongodb://localhost:27017/shipsim"
   db.ais.countDocuments()
   db.ais.findOne()
   ```

3. Check MongoDB logs for errors:
   ```bash
   sudo tail -f /var/log/mongodb/mongod.log
   ```

**Problem: Connection string issues**

- Ensure the database name is in the path: `mongodb://host:port/database_name`
- For authentication, add `?authSource=admin` or appropriate auth database
- For Atlas, use the `mongodb+srv://` protocol
- Check firewall rules if connecting to remote MongoDB

## Output Format

Each ship generates JSON messages with the following structure:

```json
{
  "timestamp": "2025-10-28T12:34:56.789Z",
  "message_type": 1,
  "mmsi": 366123456,
  "ship_name": "MSC Singapore",
  "location": {
    "type": "Point",
    "coordinates": [-122.387654, 37.825432]
  },
  "navigation": {
    "status": "under way using engine",
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
- **ship_name**: Realistic ship name (10,000+ unique combinations)
- **location**: GeoJSON Point format with coordinates [longitude, latitude]. Access coordinates as `location.coordinates[0]` (longitude) and `location.coordinates[1]` (latitude)
- **navigation**: Current navigation status, speed, course, and heading
- **nmea_sentence**: Raw NMEA !AIVDM sentence (standard maritime format)

### Navigation Status Values

The `navigation.status` field contains a text string describing the ship's current status:

- **"under way using engine"**: Ship is moving under its own power
- **"at anchor"**: Ship is anchored (stationary)
- **"not under command"**: Ship is unable to maneuver
- **"restricted maneuverability"**: Ship has limited ability to maneuver
- **"moored"**: Ship is tied to a dock or mooring (stationary)

Note: Ships with "at anchor" or "moored" status remain stationary and report zero speed.

## Examples

### Run for Limited Time

Generate data for a specific duration:

```bash
# Run for 5 minutes
export MONGODB_URI="mongodb://localhost:27017/shipsim"
python ship_simulator.py --duration 300
```

### Long-Running Simulation

For production or long-term testing:

```bash
# Run indefinitely in background
nohup python ship_simulator.py --mongodb-uri "mongodb://localhost:27017/shipsim" &

# Monitor with tail
tail -f nohup.out
```

### Querying Realtime Data with jq

If `output_stdout` is true in config, you can pipe to jq:

```bash
# Show only locations
python ship_simulator.py | jq '.location'

# Filter ships above 15 knots
python ship_simulator.py | jq 'select(.navigation.speed_knots > 15)'

# Extract ship names and coordinates
python ship_simulator.py | jq '{name: .ship_name, lon: .location.coordinates[0], lat: .location.coordinates[1]}'
```

### Multiple Simulation Areas

Run multiple simulators for different regions:

```bash
# Terminal 1: Firth of Clyde (default)
python ship_simulator.py --mongodb-uri "mongodb://localhost:27017/shipsim" --collection firth_of_clyde

# Terminal 2: New York (after creating polygon and config)
python ship_simulator.py --mongodb-uri "mongodb://localhost:27017/shipsim" --collection new_york
```

### Production Monitoring

Check statistics:

```bash
# Count documents
mongosh "mongodb://localhost:27017/shipsim"
db.ais.countDocuments()

# Recent ships
db.ais.find().sort({timestamp: -1}).limit(10)

# Ships by status
db.ais.aggregate([
  {$group: {_id: "$navigation.status", count: {$sum: 1}}},
  {$sort: {count: -1}}
])
```

## Architecture

The simulator consists of five main components:

### 1. Ship Class
- Maintains ship state (position, heading, speed, MMSI, status)
- Implements random walk movement model with geofencing
- Generates realistic course and speed changes
- Applies edge avoidance when approaching polygon boundaries
- Stationary behavior for anchored/moored vessels

### 2. BoundingPolygon Class
- Loads GeoJSON polygons from MongoDB
- Point-in-polygon detection using ray casting algorithm
- Random point generation within polygon boundaries
- Distance-to-edge calculations
- Heading suggestion for edge avoidance (distance-weighted blending)

### 3. ConfigManager Class
- Loads configuration from MongoDB
- Auto-creates default configuration if not present
- Manages bounding polygon loading and initialization
- Falls back to embedded default "firth_of_clyde" polygon

### 4. AISEncoder Class
- Encodes ship data into AIS binary format
- Converts to 6-bit ASCII payload
- Generates NMEA !AIVDM sentences with checksums
- Handles AIS Position Report messages (Types 1, 2, 3)
- Maps text status strings to AIS status codes

### 5. ShipSimulator Class
- Manages fleet of ships
- Coordinates position updates
- Generates AIS messages for all ships
- Provides streaming output interface
- Optional MongoDB storage with batched writes

## Movement Model

Ships use an enhanced random walk algorithm with geofencing:

### Basic Movement
- Heading changes randomly with occasional course adjustments (-5 to +5 degrees)
- Speed varies realistically between 3 and 20 knots
- Position updates based on speed and heading using spherical earth calculations
- 90% of ships are "under way using engine", 10% are stationary (anchored/moored)

### Edge Avoidance
- Ships detect when approaching polygon boundaries
- Applies weighted steering correction based on distance:
  - Within 5nm of edge: 70% correction toward center, 30% current heading
  - Within 10nm of edge: 30% correction toward center, 70% current heading
  - Beyond 10nm: No correction applied
- Uses circular averaging to blend headings smoothly (handles 359°/0° wraparound)

### Stationary Ships
- Ships with "at anchor" or "moored" status remain stationary
- Speed fixed at 0 knots
- Position does not update
- Heading remains constant

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
- **Important**: GeoJSON uses [longitude, latitude] order, opposite of typical [lat, lon]

### GeoJSON Format

The simulator uses standard GeoJSON format with FeatureCollection:

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {"name": "polygon_name"},
    "geometry": {
      "type": "Polygon",
      "coordinates": [
        [
          [lon1, lat1],
          [lon2, lat2],
          [lon3, lat3],
          [lon1, lat1]  // Must close the polygon
        ]
      ]
    }
  }]
}
```

Key requirements:
- First and last coordinates must be identical (closed polygon)
- Coordinate order is [longitude, latitude]
- Multiple rings are supported (outer boundary + holes)

## Stopping the Simulator

Press `Ctrl+C` to stop the simulation gracefully. The simulator will:
- Display statistics (messages generated, duration)
- Flush any pending MongoDB writes
- Close database connections cleanly

## License

This is a demonstration/educational tool. Use freely for testing and development purposes.

## Future Enhancements

Potential improvements:
- More AIS message types (static data, voyage data)
- Collision avoidance behavior between ships
- Port/harbor awareness and docking behavior
- Weather effects on movement and speed
- AIS message variations based on ship type (cargo, tanker, passenger)
- Support for additional output formats (CSV, Parquet)
- Web dashboard for realtime visualization
- Docker containerization for easy deployment
