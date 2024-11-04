import csv
import os
import pathlib
import shutil
import socket
import subprocess
import threading
import sys
from time import sleep

import telebot
import yaml
import zmq


## Helpers
def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def get_hostname():
    try:
        return socket.gethostname()
    except OSError:
        return "Unknown"


def load_subscribers(input_file):
    try:
        with open(input_file, "r") as file:
            existing_ids = yaml.safe_load(file)
            if existing_ids is None:
                existing_ids = {}
    except FileNotFoundError:
        existing_ids = {}
    return existing_ids


## Bot initialization
welcome_message = """
    Welcome to the Telegram Bot!

    Here are the available commands:
    /start - Start the bot and get a welcome message.
    /meas_files - Get .zip folder of all measurements.
    /power_plot - Generate a plot based on the data.
    /subscribe - Recieve update messages from the bot.
    /unsubscribe - Unsubscribe from update messages.
    /warnings [on/off] - Enable or disable warning messages.
    /status - Get the current status of the Orange Box.
"""

subscribers_file = pathlib.Path(__file__).parent / "subscribers.txt"
new_subscribers_file = pathlib.Path(__file__).parent / "subscribers.yaml"
tokens_file = pathlib.Path(__file__).parent / "tokens.yaml"

with open(tokens_file, "r") as file:
    all_tokens = yaml.safe_load(file)
    bot_token = all_tokens[get_hostname()]

bot = telebot.TeleBot(bot_token)


## Upgrade the subscribers file from .txt to .yaml.
def upgrade_subscribers_file():
    if new_subscribers_file.exists() or not subscribers_file.exists():
        return

    with open(subscribers_file, "r") as old_file:
        subscribers = [line.strip() for line in old_file.readlines()]

    subscribers_config = {str(id): {"subscribed": True} for id in subscribers}

    with open(new_subscribers_file, "w") as new_file:
        yaml.dump(subscribers_config, new_file)

    subscribers_file.unlink()


##  Broadcast message to all subscribers.
def broadcast_message(message):
    # You can import the bot from anywhere and use it to send messages,
    # but only one bot can receive messages from users.
    # https://github.com/eternnoir/pyTelegramBotAPI/issues/1253#issuecomment-894232944
    subscribers = load_subscribers(new_subscribers_file)

    for id in subscribers:
        if not subscribers[id]["subscribed"]:
            continue
        if message.startswith("[Warning]") and not subscribers[id].get("warnings", False):
            continue
        bot.send_message(id, message)
        print(f"Broadcast sent: {message}")


## Handlers receiving messages.
@bot.message_handler(commands=["start"])
def handle_start(message):
    help_message = "Feel free to explore the bot's functionalities! If you have any questions, use the /help command."
    bot.send_message(message.chat.id, f"{welcome_message}\n\n{help_message}")


@bot.message_handler(commands=["help"])
def handle_help(message):
    bot.send_message(message.chat.id, welcome_message)


@bot.message_handler(commands=["subscribe"])
def handle_add_id(message):
    existing_ids = load_subscribers(new_subscribers_file)

    id = str(message.chat.id)
    if id in existing_ids and existing_ids[id]["subscribed"]:
        bot.reply_to(message, "Already subscribed")
        print(f"Already subscribed: {id}")
    else:
        if id not in existing_ids:
            existing_ids[id] = {"subscribed": True}
        else:
            existing_ids[id]["subscribed"] = True
        with open(new_subscribers_file, "w") as file:
            yaml.dump(existing_ids, file)
        bot.reply_to(message, "Subscribed")
        print(f"Subscribed: {id}")


@bot.message_handler(commands=["unsubscribe"])
def handle_remove_id(message):
    existing_ids = load_subscribers(new_subscribers_file)

    id = str(message.chat.id)
    if id not in existing_ids or not existing_ids[id]["subscribed"]:
        bot.reply_to(message, "Not subscribed")
        print(f"Not subscribed: {id}")
    else:
        if id in existing_ids:
            existing_ids[id]["subscribed"] = False
        else:
            existing_ids[id] = {"subscribed": False}
        with open(new_subscribers_file, "w") as file:
            yaml.dump(existing_ids, file)
        bot.reply_to(message, "Unsubscribed")
        print(f"Unsubscribed: {id}")


