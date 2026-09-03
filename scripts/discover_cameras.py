"""
Camera discovery for the CCTV integration service.

Finds IP cameras / NVRs on one or more subnets using four techniques:

    1. ONVIF WS-Discovery   UDP multicast probe, vendor-agnostic
    2. TCP port sweep       RTSP / HTTP / vendor SDK ports
    3. RTSP OPTIONS probe   confirms a real RTSP server, reads Server header
    4. HTTP GET probe       vendor hint from Server / WWW-Authenticate

Standard library only, no extra dependencies.

Usage:
    python scripts/discover_cameras.py
    python scripts/discover_cameras.py --cidr 192.168.100.0/24
    python scripts/discover_cameras.py --cidr 10.83.197.0/24 --json found.json
    python scripts/discover_cameras.py --no-onvif --timeout 1.0
"""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import re
import socket
import struct
import subprocess
import sys
import uuid
from dataclasses import dataclass, field


# ============================================================
# Ports commonly exposed by IP cameras, DVRs and NVRs
# ============================================================
CAMERA_PORTS: dict[int, str] = {
    80: "HTTP / web UI",
    88: "HTTP alt (Foscam)",
    554: "RTSP",
    8000: "Hikvision SDK",
    8080: "HTTP alt",
    8554: "RTSP alt",
    9000: "HTTP alt",
    34567: "XiongMai / dvrip",
    37777: "Dahua DVR / NVR",
}

# Scanned against every host first, to find live devices cheaply.
PROBE_PORTS = (554, 80, 37777, 8000)

RTSP_PORTS = (554, 8554)
HTTP_PORTS = (80, 88, 8080, 9000)


# ============================================================
# MAC OUI prefixes of common CCTV vendors (hint only)
# ============================================================
VENDOR_OUIS: dict[str, str] = {
    "44:19:b6": "Hikvision",
    "4c:bd:8f": "Hikvision",
    "bc:ad:28": "Hikvision",
    "c0:56:e3": "Hikvision",
    "28:57:be": "Hikvision",
    "54:c4:15": "Hikvision",
    "a4:14:37": "Hikvision",
    "3c:ef:8c": "Dahua",
    "90:02:a9": "Dahua",
    "4c:11:bf": "Dahua",
    "08:ed:ed": "Dahua",
    "e0:50:8b": "Dahua",
    "9c:14:63": "Dahua",
    "48:ea:63": "Uniview",
    "6c:f1:7e": "Uniview",
    "00:40:8c": "Axis",
    "ac:cc:8e": "Axis",
    "e4:30:22": "Hanwha",
    "00:02:d1": "Vivotek",
    "00:07:5f": "Bosch",
    "ec:71:db": "Reolink",
}

# ============================================================
# RTSP URL templates, printed as a starting point for the
# rtsp_url column on the cameras table
# ============================================================
RTSP_TEMPLATES: dict[str, list[str]] = {
    "Hikvision": [
        "rtsp://USER:PASS@{ip}:{port}/Streaming/Channels/101",
        "rtsp://USER:PASS@{ip}:{port}/Streaming/Channels/102  (sub stream)",
    ],
    "Dahua": [
        "rtsp://USER:PASS@{ip}:{port}/cam/realmonitor?channel=1&subtype=0",
        "rtsp://USER:PASS@{ip}:{port}/cam/realmonitor?channel=1&subtype=1",
    ],
    "Uniview": [
        "rtsp://USER:PASS@{ip}:{port}/media/video1",
    ],
    "Axis": [
        "rtsp://USER:PASS@{ip}:{port}/axis-media/media.amp",
    ],
    "Hanwha": [
        "rtsp://USER:PASS@{ip}:{port}/profile2/media.smp",
    ],
    "Vivotek": [
        "rtsp://USER:PASS@{ip}:{port}/live.sdp",
    ],
    "Reolink": [
        "rtsp://USER:PASS@{ip}:{port}/h264Preview_01_main",
    ],
    "unknown": [
        "rtsp://USER:PASS@{ip}:{port}/  (check the vendor docs or ONVIF XAddr)",
    ],
}


