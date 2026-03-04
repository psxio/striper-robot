#!/usr/bin/env python3
"""RTK corrections setup helper for striper robot.

Helps configure NTRIP corrections for the UM980 GPS to achieve
2cm positioning accuracy (vs 2-3m without RTK).

Usage:
    python scripts/rtk_setup.py --lat 30.2672 --lon -97.7431
    python scripts/rtk_setup.py --lat 30.2672 --lon -97.7431 --radius 100
    python scripts/rtk_setup.py --test-connection --mountpoint AUSTIN_RTK
"""

import argparse
import math
import socket
import sys
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# NTRIP caster defaults
# ---------------------------------------------------------------------------
RTK2GO_HOST = "rtk2go.com"
RTK2GO_PORT = 2101

POLARIS_HOST = "polaris.pointonenav.com"
POLARIS_PORT = 2101


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_sourcetable(host=RTK2GO_HOST, port=RTK2GO_PORT, timeout=10):
    """Fetch NTRIP sourcetable from a caster."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Ntrip-Version: Ntrip/2.0\r\n"
            f"User-Agent: StripeRobot/1.0\r\n"
            f"\r\n"
        )
        sock.sendall(request.encode())

        data = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"ENDSOURCETABLE" in data:
                    break
            except socket.timeout:
                break
        sock.close()
        return data.decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: {e}"


def parse_sourcetable(raw):
    """Parse NTRIP sourcetable into list of mountpoints."""
    mounts = []
    for line in raw.splitlines():
        if not line.startswith("STR;"):
            continue
        parts = line.split(";")
        if len(parts) < 19:
            continue
        try:
            mount = {
                "name": parts[1],
                "identifier": parts[2],
                "format": parts[3],
                "format_details": parts[4],
                "carrier": parts[5],
                "nav_system": parts[6],
                "network": parts[7],
                "country": parts[8],
                "lat": float(parts[9]) if parts[9] else 0,
                "lon": float(parts[10]) if parts[10] else 0,
                "nmea": parts[11],
                "solution": parts[12],
                "generator": parts[13],
                "compression": parts[14],
                "auth": parts[15],
                "fee": parts[16],
                "bitrate": parts[17],
            }
            mounts.append(mount)
        except (ValueError, IndexError):
            continue
    return mounts


def find_nearest(mounts, lat, lon, radius_km=100, limit=10):
    """Find nearest mountpoints within radius."""
    results = []
    for m in mounts:
        if m["lat"] == 0 and m["lon"] == 0:
            continue
        dist = haversine_km(lat, lon, m["lat"], m["lon"])
        if dist <= radius_km:
            m["distance_km"] = round(dist, 1)
            results.append(m)
    results.sort(key=lambda x: x["distance_km"])
    return results[:limit]


def test_connection(host, port, mountpoint=None, timeout=5):
    """Test TCP connectivity to NTRIP caster."""
    print(f"Testing connection to {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        print(f"  TCP connection: OK")

        if mountpoint:
            request = (
                f"GET /{mountpoint} HTTP/1.1\r\n"
                f"Host: {host}\r\n"
                f"Ntrip-Version: Ntrip/2.0\r\n"
                f"User-Agent: StripeRobot/1.0\r\n"
                f"\r\n"
            )
            sock.sendall(request.encode())
            response = sock.recv(1024).decode("utf-8", errors="replace")
            if "200 OK" in response or "ICY 200" in response:
                print(f"  Mountpoint '{mountpoint}': OK (streaming)")
            elif "401" in response:
                print(f"  Mountpoint '{mountpoint}': requires authentication")
            elif "404" in response:
                print(f"  Mountpoint '{mountpoint}': NOT FOUND")
            else:
                print(f"  Mountpoint response: {response[:100]}")
        sock.close()
        return True
    except socket.timeout:
        print(f"  Connection: TIMEOUT (host may be down)")
        return False
    except Exception as e:
        print(f"  Connection: FAILED ({e})")
        return False


def print_mission_planner_config(mountpoint, host=RTK2GO_HOST, port=RTK2GO_PORT):
    """Print Mission Planner NTRIP injection settings."""
    print()
    print("=" * 60)
    print("  MISSION PLANNER NTRIP CONFIGURATION")
    print("=" * 60)
    print()
    print("  In Mission Planner, go to: Setup > Optional Hardware > RTK/GPS Inject")
    print()
    print(f"  Host:        {host}")
    print(f"  Port:        {port}")
    print(f"  Mountpoint:  {mountpoint}")
    print(f"  Username:    your.email@example.com")
    print(f"  Password:    (leave blank for RTK2Go)")
    print()
    print("  Then click 'Connect' and verify 'RTK Fixed' appears in GPS status.")
    print()
    print("  Note: Your computer must be connected to the Pixhawk via USB or")
    print("  telemetry radio for NTRIP injection to work through Mission Planner.")
    print()


def print_ardurover_params():
    """Print ArduRover params for NTRIP via GCS injection."""
    print()
    print("=" * 60)
    print("  ARDUROVER PARAMETER REFERENCE")
    print("=" * 60)
    print()
    print("  These params are already set in striper.param:")
    print()
    print("  GPS_TYPE       = 25    (UM980)")
    print("  GPS_GNSS_MODE  = 0     (auto - all constellations)")
    print("  SERIAL3_PROTOCOL = 5   (GPS)")
    print("  SERIAL3_BAUD    = 115  (115200)")
    print()
    print("  RTK corrections are injected by Mission Planner or QGC,")
    print("  not configured as ArduRover params. The GCS receives RTCM3")
    print("  from the NTRIP caster and forwards it to the Pixhawk via")
    print("  the MAVLink GPS_INJECT_DATA message.")
    print()
    print("  For standalone NTRIP (no laptop in field):")
    print("  - Use a Raspberry Pi or ESP32 with NTRIP client")
    print("  - Connect to Pixhawk SERIAL4 for RTCM3 injection")
    print("  - Or use UM980's built-in NTRIP client (requires WiFi/cellular)")
    print()


def print_provider_comparison():
    """Print comparison of RTK correction providers."""
    print()
    print("=" * 60)
    print("  RTK CORRECTION PROVIDERS")
    print("=" * 60)
    print()
    print("  +-------------------+--------+----------+-------------------+")
    print("  | Provider          | Cost   | Coverage | Setup             |")
    print("  +-------------------+--------+----------+-------------------+")
    print("  | RTK2Go            | Free   | Varies   | Email signup      |")
    print("  | Point One Polaris | $50/mo | USA/EU   | API key           |")
    print("  | Own base station  | ~$200  | 20km     | ZED-F9P + antenna |")
    print("  | State CORS        | Free   | State    | Register          |")
    print("  +-------------------+--------+----------+-------------------+")
    print()
    print("  Recommendation: Start with RTK2Go (free). If no base station")
    print("  within 30km, upgrade to Point One Polaris ($50/mo) or set up")
    print("  your own base station with a second UM980/ZED-F9P.")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="RTK/NTRIP setup helper for Striper Robot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--lat", type=float, help="Your latitude (decimal degrees)")
    parser.add_argument("--lon", type=float, help="Your longitude (decimal degrees)")
    parser.add_argument("--radius", type=float, default=50,
                        help="Search radius in km (default: 50)")
    parser.add_argument("--test-connection", action="store_true",
                        help="Test NTRIP caster connectivity")
    parser.add_argument("--mountpoint", type=str,
                        help="Specific mountpoint to test")
    parser.add_argument("--host", type=str, default=RTK2GO_HOST,
                        help=f"NTRIP caster host (default: {RTK2GO_HOST})")
    parser.add_argument("--port", type=int, default=RTK2GO_PORT,
                        help=f"NTRIP caster port (default: {RTK2GO_PORT})")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  STRIPER ROBOT - RTK CORRECTIONS SETUP")
    print("=" * 60)

    # Always show provider comparison
    print_provider_comparison()

    # Test connection if requested
    if args.test_connection:
        test_connection(args.host, args.port, args.mountpoint)
        if args.mountpoint:
            print_mission_planner_config(args.mountpoint, args.host, args.port)
        print_ardurover_params()
        return

    # Search for nearby base stations
    if args.lat is not None and args.lon is not None:
        print(f"Searching for NTRIP base stations near ({args.lat}, {args.lon})...")
        print(f"Radius: {args.radius} km")
        print(f"Caster: {args.host}:{args.port}")
        print()

        raw = fetch_sourcetable(args.host, args.port)
        if raw.startswith("ERROR:"):
            print(f"  Failed to fetch sourcetable: {raw}")
            print("  Check your internet connection and try again.")
            sys.exit(1)

        mounts = parse_sourcetable(raw)
        print(f"  Found {len(mounts)} total mountpoints on {args.host}")

        nearest = find_nearest(mounts, args.lat, args.lon, args.radius)

        if not nearest:
            print(f"\n  No mountpoints found within {args.radius}km.")
            print("  Try increasing --radius, or consider Point One Polaris ($50/mo)")
            print("  or setting up your own base station.")
        else:
            print(f"\n  Nearest {len(nearest)} mountpoints:")
            print()
            print("  +-----+-----------------------+--------+--------+--------+")
            print("  |  #  | Mountpoint            | Dist   | Format | Nav    |")
            print("  +-----+-----------------------+--------+--------+--------+")
            for i, m in enumerate(nearest):
                print(f"  | {i+1:3d} | {m['name'][:21]:21s} | {m['distance_km']:5.1f}km "
                      f"| {m['format'][:6]:6s} | {m['nav_system'][:6]:6s} |")
            print("  +-----+-----------------------+--------+--------+--------+")

            best = nearest[0]
            print(f"\n  Recommended: {best['name']} ({best['distance_km']}km away)")
            print(f"  Format: {best['format']} | Nav: {best['nav_system']}")

            print_mission_planner_config(best["name"], args.host, args.port)

        print_ardurover_params()
    else:
        print("  Usage: python scripts/rtk_setup.py --lat YOUR_LAT --lon YOUR_LON")
        print()
        print("  This will search RTK2Go for nearby NTRIP base stations and")
        print("  generate Mission Planner configuration instructions.")
        print()
        print("  Example for Austin, TX:")
        print("    python scripts/rtk_setup.py --lat 30.2672 --lon -97.7431")
        print()
        print_ardurover_params()


if __name__ == "__main__":
    main()
