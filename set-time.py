import serial
import time
from datetime import datetime, timedelta
import subprocess

# Constants
SECONDS_IN_DAY = 86400
SECONDS_IN_WEEK = 604800
UART_DEVICE = "/dev/ttyAMA0"
BAUD_RATE = 921600

# Function to validate GPS time
def validate_gps_time(gps_week, time_of_week):
    try:
        gps_week = int(gps_week)
        time_of_week = float(time_of_week)
    except ValueError:
        print("Invalid GPS data: non-numeric values detected.")
        return False

    if gps_week < 0 or gps_week > 5000:
        print(f"Invalid GPSweek value: {gps_week}. Skipping.")
        return False

    if 0 <= time_of_week < SECONDS_IN_WEEK:
        return True
    else:
        print(f"Invalid timeOfWeek value: {time_of_week}. Skipping.")
        return False

# Function to get datetime from GPS week and time of week
def get_datetime_from_gps(gps_week: int, time_of_week: float) -> datetime:
    """Converts GPS week and time of week to a datetime object.

    Args:
        gps_week (int): The GPS week number.
        time_of_week (float): The time of the week in seconds.

    Returns:
        datetime: A datetime object representing the corresponding date and time.
    """
    return datetime(1980, 1, 6, 0, 0, 0) + timedelta(weeks=gps_week, seconds=time_of_week)

# Function to format GPS time and update the system date
def format_gps_time(gps_week, time_of_week):
    formatted_datetime = get_datetime_from_gps(gps_week, time_of_week)

    print(f"Formatted Date: {formatted_datetime.strftime('%Y-%m-%d')}")
    print(f"Time: {formatted_datetime.strftime('%H:%M:%S')}")

    if formatted_datetime.year >= 2024:
        print(f"Valid GPS time detected. Setting system time to: {formatted_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        subprocess.run(["sudo", "date", "-s", formatted_datetime.strftime('%Y-%m-%d %H:%M:%S')])
        exit(0)
    else:
        print("Invalid GPS time detected. Possible no-fix.")

# Read data from the UART device
def read_from_uart():
    while(True):
        with serial.Serial(UART_DEVICE, BAUD_RATE, timeout=1) as ser:
            line = ser.readline().decode('utf-8').strip()

            if line.startswith("$PINS1"):
                print(f"Raw Line: {line}")
                tokens = line.split(',')

                if len(tokens) >= 3:
                    time_of_week = tokens[1]
                    gps_week = tokens[2]

                    if validate_gps_time(gps_week, time_of_week):
                        format_gps_time(int(gps_week), float(time_of_week))
                    else:
                        print("Skipping invalid GPS time.")
                else:
                    print("Incomplete line received, skipping.")
            
            time.sleep(5)  # Wait before the next read

if __name__ == "__main__":
    read_from_uart()
