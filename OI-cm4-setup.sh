#!/bin/bash
set -euo pipefail # exit script if an error occurs
IFS=$'\n\t'

# OI CM4 Setup Script
# Script to install dependencies and configure Raspberry Pi CM4

# Usage
show_help() {
  cat << EOF
Usage: $0 [OPTIONS]

This script installs dependencies and configures the CM4 for OI products.

Options:
  photo      Install photogrammetry software
  mag        Install MAVLink→MAG forwarder
  lidar      Install LiDAR mapping software
  cot        Enable CoT broadcast service
  quspin     Install QuSpin magnetometer software
  time       Configure INS-based time synchronization
  -h, --help Show this help message and exit

Example:
  $0 photo mag time
EOF
}

# Parse command line arguments for optional installations
INSTALL_PHOTO=false
INSTALL_MAG=false
INSTALL_LIDAR=false
INSTALL_TAK=false
INSTALL_QSPIN=false
INSTALL_TIME=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) show_help; exit 0 ;;  
    photo)  INSTALL_PHOTO=true ;;  
    mag)    INSTALL_MAG=true ;;  
    lidar)  INSTALL_LIDAR=true ;;  
    cot)    INSTALL_COT=true ;;  
    quspin) INSTALL_QSPIN=true ;;  
    time)   INSTALL_TIME=true ;;  
    *)
      echo "Unknown option: $1"
      show_help
      exit 1
      ;;
  esac
  shift
done

USER_DIR="/home/droneman"
SYSTEM_SERVICES="${USER_DIR}/oi-cm4-toolkit/system-services"

echo "Starting system setup for CM4..."

# ensure timezone is UTC
sudo timedatectl set-timezone UTC

# Update the package list and upgrade existing packages
sudo apt update && sudo apt upgrade -y

CORE_PKGS=(git meson ninja-build pkg-config gcc g++ python3-pip)

echo "Installing Mavlink-Router dependencies..."
for program in "${CORE_PKGS[@]}"; do
    if ! dpkg-query -W -f='${Status}' "$program" 2>/dev/null | grep -q "install ok installed"; then
        echo "Installing $program..."
        sudo apt-get install -y $program
    else
        echo "$program is already installed. Skipping..."
    fi

    # update python3-pip
    if [[ "$program" == "python3-pip" ]]; then
        echo "Configuring python3-pip..."
        
        # python setup
        echo "Checking for Python external management removal..."
        if [ -f /usr/lib/python3.11/EXTERNALLY-MANAGED ]; then           #python 3.11 for raspian OS, 3.12 for ubuntu
            echo "Removing requirement for Python virtual environment..."
            sudo mv /usr/lib/python3.11/EXTERNALLY-MANAGED /usr/lib/python3.11/EXTERNALLY-MANAGED.old
        else
            echo "Python external management already disabled. Skipping..."
        fi

        pip3 install --upgrade pip
    fi
done

# Install mavlink interfacing dependencies
sudo pip3 install pymavlink pyserial

# make sure we are in the correct directory
cd "$USER_DIR"

# WiringPi setup
if [ -d "$USER_DIR/WiringPi" ]; then
    echo "WiringPi repository already exists."
else
    git clone https://github.com/WiringPi/WiringPi.git
    cd "$USER_DIR/WiringPi"                    # in WiringPi dir
    ./build debian

    deb_file=$(find debian-template -maxdepth 1 -type f -name "wiringpi_*_arm64.deb" | head -n 1) # Dynamically locate the generated deb file regardless of version.
    if [ -z "$deb_file" ]; then
        echo "Error: Could not find the WiringPi deb file in debian-template."
        exit 1
    fi

    mv "$deb_file" .

    deb_file_basename=$(basename "$deb_file") # Get the base name of the file (e.g. wiringpi_3.14_arm64.deb).
    sudo apt install ./"$deb_file_basename" # install it
fi

cd "$USER_DIR" 

