from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
                           QPushButton, QLabel, QDialogButtonBox, QSizePolicy)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class FileViewerDialog(QDialog):
    def __init__(self, parent, title, content):
        super().__init__(parent)
        
        self.setWindowTitle(title)
        self.setMinimumSize(700, 500)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Add text area for file content
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Courier New", 10))
        self.text_edit.setText(content)
        layout.addWidget(self.text_edit)
        
        # Add button box
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(button_box)
        layout.addLayout(button_layout)
        
        # Set dialog properties
        self.setLayout(layout)