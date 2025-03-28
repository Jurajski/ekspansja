from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF,QTimer
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter, QFont
import sys
import os
from PyQt5 import QtCore
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsLineItem
from PyQt5.QtGui import QBrush, QPen, QColor
from PyQt5.QtCore import QRectF, Qt

class ConnectionLine(QGraphicsLineItem):
    """Temporary line displayed during connection dragging"""
    def __init__(self, start_pos):
        super().__init__()
        self.setLine(QLineF(start_pos, start_pos))
        self.setPen(QPen(Qt.darkGray, 1, Qt.DashLine))
        
class Unit(QGraphicsItem):
    def __init__(self, x, y, size=40, owner="player"):
        super().__init__()
        
        self.size = size
        self.owner = owner  # "player", "pc", or "neutral"
        
        # Set color based on owner
        if owner == "player":
            self.color = QColor(50, 200, 50)  # Green
        elif owner == "pc":
            self.color = QColor(200, 50, 50)  # Red
        else:  # neutral
            self.color = QColor(150, 150, 150)  # Gray
            
        self.connections = []  # List of other Unit instances
        self.dragging_connection = False
        self.temp_connection_line = None
        
        # Initialize value based on owner type
        if owner == "neutral":
            self.value = 10  # Neutral units start with 10
            self.player_points = 0  # Points given by player
            self.pc_points = 0      # Points given by PC
        else:
            self.value = 0

        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        
    def paint(self, painter, option, widget=None):
        # Draw lines to connected units
        pen = QPen(Qt.darkGray, 1, Qt.DashLine)
        painter.setPen(pen)
        for other in self.connections:
            start = self.scenePos() + self.boundingRect().center()
            end = other.scenePos() + other.boundingRect().center()
            painter.drawLine(self.mapFromScene(start), self.mapFromScene(end))

        # Then draw the unit itself
        pen = QPen(Qt.black, 2)
        brush = QBrush(self.color if not self.isSelected() else QColor(255, 255, 0))

        painter.setPen(pen)
        painter.setBrush(brush)
        painter.drawEllipse(0, 0, self.size, self.size)
        
        # Display the value in the center of the unit
        painter.setPen(QPen(Qt.white))
        painter.setFont(QFont("Arial", self.size // 4))
        
        # Special display for neutral units
        if self.owner == "neutral":
            # Show neutral value in brackets
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
        """Transfer points from a connected unit to this unit"""
        # If this is a neutral unit receiving points
        if self.owner == "neutral":
            if from_unit.owner == "player":
                self.player_points += 1
                # Check for takeover
                if self.player_points >= 10:
                    self.convert_to("player")
            elif from_unit.owner == "pc":
                self.pc_points += 1
            # Check for takeover
                if self.pc_points >= 10:
                    self.convert_to("pc")
    
    # If this is a player unit and is attacked by PC unit
        elif self.owner == "player" and from_unit.owner == "pc":
            self.decrease_value()
        # Check if value reached zero
            if self.value == 0:
                self.convert_to_neutral()
    
    # If this is a PC unit and is attacked by player unit
        elif self.owner == "pc" and from_unit.owner == "player":
            self.decrease_value()
        # Check if value reached zero
            if self.value == 0:
                self.convert_to_neutral()
            
        self.update()

    def convert_to_neutral(self):
        """Convert unit to neutral when its value reaches zero"""
        self.owner = "neutral"
        self.color = QColor(150, 150, 150)  # Gray
        self.value = 10  # Reset to default neutral value
        self.player_points = 0
        self.pc_points = 0
        self.update()
        print(f"Unit converted to neutral")
    def convert_to(self, new_owner):
        """Convert this unit to a new owner (player or pc)"""
        self.owner = new_owner
    
    # Update color based on new owner
        if new_owner == "player":
            self.color = QColor(50, 200, 50)  # Green
            self.value = self.player_points  # Set value to accumulated player points
        elif new_owner == "pc":
            self.color = QColor(200, 50, 50)  # Red
            self.value = self.pc_points  # Set value to accumulated PC points
    
    # Reset the points counters
        self.player_points = 0
        self.pc_points = 0
    
        self.update()
        print(f"Unit converted to {new_owner}")    
        
    def boundingRect(self):
        # Określa "obszar roboczy" jednostki (dla kolizji, zaznaczenia itd.)
        return QRectF(0, 0, self.size, self.size)

    
    def increase_value(self, amount=1):
        self.value += amount
        self.update()
        
    def decrease_value(self, amount=1):
        self.value -= amount
        self.value = max(0, self.value)  # Ensure value doesn't go below 0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Start connection dragging on any left click
            self.dragging_connection = True
            start_pos = self.scenePos() + self.boundingRect().center()
            self.temp_connection_line = ConnectionLine(start_pos)
            self.scene().addItem(self.temp_connection_line)
            event.accept()
        else:
            super().mousePressEvent(event)
            
    def mouseMoveEvent(self, event):
        if self.dragging_connection and self.temp_connection_line:
            # Update temp line endpoint to follow mouse
            start_pos = self.scenePos() + self.boundingRect().center()
            mouse_pos = self.mapToScene(event.pos())
            self.temp_connection_line.setLine(QLineF(start_pos, mouse_pos))
            event.accept()
        else:
            super().mouseMoveEvent(event)
            
    def mouseReleaseEvent(self, event):
        if self.dragging_connection and self.temp_connection_line:
            # Find if we're over another unit
            end_pos = self.mapToScene(event.pos())
            items = self.scene().items(end_pos)
            
            # Remove temp line
            self.scene().removeItem(self.temp_connection_line)
            self.temp_connection_line = None
            
            # Find if mouse was released over another unit
            for item in items:
                if isinstance(item, Unit) and item != self:
                    self.connect_to(item)
                    break
                    
            self.dragging_connection = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)
            
    def connect_to(self, other_unit):
        if other_unit not in self.connections:
            self.connections.append(other_unit)
            other_unit.connections.append(self)  # Optional: make it bidirectional
            self.update()
            other_unit.update()
            print(f"Connected units")



plugin_path = os.path.join(os.path.dirname(QtCore.__file__), "plugins", "platforms")
os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Create a scene
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 800, 600)  # Set scene dimensions
        
        # Create a view to display the scene
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        
        # Set the view as the central widget
        self.setCentralWidget(self.view)
        
        # Add items to the scene
        self.add_items()
        
        # Setup window
        self.setWindowTitle("Unit Connection Example")
        self.resize(850, 650)
        
        # Install event filter to handle key presses
        self.view.installEventFilter(self)
        
        # Create timer to increase unit values every second
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.increment_all_units)
        self.timer.start(1000)  # 1000 ms = 1 second
        
    def increment_all_units(self):
    # First increment all non-neutral units
        for item in self.scene.items():
            if isinstance(item, Unit) and item.owner != "neutral":
                item.increase_value()
    
    # Now check for connections and transfer points
        for item in self.scene.items():
            if isinstance(item, Unit):
            # Process connections for each unit
                for connected_unit in item.connections:
                # Case 1: Transfer points from player/PC to neutral units
                    if item.owner != "neutral" and connected_unit.owner == "neutral":
                        connected_unit.transfer_points(item)
                
                # Case 2: Player units attack PC units
                    elif item.owner == "player" and connected_unit.owner == "pc":
                        connected_unit.transfer_points(item)
                
                # Case 3: PC units attack player units
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
        
    def add_items(self):
    # Player unit (green)
        unit1 = Unit(150, 300, size=50, owner="player")
        self.scene.addItem(unit1)

    # Computer units (red)
        unit2 = Unit(150, 150, size=50, owner="pc")
        self.scene.addItem(unit2)
    
        unit3 = Unit(300, 150, size=50, owner="pc")
        self.scene.addItem(unit3)

        unit4 = Unit(300, 300, size=50, owner="neutral")
        self.scene.addItem(unit4)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())