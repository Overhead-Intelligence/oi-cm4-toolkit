#!/usr/bin/env python3
import asyncio
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak

CHAT_TYPE       = "b-t-f"      # GeoChat event type for one-to-one chat
PRESENCE_TYPE   = "a-f-A-C-H-Q"  # Presence + chat invitation
UID0_FIELD      = "uid0"
UID1_FIELD      = "uid1"

def get_location():
    """Replace with your real GPS-reading code."""
    return 27.95391667, -81.61530556, 10.0

def make_cot(lat, lon, hae, uid, cot_type):
    """Generate a CoT XML message as bytes."""
    return pytak.gen_cot(
        lat=lat, lon=lon, hae=hae,
        uid=uid, cot_type=cot_type
    )

async def send_presence(writer, my_uid):
    """
    Every 5 s broadcast a presence event with a direct-chat invitation
    so ATAK will show “Chat” on your icon.
    """
    while True:
        lat, lon, hae = get_location()
        base = make_cot(lat, lon, hae, my_uid, PRESENCE_TYPE)
        root = ET.fromstring(base)

        # Replace <detail> with our own that includes a __chat for direct chat
        old_det = root.find("detail")
        if old_det is not None:
            root.remove(old_det)
        det = ET.SubElement(root, "detail")

        # Contact block (so ATAK knows who you are)
        ET.SubElement(det, "contact", callsign=my_uid)

        # __chat invitation for a _direct_ chat thread with UID=my_uid
        ET.SubElement(det, "__chat", {
            "id": f"ChatThread.{my_uid}",
            "chatroom": f"ChatThread.{my_uid}",
            "senderCallsign": my_uid,
            "groupOwner": "false"
        })

        # chatgrp with exactly two participants placeholder—you and whoever taps “Chat”
        ET.SubElement(det, "chatgrp", {
            "id": f"ChatThread.{my_uid}",
            UID0_FIELD: my_uid
        })

        ET.SubElement(det, "hierarchy")  # required stub

        # Write it back out
        xml = ET.tostring(root)
        writer.write(xml)
        await writer.drain()
        await asyncio.sleep(5)

async def send_direct_chat(writer, my_uid):
    """
    Prompt for a recipient callsign + message, then send a direct GeoChat (b-t-f).
    """
    loop = asyncio.get_event_loop()
    while True:
        to_uid = await loop.run_in_executor(None, input, "To: ")
        to_uid = to_uid.strip()
        if not to_uid:
            continue

        text = await loop.run_in_executor(None, input, f"Message to {to_uid}: ")
        text = text.strip()
        if not text:
            continue

        now = pytak.cot_time()
        conv_id = f"ChatThread.{my_uid}.{to_uid}"

        ev = ET.Element("event", {
            "version":"2.0", "type":CHAT_TYPE, "uid":conv_id,
            "how":"h-g-i-g-o", "time":now, "start":now,
            "stale":pytak.cot_time(3600)
        })
        ET.SubElement(ev, "point", {
            "lat":"0","lon":"0","hae":"9999999",
            "ce":"9999999","le":"9999999"
        })

        det = ET.SubElement(ev, "detail")
        ET.SubElement(det, "__chat", {
            "id":conv_id,
            "chatroom":conv_id,
            "senderCallsign":my_uid,
            "groupOwner":"false"
        })
        ET.SubElement(det, "chatgrp", {
            "id":conv_id,
            UID0_FIELD: my_uid,
            UID1_FIELD: to_uid
        })
        ET.SubElement(det, "hierarchy")
        ET.SubElement(det, "link", {
            "uid":my_uid, "type":"a-f-G-U-C-I", "relation":"p-p"
        })
        ET.SubElement(det, "remarks", {
            "source":my_uid, "to":to_uid, "time":now
        }).text = text

        # Tell ATAK to pop the direct‐chat UI for to_uid
        marti = ET.SubElement(det, "marti")
        ET.SubElement(marti, "dest", {"callsign": to_uid})

        writer.write(ET.tostring(ev))
        await writer.drain()

async def recv_direct_chat(reader, my_uid):
    """
    Listen for incoming ChatType=b-t-f events that include you,
    and print out direct one-to-one messages.
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
            remarks = det.find("remarks")
            if chatgrp is None or remarks is None:
                continue

            # Check if we're participant uid0 or uid1
            if (chatgrp.get(UID0_FIELD) == my_uid
                and chatgrp.get(UID1_FIELD) ):
                other = chatgrp.get(UID1_FIELD)
            elif (chatgrp.get(UID1_FIELD) == my_uid
                  and chatgrp.get(UID0_FIELD) ):
                other = chatgrp.get(UID0_FIELD)
            else:
                continue

            # Skip messages we sent ourselves
            if remarks.get("source") == my_uid:
                continue

            print(f"\n[Chat] {other} → me: {remarks.text}\n")

async def main():
    # --- TLS Configuration ---
    cfg = ConfigParser()
    cfg.add_section("tak_tls")
    cfg.set("tak_tls", "COT_URL", "tls://10.224.5.255:8089")
    cfg.set("tak_tls", "COT_HOST_ID", "cm4-client")
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_CERT", r"C:\Users\Brandon Camacho\Documents\Repos\oi-cm4-toolkit\tak\certs\client_cert.pem")
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_KEY",  r"C:\Users\Brandon Camacho\Documents\Repos\oi-cm4-toolkit\tak\certs\client_key.pem")
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_CAFILE",r"C:\Users\Brandon Camacho\Documents\Repos\oi-cm4-toolkit\tak\certs\ca_bundle.pem")
    # Testing only—remove in production
    cfg.set("tak_tls", "PYTAK_TLS_DONT_VERIFY",       "1")
    cfg.set("tak_tls", "PYTAK_TLS_DONT_CHECK_HOSTNAME","1")
    conf = cfg["tak_tls"]

    # Establish the TLS CoT stream
    reader, writer = await pytak.protocol_factory(conf)
    my_uid = conf["COT_HOST_ID"]

    # Run all tasks concurrently
    await asyncio.gather(
        send_presence(writer, my_uid),
        recv_direct_chat(reader, my_uid),
        send_direct_chat(writer, my_uid),
    )

if __name__=="__main__":
    asyncio.run(main())
