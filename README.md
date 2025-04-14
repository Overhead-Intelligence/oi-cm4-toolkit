# CM4 Scripts

## Table of Contents
1. [Introduction](#introduction)
2. [Features](#features)
3. [Installation](#installation)
4. [Usage](#usage)
5. [Contact](#contact)
6. [Changelog](#changelog)

<a name="introduction"></a>
## Introduction 
This README details the current features of OI CM4 Toolkit **Version 1.3.0**

The purpose of this repository is to provide convenience scripts for debugging, setup, and management of firmware projects on the Raspberry Pi Compute Module.

<a name="installation"></a>
## Installation
Simply clone the repo to the home directory ("/home/droneman/") on the Pi.

<a name="usage"></a>
## Usage
*For development use only*

<a name="contact"></a>
## Contact
For any questions or feedback, please contact the main developer of this project:

- Name: Jean Bezerra
- Contact Email: jean@overheadintel.com

## Changelog
### Latest Version [1.3.0] - 2025-04-14

#### New Features
- Introduced `vendor-cm4-setup` script for a standard minimal installation.
- Added TAK (Team Awareness Kit) scripts for Cursor-on-Target (CoT) broadcasting.
- Developed a MAVLink reader/writer script for general CM4 firmware usage.

#### Updates and Changes
- Relocated system services from `/etc/systemd/system/` to the `system-services` folder.
- Moved `test-uart` and `cam-control` scripts to the `sensor-testing` folder.
- Enhanced the `OI-cm4-setup` script with modular installation functionality.

For a complete history of changes, refer to the [CHANGELOG.md](CHANGELOG.md) file.