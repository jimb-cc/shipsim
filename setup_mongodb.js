// MongoDB Setup Script for Ship Simulator
// Run this script with admin credentials:
//   mongosh --username <admin-user> --password <admin-password> --authenticationDatabase admin < setup_mongodb.js
//
// Or set environment variables and run:
//   export SHIPSIM_APP_PASSWORD="your_secure_password"
//   mongosh --username <admin-user> --password <admin-password> --authenticationDatabase admin < setup_mongodb.js

// Get password from environment variable, or generate a random one
const appPassword = process.env.SHIPSIM_APP_PASSWORD;

if (!appPassword) {
  print("ERROR: SHIPSIM_APP_PASSWORD environment variable must be set");
  print("Example: export SHIPSIM_APP_PASSWORD='your_secure_password'");
  quit(1);
}

// Switch to shipsim database
use shipsim

// Create a dedicated app user with readWrite permissions on shipsim database only
try {
  db.createUser({
    user: "shipsim_app",
    pwd: appPassword,
    roles: [
      { role: "readWrite", db: "shipsim" }
    ]
  })
  print("✓ User 'shipsim_app' created with readWrite permissions on 'shipsim' database")
} catch (err) {
  if (err.code === 51003) {
    print("ℹ User 'shipsim_app' already exists")
  } else {
    throw err
  }
}

// Create the collection if it doesn't exist
db.createCollection("ais")
print("✓ Collection 'ais' created")

// Create 2dsphere index on location field for geospatial queries
db.ais.createIndex({ "location": "2dsphere" })
print("✓ Geospatial index created on 'location' field")

print("")
print("Setup complete! You can now run the ship simulator with:")
print("  python ship_simulator.py --mongodb-user shipsim_app --mongodb-password <your-password>")
