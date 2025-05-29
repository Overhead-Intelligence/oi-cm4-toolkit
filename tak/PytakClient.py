#!/usr/bin/env python3
import asyncio
import socket
import struct
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak
from collections import defaultdict
from cot_broadcast import read_csv_values
import subprocess

# Configuration settings
#SERVER_URL = "tls://45.32.196.115:8089" # vector server
SERVER_URL = "tls://35.231.4.140:8089"   # OI google cloud server
UID        = "vector6"
CALLSIGN   = "Vector6"
CHATROOM   = "All Chat Rooms"
MCAST_ADDR = "224.10.10.1"
MCAST_PORT = 17012
TEAM_COLOR = "Cyan"
ROLE       = "Team Member"

all_positions = defaultdict(list)

def build_tls_conf():
    cfg = ConfigParser()
    cfg.add_section("tak")
    cfg.set("tak", "COT_URL", SERVER_URL)
    
    # paths to your cert/key/CA
    cfg.set("tak", "PYTAK_TLS_CLIENT_CERT", "/home/droneman/oi-cm4-toolkit/tak/certs/vector6_cert.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_KEY",  "/home/droneman/oi-cm4-toolkit/tak/certs/vector6_key.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_CAFILE", "/home/droneman/oi-cm4-toolkit/tak/certs/vector6_ca_bundle.pem")
    # for testing only or if needed
    cfg.set("tak", "PYTAK_TLS_DONT_VERIFY",       "1")
    cfg.set("tak", "PYTAK_TLS_DONT_CHECK_HOSTNAME","1")
    return cfg["tak"]


def make_presence() -> bytes:
    """
    Build an ATAK-compatible a-f-G-U-C (Unit Contact) CoT event,
    which shows up under Contacts, has a GeoChat endpoint, status,
    track, takv, etc.
    """
    now = pytak.cot_time()
    ev = ET.Element("event", {
        "version": "2.0",
        "uid": UID,
        "type": "a-f-A", 
        "time": now,
        "start": now,
        "stale": pytak.cot_time(75),
        "how": "h-e"
    })

    lat, lon, alt, battery, heading, grnd_speed = read_csv_values() # Update location values from the CSV file
    #lat, lon, alt, battery, heading, grnd_speed = 27.95, -81.62, 10, 45, 102, 20
    #print(f"{lat}, {lon}, {alt}, {battery}, {heading}, {grnd_speed}")

    # 2) Point block
    ET.SubElement(ev, "point", {
        "lat": f"{lat}",
        "lon": f"{lon}",
        "hae": f"{alt}",
        "ce":  "10",
        "le":  "10",
    })

    # 3) Detail block
    det = ET.SubElement(ev, "detail")

    # 3a) Contact info (Contacts tab)
    ET.SubElement(det, "contact", {
        "callsign": CALLSIGN,
        "endpoint": "udp://224.10.10.1:17012" #MY_ENDPOINT
        #"phone":    MY_PHONE,
    })

    # 3b) UID (optional extra metadata)
    ET.SubElement(det, "uid", {"Droid": CALLSIGN})

    # 3c) Group affiliation
    ET.SubElement(det, "__group", {
        "name": TEAM_COLOR,
        "role": ROLE
    })

    # 3d) Precision location (so ATAK can show the little accuracy circle)
    ET.SubElement(det, "precisionlocation", {
        "geopointsrc": "USER",
        "altsrc":      "SRTM1"
    })

    # 3e) Status (battery)
    ET.SubElement(det, "status", {"battery": str(int(battery))})

    # 3f) TAK-version info
    ET.SubElement(det, "takv", {
        "device":   "PyTAK",
        "platform": "Python",
        "os":       "Linux",
        "version":  "1.0" #fix
    })

    # 3g) Track (speed/course)
    ET.SubElement(det, "track", {
        "speed":  f"{grnd_speed}",
        "course": f"{heading}"
    })

     # stub to enable “Start Chat”
    ET.SubElement(det, "__chat")
    # *** advertise GeoChat connector ***
    conns = ET.SubElement(det, "connectors")
    ET.SubElement(conns, "connector", type="Geo Chat", protocol="tcp", endpoint="10.224.3.140:4242")
    
    return ET.tostring(ev)


