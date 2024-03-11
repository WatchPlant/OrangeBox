#!/bin/bash
source /home/rock/OrangeBox/scripts/startup.sh


# Define your wireless interface
INTERFACE="p2p0"

if [[ $(ip link show "$INTERFACE" | grep "state UP") ]]; then
    # Check if the wireless interface is associated with an access point
    if [[ $(iw dev "$INTERFACE" link | grep "Connected") ]]; then
        check_internet
        if [ $? -eq 0 ]; then
            set_leds 6
        else
            set_leds 5
        fi
    else
        echo "Wireless interface is up but not connected to any Wi-Fi network"
        set_leds 4
    fi
else
    echo "Wireless interface is not up"
    set_leds 4
fi
