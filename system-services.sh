#!/bin/bash

# Define the services to check
SERVICES=("mavlink-router" "set-datetime" "photogram" "quspin-mag" "mavlink-mag-forwarder")

# Function to check the status of services
check_status() {
    for SERVICE in "${SERVICES[@]}"; do
        echo "========================================"
        echo "Service: $SERVICE"
        echo "----------------------------------------"

        # Check if the service is active
        STATUS=$(systemctl is-active "$SERVICE")
        echo "Status: $STATUS"

        # Check if the service is enabled
        ENABLED=$(systemctl is-enabled "$SERVICE" 2>/dev/null)
        echo "Enabled: $ENABLED"

        # Get the last 10 lines of the service's logs
        echo "Logs:"
        journalctl -u "$SERVICE" -n 10 --no-pager

        echo
    done
}

# Function to enable all services
enable_services() {
    for SERVICE in "${SERVICES[@]}"; do
        echo "Enabling service: $SERVICE"
        sudo systemctl enable "$SERVICE"
    done
}

# Function to disable all services
disable_services() {
    for SERVICE in "${SERVICES[@]}"; do
        echo "Disabling service: $SERVICE"
        sudo systemctl disable "$SERVICE"
    done
}

# Check command-line arguments
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 {status|enable|disable}"
    exit 1
fi

case "$1" in
    status)
        check_status
        ;;
    enable)
        enable_services
        ;;
    disable)
        disable_services
        ;;
    *)
        echo "Invalid option: $1"
        echo "Usage: $0 {status|enable|disable}"
        exit 1
        ;;
esac
