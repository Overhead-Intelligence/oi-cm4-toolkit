import sys
from pymavlink import mavutil
import time

# Constants
UDP_IP = "127.0.0.1"
UDP_PORT = 10005


class MAVLinkReader:
    """
    A class to encapsulate MAVLink interactions and commands.
    """

    def __init__(self, ip=UDP_IP, port=UDP_PORT):
        """
        Initialize MAVLink connection.
        """
        self.mav = mavutil.mavlink_connection(f'udp:{ip}:{port}')

    def get_armed_status(self):
        """
        Check and return the armed status of the drone.

        Returns:
            bool: True if armed, False otherwise.
        """
        while True:
            msg = self.mav.recv_msg()
            print(msg)
            if msg and msg.get_type() == 'HEARTBEAT':
                if msg.type == 1 and msg.autopilot == 3:  # Fixed-wing, ArduPilot
                    return (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
            time.sleep(0.1)

    def get_agl_altitude(self):
        """
        Get the altitude above ground level (AGL).

        Returns:
            float: AGL altitude in meters, or None if unavailable.
        """
        while True:
            msg = self.mav.recv_msg()
            if msg and msg.get_type() == 'TERRAIN_REPORT':
                return msg.current_height  # AGL Altitude in meters
            time.sleep(0.1)

    def get_rangefinder_distance(self):
        """
        Get the rangefinder value.

        Returns:
            float: Rangefinder value in meters, or None if unavailable.
        """
        while True:
            msg = self.mav.recv_msg()
            if msg and msg.get_type() == 'RANGEFINDER':
                return msg.distance  # Rangefinder in meters
            time.sleep(0.1)
    
    def get_wind(self):
        """
        Get the rangefinder value.

        Returns:
            float: Rangefinder value in meters, or None if unavailable.
        """
        while True:
            msg = self.mav.recv_msg()
            if msg and msg.get_type() == 'WIND':
                return msg.direction, msg.speed, msg.speed_z  # Rangefinder in meters
            time.sleep(0.1)

    def get_battery_remaining(self):
        """
        Get the battery remaining value.

        Returns:
            float: Battery life in percentage value 0-100%.
        """
        while True:
            msg = self.mav.recv_msg()
            if msg and msg.get_type() == 'BATTERY_STATUS':
                return (msg.voltages[0]/1000)  # Rangefinder in meters
            time.sleep(0.1)

    def get_heading(self):
        """
        Get the current heading in degrees.

        Returns:
            int: Current heading in degrees.
        """
        while True:
            msg = self.mav.recv_msg()
            if msg and msg.get_type() == 'VFR_HUD':
                return msg.heading  # Rangefinder in meters
            time.sleep(0.1)

    def get_flight_mode(self):
        """
        Get the battery remaining value.

        Returns:
            float: Battery life in percentage value 0-100%.
        """
        while True:
            msg = self.mav.recv_msg()
            print(msg)
            # !! These modes may NOT be accurage, testing still needed... !!
            if msg and msg.get_type() == 'HEARTBEAT':
                if msg.custom_mode == 0:
                    return "stabilize"
                elif msg.custom_mode == 3:
                    return "auto"
                elif msg.custom_mode == 4:
                    return "guided"
                elif msg.custom_mode == 5:
                    return "loiter"
                elif msg.custom_mode == 11:
                    return "althold"

            time.sleep(0.1)        

    def execute_command(self, command):
        """
        Execute a specified command and print the result.

        Args:
            command (str): The command to execute.
        """
        # Available commands, dispatch dictionary
        commands = {
            "armed": lambda: self.get_armed_status(),
            "agl": lambda: self.get_agl_altitude(),
            "rangefinder": lambda: self.get_rangefinder_distance(),
            "wind" : lambda: self.get_wind(),
            "battery" : lambda: self.get_battery_remaining(),
            "flight_mode" : lambda: self.get_flight_mode(),
        }

        # Execute the corresponding function
        if command in commands:
            result = commands[command]() # call the function by accessing the value using key "command"
            
            # armed command returns an explicit 'true' or 'false' string
            if command == "armed":
                print("true" if result else "false")
            
            # everything else should return a float, we can handle other types as needed
            elif command in ["agl","rangefinder", "wind", "battery"]:
                if result is not None:
                    print(result)
                else:
                    print("nan")
                    sys.exit(2)

        # Catch when an unknown command is passed
        else:
            print(f"Unknown command: {command}")
            print("Supported commands: " + ", ".join(commands.keys()))
            sys.exit(1)


def main():
    """
    Main entry point for the script.
    """

    # Check for correct number of arguments in function call
    if len(sys.argv) != 2:
        print("Usage: python read-mav.py { -command- }")
        sys.exit(1)

    # Parse command-line arguments
    command = sys.argv[1].lower()

    # Create an instance of MAVLinkReader
    reader = MAVLinkReader()

    # Execute the specified command
    reader.execute_command(command)


if __name__ == "__main__":
    main()
