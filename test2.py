import serial

try:
    ser = serial.Serial('COM2', 9600, timeout=1)
    print(f"Connected to {ser.portstr}")
    ser.close()
except Exception as e:
    print(f"Error: {e}")