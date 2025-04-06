from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem, QPushButton, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QAction, QMessageBox, QSizePolicy, QProgressBar, QFileDialog
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF, QTimer
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter, QFont, QPixmap, QIcon
import os
import sys
import json
import xml.dom.minidom
from PyQt5 import QtCore
import resources_rc
from config_dialog import ConfigDialog
from game_history import GameHistoryRecorder
from file_viewer import FileViewerDialog

class ConnectionLine(QGraphicsLineItem):
    def __init__(self, start_pos):
        super().__init__()
        self.setLine(QLineF(start_pos, start_pos))
        self.setPen(QPen(Qt.darkGray, 1, Qt.DashLine))
        
class Unit(QGraphicsItem):
    def __init__(self, x, y, size=40, owner="player"):
        super().__init__()
        
        self.size = size
        self.owner = owner
        
        if owner == "player":
            self.pixmap = QPixmap(":/images/grafika/green.bmp")
            self.color = QColor(50, 200, 50)
        elif owner == "pc":
            self.pixmap = QPixmap(":/images/grafika/red.bmp")
            self.color = QColor(200, 50, 50)
        else:
            self.pixmap = QPixmap(":/images/grafika/grey.bmp")
            self.color = QColor(150, 150, 150)
        
        if not self.pixmap.isNull():
            self.pixmap = self.pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
        self.connections = []
        self.dragging_connection = False
        self.deleting_connection = False
        self.temp_connection_line = None
        self.highlight_type = None
        self.is_highlighted = False
        
        if owner == "neutral":
            self.value = 10
            self.player_points = 0
            self.pc_points = 0
        else:
            self.value = 0

        self.main_window = None
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        
        # Add unique ID for each unit (for history tracking)
        self.unit_id = id(self)

    def disconnect_from(self, other_unit):
        if other_unit in self.connections:
            self.connections.remove(other_unit)
            if self in other_unit.connections:
                other_unit.connections.remove(self)
            
            self.update()
            other_unit.update()
            if self.scene():
                self.scene().update()
            
            if self.main_window and self.owner == self.main_window.current_turn:
                self.main_window.action_performed()
                
                # Record the disconnection in history
                if hasattr(self.main_window, 'history_recorder'):
                    self.main_window.history_recorder.record_disconnect(self.unit_id, other_unit.unit_id)

    def paint(self, painter, option, widget=None):
        if self.is_highlighted:
            if self.highlight_type == "connect":
                painter.setPen(QPen(QColor(0, 100, 255), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(-5, -5, self.size + 10, self.size + 10)
            elif self.highlight_type == "attack":
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(-5, -5, self.size + 10, self.size + 10)
            elif self.highlight_type == "transfer":
                painter.setPen(QPen(QColor(255, 255, 0), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(-5, -5, self.size + 10, self.size + 10)
            elif self.highlight_type == "ally":
                painter.setPen(QPen(QColor(0, 255, 0), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(-5, -5, self.size + 10, self.size + 10)
        
        pen = QPen(Qt.darkGray, 1, Qt.DashLine)
        painter.setPen(pen)
        for other in self.connections:
            start = self.scenePos() + self.boundingRect().center()
            end = other.scenePos() + other.boundingRect().center()
            painter.drawLine(self.mapFromScene(start), self.mapFromScene(end))

        if not self.pixmap.isNull():
            if self.isSelected():
                painter.setPen(QPen(Qt.black, 2))
                painter.setBrush(QBrush(QColor(255, 255, 0)))
                painter.drawEllipse(0, 0, self.size, self.size)
                
            painter.drawPixmap(0, 0, self.pixmap)
        else:
            pen = QPen(Qt.black, 2)
            brush = QBrush(self.color if not self.isSelected() else QColor(255, 255, 0))
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawEllipse(0, 0, self.size, self.size)
        
        painter.setPen(QPen(Qt.white))
        painter.setFont(QFont("Arial", self.size // 4))
        
        if self.owner == "neutral":
            display_text = f"[{self.value}]"
            if self.player_points > 0:
                display_text += f"\nP:{self.player_points}"
            if self.pc_points > 0:
                display_text += f"\nC:{self.pc_points}"
        else:
            display_text = str(self.value)
            
        painter.drawText(QRectF(0, 0, self.size, self.size), 
                         Qt.AlignCenter, display_text)
    
    def transfer_points(self, from_unit):
        if self.owner == "neutral":
            if from_unit.owner == "player":
                self.player_points += 1
                if self.player_points >= 10:
                    self.convert_to("player")
            elif from_unit.owner == "pc":
                self.pc_points += 1
                if self.pc_points >= 10:
                    self.convert_to("pc")
    
        elif self.owner == "player" and from_unit.owner == "pc":
            self.decrease_value()
            if self.value == 0:
                self.convert_to_neutral()
    
        elif self.owner == "pc" and from_unit.owner == "player":
            self.decrease_value()
            if self.value == 0:
                self.convert_to_neutral()
            
        self.update()

    def convert_to_neutral(self):
        self.owner = "neutral"
        self.color = QColor(150, 150, 150)
        self.pixmap = QPixmap(":/images/grafika/grey.bmp")
        if not self.pixmap.isNull():
            self.pixmap = self.pixmap.scaled(self.size, self.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.value = 10
        self.player_points = 0
        self.pc_points = 0
        self.update()
        
        if self.main_window:
            self.main_window.check_game_over()

    def convert_to(self, new_owner):
        old_owner = self.owner
        self.owner = new_owner

        if new_owner == "player":
            self.color = QColor(50, 200, 50)
            self.pixmap = QPixmap(":/images/grafika/green.bmp")
            self.value = self.player_points
        elif new_owner == "pc":
            self.color = QColor(200, 50, 50)
            self.pixmap = QPixmap(":/images/grafika/red.bmp")
            self.value = self.pc_points
    
        if not self.pixmap.isNull():
            self.pixmap = self.pixmap.scaled(self.size, self.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
        self.player_points = 0
        self.pc_points = 0

        self.update()
        
        # Record ownership change
        if self.main_window and hasattr(self.main_window, 'history_recorder'):
            self.main_window.history_recorder.record_unit_change(self.unit_id, {
                "owner_change": True,
                "old_owner": old_owner,
                "new_owner": new_owner,
                "new_value": self.value
            })
        
        if self.main_window:
            self.main_window.check_game_over()
        
    def boundingRect(self):
        return QRectF(0, 0, self.size, self.size)
    
    def increase_value(self, amount=1):
        old_value = self.value
        self.value += amount
        self.update()
        
        # Record the value change
        if self.main_window and hasattr(self.main_window, 'history_recorder'):
            self.main_window.history_recorder.record_unit_change(self.unit_id, {
                "value_change": amount,
                "old_value": old_value,
                "new_value": self.value
            })
        
    def decrease_value(self, amount=1):
        old_value = self.value
        self.value -= amount
        self.value = max(0, self.value)
        self.update()
        
        # Record the value change
        if self.main_window and hasattr(self.main_window, 'history_recorder'):
            self.main_window.history_recorder.record_unit_change(self.unit_id, {
                "value_change": -amount,
                "old_value": old_value,
                "new_value": self.value
            })

    def mousePressEvent(self, event):
        if self.main_window and self.owner != "neutral" and self.owner != self.main_window.current_turn:
            return
            
        if event.button() == Qt.LeftButton:
            self.clear_all_highlights()
            self.setSelected(True)
            
            if event.modifiers() == Qt.ControlModifier:
                self.dragging_connection = True
                start_pos = self.scenePos() + self.boundingRect().center()
                self.temp_connection_line = ConnectionLine(start_pos)
                self.scene().addItem(self.temp_connection_line)
                self.show_possible_moves()  # Only show highlights when actively connecting
            event.accept()
        elif event.button() == Qt.RightButton:
            if self.main_window and self.owner != "neutral" and self.owner != self.main_window.current_turn:
                return
                
            self.deleting_connection = True
        
            self.clear_all_highlights()
            for unit in self.connections:
                unit.is_highlighted = True
                unit.highlight_type = "attack"
                unit.update()
        
            start_pos = self.scenePos() + self.boundingRect().center()
            self.temp_connection_line = ConnectionLine(start_pos)
            self.temp_connection_line.setPen(QPen(Qt.red, 2, Qt.DashLine))
            self.scene().addItem(self.temp_connection_line)
        
            event.accept()
        else:
            super().mousePressEvent(event)
            
    def clear_all_highlights(self):
        if self.scene():
            for item in self.scene().items():
                if isinstance(item, Unit):
                    item.is_highlighted = False
                    item.highlight_type = None
                    item.update()
                    
    def show_possible_moves(self):
        if not self.scene():
            return
            
        all_units = [item for item in self.scene().items() if isinstance(item, Unit) and item != self]
        
        for unit in all_units:
            if unit not in self.connections:
                unit.is_highlighted = True
                unit.highlight_type = "connect"
            else:
                if unit.owner == "neutral" and self.owner != "neutral":
                    unit.is_highlighted = True
                    unit.highlight_type = "transfer"
                elif unit.owner != self.owner and unit.owner != "neutral" and self.owner != "neutral":
                    unit.is_highlighted = True
                    unit.highlight_type = "attack"
                elif unit.owner == self.owner:
                    unit.is_highlighted = True
                    unit.highlight_type = "ally"
                    
            unit.update()        
            
    def mouseMoveEvent(self, event):
        if (self.dragging_connection or self.deleting_connection) and self.temp_connection_line:
            start_pos = self.scenePos() + self.boundingRect().center()
            mouse_pos = self.mapToScene(event.pos())
            self.temp_connection_line.setLine(QLineF(start_pos, mouse_pos))
            event.accept()
        else:
            super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event):
        if self.dragging_connection and self.temp_connection_line:
            end_pos = self.mapToScene(event.pos())
            
            # Clean up connection line
            self.scene().removeItem(self.temp_connection_line)
            self.temp_connection_line = None
            
            # Find item under cursor
            item_under_cursor = None
            for item in self.scene().items(end_pos):
                if isinstance(item, Unit) and item != self:
                    item_under_cursor = item
                    break
            
            # Connect only if we found a unit under the cursor
            if item_under_cursor:
                self.connect_to(item_under_cursor)
            
            # Clear all highlights after connection is made
            self.clear_all_highlights()
            self.dragging_connection = False
            event.accept()
        elif self.deleting_connection:
            end_pos = self.mapToScene(event.pos())
            
            # Clean up connection line
            if self.temp_connection_line:
                self.scene().removeItem(self.temp_connection_line)
                self.temp_connection_line = None
            
            # Find item under cursor
            item_under_cursor = None
            for item in self.scene().items(end_pos):
                if isinstance(item, Unit) and item != self and item in self.connections:
                    item_under_cursor = item
                    break
            
            # Disconnect only if we found a connected unit under the cursor
            if item_under_cursor:
                self.disconnect_from(item_under_cursor)
            
            # Always clear highlights when releasing
            self.clear_all_highlights()
            self.deleting_connection = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def handle_selection_changed(self):
        """Handle selection change to clear highlights"""
        if not self.dragging_connection and not self.deleting_connection:
            self.clear_all_highlights()
            
    def connect_to(self, other_unit):
        if other_unit not in self.connections:
            self.connections.append(other_unit)
            other_unit.connections.append(self)
            self.update()
            other_unit.update()
            
            if self.main_window and self.owner == self.main_window.current_turn:
                self.main_window.action_performed()
                
                # Record the connection in history
                if hasattr(self.main_window, 'history_recorder'):
                    self.main_window.history_recorder.record_connection(self.unit_id, other_unit.unit_id)

plugin_path = os.path.join(os.path.dirname(QtCore.__file__), "plugins", "platforms")
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

class LevelManager:
    def __init__(self):
        self.levels = []
        self.current_level_index = 0

    def add_level(self, level_config):
        self.levels.append(level_config)

    def get_current_level(self):
        if self.levels and 0 <= self.current_level_index < len(self.levels):
            return self.levels[self.current_level_index]
        return None

    def next_level(self):
        if self.current_level_index < len(self.levels) - 1:
            self.current_level_index += 1
            return True
        return False

    def reset(self):
        self.current_level_index = 0

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        
        self.level_manager = LevelManager()
        self.setup_levels()
        
        self.current_turn = "player"
        self.turn_duration = 5000
        self.turn_timer = QTimer(self)
        self.turn_timer.timeout.connect(self.switch_turn)
        self.turn_timer.setSingleShot(True)
        
        self.timer_tick = 100
        self.time_remaining = self.turn_duration
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.update_progress)
        
        # Initialize game history recorder
        self.history_recorder = GameHistoryRecorder()
        self.history_recorder.playback_finished.connect(self.on_playback_finished)
        self.is_playback_mode = False
        
        # Game configuration
        self.game_mode = "Single Player"  # Default mode
        self.network_ip = "127.0.0.1"
        self.network_port = 5000
        
        self.setWindowTitle("Expansion War")
        self.resize(850, 650)
        
        self.create_menu_bar()
        self.create_level_toolbar()
        self.create_turn_indicator()
        
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 800, 600)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        
        self.setCentralWidget(self.view)
        
        self.statusBar().showMessage(f"Level: {self.level_manager.current_level_index + 1}")
        
        self.view.installEventFilter(self)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.increment_all_units)
        self.timer.start(1000)
        self.scene.selectionChanged.connect(self.handle_selection_changed)
        
        self.load_level()
        self.start_turn()
        
        self.game_over = False
        
        # Unit ID to object mapping (for history playback)
        self.unit_map = {}
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        game_menu = menubar.addMenu('&Game')
        
        config_action = QAction('&Configuration', self)
        config_action.setShortcut('C')
        config_action.setStatusTip('Open configuration dialog')
        config_action.triggered.connect(self.show_config_dialog)
        game_menu.addAction(config_action)
        
        next_action = QAction('&Next Level', self)
        next_action.setShortcut('N')
        next_action.setStatusTip('Go to next level')
        next_action.triggered.connect(self.next_level)
        game_menu.addAction(next_action)
        
        reset_action = QAction('&Reset Level', self)
        reset_action.setShortcut('R')
        reset_action.setStatusTip('Reset current level')
        reset_action.triggered.connect(self.reset_level)
        game_menu.addAction(reset_action)
        
        game_menu.addSeparator()
        
        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close)
        game_menu.addAction(exit_action)
        
        # Add file menu
        file_menu = menubar.addMenu('&File')
        
        load_json_action = QAction('Load &JSON File', self)
        load_json_action.setStatusTip('Load and view JSON file')
        load_json_action.triggered.connect(self.load_json_file)
        file_menu.addAction(load_json_action)
        
        load_xml_action = QAction('Load &XML File', self)
        load_xml_action.setStatusTip('Load and view XML file')
        load_xml_action.triggered.connect(self.load_xml_file)
        file_menu.addAction(load_xml_action)
    
    def load_json_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open JSON File", "", "JSON Files (*.json)")
        if file_path:
            try:
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    formatted_json = json.dumps(data, indent=4)
                    self.show_file_content(f"JSON Viewer - {os.path.basename(file_path)}", formatted_json)
                    self.statusBar().showMessage(f"Loaded JSON file: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load JSON file: {str(e)}")

    def load_xml_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open XML File", "", "XML Files (*.xml)")
        if file_path:
            try:
                dom = xml.dom.minidom.parse(file_path)
                pretty_xml = dom.toprettyxml(indent="  ")
                self.show_file_content(f"XML Viewer - {os.path.basename(file_path)}", pretty_xml)
                self.statusBar().showMessage(f"Loaded XML file: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load XML file: {str(e)}")

    def show_file_content(self, title, content):
        dialog = FileViewerDialog(self, title, content)
        dialog.exec_()
    
    def create_level_toolbar(self):
        toolbar = self.addToolBar("Levels")
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        toolbar.setVisible(True)
        toolbar.setStyleSheet("QToolBar { background-color: #f0f0f0; border: 10px solid #c0c0c0; spacing: 10px; }")
        
        level_label = QLabel("Select Level:")
        level_label.setStyleSheet("font-weight: bold; margin-right: 10px; margin-left: 5px;")
        toolbar.addWidget(level_label)
        
        self.level_buttons = []
        for i in range(len(self.level_manager.levels)):
            level_button = QPushButton(f"Level {i+1}")
            level_button.setMinimumWidth(80)
            level_button.setStyleSheet("QPushButton { padding: 5px 10px; }")
            level_button.clicked.connect(lambda checked, level=i: self.select_level(level))
            toolbar.addWidget(level_button)
            self.level_buttons.append(level_button)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        
        reset_button = QPushButton("Reset Level")
        reset_button.setStyleSheet("QPushButton { background-color: #ffcc00; color: black; font-weight: bold; padding: 5px 15px; margin-right: 10px; }")
        reset_button.clicked.connect(self.reset_level)
        toolbar.addWidget(reset_button)
        
    def create_turn_indicator(self):
        turn_toolbar = self.addToolBar("Turn System")
        turn_toolbar.setMovable(False)
        turn_toolbar.setStyleSheet("QToolBar { background-color: #f0f0f0; border: 1px solid #c0c0c0; spacing: 10px; }")
        
        self.turn_label = QLabel("Current Turn: GREEN PLAYER")
        self.turn_label.setStyleSheet("font-weight: bold; color: green; font-size: 14px; margin: 0px 10px;")
        turn_toolbar.addWidget(self.turn_label)
        
        self.turn_progress = QProgressBar()
        self.turn_progress.setRange(0, self.turn_duration)
        self.turn_progress.setValue(self.turn_duration)
        self.turn_progress.setTextVisible(False)
        self.turn_progress.setMinimumWidth(200)
        self.turn_progress.setMaximumWidth(300)
        self.turn_progress.setStyleSheet("QProgressBar { border: 1px solid gray; border-radius: 3px; background: white; } "
                                         "QProgressBar::chunk { background-color: green; }")
        turn_toolbar.addWidget(self.turn_progress)
        
        self.time_label = QLabel("5.0s")
        self.time_label.setStyleSheet("font-weight: bold; margin: 0px 10px;")
        turn_toolbar.addWidget(self.time_label)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        turn_toolbar.addWidget(spacer)
        
        self.skip_button = QPushButton("Skip Turn")
        self.skip_button.clicked.connect(self.switch_turn)
        self.skip_button.setStyleSheet("QPushButton { background-color: #ddd; padding: 5px 10px; margin-right: 10px; }")
        turn_toolbar.addWidget(self.skip_button)

    def select_level(self, level_index):
        if 0 <= level_index < len(self.level_manager.levels):
            self.level_manager.current_level_index = level_index
            self.load_level()
            self.update_button_styles()
        
    def update_button_styles(self):
        for i, button in enumerate(self.level_buttons):
            if i == self.level_manager.current_level_index:
                button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 5px 10px; }")
            else:
                button.setStyleSheet("QPushButton { padding: 5px 10px; }")

    def setup_levels(self):
        self.level_manager.add_level([
            {"x": 150, "y": 300, "size": 50, "owner": "player"},
            {"x": 150, "y": 150, "size": 50, "owner": "pc"},
            {"x": 300, "y": 150, "size": 50, "owner": "pc"},
            {"x": 300, "y": 300, "size": 50, "owner": "neutral"}
        ])
        
        self.level_manager.add_level([
            {"x": 100, "y": 100, "size": 50, "owner": "player"},
            {"x": 200, "y": 100, "size": 50, "owner": "neutral"},
            {"x": 300, "y": 100, "size": 50, "owner": "pc"},
            {"x": 400, "y": 100, "size": 50, "owner": "neutral"},
            {"x": 250, "y": 300, "size": 50, "owner": "neutral"}
        ])
        
        self.level_manager.add_level([
            {"x": 100, "y": 300, "size": 50, "owner": "player"},
            {"x": 200, "y": 200, "size": 50, "owner": "neutral"},
            {"x": 300, "y": 300, "size": 50, "owner": "pc"},
            {"x": 150, "y": 400, "size": 50, "owner": "neutral"},
            {"x": 350, "y": 400, "size": 50, "owner": "neutral"},
            {"x": 400, "y": 200, "size": 50, "owner": "pc"}
        ])

    def load_level(self):
        current_level = self.level_manager.current_level_index + 1
        
        self.statusBar().showMessage(f"Level: {current_level}")
        self.setWindowTitle(f"Expansion War - Level {current_level}")
        
        self.update_button_styles()
        
        self.clear_all_connections_and_highlights()
        
        self.scene.clear()
        self.unit_map = {}  # Clear unit mapping
        
        level_config = self.level_manager.get_current_level()
        if level_config:
            for unit_config in level_config:
                unit = Unit(**unit_config)
                unit.main_window = self
                self.scene.addItem(unit)
                self.unit_map[unit.unit_id] = unit
        
        self.current_turn = "player"
        self.start_turn()
        
        self.game_over = False
        
        # Clear history when loading a new level
        if hasattr(self, 'history_recorder'):
            self.history_recorder.clear_history()

    def clear_all_connections_and_highlights(self):
        for item in self.scene.items():
            if isinstance(item, Unit):
                item.connections = []
                
                item.is_highlighted = False
                item.highlight_type = None
                
                if item.temp_connection_line and item.temp_connection_line in self.scene.items():
                    self.scene.removeItem(item.temp_connection_line)
                    item.temp_connection_line = None
                
                item.dragging_connection = False
                item.deleting_connection = False
        
        self.scene.update()

    def next_level(self):
        if self.level_manager.next_level():
            self.load_level()
        else:
            QMessageBox.information(self, "Game Complete", "You have completed all levels!")

    def reset_level(self):
        self.load_level()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_N:
            self.next_level()
        elif event.key() == Qt.Key_R:
            self.reset_level()
        else:
            super().keyPressEvent(event)

    def handle_selection_changed(self):
        selected_items = self.scene.selectedItems()
        
        if not selected_items:
            # Only clear highlights if nothing is selected
            for item in self.scene.items():
                if isinstance(item, Unit):
                    item.is_highlighted = False
                    item.highlight_type = None
                    item.update()
                    
    def increment_all_units(self):
        units_with_same_owner_connections = set()
    
        for item in self.scene.items():
            if isinstance(item, Unit) and item.owner != "neutral":
                for connected_unit in item.connections:
                    if connected_unit.owner == item.owner:
                        units_with_same_owner_connections.add(item)
                        units_with_same_owner_connections.add(connected_unit)
    
        for item in self.scene.items():
            if isinstance(item, Unit) and item.owner != "neutral":
                if item in units_with_same_owner_connections:
                    item.increase_value(2)
                else:
                    item.increase_value(1)
    
        for item in self.scene.items():
            if isinstance(item, Unit):
                for connected_unit in item.connections:
                    if item.owner != "neutral" and connected_unit.owner == "neutral":
                        connected_unit.transfer_points(item)
                        item.decrease_value()
                
                    elif item.owner == "player" and connected_unit.owner == "pc":
                        connected_unit.transfer_points(item)
                
                    elif item.owner == "pc" and connected_unit.owner == "player":
                        connected_unit.transfer_points(item)     
   
    def eventFilter(self, source, event):
        if source is self.view and event.type() == QtCore.QEvent.KeyPress:
            selected_items = self.scene.selectedItems()
            if selected_items:
                if event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
                    for item in selected_items:
                        if isinstance(item, Unit):
                            item.increase_value()
                    return True
                elif event.key() == Qt.Key_Minus:
                    for item in selected_items:
                        if isinstance(item, Unit):
                            item.decrease_value()
                    return True
        return super().eventFilter(source, event)

    def start_turn(self):
        if self.current_turn == "player":
            self.turn_label.setText("Current Turn: GREEN PLAYER")
            self.turn_label.setStyleSheet("font-weight: bold; color: green; font-size: 14px; margin: 0px 10px;")
            self.turn_progress.setStyleSheet("QProgressBar { border: 1px solid gray; border-radius: 3px; background: white; } "
                                           "QProgressBar::chunk { background-color: green; }")
        else:
            self.turn_label.setText("Current Turn: RED PLAYER")
            self.turn_label.setStyleSheet("font-weight: bold; color: red; font-size: 14px; margin: 0px 10px;")
            self.turn_progress.setStyleSheet("QProgressBar { border: 1px solid gray; border-radius: 3px; background: white; } "
                                           "QProgressBar::chunk { background-color: red; }")
        
        self.time_remaining = self.turn_duration
        self.turn_progress.setValue(self.time_remaining)
        self.time_label.setText(f"{self.time_remaining/1000:.1f}s")
        
        self.turn_timer.start(self.turn_duration)
        self.progress_timer.start(self.timer_tick)
        
        # Record turn switch in history
        if hasattr(self, 'history_recorder') and not self.is_playback_mode:
            self.history_recorder.record_turn_switch(self.current_turn)

    def update_progress(self):
        self.time_remaining -= self.timer_tick
        if self.time_remaining < 0:
            self.time_remaining = 0
        
        self.turn_progress.setValue(self.time_remaining)
        self.time_label.setText(f"{self.time_remaining/1000:.1f}s")

    def switch_turn(self):
        self.turn_timer.stop()
        self.progress_timer.stop()
        
        self.current_turn = "pc" if self.current_turn == "player" else "player"
        
        self.start_turn()
        
        self.check_game_over()
    
    def load_game_history(self, history):
        """Load game history for playback"""
        try:
            # Convert all ID fields to integers if they're strings
            for move in history:
                for key in ["from_id", "to_id", "unit_id"]:
                    if key in move and not isinstance(move[key], (int, float)):
                        try:
                            move[key] = int(float(move[key]))
                        except (ValueError, TypeError):
                            pass
                            
            self.history_recorder.load_history(history)
            self.statusBar().showMessage(f"Loaded {len(history)} moves. Ready for playback.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load game history: {str(e)}")
            import traceback
            traceback.print_exc()

    def start_playback(self, speed=1.0):
        """Start playback of loaded history"""
        if not self.history_recorder.history:
            QMessageBox.warning(self, "No History", "No game history available for playback.")
            return
            
        self.is_playback_mode = True
        # Stop all game timers
        self.turn_timer.stop()
        self.progress_timer.stop()
        self.timer.stop()
        
        QMessageBox.information(self, "Playback Starting", 
                          f"Starting playback of {len(self.history_recorder.history)} moves at {speed}x speed")
        self.history_recorder.start_playback(self, speed)

    def execute_connection(self, from_id, to_id):
        """Execute a connection between units (for playback)"""
        from_unit = self.find_unit_by_id(from_id)
        to_unit = self.find_unit_by_id(to_id)
        
        if from_unit and to_unit:
            # Temporarily disable recording
            old_recording = self.history_recorder.is_recording
            self.history_recorder.is_recording = False
            
            # Check if already connected
            if to_unit in from_unit.connections:
                self.history_recorder.is_recording = old_recording
                return True
                
            from_unit.connect_to(to_unit)
            
            # Restore recording state
            self.history_recorder.is_recording = old_recording
            return True
        return False
    
    def execute_disconnection(self, from_id, to_id):
        """Execute a disconnection between units (for playback)"""
        from_unit = self.find_unit_by_id(from_id)
        to_unit = self.find_unit_by_id(to_id)
        
        if from_unit and to_unit:
            # Temporarily disable recording
            old_recording = self.history_recorder.is_recording
            self.history_recorder.is_recording = False
            
            # Check if actually connected
            if to_unit not in from_unit.connections:
                self.history_recorder.is_recording = old_recording
                return True
                
            from_unit.disconnect_from(to_unit)
            
            # Restore recording state
            self.history_recorder.is_recording = old_recording
            return True
        return False
    
    def update_unit(self, unit_id, changes):
        """Update a unit's properties (for playback)"""
        unit = self.find_unit_by_id(unit_id)
        if not unit:
            return False
            
        # Temporarily disable recording
        old_recording = self.history_recorder.is_recording
        self.history_recorder.is_recording = False
        
        success = False
        if "value_change" in changes:
            value_change = float(changes["value_change"]) if isinstance(changes["value_change"], str) else changes["value_change"]
            if value_change > 0:
                unit.increase_value(abs(value_change))
                success = True
            else:
                unit.decrease_value(abs(value_change))
                success = True
        
        if "owner_change" in changes:
            unit.owner = str(changes["new_owner"])
            if changes["new_owner"] == "player":
                unit.color = QColor(50, 200, 50)
                unit.pixmap = QPixmap(":/images/grafika/green.bmp")
            elif changes["new_owner"] == "pc":
                unit.color = QColor(200, 50, 50)
                unit.pixmap = QPixmap(":/images/grafika/red.bmp")
            else:
                unit.color = QColor(150, 150, 150)
                unit.pixmap = QPixmap(":/images/grafika/grey.bmp")
                
            if not unit.pixmap.isNull():
                unit.pixmap = unit.pixmap.scaled(unit.size, unit.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
            new_value = changes.get("new_value")
            if new_value is not None:
                unit.value = float(new_value) if isinstance(new_value, str) else new_value
            unit.update()
            success = True
        
        # Restore recording state
        self.history_recorder.is_recording = old_recording
        return success
    
    def find_unit_by_id(self, unit_id):
        """Find a unit by its ID"""
        # Handle different types of IDs
        try:
            unit_id = int(unit_id)
        except (ValueError, TypeError):
            pass
            
        # First check our unit map
        if unit_id in self.unit_map:
            return self.unit_map[unit_id]
        
        # If not found, try to find by iterating (and update map)
        for item in self.scene.items():
            if isinstance(item, Unit):
                if hasattr(item, 'unit_id') and item.unit_id == unit_id:
                    self.unit_map[unit_id] = item
                    return item
        
        self.statusBar().showMessage(f"Warning: Could not find unit with ID {unit_id}")
        return None
        
    @property
    def game_history(self):
        """Get the current game history"""
        if hasattr(self, 'history_recorder'):
            return self.history_recorder.get_history()
        return []

    def show_config_dialog(self):
        """Show the game configuration dialog"""
        dialog = ConfigDialog(self)
        if dialog.exec_():
            config = dialog.get_config()
            self.game_mode = config["game_mode"]
            self.network_ip = config["ip_address"]
            self.network_port = config["port"]
            
            self.statusBar().showMessage(f"Game Mode: {self.game_mode}")
    
    def check_game_over(self):
        if self.game_over:
            return
            
        green_units = 0
        red_units = 0
        
        for item in self.scene.items():
            if isinstance(item, Unit):
                if item.owner == "player":
                    green_units += 1
                elif item.owner == "pc":
                    red_units += 1
        
        winner = None
        if green_units == 0 and red_units > 0:
            winner = "red"
        elif red_units == 0 and green_units > 0:
            winner = "green"
            
        if winner:
            self.game_over = True
            self.turn_timer.stop()
            self.progress_timer.stop()
            self.timer.stop()
            self.show_game_over_dialog(winner)
    
    def show_game_over_dialog(self, winner):
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Game Over!")
        
        if winner == "green":
            dialog.setIcon(QMessageBox.Information)
            dialog.setWindowIcon(QIcon(QPixmap(":/images/grafika/green.bmp")))
            dialog.setText("<h2>Green Player Wins!</h2>")
            dialog.setInformativeText("Green player has conquered the map!")
        else:
            dialog.setIcon(QMessageBox.Information)
            dialog.setWindowIcon(QIcon(QPixmap(":/images/grafika/red.bmp")))
            dialog.setText("<h2>Red Player Wins!</h2>")
            dialog.setInformativeText("Red player has conquered the map!")
        
        restart_button = dialog.addButton("Restart Level", QMessageBox.AcceptRole)
        next_level_button = dialog.addButton("Next Level", QMessageBox.ActionRole)
        dialog.addButton("Close", QMessageBox.RejectRole)
        
        dialog.exec_()
        
        clicked_button = dialog.clickedButton()
        if clicked_button == restart_button:
            self.game_over = False
            self.reset_level()
        elif clicked_button == next_level_button:
            self.game_over = False
            self.next_level()
        
    def action_performed(self):
        """Called when a player performs an action (connect/disconnect)"""
        if not self.game_over:
            self.switch_turn()
            
        self.check_game_over()
        
    def on_playback_finished(self):
        """Called when playback is complete"""
        self.is_playback_mode = False
        # Restart game timers
        self.timer.start(1000)
        self.start_turn()
        QMessageBox.information(self, "Playback Complete", "Game history playback has finished.")
        
    def prepare_for_playback(self):
        """Prepare the game state for playback"""
        # Map units by position for more reliable mapping during playback
        self.position_unit_map = {}
        for item in self.scene.items():
            if isinstance(item, Unit):
                # Use position as a key (rounded to nearest 10px for stability)
                pos_key = (int(item.pos().x() // 10) * 10, int(item.pos().y() // 10) * 10)
                self.position_unit_map[pos_key] = item
                
        # Also map by index for levels that use standard configurations
        self.index_unit_map = {}
        unit_items = [item for item in self.scene.items() if isinstance(item, Unit)]
        for i, unit in enumerate(unit_items):
            self.index_unit_map[i] = unit
            
        # Additional debugging information
        print(f"Prepared {len(self.unit_map)} units for playback")
        print(f"Position map has {len(self.position_unit_map)} entries")
        print(f"Index map has {len(self.index_unit_map)} entries")
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
