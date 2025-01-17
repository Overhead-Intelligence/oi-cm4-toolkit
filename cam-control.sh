#!/bin/bash

# GPIO Pin Definitions
USB_PIN=13
SHUTTER_PIN=14
FOCUS_PIN=12
TRIGGER_PIN=10

USB_MOUNT_PATH="/media/usb/DCIM"

# Initialize gpio pin direction and values
gpio mode $SHUTTER_PIN out
gpio mode $FOCUS_PIN out
gpio mode $USB_PIN out
gpio mode $TRIGGER_PIN in

gpio write $SHUTTER_PIN 1  
gpio write $FOCUS_PIN 0

# Function to toggle the USB GPIO pin and check connection status
toggle_usb() {
    gpio toggle $USB_PIN

    sleep 0.7  # Allow time for the USB device to connect/disconnect

    if [ -d "$USB_MOUNT_PATH" ]; then
        echo "USB is connected."
    else
        echo "USB is not connected."
    fi
}

# Function to trigger the camera shutter multiple times
trigger_shutter() {
    local count=${1:-1}  # Default to 1 if no argument is provided

    for ((i = 1; i <= count; i++)); do
        echo "Triggering camera shutter ($i/$count)..."
        gpio write $FOCUS_PIN 0  # Bring focus pin low
        sleep 1
        gpio write $SHUTTER_PIN 0  # Bring shutter pin low
        sleep 1.5
        gpio write $SHUTTER_PIN 1  
        gpio write $FOCUS_PIN 1  
        sleep 1.5  # Add a delay between shots if needed
    done
}

# Function for development test mode
devtest() {
    echo "Waiting for CUBE photo trigger command..."
    while true; do
        if [[ $(gpio read $TRIGGER_PIN) -eq 0 ]]; then
            echo "GPIO $TRIGGER_PIN triggered, shuttering cam..."
            trigger_shutter 1
            # Wait for the GPIO to go HIGH before continuing to avoid multiple triggers
            while [[ $(gpio read $TRIGGER_PIN) -eq 0 ]]; do
                sleep 0.1
            done
            echo "resetting..."
        fi
        sleep 0.1  # Polling interval
    done
}

# Main logic to handle command-line arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 {usb|shutter [count]|devtest}"
    exit 1
fi

case "$1" in
    usb)
        toggle_usb
        ;;
    shutter)
        if [[ $# -eq 1 ]]; then
            # Default to 1 if no second argument is provided
            trigger_shutter 1
        elif [[ $# -eq 2 && $2 =~ ^[0-9]+$ ]]; then
            # Use the provided number if it's valid
            trigger_shutter "$2"
        else
            echo "Usage: $0 shutter [count]"
            exit 1
        fi
        ;;
    devtest)
        devtest
        ;;
    *)
        echo "Invalid option: $1"
        echo "Usage: $0 {usb|shutter [count]|devtest}"
        exit 1
        ;;
esac
