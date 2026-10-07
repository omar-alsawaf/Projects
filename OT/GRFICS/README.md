# GRFICS — OT/ICS Red Team Lab

A hands-on offensive security walkthrough against **GRFICS** (Graphical Realism Framework for Industrial Control Simulations), a Fortiphyd Logic containerized OT/ICS lab simulating a chemical plant process.

This project documents a full attack chain against a simulated chemical reactor: **network discovery → protocol fingerprinting → MITM/ARP spoofing → C2 deployment → direct Modbus command injection → PLC logic poisoning → physical consequence.**

![Explosion](./PlcAttack/explosion.png)

---

## 🧱 Target Infrastructure

The lab is a set of containerized hosts spanning an IT segment (`192.168.90.0/24`) and an OT segment (`192.168.95.0/24`), bridged by a router:

| Container | Role | Address |
|---|---|---|
| `fortiphyd/grfics-attacker` (kali) | Attacker workstation | `192.168.90.x`, VNC `6088→6080` |
| `fortiphyd/grfics-scadalts` | HMI / SCADA-LTS | `192.168.90.107`, Web `6081→8080` |
| `fortiphyd/grfics-workstation` | Engineering workstation (EWS) | VNC `6080→6080` |
| `fortiphyd/grfics-simulation` | 3D physical process simulator | Web/3D GUI `80→80` |
| `fortiphyd/grfics-plc` | OpenPLC | `192.168.95.2:502`, Web UI `8080→8080` |
| `fortiphyd/grfics-router` | Network pivot | `192.168.90.200`, WireGuard `51820/udp` |
| `fortiphyd/grfics-caldera` | C2 (MITRE Caldera) | `8888/tcp` |

**Target valve/device addressing (OT segment):**

| Device | IP |
|---|---|
| Feed 1 Valve | `192.168.95.10` |
| Feed 2 Valve | `192.168.95.11` |
| Purge Valve | `192.168.95.12` |
| Product Valve | `192.168.95.13` |

---

## 🧭 Attack Chain

| Stage | Objective | Write-up |
|---|---|---|
| 1 | Reconnaissance & Discovery | [`reconnaissance-and-discovery/`](./reconnaissance-and-discovery/reconnaissance-and-discovery.md) |
| 2 | ARP Spoofing & Packet Sniffing | [`ArpSpoofing-and-PacketSniffing/`](./ArpSpoofing-and-PacketSniffing/ArpSpoofing-and-PacketSniffing.md) |
| 3 | C2 Deployment & Modbus Enumeration (Caldera) | [`Caldera_ModbusEnum/`](./Caldera_ModbusEnum/Caldera_modbusEnum.md) |
| 4 | Modbus Command Injection & Register Mapping | [`ModbusCommanInjection-and-RegisterMapping/`](./ModbusCommanInjection-and-RegisterMapping/ModbusCommanInjection-and-RegisterMapping.md) |
| 5 | PLC Logic Exploitation (`pressure_sp`) | [`PlcAttack/`](./PlcAttack/PlcAttack.md) |

### 1. Reconnaissance & Discovery
Mapped both subnets, identified the router pivot (`192.168.90.200`), enumerated live hosts and open ports with `nmap`, and confirmed Modbus/TCP (502) running across the OT segment. Metasploit's `modbus_banner_grabbing` module fingerprinted each device as a `pymodbus` 3.0.0 server (vendor URL `github.com/pymodbus-dev/pymodbus`).

### 2. ARP Spoofing & Packet Sniffing
Used `arpspoof` to poison the HMI's (`192.168.90.107`) ARP cache, placing the attacker machine in the middle of HMI↔PLC traffic. From that position, sniffed live Modbus polling traffic and captured the exact **Write Single Coil** command (FC 5, coil `40`) generated when an operator pressed "Stop" on the SCADA-LTS HMI.

### 3. C2 Deployment & Modbus Enumeration
Deployed a Caldera **Sandcat** agent (disguised as `splunkd`) to a compromised host, then used Caldera to run a `pymodbus`-based device-identification ability against `192.168.95.10:502` entirely through the established C2 channel.

### 4. Modbus Command Injection & Register Mapping
Scanned OpenPLC's full Modbus register space (`192.168.95.2:502`) to map holding registers (FC3/FC16) and input registers (FC4), distinguishing **transient** registers (overwritten every PLC scan cycle, e.g. `HR 100`) from **persistently writable** ones (e.g. `HR 1026`, which maps directly to a setpoint). Built `modcommandinjection.py`, a multithreaded Modbus client that continuously writes to each valve's holding registers at 10 ms intervals — fast enough to win the race against the PLC's own scan-cycle writes — to directly force all four valves (feed 1, feed 2, purge, product) open or closed regardless of the PLC's control logic, and verified each resulting physical state against the HMI/3D simulation.

### 5. PLC Logic Exploitation — `pressure_sp`
Rather than racing register writes, this stage edits the PLC's own control program. `pressure_sp` — the setpoint driving the vessel's purge/relief proportional controller — is bounded only by its `UINT` type (0–65535), with no real safety ceiling enforced in logic. Uploading a modified `exploit.st` through OpenPLC's web UI with `pressure_sp` pinned to `65535` silently collapses the relief loop's error term to ≤0: the PLC keeps running, reports no fault, and the purge valve never meaningfully opens — letting vessel pressure build unchecked to a simulated explosion.

---

## 📂 Repository Structure

```
GRFICS/
├── README.md
├── reconnaissance-and-discovery/
│   ├── reconnaissance-and-discovery.md
│   ├── OurKali.png, ExistingNetworks.png
│   ├── modbusBannerGrab
│   ├── 192.168.90.X/  (ActiveHosts.txt, OpenPorts.txt, NmapScans/)
│   └── 192.168.95.X/  (ActiveHosts.txt, OpenPorts.txt, NmapScans/)
├── ArpSpoofing-and-PacketSniffing/
│   ├── ArpSpoofing-and-PacketSniffing.md
│   ├── modbus.pcapng
│   └── *.png
├── Caldera_ModbusEnum/
│   ├── Caldera_modbusEnum.md
│   └── *.png
├── ModbusCommanInjection-and-RegisterMapping/
│   ├── ModbusCommanInjection-and-RegisterMapping.md
│   ├── modcommandinjection.py
│   ├── scan.py
│   ├── writeable.py
│   └── *.png
└── PlcAttack/
    ├── PlcAttack.md
    ├── chemical.st            # Baseline PLC logic
    ├── exploit.st              # Weaponized logic (pressure_sp := 65535)
    ├── chemical/                # Full OpenPLC/MatIEC build output (POUS.c, LOCATED_VARIABLES.h, VARIABLES.csv, etc.)
    └── *.png
```

## 🧰 Tooling Used

`nmap` · Wireshark/`tshark` · `arpspoof` · Metasploit (`scanner/scada/modbus_banner_grabbing`) · `pymodbus` · MITRE Caldera (Sandcat agent) · OpenPLC · SCADA-LTS

## ⚠️ Disclaimer

This project was carried out entirely against the **GRFICS simulated environment**, a framework purpose-built by Fortiphyd Logic and the Georgia Institute of Technology for OT security training. No real industrial hardware or production system was involved. Techniques documented here are for educational and lab-based red/blue team training purposes only.

## 🙏 Credit

Built on [GRFICS](https://github.com/Fortiphyd) by **Fortiphyd Logic** and Georgia Institute of Technology. See their workshop paper, *"Lowering the Barriers to Industrial Control System Security with GRFICS."*
