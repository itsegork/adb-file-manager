# ADB File Manager

GUI File Manager for Android devices using ADB (Android Debug Bridge).

## Features

- **Two-panel interface** - local computer + Android device
- **File operations**:
  - Browse files on both computer and Android
  - Send files from computer to Android
  - Download files from Android to computer
  - Delete files on both computer and Android
  - Create folders on Android
  - **Rename files and folders** on both computer and Android
  - Install APK files directly from computer or device
- **Auto-refresh** after file operations
- **Context menu** with different options for files and folders
- **Scrcpy integration** with configuration dialog (audio/video settings, screen options)
- **Device information**:
  - Battery level and status
  - Storage usage
  - Android version
  - Device model
- **ADB command line** - execute any ADB command directly from the interface
- **Log panel** with color highlighting and management options
- **Update checker** - automatically checks for new versions on GitHub

## Requirements

- Python 3.6+
- ADB (android-tools)
- tkinter (usually included with Python)
- scrcpy
- noto-fonts-emoji

## Build from GitHub (Arch Linux)
- Install dependencies
`sudo pacman -S python tk android-tools scrcpy noto-fonts-emoji`
- Clone repository:
`git clone https://github.com/itsegork/adb-file-manager.git`
- Go to directory
`cd adb-file-manager`
- Start assembling the project
`makepkg -si`