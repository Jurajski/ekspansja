from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                            QRadioButton, QPushButton, QGroupBox, QButtonGroup, 
                            QSpinBox, QFormLayout, QSlider, QComboBox, QFileDialog, 
                            QMessageBox)
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator, QIntValidator
import json
import xml.etree.ElementTree as ET
import os
from pymongo import MongoClient
import datetime

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Configuration")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        
        self.game_modes = ["Single Player", "Two Players Local", "Network Game"]
        self.selected_mode = self.game_modes[0]
        self.ip_address = "127.0.0.1"
        self.port = 5000
        
        # MongoDB connection (modify as needed)
        self.mongo_client = None
        try:
            self.mongo_client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
            self.mongo_client.server_info()  # Will throw an exception if cannot connect
            self.db = self.mongo_client["expansion_war"]
            self.collection = self.db["game_history"]
            print("MongoDB connection successful")
        except Exception as e:
            self.mongo_client = None
            print(f"MongoDB connection failed: {str(e)}")
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Game mode selection
        mode_group = QGroupBox("Game Mode")
        mode_layout = QVBoxLayout()
        self.mode_group = QButtonGroup(self)
        
        for i, mode in enumerate(self.game_modes):
            radio = QRadioButton(mode)
            if i == 0:
                radio.setChecked(True)
            self.mode_group.addButton(radio, i)
            mode_layout.addWidget(radio)
            
        self.mode_group.buttonClicked.connect(self.on_mode_changed)
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)
        
        # Network settings
        self.network_group = QGroupBox("Network Settings")
        self.network_group.setEnabled(False)
        network_layout = QFormLayout()
        
        # IP Address with validation
        self.ip_input = QLineEdit(self.ip_address)
        ip_regex = QRegExp(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
        self.ip_input.setValidator(QRegExpValidator(ip_regex))
        self.ip_input.setPlaceholderText("Enter IP address (e.g. 192.168.1.1)")
        network_layout.addRow("IP Address:", self.ip_input)
        
        # Port with validation
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(self.port)
        self.port_input.setToolTip("Port range: 1024-65535")
        network_layout.addRow("Port:", self.port_input)
        
        self.network_group.setLayout(network_layout)
        main_layout.addWidget(self.network_group)
        
        # Game history management
        history_group = QGroupBox("Game History")
        history_layout = QVBoxLayout()
        
        save_load_layout = QHBoxLayout()
        
        # Save buttons
        self.btn_save_xml = QPushButton("Save to XML")
        self.btn_save_json = QPushButton("Save to JSON")
        self.btn_save_db = QPushButton("Save to Database")
        save_load_layout.addWidget(self.btn_save_xml)
        save_load_layout.addWidget(self.btn_save_json)
        save_load_layout.addWidget(self.btn_save_db)
        
        # Load buttons
        load_layout = QHBoxLayout()
        self.btn_load_xml = QPushButton("Load from XML")
        self.btn_load_json = QPushButton("Load from JSON")
        self.btn_load_db = QPushButton("Load from Database")
        load_layout.addWidget(self.btn_load_xml)
        load_layout.addWidget(self.btn_load_json)
        load_layout.addWidget(self.btn_load_db)
        
        history_layout.addLayout(save_load_layout)
        history_layout.addLayout(load_layout)
        
        # Playback controls
        playback_layout = QHBoxLayout()
        self.btn_playback = QPushButton("Start Playback")
        self.playback_speed = QComboBox()
        self.playback_speed.addItems(["0.5x", "1.0x", "1.5x", "2.0x"])
        self.playback_speed.setCurrentIndex(1)
        playback_layout.addWidget(self.btn_playback)
        playback_layout.addWidget(QLabel("Speed:"))
        playback_layout.addWidget(self.playback_speed)
        
        history_layout.addLayout(playback_layout)
        history_group.setLayout(history_layout)
        main_layout.addWidget(history_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.btn_ok)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Connect history buttons
        self.btn_save_xml.clicked.connect(self.save_history_xml)
        self.btn_save_json.clicked.connect(self.save_history_json)
        self.btn_save_db.clicked.connect(self.save_history_db)
        self.btn_load_xml.clicked.connect(self.load_history_xml)
        self.btn_load_json.clicked.connect(self.load_history_json)
        self.btn_load_db.clicked.connect(self.load_history_db)
        self.btn_playback.clicked.connect(self.start_playback)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
        # If MongoDB is not available, disable database buttons
        if not self.mongo_client:
            self.btn_save_db.setEnabled(False)
            self.btn_load_db.setEnabled(False)
            self.btn_save_db.setToolTip("MongoDB connection not available")
            self.btn_load_db.setToolTip("MongoDB connection not available")
    
    def on_mode_changed(self, button):
        mode_idx = self.mode_group.id(button)
        self.selected_mode = self.game_modes[mode_idx]
        
        # Enable network settings only for network game
        self.network_group.setEnabled(mode_idx == 2)
    
    def get_config(self):
        return {
            "game_mode": self.selected_mode,
            "ip_address": self.ip_input.text(),
            "port": self.port_input.value()
        }
        
    def save_history_xml(self):
        if not hasattr(self.parent(), 'game_history') or not self.parent().game_history:
            QMessageBox.information(self, "No History", "No game history available to save.")
            return
            
        filename, _ = QFileDialog.getSaveFileName(self, "Save Game History", "", "XML Files (*.xml)")
        if not filename:
            return
            
        if not filename.endswith('.xml'):
            filename += '.xml'
            
        try:
            root = ET.Element("game_history")
            
            # Game configuration
            config = ET.SubElement(root, "configuration")
            ET.SubElement(config, "game_mode").text = self.selected_mode
            ET.SubElement(config, "timestamp").text = datetime.datetime.now().isoformat()
            
            # Add network settings if network mode
            if self.selected_mode == "Network Game":
                network_config = ET.SubElement(config, "network_settings")
                ET.SubElement(network_config, "ip_address").text = self.ip_input.text()
                ET.SubElement(network_config, "port").text = str(self.port_input.value())
            
            # Game moves
            moves = ET.SubElement(root, "moves")
            for move in self.parent().game_history:
                move_elem = ET.SubElement(moves, "move")
                for key, value in move.items():
                    ET.SubElement(move_elem, key).text = str(value)
            
            # Save to file
            tree = ET.ElementTree(root)
            tree.write(filename)
            QMessageBox.information(self, "Success", f"Game history saved to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save XML file: {str(e)}")
    
    def save_history_json(self):
        if not hasattr(self.parent(), 'game_history') or not self.parent().game_history:
            QMessageBox.information(self, "No History", "No game history available to save.")
            return
            
        filename, _ = QFileDialog.getSaveFileName(self, "Save Game History", "", "JSON Files (*.json)")
        if not filename:
            return
            
        if not filename.endswith('.json'):
            filename += '.json'
            
        try:
            config = {
                "game_mode": self.selected_mode,
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            # Add network settings if network mode
            if self.selected_mode == "Network Game":
                config["network_settings"] = {
                    "ip_address": self.ip_input.text(),
                    "port": self.port_input.value()
                }
                
            data = {
                "configuration": config,
                "moves": self.parent().game_history
            }
            
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
                
            QMessageBox.information(self, "Success", f"Game history saved to {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save JSON file: {str(e)}")
    
    def save_history_db(self):
        if not self.mongo_client:
            error_msg = "MongoDB connection not available. Make sure MongoDB server is running on localhost:27017."
            QMessageBox.critical(self, "Error", error_msg)
            return
            
        if not hasattr(self.parent(), 'game_history') or not self.parent().game_history:
            QMessageBox.information(self, "No History", "No game history available to save.")
            return
            
        try:
            config = {
                "game_mode": self.selected_mode,
                "timestamp": datetime.datetime.now()
            }
            
            # Add network settings if network mode
            if self.selected_mode == "Network Game":
                config["network_settings"] = {
                    "ip_address": self.ip_input.text(),
                    "port": self.port_input.value()
                }
                
            data = {
                "configuration": config,
                "moves": self.parent().game_history
            }
            
            result = self.collection.insert_one(data)
            QMessageBox.information(self, "Success", f"Game history saved to database (ID: {result.inserted_id})")
        except Exception as e:
            error_details = str(e)
            print(f"MongoDB save error: {error_details}")
            QMessageBox.critical(self, "Error", f"Failed to save to database: {error_details}")
    
    def load_history_xml(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Game History", "", "XML Files (*.xml)")
        if not filename:
            return
            
        try:
            tree = ET.parse(filename)
            root = tree.getroot()
            
            game_history = []
            for move_elem in root.findall("./moves/move"):
                move = {}
                for child in move_elem:
                    # Handle numeric values specifically
                    if child.tag in ["from_id", "to_id", "unit_id", "value_change", "old_value", "new_value"]:
                        try:
                            # Try to convert to appropriate type
                            move[child.tag] = float(child.text) if '.' in child.text else int(child.text)
                        except (ValueError, TypeError):
                            move[child.tag] = child.text
                    else:
                        # Handle boolean values
                        if child.tag == "owner_change" and child.text.lower() == "true":
                            move[child.tag] = True
                        elif child.tag == "owner_change" and child.text.lower() == "false":
                            move[child.tag] = False
                        else:
                            move[child.tag] = child.text
                game_history.append(move)
            
            if game_history:
                QMessageBox.information(self, "Loading Game History", 
                                   f"Found {len(game_history)} moves in the XML file. Press OK to start loading.")
                self.parent().load_game_history(game_history)
                QMessageBox.information(self, "Success", f"Game history loaded with {len(game_history)} moves")
            else:
                QMessageBox.warning(self, "Warning", "No moves found in the XML file")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load XML file: {str(e)}")
            import traceback
            traceback.print_exc()  # Print detailed error to console
    
    def load_history_json(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load Game History", "", "JSON Files (*.json)")
        if not filename:
            return
            
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
            game_history = data.get("moves", [])
            if game_history:
                self.parent().load_game_history(game_history)
                QMessageBox.information(self, "Success", f"Game history loaded from {filename}")
            else:
                QMessageBox.warning(self, "Warning", "No moves found in the JSON file")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load JSON file: {str(e)}")
    
    def load_history_db(self):
        if not self.mongo_client:
            QMessageBox.critical(self, "Error", "MongoDB connection not available")
            return
            
        try:
            # Get the latest game history
            latest_game = self.collection.find_one(sort=[("configuration.timestamp", -1)])
            if latest_game:
                game_history = latest_game.get("moves", [])
                if game_history:
                    self.parent().load_game_history(game_history)
                    QMessageBox.information(self, "Success", "Game history loaded from database")
                else:
                    QMessageBox.warning(self, "Warning", "No moves found in the database record")
            else:
                QMessageBox.information(self, "No Data", "No game history found in the database")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load from database: {str(e)}")
    
    def start_playback(self):
        if hasattr(self.parent(), 'start_playback'):
            speed_text = self.playback_speed.currentText()
            speed = float(speed_text.replace('x', ''))
            self.parent().start_playback(speed)
            self.accept()
        else:
            QMessageBox.warning(self, "Not Implemented", "Playback functionality not available")
