#capture.py
import sys
import time
import re
import CameraWorkerClass
import ImageProcessLib as IPL
import threading
from ctypes import *
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem, QSizePolicy
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QGraphicsScene
from PyQt5.uic import loadUi
from datetime import datetime
from PyQt5.QtGui import QPixmap, QBrush, QColor
from PyQt5.QtCore import Qt
import os
import glob
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
sys.path.append("/MvImport")

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
        self.scene = QGraphicsScene()  # Create a QGraphicsScene for the graphicsView
        self.graphicsView.setScene(self.scene)  # Set the scene to the graphicsView

        # # Folder Selection button
        self.pB_SelectFolder.clicked.connect(self.select_folder)
        self.pB_BrowseFolder.clicked.connect(self.browse_folder)
        self.pB_StartProcess.clicked.connect(self.start_processing)
        self.pB_TestRS485.clicked.connect(self.test_rs485_connection)
        # Start and Stop buttons
        self.pB_StartCamera.clicked.connect(self.start_camera)
        self.pB_StopCamera.clicked.connect(self.stop_camera)

        # Quit button
        self.pB_Quit.clicked.connect(self.close)

        # Add a table to display *_diff.txt results under Quit
        # We'll create it programmatically and place it below existing widgets in the layout
        # If the UI file already has a placeholder, this will simply set up the table object
        self.diff_table = QTableWidget(self)
        self.diff_table.setColumnCount(2)
        self.diff_table.setHorizontalHeaderLabels(["Index", "Diff Value"])
        # Optionally set a reasonable initial size
        self.diff_table.setMinimumHeight(150)
        # Make table expand vertically to fill the area under Quit; keep Preferred width to match Quit
        sp = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sp.setHorizontalStretch(0)
        sp.setVerticalStretch(1)
        self.diff_table.setSizePolicy(sp)

        # Insert the table into the Inputs/Controls layout under the Quit button
        try:
            # The layout object created by loadUi is named 'Layout_InputsAndControls'
            if hasattr(self, 'Layout_InputsAndControls'):
                # try to find the Quit button position and insert after it
                try:
                    # find index of pB_Quit in the layout
                    idx = None
                    for i in range(self.Layout_InputsAndControls.count()):
                        item = self.Layout_InputsAndControls.itemAt(i)
                        if item and item.widget() is not None and item.widget().objectName() == 'pB_Quit':
                            idx = i
                            break

                    if idx is not None:
                        # try inserting before the bottom spacer if present
                        insert_index = idx + 1
                        # if the last item is a spacer, insert before it
                        count = self.Layout_InputsAndControls.count()
                        if count > 0:
                            last_item = self.Layout_InputsAndControls.itemAt(count - 1)
                            try:
                                if last_item.spacerItem() is not None:
                                    insert_index = count - 1
                            except Exception:
                                pass
                        self.Layout_InputsAndControls.insertWidget(insert_index, self.diff_table, 1)
                    else:
                        self.Layout_InputsAndControls.addWidget(self.diff_table)
                except Exception:
                    self.Layout_InputsAndControls.addWidget(self.diff_table)
            else:
                # fall back: append to the verticalLayoutWidget if present
                try:
                    self.verticalLayoutWidget.layout().addWidget(self.diff_table)
                except Exception:
                    pass
        except Exception as e:
            # Don't crash UI init if insertion fails
            self.log_to_output(f"Failed to insert diff table into layout: {e}")

        # Camera worker and thread
        self.camera_worker = CameraWorkerClass.CameraWorker()
        self.camera_thread = threading.Thread(target=self.camera_worker.run_camera, daemon=True)

        # Connect the log signal and count signal to the log method
        self.camera_worker.log_signal.connect(self.log_to_output)
        self.camera_worker.image_saved_signal.connect(self.check_image_count)  # Connect signal to check image count



    def test_rs485_connection(self):
        import serial
        try:
            ser = serial.Serial('COM2', 9600, timeout=1)
            msg = f"Connected to {ser.portstr}"
            ser.close()
        except Exception as e:
            msg = f"RS485 Error: {e}"
        self.log_to_output(msg)

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

    def browse_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.selected_folder = folder_path
            self.log_to_output(f"Selected folder: {folder_path}")
        else:
            self.log_to_output("No folder selected.")

    def start_processing(self):
        if not self.selected_folder:
            self.log_to_output("No folder selected for processing.")
            return

        selected_type = None
        if self.rb_SX.isChecked():
            selected_type = "SX"
        elif self.rb_S1.isChecked():
            selected_type = "S1"
        elif self.rb_S2.isChecked():
            selected_type = "S2"
        elif self.rb_F1.isChecked():
            selected_type = "F1"
        elif self.rb_F2.isChecked():
            selected_type = "F2"
        elif self.rb_F3.isChecked():
            selected_type = "F3"

        if not selected_type:
            self.log_to_output("No type selected for comparison.")
            return

        self.log_to_output(f"Processing images in folder: {self.selected_folder} with type: {selected_type}")

        try:
            # Call the MAIN function from ImageProcessLib
            plot_output_path, closest_filetype = IPL.MAIN(self.selected_folder)

            # Try to resolve returned path (IPL.MAIN may return a relative filename)
            resolved = self.resolve_plot_path(plot_output_path, search_folder=self.selected_folder)
            if not resolved:
                self.log_to_output(f"Plot not found after IPL.MAIN returned: {plot_output_path}")
            else:
                plot_output_path = resolved

            # Log the results
            self.log_to_output(f"Processing completed. Closest file type: {closest_filetype}")
            self.log_to_output(f"Plot saved at: {plot_output_path}")

            # Display the plot in the UI
            self.display_image(plot_output_path)

        except Exception as e:
            self.log_to_output(f"Error during processing: {e}")

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

        # Display the latest image in the graphicsView
        if image_files:
            latest_image = os.path.join(folder_path, image_files[-1])  # Get the most recent image
            self.display_image(latest_image)

        # Trigger a new function if the count reaches 3
        if image_count == 3:
            self.log_to_output("3 images captured. Triggering the process ...")
            self.process_images(folder_path, image_files)
            
    def process_images(self, folder_path, image_files):
        """Processes the images by moving them into a uniquely named folder inside 'ProcessFolder' in the current directory."""
        self.log_to_output("Processing images...")

        # Get the current working directory
        current_dir = os.getcwd()

        # Create 'ProcessFolder' inside the current directory if it doesn't exist
        process_folder_path = os.path.join(current_dir, "ProcessFolder")
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
            source_path = os.path.join(folder_path, image_file)  # Source path is based on the provided folder_path
            destination_path = os.path.join(unique_folder_path, image_file)  # Destination is in the unique folder
            if os.path.exists(source_path):
                try:
                    os.rename(source_path, destination_path)
                    self.log_to_output(f"Moved {image_file} to {unique_folder_path}")
                except PermissionError:
                    self.log_to_output(f"Permission denied: Unable to move {image_file}. Try running as administrator.")
                except Exception as e:
                    self.log_to_output(f"Failed to move {image_file}: {e}")
            else:
                self.log_to_output(f"File not found: {image_file}")

        # Process images and get closest filetype
        plot_output_path, closest_filetype = IPL.MAIN(unique_folder_path)

        # resolve plot path (IPL.MAIN may return relative name)
        resolved = self.resolve_plot_path(plot_output_path, search_folder=unique_folder_path)
        if not resolved:
            self.log_to_output(f"Plot not found after IPL.MAIN returned: {plot_output_path}")
        else:
            plot_output_path = resolved

        # Rename the folder to append the closest type
        new_folder_name = unique_folder_name + f"_{closest_filetype}"
        new_folder_path = os.path.join(process_folder_path, new_folder_name)
        try:
            os.rename(unique_folder_path, new_folder_path)
            self.log_to_output(f"Renamed folder to: {new_folder_path}")
        except Exception as e:
            self.log_to_output(f"Failed to rename folder: {e}")
        # Update path for further use
        unique_folder_path = new_folder_path

        # Try to resolve plot path again now that folder may have been renamed
        resolved_after_rename = self.resolve_plot_path(plot_output_path, search_folder=unique_folder_path)
        if resolved_after_rename:
            plot_output_path = resolved_after_rename
        else:
            # Final fallback: search the ProcessFolder parent for any matching pngs using the unique folder prefix
            try:
                parent_process = os.path.dirname(unique_folder_path)
                prefix = os.path.basename(unique_folder_path).split('_')[0]
                patterns = [f"{prefix}*comparison_plot*.png", f"{prefix}*_plot.png", f"{prefix}*.png"]
                found = None
                for p in patterns:
                    matches = glob.glob(os.path.join(parent_process, "**", p), recursive=True)
                    if matches:
                        found = matches[0]
                        break
                if found:
                    self.log_to_output(f"Found plot via final fallback: {found}")
                    plot_output_path = found
                else:
                    self.log_to_output(f"Final fallback: no plot found for prefix {prefix} in {parent_process}")
            except Exception as e:
                self.log_to_output(f"Error during final fallback search: {e}")

        closest_filetype_integer = self.map_filetype_to_integer(closest_filetype)
        # Read HMI/PLC variable (e.g., M501) at process start and store in self.IS_SX
        try:
            # address 1 corresponds to d4; unit/slave id 2 for your HMI (107-ev configured as unit 2)
            self.IS_SX = self.read_hmi_register(address=1, unit=2, port='COM2', baudrate=9600)
        except Exception:
            # If read fails, set to None and continue
            self.IS_SX = None

        ###
        # Write the integer value to the HMI register (report result of image processing)
        try:
            self.write_to_hmi_register(closest_filetype_integer)
        except Exception as e:
            self.log_to_output(f"Failed to write result to HMI: {e}")
        ###

        self.log_to_output(f"Process Is completed, closest file type is:  {closest_filetype}")
        self.display_image(plot_output_path)

        # Try to locate any *_diff.txt file in the processed folder and display it
        try:
            # use unique_folder_path which points to the renamed folder
            diff_matches = glob.glob(os.path.join(unique_folder_path, "*_diff.txt"))
            if diff_matches:
                # pick the first one
                self.display_diff_file(diff_matches[0])
            else:
                # also try searching parent ProcessFolder as fallback
                parent_process = os.path.dirname(unique_folder_path)
                diff_matches = glob.glob(os.path.join(parent_process, "**", "*_diff.txt"), recursive=True)
                if diff_matches:
                    self.display_diff_file(diff_matches[0])
        except Exception as e:
            self.log_to_output(f"Error searching for diff files: {e}")

    def write_to_hmi_register(self, value):

        # Configuration (adjust as needed)
        PORT = 'COM2'        # Confirm your COM port
        BAUDRATE = 9600      # Match HMI settings
        SLAVE_ID = 2         # HMI slave address (default=1)
        S0_ADDRESS = 0       # Correct address for S0 (now confirmed!)

        client = ModbusSerialClient(
        port=PORT,
        baudrate=BAUDRATE,
        parity='E',
        stopbits=1,
        bytesize=8,
        timeout=3
    )
    
        try:
            if not client.connect():
                self.log_to_output(f"Modbus connection failed on {PORT}")
                return

            # Validate value range for a single 16-bit register
            try:
                ival = int(value)
            except Exception:
                self.log_to_output(f"Invalid value for register: {value}")
                return

            if not (0 <= ival <= 0xFFFF):
                self.log_to_output(f"Value {ival} out of range for single register (0..65535). Aborting write.")
                return

            self.log_to_output(f"Writing {ival} to S0 (address {S0_ADDRESS}) on slave {SLAVE_ID}...")

            # Attempt to call write_register with the correct keyword for this pymodbus version
            try:
                from inspect import signature
                sig = signature(client.write_register)
                if 'unit' in sig.parameters:
                    response = client.write_register(S0_ADDRESS, ival, unit=SLAVE_ID)
                elif 'slave' in sig.parameters:
                    response = client.write_register(S0_ADDRESS, ival, slave=SLAVE_ID)
                else:
                    # positional fallback
                    response = client.write_register(S0_ADDRESS, ival)
            except Exception:
                # Last resort positional call
                response = client.write_register(S0_ADDRESS, ival)

            # Some pymodbus responses use isError(), others use None or boolean
            try:
                if response is None:
                    self.log_to_output("No response from write_register (response is None)")
                elif hasattr(response, 'isError') and response.isError():
                    self.log_to_output(f"Modbus write error: {response}")
                else:
                    self.log_to_output("Success! Value written to S0.")
            except Exception as e:
                self.log_to_output(f"Unexpected response from write_register: {e}")
        except ModbusException as e:
            self.log_to_output(f"Communication error: {e}")
        finally:
            try:
                client.close()
            except Exception:
                pass

    def read_hmi_register(self, address=1, unit=2, port='COM2', baudrate=9600, timeout=3):
        """Read a single holding register from the HMI/PLC over Modbus RTU and return its integer value.

        Defaults assume register 501 (M501), slave/unit id 2, COM2, 9600 baud. Adjust when needed.
        Returns integer value on success or raises an exception on failure.
        """
        client = ModbusSerialClient(
            port=port,
            baudrate=baudrate,
            parity='E',
            stopbits=1,
            bytesize=8,
            timeout=timeout
        )

        try:
            if not client.connect():
                raise ConnectionError(f"Modbus connect failed on {port}")

            # Try to call read_holding_registers with the appropriate keyword for installed pymodbus
            response = None
            from inspect import signature
            try:
                sig = signature(client.read_holding_registers)
                if 'unit' in sig.parameters:
                    response = client.read_holding_registers(address, count=1, unit=unit)
                elif 'slave' in sig.parameters:
                    response = client.read_holding_registers(address, count=1, slave=unit)
                else:
                    # positional fallback
                    response = client.read_holding_registers(address, 1)
            except Exception:
                # If signature introspection fails for any reason, try common call patterns
                try:
                    response = client.read_holding_registers(address, 1, unit)
                except TypeError:
                    try:
                        response = client.read_holding_registers(address, 1, unit=unit)
                    except Exception:
                        response = client.read_holding_registers(address, 1)

            if response is None:
                raise IOError(f"No response reading register {address} (unit {unit})")

            if hasattr(response, 'isError') and response.isError():
                raise IOError(f"Modbus error reading register {address}: {response}")

            # Extract register value in a version-agnostic way
            if hasattr(response, 'registers') and len(response.registers) > 0:
                val = int(response.registers[0])
            else:
                # older/newer variants
                try:
                    val = int(response.getRegister(0))
                except Exception:
                    # Try to interpret response as simple tuple/list
                    try:
                        if isinstance(response, (list, tuple)) and len(response) > 0:
                            val = int(response[0])
                        else:
                            raise IOError(f"Unexpected Modbus response format: {response}")
                    except Exception:
                        raise IOError(f"Unexpected Modbus response format: {response}")

            self.log_to_output(f"Read register {address} (unit {unit}) -> {val}")
            return val

        except Exception as e:
            self.log_to_output(f"Failed to read HMI register {address}: {e}")
            raise
        finally:
            try:
                client.close()
            except Exception:
                pass

    def display_image(self, image_path):
        """Displays the captured image in the graphicsView. Waits briefly for the file to be written and tries multiple loaders."""
        if not image_path:
            self.log_to_output("No image path provided to display_image.")
            return

        timeout = 8.0  # seconds
        interval = 0.2
        waited = 0.0

        # Wait for file to exist and be non-empty
        while waited < timeout:
            if os.path.exists(image_path):
                try:
                    size = os.path.getsize(image_path)
                except Exception as e:
                    self.log_to_output(f"Could not get file size: {e}")
                    size = 0
                if size > 0:
                    break
            time.sleep(interval)
            waited += interval

        if not os.path.exists(image_path):
            self.log_to_output(f"Image file does not exist: {image_path}")
            return
        try:
            size = os.path.getsize(image_path)
        except Exception as e:
            self.log_to_output(f"Could not get file size: {e}")
            size = 0
        self.log_to_output(f"Image exists. size={size} bytes, path={image_path}")

        # Try to read file bytes (better when the file gets locked by another process)
        data = None
        try:
            with open(image_path, "rb") as f:
                data = f.read()
        except Exception as e:
            self.log_to_output(f"Failed to open image file for reading: {e}")

        pixmap = QPixmap()
        loaded = False

        # Primary: try loadFromData if we have bytes
        if data:
            try:
                loaded = pixmap.loadFromData(data)
                if loaded and not pixmap.isNull():
                    self.log_to_output("Loaded image with QPixmap.loadFromData()")
            except Exception as e:
                self.log_to_output(f"loadFromData failed: {e}")
                loaded = False

        # Secondary: try direct load from path
        if not loaded:
            try:
                loaded = pixmap.load(image_path)
                if loaded and not pixmap.isNull():
                    self.log_to_output("Loaded image with QPixmap.load(path)")
            except Exception as e:
                self.log_to_output(f"QPixmap.load(path) failed: {e}")
                loaded = False

        # Fallback: try QImage then convert
        if (not loaded) or pixmap.isNull():
            try:
                from PyQt5.QtGui import QImage
                img = QImage()
                if data:
                    ok = img.loadFromData(data)
                else:
                    ok = img.load(image_path)
                if ok and not img.isNull():
                    pixmap = QPixmap.fromImage(img)
                    loaded = True
                    self.log_to_output("Loaded image via QImage -> QPixmap")
                else:
                    self.log_to_output("QImage could not load the image")
            except Exception as e:
                self.log_to_output(f"QImage fallback failed: {e}")

        # Optional diagnostic using PIL to verify image validity (if installed)
        if (not loaded) and data:
            try:
                from io import BytesIO
                try:
                    from PIL import Image
                    bio = BytesIO(data)
                    im = Image.open(bio)
                    im.verify()  # will raise if image is broken
                    # reload to get a usable image
                    bio.seek(0)
                    im = Image.open(bio).convert("RGBA")
                    # convert PIL image to QImage
                    from PyQt5.QtGui import QImage
                    qim = QImage(im.tobytes("raw", "RGBA"), im.width, im.height, QImage.Format_RGBA8888)
                    pixmap = QPixmap.fromImage(qim)
                    loaded = True
                    self.log_to_output("Validated and loaded image via PIL -> QImage")
                except ImportError:
                    self.log_to_output("PIL not available; skipping PIL validation")
                except Exception as e:
                    self.log_to_output(f"PIL validation failed: {e}")
            except Exception:
                pass

        if (not loaded) or pixmap.isNull():
            self.log_to_output(f"Failed to load image: {image_path}")
            return

        # Display
        try:
            self.scene.clear()
            self.scene.addPixmap(pixmap)
            self.graphicsView.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            # Force a UI update
            try:
                self.graphicsView.viewport().update()
            except Exception:
                pass
            self.log_to_output(f"Displayed image: {image_path}")
        except Exception as e:
            self.log_to_output(f"Failed to display pixmap: {e}")

    def resolve_plot_path(self, plot_output_path, search_folder=None):
        """Make returned plot path usable:
           - accept absolute path
           - try as relative to search_folder
           - fallback: search for '*comparison_plot*.png' (or any .png) in search_folder
        """
        if not plot_output_path:
            self.log_to_output("resolve_plot_path: no path returned")
            return None

        # if absolute and exists, return it
        if os.path.isabs(plot_output_path) and os.path.exists(plot_output_path):
            return plot_output_path

        # try as absolute (in case returned relative)
        abs_candidate = os.path.abspath(plot_output_path)
        if os.path.exists(abs_candidate):
            return abs_candidate

        # try relative to provided search_folder
        if search_folder:
            rel_candidate = os.path.join(search_folder, plot_output_path)
            if os.path.exists(rel_candidate):
                return rel_candidate
            rel_candidate2 = os.path.abspath(rel_candidate)
            if os.path.exists(rel_candidate2):
                return rel_candidate2

        # fallback: search common names in search_folder (or parent dir of returned path)
        folder_to_search = search_folder or os.path.dirname(plot_output_path) or self.selected_folder or os.getcwd()
        try:
            patterns = ['*comparison_plot*.png', '*_plot.png', '*.png']
            for p in patterns:
                matches = glob.glob(os.path.join(folder_to_search, p))
                if matches:
                    self.log_to_output(f"resolve_plot_path: using found file {matches[0]}")
                    return matches[0]
        except Exception as e:
            self.log_to_output(f"resolve_plot_path: search failed: {e}")

        self.log_to_output(f"resolve_plot_path: unable to resolve plot path: {plot_output_path}")
        return None

    def display_diff_file(self, diff_path):
        """Read a *_diff.txt file and populate the diff_table.

        First column: index (0..n-1)
        Second column: numeric diff value from the file
        Values outside [-0.03, 0.03] are colored red.
        """
        if not diff_path or not os.path.exists(diff_path):
            self.log_to_output(f"Diff file not found: {diff_path}")
            return

        try:
            with open(diff_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.log_to_output(f"Failed to read diff file {diff_path}: {e}")
            return

        # Extract numbers from the file. Assume a line-per-value or whitespace-separated values.
        numbers = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            # try to parse a single float from the line
            m = re.search(r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?", line)
            if m:
                try:
                    numbers.append(float(m.group(0)))
                except Exception:
                    continue

        # Fallback: if no numbers by lines, try to find all floats in the whole file
        if not numbers:
            for m in re.finditer(r"[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?", content):
                try:
                    numbers.append(float(m.group(0)))
                except Exception:
                    pass

        # Populate table
        self.diff_table.setRowCount(len(numbers))
        for i, val in enumerate(numbers):
            idx_item = QTableWidgetItem(str(i))
            val_item = QTableWidgetItem(f"{val:.6f}")

            # Color out-of-range values red
            if val > 0.015 or val < -0.015:
                val_item.setForeground(QBrush(QColor('orange')))
            if val > 0.03 or val < -0.03:
                val_item.setForeground(QBrush(QColor('red')))

            self.diff_table.setItem(i, 0, idx_item)
            self.diff_table.setItem(i, 1, val_item)

        self.log_to_output(f"Displayed diff file: {diff_path} with {len(numbers)} entries")

    def map_filetype_to_integer(self, filetype):
        """
        Maps filetype strings to corresponding integers.
        """
        # Normalize incoming filetype to uppercase to avoid unexpected -1 values
        if not isinstance(filetype, str):
            return -1
        key = filetype.strip().upper()
        mapping = {
            "FAILED": 12,
            "F3": 11,
            "F2": 10,
            "F1": 9,
            "S2": 8,
            "S1": 7,
            "SX": 6,
        }
        return mapping.get(key, -1)  # Return -1 if the filetype is not in the mapping