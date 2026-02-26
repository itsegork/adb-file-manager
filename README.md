# ADB File Manager

GUI File Manager for Android devices using ADB (Android Debug Bridge).

## Features

- Two-panel interface (local computer + Android device)
- Browse files on both computer and Android
- Send files from computer to Android
- Download files from Android to computer
- Delete files on both computer and Android
- Create folders on Android
- Auto-refresh every 5 seconds
- Context menu with different options for files and folders
- Scrcpy integration for screen mirroring

## Requirements

- Python 3.6+
- ADB (android-tools)
- tkinter (usually included with Python)

Optional:
- scrcpy - for screen mirroring

## Build from GitHub (Arch Linux)
- Install dependencies
`sudo pacman -S python tk android-tools`
    > Optional dependencies: 
      `sudo pacman -S scrcpy`
- Clone repository:
`git clone https://github.com/itsegork/adb-file-manager.git`
- Go to directory
`cd adb-file-manager`
- Start assembling the project
`makepkg -si`
