#!/usr/bin/env python3
"""
sitl_test.py — Automated SITL Test Harness for Striper Robot

Connects to an ArduRover SITL instance, uploads a rectangular paint mission,
arms and runs in AUTO mode, then monitors waypoint progress, relay events,
and speed transitions.

Prerequisites:
    pip install pymavlink

Usage:
    python scripts/sitl_test.py --connection tcp:127.0.0.1:5760
    python scripts/sitl_test.py --connection udp:127.0.0.1:14550

The SITL instance must be running before starting this script.
Use ardurover/sitl/sim_striper.sh to launch SITL.
"""

import argparse
import sys
import time

try:
    from pymavlink import mavutil, mavwp
except ImportError:
    print("ERROR: pymavlink not installed. Run: pip install pymavlink")
    sys.exit(1)


# ── Configuration ──────────────────────────────────────────────────────────

# Rectangular mission around SITL default location (Phoenix, AZ)
# Generates a simple rectangle with DO_SET_RELAY paint commands
DEFAULT_LAT = 33.4484
DEFAULT_LON = -112.0740
RECT_WIDTH_M = 20.0   # meters east-west
RECT_HEIGHT_M = 10.0  # meters north-south

# Timeouts
CONNECT_TIMEOUT = 30    # seconds
ARM_TIMEOUT = 30        # seconds
MISSION_TIMEOUT = 180   # seconds for entire mission
HEARTBEAT_TIMEOUT = 5   # seconds between heartbeats


# ── Helpers ────────────────────────────────────────────────────────────────

def meters_to_lat(meters):
    """Approximate meters to latitude degrees."""
    return meters / 111320.0


def meters_to_lon(meters, lat):
    """Approximate meters to longitude degrees at a given latitude."""
    import math
    return meters / (111320.0 * math.cos(math.radians(lat)))


def build_rectangular_mission(lat, lon, width_m, height_m):
    """Build a rectangular paint mission with relay commands.

    Returns a list of MAVLink mission items:
      1. Home waypoint
      2. DO_SET_RELAY(0, 1)  — paint ON
      3-6. Rectangle corners
      7. DO_SET_RELAY(0, 0)  — paint OFF
      8. RTL
    """
    dlat = meters_to_lat(height_m)
    dlon = meters_to_lon(width_m, lat)

    corners = [
        (lat, lon),                     # bottom-left (start)
        (lat, lon + dlon),              # bottom-right
        (lat + dlat, lon + dlon),       # top-right
        (lat + dlat, lon),              # top-left
    ]

    items = []
    seq = 0

    # Item 0: Home
    items.append(_wp(seq, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                      lat, lon, 0, is_home=True))
    seq += 1

    # Paint ON before first corner
    items.append(_relay_cmd(seq, relay=0, state=1))
    seq += 1

    # Navigate rectangle
    for clat, clon in corners:
        items.append(_wp(seq, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                          clat, clon, 0))
        seq += 1

    # Return to start to close the rectangle
    items.append(_wp(seq, mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                      corners[0][0], corners[0][1], 0))
    seq += 1

    # Paint OFF
    items.append(_relay_cmd(seq, relay=0, state=0))
    seq += 1

    # RTL
    items.append(_wp(seq, mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
                      0, 0, 0))
    seq += 1

    return items


def _wp(seq, cmd, lat, lon, alt, is_home=False):
    """Create a MAVLink mission item."""
    return mavutil.mavlink.MAVLink_mission_item_int_message(
        target_system=1,
        target_component=1,
        seq=seq,
        frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        command=cmd,
        current=1 if is_home else 0,
        autocontinue=1,
        param1=0, param2=0, param3=0, param4=0,
        x=int(lat * 1e7),
        y=int(lon * 1e7),
        z=int(alt),
        mission_type=0,
    )


