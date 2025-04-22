#!/usr/bin/env python3
import asyncio
from configparser import ConfigParser
from datetime import datetime, timezone
import pytak

def get_location():
    """
    Stub for obtaining current location.
    Replace this with your GPS‐reading code.
    Returns (lat, lon, hae) in decimal degrees & meters.
    """
    # e.g. read from your CSV or GPS serial port
    return 27.95391667, -81.61530556, 10.0

async def send_location(writer, uid):
    """
    Build a CoT XML event and send it over the provided writer.
    """
    lat, lon, hae = get_location()
    # Use a UAV/drone icon type: a-f-A-U-A
    cot = pytak.gen_cot(
        lat=lat,
        lon=lon,
        hae=hae,
        uid=uid,
        cot_type="a-f-A-U-A"
    )
    writer.write(cot)
    # If this is a stream writer, drain; if a datagram, this is a no-op
    # if hasattr(writer, "drain"):
    #     await writer.drain()

async def main():
    # --- 1. Build config pointing to your TAK server ---
    cfg = ConfigParser()
    cfg.add_section("tak")
    
    # For UDP broadcast/multicast use udp://<host>:<port>
    # Change to tcp://<server>:<port> or tls://... as needed
    cfg.set("tak", "COT_URL", "tcp://10.224.5.255:8089")
    
    # This host ID shows up in ATAK as the callsign/UID
    cfg.set("tak", "COT_HOST_ID", "cm4-client")
    conf = cfg["tak"]

    # --- 2. Create reader/writer pair via PyTAK ---
    reader, writer = await pytak.protocol_factory(conf)
    uid = conf.get("COT_HOST_ID")

    # --- 3. Periodically send location updates ---
    try:
        while True:
            await send_location(writer, uid)
            print(f"[{datetime.now(timezone.utc).isoformat()}] Sent location: {get_location()}")
            await asyncio.sleep(5)
    except asyncio.CancelledError:
        pass
    finally:
        # clean up socket if needed
        if hasattr(writer, "close"):
            writer.close()
            if asyncio.iscoroutine(writer.close()):
                await writer.close()

if __name__ == "__main__":
    asyncio.run(main())
