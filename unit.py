from PyQt5.QtWidgets import QGraphicsItem, QGraphicsLineItem
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter, QFont, QPixmap

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
        if not hasattr(self.main_window, 'game_mode') or self.main_window.game_mode != "Network Game" or self.main_window.game_over:
            return self.owner == "neutral" or self.owner == self.main_window.current_turn
            
        # In network game, only allow interaction if:
        # 1. It's our turn (player_role matches current_turn)
        # 2. We own the unit (current_turn matches unit.owner) OR the unit is neutral
        is_our_turn = self.main_window.current_turn == self.main_window.player_role
        is_our_unit = self.owner == "neutral" or self.owner == self.main_window.current_turn
        
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
            
            if self.main_window and hasattr(self.main_window, 'current_turn') and self.owner == self.main_window.current_turn:
                # Store the disconnect action for network sync
                self.last_action = {
                    "type": "disconnect",
                    "source_id": self.unit_id,
                    "target_id": other_unit.unit_id
                }
                if hasattr(self.main_window, 'action_performed'):
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
            
            if self.main_window and hasattr(self.main_window, 'current_turn') and self.owner == self.main_window.current_turn:
                # Store the connect action for network sync
                self.last_action = {
                    "type": "connect",
                    "source_id": self.unit_id,
                    "target_id": other_unit.unit_id
                }
                if hasattr(self.main_window, 'action_performed'):
                    self.main_window.action_performed(self.last_action)
