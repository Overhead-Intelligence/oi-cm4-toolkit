#!/usr/bin/env python3
import asyncio
import subprocess
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak

def get_location():
    # TODO ↦ Replace with your GPS-reading routine
    return 27.95391667, -81.61530556, 10.0

def make_cot(lat, lon, hae, uid, cot_type):
    """Build a CoT XML message (bytes)."""
    return pytak.gen_cot(
        lat=lat, lon=lon, hae=hae,
        uid=uid, cot_type=cot_type
    )

async def send_location(writer, uid):
    while True:
        lat, lon, hae = get_location()
        cot = make_cot(lat, lon, hae, uid, "a-f-A-U-A")
        writer.write(cot)
        await writer.drain()
        await asyncio.sleep(5)

async def recv_and_handle(reader, writer, my_uid):
    buffer = b""
    while True:
        data = await reader.read(4096)
        if not data:
            print("► Connection closed by server")
            return
        buffer += data
        # Split out complete <event>…</event> packets
        while b"</event>" in buffer:
            packet, buffer = buffer.split(b"</event>", 1)
            xml = packet + b"</event>"
            try:
                root = ET.fromstring(xml)
            except ET.ParseError:
                continue

            # Extract the sender UID (COT_HOST_ID) if present
            detail = root.find("detail")
            contact = detail.find("contact") if detail is not None else None
            sender = contact.get("callsign") if contact is not None else root.get("uid")

            # Only process messages _to_ us, or broadcasts
            # e.g. you might convention: if root.get("type")=="t-x-c-m", it's chat
            if sender != my_uid:
                # Look for a <chat> or <command> element
                chat = detail.find("chat") if detail is not None else None
                cmd  = detail.find("command") if detail is not None else None

                if chat is not None:
                    text = chat.text.strip()
                    print(f"◄ Chat from {sender}: {text}")
                    # echo back
                    reply = ET.Element("detail")
                    ET.SubElement(reply, "contact", callsign=my_uid)
                    ET.SubElement(reply, "chat").text = f"ACK: {text}"
                    cot = make_cot(0,0,0, my_uid, "t-x-c-m")
                    # inject our custom detail
                    cot_root = ET.fromstring(cot)
                    old_det = cot_root.find("detail")
                    cot_root.remove(old_det)
                    cot_root.append(reply)
                    writer.write(ET.tostring(cot_root))
                    await writer.drain()

                elif cmd is not None:
                    command_text = cmd.text.strip()
                    print(f"◄ Command from {sender}: {command_text}")
                    # Simple command execution (dangerous! sandbox or whitelist in prod)
                    try:
                        result = subprocess.check_output(
                            command_text, shell=True, stderr=subprocess.STDOUT, timeout=5
                        ).decode().strip()
                    except Exception as e:
                        result = f"Error: {e}"

                    # send back a chat with the result
                    reply = ET.Element("detail")
                    ET.SubElement(reply, "contact", callsign=my_uid)
                    ET.SubElement(reply, "chat").text = result[:200]  # limit length
                    cot = make_cot(0,0,0, my_uid, "t-x-c-m")
                    cot_root = ET.fromstring(cot)
                    old_det = cot_root.find("detail")
                    cot_root.remove(old_det)
                    cot_root.append(reply)
                    writer.write(ET.tostring(cot_root))
                    await writer.drain()

async def main():
    # --- TLS config (as before) ---
    cfg = ConfigParser()
    cfg.add_section("tak_tls")
    cfg.set("tak_tls", "COT_URL", "tls://10.224.5.255:8089")
    cfg.set("tak_tls", "COT_HOST_ID", "cm4-tls-client")
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_CERT",
            r"C:\Users\Brandon Camacho\Documents\Repos\oi-cm4-toolkit\tak\certs\client_cert.pem")
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_KEY",
            r"C:\Users\Brandon Camacho\Documents\Repos\oi-cm4-toolkit\tak\certs\client_key.pem")
    cfg.set("tak_tls", "PYTAK_TLS_CLIENT_CAFILE",
            r"C:\Users\Brandon Camacho\Documents\Repos\oi-cm4-toolkit\tak\certs\ca_bundle.pem")
    # Testing only—remove in production
    cfg.set("tak_tls", "PYTAK_TLS_DONT_VERIFY", "1")
    cfg.set("tak_tls", "PYTAK_TLS_DONT_CHECK_HOSTNAME", "1")
    conf = cfg["tak_tls"]

    # Create our TLS connection
    reader, writer = await pytak.protocol_factory(conf)
    uid = conf["COT_HOST_ID"]

    # Run both send & receive concurrently
    await asyncio.gather(
        send_location(writer, uid),
        recv_and_handle(reader, writer, uid),
    )

if __name__ == "__main__":
    asyncio.run(main())
