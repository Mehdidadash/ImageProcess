#capture.py
print("Main.py is running...")
import sys,os
from PyQt5.QtWidgets import QApplication
import CameraAppClass

# Run the application
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraAppClass.CameraApp()
    window.show()
    sys.exit(app.exec_())