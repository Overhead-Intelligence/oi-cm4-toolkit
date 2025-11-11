#!/usr/bin/env python3
import asyncio
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak
from collections import defaultdict
import math
import sys
import uuid
import random
sys.path.append('testing') 

# custom module to read CSV values
from cot_broadcast import read_csv_values

# Configuration settings
#SERVER_URL = "tls://45.32.196.115:8089" # vector server
SERVER_URL = "tls://35.231.4.140:8089"   # OI google cloud server
CALLSIGN   = "UAS_Test_Drone"
rd = random.Random()
rd.seed(CALLSIGN)
#UID = str(uuid.UUID(int=rd.getrandbits(128), version=4)) #CALLSIGN + "-" + 
UID        = "UAS_Test_Drone"

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
    cfg.set("tak", "PYTAK_TLS_CLIENT_CERT", "/home/droneman/oi-cm4-toolkit/tak/certs/Magellan_cert.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_KEY",  "/home/droneman/oi-cm4-toolkit/tak/certs/Magellan_key.pem")
    cfg.set("tak", "PYTAK_TLS_CLIENT_CAFILE", "/home/droneman/oi-cm4-toolkit/tak/certs/Magellan_ca_bundle.pem")
    # for testing only or if needed
    cfg.set("tak", "PYTAK_TLS_DONT_VERIFY",       "1")
    cfg.set("tak", "PYTAK_TLS_DONT_CHECK_HOSTNAME","1")
    return cfg["tak"]


def make_presence() -> bytes:
    now = pytak.cot_time()
    # ——— Use your real data later ———
    # lat, lon, alt, battery, heading, speed, gimbal_az, gimbal_el = read_csv_values()
    lat, lon, alt = 27.95, -81.62, 10
    heading = 200.0        # Drone heading (degrees, 0 = North)
    speed = 150.0          # m/s
    gimbal_az = 30.0      # Camera azimuth offset from heading
    gimbal_el = -25.0     # Camera elevation (negative = down)
    fov = 60.0            # Horizontal FOV (degrees)
    vfov = 38.0           # Vertical FOV
    sensor_range = 2000   # Max range in meters

    ev = ET.Element("event", {
        "version": "2.0",
        "uid": UID,
        "type": "a-f-A-M-F-Q",
        "time": now,
        "start": now,
        "stale": pytak.cot_time(30),
        "how": "m-g",
        "access": "Undefined"
    })

    ET.SubElement(ev, "point", {
        "lat": f"{lat:.6f}",
        "lon": f"{lon:.6f}",
        "hae": f"{alt}",
        "ce": "10.0",
        "le": "10.0"
    })

    det = ET.SubElement(ev, "detail")
    uastool = ET.SubElement(det, "_uastool")
    uastool.set("extendedCot", "true")
    uastool.set("activeRoute", "false")


    ET.SubElement(det, "track", {
        "course": f"{heading:.2f}",
        "speed": f"{speed:.2f}",
        "slope": " 0.0"
    })
    # ——— SPATIAL: REQUIRED FOR WINTAK POINTER & CONE ———
    spatial = ET.SubElement(det, "spatial")
    ET.SubElement(spatial, "attitude", {
        "roll": "0.0",
        "pitch": "0.0",
        "yaw": f"{heading:.2f}"
    })
    ET.SubElement(spatial, "spin", {
        "roll": "0.0", "pitch": "0.0", "yaw": "0.0"
    })

    
    sensor = ET.SubElement(det, "sensor", {
        "azimuth": f"{heading:.2f}",
        "elevation": f"{gimbal_el:.2f}",
        "fov": f"{fov:.1f}",
        "vfov": f"{vfov:.1f}",
        "range": str(sensor_range),
        "type": "r-e",           # r-e = remote electro-optical
        "version": "0.6",
        "north": "0.0",          # Optional, usually 0
        "roll": "0.0"
    })
    # ——— STRAIGHT WHITE LINE (100m ahead) ———
    line_length_deg = 0.0162  # ~100m at equator (adjust for latitude if needed)
    line_angle_offset = 0.0
    line_heading = (heading + line_angle_offset) % 360

    delta_lat = line_length_deg * math.cos(math.radians(line_heading))
    delta_lon = line_length_deg * math.sin(math.radians(line_heading)) / math.cos(math.radians(lat))
    end_lat = lat + delta_lat
    end_lon = lon + delta_lon

    shape = ET.SubElement(det, "shape")
    poly = ET.SubElement(shape, "polyline", {
        "closed": "false",
        "ownerUID": UID
    })
    ET.SubElement(poly, "vertex", {"lat": f"{lat:.6f}", "lon": f"{lon:.6f}"})
    ET.SubElement(poly, "vertex", {"lat": f"{end_lat:.6f}", "lon": f"{end_lon:.6f}"})



    return ET.tostring(ev, encoding="utf-8")



# main async function
async def async_main():
    
    # — TLS setup —
    conf = build_tls_conf()
    tls_reader, tls_writer = await pytak.protocol_factory(conf)
    print(f"TLS connected to {SERVER_URL}")

    # send initial presence
    tls_writer.write(make_presence());  await tls_writer.drain()


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
           # udp_sock.sendto(pkt, (MCAST_ADDR, MCAST_PORT))
            tls_writer.write(pkt)
            await tls_writer.drain()
        tls_writer.close()
        await tls_writer.wait_closed()
       # udp_sock.close()
        asyncio.get_event_loop().stop()
     # run all three
    await asyncio.gather(
        #process_events(tls_reader, udp_sock, tls_writer),
        presence_loop(),
        #input_loop(),
    )


###### MAIN ########

if __name__=="__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