def _relay_cmd(seq, relay, state):
    """Create a DO_SET_RELAY mission command."""
    return mavutil.mavlink.MAVLink_mission_item_int_message(
        target_system=1,
        target_component=1,
        seq=seq,
        frame=mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        command=mavutil.mavlink.MAV_CMD_DO_SET_RELAY,
        current=0,
        autocontinue=1,
        param1=relay,
        param2=state,
        param3=0, param4=0,
        x=0, y=0, z=0,
        mission_type=0,
    )


# ── Main Test Flow ─────────────────────────────────────────────────────────

class SITLTest:
    """Automated SITL test runner."""

    def __init__(self, connection_string):
        self.conn_str = connection_string
        self.master = None
        self.waypoints_reached = set()
        self.relay_events = []
        self.speed_transitions = []
        self.last_speed = 0.0
        self.mission_complete = False

    def connect(self):
        """Connect to SITL and wait for heartbeat."""
        print(f"Connecting to {self.conn_str}...")
        self.master = mavutil.mavlink_connection(self.conn_str)
        self.master.wait_heartbeat(timeout=CONNECT_TIMEOUT)
        print(f"Connected. Target system={self.master.target_system}, "
              f"component={self.master.target_component}")

    def upload_mission(self, items):
        """Upload mission items to vehicle."""
        print(f"Uploading mission ({len(items)} items)...")

        # Send mission count
        self.master.mav.mission_count_send(
            self.master.target_system,
            self.master.target_component,
            len(items),
            0,  # mission_type = mission
        )

        for item in items:
            # Wait for mission request
            msg = self.master.recv_match(
                type=['MISSION_REQUEST_INT', 'MISSION_REQUEST'],
                blocking=True,
                timeout=10,
            )
            if msg is None:
                print("ERROR: Timeout waiting for MISSION_REQUEST")
                return False

            seq = msg.seq
            if seq < len(items):
                self.master.mav.send(items[seq])
            else:
                print(f"ERROR: Requested seq {seq} out of range")
                return False

        # Wait for ACK
        ack = self.master.recv_match(type='MISSION_ACK', blocking=True, timeout=10)
        if ack and ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
            print("Mission uploaded successfully.")
            return True
        else:
            print(f"ERROR: Mission upload failed (ack={ack})")
            return False

    def arm(self):
        """Arm the vehicle via MAV_CMD_COMPONENT_ARM_DISARM (works for all vehicle types)."""
        print("Arming vehicle...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0,    # confirmation
            1,    # param1: 1 = arm
            0, 0, 0, 0, 0, 0,
        )
        self.master.motors_armed_wait()
        print("Vehicle armed.")

    def set_mode(self, mode_name):
        """Set vehicle mode by name."""
        mode_id = self.master.mode_mapping().get(mode_name)
        if mode_id is None:
            print(f"ERROR: Unknown mode '{mode_name}'")
            return False
        self.master.set_mode(mode_id)
        print(f"Mode set to {mode_name} ({mode_id})")
        return True

    def run_mission(self):
        """Monitor mission execution until completion or timeout."""
        print(f"Running mission (timeout={MISSION_TIMEOUT}s)...")
        start = time.time()

        while time.time() - start < MISSION_TIMEOUT:
            msg = self.master.recv_match(
                type=[
                    'MISSION_ITEM_REACHED',
                    'MISSION_CURRENT',
                    'STATUSTEXT',
                    'VFR_HUD',
                    'NAV_CONTROLLER_OUTPUT',
                    'HEARTBEAT',
                ],
                blocking=True,
                timeout=HEARTBEAT_TIMEOUT,
            )

            if msg is None:
                continue

            msg_type = msg.get_type()

            if msg_type == 'MISSION_ITEM_REACHED':
                seq = msg.seq
                self.waypoints_reached.add(seq)
                print(f"  WP {seq} reached")

            elif msg_type == 'MISSION_CURRENT':
                if msg.seq == 0 and len(self.waypoints_reached) > 2:
                    # Returned to home — mission likely complete
                    self.mission_complete = True
                    break

            elif msg_type == 'STATUSTEXT':
                text = msg.text
                if 'PAINT' in text or 'RELAY' in text or 'SPEED_SYNC' in text:
                    print(f"  [{msg.severity}] {text}")
                    if 'PAINT' in text or 'RELAY' in text.upper():
                        self.relay_events.append(text)

                # Detect mission complete message
                if 'Mission Complete' in text or 'Reached destination' in text:
                    self.mission_complete = True
                    break

            elif msg_type == 'VFR_HUD':
                speed = msg.groundspeed
                # Track significant speed transitions
                if abs(speed - self.last_speed) > 0.2:
                    self.speed_transitions.append({
                        'time': time.time() - start,
                        'from': self.last_speed,
                        'to': speed,
                    })
                self.last_speed = speed

            elif msg_type == 'HEARTBEAT':
                mode = mavutil.mode_string_v10(msg)
                if mode == 'RTL' and len(self.waypoints_reached) > 2:
                    self.mission_complete = True
                    break

        elapsed = time.time() - start
        print(f"Mission monitoring ended after {elapsed:.1f}s")

    def report(self):
        """Print test results summary."""
        print("\n" + "=" * 60)
        print(" SITL TEST RESULTS")
        print("=" * 60)

        print(f"\n  Mission complete: {'YES' if self.mission_complete else 'NO'}")
        print(f"  Waypoints reached: {sorted(self.waypoints_reached)}")
        print(f"  Relay events: {len(self.relay_events)}")
        for evt in self.relay_events:
            print(f"    - {evt}")
        print(f"  Speed transitions: {len(self.speed_transitions)}")
        for st in self.speed_transitions[:10]:
            print(f"    - t={st['time']:.1f}s: {st['from']:.2f} → {st['to']:.2f} m/s")

        print("\n" + "=" * 60)

        # Determine pass/fail
        passed = True
        if not self.mission_complete:
            print("  FAIL: Mission did not complete")
            passed = False
        if len(self.waypoints_reached) < 4:
            print(f"  FAIL: Only {len(self.waypoints_reached)} waypoints reached (expected >= 4)")
            passed = False

        # Verify paint relay events (at least one ON and one OFF)
        relay_on = any("ON" in e for e in self.relay_events)
        relay_off = any("OFF" in e for e in self.relay_events)
        if len(self.relay_events) < 2 or not relay_on or not relay_off:
            print(f"  FAIL: Expected >=2 relay events (ON+OFF), got {len(self.relay_events)}")
            passed = False

        if passed:
            print("  RESULT: PASS")
        else:
            print("  RESULT: FAIL")

        print("=" * 60)
        return passed


