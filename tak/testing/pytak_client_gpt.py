#!/usr/bin/env python3
import asyncio
from configparser import ConfigParser
import xml.etree.ElementTree as ET
import pytak

def get_location():
    # TODO → Replace with your real GPS reader
    return 27.95391667, -81.61530556, 10.0

def make_cot(lat, lon, hae, uid, cot_type="a-f-G-U-C"):
    """Helper to build a CoT XML message as bytes."""
    return pytak.gen_cot(
        lat=lat, lon=lon, hae=hae,
        uid=uid, cot_type=cot_type
    )

async def send_loop(writer, uid):
    """Every 5s read location, build CoT, send via TLS writer."""
    while True:
        lat, lon, hae = get_location()
        cot = make_cot(lat, lon, hae, uid)
        writer.write(cot)
        await writer.drain()
        print(f"[SENT]  {lat:.6f},{lon:.6f},{hae}")
        await asyncio.sleep(5)

async def recv_loop(reader):
    """Continuously read incoming CoT events and print them."""
    buffer = b""
    while True:
        data = await reader.read(4096)
        if not data:
            print("Connection closed by server.")
            return
        buffer += data
        # Split complete events by </event>
        while b"</event>" in buffer:
            packet, buffer = buffer.split(b"</event>", 1)
            xml = packet + b"</event>"
            print("[RECV]\n", xml.decode(), "\n")
            # (Optional) parse and react:
            # root = ET.fromstring(xml)
            # msg_type = root.get("type")
            # ...  

async def main():
    # --- 1) Build your TLS config ---
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
    # For testing only; remove in prod.
    cfg.set("tak_tls", "PYTAK_TLS_DONT_VERIFY", "1")
    cfg.set("tak_tls", "PYTAK_TLS_DONT_CHECK_HOSTNAME", "1")
    conf = cfg["tak_tls"]

    # --- 2) Connect via TLS ---
    reader, writer = await pytak.protocol_factory(conf)
    uid = conf["COT_HOST_ID"]

    # --- 3) Run send & receive loops in parallel ---
    await asyncio.gather(
        send_loop(writer, uid),
        recv_loop(reader),
    )

if __name__ == "__main__":
    asyncio.run(main())
