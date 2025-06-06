#!/usr/bin/env python3
import argparse
import serial
import sys

def main():
    parser = argparse.ArgumentParser(
        description="Read from a UART device at a specified baud rate."
    )
    parser.add_argument("device", help="UART device (e.g. /dev/ttyAMA0 or ttyAMA5)")
    parser.add_argument("baudrate", type=int, help="Baud rate (e.g. 115200)")
    args = parser.parse_args()

    # Ensure the device string starts with /dev/
    device = args.device if args.device.startswith("/dev/") else f"/dev/{args.device}"
    baudrate = args.baudrate

    try:
        ser = serial.Serial(
            port=device,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,    # Non-blocking read
            xonxoff=False,  # Disable software flow control
            rtscts=False,   # Disable hardware (RTS/CTS) flow control
            dsrdtr=False    # Disable hardware (DSR/DTR) flow control
        )
        ser.reset_input_buffer()

    except Exception as e:
        print(f"Error opening serial port {device}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Listening on {device} at {baudrate} baud...")
    try:
        while True:
            # Read up to 1024 bytes at a time
            data = ser.readline()
            #if data and data.startswith(b'#'):
            if data:
                # Attempt to decode data as UTF-8 text; replace invalid characters
                try:
                    text = data.decode("utf-8", errors="replace")
                    print(text, end="", flush=True)
                    
                except Exception as decode_err:
                    print(f"\nError decoding data: {decode_err}")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