# ============================================================
# Result container
# ============================================================
@dataclass
class Device:
    ip: str
    open_ports: list[int] = field(default_factory=list)
    mac: str | None = None
    vendor: str | None = None
    rtsp_server: str | None = None
    http_server: str | None = None
    http_realm: str | None = None
    onvif_xaddrs: list[str] = field(default_factory=list)

    @property
    def rtsp_port(self) -> int | None:
        for port in RTSP_PORTS:
            if port in self.open_ports:
                return port
        return None

    def as_dict(self) -> dict:
        return {
            "ip": self.ip,
            "open_ports": self.open_ports,
            "mac": self.mac,
            "vendor": self.vendor,
            "rtsp_port": self.rtsp_port,
            "rtsp_server": self.rtsp_server,
            "http_server": self.http_server,
            "http_realm": self.http_realm,
            "onvif_xaddrs": self.onvif_xaddrs,
        }


# ============================================================
# Low level probes
# ============================================================
def tcp_open(ip: str, port: int, timeout: float) -> bool:
    """Return True if a TCP connection to ip:port succeeds."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)

        try:
            return sock.connect_ex((ip, port)) == 0
        except OSError:
            return False


def rtsp_options(ip: str, port: int, timeout: float) -> str | None:
    """
    Send an RTSP OPTIONS request.

    Returns the Server header (or a bare "RTSP/1.0" marker) when the
    peer really speaks RTSP, otherwise None.
    """

    request = (
        f"OPTIONS rtsp://{ip}:{port}/ RTSP/1.0\r\n"
        "CSeq: 1\r\n"
        "User-Agent: cctv-discovery\r\n"
        "\r\n"
    )

    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(request.encode("ascii"))
            raw = sock.recv(2048).decode("latin-1", errors="replace")
    except OSError:
        return None

    if "RTSP/1.0" not in raw:
        return None

    match = re.search(r"^Server:\s*(.+)$", raw, re.IGNORECASE | re.MULTILINE)

    if match:
        return match.group(1).strip()

    return "RTSP/1.0 (no Server header)"


def http_probe(ip: str, port: int, timeout: float) -> tuple[str | None, str | None]:
    """
    Send a plain HTTP GET.

    Returns (server_header, auth_realm); either may be None.
    """

    request = (
        "GET / HTTP/1.0\r\n"
        f"Host: {ip}\r\n"
        "User-Agent: cctv-discovery\r\n"
        "\r\n"
    )


    try:
        with socket.create_connection((ip, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(request.encode("ascii"))
            raw = sock.recv(4096).decode("latin-1", errors="replace")
    except OSError:
        return None, None

    server = re.search(r"^Server:\s*(.+)$", raw, re.IGNORECASE | re.MULTILINE)
    realm = re.search(r'realm="([^"]+)"', raw, re.IGNORECASE)

    return (
        server.group(1).strip() if server else None,
        realm.group(1).strip() if realm else None,
    )


def arp_table() -> dict[str, str]:
    """
    Parse the OS ARP cache into {ip: mac}.

    Populated as a side effect of the port sweep, so call this afterwards.
    """

    try:
        output = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}

    table: dict[str, str] = {}

    pattern = re.compile(
        r"(\d{1,3}(?:\.\d{1,3}){3})\s+"
        r"([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})"
    )

    for ip, mac in pattern.findall(output):
        table[ip] = mac.replace("-", ":").lower()

    return table


# ============================================================
# ONVIF WS-Discovery
# ============================================================
WS_DISCOVERY_GROUP = "239.255.255.250"
WS_DISCOVERY_PORT = 3702

WS_PROBE = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
 xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
 xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
 xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
<e:Header>
<w:MessageID>uuid:{message_id}</w:MessageID>
<w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
<w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
</e:Header>
<e:Body>
<d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe>
</e:Body>
</e:Envelope>"""


def local_ipv4_addresses() -> list[str]:
    """Best effort list of usable local IPv4 addresses."""

    addresses: set[str] = set()

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass

    return sorted(
        addr
        for addr in addresses
        if not addr.startswith(("127.", "169.254."))
    )


