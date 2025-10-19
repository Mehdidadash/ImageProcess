#capture.py
import sys
import time
import CameraWorkerClass
import threading
from ctypes import *
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.uic import loadUi
from datetime import datetime
import os
sys.path.append("../MvImport")

from CameraParams_header import *
from MvCameraControl_class import *

# Helper function to convert error codes to human-readable messages
def get_error_message(error_code):
    error_messages = {
        0x80000000: "General error",
        0x80000001: "Invalid handle",
        0x80000002: "Invalid parameter",
        0x80000003: "Not supported",
        0x80000004: "No data",
        0x80000005: "Timeout",
        0x80000006: "Resource allocation failed",
        0x80000007: "Access denied",
        0x80000008: "Device not found",
        0x80000009: "Device is already opened",
        0x8000000A: "Device is not opened",
        0x8000000B: "Device is not started",
        0x8000000C: "Device is already started",
        0x8000000D: "Device is not stopped",
        0x8000000E: "Device is already stopped",
        0x8000000F: "Buffer is too small",
        0x80000010: "Invalid pointer",
        0x80000011: "Invalid value",
        0x80000012: "Invalid call",
        0x80000013: "Invalid buffer",
        0x80000014: "Invalid frame",
        0x80000015: "Invalid address",
        0x80000016: "Invalid length",
        0x80000017: "Invalid type",
        0x80000018: "Invalid access",
        0x80000019: "Invalid index",
        0x8000001A: "Invalid size",
        0x8000001B: "Invalid alignment",
        0x8000001C: "Invalid format",
        0x8000001D: "Invalid configuration",
        0x8000001E: "Invalid state",
        0x8000001F: "Invalid operation",
    }
    return error_messages.get(error_code, "Unknown error")


    log_signal = pyqtSignal(str)  # Signal to send log messages to the main thread

    def __init__(self):
        super().__init__()
        self.camera = None
        self.running = False
        self.max_retries_value = 5
        self.delay_between_retries_value = 0.05

    def set_parameters(self, max_retries, delay_between_retries):
        """Sets the parameters for the camera worker."""
        self.max_retries_value = max_retries
        self.delay_between_retries_value = delay_between_retries

    def run_camera(self):
        """Runs the camera operations."""
        # Initialize camera
        self.camera = MvCamera()
        device_list = MV_CC_DEVICE_INFO_LIST()
        ret = self.camera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, device_list)
        if ret != 0:
            self.log_signal.emit(f"Failed to enumerate devices. Error code: {hex(ret)}")
            return

        if device_list.nDeviceNum == 0:
            self.log_signal.emit("No devices found.")
            return

        # Open the first camera
        st_device_info = cast(device_list.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
        ret = self.camera.MV_CC_CreateHandle(st_device_info)
        if ret != 0:
            self.log_signal.emit(f"Failed to create handle. Error code: {hex(ret)}")
            return

        ret = self.camera.MV_CC_OpenDevice()
        if ret != 0:
            self.log_signal.emit(f"Failed to open device. Error code: {hex(ret)}")
            return

        self.log_signal.emit("Camera opened successfully.")

        # Start grabbing
        ret = self.camera.MV_CC_StartGrabbing()
        if ret != 0:
            self.log_signal.emit(f"Failed to start grabbing. Error code: {hex(ret)}")
            return

        self.log_signal.emit("Grabbing started. Waiting for Line0 to go high...")

        # Monitor Line0 and capture images
        last_line0_state = False
        try:
            while self.running:  # Loop while the running flag is True
                # Get current state of Line0
                stBool = c_bool(False)
                ret = self.camera.MV_CC_GetBoolValue("LineStatus", stBool)
                if ret != 0:
                    self.log_signal.emit(f"Failed to get Line0 status. Error code: {hex(ret)}")
                    break

                current_line0_state = stBool.value

                # Check for rising edge (low to high transition)
                if not last_line0_state and current_line0_state:
                    self.log_signal.emit("Rising edge detected on Line0. Capturing image...")

                    # Grab a valid frame
                    stOutFrame = self.get_valid_frame()
                    if stOutFrame:
                        # Save the image
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        file_path = f"image_{timestamp}.bmp"
                        self.save_image_as_bmp(stOutFrame.stFrameInfo, stOutFrame.pBufAddr, file_path)

                        # Free the frame buffer
                        self.camera.MV_CC_FreeImageBuffer(stOutFrame)

                last_line0_state = current_line0_state
                time.sleep(0.01)  # Small delay to avoid busy-waiting

        except Exception as e:
            self.log_signal.emit(f"Error: {e}")
        finally:
            # Stop grabbing and close the camera
            if self.camera:
                self.camera.MV_CC_StopGrabbing()
                self.camera.MV_CC_CloseDevice()
                self.camera.MV_CC_DestroyHandle()
                self.log_signal.emit("Camera closed.")

    def get_valid_frame(self):
        """Attempts to grab a valid frame, retrying if necessary."""
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))

        for attempt in range(self.max_retries_value):
            ret = self.camera.MV_CC_GetImageBuffer(stOutFrame, 1000)  # Timeout of 1000 ms
            if ret == 0 and stOutFrame.stFrameInfo.nWidth > 0 and stOutFrame.stFrameInfo.nHeight > 0:
                # Valid frame grabbed
                self.log_signal.emit(f"Frame grabbed successfully on attempt {attempt + 1}.")
                return stOutFrame
            else:
                # Frame grab failed
                self.log_signal.emit(f"Frame grab failed on attempt {attempt + 1}. Return code: {hex(ret)}")
                time.sleep(self.delay_between_retries_value)  # Delay between retries

        # If no valid frame is grabbed after retries
        self.log_signal.emit(f"Failed to get valid frame after {self.max_retries_value} retries.")
        return None

    def save_image_as_bmp(self, frame_info, buffer, file_path):
        """Saves the captured image as a BMP file."""
        stSaveParam = MV_SAVE_IMAGE_TO_FILE_PARAM_EX()
        stSaveParam.enPixelType = frame_info.enPixelType
        stSaveParam.nWidth = frame_info.nWidth
        stSaveParam.nHeight = frame_info.nHeight
        stSaveParam.nDataLen = frame_info.nFrameLen
        stSaveParam.pData = cast(buffer, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Bmp
        stSaveParam.pcImagePath = ctypes.create_string_buffer(file_path.encode('ascii'))
        stSaveParam.iMethodValue = 1

        ret = self.camera.MV_CC_SaveImageToFileEx(stSaveParam)
        if ret == 0:
            self.log_signal.emit(f"Image saved successfully: {file_path}")
        else:
            self.log_signal.emit(f"Failed to save image. Error code: {hex(ret)}")

# Main application window
class CameraApp(QMainWindow):
    def __init__(self):
        super(CameraApp, self).__init__()
        loadUi("CameraAppUI.ui", self)  # Load the UI file

        # Initialize attributes
        self.selected_folder = ""  # To store the selected folder path

        # # Folder Selection button
        self.pB_SelectFolder.clicked.connect(self.select_folder)

        # Start and Stop buttons
        self.pB_StartCamera.clicked.connect(self.start_camera)
        self.pB_StopCamera.clicked.connect(self.stop_camera)

        # Quit button
        self.pB_Quit.clicked.connect(self.close)


        # Camera worker and thread
        self.camera_worker = CameraWorkerClass.CameraWorker()
        self.camera_thread = threading.Thread(target=self.camera_worker.run_camera, daemon=True)

        # Connect the log signal and count signal to the log method
        self.camera_worker.log_signal.connect(self.log_to_output)
        self.camera_worker.image_saved_signal.connect(self.check_image_count)  # Connect signal to check image count


    def start_camera(self):
        #Starts the camera in a separate thread
        if self.camera_worker.running:
            self.self.log_to_output("Camera is already running.")
            return

        try:
            # Validate and get values from input fields
            max_retries = int(self.tx_MaxRetries.text())
            delay_between_retries = float(self.tx_Delay.text())

            if max_retries <= 0 or delay_between_retries <= 0:
                raise ValueError("Values must be greater than 0.")
        except ValueError as e:
            self.self.log_to_output(f"Invalid input: {e}")
            return

        # Set parameters for the camera worker
        self.camera_worker.set_parameters(max_retries, delay_between_retries)

        # Pass the selected folder to the camera worker
        self.camera_worker.set_save_folder(self.selected_folder)

        # Disable the start button and enable the stop button
        self.pB_StartCamera.setEnabled(False)
        self.pB_StopCamera.setEnabled(True)

        # Start the camera in a separate thread
        self.camera_worker.running = True
        self.camera_thread = threading.Thread(target=self.camera_worker.run_camera, daemon=True)  # Create a new thread
        self.camera_thread.start()

    def stop_camera(self):
        """Stops the camera and allows reconfiguration."""
        if not self.camera_worker.running:
            self.log("Camera is not running.")
            return

        # Set the running flag to False to stop the camera loop
        self.camera_worker.running = False

            # Wait for the camera thread to finish if it exists
        if hasattr(self, 'camera_thread') and self.camera_thread.is_alive():
            self.camera_thread.join()

        # Enable the start button and disable the stop button
        self.pB_StartCamera.setEnabled(True)
        self.pB_StopCamera.setEnabled(False)

        self.log_to_output("Camera stopped. You can reconfigure and start again.")

    def select_folder(self):
        """Opens a dialog to select a folder."""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.selected_folder = folder_path  # Store the selected folder path
            self.log_to_output(f"Selected folder: {folder_path}")
        else:
            self.log_to_output("No folder selected.")

    def log_to_output(self, message):
        current_time = datetime.now().strftime("%H:%M")  # Get current time in HH:MM format
        formatted_message = f"[{current_time}] - {message}"  # Prepend the timestamp to the message
        self.tE_Outputs.append(formatted_message)  # Append the formatted message to the TextEdit
        self.tE_Outputs.append("=" * 50)  # Append the formatted message to the TextEdit

    def check_image_count(self, folder_path):
        """Checks the number of images in the folder and triggers a function if the count reaches 3."""
        if not folder_path:
            folder_path = os.getcwd()  # Use the current working directory if no folder is provided
            self.log_to_output(f"Save folder is not set. Using the current directory to count number of images: {folder_path}")

        # Count the number of image files in the folder
        image_files = [f for f in os.listdir(folder_path) if f.endswith(".bmp")]
        image_count = len(image_files)

        self.log_to_output(f"Number of images in folder: {image_count}")

        # Trigger a new function if the count reaches 3
        if image_count == 3:
            self.log_to_output("3 images captured. Triggering the process ...")
            self.process_images(self, folder_path, image_files)
            
    def process_images(self, folder_path, image_files):
        """Processes the images in the folder."""
        self.log_to_output("Processing images...")

        # Create 'ProcessFolder' inside the given folder_path if it doesn't exist
        process_folder_path = os.path.join(folder_path, "ProcessFolder")
        if not os.path.exists(process_folder_path):
            os.makedirs(process_folder_path)
            self.log_to_output(f"'ProcessFolder' created at: {process_folder_path}")

        # Create a unique folder inside 'ProcessFolder'
        unique_folder_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_folder_path = os.path.join(process_folder_path, unique_folder_name)
        os.makedirs(unique_folder_path)
        self.log_to_output(f"Unique folder created: {unique_folder_path}")

        # Move the image files to the unique folder
        for image_file in image_files:
            source_path = os.path.join(folder_path, image_file)
            destination_path = os.path.join(unique_folder_path, image_file)
            if os.path.exists(source_path):
                os.rename(source_path, destination_path)
                self.log_to_output(f"Moved {image_file} to {unique_folder_path}")
            else:
                self.log_to_output(f"File not found: {image_file}")

        self.log_to_output("Image processing completed.")