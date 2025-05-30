#!/usr/bin/env python3
import asyncio
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak
import subprocess
import csv

# bring in the chat parser from atak_chat.py
from atak_chat import ChatMessageHandler

# Configuration settings
SERVER_URL = "tls://45.32.196.115:8089" # vector server
#SERVER_URL = "tls://35.231.4.140:8089"   # OI google cloud server
UID        = "vector6"
CALLSIGN   = "Vector6"

TEAM_COLOR = "Cyan"
ROLE       = "Team Member"

# Launch the mavlink-reader.py script
CSV_FILE = "/home/droneman/oi-cm4-toolkit/mavlink-reader/mavlink-data.csv"
mavlink_reader_script = "/home/droneman/oi-cm4-toolkit/mavlink-reader/mavlink-reader.py"
subprocess.Popen(["python3", mavlink_reader_script, "stream"])

# Build TLS configuration
def build_tls_conf():
    cfg = ConfigParser()
    cfg.add_section("tak")
    cfg.set("tak", "COT_URL", SERVER_URL)
    cfg.set("tak", "PYTAK_TLS_CLIENT_CERT", "/home/droneman/oi-cm4-toolkit/tak/certs/Pytak3_cert.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_KEY",  "/home/droneman/oi-cm4-toolkit/tak/certs/Pytak3_key.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_CAFILE", "/home/droneman/oi-cm4-toolkit/tak/certs/Pytak3_ca_bundle.pem")
    cfg.set("tak", "PYTAK_TLS_DONT_VERIFY",       "1")
    cfg.set("tak", "PYTAK_TLS_DONT_CHECK_HOSTNAME","1")
    return cfg["tak"]

# Generate presence CoT
def make_presence() -> bytes:
    now = pytak.cot_time()
    ev = ET.Element("event", {
        "version": "2.0",
        "uid": UID,
        "type": "a-f-G-U-C",
        "time": now,
        "start": now,
        "stale": pytak.cot_time(75),
        "how": "h-e"
    })
    # grab location values from the CSV file
    lat, lon, alt, battery, heading, grnd_speed = read_csv_values() # Update location values from the CSV file
    
    if not lat:
        lat, lon, alt, battery, heading, grnd_speed = 27.95, -81.62, 10, 45, 102, 20
    #print(f"{lat}, {lon}, {alt}, {battery}, {heading}, {grnd_speed}")

    ET.SubElement(ev, "point", {"lat": f"{lat}", "lon": f"{lon}", "hae": f"{alt}", "ce":  "10", "le":  "10"})
    
    # Detail block
    det = ET.SubElement(ev, "detail")
    ET.SubElement(det, "contact", {"callsign": CALLSIGN, "endpoint": "*:-1:stcp"}) # Contact info 
    #ET.SubElement(det, "uid", {"Droid": CALLSIGN}) # UID (optional extra metadata)
    ET.SubElement(det, "__group", {"name": TEAM_COLOR, "role": ROLE}) # Group affiliation
    ET.SubElement(det, "precisionlocation", {"geopointsrc": "USER", "altsrc":      "SRTM1"}) # Precision location (so ATAK can show the little accuracy circle)
    ET.SubElement(det, "status", {"battery": str(int(battery))})     # Status (battery)
    ET.SubElement(det, "takv", {"device": "PyTAK", "platform": "Python", "os": "Linux", "version": "1.0"}) # TAK-version info
    ET.SubElement(det, "track", {"speed":  f"{grnd_speed}", "course": f"{heading}"})

    # stub to enable “Start Chat”
    ET.SubElement(det, "__chat")
    # *** advertise GeoChat connector ***
    conns = ET.SubElement(det, "connectors")
    ET.SubElement(conns, "connector", {"type": "Geo Chat", "protocol": "stcp", "endpoint": "*:-1:stcp"})
    return ET.tostring(ev)

# Generate chat CoT for echo replies
def make_chat(message: str, chatroom: str) -> bytes:
    now = pytak.cot_time()
    ev = ET.Element("event", {
        "version": "2.0",
        "type": "b-t-f",
        "uid": f"{UID}-{now}",
        "how": "h-g-i-g-o",
        "time": now,
        "start": now,
        "stale": pytak.cot_time(3600)
    })
    ET.SubElement(ev, "point", {"lat": "0","lon": "0","hae": "0","ce": "10","le": "10"})
    det = ET.SubElement(ev, "detail")
    ET.SubElement(det, "__chat", {"id": chatroom, "chatroom": chatroom, "senderCallsign": CALLSIGN})
    ET.SubElement(det, "chatgrp", {"id": chatroom, "uid0": UID})
    ET.SubElement(det, "link", {"uid": UID, "type": "a-f-G-U-C", "relation": "p-p"})
    remarks = ET.SubElement(det, "remarks", {"source": CALLSIGN, "to": chatroom, "time": now})
    remarks.text = message
    return ET.tostring(ev)

def read_csv_values():
    """
    Reads the CSV file and returns the latest latitude, longitude, and altitude.
    The CSV file is expected to have the following header:
    flight_mode,armed,battery,rangefinder_dst,agl,heading,ground_speed,air_speed,wind_dir,wind_speed,UTC_Date_Time,lat,lon
    Here we use the "lat", "lon", and "agl" columns.
    """
    
    try:
        with open(CSV_FILE, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # If multiple rows exist, this will take the last one;
                # typically, the mavlink-reader overwrites the file with one row.
                lat = float(row.get("lat", 0.0))
                lon = float(row.get("lon", 0.0))
                alt = float(row.get("agl", 0.0))
                battery = float(row.get("battery", 0.0))
                grnd_speed = float(row.get("ground_speed", 0.0))
                heading = float(row.get("heading", 0.0))
                #print(f"Read from CSV: lat={lat}, lon={lon}, alt={alt}")
    except Exception as e:
        print(f"Error reading CSV: {e}")
    return lat, lon, alt, battery, heading, grnd_speed


# Main async routine
enabled = True
async def async_main():
    conf = build_tls_conf()
    tls_reader, tls_writer = await pytak.protocol_factory(conf)
    print(f"TLS connected to {SERVER_URL}")

    # send initial presence
    tls_writer.write(make_presence()); await tls_writer.drain()

    # presence refresher
    async def presence_loop():
        while enabled:
            tls_writer.write(make_presence())
            await tls_writer.drain()
            await asyncio.sleep(5)

    # chat listener and echoer
    async def chat_loop():
        while enabled:
            try:
                data = await tls_reader.read(4096)
                if not data:
                    print("[INFO] Connection closed by server")
                    return

                # parse the CoT XML
                ev = ET.fromstring(data)
                if ev.tag != "event":
                    continue
                
                print(f"[INFO] Received CoT: {ET.tostring(ev, encoding='unicode')}")

                # # check for chat messages
                # chat = ev.find(".//__chat")
                # if chat is not None:
                #     chatroom = chat.get("id", "default")
                #     message = ev.findtext(".//remarks", "")
                #     if message:
                #         print(f"Received chat message in {chatroom}: {message}")
                #         # Echo back the message
                #         response = make_chat(f"Echo: {message}", chatroom)
                #         tls_writer.write(response)
                #         await tls_writer.drain()

                

            except Exception as e:
                print(f"Error processing data: {e}")
                continue
    
    # run presence + chat loops concurrently
    await asyncio.gather(presence_loop(), chat_loop())

# Entry point
if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        enabled = False
        print("Program terminated by user")
