readonly PING_URL="https://github.com"


copy_config_from_usb () {
    local CONFIG_FILE=$1

    if [[ -z $CONFIG_FILE ]]; then
        echo "Provide file name as first positional argument."
        exit 1
    fi

    sudo mkdir /media/usb
    sudo mount /dev/sda1 /media/usb
    if [ -f "/media/usb/orange_box.config" ]; then
        cp /media/usb/orange_box.config "$CONFIG_FILE"
        tr < "$CONFIG_FILE"  -d '\000' > config.fixed && mv config.fixed "$CONFIG_FILE"
        dos2unix "$CONFIG_FILE"
    fi
    sudo umount /media/usb
}

check_internet () {
    wget -q --tries=5 --timeout=2 --spider "$PING_URL"
    local status=$?
    if [ $status -eq 0 ]; then
        echo "Internet connection is available."
    else
        echo "Internet connection unavailable."
    fi
    return $status
}

set_leds () {
    local LED_SETTING=$1

    # Show default: green led on, blue led flashing
    if [[ -z $LED_SETTING ]]; then
        exit 1
    fi

    echo $LED_SETTING > /tmp/led_state

    # Show success: green led flashing, blue led off
    if [[ $LED_SETTING -eq 3 ]]; then
        sudo sh -c "echo 0 > /sys/class/leds/rockpis\:blue\:user/brightness"
        sudo sh -c "echo heartbeat > /sys/class/leds/rockpis\:green\:power/trigger"
    # Show failure: green led off, blue led flashing
    elif [[ $LED_SETTING -eq 2 ]]; then
        sudo sh -c "echo heartbeat > /sys/class/leds/rockpis\:blue\:user/trigger"
        sudo sh -c "echo 0 > /sys/class/leds/rockpis\:green\:power/brightness"
    fi
}

connect_to_wifi () {
    local CONFIG_FILE="/home/rock/OrangeBox/config/orange_box.config"
    local DEFAULT_FILE="/home/rock/OrangeBox/config/default.config"
    local STATUS_DIR="/home/rock/OrangeBox/status/"
    local WIFI_FILE="$STATUS_DIR/wifi_connect_success.txt"

    # Perform checks.
    if [ ! -d "$STATUS_DIR" ]; then
        mkdir -p "$STATUS_DIR"
    fi
    if [ ! -f "$STATUS_DIR/experiment_number.txt" ]; then
        echo 1 > "$STATUS_DIR/experiment_number.txt"
    fi
    if [ ! -f "$CONFIG_FILE" ]; then
        cp "$DEFAULT_FILE" "$CONFIG_FILE"
    fi

    # Connect to wifi
    if [ ! -f "$WIFI_FILE" ]; then
        sleep 120
        if [ ! -f "$CONFIG_FILE" ]; then
            copy_config_from_usb "$CONFIG_FILE"
        fi
        source "$CONFIG_FILE"
        if sudo nmcli -w 180 dev wifi connect "$SSID" password "$PASS"; then
            echo success > "$WIFI_FILE"
            echo "Successfully created WIFI connection."
        else
            source "$DEFAULT_FILE"
            sudo nmcli -w 180 dev wifi connect "$SSID" password "$PASS" && \
            echo "Failed to create WIFI connection. Connected to default network instead."
        fi
    else
        sleep 30
        echo "WIFI connection was already created."
    fi

    check_internet
    if [ $? -eq 0 ]; then
        LED_SETTING=3
    else
        LED_SETTING=2
    fi

    set_leds "$LED_SETTING"
}

update_drivers () {
    check_internet
    if [ $? -eq 0 ]; then
        cd /home/rock/OrangeBox
        echo "... Pulling from main repository."
        git pull origin main
        echo "... Building."
        bash /home/rock/OrangeBox/system/build_all.sh
        echo "... Updating gitman dependencies."
        /home/rock/.local/bin/gitman install
        cd /home/rock
        if [ ! -d "/home/rock/OB_patches" ]; then
            git clone git@github.com:WatchPlant/OB_patches.git
        fi
        cd OB_patches
        git pull origin main
        bash install.sh
    else
        echo "Internet connection unavailable. Skipping update."
    fi
}

main () {
    set_leds 1

    if [ -f ~/extra_config.sh ]; then
        . ~/extra_config.sh
    fi

    # Set working directory.
    cd /home/rock/OrangeBox

    # Connect to WIFI.
    echo "Trying to connect to WiFi."
    connect_to_wifi

    # Check internet connection and update all repositories.
    echo "Updating drivers."
    # If DISABLE_UPDATE exists and is set to 1, then skip updating drivers.
    if [ -z "$DISABLE_UPDATE" ] || [ "$DISABLE_UPDATE" != "1" ]; then
        update_drivers
        echo "Updating drivers complete." 
    else
        echo "Skipping driver update."
    fi

    # Run the main tmuxinator file.
    echo "Starting tmuxinator."
    cd /home/rock/OrangeBox
    tmuxinator start -p system.yaml
    tmuxinator start -p sensors.yaml "$RUN_MODE"
    echo "Tmuxinator running."

    check_internet
    if [ $? -eq 0 ]; then
        LED_SETTING=6
    else
        LED_SETTING=5
    fi
    set_leds "$LED_SETTING"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi

