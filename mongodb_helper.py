"""
MongoDB helper for Expansion War game

This module provides helper functions for MongoDB operations.
"""

import pymongo
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime

class MongoDBHelper:
    def __init__(self, host='localhost', port=27017, db_name='expansion_war'):
        """Initialize MongoDB connection"""
        self.client = MongoClient(f'mongodb://{host}:{port}/')
        self.db = self.client[db_name]
        self.saved_games = self.db['saved_games']
        
    def save_game(self, game_state, game_name):
        """Save game state to MongoDB"""
        # Add game name and timestamp if not present
        if 'game_name' not in game_state:
            game_state['game_name'] = game_name
            
        if 'metadata' not in game_state:
            game_state['metadata'] = {}
            
        if 'saved_at' not in game_state['metadata']:
            game_state['metadata']['saved_at'] = datetime.now().isoformat()
            
        # Insert the document
        result = self.saved_games.insert_one(game_state)
        return result.inserted_id
        
    def load_game(self, game_id):
        """Load game state from MongoDB by ID"""
        # Convert string ID to ObjectId if needed
        if isinstance(game_id, str):
            game_id = ObjectId(game_id)
            
        # Fetch game state
        return self.saved_games.find_one({"_id": game_id})
        
    def get_saved_games(self):
        """Get list of all saved games"""
        return list(self.saved_games.find({}, {
            "game_name": 1,
            "metadata.saved_at": 1
        }))
        
    def delete_game(self, game_id):
        """Delete a saved game"""
        # Convert string ID to ObjectId if needed
        if isinstance(game_id, str):
            game_id = ObjectId(game_id)
            
        # Delete the document
        result = self.saved_games.delete_one({"_id": game_id})
        return result.deleted_count > 0
