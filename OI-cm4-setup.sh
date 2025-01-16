#!/bin/bash

# home directory
USER_DIR="/home/droneman"

# exit script if an error occurs
set -e

# Script to install dependencies and configure Raspberry Pi CM4
echo "Starting system setup for CM4..."

# ensure timezone is UTC
sudo timedatectl set-timezone UTC

# Update the package list and upgrade existing packages
sudo apt update && sudo apt upgrade -y

# programs to install
PROGRAMS=(
    "git"
    "meson"
    "ninja-build"
    "pkg-config"
    "gcc"
    "g++"
    "systemd"
    "python3-pip"
)

echo "Installing Mavlink-Router dependencies..."
for program in "${PROGRAMS[@]}"; do
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
        if [ -f /usr/lib/python3.11/EXTERNALLY-MANAGED.old ]; then
            echo "Python external management already disabled. Skipping..."
        else
            echo "Removing requirement for Python virtual environment..."
            sudo mv /usr/lib/python3.11/EXTERNALLY-MANAGED /usr/lib/python3.11/EXTERNALLY-MANAGED.old
        fi

        pip3 install --upgrade pip
    fi
done


# make sure we are in the correct directory
cd "$USER_DIR"

# WiringPi setup
if [ -d "$USER_DIR/WiringPi" ]; then
    echo "WiringPi repository already exists."
else
    git clone https://github.com/WiringPi/WiringPi.git
    cd "$USER_DIR/WiringPi"                    # in WiringPi dir
    ./build debian
    mv debian-template/wiringpi_3.10_arm64.deb .
    sudo apt install ./wiringpi_3.10_arm64.deb # install it
fi

cd "$USER_DIR" 

# Photogrammetry setup
if [ -d "$USER_DIR/photogrammetry" ]; then
    echo "Photogrammetry repository already exists. Pulling latest updates..."
    cd "$USER_DIR/photogrammetry"
    git pull
else
    git clone git@bitbucket.org:overhead-intelligence/photogrammetry.git
    mkdir "$USER_DIR/photogrammetry/logs"
fi

cd "$USER_DIR" 

# Magnetometry setup
if [ -d "$USER_DIR/mavlink-mag-forwarder" ]; then
    echo "Mavlink Mag Forwarder repository already exists. Pulling latest updates..."
    cd "$USER_DIR/mavlink-mag-forwarder"
    git pull
else
    git clone git@bitbucket.org:overhead-intelligence/mavlink-mag-forwarder.git
fi

cd "$USER_DIR" 

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

# Install mavlink forwarder dependencies
sudo pip3 install pymavlink pyserial

# create system services
if systemctl list-unit-files | grep -q "set-datetime.service"; then
    echo "set-datetime.service already exists. Ensuring it is enabled..."
    sudo systemctl enable set-datetime.service
else
    echo "Creating set-datetime.service..."
    sudo tee /etc/systemd/system/set-datetime.service > /dev/null <<EOL
[Unit]
Description=Set System Time from GPS Data
After=network.target

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 15
ExecStart=/usr/bin/python3 /home/droneman/shell-scripts/set-time.py
RemainAfterExit=false
Restart=no
User=root

[Install]
WantedBy=multi-user.target
EOL
    sudo systemctl enable set-datetime.service
fi

if systemctl list-unit-files | grep -q "photogram.service"; then
    echo "photogram.service already exists. Ensuring it is enabled..."
    sudo systemctl enable photogram.service
else
    echo "Creating photogram.service..."
    sudo tee /etc/systemd/system/photogram.service > /dev/null <<EOL
[Unit]
Description=Photogrammetry Auto-Start Service
After=set-datetime.service

[Service]
Type=oneshot
User=root
ExecStartPre=/bin/sleep 45
ExecStart=/home/droneman/photogrammetry/build/main

[Install]
WantedBy=multi-user.target
EOL
    sudo systemctl enable photogram.service
fi

if systemctl list-unit-files | grep -q "mavlink-forward.service"; then
    echo "mavlink-forward.service already exists. Ensuring it is enabled..."
    sudo systemctl enable mavlink-forward.service
else
    echo "Creating mavlink-forward.service..."
    sudo tee /etc/systemd/system/mavlink-forward.service > /dev/null <<EOL
[Unit]
Description=Auto-Start Mavlink to MagComp data stream
After=photogram.service

[Service]
User=droneman
Type=simple
ExecStartPre=/bin/sleep 15
ExecStart=/usr/bin/python3 /home/droneman/mavlink-mag-forwarder/mavlink-forward.py

[Install]
WantedBy=multi-user.target
EOL
    sudo systemctl disable mavlink-forward.service
fi

# Stop and disable systemd-timesyncd.service
if systemctl is-enabled systemd-timesyncd.service &>/dev/null; then
    echo "Stopping and disabling systemd-timesyncd.service..."
    sudo systemctl stop systemd-timesyncd.service
    sudo systemctl disable systemd-timesyncd.service
else
    echo "systemd-timesyncd.service is already disabled. Skipping..."
fi

# Modify /boot/firmware/config.txt to enable UARTs and disable Bluetooth
echo "Configuring /boot/firmware/config.txt..."

# Check if the lines already exist before adding them
CONFIG_FILE="/boot/firmware/config.txt"
if ! grep -q "dtoverlay=uart0" "$CONFIG_FILE"; then
    echo "dtoverlay=uart0" | sudo tee -a $CONFIG_FILE
    echo "dtoverlay=uart2" | sudo tee -a $CONFIG_FILE
    echo "dtoverlay=uart3" | sudo tee -a $CONFIG_FILE
    echo "dtoverlay=uart5" | sudo tee -a $CONFIG_FILE
    echo "dtoverlay=disable-bt" | sudo tee -a $CONFIG_FILE
else
    echo "UART and Bluetooth configurations already present in $CONFIG_FILE"
fi

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
Baud = 115200
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
[UdpEndpoint Rockblock]
Mode = Normal
Address = 0.0.0.0
Port = 10003
RetryTimeout = 5
[UdpEndpoint MagComp]
Mode = Normal
Address = 0.0.0.0
Port = 10004
RetryTimeout = 5
[UdpEndpoint PhotoGram]
Mode = Normal
Address = 0.0.0.0
Port = 10005
RetryTimeout = 5
[UdpEndpoint Internal6]
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
echo "Setup complete. Please reboot to apply changes..."
#sudo reboot
