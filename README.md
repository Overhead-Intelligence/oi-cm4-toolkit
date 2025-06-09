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
This README details the current features of OI CM4 Toolkit **Version 1.4.0**

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
### Latest Version [1.4.0] - 2025-06-09

#### New Features
- Added pytak-client that will connect the drone to the OI Google cloud TAK server.
- Added video-server scripts for gimbal video forwarding.

#### Updates and Changes
- Changed the source git repositories in `OI-cm4-setup` from Bitbucket to GitHub.
- User can now provide a folder path as an argument to `mavlink-reader.py` to log the mavlink data stream to said file.

For a complete history of changes, refer to the [CHANGELOG.md](CHANGELOG.md) file.