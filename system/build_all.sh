# TODO: Use an actual build system like CMakeLists
CURRENT_DIR="$(pwd)"
SCRIPT_DIR="$(dirname -- "$(readlink -f "${BASH_SOURCE}")")"

echo "[BUILDING] Led driver"
cd "${SCRIPT_DIR}/led_driver/"
bash build.sh

echo "[BUILDING] Button monitor"
cd "${SCRIPT_DIR}/button_monitor/"
bash build.sh

# echo "[INSTALLING] Telegram bot"
# cd "${SCRIPT_DIR}/telegram_bot/"
# pip3 install -e .

cd "${CURRENT_DIR}"