# Photogrammetry setup
if [ "$INSTALL_PHOTO" = true ]; then
    if [ -d "$USER_DIR/photogrammetry" ]; then
        echo "Photogrammetry repository already exists. Pulling latest updates..."
        cd "$USER_DIR/photogrammetry"
        git pull
    else
        git clone git@github.com:Overhead-Intelligence/photogrammetry.git
        mkdir "$USER_DIR/photogrammetry/logs"
        sudo systemctl link /home/droneman/oi-cm4-toolkit/system-services/photogram.service
        sudo systemctl enable photogram.service
    fi
fi

cd "$USER_DIR" 

# Magnetometry setup
if [ "$INSTALL_MAG" = true ]; then
    if [ -d "$USER_DIR/mavlink-mag-forwarder" ]; then
        echo "Mavlink Mag Forwarder repository already exists. Pulling latest updates..."
        cd "$USER_DIR/mavlink-mag-forwarder"
        git pull
    else
        git clone git@github.com:Overhead-Intelligence/mavlink-mag-forwarder.git
        sudo systemctl link /home/droneman/oi-cm4-toolkit/system-services/mavlink-mag-forwarder.service
        sudo systemctl enable mavlink-mag-forwarder.service
    fi
fi

cd "$USER_DIR" 

# LiDAR setup
if [ "$INSTALL_LIDAR" = true ]; then
    if [ -d "$USER_DIR/lidar-logger" ]; then
        echo "LiDAR repository already exists. Pulling latest updates..."
        cd "$USER_DIR/lidar-logger"
        git pull
    else
        git clone git@github.com:Overhead-Intelligence/lidar-logger.git
        # sudo systemctl link /home/droneman/oi-cm4-toolkit/system-services/lidar-logger.service
        # sudo systemctl enable lidar-logger.service
    fi
fi

cd "$USER_DIR"

# PyTak client setup
if [ "$INSTALL_TAK" = true ]; then
    sudo systemctl link /home/droneman/oi-cm4-toolkit/system-services/pytak-client.service
    sudo systemctl enable pytak-client.service
fi

# QSPIN setup
if [ "$INSTALL_QSPIN" = true ]; then
    if [ -d "$USER_DIR/quspin-mag" ]; then
        echo "QuSpin MAG repository already exists. Pulling latest updates..."
        cd "$USER_DIR/quspin-mag"
        git pull
    else
        git clone git@github.com:Overhead-Intelligence/quspin-mag.git
        # sudo systemctl link /home/droneman/oi-cm4-toolkit/system-services/quspin-mag.service
        # sudo systemctl enable quspin-mag.service
    fi
fi

# Time synchronization with INS setup
if [ "$INSTALL_TIME" = true ]; then
    sudo systemctl link /home/droneman/oi-cm4-toolkit/system-services/set-datetime.service
    sudo systemctl enable set-datetime.service

    # Stop and disable systemd-timesyncd.service
    if systemctl is-enabled systemd-timesyncd.service &>/dev/null; then
        echo "Stopping and disabling systemd-timesyncd.service..."
        sudo systemctl stop systemd-timesyncd.service
        sudo systemctl disable systemd-timesyncd.service
    else
        echo "systemd-timesyncd.service is already disabled. Skipping..."
    fi
fi

# mavlink router setup
if [ -d "$USER_DIR/mavlink-router" ]; then
    echo "Mavlink-router repository already exists. Skipping..."
else
    git clone https://github.com/intel/mavlink-router.git
    cd "$USER_DIR/mavlink-router"
    git submodule update --init --recursive
    sudo meson setup build .
    sudo ninja -C build install
    sudo systemctl enable mavlink-router.service
fi

cd "$USER_DIR"

# Modify /boot/firmware/config.txt to enable UARTs and disable Bluetooth
echo "Configuring /boot/firmware/config.txt..."