def main():
    parser = argparse.ArgumentParser(
        description="Automated SITL test harness for the Striper robot"
    )
    parser.add_argument(
        "--connection", "-c",
        default="tcp:127.0.0.1:5760",
        help="MAVLink connection string (default: tcp:127.0.0.1:5760)",
    )
    parser.add_argument(
        "--lat", type=float, default=DEFAULT_LAT,
        help=f"Mission center latitude (default: {DEFAULT_LAT})",
    )
    parser.add_argument(
        "--lon", type=float, default=DEFAULT_LON,
        help=f"Mission center longitude (default: {DEFAULT_LON})",
    )
    parser.add_argument(
        "--width", type=float, default=RECT_WIDTH_M,
        help=f"Rectangle width in meters (default: {RECT_WIDTH_M})",
    )
    parser.add_argument(
        "--height", type=float, default=RECT_HEIGHT_M,
        help=f"Rectangle height in meters (default: {RECT_HEIGHT_M})",
    )
    args = parser.parse_args()

    test = SITLTest(args.connection)

    try:
        test.connect()

        # Build and upload mission
        mission = build_rectangular_mission(
            args.lat, args.lon, args.width, args.height
        )
        if not test.upload_mission(mission):
            print("ABORT: Mission upload failed")
            sys.exit(1)

        # Arm and run
        test.arm()
        test.set_mode("AUTO")
        test.run_mission()

        # Report
        passed = test.report()
        sys.exit(0 if passed else 1)

    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        test.report()
        sys.exit(130)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