def make_chat(text):
    lat, lon, alt, battery, heading, grnd_speed = read_csv_values() # Update location values from the CSV file

    #lat, lon, alt, battery, heading, grnd_speed = 27.95, -81.62, 10, 45, 102, 20

    now = pytak.cot_time()
    ev = ET.Element("event", {
        "version":"2.0", "type":"b-t-f", "uid":f"{UID}-{now}",
        "how":"h-g-i-g-o", "time":now, "start":now,
        "stale":pytak.cot_time(3600)
    })
    ET.SubElement(ev, "point", {"lat":str(lat),"lon":str(lon),"hae":str(alt),"ce":"10","le":"10"})
    det = ET.SubElement(ev, "detail")
    ET.SubElement(det, "__chat", {
        "id": CHATROOM,
        "chatroom": CHATROOM,
        "senderCallsign": CALLSIGN
    })
    ET.SubElement(det, "chatgrp", {"id": CHATROOM, "uid0": UID})
    ET.SubElement(det, "link", {"uid": UID, "type": "a-f-G", "relation": "p-p"})
    ET.SubElement(det, "hierarchy")
    ET.SubElement(det, "remarks", {
        "source": CALLSIGN,
        "to": CHATROOM,
        "time": now
    }).text = text
    return ET.tostring(ev)

def collect_position(user):
    uid = user["uid"]
    all_positions[uid].append((user["callsign"], user["time"], user["lat"], user["lon"], user["hae"])) #, user["callsign"]

async def process_events(tls_reader, udp_sock, tls_writer):
    """
    Single coroutine that reads from both:
      - tls_reader (async)
      - udp_sock  (sync, via run_in_executor)
    Splits into <event>…</event>, then:
      - if it's a CoT point, calls collect_position()
      - if it's a free-chat, handles “position” command or prints
    """
    loop = asyncio.get_event_loop()
    buf_tcp = b""
    buf_udp = b""

    async def read_tcp():
        nonlocal buf_tcp
        data = await tls_reader.read(4096)
        if not data:
            return []
        buf_tcp += data
        parts = []
        while b"</event>" in buf_tcp:
            pkt, buf_tcp = buf_tcp.split(b"</event>", 1)
            parts.append(pkt + b"</event>")
        return parts

    def read_udp():
        nonlocal buf_udp
        data, _ = udp_sock.recvfrom(8192)
        buf_udp += data
        parts = []
        while b"</event>" in buf_udp:
            pkt, buf_udp = buf_udp.split(b"</event>", 1)
            parts.append(pkt + b"</event>")
        return parts

    while True:
        # Launch both reads in parallel
        tcp_task = asyncio.create_task(read_tcp())
        udp_task = loop.run_in_executor(None, read_udp)
        done, _ = await asyncio.wait(
            [tcp_task, udp_task], return_when=asyncio.FIRST_COMPLETED
        )

        if tcp_task in done:
            udp_task.cancel()
            events = tcp_task.result()
        else:
            tcp_task.cancel()
            events = await udp_task

        for xml in events:
            try:
                root = ET.fromstring(xml)
            except ET.ParseError:
                continue

            
            # — free‐text chat handler —
            if root.get("type") == "b-t-f":
                det     = root.find("detail")
                chatelt = det.find("__chat")  if det is not None else None
                remarks = det.find("remarks") if det is not None else None
                if chatelt is not None and remarks is not None:
                    sender = chatelt.get("senderCallsign")
                    text   = (remarks.text or "").strip().lower()
                    if text == "position":
                        print(f"\n[REQUEST] {sender} asked for positions, sending report…")
                        pkt = make_position_report()
                        # send over TLS (so ATAK clients see it)
                        tls_writer.write(pkt)
                        await tls_writer.drain()
                        # send over UDP (so WinTAK sees it)
                        udp_sock.sendto(pkt, (MCAST_ADDR, MCAST_PORT))
                    else:
                        print(f"\n[CHAT][{sender}] {remarks.text}")
            else:
                # — CoT position collector —
                pt = root.find("point")
                det = root.find("detail")
                callsign = None
                if det is not None:
                    contact = det.find("contact")
                    if contact is not None:
                        callsign = contact.get("callsign")
                if pt is not None:
                    collect_position({
                        "callsign": callsign,
                        "uid":  root.get("uid"),
                        "time": root.get("time"),
                        "lat":  float(pt.get("lat", 0)),
                        "lon":  float(pt.get("lon", 0)),
                        "hae":  float(pt.get("hae", 0))
                    })

