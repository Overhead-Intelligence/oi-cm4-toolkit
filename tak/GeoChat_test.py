#!/usr/bin/env python3
import asyncio
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak

CHAT_TYPE     = "b-t-f"       # GeoChat event type for one-to-one chat
PRESENCE_TYPE = "a-f-A-C-H-Q" # Presence + chat invitation

def get_location():
    """Replace with your real GPS reading code."""
    return 27.95391667, -81.61530556, 10.0

def make_cot(lat, lon, hae, uid, cot_type):
    """Generate a CoT XML message (bytes)."""
    return pytak.gen_cot(lat=lat, lon=lon, hae=hae, uid=uid, cot_type=cot_type)

async def send_presence(writer, my_uid, conv_id, peer_uid):
    """
    Every 5 s broadcast your location + a __chat invitation
    for the direct‐chat thread `conv_id` with peer `peer_uid`.
    """
    while True:
        lat, lon, hae = get_location()
        raw = make_cot(lat, lon, hae, my_uid, PRESENCE_TYPE)
        root = ET.fromstring(raw)

        # Replace <detail> with our own that includes the direct chat invitation
        old_det = root.find("detail")
        if old_det is not None:
            root.remove(old_det)
        det = ET.SubElement(root, "detail")

        # Identify self
        ET.SubElement(det, "contact", callsign=my_uid)

        # Invite peer_uid to this direct chat
        ET.SubElement(det, "__chat", {
            "id":      conv_id,
            "chatroom":conv_id,
            "senderCallsign": my_uid,
            "groupOwner": "false"
        })
        ET.SubElement(det, "chatgrp", {
            "id":    conv_id,
            "uid0":  my_uid,
            "uid1":  peer_uid
        })
        ET.SubElement(det, "hierarchy")  # stub

        writer.write(ET.tostring(root))
        await writer.drain()
        await asyncio.sleep(5)

async def send_direct_chat(writer, my_uid, conv_id, peer):
    """
    Loop: prompt user for text and send it as b-t-f direct‐chat.
    """
    loop = asyncio.get_event_loop()
    while True:
        msg = await loop.run_in_executor(None, input, f"To {peer}: ")
        msg = msg.strip()
        if not msg:
            continue

        now = pytak.cot_time()
        ev = ET.Element("event", {
            "version":"2.0", "type":CHAT_TYPE, "uid":conv_id,
            "how":"h-g-i-g-o","time":now,"start":now,
            "stale":pytak.cot_time(3600)
        })
        ET.SubElement(ev, "point", {
            "lat":"0","lon":"0","hae":"9999999",
            "ce":"9999999","le":"9999999"
        })

        det = ET.SubElement(ev, "detail")
        ET.SubElement(det, "__chat", {
            "id":      conv_id,
            "chatroom":conv_id,
            "senderCallsign": my_uid,
            "groupOwner":"false"
        })
        ET.SubElement(det, "chatgrp", {
            "id":   conv_id,
            "uid0": my_uid,
            "uid1": peer
        })
        ET.SubElement(det, "hierarchy")
        ET.SubElement(det, "link", {
            "uid":my_uid, "type":"a-f-G-U-C-I", "relation":"p-p"
        })
        ET.SubElement(det, "remarks", {
            "source":my_uid, "to":peer, "time":now
        }).text = msg

        marti = ET.SubElement(det, "marti")
        ET.SubElement(marti, "dest", {"callsign": peer})

        writer.write(ET.tostring(ev))
        await writer.drain()

async def recv_direct_chat(reader, my_uid):
    """
    Loop: print any incoming b-t-f events where you are uid1 or uid0.
    """
    buf = b""
    while True:
        chunk = await reader.read(4096)
        if not chunk:
            print("► Disconnected")
            return
        buf += chunk
        while b"</event>" in buf:
            pkt, buf = buf.split(b"</event>", 1)
            xml = pkt + b"</event>"
            try:
                root = ET.fromstring(xml)
            except ET.ParseError:
                continue
            if root.get("type") != CHAT_TYPE:
                continue

            det = root.find("detail")
            if det is None:
                continue
            chatgrp = det.find("chatgrp")
            rm      = det.find("remarks")
            if chatgrp is None or rm is None:
                continue

            u0 = chatgrp.get("uid0")
            u1 = chatgrp.get("uid1")
            # Check if we’re in this thread
            if u0 == my_uid and u1:
                peer = u1
            elif u1 == my_uid and u0:
                peer = u0
            else:
                continue

            # Skip our own messages
            if rm.get("source") == my_uid:
                continue

            print(f"\n[Chat] {peer} → you: {rm.text}\n")

async def main():
    # — TLS Configuration —
    cfg = ConfigParser()
    cfg.add_section("tak_tls")
    cfg.set("tak_tls","COT_URL", "tls://10.224.5.255:8089")
    cfg.set("tak_tls","COT_HOST_ID","cm4-client")
    cfg.set("tak_tls","PYTAK_TLS_CLIENT_CERT",r"C:\...\client_cert.pem")
    cfg.set("tak_tls","PYTAK_TLS_CLIENT_KEY", r"C:\...\client_key_nopass.pem")
    cfg.set("tak_tls","PYTAK_TLS_CLIENT_CAFILE",r"C:\...\ca_bundle.pem")
    # Testing only
    cfg.set("tak_tls","PYTAK_TLS_DONT_VERIFY","1")
    cfg.set("tak_tls","PYTAK_TLS_DONT_CHECK_HOSTNAME","1")
    conf = cfg["tak_tls"]

    reader, writer = await pytak.protocol_factory(conf)
    my_uid = conf["COT_HOST_ID"]

    # Prompt once for whom to chat with:
    peer = input("Chat with (callsign): ").strip()
    conv_id = f"chat.{my_uid}.{peer}"

    # Run all three loops concurrently:
    await asyncio.gather(
        send_presence(writer, my_uid, conv_id, peer),
        recv_direct_chat(reader, my_uid),
        send_direct_chat(writer, my_uid, conv_id, peer),
    )

if __name__=="__main__":
    asyncio.run(main())
