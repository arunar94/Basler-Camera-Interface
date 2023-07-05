import os
import sys
import time
from pypylon import pylon
from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QImage, QPixmap, QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QMainWindow,
    QFileDialog,
)
from settings import SettingsWindow
from writers import FFMPEG_VideoWriter, Raw_Writer


# No of virtual cameras
os.environ["PYLON_CAMEMU"] = "2"
n_cams = int(os.environ["PYLON_CAMEMU"])
# n_cams = 1


# Creates the signals to send the array
class RecordingAgents(QObject):
    for i in range(n_cams):
        name = f"array_signal_{i}"
        locals()[name] = Signal(tuple)


class CameraStream(QMainWindow):
    recordSignal = Signal(tuple)

    def __init__(self):
        super().__init__()

        self.recording_threads = [None] * n_cams
        self.recordingAgent = RecordingAgents()
        self.fileLocation = (
            "."  # Current directory is default file location for storing output
        )
        self.counter = 0
        self.initUI()
        self.runCameras()

    def initUI(self):
        self.setWindowTitle("Basler Camera Stream")
        self.recordSignal.connect(self.startRecordingThread)
        self.setFixedSize(1000, 950)
        widget = QWidget(self)
        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu("&File")
        fileSaveAction = QAction("Save At", self)
        fileSaveAction.triggered.connect(self.getFileLocation)
        fileMenu.addAction(fileSaveAction)

        settingsMenu = menuBar.addMenu("&Settings")
        settingsAction = QAction("Open", self)
        settingsAction.triggered.connect(self.getCameraParams)
        settingsMenu.addAction(settingsAction)

        # Create labels and record buttons for displaying video streams
        self.labels = []
        self.stop_record_buttons = []
        self.combo_boxes = []
        self.is_recording = [False] * n_cams

        for k in range(n_cams):
            label = QLabel(self)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setFixedSize(250, 250)
            self.labels.append(label)
            combobox = QComboBox()
            combobox.setPlaceholderText("Choose Recording Method")
            combobox.addItems(["Raw_writer", "FFmpeg"])
            self.combo_boxes.append(combobox)
            button = QPushButton("Stop Recording", self)
            self.stop_record_buttons.append(button)
            button.clicked.connect(
                lambda _=None, cnt=k, obj=button: self.toggleRecording(cnt, obj)
            )
            combobox.activated.connect(
                lambda _=None, cnt=k, obj=combobox: self.toggleRecording(cnt, obj)
            )

        # Create a layout for the labels and buttons
        self.totalLayout = QVBoxLayout()
        gridLayout = QGridLayout()
        for i in range(n_cams):
            layout = QVBoxLayout()
            layout.addWidget(self.labels[i])
            layout.addWidget(self.combo_boxes[i])
            layout.addWidget(self.stop_record_buttons[i])
            gridLayout.addLayout(layout, i // 4, i % 4)
        gridLayout.setContentsMargins(5, 5, 5, 5)  # left, top, right, bottom
        self.totalLayout.addLayout(gridLayout)
        self.totalLayout.addSpacing(1)
        widget.setLayout(self.totalLayout)
        self.setCentralWidget(widget)
        
        # Create a timer to update the video streams
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateStreams)
        self.timer.start(1)

    def getFileLocation(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOptions(options)

        if dialog.exec() == QFileDialog.Accepted:
            selected_directory = dialog.selectedFiles()[0]
            self.fileLocation = selected_directory
            self.fileLoc_line.setText(f"{selected_directory}")

    def getHLayouts(self, label_1, label_2):
        lab1 = QLabel(str(label_1), self)
        lab2 = QLabel(str(label_2), self)
        lab2.setFixedWidth(900)
        self.hLayout = QHBoxLayout()
        self.hLayout.addWidget(lab1)
        self.hLayout.addWidget(lab2)

        return self.hLayout

    def runCameras(self, cam_params=("Mono8", 40, 1000)):
        self.counter += 1
        # Open the cameras
        self.cameras = []
        self.raw_writer_arr = [None] * n_cams
        self.ffmpeg_arr = [None] * n_cams
        pix_format, frameRate, expTime = cam_params

        tlFactory = pylon.TlFactory.GetInstance()
        devices = tlFactory.EnumerateDevices()

        for i in range(len(devices)):
            camera = pylon.InstantCamera(tlFactory.CreateDevice(devices[i]))
            self.cameras.append(camera)
            camera.Open()

            # Start recording from the cameras
            camera.AcquisitionFrameRateEnable.SetValue(True)
            camera.AcquisitionFrameRateAbs.SetValue(frameRate)
            camera.AcquisitionMode.SetValue("Continuous")
            camera.PixelFormat.SetValue(pix_format)
            camera.ExposureTimeAbs.SetValue(expTime)
            camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        # Get the resulting frame rate
        resultingFR = camera.ResultingFrameRateAbs.GetValue()
        self.paramsVLayout = QVBoxLayout()
        if self.counter == 1:
            self.fr_line = QLineEdit("Frame Rate: 20")
            self.pf_line = QLineEdit("Pixel Format: Mono8")
            self.et_line = QLineEdit("Exposure Time: 1000")
            current_dir = os.getcwd()
            self.fileLoc_line = QLineEdit(f"{current_dir}")
            self.fr_line.setFixedWidth(200)
            self.pf_line.setFixedWidth(200)
            self.et_line.setFixedWidth(200)
            self.fileLoc_line.setFixedWidth(500)
            self.fr_line.setReadOnly(True)
            self.pf_line.setReadOnly(True)
            self.et_line.setReadOnly(True)
            self.fileLoc_line.setReadOnly(True)
            self.paramsVLayout.addWidget(self.fr_line)
            self.paramsVLayout.addWidget(self.pf_line)
            self.paramsVLayout.addWidget(self.et_line)
            self.paramsVLayout.addWidget(self.fileLoc_line)
            self.totalLayout.addLayout(self.paramsVLayout)

        elif self.counter > 1:
            self.fr_line.setText(f"Frame Rate: {resultingFR}")
            self.pf_line.setText(f"Pixel Format: {pix_format}")
            self.et_line.setText(f"Exposure Time: {expTime}")

    def getCameraParams(self):
        cam_object = self.cameras[0]
        self.pixel_formats = cam_object.PixelFormat.Symbolics
        self.settingsWindow = SettingsWindow()

        for format_name in self.pixel_formats:
            self.settingsWindow.combo_box.addItem(format_name)

        self.settingsWindow.show()
        self.settingsWindow.cam_parameters.connect(self.runCameras)

    # First point of contact after the button click
    def toggleRecording(self, camera_idx, obj):
        self.is_recording[camera_idx] = True if isinstance(obj, QComboBox) else False

        flag = self.is_recording[camera_idx]
        record_method = str(self.combo_boxes[camera_idx].currentText())

        if flag:
            if record_method == "Raw_writer":
                raw_writer = Raw_Writer(f"cam_{camera_idx}_output.npz")
                self.raw_writer_arr[camera_idx] = raw_writer
            else:
                ffmpeg_writer = FFMPEG_VideoWriter(
                    f"cam_{camera_idx}_output_t2.avi",
                    (
                        self.cameras[camera_idx].Height.Value,
                        self.cameras[camera_idx].Width.Value,
                    ),
                    fps=25,
                )
                self.ffmpeg_arr[camera_idx] = ffmpeg_writer

            self.recordSignal.emit((camera_idx, flag))
            self.labels[camera_idx].setStyleSheet("border: 3px solid red;")

        else:
            self.recordSignal.emit((camera_idx, flag))
            self.labels[camera_idx].setStyleSheet("border: None;")
            self.combo_boxes[camera_idx].setCurrentIndex(-1)

    def closeEvent(self, event):
        widgetList = QApplication.topLevelWidgets()
        numWindows = len(widgetList)
        if numWindows >= 1:
            event.accept()
        else:
            event.ignore()

    # Starts/stops corresponding camera's recording thread
    @Slot(tuple)
    def startRecordingThread(self, tup_val):
        camera_idx, recordFlag = tup_val

        if self.recording_threads[camera_idx] is None:
            self.recording_threads[camera_idx] = QThread()

        self.recording_threads[camera_idx].run = lambda: self.recordFrames(
            camera_idx, recordFlag
        )
        self.recording_threads[camera_idx].start()
        time.sleep(0.02)

        if recordFlag is False:
            self.recording_threads[camera_idx].quit()
            self.recording_threads[camera_idx] = None

    # Connects to getArray method to record frames
    @Slot()
    def recordFrames(self, camera_idx, recFlag):
        name = f"array_signal_{camera_idx}"
        sig_connect = getattr(self.recordingAgent, name)

        if recFlag:
            sig_connect.connect(self.getArray)

        else:
            sig_connect.disconnect(self.getArray)

    # Receives the image array from the cameras and records
    @Slot(tuple)
    def getArray(self, tup):
        arr_val, camera_idx, file_path = tup
        record_str = str(self.combo_boxes[camera_idx].currentText())
        if record_str == "Raw_writer":
            self.raw_writer_arr[camera_idx].write_frame(arr_val, file_path)
        elif record_str == "FFmpeg":
            self.ffmpeg_arr[camera_idx].write_frame(arr_val, file_path)
        else:
            return

    def updateStreams(self):
        # Get the latest frames from the cameras

        # converter = pylon.ImageFormatConverter()
        # converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        # converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        # converter = pylon.ImageFormatConverter()
        # converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        # converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        rawGrabResult = []

        for i, camera in enumerate(self.cameras):
            grabResult = camera.RetrieveResult(
                5000, pylon.TimeoutHandling_ThrowException
            )
            rawGrabResult.append(grabResult)

            # if grabResult.GrabSucceeded():
            #     temp = converter.Convert(grabResult)
            #     grabResultArr.append(temp)
            # if grabResult.GrabSucceeded():
            #     temp = converter.Convert(grabResult)
            #     grabResultArr.append(temp)

        images = []

        for i, _ in enumerate(rawGrabResult):
            imgVal = rawGrabResult[i].Array
            imgNum = rawGrabResult[i].GetImageNumber()

            name = f"array_signal_{i}"
            sig = getattr(self.recordingAgent, name)
            image = QImage(
                imgVal, imgVal.shape[1], imgVal.shape[0], QImage.Format_Grayscale8
            )
            images.append(image)
            sig.emit((imgVal, i, self.fileLocation))

        for item in rawGrabResult:
            item.Release()

        for i, label in enumerate(self.labels):
            pxmap = QPixmap.fromImage(images[i])
            label.setPixmap(pxmap) #set the pixmap for the labels


if __name__ == "__main__":
    app = QApplication(sys.argv)
    stream = CameraStream()
    stream.show()
    sys.exit(app.exec())
