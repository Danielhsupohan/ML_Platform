import sys
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PySide6.QtCore import Qt, QMimeData, QByteArray, QDataStream, QIODevice, QPoint, Signal
from PySide6.QtGui import QDrag, QPainter, QPen

class DraggableLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(80, 30)
        self.setText(text)
        self.setStyleSheet("background-color: lightblue;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        
        drag = QDrag(self)
        mime_data = QMimeData()

        item_data = QByteArray()
        data_stream = QDataStream(item_data, QIODevice.WriteOnly)
        data_stream.writeQString(self.text())

        mime_data.setData('application/x-dnditemdata', item_data)
        drag.setMimeData(mime_data)
        drag.exec(Qt.CopyAction | Qt.MoveAction)

class MovableButton(QFrame):
    moved = Signal()
    clicked_with_pos = Signal(QPoint, str)
    
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 50)
        self.setFrameStyle(QFrame.Box | QFrame.Plain)
        self.setStyleSheet("background-color: white;")
        self.setMouseTracking(True)
        self.drag_start_position = None

        self.layout = QHBoxLayout(self)
        self.input_area = QLabel(self)
        self.input_area.setFixedSize(20, 50)
        self.input_area.setStyleSheet("background-color: red;")
        
        self.drag_area = QLabel(text, self)
        self.drag_area.setAlignment(Qt.AlignCenter)
        self.drag_area.setStyleSheet("background-color: lightgreen;")
        
        self.output_area = QLabel(self)
        self.output_area.setFixedSize(20, 50)
        self.output_area.setStyleSheet("background-color: blue;")
        
        self.layout.addWidget(self.input_area)
        self.layout.addWidget(self.drag_area)
        self.layout.addWidget(self.output_area)

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        if event.button() == Qt.LeftButton:
            if self.drag_area.geometry().contains(pos):
                self.drag_start_position = pos
                self.setStyleSheet("background-color: lightgreen;")
            elif self.input_area.geometry().contains(pos):
                self.clicked_with_pos.emit(self.mapToParent(pos), "input")
            elif self.output_area.geometry().contains(pos):
                self.clicked_with_pos.emit(self.mapToParent(pos), "output")
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setStyleSheet("background-color: white;")
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_start_position:
            if self.drag_area.geometry().contains(self.drag_start_position):
                self.move(self.mapToParent(event.position().toPoint() - self.drag_start_position))
                self.moved.emit()

class DropArea(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: white; border: 1px solid black;")
        self.setMinimumSize(400, 400)
        self.labels = []
        self.connections = []
        self.connections_order = []  # 用於記錄連接順序
        self.start_button = None
        self.start_side = None

    def dragEnterEvent(self, event):
        if (event.mimeData().hasFormat('application/x-dnditemdata')):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if (event.mimeData().hasFormat('application/x-dnditemdata')):
            item_data = event.mimeData().data('application/x-dnditemdata')
            data_stream = QDataStream(item_data, QIODevice.ReadOnly)
            text = data_stream.readQString()

            button = MovableButton(text, self)
            pos = self.snap_to_grid(event.position().toPoint() - QPoint(button.width() / 2, button.height() / 2))
            button.move(pos)
            button.show()
            button.clicked_with_pos.connect(self.handle_button_click)
            button.moved.connect(self.update)
            self.labels.append(button)
            event.acceptProposedAction()

    def snap_to_grid(self, pos, grid_size=20):
        x = (pos.x() // grid_size) * grid_size
        y = (pos.y() // grid_size) * grid_size
        return QPoint(x, y)

    def handle_button_click(self, pos, side):
        for button in self.labels:
            if button.geometry().contains(pos):
                if side == "output":
                    self.start_button = button
                    self.start_side = side
                elif side == "input" and self.start_button and self.start_button != button:
                    connection = (self.start_button, button)
                    self.connections.append(connection)
                    self.connections_order.append(connection)  # 按順序記錄連接
                    self.update()
                    self.start_button = None
                break

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        pen = QPen(Qt.black, 2)
        painter.setPen(pen)
        connection_counts = {}  # 用於記錄每個連接的次數
        for start_button, end_button in self.connections:
            connection = (start_button, end_button)
            if connection not in connection_counts:
                connection_counts[connection] = 0
            else:
                connection_counts[connection] += 1
            self.draw_connection(painter, start_button, end_button, connection_counts[connection])

    def draw_connection(self, painter, start_button, end_button, offset):
        start_pos = start_button.output_area.geometry().center() + start_button.pos()
        end_pos = end_button.input_area.geometry().center() + end_button.pos()
        # 添加向上偏移以避免重疊
        painter.drawLine(start_pos + QPoint(0, -offset * 10), end_pos + QPoint(0, -offset * 10))

    def undo_last_connection(self):
        if self.connections:
            last_connection = self.connections.pop()
            self.connections_order.remove(last_connection)
            self.update()

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("拖拽按鈕介面")
        self.setGeometry(100, 100, 800, 600)

        layout = QHBoxLayout(self)

        left_panel = QVBoxLayout()
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setFixedWidth(150)
        left_widget.setStyleSheet("background-color: lightgray; border: 1px solid black;")

        for i in range(3):   #方塊數量
            left_panel.addWidget(DraggableLabel(f"方塊 {i+1}"))

        complete_button = QPushButton("完成")
        complete_button.clicked.connect(self.save_connections)
        complete_button.pressed.connect(lambda: complete_button.setStyleSheet("background-color: lightgreen;"))
        complete_button.released.connect(lambda: complete_button.setStyleSheet(""))

        cancel_button = QPushButton("上一步")
        cancel_button.clicked.connect(self.undo_connection)
        cancel_button.pressed.connect(lambda: cancel_button.setStyleSheet("background-color: lightcoral;"))
        cancel_button.released.connect(lambda: cancel_button.setStyleSheet(""))

        left_panel.addWidget(complete_button)
        left_panel.addWidget(cancel_button)

        self.right_panel = DropArea()

        layout.addWidget(left_widget)
        layout.addWidget(self.right_panel)

        self.setLayout(layout)
        self.connection_history = []  # 用於儲存所有的連接紀錄

    def save_connections(self):
        connections_list = []
        for start_button, end_button in self.right_panel.connections_order:
            start_index = self.right_panel.labels.index(start_button) + 1
            end_index = self.right_panel.labels.index(end_button) + 1
            connections_list.append((start_index, end_index))
        
        self.connection_history.append(connections_list)  # 儲存連接到列表中
        for connection in connections_list:
            print(f"{connection[0]} -> {connection[1]}")
        print("所有連接紀錄:", self.connection_history)  # 打印出所有的連接紀錄

    def undo_connection(self):
        self.right_panel.undo_last_connection()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())