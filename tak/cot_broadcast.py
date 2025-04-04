#!/usr/bin/env python3
import socket
import time
from datetime import datetime, timedelta, timezone

# Configuration parameters:
BROADCAST_IP = "255.255.255.255"  # Update this to your network's broadcast address
PORT = 6969                   # Port that ATAK is listening on for CoT messages

def create_cot_message(lat, lon, altitude, uid="drone-1", callsign="Default Goose"):
    """
    Generate a simple CoT XML message with current time and provided location.
    
    Args:
        lat (float): Latitude in decimal degrees.
        lon (float): Longitude in decimal degrees.
        altitude (float): Height above ellipsoid in meters.
        uid (str): Unique identifier for the source.
        callsign (str): Human-friendly name for the source.
    
    Returns:
        str: A CoT message in XML format.
    """
    now = datetime.now(timezone.utc)
    time_str = now.isoformat() + "Z"
    start_str = time_str
    stale_str = (now + timedelta(minutes=5)).isoformat() + "Z"
    
    cot_message = f"""<?xml version="1.0" encoding="UTF-8"?>
<event version="2.0" uid="{uid}" type="a-f-A-C-F" how="m-g" time="{time_str}" start="{start_str}" stale="{stale_str}">
    <point lat="{lat}" lon="{lon}" hae="{altitude}" ce="9999.0" le="9999.0"/>
    <detail>
        <contact callsign="{callsign}"/>
    </detail>
</event>"""
    return cot_message

def main():
    # Create a UDP socket configured for broadcasting
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Example position - replace these values with your telemetry data if available
    latitude = 27.7749
    longitude = -81.4194
    altitude = 10.0

    print("Broadcasting CoT messages. Press Ctrl+C to stop.")
    try:
        while True:
            message = create_cot_message(latitude, longitude, altitude)
            # Send the message via UDP broadcast
            sock.sendto(message.encode('utf-8'), (BROADCAST_IP, PORT))
            print("Broadcasted CoT message:")
            print(message)
            print("-" * 50)
            # Wait a few seconds before sending the next message
            time.sleep(5)
    except KeyboardInterrupt:
        print("Broadcasting stopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
