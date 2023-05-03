CONFIG_FILE="/home/rock/OrangeBox/config/orange_box.config"
STATUS_DIR="/home/rock/OrangeBox/status/"
WIFI_FILE="$STATUS_DIR/wifi_connect_success.txt"
if [ ! -d "$STATUS_DIR" ]; then
    mkdir -p "$STATUS_DIR"
fi

if [ ! -f "$WIFI_FILE" ]; then
    sleep 120
    bash scripts/copy_usb.sh "$CONFIG_FILE"
    source "$CONFIG_FILE"
    sudo nmcli -w 180 dev wifi connect "$SSID" password "$PASS" && \
    echo success > "$WIFI_FILE" && \
    echo "Successfully created WIFI connection." && \
    bash scripts/set_leds.sh
else
    sleep 30
    echo "WIFI connection was already created."
    bash scripts/set_leds.sh
fi