@bot.message_handler(commands=["warnings"])
def handle_warnings(message):
    existing_ids = load_subscribers(new_subscribers_file)

    id = str(message.chat.id)
    if id not in existing_ids or not existing_ids[id]["subscribed"]:
        bot.reply_to(message, "You are not subscribed. Warning messages are disabled by default.")
        print(f"You are not subscribed. Warning messages are disabled by default: {id}")
    else:
        if len(message.text.split()) != 2:
            bot.reply_to(message, "Please specify 'on' or 'off'.")
            return

        command = message.text.split()[1].lower()
        if command not in ["on", "off"]:
            bot.reply_to(message, "Invalid input. Please specify 'on' or 'off'.")
            return

        existing_ids[id]["warnings"] = command == "on"
        with open(new_subscribers_file, "w") as file:
            yaml.dump(existing_ids, file)
        bot.reply_to(message, f"Warning messages {command}.")
        print(f"Warning messages {command}: {id}")


@bot.message_handler(commands=["status"])
def handle_status(message):
    battery_voltage = "N/A"
    battery_current = "N/A"
    disk_usage = "N/A"

    # Network status
    ip_address = get_ip_address()
    result = subprocess.run("nmcli -t -f name connection show --active", shell=True, capture_output=True, text=True)
    ssid = result.stdout.strip()

    # Current battery level
    try:
        csv_files = sorted(pathlib.Path("/home/rock/measurements/Power").glob("*.csv"))
        with open(csv_files[-1], "r") as f:
            reader = csv.reader(f)
            last_line = None
            for row in reader:
                last_line = row

        battery_voltage = last_line[3] if last_line else "N/A"
        battery_current = last_line[4] if last_line else "N/A"
    except Exception as e:
        print(f"Error: {e}")

    # Battery status
    if float(battery_current) > 0:
        battery_status = "charging"
    elif float(battery_voltage) >= 4.0:
        battery_status = "good"
    elif float(battery_voltage) >= 3.7:
        battery_status = "ok"
    elif 3.5 < float(battery_voltage) < 3.7:
        battery_status = "low"
    elif float(battery_voltage) < 3.5:
        battery_status = "critical"
    else:
        battery_status = "N/A"

    # Disk usage
    command = "df -h / | awk '{print $5}' | grep -oP '\\d+%'"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    disk_usage = result.stdout.strip()

    response = (
        f"I am alive!\n\n"
        f"IP address: {ip_address}\n"
        f"WIFI: {ssid}\n"
        f"Battery voltage: {battery_voltage} V ({battery_status})\n"
        f"Disk usage: {disk_usage}"
    )
    bot.reply_to(message, response)


@bot.message_handler(commands=["meas_files"])
def handle_file(message):
    folder_path = "/home/rock/measurements/"
    try:
        shutil.make_archive("measurements", "zip", folder_path)
        with open("measurements.zip", "rb") as file:
            bot.send_document(message.chat.id, file)
        os.remove("measurements.zip")
    except Exception as e:
        print(f"Error: {e}")


@bot.message_handler(commands=["power_plot"])
def send_plot(message):
    # try:
    #     with open(pathlib.Path.home() / "OrangeBox/status/power_plot.png", "rb") as image:
    #         bot.send_photo(message.chat.id, image)

    # except FileNotFoundError:
    #     bot.reply_to(message, "Power Plot Currently Unavailable.")
    bot.reply_to(message, "Sorry, this feature is currently unavailable.")


def zmq_listener():
    while True:
        message = zmq_socket.recv_string()
        broadcast_message(message)


if __name__ == "__main__":
    ## ZMQ subscriber
    zmq_context = zmq.Context()
    zmq_socket = zmq_context.socket(zmq.SUB)
    zmq_socket.bind("tcp://127.0.0.1:5556")
    zmq_socket.subscribe(b"")
    zmq_socket.poll(timeout=0)

    first_pass = True
    listener_thread = threading.Thread(target=zmq_listener)
    listener_thread.daemon = True
    listener_thread.start()

    upgrade_subscribers_file()

    while True:
        sleep(1)
        try:
            print("(re)Starting bot...")
            if first_pass:
                broadcast_message(
                    f"Hello! I'm up and running :)\nMy IP address is: {get_ip_address()}"
                )
                first_pass = False
            bot.infinity_polling(skip_pending=True)
        except KeyboardInterrupt:
            listener_thread.join()
            zmq_socket.close()
            zmq_context.term()
            sys.exit()
        except Exception as e:
            print(f"Error: {e}")
