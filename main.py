from PyQt5.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QBrush, QPen, QColor, QPainter
import sys
import os
from PyQt5 import QtCore  # or PySide2 if that's what you're using
from PyQt5.QtWidgets import QGraphicsItem
from PyQt5.QtGui import QBrush, QPen, QColor
from PyQt5.QtCore import QRectF, Qt

class Unit(QGraphicsItem):
    def __init__(self, x, y, size=40, color=QColor(50, 200, 50)):
        super().__init__()
        
        self.size = size
        self.color = color
        self.connections = []  # List of other Unit instances

        self.setPos(x, y)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        

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
        print("Kliknięto jednostkę!")
        super().mousePressEvent(event)
    def connect_to(self, other_unit):
        if other_unit not in self.connections:
            self.connections.append(other_unit)
            other_unit.connections.append(self)  # Optional: make it bidirectional



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
        self.setWindowTitle("QGraphicsScene Example")
        self.resize(850, 650)
        
    def add_items(self):
        # Dodanie jednostki na mapę
        unit1 = Unit(150, 300,size=50,color=QColor(50,200,50))
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