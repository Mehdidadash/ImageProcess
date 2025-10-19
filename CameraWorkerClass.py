#capture.py
import sys
import time
import threading
from ctypes import *
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
import os
sys.path.append("/MvImport")

from CameraParams_header import *
from MvCameraControl_class import *

class CameraWorker(QObject):
    log_signal = pyqtSignal(str)  # Signal to send log messages to the main thread
    image_saved_signal = pyqtSignal(str) # Signal to notify when an image is saved

    def __init__(self):
        super().__init__()
        self.camera = None
        self.running = False
        self.max_retries_value = 5
        self.delay_between_retries_value = 0.05
        self.save_folder = ""  # To store the folder path for saving images

    def set_parameters(self, max_retries, delay_between_retries):
        """Sets the parameters for the camera worker."""
        self.max_retries_value = max_retries
        self.delay_between_retries_value = delay_between_retries

    def set_save_folder(self, folder_path):
        """Sets the folder path for saving images."""
        self.save_folder = folder_path

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
        if not self.save_folder:
            current_directory = os.getcwd()
            self.log_signal.emit(f"Save folder is not set. Using the current directory: {current_directory}")
            full_file_path = os.path.join(current_directory, file_path)  # Save in the current directory
        else:
            full_file_path = f"{self.save_folder}/{file_path}"  # Save in the selected folder




        stSaveParam = MV_SAVE_IMAGE_TO_FILE_PARAM_EX()
        stSaveParam.enPixelType = frame_info.enPixelType
        stSaveParam.nWidth = frame_info.nWidth
        stSaveParam.nHeight = frame_info.nHeight
        stSaveParam.nDataLen = frame_info.nFrameLen
        stSaveParam.pData = cast(buffer, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Bmp
        stSaveParam.pcImagePath = ctypes.create_string_buffer(full_file_path.encode('ascii'))
        stSaveParam.iMethodValue = 1

        ret = self.camera.MV_CC_SaveImageToFileEx(stSaveParam)
        if ret == 0:
            self.log_signal.emit(f"Image saved successfully: {full_file_path}")
            self.image_saved_signal.emit(self.save_folder)  # Emit signal with the folder path
        else:
            self.log_signal.emit(f"Failed to save image. Error code: {hex(ret)}")
