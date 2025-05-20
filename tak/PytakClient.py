##############################################################################################################################################
##############################################################################################################################################
#                                                                                                                                            #
#       DO NOT EDIT     DO NOT EDIT       DO NOT EDIT         DO NOT EDIT         DO NOT EDIT          DO NOT EDIT         DO NOT EDIT       #
#                                                                                                                                            #
#       WORKING MODEL; DIRECTLY MESSAGE PYTAK CLIENT; RESPONDS IN GROUP CHAT WORKS FOR ALL CLIENT TYPES; FALL BACK TO ONLY IF NECESSARY       #
#                                                                                                                                            #
##############################################################################################################################################
##############################################################################################################################################


#!/usr/bin/env python3
import asyncio
import socket
import struct
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak
from datetime import datetime
from collections import defaultdict
from cot_broadcast import read_csv_values

# Configuration settings
HOSTNAME = socket.gethostname()
SERVER_URL = "tls://10.224.5.255:8089"
#SERVER_URL = "atak.tfvector.com"
UID        = f"{HOSTNAME}-UID"
CALLSIGN   = HOSTNAME
CHATROOM   = "All Chat Rooms"
MCAST_ADDR = "224.10.10.1"
MCAST_PORT = 17012
TEAM_COLOR = "Cyan"
ROLE       = "Team Member"

#USERNAME = "roger2"
#PASSWORD = "atakatak1234!!"

all_positions = defaultdict(list)

def build_tls_conf():
    cfg = ConfigParser()
    cfg.add_section("tak")
    cfg.set("tak", "COT_URL", SERVER_URL)
    
    #cfg.set("tak",
    #        "COT_URL",
    #        f"tls://{SERVER_HOST}:{SERVER_PORT}")
    #cfg.set("tak", "COT_HOST_ID", UID)
    
    # paths to your cert/key/CA
    cfg.set("tak", "PYTAK_TLS_CLIENT_CERT", "/home/droneman/Documents/tak/client_cert.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_KEY",  "/home/droneman/Documents/tak/client_key.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_CAFILE", "/home/droneman/Documents/tak/ca_bundle.pem")
    # for testing only or if needed
    cfg.set("tak", "PYTAK_TLS_DONT_VERIFY",       "1")
    cfg.set("tak", "PYTAK_TLS_DONT_CHECK_HOSTNAME","1")
    return cfg["tak"]

def make_heartbeat():
    return pytak.gen_cot(
        lat=0, lon=0, hae=0,
        uid=UID,
        cot_type="t-x-c-t"
    )



PRESENCE_LAT = 27.95
PRESENCE_LON = -81.61
MY_ENDPOINT = "10.224.3.140:4242:tcp"
MY_PHONE = 18633353998 # Dummy number not real

# Dummy functions for testing details portion of pytak client
def get_battery() -> int:
    # read from your on-board sensor, or return a dummy value
    return 42
def get_speed() -> float:
    # maybe you compute speed from GPS deltas
    return 3.5
def get_course() -> float:
    # maybe you have a compass or heading from MAVLink
    return 308.0

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
        #"access": "Undefined", 
    })

    lat, lon, alt = read_csv_values() # Update location values from the CSV file
    
    # 2) Point block
    ET.SubElement(ev, "point", {
        "lat": f"{lat}",
        "lon": f"{lon}",
        "hae": f"{alt}",
        "ce":  "9999999",
        "le":  "9999999",
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
    grp = ET.SubElement(det, "__group", {
        "name": TEAM_COLOR,
        "role": ROLE
    })

    # 3d) Precision location (so ATAK can show the little accuracy circle)
    ET.SubElement(det, "precisionlocation", {
        "geopointsrc": "USER",
        "altsrc":      "SRTM1"
    })

    # 3e) Status (battery)
    ET.SubElement(det, "status", {"battery": str(get_battery())})

    # 3f) TAK-version info
    ET.SubElement(det, "takv", {
        "device":   "PyTAK",
        "platform": "Python",
        "os":       "Linux",
        "version":  "1.0" #fix
    })

    # 3g) Track (speed/course)
    ET.SubElement(det, "track", {
        "speed":  f"{get_speed():.8f}",
        "course": f"{get_course():.8f}"
    })

     # stub to enable “Start Chat”
    ET.SubElement(det, "__chat")
    # *** advertise GeoChat connector ***
    conns = ET.SubElement(det, "connectors")
    ET.SubElement(conns, "connector", type="Geo Chat", protocol="tcp", endpoint="10.224.3.140:4242")
    
    return ET.tostring(ev)




def make_chat(text):
    now = pytak.cot_time()
    ev = ET.Element("event", {
        "version":"2.0", "type":"b-t-f", "uid":f"{UID}-{now}",
        "how":"h-g-i-g-o", "time":now, "start":now,
        "stale":pytak.cot_time(3600)
    })
    ET.SubElement(ev, "point", {"lat":"27.4","lon":"-82.4","hae":"10","ce":"10","le":"10"})
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

def collect_position(event):
    uid = event["uid"]
    all_positions[uid].append((event["time"], event["lat"], event["lon"], event["hae"]))

def output_positions():
    if not all_positions:
        print("[POSITION] No positions recorded yet.")
        return
    print("[POSITION] Last known positions:")
    for uid, pts in all_positions.items():
        t, lat, lon, hae = pts[-1]      
        print(f"{uid:20s} @ {t} : lat={lat:.6f}, lon={lon:.6f}, hae={hae}")

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

            # — CoT position collector —
            pt = root.find("point")
            if pt is not None:
                collect_position({
                    "uid":  root.get("uid"),
                    "time": root.get("time"),
                    "lat":  float(pt.get("lat")),
                    "lon":  float(pt.get("lon")),
                    "hae":  float(pt.get("hae", 0)),
                })

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

async def tcp_and_udp_chat():
    # — TLS setup —
    conf = build_tls_conf()
    tls_reader, tls_writer = await pytak.protocol_factory(conf)
    print(f"TLS connected to {SERVER_URL}")

####################################### TESTING LOGIN FOR VECTOR SEVER ###################################    
    # This may or may not work???
    #login = f"<login user='{USERNAME}' pass='{PASSWORD}'/>".encode("utf-8")
    #tls_writer.write(login)
    #await tls_writer.drain()
##########################################################################################################

    # send initial heartbeat & presence
    tls_writer.write(make_heartbeat()); await tls_writer.drain()
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
        for uid, pts in all_positions.items():
            t, lat, lon, hae = pts[-1]
            # 1) skip the “zero” or magic hae defaults
            if (lat == 0.0 and lon == 0.0) or hae in (0.0, 9999999.0):
                continue

            # 2) skip system UIDs
            if uid.startswith("GeoChat.") or uid == "takPong":
                continue
            
            lines.append(f"{uid}@{t}: lat={lat:.6f}, lon={lon:.6f}, hae={hae}")
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
