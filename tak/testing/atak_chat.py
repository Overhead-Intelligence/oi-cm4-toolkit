import asyncio
import os
import pytak
import xml.etree.ElementTree as ET
import logging
import uuid
import time
import socket
from typing import Optional, Dict, Any
import threading

class ChatWorker(pytak.QueueWorker):
    """Worker class to handle chat message processing."""
    
    def __init__(self, queue, config, chat_client):
        super().__init__(queue, config)
        self.chat_client = chat_client
        self.logger = logging.getLogger('atak_chat.worker')
        
    async def handle_data(self, data):
        """Handle pre-CoT data, serialize to CoT Event, then puts on queue."""
        try:
            self.logger.debug("Attempting to send data to queue")
            await self.put_queue(data)
            self.logger.debug("Data sent to queue successfully")
        except Exception as e:
            self.logger.error(f"Error in handle_data: {str(e)}")
            if isinstance(e, ConnectionResetError):
                self.logger.warning("Connection reset detected")
                self.chat_client.connection_lost = True

    async def run(self):
        """Run the loop for processing chat messages."""
        try:
            self.logger.info("ChatWorker starting up")
            # Send initial presence
            presence_msg = self.chat_client.create_presence_message()
            self.logger.debug("Sending initial presence message")
            await self.handle_data(presence_msg)
            await asyncio.sleep(2)  # Wait a moment before allowing messages
            self.logger.info("ChatWorker initialization complete")
        except Exception as e:
            self.logger.error(f"Error in ChatWorker run: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

class ChatMessageHandler:
    """Handles processing of received chat messages."""
    
    def __init__(self):
        self.logger = logging.getLogger('atak_chat.message_handler')
        self.message_queue = asyncio.Queue()
        self.last_sender = None
        self.sender_history = {}  # Maps sender callsigns to their UIDs

    def parse_chat_message(self, data):
        """Parse a CoT message and extract chat information."""
        try:
            # Decode and parse the XML data
            data_str = data.decode() if isinstance(data, bytes) else data
            root = ET.fromstring(data_str)
            
            # Check if it's a chat message
            if root.get("type") == "b-t-f":
                detail = root.find("detail")
                if detail is not None:
                    # Extract message components
                    message_info = {
                        "text": None,
                        "sender": "Unknown",
                        "chatroom": "Unknown",
                        "sender_uid": None,
                        "raw_xml": data_str
                    }
                    
                    # Get message text
                    remarks = detail.find("remarks")
                    if remarks is not None:
                        message_info["text"] = remarks.text
                    
                    # Get chat metadata
                    chat = detail.find("__chat") or detail.find("chat")
                    if chat is not None:
                        message_info["chatroom"] = chat.get("chatroom", "Unknown")
                        message_info["sender"] = chat.get("senderCallsign", "Unknown")
                    
                    # Get sender UID
                    link = detail.find("link")
                    if link is not None:
                        message_info["sender_uid"] = link.get("uid")
                        
                    # Store sender information
                    if message_info["sender"] != "Unknown" and message_info["sender_uid"]:
                        self.last_sender = message_info["sender"]
                        self.sender_history[message_info["sender"]] = message_info["sender_uid"]
                    
                    return message_info
            
            return None
        except Exception as e:
            self.logger.error(f"Error parsing chat message: {str(e)}")
            return None

class ChatReceiver(pytak.QueueWorker):
    """Handles receiving chat messages."""
    
    def __init__(self, rx_queue, config, message_handler):
        super().__init__(rx_queue, config)
        self.logger = logging.getLogger('atak_chat.receiver')
        self.message_handler = message_handler
        self.monitoring = False

    async def handle_data(self, data):
        """Handle data from the receive queue."""
        try:
            message_info = self.message_handler.parse_chat_message(data)
            if message_info:
                await self.message_handler.message_queue.put(message_info)
                self.logger.debug(f"Received chat message from {message_info['sender']}: {message_info['text']}")
        except Exception as e:
            self.logger.error(f"Error handling received data: {str(e)}")

    async def run(self):
        """Process messages from the receive queue."""
        self.logger.info("Chat receiver started")
        while True:
            try:
                data = await self.queue.get()
                await self.handle_data(data)
            except asyncio.CancelledError:
                self.logger.info("Chat receiver cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in receiver run loop: {str(e)}")

class AtakChat:
    def __init__(self, vehicle_id: int, client_cert: str, server_cert: str, server_url="argustak.com", 
                 ssl_port=8089, tcp_port=8087, client_password="argustak"):
        # Configure logging first
        logging.basicConfig(
            level=logging.DEBUG,  # Set to DEBUG for more detailed logs
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('atak_chat')
        
        self.vehicle_id = vehicle_id
        self.client_cert = client_cert
        self.server_cert = server_cert
        self.server_url = server_url
        self.ssl_port = ssl_port
        self.tcp_port = tcp_port
        self.client_password = client_password
        self.running = False
        self.clitool = None
        self.task = None
        self.loop = None
        self.connection_lost = False
        self.connection_attempts = 0
        self.max_connection_attempts = 100  # Increased from 5 to 100 to keep trying
        self.connection_retry_delay = 3  # seconds
        self.connection_established = False
        self.initial_connection_timeout = 300  # 5 minutes timeout (300 seconds)
        self.connection_event = asyncio.Event()  # Used to signal successful connection
        
        # Position update optimization
        self.position_updated = False
        self.position_lock = threading.Lock()
        self.last_position_update_time = 0
        self.position_update_min_interval = 0.5  # Increased to 500ms minimum between updates
        
        # Default position (Washington, DC)
        self.current_position = {
            "lat": 38.897957,   # Latitude
            "lon": -77.036560,  # Longitude
            "hae": 100.0,       # Height above ellipsoid (meters)
            "ce": 10.0,         # Circular error (meters)
            "le": 10.0,         # Linear error (meters)
            "course": 0.0,      # Course in degrees
            "speed": 0.0        # Speed in m/s
        }
        
        # Identity configuration
        self.identity = {
            "uid": f"PYTHON-CHAT-{vehicle_id}",
            "callsign": f"Pilot_{vehicle_id}",
            "team_color": "Blue",
            "team_name": "Python Team",
            "role": "Team Member",
            "device": "Python Client"
        }
        
        self.logger.info(f"AtakChat initialized with vehicle_id: {vehicle_id}")
        self.logger.debug(f"Using certificates - Client: {client_cert}, Server: {server_cert}")
        self.logger.debug(f"Using server: {server_url} (SSL: {ssl_port}, TCP: {tcp_port})")

        # Add message handling
        self.message_handler = ChatMessageHandler()
        self.chat_receiver = None

    def update_position(self, lat: float, lon: float, alt: float = None, course: float = None, speed: float = None) -> None:
        """
        Update the current position.
        
        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            alt: Optional altitude in meters
            course: Optional course in degrees
            speed: Optional speed in m/s
        """
        with self.position_lock:
            self.current_position["lat"] = lat
            self.current_position["lon"] = lon
            if alt is not None:
                self.current_position["hae"] = alt
            if course is not None:
                self.current_position["course"] = course
            if speed is not None:
                self.current_position["speed"] = speed
            self.position_updated = True
            self.logger.debug(f"Position updated to: lat={lat:.6f}, lon={lon:.6f}, alt={self.current_position['hae']:.1f}m")

    def create_presence_message(self) -> bytes:
        """Create a presence message with current position."""
        root = ET.Element("event")
        root.set("version", "2.0")
        root.set("type", "a-f-G-U-C")  # Friendly Ground Unit, Civilian
        root.set("uid", self.identity["uid"])
        root.set("how", "m-g")
        root.set("time", pytak.cot_time())
        root.set("start", pytak.cot_time())
        root.set("stale", pytak.cot_time(600))  # 10 minutes

        # Set current position
        point = ET.SubElement(root, "point")
        point.set("lat", str(self.current_position["lat"]))
        point.set("lon", str(self.current_position["lon"]))
        point.set("hae", str(self.current_position["hae"]))
        point.set("ce", str(self.current_position["ce"]))
        point.set("le", str(self.current_position["le"]))

        # Add contact details
        detail = ET.SubElement(root, "detail")
        
        # Contact info
        contact = ET.SubElement(detail, "contact")
        contact.set("callsign", self.identity["callsign"])
        contact.set("endpoint", "*:-1:stcp")
        
        # Group/team info
        group = ET.SubElement(detail, "group")
        group.set("role", self.identity["role"])
        group.set("name", self.identity["team_name"])
        
        # Color - helps with visual identification
        color = ET.SubElement(detail, "__group")
        color.set("name", self.identity["team_color"])
        
        # User icon
        usericon = ET.SubElement(detail, "usericon")
        usericon.set("iconsetpath", "34ae1613-9645-4222-a9d2-e5f243dea2865/Service/PYTHON.png")
        
        # Status info
        status = ET.SubElement(detail, "status")
        status.set("battery", "100")
        
        # Precision location
        precisionlocation = ET.SubElement(detail, "precisionlocation")
        precisionlocation.set("altsrc", "GPS")
        precisionlocation.set("geopointsrc", "GPS")
        
        # TAK client info
        takv = ET.SubElement(detail, "takv")
        takv.set("device", self.identity["device"])
        takv.set("platform", "Python")
        takv.set("os", "Python")
        takv.set("version", "1.0")
        
        # Track info
        track = ET.SubElement(detail, "track")
        track.set("course", str(self.current_position["course"]))
        track.set("speed", str(self.current_position["speed"]))

        return ET.tostring(root)

    # A new method to forcibly close any existing sockets for this vehicle ID
    def _force_socket_cleanup(self):
        """Force cleanup of any lingering sockets"""
        try:
            self.logger.info(f"Attempting to force socket cleanup for vehicle {self.vehicle_id}")
            # Try to find and close any sockets that might be using our ports
            ssl_port = 8089
            tcp_port = 8087
            
            # This is a best-effort attempt, it won't catch all scenarios
            for sock in socket.socket.__subclasses__():
                for instance in sock.__subclasses__():
                    for obj in instance.__subclasses__():
                        try:
                            if hasattr(obj, 'getsockname'):
                                sock_info = obj.getsockname()
                                if sock_info and len(sock_info) >= 2:
                                    if sock_info[1] in (ssl_port, tcp_port):
                                        self.logger.info(f"Closing socket on port {sock_info[1]}")
                                        obj.close()
                        except:
                            pass
        except Exception as e:
            self.logger.error(f"Error during force socket cleanup: {str(e)}")

    async def connect(self) -> bool:
        """Connect to the TAK server with improved reliability."""
        self.logger.info(f"Attempting to connect to TAK server (vehicle {self.vehicle_id})")
        
        # Track connection attempts for this round
        self.connection_attempts += 1
        
        # Clean up existing resources more aggressively
        if self.clitool:
            self.logger.debug("Cleaning up existing connection")
            try:
                await self.clitool.cleanup()
            except Exception as e:
                self.logger.warning(f"Error during cleanup: {str(e)}")
            self.clitool = None
            
        # Attempt to forcibly clean up any lingering sockets
        self._force_socket_cleanup()
        
        # Wait a moment to allow socket cleanup
        await asyncio.sleep(0.5)
        
        # Connection configurations with timeouts
        connection_attempts = [
            {
                "name": "SSL on port " + str(self.ssl_port),
                "config": {
                    "COT_URL": f"ssl://{self.server_url}:{self.ssl_port}",
                    "PYTAK_TLS_CLIENT_CERT": self.client_cert,
                    "PYTAK_TLS_CLIENT_KEY": self.client_cert,
                    "PYTAK_TLS_CLIENT_PASSWORD": self.client_password,
                    "PYTAK_TLS_DONT_VERIFY": "true",
                    "PYTAK_TLS_DONT_CHECK_HOSTNAME": "true",
                    "PYTAK_TLS_CA_CERT": self.server_cert,
                    "PYTAK_CONNECTION_TIMEOUT": "15",  # Shorter timeout
                    "PYTAK_LINGER_TIME": "0",  # Disable socket lingering
                    "FTS_COMPAT": "false"  # Disable FTS compatibility mode for faster updates
                }
            },
            {
                "name": "TCP on port " + str(self.tcp_port),
                "config": {
                    "COT_URL": f"tcp://{self.server_url}:{self.tcp_port}",
                    "PYTAK_CONNECTION_TIMEOUT": "15",  # Shorter timeout
                    "PYTAK_LINGER_TIME": "0",  # Disable socket lingering
                    "FTS_COMPAT": "false"  # Disable FTS compatibility mode for faster updates
                }
            }
        ]

        # Add some randomness to the connection attempt order based on vehicle ID
        if self.vehicle_id % 2 == 1:
            connection_attempts.reverse()

        # Try connection methods until one works
        for attempt in connection_attempts:
            self.logger.info(f"Vehicle {self.vehicle_id} trying connection method: {attempt['name']}")
            try:
                # Create new connection with a timeout
                self.logger.debug("Creating new CLITool instance")
                self.clitool = pytak.CLITool(attempt["config"])
                
                # Setup connection with timeout
                self.logger.debug("Setting up connection")
                setup_task = asyncio.create_task(self.clitool.setup())
                
                # Wait for setup with timeout
                try:
                    await asyncio.wait_for(setup_task, timeout=20)  # 20 second timeout
                except asyncio.TimeoutError:
                    self.logger.warning(f"Connection setup timed out for {attempt['name']}")
                    # Clean up the failed connection attempt
                    if self.clitool:
                        try:
                            await self.clitool.cleanup()
                        except Exception as e:
                            self.logger.warning(f"Error during cleanup after timeout: {str(e)}")
                        self.clitool = None
                    continue
                
                self.logger.info(f"Vehicle {self.vehicle_id} connected successfully using {attempt['name']}")
                
                # Add the chat workers
                self.chat_receiver = ChatReceiver(self.clitool.rx_queue, attempt["config"], self.message_handler)
                self.clitool.add_tasks(set([
                    ChatWorker(self.clitool.tx_queue, attempt["config"], self),
                    self.chat_receiver
                ]))
                
                self.connection_lost = False
                self.connection_attempts = 0  # Reset on successful connection
                self.connection_established = True
                self.connection_event.set()  # Signal successful connection
                return True
                
            except Exception as e:
                self.logger.error(f"Connection attempt failed: {str(e)}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Clean up after failed attempt
                if self.clitool:
                    try:
                        await self.clitool.cleanup()
                    except Exception as cleanup_error:
                        self.logger.warning(f"Error during cleanup after failed connection: {str(cleanup_error)}")
                    self.clitool = None
                
                # Wait before next attempt
                await asyncio.sleep(1)
                continue

        self.logger.error(f"All connection attempts failed for vehicle {self.vehicle_id}")
        
        # Add a delay before allowing another connection attempt
        await asyncio.sleep(self.connection_retry_delay)
        
        return False

    async def persistent_connect(self) -> bool:
        """Persistently try to connect until successful or timeout occurs."""
        self.logger.info(f"Starting persistent connection for vehicle {self.vehicle_id} with {self.initial_connection_timeout}s timeout")
        
        # Reset connection event
        self.connection_event.clear()
        
        # Start time for timeout tracking
        start_time = time.time()
        
        # Loop until connected or timeout
        while True:
            # Check for timeout
            elapsed_time = time.time() - start_time
            if elapsed_time > self.initial_connection_timeout:
                self.logger.error(f"Connection timeout after {elapsed_time:.1f} seconds for vehicle {self.vehicle_id}")
                return False
                
            # Try to connect
            if await self.connect():
                self.logger.info(f"Vehicle {self.vehicle_id} successfully connected after {elapsed_time:.1f} seconds")
                return True
                
            # Log the attempt and remaining time
            remaining_time = self.initial_connection_timeout - elapsed_time
            self.logger.warning(f"Connection attempt {self.connection_attempts} failed for vehicle {self.vehicle_id}. "
                              f"Retrying... ({remaining_time:.1f} seconds remaining until timeout)")
            
            # Wait before next attempt with adaptive backoff
            # Start with short delays but gradually increase
            retry_delay = min(self.connection_retry_delay * (1 + self.connection_attempts / 10), 10)
            await asyncio.sleep(retry_delay)

    async def reconnect(self) -> bool:
        """Attempt to reconnect if the connection is lost."""
        self.logger.info(f"Attempting to reconnect vehicle {self.vehicle_id}")
        
        # Perform thorough cleanup
        if self.clitool:
            try:
                await self.clitool.cleanup()
            except Exception as e:
                self.logger.warning(f"Error cleaning up during reconnect: {str(e)}")
            self.clitool = None
        
        # Wait before attempting reconnect
        await asyncio.sleep(2)
        
        # Use persistent connect to keep trying until success
        return await self.persistent_connect()

    async def send_message(self, message: str, chat_room: str = "All Chat Rooms") -> bool:
        """Send a message to the specified chat room."""
        if not self.clitool or not self.running:
            self.logger.error("Not connected or not running")
            return False

        try:
            self.logger.debug(f"Preparing to send message to {chat_room}: {message}")
            
            # Generate a unique message ID
            message_id = uuid.uuid4().hex
            self.logger.debug(f"Generated message ID: {message_id}")
            
            # Create the message XML
            root = ET.Element("event")
            root.set("version", "2.0")
            root.set("type", "b-t-f")  # Chat/free text message
            root.set("uid", f"GeoChat.{self.identity['uid']}.{chat_room}.{message_id}")
            root.set("how", "h-g-i-g-o")  # Human input
            root.set("time", pytak.cot_time())
            root.set("start", pytak.cot_time())
            root.set("stale", pytak.cot_time(300))  # 5 minutes

            # Point information (use 0,0 for chat messages)
            point = ET.SubElement(root, "point")
            point.set("lat", "0.0")
            point.set("lon", "0.0")
            point.set("hae", "9999999.0")
            point.set("ce", "9999999.0")
            point.set("le", "9999999.0")

            # Detail section
            detail = ET.SubElement(root, "detail")
            
            # Chat metadata - using __chat as seen in working example
            chat = ET.SubElement(detail, "__chat")
            chat.set("chatroom", chat_room)
            chat.set("groupOwner", "false")
            chat.set("messageId", message_id)
            chat.set("id", chat_room)
            chat.set("senderCallsign", self.identity["callsign"])
            chat.set("parent", "RootContactGroup")
            
            # Add chatgrp element as seen in the working example
            chatgrp = ET.SubElement(chat, "chatgrp")
            chatgrp.set("uid0", self.identity["uid"])
            chatgrp.set("uid1", chat_room)
            chatgrp.set("id", chat_room)
            
            # Link to sender
            link = ET.SubElement(detail, "link")
            link.set("uid", self.identity["uid"])
            link.set("type", "a-f-G-U-C")
            link.set("relation", "p-p")
            
            # Message text with source and destination
            remarks = ET.SubElement(detail, "remarks")
            remarks.set("source", f"BAO.F.Python.{self.identity['uid']}")
            remarks.set("to", chat_room)
            remarks.set("time", pytak.cot_time())
            remarks.text = message
            
            # Additional marti destination info
            marti = ET.SubElement(detail, "marti")
            dest = ET.SubElement(marti, "dest")
            dest.set("callsign", chat_room)

            # Convert to bytes and send
            data = ET.tostring(root)
            self.logger.debug("Message XML created successfully")
            
            # Send the message
            self.logger.info(f"Sending chat message to {chat_room}: {message}")
            await self.clitool.tx_queue.put(data)
            self.logger.debug("Message sent to queue successfully")
            
            # Brief pause to avoid overwhelming the server
            await asyncio.sleep(0.5)
            return True

        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            if isinstance(e, ConnectionResetError):
                self.logger.warning("Connection reset detected during send")
                self.connection_lost = True
                # Attempt to reconnect in the background
                asyncio.create_task(self.reconnect())
            return False

    async def send_position_update(self) -> bool:
        """Send a position update to the TAK server."""
        if not self.clitool or not self.running:
            self.logger.error("Not connected or not running")
            return False

        try:
            self.logger.debug(f"Sending position update: lat={self.current_position['lat']:.6f}, lon={self.current_position['lon']:.6f}")
            presence_data = self.create_presence_message()
            await self.clitool.tx_queue.put(presence_data)
            return True
        except Exception as e:
            self.logger.error(f"Error sending position update: {str(e)}")
            if isinstance(e, ConnectionResetError):
                self.logger.warning("Connection reset detected during position update")
                self.connection_lost = True
                # Attempt to reconnect in the background
                asyncio.create_task(self.reconnect())
            return False

    async def send_direct_position_update(self) -> bool:
        """
        Send a position update directly to the TAK server with minimal latency.
        This bypasses FTS compatibility mode delays.
        """
        if not self.clitool or not self.running:
            self.logger.error("Not connected or not running for direct position update")
            return False
            
        try:
            # Check if we need to rate-limit the updates
            current_time = time.time()
            with self.position_lock:
                # Enforce a minimum time between position updates to prevent flooding
                elapsed = current_time - self.last_position_update_time
                if elapsed < self.position_update_min_interval:
                    self.logger.debug(f"Skipping position update (too soon: {elapsed:.3f}s < {self.position_update_min_interval:.3f}s)")
                    return True  # Pretend success but skip this update
                
                # Update the timestamp
                self.last_position_update_time = current_time
                
                # Reset the updated flag
                self.position_updated = False
                
                # Capture current position values within the lock
                presence_data = self.create_presence_message()
            
            # Get the tx_queue directly - outside the lock to prevent deadlocks
            if hasattr(self.clitool, 'tx_queue'):
                tx_queue = self.clitool.tx_queue
                
                # Non-blocking put - we're already in an async context
                await tx_queue.put(presence_data)
                
                self.logger.debug(f"Direct position update sent: lat={self.current_position['lat']:.6f}, lon={self.current_position['lon']:.6f}")
                return True
            else:
                # Fall back to regular method if tx_queue isn't available
                return await self.send_position_update()
                
        except Exception as e:
            self.logger.error(f"Error in direct position update: {str(e)}")
            if isinstance(e, ConnectionResetError):
                self.logger.warning("Connection reset detected during direct position update")
                self.connection_lost = True
            return False

    async def _connection_monitor(self):
        """Monitor connection status and attempt reconnection if needed."""
        self.logger.info(f"Starting connection monitor for vehicle {self.vehicle_id}")
        while self.running:
            try:
                if self.connection_lost:
                    self.logger.warning(f"Vehicle {self.vehicle_id} detected disconnection, attempting reconnect")
                    self.connection_lost = False
                    if await self.reconnect():
                        self.logger.info(f"Vehicle {self.vehicle_id} successfully reconnected")
                    else:
                        self.logger.error(f"Vehicle {self.vehicle_id} failed to reconnect")
                        self.connection_lost = True
                
                # Send periodic presence updates to keep connection alive
                if self.clitool and not self.connection_lost:
                    await self.send_position_update()
                
                await asyncio.sleep(15)  # Check every 15 seconds
            except asyncio.CancelledError:
                self.logger.info("Connection monitor cancelled")
                break
            except Exception as e:
                self.logger.error(f"Error in connection monitor: {str(e)}")
                await asyncio.sleep(5)  # Sleep on error

    def start(self) -> bool:
        """
        Start the chat client. This method blocks until a connection is established
        or until the timeout is reached.
        
        Returns:
            bool: True if connection was successful, False otherwise
        """
        if self.running:
            self.logger.warning("Already running")
            return True

        self.logger.info(f"Starting chat client for vehicle {self.vehicle_id}")
        self.running = True
        self.connection_established = False

        async def _run():
            try:
                self.logger.info(f"Initiating persistent connection for vehicle {self.vehicle_id}")
                
                # Use persistent connect to keep trying until timeout
                if await self.persistent_connect():
                    self.logger.info(f"Connection established for vehicle {self.vehicle_id}, starting main loop")
                    
                    # Start connection monitor
                    monitor_task = asyncio.create_task(self._connection_monitor())
                    
                    # Run the main client
                    try:
                        await self.clitool.run()
                    finally:
                        # Clean up monitor if main client exits
                        if not monitor_task.done():
                            monitor_task.cancel()
                            try:
                                await monitor_task
                            except asyncio.CancelledError:
                                pass
                else:
                    self.logger.error(f"Failed to establish connection for vehicle {self.vehicle_id} after timeout")
                    self.running = False
                    self.connection_event.set()  # Signal that we've given up
                
            except asyncio.CancelledError:
                self.logger.info(f"Main task cancelled for vehicle {self.vehicle_id}, shutting down...")
            except Exception as e:
                self.logger.error(f"Error in run loop for vehicle {self.vehicle_id}: {str(e)}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                self.connection_event.set()  # Signal that we've encountered an error

        self.loop = asyncio.new_event_loop()
        self.task = self.loop.create_task(_run())
        
        # Run the event loop in a separate thread
        import threading
        def run_loop():
            self.logger.info(f"Starting event loop for vehicle {self.vehicle_id}")
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_forever()
            except Exception as e:
                self.logger.error(f"Error in event loop for vehicle {self.vehicle_id}: {str(e)}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            finally:
                try:
                    # Cancel all remaining tasks
                    pending = asyncio.all_tasks(self.loop)
                    for task in pending:
                        task.cancel()
                    # Wait for all tasks to complete with a timeout
                    self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    self.loop.close()
                except Exception as e:
                    self.logger.error(f"Error during final cleanup for vehicle {self.vehicle_id}: {e}")
        
        self.event_loop_thread = threading.Thread(target=run_loop, daemon=True)
        self.event_loop_thread.start()
        self.logger.info(f"Chat client started for vehicle {self.vehicle_id}")
        
        # Block until connection is established or timeout
        # We'll use a separate event loop to wait for the connection event
        wait_loop = asyncio.new_event_loop()
        
        def wait_for_connection():
            try:
                # Wait for the connection event
                start_time = time.time()
                while True:
                    # Check if the event is set
                    if self.connection_established:
                        return True
                    
                    # Check for timeout
                    if time.time() - start_time > self.initial_connection_timeout:
                        self.logger.error(f"Timeout waiting for connection for vehicle {self.vehicle_id}")
                        return False
                    
                    # Sleep briefly
                    time.sleep(0.5)
                    
                    # Print progress every 10 seconds
                    elapsed = time.time() - start_time
                    if int(elapsed) % 10 == 0:
                        self.logger.info(f"Still waiting for connection for vehicle {self.vehicle_id} "
                                       f"({elapsed:.0f}s elapsed, {self.initial_connection_timeout - elapsed:.0f}s remaining)")
            except Exception as e:
                self.logger.error(f"Error waiting for connection: {str(e)}")
                return False
        
        # Wait for connection
        self.logger.info(f"Waiting for vehicle {self.vehicle_id} to connect (timeout: {self.initial_connection_timeout}s)")
        connected = wait_for_connection()
        
        # If we couldn't connect after timeout, stop the client
        if not connected:
            self.logger.error(f"Connection failed for vehicle {self.vehicle_id} after timeout")
            self.stop()
            return False
            
        self.logger.info(f"Vehicle {self.vehicle_id} connected successfully")
        return True

    async def _cleanup(self):
        """Internal cleanup method."""
        try:
            self.logger.debug(f"Starting cleanup for vehicle {self.vehicle_id}")
            if self.clitool:
                # Cancel all tasks
                tasks = [t for t in asyncio.all_tasks(self.loop) if t is not asyncio.current_task(self.loop)]
                for task in tasks:
                    self.logger.debug(f"Cancelling task: {task}")
                    task.cancel()
                
                # Wait for tasks to complete
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                try:
                    await self.clitool.cleanup()
                except Exception as e:
                    self.logger.warning(f"Error during CLITool cleanup: {str(e)}")
                
                # Clear the reference to CLITool
                self.clitool = None
                
            self.logger.debug(f"Cleanup completed for vehicle {self.vehicle_id}")
        except Exception as e:
            self.logger.error(f"Error during cleanup for vehicle {self.vehicle_id}: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")

    def stop(self) -> None:
        """Stop the chat client."""
        if not self.running:
            return

        self.logger.info(f"Stopping chat client for vehicle {self.vehicle_id}")
        self.running = False

        if not self.loop or not self.loop.is_running():
            return

        try:
            # Run cleanup and wait for it to complete
            future = asyncio.run_coroutine_threadsafe(self._cleanup(), self.loop)
            future.result(timeout=5)  # Wait up to 5 seconds for cleanup
            
            # Stop the event loop
            self.loop.call_soon_threadsafe(self.loop.stop)
            
            # Wait for the event loop thread to finish
            if hasattr(self, 'event_loop_thread'):
                self.event_loop_thread.join(timeout=5)
            
            # Close the loop
            if not self.loop.is_closed():
                self.loop.close()
            self.loop = None
            self.task = None
            
            self.logger.info(f"Chat client stopped for vehicle {self.vehicle_id}")
        except Exception as e:
            self.logger.error(f"Error during stop for vehicle {self.vehicle_id}: {str(e)}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            # Force cleanup if normal shutdown fails
            if self.loop and self.loop.is_running():
                self.loop.stop()
                if not self.loop.is_closed():
                    self.loop.close()
            self.loop = None
            self.task = None 

    async def receive_message(self, timeout: float = 5.0) -> Optional[dict]:
        """
        Receive a single chat message with timeout.
        
        Args:
            timeout: Maximum time to wait for a message in seconds
            
        Returns:
            dict: Message information or None if no message received
        """
        if not self.running or not self.clitool:
            self.logger.error("Not connected or not running")
            return None
            
        try:
            self.logger.debug(f"Waiting for message (timeout: {timeout}s)")
            message = await asyncio.wait_for(
                self.message_handler.message_queue.get(),
                timeout=timeout
            )
            return message
        except asyncio.TimeoutError:
            self.logger.debug("No message received within timeout")
            return None
        except Exception as e:
            self.logger.error(f"Error receiving message: {str(e)}")
            return None

    async def monitor_chat(self, callback=None):
        """
        Monitor chat continuously and optionally process messages with a callback.
        
        Args:
            callback: Optional function to call with each message
        """
        if not self.running or not self.clitool:
            self.logger.error("Not connected or not running")
            return
            
        try:
            self.logger.info(f"Starting chat monitoring for vehicle {self.vehicle_id}")
            while self.running:
                try:
                    message = await self.message_handler.message_queue.get()
                    self.logger.info(f"Message from {message['sender']}: {message['text']}")
                    
                    if callback:
                        try:
                            await callback(message)
                        except Exception as e:
                            self.logger.error(f"Error in message callback: {str(e)}")
                            
                except asyncio.CancelledError:
                    self.logger.info("Chat monitoring cancelled")
                    break
                except Exception as e:
                    self.logger.error(f"Error in monitor loop: {str(e)}")
                    await asyncio.sleep(1)  # Brief pause on error
                    
        except Exception as e:
            self.logger.error(f"Error in chat monitor: {str(e)}")
        finally:
            self.logger.info(f"Chat monitoring stopped for vehicle {self.vehicle_id}") 