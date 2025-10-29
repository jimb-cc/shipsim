#!/usr/bin/env python3
"""
AIS Ship Movement Simulator
Simulates ship movements at sea and generates AIS data streams in JSON format with embedded NMEA sentences.
"""

import math
import random
import time
import json
import sys
import copy
import getpass
import os
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

try:
    from pymongo import MongoClient, GEOSPHERE
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False


class AISEncoder:
    """Encodes AIS messages to NMEA format."""

    # AIS 6-bit ASCII encoding table
    PAYLOAD_ARMOR = "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_ !\"#$%&'()*+,-./0123456789:;<=>?"

    # Status text to AIS integer code mapping (for NMEA encoding)
    STATUS_TO_CODE = {
        "under way using engine": 0,
        "at anchor": 1,
        "not under command": 2,
        "restricted maneuverability": 3,
        "moored": 5
    }

    @staticmethod
    def encode_sixbit(value: int, num_bits: int) -> str:
        """Encode an integer value to 6-bit ASCII string."""
        result = []
        for i in range((num_bits + 5) // 6):
            # Extract 6 bits at a time from the value
            shift = num_bits - (i + 1) * 6
            if shift < 0:
                shift = 0
            six_bits = (value >> max(0, shift)) & 0x3F
            result.append(AISEncoder.PAYLOAD_ARMOR[six_bits])
        return ''.join(result)

    @staticmethod
    def encode_position_report(ship_data: Dict[str, Any]) -> str:
        """
        Encode AIS Position Report (Type 1, 2, or 3) to NMEA payload.
        Returns the encoded payload string.
        """
        # Build binary message (simplified - focusing on key fields)
        msg_type = ship_data['message_type']  # 1, 2, or 3
        repeat = 0
        mmsi = ship_data['mmsi']
        # Convert text status to integer code for NMEA encoding
        status = AISEncoder.STATUS_TO_CODE.get(ship_data['status'], 0)
        turn = 0  # Rate of turn
        speed = int(ship_data['speed'] * 10)  # Speed in 0.1 knots
        accuracy = 1
        lon = int(ship_data['lon'] * 600000)  # Longitude in 1/10000 minutes
        lat = int(ship_data['lat'] * 600000)  # Latitude in 1/10000 minutes
        course = int(ship_data['course'] * 10)  # Course in 0.1 degrees
        heading = int(ship_data['heading'])
        timestamp = ship_data['timestamp']
        maneuver = 0
        spare = 0
        raim = 0
        radio = 0

        # Pack the bits (simplified version - real AIS encoding is more complex)
        # This is a basic implementation that creates valid-looking NMEA sentences
        bits = []
        bits.append(format(msg_type, '06b'))      # 6 bits: message type
        bits.append(format(repeat, '02b'))        # 2 bits: repeat indicator
        bits.append(format(mmsi, '030b'))         # 30 bits: MMSI
        bits.append(format(status, '04b'))        # 4 bits: navigation status
        bits.append(format(turn & 0xFF, '08b'))   # 8 bits: rate of turn
        bits.append(format(min(speed, 1022), '010b'))  # 10 bits: speed
        bits.append(format(accuracy, '01b'))      # 1 bit: position accuracy
        bits.append(format(lon & 0x7FFFFFF, '028b'))   # 28 bits: longitude
        bits.append(format(lat & 0x7FFFFFF, '027b'))   # 27 bits: latitude
        bits.append(format(course & 0xFFF, '012b'))    # 12 bits: course
        bits.append(format(heading & 0x1FF, '09b'))    # 9 bits: heading
        bits.append(format(timestamp, '06b'))     # 6 bits: timestamp
        bits.append(format(maneuver, '02b'))      # 2 bits: maneuver indicator
        bits.append(format(spare, '03b'))         # 3 bits: spare
        bits.append(format(raim, '01b'))          # 1 bit: RAIM flag
        bits.append(format(radio, '019b'))        # 19 bits: radio status

        # Combine all bits
        bit_string = ''.join(bits)

        # Pad to 6-bit boundary
        while len(bit_string) % 6 != 0:
            bit_string += '0'

        # Convert to 6-bit ASCII
        payload = []
        for i in range(0, len(bit_string), 6):
            six_bits = int(bit_string[i:i+6], 2)
            payload.append(AISEncoder.PAYLOAD_ARMOR[six_bits])

        return ''.join(payload)

    @staticmethod
    def create_nmea_sentence(payload: str, channel: str = 'A') -> str:
        """
        Create a complete NMEA !AIVDM sentence with checksum.
        """
        # For single-sentence messages
        fragment_count = 1
        fragment_number = 1
        message_id = ""  # Empty for single-sentence
        radio_channel = channel
        fill_bits = 0

        # Build sentence without checksum
        sentence = f"AIVDM,{fragment_count},{fragment_number},{message_id},{radio_channel},{payload},{fill_bits}"

        # Calculate checksum
        checksum = 0
        for char in sentence:
            checksum ^= ord(char)

        # Return complete sentence with ! prefix and *checksum suffix
        return f"!{sentence}*{checksum:02X}"


class MongoDBHandler:
    """Handles MongoDB connection and data storage."""

    def __init__(self, connection_uri: str, collection: str = 'ais'):
        """
        Initialize MongoDB connection using a connection URI.

        Args:
            connection_uri: MongoDB connection URI (e.g., mongodb://user:pass@host:port/database)
            collection: Collection name for AIS data (default: 'ais')

        Examples:
            mongodb://localhost:27017/shipsim
            mongodb://user:pass@localhost:27017/shipsim?authSource=admin
            mongodb+srv://user:pass@cluster.mongodb.net/shipsim
        """
        if not PYMONGO_AVAILABLE:
            raise ImportError("pymongo is required for MongoDB support. Install with: pip install pymongo")

        self.connection_uri = connection_uri
        self.collection_name = collection

        try:
            self.client = MongoClient(connection_uri, serverSelectionTimeoutMS=5000)
            # Test connection
            self.client.admin.command('ping')

            # Extract database name from URI
            self.database_name = self.client.get_default_database().name
            self.db = self.client.get_default_database()
            self.collection = self.db[collection]

            print(f"✓ Connected to MongoDB database '{self.database_name}'", file=sys.stderr)

            # Create geospatial index on location field if it doesn't exist
            self._ensure_geospatial_index()

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {e}")
        except Exception as e:
            raise ConnectionError(f"Invalid MongoDB connection URI: {e}")

    def _ensure_geospatial_index(self):
        """Create a 2dsphere index on the location field for geospatial queries."""
        try:
            index_info = self.collection.index_information()
            if 'location_2dsphere' not in index_info:
                self.collection.create_index([("location", GEOSPHERE)], name="location_2dsphere")
                print(f"✓ Created geospatial index on {self.database_name}.{self.collection_name}.location",
                      file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not create geospatial index (continuing anyway): {e}", file=sys.stderr)
            # Continue without index - we can still insert data

    def insert_message(self, message: Dict[str, Any]) -> None:
        """
        Insert a single AIS message into MongoDB.

        Args:
            message: AIS message dictionary
        """
        self.collection.insert_one(message)

    def insert_messages(self, messages: List[Dict[str, Any]]) -> None:
        """
        Insert multiple AIS messages into MongoDB.

        Args:
            messages: List of AIS message dictionaries
        """
        if messages:
            self.collection.insert_many(messages)

    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()


class ConfigManager:
    """Manages simulator configuration stored in MongoDB."""

    DEFAULT_CONFIG = {
        'num_ships': 20,
        'interval': 10.0,
        'center_lat': 55.8,
        'center_lon': -5.0,
        'radius': 1.0,
        'bounding_poly_name': 'firth_of_clyde',
        'output_stdout': True
    }

    def __init__(self, db):
        """
        Initialize configuration manager.

        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.config_collection = db['config']

    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from MongoDB. Creates default config if none exists.

        Returns:
            Dictionary containing configuration settings
        """
        # Try to find existing config
        config = self.config_collection.find_one()

        if config is None:
            # Create default config
            print("ℹ No configuration found, creating default config...", file=sys.stderr)
            config = self.DEFAULT_CONFIG.copy()
            self.config_collection.insert_one(config)
            print("✓ Created default configuration in shipsim.config collection", file=sys.stderr)
        else:
            # Remove MongoDB _id field
            if '_id' in config:
                del config['_id']
            print("✓ Loaded configuration from shipsim.config collection", file=sys.stderr)

        return config

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration in MongoDB.

        Args:
            updates: Dictionary of configuration updates
        """
        self.config_collection.update_one({}, {'$set': updates}, upsert=True)
        print(f"✓ Updated configuration: {', '.join(updates.keys())}", file=sys.stderr)


class Ship:
    """Represents a ship with position, heading, and movement behavior."""

    # Navigation status text strings
    STATUS_UNDER_WAY = "under way using engine"
    STATUS_AT_ANCHOR = "at anchor"
    STATUS_NOT_UNDER_COMMAND = "not under command"
    STATUS_RESTRICTED_MANEUVERABILITY = "restricted maneuverability"
    STATUS_MOORED = "moored"

    # Stationary statuses - ships with these statuses should not move
    STATIONARY_STATUSES = {STATUS_AT_ANCHOR, STATUS_MOORED}

    def __init__(self, mmsi: int, name: str, lat: float, lon: float,
                 speed: float = None, heading: float = None):
        """
        Initialize a ship.

        Args:
            mmsi: Maritime Mobile Service Identity (unique 9-digit identifier)
            name: Ship name
            lat: Initial latitude (-90 to 90)
            lon: Initial longitude (-180 to 180)
            speed: Initial speed in knots (random if None)
            heading: Initial heading in degrees (random if None)
        """
        self.mmsi = mmsi
        self.name = name
        self.lat = lat
        self.lon = lon
        self.speed = speed if speed is not None else random.uniform(5, 15)
        self.heading = heading if heading is not None else random.uniform(0, 360)

        # Randomly assign status (90% under way, 10% stationary)
        if random.random() < 0.9:
            self.status = self.STATUS_UNDER_WAY
        else:
            self.status = random.choice([self.STATUS_AT_ANCHOR, self.STATUS_MOORED])
            self.speed = 0  # Stationary ships have zero speed

        # Movement parameters
        self.turn_rate = random.uniform(-3, 3)  # degrees per update
        self.speed_change = random.uniform(-0.5, 0.5)  # knots per update

    def update_position(self, time_delta: float = 10.0):
        """
        Update ship position based on current heading and speed.
        Stationary ships (anchored or moored) do not move.

        Args:
            time_delta: Time elapsed in seconds
        """
        # Skip movement for stationary ships
        if self.status in self.STATIONARY_STATUSES:
            self.speed = 0  # Ensure speed stays at zero
            return

        # Random walk: occasionally change heading and speed
        if random.random() < 0.1:  # 10% chance to change course
            self.turn_rate = random.uniform(-5, 5)

        if random.random() < 0.05:  # 5% chance to change speed
            self.speed_change = random.uniform(-1, 1)

        # Update heading (with random walk)
        self.heading += self.turn_rate * (time_delta / 10.0)
        self.heading = self.heading % 360

        # Update speed (with random walk, keep between 3 and 20 knots)
        self.speed += self.speed_change * (time_delta / 10.0)
        self.speed = max(3, min(20, self.speed))

        # Calculate distance traveled (in nautical miles)
        distance_nm = self.speed * (time_delta / 3600.0)

        # Convert to degrees (approximate)
        # 1 nautical mile = 1/60 degree of latitude
        # Longitude adjustment depends on latitude
        lat_change = distance_nm * math.cos(math.radians(self.heading)) / 60.0
        lon_change = distance_nm * math.sin(math.radians(self.heading)) / (60.0 * math.cos(math.radians(self.lat)))

        # Update position
        self.lat += lat_change
        self.lon += lon_change

        # Keep within reasonable bounds (-90 to 90 lat, -180 to 180 lon)
        self.lat = max(-85, min(85, self.lat))
        if self.lon > 180:
            self.lon -= 360
        elif self.lon < -180:
            self.lon += 360

    def get_ais_data(self) -> Dict[str, Any]:
        """
        Get current ship data in AIS format.

        Returns:
            Dictionary containing AIS message fields
        """
        return {
            'message_type': random.choice([1, 2, 3]),  # Position report types
            'mmsi': self.mmsi,
            'status': self.status,
            'speed': self.speed,
            'lon': self.lon,
            'lat': self.lat,
            'course': self.heading,  # Course over ground (simplified to heading)
            'heading': self.heading,  # True heading
            'timestamp': int(time.time()) % 60,  # Seconds within minute
        }


class ShipNameGenerator:
    """Generates realistic ship names with over 10,000 unique combinations."""

    # Container ship prefixes and patterns
    CONTAINER_PREFIXES = ['MSC', 'Maersk', 'Ever', 'COSCO', 'CMA CGM', 'Hapag-Lloyd', 'ONE',
                          'Yang Ming', 'PIL', 'ZIM', 'Wan Hai', 'Evergreen']

    # General cargo and bulk carrier patterns
    CARGO_PREFIXES = ['Atlantic', 'Pacific', 'Nordic', 'Celtic', 'Baltic', 'Mediterranean',
                      'Arctic', 'Antarctic', 'Tropical', 'Equatorial', 'Polar', 'Southern',
                      'Northern', 'Eastern', 'Western', 'Central', 'Global', 'World',
                      'Inter', 'Trans', 'Pan', 'Euro', 'Asian', 'African', 'American']

    # Tanker patterns
    TANKER_PREFIXES = ['Nordic', 'Celtic', 'Pacific', 'Atlantic', 'Arctic', 'Tropical',
                       'Baltic', 'Mediterranean', 'Aegean', 'Adriatic', 'Caribbean',
                       'Indian', 'Persian', 'Arabian', 'North Sea', 'Black Sea']
    TANKER_TYPES = ['Spirit', 'Champion', 'Voyager', 'Navigator', 'Pioneer', 'Explorer',
                    'Venture', 'Enterprise', 'Endeavor', 'Achievement', 'Progress',
                    'Prosperity', 'Fortune', 'Destiny', 'Legacy', 'Heritage']

    # General maritime words (greatly expanded)
    MARITIME_WORDS = ['Ocean', 'Sea', 'Wave', 'Wind', 'Storm', 'Horizon', 'Venture',
                      'Explorer', 'Trader', 'Voyager', 'Navigator', 'Discovery', 'Enterprise',
                      'Freedom', 'Liberty', 'Victory', 'Glory', 'Pride', 'Spirit', 'Star',
                      'Moon', 'Sun', 'Dawn', 'Dusk', 'Phoenix', 'Dragon', 'Eagle', 'Falcon',
                      'Hawk', 'Osprey', 'Albatross', 'Seagull', 'Pelican', 'Cormorant',
                      'Mariner', 'Seafarer', 'Sailor', 'Captain', 'Admiral', 'Skipper',
                      'Anchor', 'Compass', 'Helm', 'Beacon', 'Lighthouse', 'Harbor',
                      'Bay', 'Cove', 'Reef', 'Tide', 'Current', 'Drift', 'Flow',
                      'Breeze', 'Gale', 'Tempest', 'Squall', 'Thunder', 'Lightning',
                      'Rainbow', 'Sunset', 'Sunrise', 'Twilight', 'Midnight', 'Daybreak',
                      'Quest', 'Journey', 'Expedition', 'Passage', 'Crossing', 'Route',
                      'Path', 'Way', 'Trail', 'Course', 'Destiny', 'Fortune', 'Luck',
                      'Treasure', 'Pearl', 'Diamond', 'Sapphire', 'Emerald', 'Ruby',
                      'Gold', 'Silver', 'Bronze', 'Platinum', 'Crystal', 'Jewel',
                      'Crown', 'Scepter', 'Throne', 'Empire', 'Kingdom', 'Realm',
                      'Legend', 'Myth', 'Hero', 'Champion', 'Warrior', 'Guardian',
                      'Sentinel', 'Protector', 'Defender', 'Shield', 'Sword', 'Lance']

    # City and place names for ships (greatly expanded)
    PLACES = ['Rotterdam', 'Singapore', 'Hamburg', 'Shanghai', 'Busan', 'Antwerp',
              'Los Angeles', 'Tokyo', 'Hong Kong', 'Dubai', 'London', 'Bremen',
              'Yokohama', 'Qingdao', 'Kaohsiung', 'Valencia', 'Seattle', 'Boston',
              'New York', 'Miami', 'Houston', 'Baltimore', 'Oakland', 'Long Beach',
              'Vancouver', 'Montreal', 'Toronto', 'Halifax', 'Churchill', 'Sydney',
              'Melbourne', 'Brisbane', 'Perth', 'Adelaide', 'Auckland', 'Wellington',
              'Copenhagen', 'Oslo', 'Stockholm', 'Helsinki', 'Reykjavik', 'Dublin',
              'Edinburgh', 'Liverpool', 'Bristol', 'Plymouth', 'Southampton', 'Dover',
              'Marseille', 'Le Havre', 'Bordeaux', 'Genoa', 'Venice', 'Naples',
              'Barcelona', 'Bilbao', 'Lisbon', 'Porto', 'Athens', 'Piraeus',
              'Istanbul', 'Izmir', 'Haifa', 'Alexandria', 'Cairo', 'Casablanca',
              'Lagos', 'Durban', 'Cape Town', 'Mombasa', 'Mumbai', 'Kolkata',
              'Chennai', 'Karachi', 'Bangkok', 'Manila', 'Jakarta', 'Surabaya',
              'Ho Chi Minh', 'Hanoi', 'Seoul', 'Incheon', 'Taipei', 'Kobe',
              'Nagoya', 'Fukuoka', 'Vladivostok', 'St Petersburg', 'Murmansk']

    # Female names (traditional for ships) - expanded
    FEMALE_NAMES = ['Alexandra', 'Isabella', 'Victoria', 'Elizabeth', 'Catherine',
                    'Margaret', 'Eleanor', 'Caroline', 'Sophia', 'Charlotte', 'Aurora',
                    'Diana', 'Helena', 'Marina', 'Oceana', 'Stella', 'Luna',
                    'Anastasia', 'Beatrice', 'Cordelia', 'Delilah', 'Evangeline',
                    'Francesca', 'Gabriella', 'Henrietta', 'Juliana', 'Katerina',
                    'Leonora', 'Madeline', 'Natalia', 'Ophelia', 'Penelope',
                    'Rosalind', 'Seraphina', 'Tatiana', 'Valentina', 'Wilhelmina',
                    'Anastasia', 'Bianca', 'Cassandra', 'Desdemona', 'Esmeralda',
                    'Fiona', 'Gwendolyn', 'Hermione', 'Isadora', 'Josephine']

    # Numeric suffixes for additional variety
    ROMAN_NUMERALS = ['II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']
    NUMERIC_SUFFIXES = list(range(2, 21))  # 2 through 20

    # Directional words
    DIRECTIONS = ['Northern', 'Southern', 'Eastern', 'Western', 'North', 'South', 'East', 'West']

    # Compass points
    COMPASS_POINTS = ['Star', 'Cross', 'Wind', 'Light', 'Sky', 'Point', 'Marker', 'Guide']

    @staticmethod
    def _maybe_add_suffix(name: str) -> str:
        """Randomly add a numeric suffix to a ship name (20% chance)."""
        if random.random() < 0.2:  # 20% chance to add suffix
            if random.random() < 0.5:  # 50/50 between Roman and Arabic numerals
                return f"{name} {random.choice(ShipNameGenerator.ROMAN_NUMERALS)}"
            else:
                return f"{name} {random.choice(ShipNameGenerator.NUMERIC_SUFFIXES)}"
        return name

    @staticmethod
    def generate_name() -> str:
        """Generate a random realistic ship name from over 10,000 unique combinations."""
        # Define patterns with weights proportional to their pool sizes
        # This ensures larger pools contribute more names and reduces collision rate
        patterns_with_weights = [
            # Weight 1044: Container ship pattern "MSC Tokyo" (12 × 87)
            (lambda: f"{random.choice(ShipNameGenerator.CONTAINER_PREFIXES)} {random.choice(ShipNameGenerator.PLACES)}", 1044),

            # Weight 2700: Cargo pattern "Atlantic Trader" (25 × 108)
            (lambda: f"{random.choice(ShipNameGenerator.CARGO_PREFIXES)} {random.choice(ShipNameGenerator.MARITIME_WORDS)}", 2700),

            # Weight 256: Tanker pattern "Nordic Spirit" (16 × 16)
            (lambda: f"{random.choice(ShipNameGenerator.TANKER_PREFIXES)} {random.choice(ShipNameGenerator.TANKER_TYPES)}", 256),

            # Weight 432: Simple pattern "Sea Explorer" (4 × 108)
            (lambda: f"{random.choice(['Sea', 'Ocean', 'Pacific', 'Atlantic'])} {random.choice(ShipNameGenerator.MARITIME_WORDS)}", 432),

            # Weight 47: Female name pattern
            (lambda: random.choice(ShipNameGenerator.FEMALE_NAMES), 47),

            # Weight 87: City-based pattern "Pride of Rotterdam"
            (lambda: f"Pride of {random.choice(ShipNameGenerator.PLACES)}", 87),

            # Weight 9396: Word of Place "Spirit of Tokyo" (108 × 87)
            (lambda: f"{random.choice(ShipNameGenerator.MARITIME_WORDS)} of {random.choice(ShipNameGenerator.PLACES)}", 9396),

            # Weight 64: Compass pattern "Northern Star" (8 × 8)
            (lambda: f"{random.choice(ShipNameGenerator.DIRECTIONS)} {random.choice(ShipNameGenerator.COMPASS_POINTS)}", 64),

            # Weight 9396: Place + Word "Tokyo Venture" (87 × 108)
            (lambda: f"{random.choice(ShipNameGenerator.PLACES)} {random.choice(ShipNameGenerator.MARITIME_WORDS)}", 9396),
        ]

        # Extract patterns and weights
        patterns = [p[0] for p in patterns_with_weights]
        weights = [p[1] for p in patterns_with_weights]

        # Choose pattern with weighted probability
        base_name = random.choices(patterns, weights=weights, k=1)[0]()

        # Sometimes add numeric suffix to multiply combinations further
        return ShipNameGenerator._maybe_add_suffix(base_name)


class ShipSimulator:
    """Manages multiple ships and generates AIS data streams."""

    def __init__(self, num_ships: int = 20, center_lat: float = 37.8,
                 center_lon: float = -122.4, radius_nm: float = 50,
                 mongodb_handler: Optional[MongoDBHandler] = None):
        """
        Initialize the ship simulator.

        Args:
            num_ships: Number of ships to simulate
            center_lat: Center latitude for ship spawning
            center_lon: Center longitude for ship spawning
            radius_nm: Radius in nautical miles for ship spawning area
            mongodb_handler: Optional MongoDB handler for data storage
        """
        self.ships: List[Ship] = []
        self.encoder = AISEncoder()
        self.mongodb_handler = mongodb_handler

        # Generate ships with random positions around center point
        for i in range(num_ships):
            # Generate random MMSI (9 digits, typically starts with country code)
            mmsi = 366000000 + random.randint(1000, 999999)
            name = ShipNameGenerator.generate_name()

            # Random position within radius
            angle = random.uniform(0, 2 * math.pi)
            distance = random.uniform(0, radius_nm) / 60.0  # Convert to degrees

            lat = center_lat + distance * math.cos(angle)
            lon = center_lon + distance * math.sin(angle) / math.cos(math.radians(center_lat))

            ship = Ship(mmsi, name, lat, lon)
            self.ships.append(ship)

    def update_all_ships(self, time_delta: float = 10.0):
        """Update positions of all ships."""
        for ship in self.ships:
            ship.update_position(time_delta)

    def generate_ais_messages(self) -> List[Dict[str, Any]]:
        """
        Generate AIS messages for all ships.

        Returns:
            List of dictionaries containing AIS data with embedded NMEA sentences
        """
        messages = []

        for ship in self.ships:
            # Get ship AIS data
            ais_data = ship.get_ais_data()

            # Encode to NMEA
            payload = self.encoder.encode_position_report(ais_data)
            nmea_sentence = self.encoder.create_nmea_sentence(payload)

            # Create JSON message with decoded fields and embedded NMEA
            # GeoJSON format uses [longitude, latitude] order
            message = {
                'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'message_type': ais_data['message_type'],
                'mmsi': ais_data['mmsi'],
                'ship_name': ship.name,
                'location': {
                    'type': 'Point',
                    'coordinates': [round(ais_data['lon'], 6), round(ais_data['lat'], 6)]
                },
                'navigation': {
                    'status': ais_data['status'],
                    'speed_knots': round(ais_data['speed'], 1),
                    'course': round(ais_data['course'], 1),
                    'heading': round(ais_data['heading'], 1)
                },
                'nmea_sentence': nmea_sentence
            }

            messages.append(message)

        return messages

    def stream(self, interval: float = 10.0, duration: float = None, output_stdout: bool = True):
        """
        Generate continuous stream of AIS messages.

        Args:
            interval: Time between updates in seconds
            duration: Total duration in seconds (None for infinite)
            output_stdout: Whether to output messages to stdout
        """
        start_time = time.time()
        message_count = 0

        try:
            while True:
                # Update ship positions
                self.update_all_ships(interval)

                # Generate and output AIS messages
                messages = self.generate_ais_messages()

                # Store to MongoDB if handler is configured
                # Make deep copies to avoid _id field contaminating original messages
                if self.mongodb_handler:
                    try:
                        messages_for_db = copy.deepcopy(messages)
                        self.mongodb_handler.insert_messages(messages_for_db)
                        message_count += len(messages)
                    except Exception as e:
                        print(f"Error writing to MongoDB: {e}", file=sys.stderr)

                # Output to stdout if enabled
                if output_stdout:
                    for message in messages:
                        print(json.dumps(message))

                # Check duration
                if duration is not None and (time.time() - start_time) >= duration:
                    break

                # Wait for next interval
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\nSimulation stopped by user", file=sys.stderr)
        finally:
            if self.mongodb_handler and message_count > 0:
                print(f"✓ Stored {message_count} messages to MongoDB", file=sys.stderr)


def main():
    """Main entry point for the simulator."""
    import argparse

    parser = argparse.ArgumentParser(
        description='AIS Ship Movement Simulator - Configuration stored in MongoDB',
        epilog='All simulator settings (num_ships, interval, location, etc.) are stored in '
               'the shipsim.config collection in MongoDB. Edit that document to change settings.'
    )
    parser.add_argument(
        '--mongodb-uri',
        type=str,
        default=None,
        help='MongoDB connection URI (e.g., mongodb://user:pass@host:port/database). '
             'Can also be set via MONGODB_URI environment variable. REQUIRED.'
    )
    parser.add_argument(
        '--collection',
        type=str,
        default='ais',
        help='Collection name for AIS data (default: ais)'
    )
    parser.add_argument(
        '-d', '--duration',
        type=float,
        default=None,
        help='Simulation duration in seconds (default: infinite). '
             'Other settings loaded from MongoDB config collection.'
    )

    args = parser.parse_args()

    # Get MongoDB URI from argument or environment variable
    mongodb_uri = args.mongodb_uri or os.environ.get('MONGODB_URI')

    if not mongodb_uri:
        print("Error: MongoDB connection URI is required.", file=sys.stderr)
        print("Provide it via --mongodb-uri argument or MONGODB_URI environment variable.", file=sys.stderr)
        print("", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  Local:  mongodb://localhost:27017/shipsim", file=sys.stderr)
        print("  Auth:   mongodb://user:pass@localhost:27017/shipsim?authSource=admin", file=sys.stderr)
        print("  Atlas:  mongodb+srv://user:pass@cluster.mongodb.net/shipsim", file=sys.stderr)
        sys.exit(1)

    # Connect to MongoDB
    try:
        mongodb_handler = MongoDBHandler(mongodb_uri, collection=args.collection)
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}", file=sys.stderr)
        sys.exit(1)

    # Load configuration from MongoDB
    try:
        config_manager = ConfigManager(mongodb_handler.db)
        config = config_manager.load_config()
    except Exception as e:
        print(f"Failed to load configuration: {e}", file=sys.stderr)
        mongodb_handler.close()
        sys.exit(1)

    # Display configuration
    print("-" * 80, file=sys.stderr)
    print(f"Starting AIS Ship Simulator with {config['num_ships']} ships...", file=sys.stderr)
    print(f"Center: ({config['center_lat']}, {config['center_lon']}), Radius: {config['radius']} nm", file=sys.stderr)
    print(f"Update interval: {config['interval']}s", file=sys.stderr)
    print(f"Bounding polygon: {config.get('bounding_poly_name', 'none')}", file=sys.stderr)
    print(f"MongoDB: {mongodb_handler.database_name}.{mongodb_handler.collection_name}", file=sys.stderr)
    print("-" * 80, file=sys.stderr)

    # Create and run simulator
    simulator = ShipSimulator(
        num_ships=config['num_ships'],
        center_lat=config['center_lat'],
        center_lon=config['center_lon'],
        radius_nm=config['radius'],
        mongodb_handler=mongodb_handler
    )

    try:
        simulator.stream(
            interval=config['interval'],
            duration=args.duration,
            output_stdout=config.get('output_stdout', True)
        )
    finally:
        mongodb_handler.close()


if __name__ == '__main__':
    main()
