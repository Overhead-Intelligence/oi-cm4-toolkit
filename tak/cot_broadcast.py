#!/usr/bin/env python3
import socket
import time
import csv
from datetime import datetime, timedelta, timezone
import subprocess

# Configuration parameters:
BROADCAST_IP = "255.255.255.255"  # Update this to your network's broadcast address
PORT = 6969                   # Port that ATAK is listening on for CoT messages
CSV_FILE = "/home/droneman/shell-scripts/mavlink-reader/mavlink-data.csv"

# Launch the mavlink-reader.py script
mavlink_reader_script = "/home/droneman/shell-scripts/mavlink-reader/mavlink-reader.py"
subprocess.Popen(["python3", mavlink_reader_script, "stream"])

def create_cot_message(lat, lon, altitude, uid="drone-1", callsign="Default Goose", type="a-f-A-C-F"):
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
<event version="2.0" uid="{uid}" type="{type}" how="m-g" time="{time_str}" start="{start_str}" stale="{stale_str}">
    <point lat="{lat}" lon="{lon}" hae="{altitude}" ce="9999.0" le="9999.0"/>
    <detail>
        <contact callsign="{callsign}"/>
    </detail>
</event>"""
    return cot_message

def read_csv_values():
    """
    Reads the CSV file and returns the latest latitude, longitude, and altitude.
    The CSV file is expected to have the following header:
    flight_mode,armed,battery,rangefinder_dst,agl,heading,ground_speed,air_speed,wind_dir,wind_speed,UTC_Date_Time,lat,lon
    Here we use the "lat", "lon", and "agl" columns.
    """
    lat, lon, alt = 0.0, 0.0, 0.0  # Default values
    try:
        with open(CSV_FILE, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # If multiple rows exist, this will take the last one;
                # typically, the mavlink-reader overwrites the file with one row.
                lat = float(row.get("lat", 0.0))
                lon = float(row.get("lon", 0.0))
                alt = float(row.get("agl", 0.0))
                #print(f"Read from CSV: lat={lat}, lon={lon}, alt={alt}")
    except Exception as e:
        print(f"Error reading CSV: {e}")
    return lat, lon, alt

def main():
    # Create a UDP socket configured for broadcasting
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    # Example position - replace these values with your telemetry data if available
    #latitude = 27.7749
    #longitude = -81.4194
    #altitude = 10.0

    hostname = socket.gethostname()
    uid = f"{hostname}-1"

    print("Broadcasting CoT messages. Press Ctrl+C to stop.")
    try:
        while True:
            lat, lon, alt = read_csv_values() # Update location values from the CSV file

            message = create_cot_message(lat, lon, alt, uid=uid, callsign=hostname)
            
            sock.sendto(message.encode('utf-8'), (BROADCAST_IP, PORT)) # Send the message via UDP broadcast
            #print("Broadcasted CoT message:")
            #print(message)
            #print("-" * 50)
            # Wait a few seconds before sending the next message
            time.sleep(5)
    except KeyboardInterrupt:
        print("Broadcasting stopped.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
