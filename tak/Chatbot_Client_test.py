#!/usr/bin/env python3
import asyncio
import socket
import struct
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak

# Configuration settings
SERVER_URL = "tls://10.224.5.255:8089"
UID        = "Chatbot1"
CALLSIGN   = "BOT-1"
CHATROOM   = "TestChat2"

# TAK server team and role identifiers
TEAM_COLOR = "Blue"
ROLE       = "Team Member"

def build_tls_conf():
    cfg = ConfigParser()
    cfg.add_section("tak")
    cfg.set("tak", "COT_URL", SERVER_URL)
    cfg.set("tak", "COT_HOST_ID", UID)
    # paths to your cert/key/CA
    cfg.set("tak", "PYTAK_TLS_CLIENT_CERT", "/home/droneman/Documents/tak/client_cert.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_KEY",  "/home/droneman/Documents/tak/client_key.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_CAFILE", "/home/droneman/Documents/tak/ca_bundle.pem")
    # for testing only
    cfg.set("tak", "PYTAK_TLS_DONT_VERIFY",       "1")
    cfg.set("tak", "PYTAK_TLS_DONT_CHECK_HOSTNAME","1")
    return cfg["tak"]

def make_heartbeat():
    return pytak.gen_cot(
        lat=0, lon=0, hae=0,
        uid=UID,
        cot_type="t-x-c-t"
    )

def make_presence():
    raw = pytak.gen_cot(
        lat=27.4, lon=-81.4, hae=10,
        uid=UID,
        cot_type="a-f-A"
    )
    root = ET.fromstring(raw)
    old_det = root.find("detail")
    if old_det is not None:
        root.remove(old_det)
    det = ET.SubElement(root, "detail")

    ET.SubElement(det, "contact", callsign=CALLSIGN)
    ET.SubElement(det, "usericon", iconsetpath="COT_MAPPING_2525B/a-f/a-f-G")
    group = ET.SubElement(det, "group", name=TEAM_COLOR, role=ROLE)
    ET.SubElement(group, "__group", name=TEAM_COLOR, role=ROLE)
    ET.SubElement(det, "takv", device="PyTAK", platform="Python", os="Linux", version="1.0")

    # GeoChat invite
    ET.SubElement(det, "__chat", {
        "id":       CHATROOM,
        "chatroom": CHATROOM,
        "senderCallsign": CALLSIGN,
        "groupOwner":     "false"
    })
    ET.SubElement(det, "chatgrp", {"id":CHATROOM, "uid0":UID})
    hier = ET.SubElement(det, "hierarchy")
    ET.SubElement(hier, "group", uid=f"Team-{TEAM_COLOR}", name=TEAM_COLOR)

    return ET.tostring(root)

def make_chat(text):
    now = pytak.cot_time()
    ev = ET.Element("event", {
        "version":"2.0", "type":"b-t-f", "uid":f"{UID}-{now}",
        "how":"h-g-i-g-o", "time":now, "start":now,
        "stale":pytak.cot_time(3600)
    })
    ET.SubElement(ev, "point", {"lat":"27.4","lon":"-81.4","hae":"10","ce":"10","le":"10"})
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

def make_udp_socket(mcast_addr, mcast_port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", mcast_port))
    mreq = struct.pack("4sl", socket.inet_aton(mcast_addr), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

async def tcp_and_udp_chat():
    # 1) Build TLS presence channel
    conf   = build_tls_conf()
    reader, writer = await pytak.protocol_factory(conf)
    print(f"TLS connected to {SERVER_URL}")

    # 2) Send heartbeat + GeoChat‐invite
    writer.write(make_heartbeat());  await writer.drain()
    writer.write(make_presence());   await writer.drain()
    print("→ Sent heartbeat & GeoChat presence")

    # 3) UDP multicast params
    MCAST_ADDR = "224.10.10.1"
    MCAST_PORT = 17012

    # 4) Join UDP chat group
    udp_sock = make_udp_socket(MCAST_ADDR, MCAST_PORT)
    print(f"UDP socket joined {MCAST_ADDR}:{MCAST_PORT}")

    # 5) TCP‐only reader for any b-t-f replies
    async def tcp_reader_loop():
        buf = b""
        while True:
            data = await reader.read(8192)
            if not data:
                print("Server closed TCP connection")
                return
            buf += data
            while b"</event>" in buf:
                pkt, buf = buf.split(b"</event>", 1)
                xml = pkt + b"</event>"
                try:
                    root = ET.fromstring(xml)
                except ET.ParseError:
                    continue
                if root.get("type") == "b-t-f":
                    remarks = root.find("./detail/remarks")
                    chatelt = root.find("./detail/__chat")
                    if remarks is not None and chatelt is not None:
                        sender = chatelt.get("senderCallsign")
                        print(f"\n[TLS {sender}] {remarks.text}\n> ", end="", flush=True)

    # 6) Keep your __chat invite alive
    async def presence_loop():
        while True:
            writer.write(make_presence())
            await writer.drain()
            await asyncio.sleep(5)

    # 7) Read stdin, send chat on **both** UDP & TLS
    async def input_loop():
        while True:
            msg = await asyncio.to_thread(input, "> ")
            if msg.lower() in ("exit","quit"):
                break

            pkt = make_chat(msg)

            # send UDP → WinTAK
            print("DEBUG: sending UDP chat:", pkt.decode())
            udp_sock.sendto(pkt, (MCAST_ADDR, MCAST_PORT))

            # echo over TLS
            writer.write(pkt)
            await writer.drain()

        writer.close()
        await writer.wait_closed()
        udp_sock.close()
        print("Bye.")
        asyncio.get_event_loop().stop()

    # 8) Run all three loops
    await asyncio.gather(
        tcp_reader_loop(),
        presence_loop(),
        input_loop(),
    )

if __name__ == "__main__":
    try:
        asyncio.run(tcp_and_udp_chat())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
