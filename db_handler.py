import json
import xml.dom.minidom
import xml.etree.ElementTree as ET
from datetime import datetime
try:
    import pymongo
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False

class DatabaseHandler:
    def __init__(self):
        self.mongodb_client = None
        self.mongodb_db = None
        self.connected = False
        
    def connect_mongodb(self, connection_string="mongodb://localhost:27017/", db_name="expansionwar"):
        """Connect to MongoDB database"""
        if not MONGODB_AVAILABLE:
            return False, "PyMongo not installed. Install with: pip install pymongo"
        
        try:
            self.mongodb_client = pymongo.MongoClient(connection_string, serverSelectionTimeoutMS=5000)
            # Check connection
            self.mongodb_client.server_info()
            self.mongodb_db = self.mongodb_client[db_name]
            self.connected = True
            return True, "Connected to MongoDB"
        except Exception as e:
            self.connected = False
            return False, f"Failed to connect to MongoDB: {str(e)}"
    
    def save_to_mongodb(self, game_state, collection_name="game_states"):
        """Save game state to MongoDB"""
        if not self.connected:
            return False, "Not connected to MongoDB. Connect first."
        
        try:
            # Add timestamp
            game_state["saved_at"] = datetime.now()
            
            # Save to MongoDB
            collection = self.mongodb_db[collection_name]
            result = collection.insert_one(game_state)
            
            return True, f"Saved game state with ID: {result.inserted_id}"
        except Exception as e:
            return False, f"Failed to save to MongoDB: {str(e)}"
    
    def load_from_mongodb(self, game_id=None, collection_name="game_states"):
        """Load game state from MongoDB"""
        if not self.connected:
            return False, "Not connected to MongoDB. Connect first.", None
        
        try:
            collection = self.mongodb_db[collection_name]
            
            if game_id:
                # Load specific game
                if isinstance(game_id, str):
                    # Convert string ID to ObjectId
                    from bson.objectid import ObjectId
                    game_id = ObjectId(game_id)
                    
                game_state = collection.find_one({"_id": game_id})
                if not game_state:
                    return False, f"Game state with ID {game_id} not found.", None
            else:
                # Load most recent game
                game_state = collection.find_one(sort=[("saved_at", pymongo.DESCENDING)])
                if not game_state:
                    return False, "No saved games found.", None
            
            # Convert ObjectId to string for JSON serialization
            game_state["_id"] = str(game_state["_id"])
            
            return True, "Loaded game state successfully.", game_state
        except Exception as e:
            return False, f"Failed to load from MongoDB: {str(e)}", None
    
    def get_saved_games(self, collection_name="game_states"):
        """Get list of saved games"""
        if not self.connected:
            return False, "Not connected to MongoDB. Connect first.", None
        
        try:
            collection = self.mongodb_db[collection_name]
            games = collection.find({}, {"saved_at": 1, "level": 1, "player_units": 1, "pc_units": 1})
            
            # Convert to list and format for display
            games_list = []
            for game in games:
                games_list.append({
                    "id": str(game["_id"]),
                    "saved_at": game["saved_at"],
                    "level": game.get("level", "Unknown"),
                    "player_units": game.get("player_units", 0),
                    "pc_units": game.get("pc_units", 0)
                })
            
            return True, "Retrieved saved games successfully.", games_list
        except Exception as e:
            return False, f"Failed to get saved games: {str(e)}", None
    
    def save_to_json_file(self, game_state, filepath):
        """Save game state to JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(game_state, f, indent=2, default=str)
            return True, f"Game state saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save to JSON file: {str(e)}"
    
    def load_from_json_file(self, filepath):
        """Load game state from JSON file"""
        try:
            with open(filepath, 'r') as f:
                game_state = json.load(f)
            return True, "Loaded game state successfully.", game_state
        except Exception as e:
            return False, f"Failed to load from JSON file: {str(e)}", None
    
    def save_to_xml_file(self, game_state, filepath):
        """Save game state to XML file"""
        try:
            # Create XML structure
            root = ET.Element("game_state")
            
            # Add metadata
            metadata = ET.SubElement(root, "metadata")
            ET.SubElement(metadata, "saved_at").text = str(datetime.now())
            ET.SubElement(metadata, "level").text = str(game_state.get("level", 0))
            
            # Add configuration
            config = ET.SubElement(root, "configuration")
            ET.SubElement(config, "game_mode").text = game_state.get("game_mode", "Single Player")
            
            # Add current state
            current_state = ET.SubElement(root, "current_state")
            ET.SubElement(current_state, "current_turn").text = game_state.get("current_turn", "player")
            
            # Add units
            units_elem = ET.SubElement(current_state, "units")
            for unit in game_state.get("units", []):
                unit_elem = ET.SubElement(units_elem, "unit")
                
                # Add unit properties
                for key, value in unit.items():
                    if key == "connections":
                        connections_elem = ET.SubElement(unit_elem, "connections")
                        for conn_id in value:
                            conn_elem = ET.SubElement(connections_elem, "connection")
                            ET.SubElement(conn_elem, "target_id").text = str(conn_id)
                    else:
                        ET.SubElement(unit_elem, key).text = str(value)
            
            # Create pretty XML
            xml_string = ET.tostring(root, encoding='unicode')
            dom = xml.dom.minidom.parseString(xml_string)
            pretty_xml = dom.toprettyxml(indent="  ")
            
            # Write to file
            with open(filepath, 'w') as f:
                f.write(pretty_xml)
                
            return True, f"Game state saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save to XML file: {str(e)}"
    
    def load_from_xml_file(self, filepath):
        """Load game state from XML file"""
        try:
            # Parse XML file
            tree = ET.parse(filepath)
            root = tree.getroot()
            
            # Create game state dictionary
            game_state = {
                "saved_at": root.find("./metadata/saved_at").text,
                "level": int(root.find("./metadata/level").text),
                "game_mode": root.find("./configuration/game_mode").text,
                "current_turn": root.find("./current_state/current_turn").text,
                "units": []
            }
            
            # Extract units
            for unit_elem in root.findall("./current_state/units/unit"):
                unit = {}
                
                # Get all unit properties
                for child in unit_elem:
                    if child.tag == "connections":
                        # Handle connections separately
                        unit["connections"] = []
                        for conn in child.findall("connection"):
                            unit["connections"].append(int(conn.find("target_id").text))
                    else:
                        # Try to convert to appropriate type
                        text = child.text
                        try:
                            # Try to convert to number if possible
                            if "." in text:
                                unit[child.tag] = float(text)
                            else:
                                unit[child.tag] = int(text)
                        except (ValueError, TypeError):
                            # Keep as string if conversion fails
                            unit[child.tag] = text
                
                game_state["units"].append(unit)
            
            return True, "Loaded game state successfully.", game_state
        except Exception as e:
            return False, f"Failed to load from XML file: {str(e)}", None
