# MongoDB Integration Guide

This guide explains how to use the AIS Ship Simulator with MongoDB for storing and querying ship tracking data.

## Overview

The ship simulator can store AIS messages in MongoDB with proper GeoJSON formatting for geospatial queries. Each message includes:
- Ship identification (MMSI, name)
- GeoJSON location data (for geospatial queries)
- Navigation data (speed, course, heading)
- Raw NMEA sentence
- Timestamp

## Setup

### 1. Start MongoDB

Ensure MongoDB is running locally on the default port (27017).

### 2. Create App User

First create the database structure:

```bash
mongosh --username <admin-user> --password --authenticationDatabase admin < setup_mongodb_admin.js
```

Then create the app user:

```bash
export SHIPSIM_APP_PASSWORD="your_secure_password"
mongosh --username <admin-user> --password --authenticationDatabase admin < setup_mongodb.js
```

This creates:
- User: `shipsim_app` with your chosen password
- Database: `shipsim`
- Collection: `ais`
- Geospatial index on `location` field

## Usage

### Basic MongoDB Storage

Store AIS data to MongoDB and output to console:

```bash
export MONGODB_PASSWORD="your_password"
python ship_simulator.py \
  --mongodb-user shipsim_app \
  -n 20 -i 10
```

### MongoDB Only (No Console Output)

Store to MongoDB without console output for better performance:

```bash
python ship_simulator.py \
  --mongodb-user shipsim_app \
  --no-stdout \
  -n 50 -i 5
# Password will be prompted
```

### Custom MongoDB Configuration

```bash
export MONGODB_PASSWORD="your_password"
python ship_simulator.py \
  --mongodb-host localhost \
  --mongodb-port 27017 \
  --mongodb-database shipsim \
  --mongodb-collection ais \
  --mongodb-user shipsim_app \
  -n 30 -i 10
```

### Using Admin User

If you need to use an admin user with different auth database:

```bash
export MONGODB_PASSWORD="admin_password"
python ship_simulator.py \
  --mongodb-user <admin-user> \
  --mongodb-auth-db admin \
  --mongodb-database shipsim \
  --mongodb-collection ais
```

## Data Format

### Document Structure

```json
{
  "timestamp": "2025-10-28T18:28:37.481920Z",
  "message_type": 2,
  "mmsi": 366387774,
  "ship_name": "SHIP-001",
  "location": {
    "type": "Point",
    "coordinates": [-5.00303, 55.818444]
  },
  "position": {
    "latitude": 55.818444,
    "longitude": -5.00303
  },
  "navigation": {
    "status": 0,
    "speed_knots": 7.2,
    "course": 152.7,
    "heading": 152.7
  },
  "nmea_sentence": "!AIVDM,1,1,,A,BE]Z\"O @AH/)FQL_<H^%=41J@@@@,0*5D"
}
```

### GeoJSON Format

The `location` field uses GeoJSON Point format:
- **Coordinates order**: `[longitude, latitude]` (MongoDB/GeoJSON standard)
- **Type**: Always "Point"
- **Index**: 2dsphere index for geospatial queries

## Querying MongoDB

### Connect to MongoDB

```bash
mongosh --username shipsim_app --password --authenticationDatabase shipsim shipsim
```

### Count Documents

```javascript
db.ais.countDocuments()
```

### Find Ships by MMSI

```javascript
db.ais.find({ mmsi: 366387774 }).sort({ timestamp: -1 }).limit(10)
```

### Find Latest Position for Each Ship

```javascript
db.ais.aggregate([
  { $sort: { timestamp: -1 } },
  { $group: {
    _id: "$mmsi",
    latest: { $first: "$$ROOT" }
  }},
  { $replaceRoot: { newRoot: "$latest" } }
])
```

### Geospatial Queries

#### Find ships within 50km of a point

```javascript
db.ais.find({
  location: {
    $near: {
      $geometry: {
        type: "Point",
        coordinates: [-5.0, 55.8]  // [longitude, latitude]
      },
      $maxDistance: 50000  // meters
    }
  }
})
```

#### Find ships within a polygon (e.g., Firth of Clyde)

```javascript
db.ais.find({
  location: {
    $geoWithin: {
      $geometry: {
        type: "Polygon",
        coordinates: [[
          [-5.5, 55.5],
          [-4.5, 55.5],
          [-4.5, 56.0],
          [-5.5, 56.0],
          [-5.5, 55.5]
        ]]
      }
    }
  }
})
```

#### Find ships within a circle

```javascript
db.ais.find({
  location: {
    $geoWithin: {
      $centerSphere: [
        [-5.0, 55.8],  // [longitude, latitude]
        10 / 6378.1    // radius in radians (10 km)
      ]
    }
  }
})
```

### Track Ship Movement Over Time

```javascript
db.ais.find(
  { mmsi: 366387774 },
  { timestamp: 1, location: 1, navigation: 1, _id: 0 }
).sort({ timestamp: 1 })
```

### Find Fast-Moving Ships

```javascript
db.ais.aggregate([
  { $sort: { timestamp: -1 } },
  { $group: {
    _id: "$mmsi",
    latest: { $first: "$$ROOT" }
  }},
  { $replaceRoot: { newRoot: "$latest" } },
  { $match: { "navigation.speed_knots": { $gt: 15 } } },
  { $sort: { "navigation.speed_knots": -1 } }
])
```

