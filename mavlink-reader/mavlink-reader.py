import sys
from pymavlink import mavutil
import time
import csv
import fcntl

# Constants
UDP_IP = "127.0.0.1"
UDP_PORT = 10004

class MavLinkData:
    def __init__(self):
        self.armed = False,
        self.rangefinder_dst = 0.0,
        self.agl = 0.0,
        self.battery = 0.0,
        self.heading = 0,
        self.flight_mode = "stabilize",
        self.wind = 0,
        self.wind_speed = 0,
        self.wind_speed_z = 0
    
    def update_data(self, msg, armed=None, rangefinder_dst=None, agl=None, battery=None, heading=None, flight_mode=None, wind=None, wind_speed = None, wind_speed_z = None):
        """
        Fills data which is present at time mavlink message read.
        
        Args:
            armed: Current arm status
            rangefinder_dst: Current rangefinder distance reading in meters
            agl: Current Above Ground Level reading from terrain in meters
            battery: Current battery voltage reading in volts
            heading: Current heading in degrees
            flight_mode: Current set flight mode
            wind: Current wind direction in degrees
            wind_speed: Current wind speed horizontal
            wind_speed_z: Current wind speed vertical

        Returns:
            None
        """
        if msg and msg.get_type() == 'HEARTBEAT':
            if msg.type == 1 and msg.autopilot == 3:  # Fixed-wing, ArduPilot
                armed = (msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED) != 0
            if msg.custom_mode == 0:
                flight_mode = "stabilize"
            elif msg.custom_mode == 3:
                flight_mode = "auto"
            elif msg.custom_mode == 4:
                flight_mode = "guided"
            elif msg.custom_mode == 5:
                flight_mode = "loiter"
            elif msg.custom_mode == 11:
                flight_mode = "althold"
        elif msg and msg.get_type() == 'RANGEFINDER':
            rangefinder_dst = msg.distance  # Rangefinder in meters
        elif msg and msg.get_type() == 'TERRAIN_REPORT':
            agl = msg.current_height  # AGL Altitude in meter
        elif msg and msg.get_type() == 'BATTERY_STATUS':
            battery = (msg.voltages[0]/1000)  # Battery voltage in Volts
        elif msg and msg.get_type() == 'VFR_HUD':
            heading = msg.heading # Heading in degrees
        elif msg and msg.get_type() == 'WIND':
            wind = msg.direction  # wind
            wind_speed = msg.speed 
            wind_speed_z = msg.speed_z
             
        self.armed = armed if armed is not None else self.armed
        self.rangefinder_dst = rangefinder_dst if rangefinder_dst is not None else self.rangefinder_dst
        self.agl = agl if agl is not None else self.agl
        self.battery = battery if battery is not None else self.battery
        self.heading = heading if heading is not None else self.heading
        self.flight_mode = flight_mode if flight_mode is not None else self.flight_mode
        self.wind = wind if wind is not None else self.wind
        self.wind_speed = wind_speed if wind_speed is not None else self.wind_speed
        self.wind_speed_z = wind_speed_z if wind_speed_z is not None else self.wind_speed_z
    
    def write_to_csv(self):
        file_path = "/home/droneman/shell-scripts/mavlink-reader/mavlink-data.csv"
        data = {
            'armed': self.armed,
            'rangefinder_dst': self.rangefinder_dst,
            'agl': self.agl,
            'battery': self.battery,
            'heading': self.heading,
            'flight_mode': self.flight_mode,
            'wind': self.wind,
            'wind_speed': self.wind_speed,
            'wind_speed_z': self.wind_speed_z
        }

        with open(file_path, mode='w', newline='') as file:
            
            fcntl.flock(file, fcntl.LOCK_EX) #lock the file before we write to it
            writer = csv.DictWriter(file, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
            fcntl.flock(file,fcntl.LOCK_UN) #unlock the file

class MavLinkReader:
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
            #print(msg)
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
        Get the wind direction in degrees

        Returns:
            float: Wind direction in degrees
        """
        while True:
            msg = self.mav.recv_msg()
            if msg and msg.get_type() == 'WIND':
                return msg.direction  # Rangefinder in meters
            time.sleep(0.1)
    
    def get_wind_speed(self):
        """
        Get the wind speed.

        Returns:
            float: Windspeed horizontal in meters per second.
        """
        while True:
            msg = self.mav.recv_msg()
            if msg and msg.get_type() == 'WIND':
                return msg.speed
            time.sleep(0.1)
    
    def get_wind_speed_z(self):
        """
        Get the vertical wind speed.

        Returns:
            float: Windspeed vertical in meters per second.
        """
        while True:
            msg = self.mav.recv_msg()
            if msg and msg.get_type() == 'WIND':
                return msg.speed_z 
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
            #print(msg)
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
    
    # Create an instance of MavLinkReader
    reader = MavLinkReader()
    data = MavLinkData()

    if command != "stream":
        # Execute the specified command
        reader.execute_command(command)

    elif command == "stream":
        last_sent_time = time.time() #initialize time variable

        message_types = ['HEARTBEAT', 'TERRAIN_REPORT', 'RANGEFINDER', 'BATTERY_STATUS', 'VFR_HUD', 'WIND'] 

        while True:
            # read MAVLink messages
            msg = reader.mav.recv_match(type=message_types, blocking=True, timeout=0.1)

            if msg:
                current_time = time.time()
                
                data.update_data(msg) # Parse mavlink message and extract the data we want
                
                # Check if at least 2.5 seconds has passed since we last wrote to file
                if (current_time - last_sent_time >= 2.5):
                    data.write_to_csv()
                    last_sent_time = current_time  # Update the last write time
            else:
                time.sleep(0.05)


if __name__ == "__main__":
    main()
