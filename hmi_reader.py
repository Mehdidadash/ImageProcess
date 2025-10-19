from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusException

def read_plc_registers():
    # Communication configuration
    PORT = 'COM2'
    BAUDRATE = 9600
    PARITY = 'E'
    STOPBITS = 1
    BYTESIZE = 8
    SLAVE_ID = 2
    TIMEOUT = 3

    # Create Modbus RTU client
    client = ModbusSerialClient(
        port=PORT,
        baudrate=BAUDRATE,
        parity=PARITY,
        stopbits=STOPBITS,
        bytesize=BYTESIZE,
        timeout=TIMEOUT
    )

    try:
        if not client.connect():
            print("❌ Failed to connect to PLC.")
            return

        print("✅ Connected to PLC\n")

        # --- Read M bits (coils) M501–M506 ---
        m_start = 501
        m_count = 6
        m_response = client.read_coils(address=m_start, count=m_count, slave=SLAVE_ID)
        if m_response.isError():
            print(f"Error reading M bits: {m_response}")
        else:
            for i, val in enumerate(m_response.bits):
                print(f"M{m_start + i} = {val}")

        print()

        # --- Read D3 and D318 (holding registers) ---
        for d_addr in [0, 1]:
            d_response = client.read_holding_registers(address=d_addr, count=1, slave=SLAVE_ID)
            if d_response.isError():
                print(f"Error reading D{d_addr}: {d_response}")
            else:
                value = d_response.registers[0]
                print(f"D{d_addr} = {value}")

    except ModbusException as e:
        print(f"⚠️ Modbus communication error: {e}")

    finally:
        client.close()
        print("\n🔌 Connection closed.")

if __name__ == "__main__":
    read_plc_registers()