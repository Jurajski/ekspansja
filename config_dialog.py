from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                            QRadioButton, QPushButton, QGroupBox, QButtonGroup, 
                            QSpinBox, QFormLayout)
from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Configuration")
        self.setMinimumWidth(500)
        self.setMinimumHeight(350)
        
        self.game_modes = ["Single Player", "Two Players Local", "Network Game"]
        self.selected_mode = self.game_modes[0]
        self.ip_address = "127.0.0.1"
        self.port = 5000
        self.network_role = "server"  # Default to server role
        
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
        network_layout = QVBoxLayout()
        
        # Network role selection (server/client)
        role_layout = QHBoxLayout()
        self.role_group = QButtonGroup(self)
        
        self.server_radio = QRadioButton("Server (Host Game)")
        self.client_radio = QRadioButton("Client (Join Game)")
        self.server_radio.setChecked(True)
        
        self.role_group.addButton(self.server_radio, 0)
        self.role_group.addButton(self.client_radio, 1)
        
        role_layout.addWidget(self.server_radio)
        role_layout.addWidget(self.client_radio)
        role_layout.addStretch()
        
        self.role_group.buttonClicked.connect(self.on_role_changed)
        network_layout.addLayout(role_layout)
        
        # Connection settings
        form_layout = QFormLayout()
        
        # IP Address with validation
        self.ip_input = QLineEdit(self.ip_address)
        ip_regex = QRegExp(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
        self.ip_input.setValidator(QRegExpValidator(ip_regex))
        self.ip_input.setPlaceholderText("Enter IP address (e.g. 192.168.1.1)")
        form_layout.addRow("IP Address:", self.ip_input)
        
        # Server info label
        self.server_info = QLabel("As server, other players will connect to your IP address")
        self.server_info.setStyleSheet("color: gray; font-style: italic;")
        form_layout.addRow("", self.server_info)
        
        # Port with validation
        self.port_input = QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(self.port)
        self.port_input.setToolTip("Port range: 1024-65535")
        form_layout.addRow("Port:", self.port_input)
        
        network_layout.addLayout(form_layout)
        
        self.network_group.setLayout(network_layout)
        main_layout.addWidget(self.network_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_cancel = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.btn_ok)
        button_layout.addWidget(self.btn_cancel)
        
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def on_mode_changed(self, button):
        mode_idx = self.mode_group.id(button)
        self.selected_mode = self.game_modes[mode_idx]
        
        # Enable network settings only for network game
        self.network_group.setEnabled(mode_idx == 2)
    
    def on_role_changed(self, button):
        if button == self.server_radio:
            self.network_role = "server"
            self.server_info.setText("As server, other players will connect to your IP address")
            self.ip_input.setPlaceholderText("Your IP address (e.g. 192.168.1.1)")
        else:
            self.network_role = "client"
            self.server_info.setText("Enter the IP address of the server you want to connect to")
            self.ip_input.setPlaceholderText("Server IP address (e.g. 192.168.1.1)")
    
    def get_config(self):
        return {
            "game_mode": self.selected_mode,
            "ip_address": self.ip_input.text(),
            "port": self.port_input.value(),
            "network_role": self.network_role
        }