def ws_discover(source_ip: str, wait_seconds: float) -> dict[str, list[str]]:
    """
    Multicast an ONVIF Probe from one local interface.

    Returns {responder_ip: [service XAddrs]}.
    """

    found: dict[str, list[str]] = {}

    probe = WS_PROBE.format(message_id=uuid.uuid4()).encode("utf-8")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((source_ip, 0))
            sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_IF,
                socket.inet_aton(source_ip),
            )
            sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_MULTICAST_TTL,
                struct.pack("b", 2),
            )
            sock.settimeout(wait_seconds)
            sock.sendto(probe, (WS_DISCOVERY_GROUP, WS_DISCOVERY_PORT))
        except OSError:
            return found

        while True:
            try:
                raw, addr = sock.recvfrom(65535)
            except (socket.timeout, TimeoutError):
                break
            except OSError:
                break

            text = raw.decode("utf-8", errors="replace")
            xaddrs = re.findall(r"<[^>]*XAddrs>([^<]+)<", text)

            urls: list[str] = []
            for chunk in xaddrs:
                urls.extend(chunk.split())

            if urls:
                found.setdefault(addr[0], [])
                for url in urls:
                    if url not in found[addr[0]]:
                        found[addr[0]].append(url)

    return found


# ============================================================
# Scan orchestration
# ============================================================
def guess_vendor(device: Device) -> str:
    """Identify the vendor from banners first, MAC OUI second."""

    banners = " ".join(
        part.lower()
        for part in (
            device.rtsp_server,
            device.http_server,
            device.http_realm,
        )
        if part
    )

    known = (
        "hikvision",
        "dahua",
        "uniview",
        "axis",
        "hanwha",
        "vivotek",
        "bosch",
        "reolink",
        "amcrest",
        "foscam",
        "tiandy",
    )

    for name in known:
        if name in banners:
            return name.capitalize()

    if device.mac:
        vendor = VENDOR_OUIS.get(device.mac[:8])
        if vendor:
            return vendor

    if 37777 in device.open_ports:
        return "Dahua"

    if 8000 in device.open_ports and 554 in device.open_ports:
        return "Hikvision"

    return "unknown"


def sweep(
    hosts: list[str],
    ports: tuple[int, ...],
    timeout: float,
    workers: int,
) -> dict[str, list[int]]:
    """Parallel TCP sweep. Returns {ip: [open ports]} for responding hosts."""

    tasks = [(ip, port) for ip in hosts for port in ports]
    results: dict[str, list[int]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(tcp_open, ip, port, timeout): (ip, port)
            for ip, port in tasks
        }

        for future in concurrent.futures.as_completed(futures):
            ip, port = futures[future]

            if future.result():
                results.setdefault(ip, []).append(port)

    for ip in results:
        results[ip].sort()

    return results


def fingerprint(device: Device, timeout: float) -> Device:
    """Fill in RTSP / HTTP banners for a device with known open ports."""

    for port in RTSP_PORTS:
        if port in device.open_ports:
            device.rtsp_server = rtsp_options(device.ip, port, timeout)
            if device.rtsp_server:
                break

    for port in HTTP_PORTS:
        if port in device.open_ports:
            server, realm = http_probe(device.ip, port, timeout)
            device.http_server = device.http_server or server
            device.http_realm = device.http_realm or realm
            if server or realm:
                break

    return device


def report(devices: list[Device]) -> None:
    """Print a human readable summary."""

    if not devices:
        print("\nNo camera-like devices found.")
        print("Things to check:")
        print("  - is the PC on the same subnet / VLAN as the cameras?")
        print("  - are the cameras behind an NVR PoE switch (own private subnet)?")
        print("  - try --cidr explicitly, and widen --timeout to 1.0")
        return

    print(f"\n{len(devices)} camera-like device(s) found\n")

    for device in devices:
        ports = ", ".join(
            f"{port} ({CAMERA_PORTS.get(port, '?')})"
            for port in device.open_ports
        )

        vendor = device.vendor or guess_vendor(device)

        print("=" * 60)
        print(f"IP           : {device.ip}")
        print(f"Vendor guess : {vendor}")
        print(f"Open ports   : {ports}")

        if device.mac:
            print(f"MAC          : {device.mac}")

        if device.rtsp_server:
            print(f"RTSP server  : {device.rtsp_server}")

        if device.http_server:
            print(f"HTTP server  : {device.http_server}")

        if device.http_realm:
            print(f"Auth realm   : {device.http_realm}")

        for xaddr in device.onvif_xaddrs:
            print(f"ONVIF XAddr  : {xaddr}")

        rtsp_port = device.rtsp_port

        if rtsp_port:
            print("Try:")
            for template in RTSP_TEMPLATES.get(
                vendor,
                RTSP_TEMPLATES["unknown"],
            ):
                print(f"  {template.format(ip=device.ip, port=rtsp_port)}")

    print("=" * 60)


