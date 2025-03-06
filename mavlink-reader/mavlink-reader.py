import sys
from pymavlink import mavutil
import time
import csv
import fcntl
from datetime import datetime
import os

# Constants
UDP_IP = "127.0.0.1"
UDP_PORT = 10004

class MavLinkData:
    def __init__(self):
        self.armed = False
        self.rangefinder_dst = 0.0
        self.agl = 0.0
        self.battery = 0.0
        self.heading = 0.0
        self.flight_mode = "default"
        self.wind_dir = 0.0
        self.wind_speed = 0.0
        self.wind_speed_z = 0.0
        self.ground_speed = 0.0
        self.air_speed = 0.0
        self.unix_time = 0.0
        self.mavlink_log_filepath = None
    
    def update_data(self, msg, armed=None, rangefinder_dst=None, agl=None, battery=None, heading=None, flight_mode=None, wind_dir=None, wind_speed = None, wind_speed_z = None, ground_speed = None, air_speed = None, unix_time = None):
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
                    flight_mode = "manual"
                elif msg.custom_mode == 5:
                    flight_mode = "fbwa"
                elif msg.custom_mode == 6:
                    flight_mode = "fbwb"
                elif msg.custom_mode == 10:
                    flight_mode = "auto"
                elif msg.custom_mode == 11:
                    flight_mode = "rtl"
                elif msg.custom_mode == 12:
                    flight_mode = "loiter"
                elif msg.custom_mode == 15:
                    flight_mode = "guided"
                elif msg.custom_mode == 19:
                    flight_mode = "qloiter"
                elif msg.custom_mode == 21:
                    flight_mode = "qrtl"
                else:
                    flight_mode = "unknown"
    
        elif msg and msg.get_type() == 'RANGEFINDER':
            rangefinder_dst = msg.distance  # Rangefinder in meters
        elif msg and msg.get_type() == 'TERRAIN_REPORT':
            agl = msg.current_height  # AGL Altitude in meters (height above terrain)
        elif msg and msg.get_type() == 'BATTERY_STATUS':
            battery = (msg.voltages[0]/1000)  # Battery voltage in Volts
        elif msg and msg.get_type() == 'VFR_HUD':
            heading = msg.heading # Heading in degrees
            ground_speed = msg.groundspeed 
            air_speed = msg.airspeed
        elif msg and msg.get_type() == 'WIND':
            wind_dir = msg.direction  # wind_dir
            wind_speed = msg.speed 
            wind_speed_z = msg.speed_z
        elif msg and msg.get_type() == 'SYSTEM_TIME':
            unix_time = msg.time_unix_usec # unix time in microseconds
             
        self.armed = armed if armed is not None else self.armed
        self.rangefinder_dst = rangefinder_dst if rangefinder_dst is not None else self.rangefinder_dst
        self.agl = agl if agl is not None else self.agl
        self.battery = battery if battery is not None else self.battery
        self.heading = heading if heading is not None else self.heading
        self.flight_mode = flight_mode if flight_mode is not None else self.flight_mode
        self.wind_dir = wind_dir if wind_dir is not None else self.wind_dir
        self.wind_speed = wind_speed if wind_speed is not None else self.wind_speed
        self.wind_speed_z = wind_speed_z if wind_speed_z is not None else self.wind_speed_z
        self.ground_speed = ground_speed if ground_speed is not None else self.ground_speed
        self.air_speed = air_speed if air_speed is not None else self.air_speed
        self.unix_time = unix_time if unix_time is not None else self.unix_time
    
    def write_to_csv(self):
        default_file_path = "/home/droneman/shell-scripts/mavlink-reader/mavlink-data.csv"
        data = {
            'flight_mode': self.flight_mode,
            'armed': self.armed,
            'battery': self.battery,
            'rangefinder_dst': self.rangefinder_dst,
            'agl': self.agl,
            'heading': self.heading,
            'ground_speed' : self.ground_speed,
            'air_speed' : self.air_speed,
            'wind_dir': self.wind_dir,
            'wind_speed': self.wind_speed,
            #'wind_speed_z': self.wind_speed_z,
            'UTC_Date_Time': datetime.utcfromtimestamp(self.unix_time / 1e6).strftime('%Y-%m-%d %H:%M:%S')  # Convert Unix time (in microseconds) to human-readable format (UTC)
        }

        # Always write to this default filepath
        with open(default_file_path, mode='w', newline='') as file:
            fcntl.flock(file, fcntl.LOCK_EX) #lock the file before we write to it
            writer = csv.DictWriter(file, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
            fcntl.flock(file,fcntl.LOCK_UN) #unlock the file
        
        # If the user has provided a mission log file path,
        # then also append the row to that file.
        if self.mavlink_log_filepath and self.mavlink_log_filepath.strip():
            mission_file_path = os.path.join(self.mavlink_log_filepath, "mavlink-data.csv")
            def append_row(file_path, data):
                file_exists = os.path.exists(file_path)
                mode = 'a' if file_exists else 'w'
                with open(file_path, mode=mode, newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=data.keys())
                    if not file_exists:
                        writer.writeheader()
                    writer.writerow(data)

            append_row(mission_file_path, data)

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
        Get the wind_dir direction in degrees

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
        Get the wind_dir speed.

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
        Get the vertical wind_dir speed.

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
            "wind_dir" : lambda: self.get_wind(),
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
    # For user command input
    command = None
    
    # Create an instance of MavLinkReader and MavLinkData
    reader = MavLinkReader()
    data = MavLinkData()


    # Check for correct number of arguments in function call
    if len(sys.argv) > 3 or len(sys.argv) == 1:
        print("Usage: python read-mav.py {command} {mavlink_log_filepath -optional-}")
        sys.exit(1)

    # Parse command-line arguments
    if len(sys.argv) == 3:
        command = sys.argv[1].lower() #command
        data.mavlink_log_filepath = sys.argv[2] #log filepath
    elif len(sys.argv) == 2:   
        command = sys.argv[1].lower() #command
    
    
    if command != "stream":
        # Execute the specified command
        reader.execute_command(command)

    elif command == "stream":
        last_sent_time = time.time() #initialize time variable

        message_types = ['HEARTBEAT', 'TERRAIN_REPORT', 'RANGEFINDER', 'BATTERY_STATUS', 'VFR_HUD', 'WIND', 'SYSTEM_TIME'] 

        while True:
            # read MAVLink messages
            msg = reader.mav.recv_match(type=message_types, blocking=True, timeout=0.1)
            #msg = reader.mav.recv_msg()

            if msg:
                #print(msg)
                current_time = time.time()
                
                data.update_data(msg) # Parse mavlink message and extract the data we want
                
                # Check if at least 1 seconds has passed since we last wrote to file
                if (current_time - last_sent_time >= 1):
                    data.write_to_csv()
                    last_sent_time = current_time  # Update the last write time
            else:
                time.sleep(0.05)
    

if __name__ == "__main__":
    main()