## Performance Tips

### 1. Batch Inserts

The simulator automatically batches inserts by ship update interval. For better performance:

```bash
# Larger intervals = fewer writes
export MONGODB_PASSWORD="your_password"
python ship_simulator.py --mongodb-user shipsim_app -i 30
```

### 2. Use --no-stdout for High Volume

When storing large amounts of data, disable console output:

```bash
python ship_simulator.py --mongodb-user shipsim_app --no-stdout -n 100 -i 5
# Password will be prompted
```

### 3. Create Additional Indexes

For specific query patterns, create additional indexes:

```javascript
// Index on timestamp for time-based queries
db.ais.createIndex({ timestamp: -1 })

// Compound index for MMSI + timestamp
db.ais.createIndex({ mmsi: 1, timestamp: -1 })

// Index on ship name
db.ais.createIndex({ ship_name: 1 })
```

### 4. TTL Index for Automatic Cleanup

Auto-delete old data after 7 days:

```javascript
db.ais.createIndex(
  { timestamp: 1 },
  { expireAfterSeconds: 604800 }  // 7 days
)
```

## Example: Real-time Ship Tracking Dashboard

### 1. Start the Simulator

```bash
export MONGODB_PASSWORD="your_password"
python ship_simulator.py \
  --mongodb-user shipsim_app \
  --no-stdout \
  -n 50 -i 5 &
```

### 2. Query Latest Positions

```javascript
// Get latest position for all ships
use shipsim
db.ais.aggregate([
  { $sort: { timestamp: -1 } },
  { $group: {
    _id: "$mmsi",
    ship_name: { $first: "$ship_name" },
    location: { $first: "$location" },
    navigation: { $first: "$navigation" },
    timestamp: { $first: "$timestamp" }
  }}
])
```

### 3. Monitor Ships in Real-time

```javascript
// Watch for new ships entering an area
db.ais.watch([
  {
    $match: {
      "fullDocument.location": {
        $geoWithin: {
          $geometry: {
            type: "Polygon",
            coordinates: [[
              [-5.2, 55.7],
              [-4.8, 55.7],
              [-4.8, 55.9],
              [-5.2, 55.9],
              [-5.2, 55.7]
            ]]
          }
        }
      }
    }
  }
])
```

## Troubleshooting

### Authentication Failed

If you get authentication errors:

```bash
# Verify user exists
mongosh --username <admin-user> --password --authenticationDatabase admin
use shipsim
db.getUsers()

# Recreate user if needed
db.dropUser("shipsim_app")
# Then run setup_mongodb.js again with SHIPSIM_APP_PASSWORD set
```

### Index Not Found

If geospatial queries fail:

```bash
# Check indexes
mongosh --username shipsim_app --password --authenticationDatabase shipsim shipsim
db.ais.getIndexes()

# Recreate index if missing
db.ais.createIndex({ "location": "2dsphere" })
```

### Permission Denied

The `shipsim_app` user has readWrite permissions on the `shipsim` database only. To access other databases, use an admin user:

```bash
export MONGODB_PASSWORD="admin_password"
python ship_simulator.py \
  --mongodb-user <admin-user> \
  --mongodb-auth-db admin
```

## Security Recommendations

For production use:

1. **Use strong passwords**: Choose secure passwords when creating users with the setup scripts

2. **Enable SSL/TLS** in MongoDB configuration

3. **Use environment variables** for credentials:
   ```bash
   export MONGODB_USER=shipsim_app
   export MONGODB_PASSWORD=your_secure_password

   python ship_simulator.py --mongodb-user $MONGODB_USER
   ```

4. **Or use interactive prompts** (most secure for interactive use):
   ```bash
   python ship_simulator.py --mongodb-user shipsim_app
   # Password will be prompted securely
   ```

4. **Restrict network access** using MongoDB IP binding

5. **Enable MongoDB audit logging**

## Integration with Other Tools

### Export to JSON

```bash
mongoexport \
  --username=shipsim_app \
  --password \
  --authenticationDatabase=shipsim \
  --db=shipsim \
  --collection=ais \
  --out=ais_data.json
```

### Import to Another Database

```bash
mongoimport \
  --username=<user> \
  --password \
  --authenticationDatabase=<auth-db> \
  --host=remote-host \
  --db=shipsim \
  --collection=ais \
  --file=ais_data.json
```

### Query with Python

```python
from pymongo import MongoClient
import os

# Use environment variable for password
password = os.environ.get('MONGODB_PASSWORD')
client = MongoClient(
    host='localhost',
    port=27017,
    username='shipsim_app',
    password=password,
    authSource='shipsim'
)
db = client.shipsim
collection = db.ais

# Find ships near a point
ships = collection.find({
    "location": {
        "$near": {
            "$geometry": {
                "type": "Point",
                "coordinates": [-5.0, 55.8]
            },
            "$maxDistance": 50000
        }
    }
})

for ship in ships:
    print(f"{ship['ship_name']}: {ship['location']['coordinates']}")
```

## Additional Resources

- [MongoDB Geospatial Queries Documentation](https://docs.mongodb.com/manual/geospatial-queries/)
- [GeoJSON Specification](https://geojson.org/)
- [AIS Message Format](https://gpsd.gitlab.io/gpsd/AIVDM.html)
