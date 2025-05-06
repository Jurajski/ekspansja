from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsLineItem, QPushButton, QLabel, QVBoxLayout, QWidget, QHBoxLayout, QAction, QMessageBox, QSizePolicy, QProgressBar, QFileDialog
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF, QTimer
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter, QFont, QPixmap, QIcon
import os
import sys
import json
import xml.etree.ElementTree as ET
import xml.dom.minidom
from PyQt5 import QtCore
import resources_rc
from config_dialog import ConfigDialog
from db_handler import DatabaseHandler
from save_load_dialog import SaveGameDialog, LoadGameDialog
from network_manager import NetworkManager, NetworkMessage
import network_connection_fix

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
        
        if (owner == "player"):
            self.pixmap = QPixmap(":/images/grafika/green.bmp")
            self.color = QColor(50, 200, 50)
        elif (owner == "pc"):
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
        
        # Network-related properties
        self.last_action = None  # Store the last action performed for network sync
        
        # Initialize player_points and pc_points for all units
        self.player_points = 0
        self.pc_points = 0
        
        if owner == "neutral":
            self.value = 10
        else:
            self.value = 0

        self.main_window = None
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        
        # Add unique ID for each unit (for history tracking)
        self.unit_id = id(self)

    def can_interact(self):
        """Check if this unit can be interacted with in current game state"""
        if not self.main_window:
            return True
            
        # In single player mode or if game is over, follow standard rules
        if self.main_window.game_mode != "Network Game" or self.main_window.game_over:
            return self.owner == "neutral" or self.owner == self.main_window.current_turn
            
        # In network game, only allow interaction if:
        # 1. It's our turn (player_role matches current_turn)
        # 2. We own the unit (unit's owner matches player_role) OR the unit is neutral
        is_our_turn = self.main_window.current_turn == self.main_window.player_role
        
        # FIX: Check if we own the unit (compare to player_role, not current_turn)
        is_our_unit = self.owner == "neutral" or self.owner == self.main_window.player_role
        
        # Debug print for interaction check
        print(f"Interaction check - Unit owner: {self.owner}, Current turn: {self.main_window.current_turn}, Player role: {self.main_window.player_role}")
        print(f"Can interact? is_our_turn: {is_our_turn}, is_our_unit: {is_our_unit}, Result: {is_our_turn and is_our_unit}")
        
        # Debug print for client interaction check
        if self.main_window.player_role == "pc":
            print(f"[CLIENT] Interaction check - Unit owner: {self.owner}, Current turn: {self.main_window.current_turn}")
            print(f"[CLIENT] Is my turn? {is_our_turn} (current_turn:{self.main_window.current_turn}==player_role:{self.main_window.player_role})")
            print(f"[CLIENT] Is my unit? {is_our_unit} (owner:{self.owner}==player_role:{self.main_window.player_role} or neutral)") 
            print(f"[CLIENT] Final permission: {is_our_turn and is_our_unit}")
        
        return is_our_turn and is_our_unit
        
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
                # Store the disconnect action for network sync
                self.last_action = {
                    "type": "disconnect",
                    "source_id": self.unit_id,
                    "target_id": other_unit.unit_id
                }
                self.main_window.action_performed(self.last_action)

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
        
        # Draw connection lines - important part for visible connections
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
            self.value = self.player_points if self.player_points > 0 else 1  # Ensure at least 1 point
        elif new_owner == "pc":
            self.color = QColor(200, 50, 50)
            self.pixmap = QPixmap(":/images/grafika/red.bmp")
            self.value = self.pc_points if self.pc_points > 0 else 1  # Ensure at least 1 point
    
        if not self.pixmap.isNull():
            self.pixmap = self.pixmap.scaled(self.size, self.size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    
        self.player_points = 0
        self.pc_points = 0

        self.update()
        
        if self.main_window:
            self.main_window.check_game_over()
        
    def boundingRect(self):
        return QRectF(0, 0, self.size, self.size)
    
    def increase_value(self, amount=1):
        old_value = self.value
        self.value += amount
        self.update()
        
    def decrease_value(self, amount=1):
        old_value = self.value
        self.value -= amount
        self.value = max(0, self.value)
        self.update()

    def mousePressEvent(self, event):
        # First check if we can interact with this unit based on network roles and turns
        if not self.can_interact():
            # Don't allow selection if we can't interact
            event.ignore()
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
            if not self.can_interact():
                event.ignore()
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
            
            # Force scene update to ensure connection lines are drawn
            if self.scene():
                self.scene().update()
            
            if self.main_window and self.owner == self.main_window.current_turn:
                # Store the connect action for network sync
                self.last_action = {
                    "type": "connect",
                    "source_id": self.unit_id,
                    "target_id": other_unit.unit_id
                }
                self.main_window.action_performed(self.last_action)

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
        
        # Apply network patches first
        try:
            import network_patch
            print("Network patches applied")
        except ImportError:
            print("Network patches not available - connection stability may be limited")
        
        # Game configuration
        self.game_mode = "Single Player"  # Default mode
        self.network_ip = "127.0.0.1"
        self.network_port = 5000
        self.network_role = "server"  # Default role for network game
        
        # Network manager
        self.network_manager = NetworkManager()
        
        # Try to apply network fixes
        try:
            from network_fixes import apply_network_fixes
            self.network_manager = apply_network_fixes(self.network_manager)
        except ImportError:
            print("Network fixes module not found - connection stability may be limited")
        
        self.network_manager.connected.connect(self.on_network_connected)
        self.network_manager.disconnected.connect(self.on_network_disconnected)
        self.network_manager.message_received.connect(self.on_network_message)
        self.network_manager.error.connect(self.on_network_error)
        self.network_manager.server_status_changed.connect(self.on_server_status_changed)
        
        # Player roles for network game
        self.player_role = "player"  # Local player is "player" by default
        self.opponent_role = "pc"    # Remote player is "pc" by default
        
        self.network_game_ready = False
        
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
        
        # Unit ID to object mapping
        self.unit_map = {}
        
        # Initialize database handler
        self.db_handler = DatabaseHandler()
        self.mongodb_saved_games = []

    def process_network_action(self, action_data):
        """Process an action received from the network"""
        if not self.network_game_ready:
            return
        
        action_type = action_data.get("type")
        source_id = action_data.get("source_id")
        target_id = action_data.get("target_id")
        
        # Find the units
        source_unit = self.find_unit_by_id(source_id)
        target_unit = self.find_unit_by_id(target_id)
        
        if not source_unit or not target_unit:
            self.on_network_error(f"Cannot find units for action: {action_data}")
            return
        
        # Apply the action
        if action_type == "connect":
            if target_unit not in source_unit.connections:
                source_unit.connections.append(target_unit)
                target_unit.connections.append(source_unit)
                source_unit.update()
                target_unit.update()
                # Force scene update to refresh connection lines
                self.scene.update()
        elif action_type == "disconnect":
            if target_unit in source_unit.connections:
                source_unit.connections.remove(target_unit)
                if source_unit in target_unit.connections:
                    target_unit.connections.remove(source_unit)
                source_unit.update()
                target_unit.update()
                # Force scene update to refresh connection lines
                self.scene.update()
        
        # Update status message to show action was received
        self.statusBar().showMessage(f"Received opponent's {action_type} action - waiting for turn change...")
        
        # Note: We don't switch turns here - we'll wait for the explicit TURN_CHANGE message

    def apply_network_game_state(self, game_state):
        """Apply game state received from network"""
        try:
            # Update network roles from received game state
            if "network_role" in game_state:
                remote_role = game_state.get("network_role")
                # Set our role as the opposite of the remote role
                if remote_role == "server":
                    self.network_role = "client"
                    self.player_role = "pc"
                    self.opponent_role = "player"
                else:
                    self.network_role = "server"
                    self.player_role = "player"
                    self.opponent_role = "pc"
            
            # Set the current turn
            if "current_turn" in game_state:
                self.current_turn = game_state.get("current_turn")
            
            # Apply the game state to our local game
            success = self.apply_game_state(game_state)
            
            if success:
                self.statusBar().showMessage("Network game state received and applied successfully")
                print("Network game state applied successfully")
                
                # Apply connection fixes to ensure all connection lines are visible
                network_connection_fix.apply_connection_fixes(self)
                
                # Make sure we have the correct turn state after loading
                if self.current_turn == self.player_role:
                    self.start_turn()
                else:
                    # Not our turn, just wait
                    self.statusBar().showMessage("Waiting for opponent's move...")
                    # Disable turn timer if it's not our turn
                    self.turn_timer.stop()
                    self.progress_timer.stop()
                    self.skip_button.setEnabled(False)
            else:
                self.statusBar().showMessage("Failed to apply network game state")
                print("Failed to apply network game state")
                QMessageBox.warning(self, "Game State Error", "Failed to apply network game state")
                
            return success
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = f"Error applying network game state: {str(e)}"
            print(error_msg)
            self.statusBar().showMessage(error_msg)
            QMessageBox.critical(self, "Game State Error", error_msg)
            return False

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
        
        # First clear all connections to avoid dangling references
        self.clear_all_connections_and_highlights()
        
        # Now clear the scene which will delete all units
        self.scene.clear()
        
        # Clear the unit map
        self.unit_map = {}
        
        # Create new units for the level
        level_config = self.level_manager.get_current_level()
        if level_config:
            for unit_config in level_config:
                unit = Unit(**unit_config)
                unit.main_window = self
                self.scene.addItem(unit)
                self.unit_map[unit.unit_id] = unit
        
        # Set initial game state
        self.current_turn = "player"
        self.start_turn()

    def clear_all_connections_and_highlights(self):
        # Create a local copy of the items to avoid modification during iteration
        items = list(self.scene.items())
        for item in items:
            if isinstance(item, Unit):
                # Clear connections
                item.connections = []
                # Clear highlights
                item.is_highlighted = False
                item.highlight_type = None
                # Remove any temp connection lines
                if hasattr(item, 'temp_connection_line') and item.temp_connection_line and item.temp_connection_line in self.scene.items():
                    self.scene.removeItem(item.temp_connection_line)
                    item.temp_connection_line = None
                # Reset connection state
                item.dragging_connection = False
                item.deleting_connection = False
        # Force scene update
        self.scene.update()

    def next_level(self):
        if self.level_manager.next_level():
            self.load_level()
        else:
            QMessageBox.information(self, "Game Complete", "You have completed all levels!")

    def reset_level(self):
        # Stop all game timers first to avoid accessing deleted objects
        self.timer.stop()
        self.turn_timer.stop()
        self.progress_timer.stop()
        
        # Set game_over to false before loading level
        self.game_over = False
        
        # Now load the level
        self.load_level()
        
        # Restart the unit timer after level is loaded
        self.timer.start(1000)

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
        """Start a new turn"""
        # Check if we're in network mode but not properly connected
        if self.game_mode == "Network Game" and not self.network_manager.valid_connection:
            print("Network game not ready - waiting for connection")
            self.statusBar().showMessage("Waiting for network connection...")
            self.time_remaining = 0
            self.skip_button.setEnabled(False)
            return
        
        # In network mode, disable inputs during opponent's turn
        if self.game_mode == "Network Game" and self.current_turn != self.player_role:
            # Only show waiting message if we're properly connected
            if self.network_game_ready:
                print(f"Waiting for opponent's move (Turn: {self.current_turn}, Your role: {self.player_role})")
                self.statusBar().showMessage(f"Waiting for opponent's move...")
                self.time_remaining = 0
                self.skip_button.setEnabled(False)
            else:
                print("Network game not ready")
                self.statusBar().showMessage("Waiting for network connection...")
                self.time_remaining = 0
                self.skip_button.setEnabled(False)
            return
        
        # Update UI - now moved to update_turn_indicator method
        self.update_turn_indicator()
        
        # Enable skip button for local turns
        self.skip_button.setEnabled(True)
        
        # Start turn timer
        self.time_remaining = self.turn_duration
        self.turn_progress.setValue(self.time_remaining)
        self.time_label.setText(f"{self.time_remaining/1000:.1f}s")
        self.turn_timer.start(self.turn_duration)
        self.progress_timer.start(self.timer_tick)

    def update_progress(self):
        self.time_remaining -= self.timer_tick
        if self.time_remaining < 0:
            self.time_remaining = 0
        self.turn_progress.setValue(self.time_remaining)
        self.time_label.setText(f"{self.time_remaining/1000:.1f}s")

    def switch_turn(self):
        """Switch the current turn between players"""
        self.turn_timer.stop()
        self.progress_timer.stop()
        
        # In network mode, only apply visual updates for turn change
        # The actual turn state is controlled by action_performed and network messages
        if self.game_mode == "Network Game" and self.network_game_ready:
            # Just update UI for the new turn state
            if self.current_turn == self.player_role:
                # It's now our turn
                print(f"Starting our turn: {self.player_role}")
            else:
                # It's opponent's turn
                print(f"Starting opponent's turn: {self.opponent_role}")
        else:
            # For local games, switch normally
            self.current_turn = "pc" if self.current_turn == "player" else "player"
            print(f"Switched turn to: {self.current_turn}")
        
        # Always start the new turn (will handle network mode correctly)
        self.update_turn_indicator()
        self.start_turn()

    def update_turn_indicator(self):
        """Update the turn indicator UI to match current_turn"""
        # Update turn indicator
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
        
        # Debug output to verify turn state
        print(f"Turn indicator updated: current_turn={self.current_turn}")
        print(f"Is it my turn? {self.current_turn == self.player_role}")
        
        # Force redraw of UI components
        self.turn_label.update()
        self.turn_progress.update()

    def show_config_dialog(self):
        """Show the game configuration dialog"""
        dialog = ConfigDialog(self)
        if dialog.exec_():
            old_game_mode = self.game_mode
            config = dialog.get_config()
            self.game_mode = config["game_mode"]
            self.network_ip = config["ip_address"]
            self.network_port = config["port"]
            self.network_role = config.get("network_role", "server")
            
            # Update statusbar
            self.statusBar().showMessage(f"Game Mode: {self.game_mode}")
            
            # If switching to network mode, initialize networking
            if self.game_mode == "Network Game" and old_game_mode != "Network Game":
                self.initialize_network()
            # If switching away from network mode, disconnect
            elif old_game_mode == "Network Game" and self.game_mode != "Network Game":
                self.network_manager.stop()

    def initialize_network(self):
        """Initialize network connection based on role"""
        # First stop any existing connections
        self.network_manager.stop()
        self.network_game_ready = False
        
        # Reset the game if switching to network mode
        self.reset_level()
        
        # Set player roles based on network role
        if self.network_role == "server":
            self.player_role = "player"  # Host is always GREEN
            self.opponent_role = "pc"
            # Host always starts first in a new network game
            self.current_turn = "player"
            print(f"Server initialized: my role={self.player_role}, opponent={self.opponent_role}, turn={self.current_turn}")
            # Start the server
            print(f"Starting server on {self.network_ip}:{self.network_port}")
            self.statusBar().showMessage("Starting server and waiting for client...")
            
            # Add delay before starting server to ensure ports are released
            QTimer.singleShot(1000, lambda: self.start_server_with_delay())
        else:
            # As client, we're the second player (RED)
            self.player_role = "pc"  # Client is always RED
            self.opponent_role = "player"
            # Client waits for host to take the first turn
            self.current_turn = "player"
            print(f"Client initialized: my role={self.player_role}, opponent={self.opponent_role}, turn={self.current_turn}")
            # Connect to server
            print(f"Connecting to server at {self.network_ip}:{self.network_port}")
            self.statusBar().showMessage(f"Connecting to server at {self.network_ip}:{self.network_port}...")
            
            # Test if the server is even running before attempting connection
            if not self.network_manager.check_server_status(self.network_ip, self.network_port):
                show_connection_dialog = QMessageBox.warning(
                    self, "Server Not Running", 
                    f"The server at {self.network_ip}:{self.network_port} doesn't appear to be running. "
                    "Check the following:\n"
                    "• Make sure the server has been started by the host player\n"
                    "• Verify you have the correct IP address and port\n"
                    "• Check if a firewall is blocking the connection\n\n"
                    "Would you like to try connecting anyway?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                    
                if show_connection_dialog == QMessageBox.No:
                    self.statusBar().showMessage("Network connection canceled.")
                    self.game_mode = "Single Player"
                    return
            
            # Attempt connection (will retry automatically)
            self.network_manager.connect_to_server(self.network_ip, self.network_port)

    def start_server_with_delay(self):
        """Start server with proper delay to allow port binding"""
        import time
        # Sleep to ensure socket is fully released
        time.sleep(1.0)
        self.network_manager.start_server(self.network_ip, self.network_port)
        # After server starts, add additional delay to allow OS to properly set up the socket
        time.sleep(0.5)
        print("Server started with extra timeout protection")

    def on_network_connected(self, success, message):
        """Handle network connection event"""
        print(f"Network connected: {success}, {message}")
        if success:
            self.statusBar().showMessage(message)
            # Only update state for verified connection
            if "verified" in message.lower() and self.network_role == "client":
                # Client is waiting for the initial game state
                self.statusBar().showMessage("Connected to server. Waiting for game to start...")
                print("Waiting for initial game state from server")
                
                # Prepare game for network play by resetting
                self.reset_level()
        else:
            print(f"Network connection failed: {message}")
            QMessageBox.critical(self, "Network Error", message)
            self.game_mode = "Single Player"  # Fallback to single player
            self.statusBar().showMessage("Network connection failed. Switched to Single Player mode.")

    def on_network_disconnected(self, message):
        """Handle network disconnection event"""
        print(f"Network disconnected: {message}")
        
        # Check for specific Windows socket error 10054 (Connection reset by peer)
        is_reset_error = "10054" in message or "reset by peer" in message.lower()
        
        if self.game_mode == "Network Game":
            # Only show dialog for unexpected disconnections, not user-initiated ones
            if "user initiated" not in message.lower():
                # Store current network settings for potential reconnect
                stored_ip = self.network_ip
                stored_port = self.network_port
                stored_role = self.network_role
                
                # Special handling for connection reset errors
                if is_reset_error:
                    self.statusBar().showMessage("Connection reset by remote host. Attempting automatic recovery...")
                    print("Detected socket reset error 10054. Attempting automatic recovery...")
                    # First stop any existing connections
                    try:
                        self.network_manager.stop()  # Remove force_cleanup parameter
                    except TypeError:
                        print("NetworkManager.stop() doesn't accept additional parameters")
                    
                    # Use a longer delay for reset errors 
                    QTimer.singleShot(3000, lambda: self.attempt_reconnection(stored_ip, stored_port, stored_role))
                    return
                
                reconnect_option = QMessageBox.question(
                    self, "Network Disconnected", 
                    f"Network connection closed: {message}\n\nWould you like to attempt reconnection?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                
                if reconnect_option == QMessageBox.Yes:
                    # Try to reconnect
                    self.statusBar().showMessage("Attempting to reconnect...")
                    # First stop any existing connections
                    try:
                        self.network_manager.stop()  # Remove force_cleanup parameter
                    except TypeError:
                        print("NetworkManager.stop() doesn't accept additional parameters")
                    
                    QTimer.singleShot(2000, lambda: self.attempt_reconnection(stored_ip, stored_port, stored_role))
                    return
            
            # If no reconnection or reconnection failed
            QMessageBox.warning(self, "Network Disconnected", 
                              f"Network connection closed: {message}\nSwitching to Single Player mode.")
            self.game_mode = "Single Player"
            self.statusBar().showMessage("Network disconnected. Switched to Single Player mode.")
            self.network_game_ready = False
            self.network_manager.connection_verified = False  # Ensure connection state is cleared

    def attempt_reconnection(self, ip, port, role):
        """Attempt to reconnect to the server or restart the server"""
        self.network_ip = ip
        self.network_port = port
        self.network_role = role
        
        # Reset network state to ensure clean reconnection
        self.network_game_ready = False
        
        if role == "client":
            # Check if server is still running before reconnecting
            self.statusBar().showMessage(f"Checking if server is available at {ip}:{port}...")
            
            if self.network_manager.check_server_status(ip, port):
                self.statusBar().showMessage(f"Server found! Reconnecting to {ip}:{port}...")
                # Remove extra parameters from connect_to_server call
                self.network_manager.connect_to_server(ip, port)
            else:
                self.statusBar().showMessage("Server not responding. Reconnection failed.")
                QMessageBox.warning(self, "Reconnection Failed", 
                                  "Could not reach the server. Switching to Single Player mode.")
                self.game_mode = "Single Player"
                return
        else:
            # We were the server, try to restart it
            self.statusBar().showMessage(f"Restarting server on {ip}:{port}...")
            # Set a longer delay to ensure ports are fully released
            QTimer.singleShot(1000, lambda: self.start_network_server(ip, port))

    def start_network_server(self, ip, port):
        """Start the network server with error handling"""
        try:
            # Make sure any previous server is fully stopped
            try:
                self.network_manager.stop()  # Remove force_cleanup parameter
            except TypeError:
                print("NetworkManager.stop() doesn't accept additional parameters")
            
            # Now start a fresh server instance
            self.network_manager.start_server(ip, port)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.statusBar().showMessage(f"Error starting server: {str(e)}")
            QMessageBox.critical(self, "Server Error", 
                               f"Failed to start server: {str(e)}\nSwitching to Single Player mode.")
            self.game_mode = "Single Player"

    def on_network_error(self, error_message):
        """Handle network error event"""
        print(f"Network error: {error_message}")
        
        # Check for the specific 10054 error (Connection reset by peer)
        if "10054" in error_message or "reset by peer" in error_message.lower():
            self.statusBar().showMessage("Connection reset detected. Network may be unstable.")
            # Don't show modal dialog for reset errors, as they'll be handled by the reconnection logic
            return
            
        # Check for critical errors that should be displayed prominently
        if "Connection refused" in error_message:
            # Don't show a message box for every retry attempt
            if "Retrying" not in error_message:
                QMessageBox.warning(self, "Network Error", error_message)
        # Update status bar with all errors
        self.statusBar().showMessage(error_message)

    def on_network_message(self, message):
        """Handle received network message"""
        if message.type == NetworkMessage.CONNECT:
            # Connection established and verified - only process if we're actually the server
            if self.network_role == "server" and self.network_manager.valid_connection:
                # Check if this connection has already been processed
                if not self.network_manager.connection_processed:
                    self.network_manager.connection_processed = True
                    
                    # Update UI to show connection
                    client_addr = message.data.get('address', 'unknown')
                    client_port = message.data.get('port', 'unknown')
                    client_id = message.data.get('client_id', 'unknown')
                    print(f"Client {client_id} connected from {client_addr}:{client_port}")
                    self.statusBar().showMessage(f"Client {client_id} connected from {client_addr}:{client_port}")
                    
                    # Wait a moment to ensure UI updates before showing dialog
                    QTimer.singleShot(300, lambda: self.show_client_connected_dialog())            
    
        elif message.type == NetworkMessage.GAME_STATE:
            # Received game state update
            print("Received game state from server")
            
            # As client, restart game before applying network state
            if self.network_role == "client":
                self.reset_level()
                
            # Apply the received state
            self.apply_network_game_state(message.data)
            self.network_game_ready = True
    
        elif message.type == NetworkMessage.ACTION:
            # Process received action
            action_type = message.data.get("type", "unknown")
            print(f"Received network action: {action_type}")
            self.process_network_action(message.data)
            
            # After processing the action, wait for explicit turn change
            # We don't switch turns here anymore to avoid race conditions
    
        elif message.type == NetworkMessage.TURN_CHANGE:
            # Turn changed message contains complete turn info
            turn_data = message.data
            
            # FIX: Check that turn_data is a dictionary
            if not isinstance(turn_data, dict):
                print(f"Error: Invalid turn change data format: {turn_data}")
                self.statusBar().showMessage(f"Error: Invalid turn change data format")
                return
                
            next_turn = turn_data.get("next_turn")
            action_id = turn_data.get("action_id", "unknown")
            
            # FIX: Add type checking for next_turn
            if not isinstance(next_turn, str):
                print(f"Error: Invalid next_turn value: {next_turn}")
                self.statusBar().showMessage("Error: Invalid turn data received")
                # Try to extract from the dictionary if possible
                if isinstance(turn_data, dict) and "next_turn" in turn_data and isinstance(turn_data["next_turn"], str):
                    next_turn = turn_data["next_turn"]
                    print(f"Extracted next_turn string: {next_turn}")
                else:
                    # Use a fallback based on current player role
                    next_turn = self.opponent_role if self.current_turn == self.player_role else self.player_role
                    print(f"Using fallback next_turn: {next_turn}")
            
            print(f"Received turn change: next_turn={next_turn}, action_id={action_id}")
            print(f"Current player role: {self.player_role}, Opponent role: {self.opponent_role}")
            
            if next_turn:
                # Only switch turn if it's valid and we're in a network game
                if self.game_mode == "Network Game" and self.network_game_ready:
                    # Update our current turn state 
                    previous_turn = self.current_turn
                    self.current_turn = next_turn  # This value must be a string like "player" or "pc"
                    print(f"Turn changed from {previous_turn} to {next_turn}")
                    
                    # Debug verification that current_turn is now a string
                    print(f"Current turn type: {type(self.current_turn)}, value: {self.current_turn}")
                    
                    # Debug output to help diagnose turn issues
                    print(f"Is it my turn now? {next_turn == self.player_role}")
                    print(f"Current turn: {self.current_turn}, My role: {self.player_role}")
                    
                    # Update UI based on whether it's our turn now
                    if next_turn == self.player_role:
                        self.statusBar().showMessage(f"Your turn now! ({self.player_role})")
                        # Make sure UI reflects it's our turn
                        self.update_turn_indicator()
                        self.start_turn()
                    else:
                        self.statusBar().showMessage(f"Waiting for opponent's move... ({next_turn}'s turn)")
                        # Disable our controls since it's not our turn
                        self.turn_timer.stop()
                        self.progress_timer.stop()
                        self.skip_button.setEnabled(False)
                        # Still update the turn indicator
                        self.update_turn_indicator()

    def show_client_connected_dialog(self):
        """Show dialog indicating a client has connected"""
        if self.network_manager.valid_connection:
            print("Verified client connection! Showing dialog and sending game state")
            QMessageBox.information(self, "Network Game", "Client connected! The game will now begin.")
            
            # Restart game before sending initial state
            self.reset_level()
            
            # Add delay before sending game state to ensure connection is stable
            QTimer.singleShot(1000, self.send_initial_game_state)
        else:
            print("Connection not verified - cannot show connection dialog")

    def send_initial_game_state(self):
        """Send the initial game state to the client"""
        print("Sending initial game state to client")
        
        # Add extra connection verification
        if not self.network_manager.valid_connection:
            print("Connection lost before sending game state!")
            QMessageBox.warning(self, "Connection Lost", 
                             "Connection to client was lost before sending game state.")
            return
        
        game_state = self.get_current_game_state()
        # Add network-specific details
        game_state["network_role"] = self.network_role
        
        # Always set initial turn to "player" (GREEN) which is the host
        game_state["current_turn"] = "player"
        self.current_turn = "player"  # Make sure our local state matches
        
        # Sleep before sending to ensure client socket is ready
        import time
        time.sleep(1.0)        
        
        success = self.network_manager.broadcast_game_state(game_state)
        
        if success:
            print("Game state sent successfully")
            self.network_game_ready = True
            self.statusBar().showMessage("Game state sent. It's your turn (GREEN)!")
            self.start_turn()
            
            # Add verification timer to check connection
            QTimer.singleShot(2000, self.verify_client_still_connected)       
        else:
            print("Failed to send initial game state")
            QMessageBox.warning(self, "Network Error", 
                               "Failed to send initial game state to client. Connection may have been lost.")

    def verify_client_still_connected(self):
        """Verify client is still connected after game state sent"""
        if not self.network_manager.valid_connection:
            print("Client disconnected after game state was sent")
            QMessageBox.warning(self, "Client Disconnected", 
                             "Client disconnected shortly after receiving game state.")
            self.game_mode = "Single Player"
            self.statusBar().showMessage("Client disconnected. Switched to Single Player mode.")
            self.network_game_ready = False
        else:
            print("Client connection verified after game state sent")
            self.statusBar().showMessage("Network game ready. Your turn!")

    def find_unit_by_id(self, unit_id):
        """Find a unit by its ID"""
        if isinstance(unit_id, str):
            try:
                unit_id = int(unit_id)
            except ValueError:
                return None
        for item in self.scene.items():
            if isinstance(item, Unit) and item.unit_id == unit_id:
                return item
        return None

    def action_performed(self, action_data=None):
        """Called when a player performs an action (connect/disconnect)"""
        if not self.game_over:
            # In network mode, send the action to the other player
            if self.game_mode == "Network Game" and self.network_game_ready:
                if action_data:
                    # Send action to remote player
                    self.network_manager.send_action(action_data)
                    
                    # Calculate next turn
                    next_turn = self.opponent_role
                    
                    # Send explicit turn change message
                    print(f"Sending turn change to opponent. Next turn: {next_turn}")
                    turn_message = {
                        "next_turn": next_turn,
                        "current_player": self.player_role,
                        "action_id": id(action_data)  # Unique ID for this action
                    }
                    self.network_manager.send_turn_change(turn_message)
                    self.statusBar().showMessage(f"Action sent to opponent. Switching to {next_turn}'s turn.")
                    
                    # Update our local turn state
                    self.current_turn = next_turn
                    
                    # Force update of turn indicator UI
                    self.update_turn_indicator()
                    
            # Switch turn locally (in single player or after sending network message)
            self.switch_turn()
        self.check_game_over()

    def check_game_over(self):
        if self.game_over:
            return
        
        # Count units of each type
        green_units = 0
        red_units = 0
        total_units = 0
        
        for item in self.scene.items():
            if isinstance(item, Unit):
                total_units += 1
                if item.owner == "player":
                    green_units += 1
                elif item.owner == "pc":
                    red_units += 1
        
        # Only determine a winner if we have actual units in the scene
        if total_units == 0:
            return
        
        winner = None
        if green_units == 0 and red_units > 0:
            winner = "red"
        elif red_units == 0 and green_units > 0:
            winner = "green"
        # Only actually end the game if there are at least some units owned by either player
        # and one player has no units
        elif (green_units + red_units) > 0 and (green_units == 0 or red_units == 0):
            winner = "green" if green_units > 0 else "red"
        
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
            # Stop all timers before resetting
            self.turn_timer.stop()
            self.progress_timer.stop()
            self.timer.stop()
            QTimer.singleShot(100, self.reset_level)  # Use timer to ensure dialog is fully closed
        elif clicked_button == next_level_button:
            self.game_over = False
            # Stop all timers before moving to next level
            self.turn_timer.stop()
            self.progress_timer.stop()
            self.timer.stop()
            QTimer.singleShot(100, self.next_level)  # Use timer to ensure dialog is fully closed

    def save_game(self):
        """Save current game state"""
        # Check if there are units to save
        if not any(isinstance(item, Unit) for item in self.scene.items()):
            QMessageBox.warning(self, "Cannot Save", "There is no active game to save.")
            return
        
        # Check if MongoDB is available
        mongodb_available = hasattr(self.db_handler, 'mongodb_client')
        
        # Show save dialog
        dialog = SaveGameDialog(self, mongodb_available)
        if dialog.exec_():
            save_info = dialog.get_save_info()
            
            # Collect game state
            game_state = self.get_current_game_state()
            
            # Save based on selected format
            if save_info["use_mongodb"]:
                # Connect to MongoDB if needed
                if not self.db_handler.connected:
                    success, message = self.db_handler.connect_mongodb(save_info["mongodb_connection_string"])
                    if not success:
                        QMessageBox.critical(self, "MongoDB Connection Error", message)
                        return
                
                # Save to MongoDB
                success, message = self.db_handler.save_to_mongodb(game_state)
                if success:
                    QMessageBox.information(self, "Game Saved", "Game state saved to MongoDB successfully.")
                else:
                    QMessageBox.critical(self, "Save Error", message)
            else:
                # Save to file (JSON or XML)
                if save_info["format"] == "json":
                    success, message = self.db_handler.save_to_json_file(game_state, save_info["filepath"])
                else:  # XML
                    success, message = self.db_handler.save_to_xml_file(game_state, save_info["filepath"])
                
                if success:
                    QMessageBox.information(self, "Game Saved", message)
                else:
                    QMessageBox.critical(self, "Save Error", message)

    def load_game(self):
        """Load a saved game"""
        # Check if MongoDB is available and get saved games
        mongodb_available = hasattr(self.db_handler, 'mongodb_client')
        
        # Show load dialog
        dialog = LoadGameDialog(self, mongodb_available, self.mongodb_saved_games)
        if dialog.exec_():
            load_info = dialog.get_load_info()
            
            # Load based on selected format
            if load_info["use_mongodb"]:
                # Connect to MongoDB if needed
                if not self.db_handler.connected:
                    success, message = self.db_handler.connect_mongodb(load_info["mongodb_connection_string"])
                    if not success:
                        QMessageBox.critical(self, "MongoDB Connection Error", message)
                        return
                
                # Load from MongoDB
                success, message, game_state = self.db_handler.load_from_mongodb(load_info["game_id"])
                if success:
                    self.apply_game_state(game_state)
                    QMessageBox.information(self, "Game Loaded", "Game state loaded from MongoDB successfully.")
                else:
                    QMessageBox.critical(self, "Load Error", message)
            else:
                # Load from file (JSON or XML)
                if load_info["format"] == "json":
                    success, message, game_state = self.db_handler.load_from_json_file(load_info["filepath"])
                else:  # XML
                    success, message, game_state = self.db_handler.load_from_xml_file(load_info["filepath"])
                
                if success:
                    self.apply_game_state(game_state)
                    QMessageBox.information(self, "Game Loaded", "Game state loaded successfully.")
                else:
                    QMessageBox.critical(self, "Load Error", message)

    def connect_to_mongodb(self, connection_string):
        """Connect to MongoDB and fetch saved games"""
        success, message = self.db_handler.connect_mongodb(connection_string)
        if success:
            # Get list of saved games
            success, message, saved_games = self.db_handler.get_saved_games()
            if success:
                self.mongodb_saved_games = saved_games
                self.statusBar().showMessage("Connected to MongoDB successfully.")
            else:
                QMessageBox.warning(self, "Warning", message)
        else:
            QMessageBox.critical(self, "Connection Error", message)

    def get_current_game_state(self):
        """Collect current game state"""
        units = []
        
        # Count units by owner
        player_units = 0
        pc_units = 0
        
        # Collect unit data
        for item in self.scene.items():
            if isinstance(item, Unit):
                unit_data = {
                    "id": item.unit_id,
                    "owner": item.owner,
                    "value": item.value,
                    "x": item.pos().x(),
                    "y": item.pos().y(),
                    "size": item.size
                }
                
                # Count by owner
                if item.owner == "player":
                    player_units += 1
                elif item.owner == "pc":
                    pc_units += 1
                
                # If neutral, include points
                if item.owner == "neutral":
                    unit_data["player_points"] = item.player_points
                    unit_data["pc_points"] = item.pc_points
                
                # Include connections
                unit_data["connections"] = [conn.unit_id for conn in item.connections]
                
                units.append(unit_data)
        
        # Create game state
        game_state = {
            "level": self.level_manager.current_level_index + 1,
            "current_turn": self.current_turn,
            "game_mode": self.game_mode,
            "player_units": player_units,
            "pc_units": pc_units,
            "units": units
        }
        
        return game_state

    def apply_game_state(self, game_state):
        """Apply loaded game state"""
        try:
            # First, ensure we've loaded the correct level
            if "level" in game_state:
                level_idx = game_state["level"] - 1  # Convert from 1-based to 0-based
                if 0 <= level_idx < len(self.level_manager.levels):
                    self.level_manager.current_level_index = level_idx
            
            # Stop all timers
            self.timer.stop()
            self.turn_timer.stop()
            self.progress_timer.stop()
            
            # Clear the game state
            self.game_over = False
            self.clear_all_connections_and_highlights()
            self.scene.clear()
            self.unit_map = {}
            
            # Create units from game state
            for unit_data in game_state.get("units", []):
                unit = Unit(
                    x=unit_data.get("x", 0),
                    y=unit_data.get("y", 0),
                    size=unit_data.get("size", 40),
                    owner=unit_data.get("owner", "neutral")
                )
                unit.unit_id = unit_data.get("id", id(unit))
                unit.value = unit_data.get("value", 0 if unit.owner != "neutral" else 10)
                unit.main_window = self
                
                if unit.owner == "neutral":
                    unit.player_points = unit_data.get("player_points", 0)
                    unit.pc_points = unit_data.get("pc_points", 0)
                
                self.scene.addItem(unit)
                self.unit_map[unit.unit_id] = unit
            
            # Create connections
            for unit_data in game_state.get("units", []):
                unit_id = unit_data.get("id")
                if unit_id in self.unit_map:
                    unit = self.unit_map[unit_id]
                    
                    # Establish connections
                    for conn_id in unit_data.get("connections", []):
                        if conn_id in self.unit_map and self.unit_map[conn_id] not in unit.connections:
                            connected_unit = self.unit_map[conn_id]
                            unit.connections.append(connected_unit)
                            if unit not in connected_unit.connections:
                                connected_unit.connections.append(unit)
            
            # Update all units to correctly draw connections
            for unit_id, unit in self.unit_map.items():
                unit.update()
            
            # Set game state
            self.current_turn = game_state.get("current_turn", "player")
            self.game_mode = game_state.get("game_mode", "Single Player")
            
            # Update UI
            self.statusBar().showMessage(f"Level: {self.level_manager.current_level_index + 1}")
            self.setWindowTitle(f"Expansion War - Level {self.level_manager.current_level_index + 1}")
            self.update_button_styles()
            
            # Restart timers and turn
            self.start_turn()
            self.timer.start(1000)
            
            # Check for game over
            self.check_game_over()
            
            return True
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to apply game state: {str(e)}")
            return False

    def close(self):
        """Override close to properly disconnect network"""
        if hasattr(self, 'network_manager'):
            self.network_manager.stop()
        super().close()

    def on_server_status_changed(self, is_running, status_message):
        """Handle server status change"""
        if is_running:
            # Server is running
            if self.game_mode == "Network Game" and self.network_role == "client" and not self.network_game_ready:
                # If we're a client and not connected, try to connect
                self.statusBar().showMessage("Server detected! Attempting to connect...")
                # Remove max_retries parameter
                self.network_manager.connect_to_server(self.network_ip, self.network_port)
        else:
            # Server is not running
            if self.game_mode == "Network Game":
                if self.network_role == "client":
                    self.statusBar().showMessage("Server not running. Waiting for server to start...")
                else:
                    # We are the server but it's not running - this shouldn't happen
                    self.statusBar().showMessage("Warning: Server appears to be offline!")
                    
                    # Try to restart the server if it's crashed
                    if hasattr(self, 'network_manager') and self.network_manager:
                        restart_server = QMessageBox.question(
                            self, "Server Offline", 
                            "The server appears to be offline. Would you like to restart it?",
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                        
                        if restart_server == QMessageBox.Yes:
                            self.statusBar().showMessage(f"Restarting server on {self.network_ip}:{self.network_port}...")
                            # Make sure server is fully stopped before restarting
                            try:
                                self.network_manager.stop()  # Remove force_cleanup parameter
                            except TypeError:
                                print("NetworkManager.stop() doesn't accept additional parameters")
                            
                            QTimer.singleShot(2000, lambda: self.start_network_server(self.network_ip, self.network_port))

    def create_menu_bar(self):
        """Create the application menu bar"""
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
        
        # Add save/load functionality
        save_action = QAction('&Save Game', self)
        save_action.setShortcut('Ctrl+S')
        save_action.setStatusTip('Save current game state')
        save_action.triggered.connect(self.save_game)
        game_menu.addAction(save_action)
        
        load_action = QAction('&Load Game', self)
        load_action.setShortcut('Ctrl+L')
        load_action.setStatusTip('Load a saved game')
        load_action.triggered.connect(self.load_game)
        game_menu.addAction(load_action)
        
        game_menu.addSeparator()
        
        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.close)
        game_menu.addAction(exit_action)
        
        # Add network menu
        network_menu = menubar.addMenu('&Network')
        
        network_diagnostics_action = QAction('&Network Diagnostics', self)
        network_diagnostics_action.setStatusTip('Open network diagnostics tool')
        network_diagnostics_action.triggered.connect(self.show_network_diagnostics)
        network_menu.addAction(network_diagnostics_action)
        
        network_menu.addSeparator()
        
        reconnect_action = QAction('&Reconnect', self)
        reconnect_action.setStatusTip('Reconnect to server')
        reconnect_action.triggered.connect(self.reconnect_to_server)
        network_menu.addAction(reconnect_action)

    def show_network_diagnostics(self):
        """Show network diagnostics dialog"""
        from network_diagnostics import NetworkDiagnosticsDialog
        
        dialog = NetworkDiagnosticsDialog(self, self.network_ip, self.network_port)
        dialog.exec_()

    def reconnect_to_server(self):
        """Attempt to reconnect to the server"""
        if self.game_mode != "Network Game" or self.network_role != "client":
            QMessageBox.information(self, "Reconnect", "Reconnect is only available in Network Game mode as a client.")
            return
            
        self.statusBar().showMessage(f"Attempting to reconnect to server at {self.network_ip}:{self.network_port}...")
        # Clean up existing connection before attempting a new one
        try:
            self.network_manager.stop()
        except Exception as e:
            print(f"Error stopping network manager: {str(e)}")
        
        # Adding longer delay before reconnection to ensure sockets properly close
        QTimer.singleShot(2000, lambda: self.attempt_reconnection(self.network_ip, self.network_port, self.network_role))

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
            
        spacer = QWidget()  # Just for spacing
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