async def tcp_and_udp_chat():
    # — TLS setup —
    conf = build_tls_conf()
    tls_reader, tls_writer = await pytak.protocol_factory(conf)
    print(f"TLS connected to {SERVER_URL}")

    # send initial presence
    tls_writer.write(make_presence());  await tls_writer.drain()

    # — UDP setup —
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.bind(("", MCAST_PORT))
    udp_sock.setsockopt(
        socket.IPPROTO_IP,
        socket.IP_ADD_MEMBERSHIP,
        struct.pack("4sl", socket.inet_aton(MCAST_ADDR), socket.INADDR_ANY)
    )
    print(f"UDP socket joined {MCAST_ADDR}:{MCAST_PORT}")

    # — keep presence alive —
    async def presence_loop():
        while True:
            tls_writer.write(make_presence())
            await tls_writer.drain()
            await asyncio.sleep(5)

    # — user input loop —
    async def input_loop():
        while True:
            msg = await asyncio.to_thread(input, "> ")
            if msg.lower() in ("exit","quit"):
                break
            pkt = make_chat(msg)
            udp_sock.sendto(pkt, (MCAST_ADDR, MCAST_PORT))
            tls_writer.write(pkt)
            await tls_writer.drain()
        tls_writer.close()
        await tls_writer.wait_closed()
        udp_sock.close()
        asyncio.get_event_loop().stop()

    # run all three
    await asyncio.gather(
        process_events(tls_reader, udp_sock, tls_writer),
        presence_loop(),
        input_loop(),
    )

def make_position_report():
    """
    Turn all_positions into one big newline-separated string
    and wrap it in a b-t-f event for chat.
    """

    if not all_positions:
        report = "[POSITION] no positions recorded yet."
    else:
        lines = []
        for uid, data in all_positions.items():
            callsign, time, lat, lon, hae = data[-1]
            # 1) skip the “zero” or magic hae defaults
            if (lat == 0.0 and lon == 0.0) or hae in (0.0, 9999999.0):
                continue

            # 2) skip system UIDs
            if uid.startswith("GeoChat.") or uid == "takPong":
                continue
            
            lines.append(f"{callsign} @ {time}: lat={lat:.6f}, lon={lon:.6f}, hae={hae}")
        report = "\n".join(lines)
    

    # now wrap it as a chat
    now = pytak.cot_time()
    ev = ET.Element("event", {
        "version":"2.0", "type":"b-t-f", "uid":f"{UID}-{now}",
        "how":"h-g-i-g-o", "time":now, "start":now,
        "stale": pytak.cot_time(3600)
    })
    ET.SubElement(ev, "point", {"lat":"0","lon":"0","hae":"0","ce":"0","le":"0"})
    det = ET.SubElement(ev, "detail")
    # group chat
    ET.SubElement(det, "__chat", {
        "id": CHATROOM,
        "chatroom": CHATROOM,
        "senderCallsign": CALLSIGN
    })
    ET.SubElement(det, "chatgrp", {"id": CHATROOM, "uid0": UID})
    # put our report lines in remarks
    remarks = ET.SubElement(det, "remarks", {
        "source": CALLSIGN,
        "to":     CHATROOM,
        "time":   now
    })
    remarks.text = report
    return ET.tostring(ev)


###### MAIN ########

if __name__=="__main__":
    try:
        asyncio.run(tcp_and_udp_chat())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
