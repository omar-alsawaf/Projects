from pymodbus.client import ModbusTcpClient

PLC_IP = "192.168.95.2"
client = ModbusTcpClient(PLC_IP, port=502)

if client.connect():
    print("[+] Connected to OpenPLC")
    
    # Scan Output/Memory Holding Registers (%QW and %MW)
    print("\n--- Non-Zero Holding Registers (FC3) ---")
    for start_addr in [100, 1024]:
        res = client.read_holding_registers(address=start_addr, count=10)
        if not res.isError():
            for idx, val in enumerate(res.registers):
                if val > 0:
                    print(f"HR {start_addr + idx}: {val}")

    # Scan Input Registers (%IW Sensor Data)
    print("\n--- Non-Zero Input Registers (FC4) ---")
    res_in = client.read_input_registers(address=100, count=15)
    if not res_in.isError():
        for idx, val in enumerate(res_in.registers):
            if val > 0:
                print(f"IR {100 + idx}: {val}")

    client.close()
