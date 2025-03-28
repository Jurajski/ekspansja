from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem
from PyQt5.QtCore import Qt, QRectF, QPointF, QLineF
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter
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
    def __init__(self, x, y, size=40, color=QColor(50, 200, 50)):
        super().__init__()
        
        self.size = size
        self.color = color
        self.connections = []  # List of other Unit instances
        self.dragging_connection = False
        self.temp_connection_line = None

        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        # Remove movable flag
        # self.setFlag(QGraphicsItem.ItemIsMovable)
        
    def boundingRect(self):
        # Określa "obszar roboczy" jednostki (dla kolizji, zaznaczenia itd.)
        return QRectF(0, 0, self.size, self.size)

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
        
    def add_items(self):
        # Dodanie jednostki na mapę
        unit1 = Unit(150, 300, size=50, color=QColor(50, 200, 50))
        self.scene.addItem(unit1)

        unit2 = Unit(150, 150, size=50, color=QColor(200, 50, 50))
        self.scene.addItem(unit2)
        
        unit3 = Unit(300, 150, size=50, color=QColor(200, 50, 50))
        self.scene.addItem(unit3)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())