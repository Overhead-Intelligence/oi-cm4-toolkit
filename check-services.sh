#!/bin/bash

# Define the services to check
SERVICES=("set-datetime" "photogram" "mavlink-forward")

for SERVICE in "${SERVICES[@]}"; do
    echo "========================================"
    echo "Service: $SERVICE"
    echo "----------------------------------------"

    # Check if the service is active
    STATUS=$(systemctl is-active "$SERVICE")
    echo "Status: $STATUS"

    # Get the last 10 lines of the service's logs
    echo "Logs:"
    journalctl -u "$SERVICE" -n 10 --no-pager

    echo
done
