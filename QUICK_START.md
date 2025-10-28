# AIS Ship Simulator - Quick Start Guide

## What You Have

A Python-based AIS (Automatic Identification System) ship movement simulator that:
- Simulates realistic ship movements in the Firth of Clyde, Scotland
- Generates AIS messages in JSON format with embedded NMEA sentences
- Stores data in MongoDB with GeoJSON formatting for geospatial queries
- Supports 10-50 ships with configurable parameters

## Installation

### 1. Python Environment

```bash
cd /home/jim/projects/shipsim
python3 -m venv venv
venv/bin/pip install pymongo
```

### 2. MongoDB Setup

First, create the database and collection:

```bash
cd /home/jim/projects/shipsim
mongosh --username <admin-user> --password --authenticationDatabase admin < setup_mongodb_admin.js
```

Then create the application user:

```bash
export SHIPSIM_APP_PASSWORD="your_secure_password_here"
mongosh --username <admin-user> --password --authenticationDatabase admin < setup_mongodb.js
```

This creates:
- Database: `shipsim`
- Collection: `ais`
- User: `shipsim_app` (readWrite on shipsim)
- Geospatial index on `location` field

## Basic Usage

### Console Output Only

```bash
venv/bin/python ship_simulator.py -n 10 -i 5
```

### Store to MongoDB

**Option 1: Interactive password prompt**
```bash
venv/bin/python ship_simulator.py \
  --mongodb-user shipsim_app \
  -n 20 -i 10
# You'll be prompted for the password
```

**Option 2: Environment variable**
```bash
export MONGODB_PASSWORD="your_password_here"
venv/bin/python ship_simulator.py \
  --mongodb-user shipsim_app \
  -n 20 -i 10
```

**Option 3: Command line (not recommended for security)**
```bash
venv/bin/python ship_simulator.py \
  --mongodb-user shipsim_app \
  --mongodb-password "your_password" \
  -n 20 -i 10
```

### MongoDB Only (No Console)

```bash
export MONGODB_PASSWORD="your_password_here"
venv/bin/python ship_simulator.py \
  --mongodb-user shipsim_app \
  --no-stdout \
  -n 50 -i 5
```

## Command Line Options

### Simulation Parameters

- `-n, --num-ships NUM` - Number of ships (default: 20)
- `-i, --interval SEC` - Update interval in seconds (default: 10)
- `-d, --duration SEC` - Run duration in seconds (default: infinite)

### Location

- `--lat DEGREES` - Center latitude (default: 55.8 - Firth of Clyde)
- `--lon DEGREES` - Center longitude (default: -5.0)
- `-r, --radius NM` - Spawning radius in nautical miles (default: 50)

### MongoDB

- `--mongodb-host HOST` - MongoDB host (default: localhost)
- `--mongodb-port PORT` - MongoDB port (default: 27017)
- `--mongodb-database DB` - Database name (default: shipsim)
- `--mongodb-collection COLL` - Collection name (default: ais)
- `--mongodb-user USER` - Username
- `--mongodb-password PASS` - Password
- `--mongodb-auth-db DB` - Auth database (default: same as database)
- `--no-stdout` - Disable console output

## Output Format

### JSON with GeoJSON Location

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

## Quick MongoDB Queries

### Connect to MongoDB

```bash
mongosh --username shipsim_app --password --authenticationDatabase shipsim shipsim
```

### Count Ships

```javascript
db.ais.countDocuments()
```

### Find Ships Near a Point

```javascript
db.ais.find({
  location: {
    $near: {
      $geometry: {
        type: "Point",
        coordinates: [-5.0, 55.8]
      },
      $maxDistance: 50000  // 50km in meters
    }
  }
}).limit(10)
```

### Get Latest Position for Each Ship

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

## Files

All files are located in `/home/jim/projects/shipsim/`:

- `ship_simulator.py` - Main simulator application
- `setup_mongodb.js` - MongoDB setup script for creating app user
- `setup_mongodb_admin.js` - MongoDB setup for database/collection/indexes
- `README.md` - Detailed documentation
- `MONGODB_GUIDE.md` - Complete MongoDB integration guide
- `QUICK_START.md` - This file
- `venv/` - Python virtual environment

## Examples

### Generate 1 hour of data

```bash
export MONGODB_PASSWORD="your_password"
venv/bin/python ship_simulator.py \
  --mongodb-user shipsim_app \
  --no-stdout \
  -n 30 -i 10 -d 3600
```

### Simulate different location (New York Harbor)

```bash
export MONGODB_PASSWORD="your_password"
venv/bin/python ship_simulator.py \
  --mongodb-user shipsim_app \
  --lat 40.7 --lon -74.0 \
  -n 25 -i 10
```

### High frequency updates

```bash
venv/bin/python ship_simulator.py \
  --mongodb-user shipsim_app \
  -n 10 -i 2
# Password will be prompted
```

## Troubleshooting

### pymongo not found

```bash
venv/bin/pip install pymongo
```

### MongoDB authentication failed

Verify the user was created:

```bash
mongosh --username <admin-user> --password --authenticationDatabase admin
use shipsim
db.getUsers()
```

### No data in MongoDB

Check that you're using the correct credentials:

```bash
venv/bin/python ship_simulator.py \
  --mongodb-user shipsim_app \
  -n 5 -i 5 -d 10
# Enter password when prompted
```

Verify data:

```bash
mongosh --username shipsim_app --password --authenticationDatabase shipsim \
  --eval "db.ais.countDocuments()" shipsim
```

## Next Steps

1. **Explore MongoDB queries**: See `MONGODB_GUIDE.md` for geospatial query examples
2. **Customize ship behavior**: Edit `Ship` class in `ship_simulator.py`
3. **Add more AIS message types**: Extend `AISEncoder` class
4. **Build a dashboard**: Use the MongoDB data with your visualization tool of choice
5. **Set up TTL indexes**: Auto-delete old data after a certain time

## Support

- MongoDB Geospatial Queries: https://docs.mongodb.com/manual/geospatial-queries/
- AIS Protocol: https://gpsd.gitlab.io/gpsd/AIVDM.html
- GeoJSON Specification: https://geojson.org/

Enjoy tracking your virtual ships!
