#!/usr/bin/env python3
import asyncio
import xml.etree.ElementTree as ET
from configparser import ConfigParser
import pytak

def gen_cot():
    """Generate a basic CoT Event."""
    root = ET.Element("event")
    root.set("version", "2.0")
    root.set("type", "t-x-c-m")  # using a chat message type
    root.set("uid", "chatclient@cm4")
    root.set("how", "m-g")
    root.set("time", pytak.cot_time())
    root.set("start", pytak.cot_time())
    root.set("stale", pytak.cot_time(60))  # Stale in 60 seconds

    # Set a sample geographical point (optional for chat messages)
    point_attrib = {
        "lat": "27.95391667",      # sample latitude
        "lon": "-81.61530556",     # sample longitude
        "hae": "0",
        "ce": "10",
        "le": "10"
    }
    ET.SubElement(root, "point", attrib=point_attrib)
    return ET.tostring(root)

class MySender(pytak.QueueWorker):
    """
    Worker that periodically generates and sends CoT events.
    This example sends a chat event every 5 seconds.
    """
    async def handle_data(self, data):
        # Directly put the generated CoT event onto the tx_queue
        await self.put_queue(data)

    async def run(self):
        #while True:
            cot_event = gen_cot()
            self._logger.info("Sending CoT Event:\n%s\n", cot_event.decode())
            await self.handle_data(cot_event)
            await asyncio.sleep(5)

class MyReceiver(pytak.QueueWorker):
    """
    Worker that handles incoming CoT events.
    """
    async def handle_data(self, data):
        self._logger.info("Received CoT Event:\n%s\n", data.decode())

    async def run(self):
        while True:
            # Get an event from the rx_queue and process it.
            cot_event = await self.queue.get()
            await self.handle_data(cot_event)

async def main():
    """Set up the configuration and start sender and receiver tasks."""
    config = ConfigParser()
    config["mycottool"] = {
        "COT_URL": "tcp://10.224.5.255:8443"
    }
    conf = config["mycottool"]

    # Initialize the PyTAK CLI tool with the configuration.
    clitool = pytak.CLITool(conf)
    await clitool.setup()

    # Add our sender and receiver workers to the PyTAK task list.
    clitool.add_tasks({
        MySender(clitool.tx_queue, conf),
        MyReceiver(clitool.rx_queue, conf)
    })

    # Run all tasks concurrently.
    await clitool.run()

if __name__ == "__main__":
    asyncio.run(main())