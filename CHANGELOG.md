# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Version [1.4.0] - 2025-06-09

### New Features
- Added pytak-client that will connect the drone to the OI Google cloud TAK server.
- Added video-server scripts for gimbal video forwarding.

### Updates and Changes
- Changed the source git repositories in `OI-cm4-setup` from Bitbucket to GitHub.
- User can now provide a folder path as an argument to `mavlink-reader.py` to log the mavlink data stream to said file.

## Version [1.3.0] - 2025-04-14

### New
- Added vendor-cm4-setup script with standard minimal installation.
- Added TAK (team-awareness-kit) based scripts for cursor-on-target (CoT) broadcasting.
- Added MAVLink reader/writer script for use in gerenal CM4 firmware.

### Changed
- Moved system services from /etc/systemd/system/ to system-services folder.
- Moved test-uart and cam-control scripts to sensor-testing folder.
- Standardized OI-cm4-setup script, added modular install functionality. 

## Version [1.2.0] - 2025-01-20

### Changed
- Renamed "toggle-cam-usb" to "cam-control"
- Added camera triggering functionality to cam-control.sh
- Renamed "check-services" to "system-services"
- Added ability to enable or disable services to system-services.sh

## Version [1.1.0]

### Changed
- Modified set-datetime.sh script to work as a python script.
- Changed serial read to be "line-by-line" to prevent data being heald up in buffer.

