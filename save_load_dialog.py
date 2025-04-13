from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QRadioButton, QPushButton, QGroupBox, QButtonGroup, 
                            QFileDialog, QMessageBox, QComboBox, QFormLayout,
                            QLineEdit, QApplication, QListWidget, QListWidgetItem)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon

class SaveGameDialog(QDialog):
    def __init__(self, parent=None, mongodb_available=False):
        super().__init__(parent)
        self.setWindowTitle("Save Game")
        self.setMinimumWidth(400)
        self.setMinimumHeight(200)
        
        self.format_type = "json"  # Default format
        self.filepath = ""
        self.use_mongodb = False
        self.mongodb_connection_string = "mongodb://localhost:27017/"
        self.mongodb_available = mongodb_available
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Format selection
        format_group = QGroupBox("Format")
        format_layout = QVBoxLayout()
        self.format_group = QButtonGroup(self)
        
        self.json_radio = QRadioButton("JSON")
        self.xml_radio = QRadioButton("XML")
        self.mongodb_radio = QRadioButton("MongoDB")
        
        self.json_radio.setChecked(True)
        self.mongodb_radio.setEnabled(self.mongodb_available)
        
        self.format_group.addButton(self.json_radio, 0)
        self.format_group.addButton(self.xml_radio, 1)
        self.format_group.addButton(self.mongodb_radio, 2)
        
        format_layout.addWidget(self.json_radio)
        format_layout.addWidget(self.xml_radio)
        format_layout.addWidget(self.mongodb_radio)
        
        self.format_group.buttonClicked.connect(self.on_format_changed)
        format_group.setLayout(format_layout)
        main_layout.addWidget(format_group)
        
        # MongoDB settings
        self.mongodb_group = QGroupBox("MongoDB Settings")
        self.mongodb_group.setEnabled(False)
        mongodb_layout = QFormLayout()
        
        self.mongo_conn_input = QLineEdit(self.mongodb_connection_string)
        mongodb_layout.addRow("Connection String:", self.mongo_conn_input)
        
        self.mongodb_group.setLayout(mongodb_layout)
        main_layout.addWidget(self.mongodb_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_cancel = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_save.clicked.connect(self.save_game)
        self.btn_cancel.clicked.connect(self.reject)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def on_format_changed(self, button):
        if button == self.mongodb_radio:
            self.mongodb_group.setEnabled(True)
            self.use_mongodb = True
        else:
            self.mongodb_group.setEnabled(False)
            self.use_mongodb = False
            
        if button == self.json_radio:
            self.format_type = "json"
        elif button == self.xml_radio:
            self.format_type = "xml"
        else:
            self.format_type = "mongodb"
    
    def save_game(self):
        if self.use_mongodb:
            self.mongodb_connection_string = self.mongo_conn_input.text()
            self.accept()
        else:
            # Get file path
            if self.format_type == "json":
                self.filepath, _ = QFileDialog.getSaveFileName(
                    self, "Save Game", "", "JSON Files (*.json)")
            else:  # XML
                self.filepath, _ = QFileDialog.getSaveFileName(
                    self, "Save Game", "", "XML Files (*.xml)")
                
            if self.filepath:
                self.accept()
    
    def get_save_info(self):
        return {
            "format": self.format_type,
            "filepath": self.filepath,
            "use_mongodb": self.use_mongodb,
            "mongodb_connection_string": self.mongodb_connection_string
        }

class LoadGameDialog(QDialog):
    def __init__(self, parent=None, mongodb_available=False, saved_games=None):
        super().__init__(parent)
        self.setWindowTitle("Load Game")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        self.format_type = "json"  # Default format
        self.filepath = ""
        self.use_mongodb = False
        self.mongodb_connection_string = "mongodb://localhost:27017/"
        self.mongodb_available = mongodb_available
        self.saved_games = saved_games or []
        self.selected_game_id = None
        
        self.setup_ui()
        
    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Format selection
        format_group = QGroupBox("Format")
        format_layout = QVBoxLayout()
        self.format_group = QButtonGroup(self)
        
        self.json_radio = QRadioButton("JSON")
        self.xml_radio = QRadioButton("XML")
        self.mongodb_radio = QRadioButton("MongoDB")
        
        self.json_radio.setChecked(True)
        self.mongodb_radio.setEnabled(self.mongodb_available)
        
        self.format_group.addButton(self.json_radio, 0)
        self.format_group.addButton(self.xml_radio, 1)
        self.format_group.addButton(self.mongodb_radio, 2)
        
        format_layout.addWidget(self.json_radio)
        format_layout.addWidget(self.xml_radio)
        format_layout.addWidget(self.mongodb_radio)
        
        self.format_group.buttonClicked.connect(self.on_format_changed)
        format_group.setLayout(format_layout)
        main_layout.addWidget(format_group)
        
        # MongoDB settings
        self.mongodb_group = QGroupBox("MongoDB Settings")
        self.mongodb_group.setEnabled(False)
        mongodb_layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        self.mongo_conn_input = QLineEdit(self.mongodb_connection_string)
        form_layout.addRow("Connection String:", self.mongo_conn_input)
        mongodb_layout.addLayout(form_layout)
        
        # Saved games list
        saved_games_label = QLabel("Saved Games:")
        mongodb_layout.addWidget(saved_games_label)
        
        self.saved_games_list = QListWidget()
        self.saved_games_list.setMinimumHeight(150)
        mongodb_layout.addWidget(self.saved_games_list)
        
        # Add saved games to list
        for game in self.saved_games:
            item = QListWidgetItem(f"{game['saved_at']} - Level {game['level']}")
            item.setData(Qt.UserRole, game['id'])
            self.saved_games_list.addItem(item)
        
        # Connect button
        self.btn_connect = QPushButton("Connect to MongoDB")
        self.btn_connect.clicked.connect(self.connect_mongodb)
        mongodb_layout.addWidget(self.btn_connect)
        
        self.mongodb_group.setLayout(mongodb_layout)
        main_layout.addWidget(self.mongodb_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load")
        self.btn_cancel = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.btn_load)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_load.clicked.connect(self.load_game)
        self.btn_cancel.clicked.connect(self.reject)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def on_format_changed(self, button):
        if button == self.mongodb_radio:
            self.mongodb_group.setEnabled(True)
            self.use_mongodb = True
        else:
            self.mongodb_group.setEnabled(False)
            self.use_mongodb = False
            
        if button == self.json_radio:
            self.format_type = "json"
        elif button == self.xml_radio:
            self.format_type = "xml"
        else:
            self.format_type = "mongodb"
    
    def connect_mongodb(self):
        # This just updates the UI, actual connection happens in the parent window
        self.mongodb_connection_string = self.mongo_conn_input.text()
        self.parent().connect_to_mongodb(self.mongodb_connection_string)
        
        # Update saved games list
        self.saved_games_list.clear()
        for game in self.parent().mongodb_saved_games:
            item = QListWidgetItem(f"{game['saved_at']} - Level {game['level']}")
            item.setData(Qt.UserRole, game['id'])
            self.saved_games_list.addItem(item)
    
    def load_game(self):
        if self.use_mongodb:
            # Get selected game ID
            selected_items = self.saved_games_list.selectedItems()
            if not selected_items:
                QMessageBox.warning(self, "No Selection", "Please select a saved game from the list.")
                return
                
            self.selected_game_id = selected_items[0].data(Qt.UserRole)
            self.mongodb_connection_string = self.mongo_conn_input.text()
            self.accept()
        else:
            # Get file path
            if self.format_type == "json":
                self.filepath, _ = QFileDialog.getOpenFileName(
                    self, "Load Game", "", "JSON Files (*.json)")
            else:  # XML
                self.filepath, _ = QFileDialog.getOpenFileName(
                    self, "Load Game", "", "XML Files (*.xml)")
                
            if self.filepath:
                self.accept()
    
    def get_load_info(self):
        return {
            "format": self.format_type,
            "filepath": self.filepath,
            "use_mongodb": self.use_mongodb,
            "mongodb_connection_string": self.mongodb_connection_string,
            "game_id": self.selected_game_id
        }