# Enable additional UARTs & disable BT/Wi-Fi
cfg="/boot/firmware/config.txt"
for overlay in uart0 uart2 uart3 uart5 disable-bt disable-wifi; do
  grep -q "dtoverlay=${overlay}" "$cfg" || \
    echo "dtoverlay=${overlay}" | sudo tee -a "$cfg"
done

#mavlink router config file
if [ -d "/etc/mavlink-router" ]; then
    echo "Mavlink-router config already exists. Skipping..."
else
    sudo mkdir /etc/mavlink-router
sudo bash -c "cat > /etc/mavlink-router/main.conf <<EOF
[General]
# debug options are 'error, warning, info, debug'
DebugLogLevel = debug
TcpServerPort = 5760
[UartEndpoint flightcontroller]
# For CM4, change ttyS1 to ttyAMA2
Device = /dev/ttyAMA2
Baud = 921600
[UdpEndpoint doodle]
Mode = Server
Address = 0.0.0.0
Port = 10001
RetryTimeout = 5
[UdpEndpoint lte]
Mode = Server
Address = 0.0.0.0
Port = 10002
RetryTimeout = 5
[UdpEndpoint MAVROS]
Mode = Server
Address = 0.0.0.0
Port = 10003
RetryTimeout = 5
[UdpEndpoint MagCompForwarder]
Mode = Normal
Address = 0.0.0.0
Port = 10004
RetryTimeout = 5
[UdpEndpoint PhotoGram]
Mode = Normal
Address = 0.0.0.0
Port = 10005
RetryTimeout = 5
[UdpEndpoint MAVLinkReader]
Mode = Normal
Address = 0.0.0.0
Port = 10006
RetryTimeout = 5
[UdpEndpoint Internal7]
Mode = Normal
Address = 0.0.0.0
Port = 10007
RetryTimeout = 5
[UdpEndpoint Intenal8]
Mode = Normal
Address = 0.0.0.0
Port = 10008
RetryTimeout = 5
[UdpEndpoint Intenal9]
Mode = Normal
Address = 0.0.0.0
Port = 10009
RetryTimeout = 5
[UdpEndpoint Intenal10]
Mode = Normal
Address = 0.0.0.0
Port = 10010
RetryTimeout = 5
[UdpEndpoint External0]
Mode = Server
Address = 0.0.0.0
Port = 11000
RetryTimeout = 5
[UdpEndpoint External1]
Mode = Server
Address = 0.0.0.0
Port = 11001
RetryTimeout = 5
[UdpEndpoint External2]
Mode = Server
Address = 0.0.0.0
Port = 11002
RetryTimeout = 5
[UdpEndpoint External3]
Mode = Server
Address = 0.0.0.0
Port = 11003
RetryTimeout = 5
[UdpEndpoint External4]
Mode = Server
Address = 0.0.0.0
Port = 11004
RetryTimeout = 5
[UdpEndpoint External5]
Mode = Server
Address = 0.0.0.0
Port = 11005
RetryTimeout = 5
[UdpEndpoint External6]
Mode = Server
Address = 0.0.0.0
Port = 11006
RetryTimeout = 5
[UdpEndpoint External7]
Mode = Server
Address = 0.0.0.0
Port = 11007
RetryTimeout = 5
[UdpEndpoint External8]
Mode = Server
Address = 0.0.0.0
Port = 11008
RetryTimeout = 5
[UdpEndpoint External9]
Mode = Server
Address = 0.0.0.0
Port = 11009
RetryTimeout = 5
[UdpEndpoint External10]
Mode = Server
Address = 0.0.0.0
Port = 11010
RetryTimeout = 5
[UdpEndpoint Support]
Mode = Server
Address = 0.0.0.0
Port = 10020
RetryTimeout = 5
[UdpEndpoint Support1]
Mode = Server
Address = 0.0.0.0
Port = 10021
RetryTimeout = 5
EOF"
fi

echo "Adding droneman user to tty group"
sudo usermod -aG tty droneman

# Reboot to apply changes
echo "Setup complete. Please reboot to apply changes."
