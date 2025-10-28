// MongoDB Setup Script for Ship Simulator
// Creates the database, collection, and geospatial index
// Run this with admin credentials:
//   mongosh --username <admin-user> --password <admin-password> --authenticationDatabase admin < setup_mongodb_admin.js

// Switch to shipsim database
use shipsim

// Create the ais collection
db.createCollection("ais")
print("✓ Collection 'ais' created")

// Create 2dsphere index on location field for geospatial queries
db.ais.createIndex({ "location": "2dsphere" })
print("✓ Geospatial index created on 'location' field")

print("")
print("MongoDB setup complete!")
print("Next step: Run setup_mongodb.js to create the application user")
