from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel,
    QSpinBox, QPushButton, QTextEdit
)
from PyQt5.QtCore import Qt
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException
import sys

class HMIWriter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HMI Register Writer")
        self.setGeometry(200, 200, 400, 250)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.value_label = QLabel("Enter value to send to HMI:")
        layout.addWidget(self.value_label)

        self.value_input = QSpinBox()
        self.value_input.setRange(9, 12)  # Restrict input to values between 9 and 12
        layout.addWidget(self.value_input)


        self.send_button = QPushButton("Send to HMI")
        self.send_button.clicked.connect(self.send_value)
        layout.addWidget(self.send_button)

        self.debug_output = QTextEdit()
        self.debug_output.setReadOnly(True)
        layout.addWidget(self.debug_output)

        self.setLayout(layout)

    def log(self, message):
        self.debug_output.append(message)

    def send_value(self):
        value = self.value_input.value()
        self.log(f"Attempting to write value: {value}")
        self.write_to_hmi_register(value)

    def write_to_hmi_register(self, value):
        PORT = 'COM6'
        BAUDRATE = 9600
        SLAVE_ID = 2
        S0_ADDRESS = 0

        client = ModbusSerialClient(
            port=PORT,
            baudrate=BAUDRATE,
            parity='E',
            stopbits=1,
            bytesize=8,
            timeout=3
        )

        try:
            if client.connect():
                self.log(f"Connected to {PORT}. Sending value...")
                response = client.write_register(
                    address=S0_ADDRESS,
                    value=value,
                    slave=SLAVE_ID
                )

                if response.isError():
                    self.log(f"❌ Error writing register: {response}")
                else:
                    self.log("✅ Success: Value written to S0.")
            else:
                self.log("❌ Connection failed.")
        except ModbusException as e:
            self.log(f"❌ Modbus error: {e}")
        except Exception as e:
            self.log(f"❌ Unexpected error: {e}")
        finally:
            client.close()
            self.log("Connection closed.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = HMIWriter()
    window.show()
    sys.exit(app.exec_())
