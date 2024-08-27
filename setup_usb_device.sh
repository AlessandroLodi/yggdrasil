#!/bin/bash

# Log file to capture the output
LOGFILE="usb_device_setup.log"
USBIPD_PATH="C:\Program Files\usbipd-win\usbipd.exe"

# Function to log messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOGFILE
}
# Step 1: Check if WSL is running
log "Checking if WSL is running..."
wsl.exe -l -v >/dev/null 2>&1
if [ $? -ne 0 ]; then
    log "WSL is not running or installed. Exiting."
    exit 1
fi
# Step 2: Install USBIPD-WIN using winget
log "Installing USBIPD-WIN..."
powershell.exe -Command "winget install --interactive --exact dorssel.usbipd-win" >/dev/null 2>&1

# Step 3: List all USB devices connected to Windows
log "Listing USB devices connected to Windows..."
usb_devices=$(powershell.exe -Command "& '$USBIPD_PATH' list" | grep -i 'GPIB-USB-HS')

if [ -z "$usb_devices" ]; then
    log "No devices found. Please connect your USB device."
    exit 1
fi
# Extract the bus ID of the instrument GPIB-USB-HS
busid=$(echo "$usb_devices" | awk '{print $1}')
log "Bus ID for GPIB-USB-HS found: $busid"

# Step 4: Bind the USB device to make it shareable with WSL
log "Binding the USB device with busid $busid..."
powershell.exe -Command "& '$USBIPD_PATH' bind --busid $busid" >/dev/null 2>&1

# Step 5: Attach the USB device to WSL
log "Attaching USB device to WSL..."
powershell.exe -Command "& '$USBIPD_PATH' attach --wsl --busid $busid" >/dev/null 2>&1

# Step 6: Verify the USB device is attached in WSL
log "Verifying the USB device in WSL..."
device_attached=$(lsusb)
log "lsusb output:$device_attached"
# log ""

if ! echo "$device_attached" | grep -qi 'GPIB-USB-HS'; then
    log "GPIB-USB-HS device not found in WSL. Attachment may have failed."
    log "Please check Windows Device Manager and WSL USB device settings."
    exit 1
else
    log "USB device successfully attached to WSL."
fi
# Final step: Provide a message indicating completion
log "USB device setup complete. You can now interact with your device using Linux tools."

# Detach USB device when done (optional step)
log "To detach the USB device, use the following command:"
log "powershell.exe -Command '& \"C:\Program Files\usbipd-win\usbipd.exe\" detach --busid $busid'"


