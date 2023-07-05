from PySide6.QtCore import Signal
from PySide6.QtGui import *
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsWindow(QWidget):
    cam_parameters = Signal(tuple)

    def __init__(self):
        super().__init__()
        self.settingsUI()

    def getLineEdit(self, title, value, units):
        self.newLineEdit = QLineEdit(self)
        self.newLineEdit.setText(value)
        line_unit = QLabel(units)
        line_title = QLabel(title)
        line_title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        line_unit.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        line_layout = QHBoxLayout()
        line_layout.addWidget(line_title)
        line_layout.addWidget(self.newLineEdit)
        line_layout.addWidget(line_unit)

        return line_layout

    def getLineEditText(self, idx1, idx2):
        temp_layout = self.v_layout.itemAt(idx1)

        if isinstance(temp_layout, QHBoxLayout):
            textWidget = temp_layout.itemAt(idx2)
            textBox = textWidget.widget()
        param_text = textBox.text()

        param_text = int(float(param_text))

        return param_text

    def settingsUI(self):
        self.setWindowTitle("Settings")
        self.v_layout = QVBoxLayout()
        self.setGeometry(10, 10, 400, 200)

        afr_layout = self.getLineEdit("Acquisition Frame rate:", "20", "frames/sec")
        self.v_layout.addLayout(afr_layout)

        expTime_layout = self.getLineEdit("Exposure Time", "1000", "µS")
        self.v_layout.addLayout(expTime_layout)

        combo_layout = QHBoxLayout()
        self.combo_box = QComboBox(self)
        self.combo_box.setCurrentIndex(0)
        combobox_label = QLabel("Pixel Format")
        combo_layout.addWidget(combobox_label)
        combo_layout.addWidget(self.combo_box)
        self.v_layout.addLayout(combo_layout)

        self.okButton = QPushButton("Ok", self)
        self.okButton.clicked.connect(self.connectToStream)
        self.v_layout.addWidget(self.okButton)

        self.setLayout(self.v_layout)

    def closeEvent(self, event):
        event.accept()

    def connectToStream(self):
        format_str = self.combo_box.currentText()
        current_fr = self.getLineEditText(0, 1)
        current_ExpTime = self.getLineEditText(1, 1)
        self.cam_parameters.emit((format_str, current_fr, current_ExpTime))
