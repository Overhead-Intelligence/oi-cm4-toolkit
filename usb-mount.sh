#!/bin/bash
# usb-mount.sh
# This script is triggered by udev when a USB block device is added.

logger "usb-mount.sh: Started with argument: $1"

DEVICE="/dev/$1"
MOUNT_POINT="/media/usb"

# Check that the device has a filesystem (this might help avoid false triggers)
FS_TYPE=$(blkid -o value -s TYPE "$DEVICE")
if [ -z "$FS_TYPE" ]; then
    logger "usb-mount.sh: No filesystem detected on $DEVICE. Exiting."
    exit 1
fi
logger "usb-mount.sh: Filesystem type on $DEVICE is $FS_TYPE."

# Create the mount point if it does not exist.
if [ ! -d "$MOUNT_POINT" ]; then
    mkdir -p "$MOUNT_POINT"
    logger "usb-mount.sh: Created mount point $MOUNT_POINT."
fi

# Wait a bit to let the device settle.
sleep 2

# Use the full path to mount (sometimes needed in udev environment)
MOUNT_BIN="/bin/mount"

sudo $MOUNT_BIN -t vfat -o uid=1000,gid=1000,utf8,umask=022 "$DEVICE" "$MOUNT_POINT"

if [ $? -eq 0 ]; then
    logger "usb-mount.sh: Successfully mounted $DEVICE at $MOUNT_POINT."
else
    logger "usb-mount.sh: Failed to mount $DEVICE at $MOUNT_POINT."
fi

exit 0