# ============================================================
# CLI
# ============================================================
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover IP cameras / NVRs on the local network.",
    )
    parser.add_argument(
        "--cidr",
        action="append",
        default=[],
        metavar="NETWORK",
        help="Subnet to scan, e.g. 192.168.100.0/24. Repeatable. "
             "Defaults to every local IPv4 subnet.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.6,
        help="Per-connection timeout in seconds (default 0.6).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=256,
        help="Concurrent socket count (default 256).",
    )
    parser.add_argument(
        "--onvif-wait",
        type=float,
        default=3.0,
        help="Seconds to listen for ONVIF replies (default 3.0).",
    )
    parser.add_argument(
        "--no-onvif",
        action="store_true",
        help="Skip the ONVIF WS-Discovery step.",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="Also write the results to this JSON file.",
    )

    return parser.parse_args(argv)


def resolve_targets(cidrs: list[str]) -> list[str]:
    """Expand the requested CIDRs, or every local /24-ish subnet."""

    networks: list[ipaddress.IPv4Network] = []

    if cidrs:
        for raw in cidrs:
            networks.append(ipaddress.ip_network(raw, strict=False))
    else:
        for address in local_ipv4_addresses():
            networks.append(
                ipaddress.ip_network(f"{address}/24", strict=False)
            )

    hosts: list[str] = []
    seen: set[str] = set()

    for network in networks:
        if network.num_addresses > 4096:
            print(
                f"Skipping {network}: too large "
                f"({network.num_addresses} addresses).",
                file=sys.stderr,
            )
            continue

        print(f"Scanning {network} ...")

        for host in network.hosts():
            text = str(host)
            if text not in seen:
                seen.add(text)
                hosts.append(text)

    return hosts


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    devices: dict[str, Device] = {}

    # --------------------------------------------------------
    # 1. ONVIF WS-Discovery
    # --------------------------------------------------------
    if not args.no_onvif:
        print("ONVIF WS-Discovery ...")

        for source_ip in local_ipv4_addresses():
            for ip, xaddrs in ws_discover(source_ip, args.onvif_wait).items():
                device = devices.setdefault(ip, Device(ip=ip))
                device.onvif_xaddrs = xaddrs

        print(f"  ONVIF replies: {len(devices)}")

    # --------------------------------------------------------
    # 2. Cheap sweep, then full port list on responders only
    # --------------------------------------------------------
    hosts = resolve_targets(args.cidr)

    live = sweep(hosts, PROBE_PORTS, args.timeout, args.workers)

    if live:
        detailed = sweep(
            list(live),
            tuple(CAMERA_PORTS),
            args.timeout,
            args.workers,
        )
    else:
        detailed = {}

    for ip, ports in detailed.items():
        devices.setdefault(ip, Device(ip=ip)).open_ports = ports

    # --------------------------------------------------------
    # 3. Fingerprint and classify
    # --------------------------------------------------------
    macs = arp_table()

    for device in devices.values():
        device.mac = macs.get(device.ip)
        fingerprint(device, max(args.timeout, 1.0))
        device.vendor = guess_vendor(device)

    # --------------------------------------------------------
    # 4. Keep only devices that look like cameras
    # --------------------------------------------------------
    found = [
        device
        for device in devices.values()
        if device.onvif_xaddrs
        or device.rtsp_server
        or any(
            port in device.open_ports
            for port in (554, 8554, 8000, 37777, 34567)
        )
    ]

    found.sort(key=lambda device: ipaddress.ip_address(device.ip))

    report(found)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(
                [device.as_dict() for device in found],
                handle,
                indent=2,
            )

        print(f"\nWrote {args.json}")

    return 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(main())
