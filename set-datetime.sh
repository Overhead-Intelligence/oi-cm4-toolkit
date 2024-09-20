#!/bin/bash

SECONDS_IN_DAY=86400
SECONDS_IN_WEEK=604800
UART_DEVICE="/dev/ttyAMA0"
BAUD_RATE=921600

# Set up UART device
stty -F $UART_DEVICE raw $BAUD_RATE cs8 clocal -cstopb

# Function to format GPS time and update the system date
formatGPStime() {
    local GPSweek=$1
    local timeOfWeek=$2

    # Start time is January 6, 1980
    base_date="1980-01-06"

    # Convert weeks to days
    daysSince1980=$(awk "BEGIN {print int($GPSweek * 7 + $timeOfWeek / $SECONDS_IN_DAY)}")

    # Get the full date by adding days to the base date
    formatted_date=$(date -d "$base_date + $daysSince1980 days" +"%Y-%m-%d")

    # Get current time (hour, min, sec)
    currentDaySeconds=$(awk "BEGIN {print int($timeOfWeek % $SECONDS_IN_DAY)}")
    hours=$(awk "BEGIN {print int($currentDaySeconds / 3600)}")
    minutes=$(awk "BEGIN {print int(($currentDaySeconds % 3600) / 60)}")
    seconds=$(awk "BEGIN {print int($currentDaySeconds % 60)}")

    # Extract the year from the formatted date
    year=$(date -d "$base_date + $daysSince1980 days" +"%Y")

    # Print the final formatted date and time
    echo "Formatted Date: $formatted_date"
    echo "Time: $(printf "%02d:%02d:%02d" "$hours" "$minutes" "$seconds")"

    # If the year is 2024 or later, update the system time
    if [ "$year" -ge 2024 ]; then
        echo "Valid GPS time detected. Setting system time to: $formatted_date $(printf "%02d:%02d:%02d" "$hours" "$minutes" "$seconds")"
        
        # Set the system date and time using the `date` command
        sudo date -s "$formatted_date $(printf "%02d:%02d:%02d" "$hours" "$minutes" "$seconds")"
        
        # Exit the script after setting the time
        exit 0
    else
        echo "Invalid GPS time detected. Possible no-fix"
    fi
}

# Function to validate GPSweek and timeOfWeek
validate_gps_time() {
    local GPSweek=$1
    local timeOfWeek=$2

    # Check if GPSweek and timeOfWeek are numeric
    if ! [[ "$GPSweek" =~ ^[0-9]+$ ]] || ! [[ "$timeOfWeek" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        echo "Invalid GPS data: non-numeric values detected."
        return 1
    fi

    # Check if GPSweek is within a reasonable range (since Jan 6, 1980)
    if [ "$GPSweek" -lt 0 ] || [ "$GPSweek" -gt 5000 ]; then
        echo "Invalid GPSweek value: $GPSweek. Skipping."
        return 1
    fi

    # Check if timeOfWeek is within the valid range (0 to 604800 seconds)
    if awk "BEGIN {exit !($timeOfWeek >= 0 && $timeOfWeek < $SECONDS_IN_WEEK)}"; then
        return 0  # Valid GPS data
    else
        echo "Invalid timeOfWeek value: $timeOfWeek. Skipping."
        return 1
    fi
}

# Read data from UART device using `cat`
cat $UART_DEVICE | while read -r line; do
    
    #wait a little before the next read
    sleep 5

    # Check if the line starts with "$PINS1"
    if [[ "$line" =~ ^\$PINS1 ]]; then
        echo "Raw Line: $line"  # Print the full line for debugging

        # Tokenize the line and extract necessary fields
        IFS=',' read -r -a tokens <<< "$line"

        # Check if we have at least the expected number of tokens (e.g., 3 or more)
        if [ ${#tokens[@]} -ge 3 ]; then
            timeOfWeek=${tokens[1]}  # 2nd token is timeOfWeek
            GPSweek=${tokens[2]}     # 3rd token is GPSweek
            #echo "GPSweek: $GPSweek"
            #echo "timeOfWeek: $timeOfWeek"

            # Validate GPSweek and timeOfWeek
            if validate_gps_time "$GPSweek" "$timeOfWeek"; then
                # Format the GPS time and attempt to set the system time
                formatGPStime "$GPSweek" "$timeOfWeek"
            else
                echo "Skipping invalid GPS time."
            fi
        else
            echo "Incomplete line received, skipping."
        fi
    fi
done
