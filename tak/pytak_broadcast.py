import asyncio
from configparser import ConfigParser
import pytak
import time

async def main():
    # Define your telemetry and identification parameters.
    lat = 27.95391667
    lon = -81.61530556
    altitude = 10.0  # Height above ellipsoid in meters
    callsign = "Drone1"
    # Set uid to the callsign; this is used for identification and can control the icon.
    uid = callsign
    # Use a CoT type that corresponds to a civil fixed-wing (adjust as needed)
    cot_type = "a-f-A-C-F"
    
    # Generate a CoT event XML string (as bytes) using pytak.gen_cot
    cot_xml = pytak.gen_cot(
        lat=lat, 
        lon=lon, 
        hae=altitude, 
        uid=uid, 
        cot_type=cot_type
    )
    
    print("Generated CoT event:")
    print(cot_xml.decode('utf-8'))
    
    # Create a simple configuration for the UDP connection.
    config = ConfigParser()
    config.add_section("example")
    # Here we set the COT_URL to a UDP destination (adjust to your network setup)
    config.set("example", "COT_URL", "udp://255.255.255.255:6969")
    # Set the host identifier
    config.set("example", "COT_HOST_ID", uid)
    conf = config["example"]
    
    # Use PyTAK's protocol_factory to get a reader and writer for the connection.
    reader, writer = await pytak.protocol_factory(conf)

    try:
        while True:
            # Send the CoT XML event using the writer.
            # Depending on the writer implementation, use write/drain or send.
            if hasattr(writer, "write"):
                writer.write(cot_xml)
                print("CoT event write.")
                if hasattr(writer, "drain"):
                    await writer.drain()
                    print("CoT event drain.")
            elif hasattr(writer, "send"):
                await writer.send(cot_xml)
                print("CoT event sent.")
            
            time.sleep(5)

    except KeyboardInterrupt:
        print("Broadcasting stopped.")
    finally:
        
        if hasattr(writer, "close"):
            writer.close()
            # In some cases close() is a coroutine.
            if asyncio.iscoroutine(writer.close()):
                await writer.close()
    

if __name__ == "__main__":
    asyncio.run(main())