#!/usr/bin/env python3
import asyncio
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak
import subprocess
import csv
import uuid
from typing import Optional, Tuple

# Configuration settings
#SERVER_URL = "tls://45.32.196.115:8089" # vector server
SERVER_URL = "tls://tak.overheadintel.com:8089"   # OI google cloud server

UID        = "magpie"
CALLSIGN   = "Magpie"

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
    cfg.set("tak", "PYTAK_TLS_CLIENT_CERT", "/home/droneman/oi-cm4-toolkit/tak/certs/Magpie_cert.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_KEY",  "/home/droneman/oi-cm4-toolkit/tak/certs/Magpie_key.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_CAFILE", "/home/droneman/oi-cm4-toolkit/tak/certs/Magpie_ca_bundle.pem")
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
    
    
    #lat, lon, alt, battery, heading, grnd_speed = 27.95, -81.62, 10, 45, 102, 20
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

# Generate chat to a chatroom
def make_chat_chatroom(message: str, chatroom: str) -> bytes:
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

def make_chat_direct(original_ev, message_text) -> bytes:

    # parse out the routing info
    detail = original_ev.find("detail")
    chat_in = detail.find("__chat")
    link_in = detail.find("link")
    sd_in   = detail.find("__serverdestination")

    chatroom    = chat_in.get("chatroom")
    chat_id     = chat_in.get("id")
    parent      = chat_in.get("parent", "RootContactGroup")
    groupOwner  = chat_in.get("groupOwner", "false")
    dests       = sd_in.get("destinations") if sd_in is not None else None
    sender_uid  = link_in.get("uid")

    # build new CoT
    now = pytak.cot_time()
    message_id = uuid.uuid4().hex

    root = ET.Element("event", {
        "version": "2.0",
        "type":    "b-t-f",
        "uid":     f"GeoChat.{UID}.{sender_uid}.{message_id}",
        "how":     "h-g-i-g-o",
        "time":    now,
        "start":   now,
        "stale":   pytak.cot_time(3600)
    })
    ET.SubElement(root, "point", {
        "lat":"0.0","lon":"0.0","hae":"9999999.0","ce":"9999999.0","le":"9999999.0"
    })
    det = ET.SubElement(root, "detail")

    # __chat with nested chatgrp
    chat = ET.SubElement(det, "__chat", {
        "parent":       parent,
        "groupOwner":   groupOwner,
        "messageId":    message_id,
        "chatroom":     chatroom,
        "id":           chat_id,
        "senderCallsign": CALLSIGN
    })
    ET.SubElement(chat, "chatgrp", {
        "uid0": UID,
        "uid1": sender_uid,
        "id":   chat_id
    })

    # link back to sender
    ET.SubElement(det, "link", {
        "uid":      sender_uid,
        "type":     "a-f-G-U-C",
        "relation": "p-p"
    })

    # serverdestination so routing is correct :contentReference[oaicite:3]{index=3}
    if dests:
        ET.SubElement(det, "__serverdestination", {
            "destinations": dests
        })

    # remarks with source/to/time
    remarks = ET.SubElement(det, "remarks", {
        "source": CALLSIGN,
        "to":     chat_id,
        "time":   now
    })
    remarks.text = message_text

    #print(f"[INFO] Sending chat message: {ET.tostring(root, encoding='unicode')}")

    return ET.tostring(root)


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

def parse_incoming_chat_event(xml: bytes) -> Optional[Tuple[ET.Element, str, str, str]]:
    """
    Returns (root, chat_id, sender_uid, server_dests)
    or None if this event isn't a free-text chat.
    """
    try:
        root = ET.fromstring(xml)
        if root.get("type") != "b-t-f":
            return None

        detail = root.find("detail")
        if detail is None:
            return None

        # __chat block holds chatroom, id, senderCallsign, plus nested chatgrp for routing
        chat = detail.find("__chat")
        if chat is None:
            return None
        chat_id = chat.get("id")                  
        sender_callsign = chat.get("senderCallsign")

        # link element: holds the sender's CoT-UID
        link = detail.find("link")
        sender_uid = link.get("uid") if link is not None else None

        # serverdestination: how to get back to exactly that device
        sd = detail.find("__serverdestination")
        dests = sd.get("destinations") if sd is not None else None

        if not (chat_id and sender_uid and dests):
            return None

        return root, chat_id, sender_uid, dests

    except ET.ParseError:
        return None

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
        buf = b""
        while enabled:
            try:
                data = await tls_reader.read(4096)
                if not data:
                    print("[INFO] Connection closed by server")
                    return

                # parse the CoT XML
                # ev = ET.fromstring(data)
                # if ev.tag != "event":
                #     continue
                
                #print(f"[INFO] Received CoT: {ET.tostring(ev, encoding='unicode')}")

                #await asyncio.sleep(0.8)

                # if ev.get("type") == "b-t-f":
                #     # echo only free‐text chats
                #     message = ev.findtext(".//remarks")
                #     if message:
                #         response = make_chat_direct(ev, f"Echo: {message}")
                #         tls_writer.write(response)
                #         await tls_writer.drain()
            
                buf += data
                # pull out one <event>…</event> at a time
                while b"</event>" in buf:
                    packet, buf = buf.split(b"</event>", 1)
                    xml = packet + b"</event>"

                    #print(f"[INFO] Received CoT: {ET.tostring(xml, encoding='unicode')}")

                    parsed = parse_incoming_chat_event(xml)
                    if not parsed:
                        continue

                    root, chat_id, sender_uid, dests = parsed

                    # grab the actual text
                    text = root.findtext(".//remarks", "").strip()
                    if not text:
                        continue

                    #print(f"[INFO] Received CoT: {ET.tostring(root, encoding='unicode')}")
                    #print(f"[INFO] Received direct chat from {sender_uid} ({chat_id}): {text!r}")

                    # build a direct-to-that-sender echo, preserving routing
                    response = make_chat_direct(
                        original_ev=root,
                        message_text=f"I heard: '{text}'"
                    )
                    # make_chat_direct already embeds the original __serverdestination,
                    # so this reply will go *only* to that device.
                    #print(f"[INFO] Sending direct chat back: {ET.tostring(ET.fromstring(response), encoding='unicode')}")
                    tls_writer.write(response)
                    await tls_writer.drain()

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
