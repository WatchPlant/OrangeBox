import os
import pathlib
import shutil
import socket
import sys
from time import sleep

import telebot
import yaml

subscribers_file = pathlib.Path(__file__).parent / "subscribers.txt"
tokens_file = pathlib.Path(__file__).parent / "tokens.yaml"

with open(tokens_file, "r") as file:
    all_tokens = yaml.safe_load(file)
    bot_token = all_tokens[socket.gethostname()]

bot = telebot.TeleBot(bot_token)

# You can import the bot from anywhere and use it to send messages,
# but only one bot can receive messages from users.
# https://github.com/eternnoir/pyTelegramBotAPI/issues/1253#issuecomment-894232944
def broadcast_message(message):
    try:
        with open(subscribers_file, "r") as file:
            subscribers = [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        subscribers = []

    for id in subscribers:
        bot.send_message(id, message)
        print(f"Broadcast sent: {message}")

welcome_message = """
    Welcome to the Telegram Bot!

    Here are the available commands:
    /start - Start the bot and get a welcome message.
    /meas_files - Get .zip folder of all measurements.
    /power_plot - Generate a plot based on the data.
    /subscribe - Recieve update messages from the bot.
    /unsubscribe - Unsubscribe from update messages.
"""

# Handlers receiving messages.
@bot.message_handler(commands=["start"])
def handle_start(message):
    help_message = "Feel free to explore the bot's functionalities! If you have any questions, use the /help command."
    bot.send_message(message.chat.id, f"{welcome_message}\n\n{help_message}")


@bot.message_handler(commands=["help"])
def handle_help(message):
    bot.send_message(message.chat.id, welcome_message)


@bot.message_handler(commands=["subscribe"])
def handle_add_id(message):
    try:
        with open(subscribers_file, "r") as file:
            existing_ids = [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        existing_ids = []

    with open(subscribers_file, "a") as file:
        id = message.chat.id
        if str(id) not in existing_ids:
            file.write(str(id) + "\n")
            bot.reply_to(message, "Subscribed")
            print(f"New subscriber: {id}")
        else:
            bot.reply_to(message, "Already subscribed")
            print(f"Already subscribed: {id}")


@bot.message_handler(commands=["unsubscribe"])
def handle_remove_id(message):
    try:
        with open(subscribers_file, "r") as file:
            existing_ids = [line.strip() for line in file.readlines()]
    except FileNotFoundError:
        existing_ids = []

    if str(message.chat.id) in existing_ids:
        existing_ids.remove(str(message.chat.id))
        with open(subscribers_file, "w") as file:
            file.writelines(existing_ids)
        bot.reply_to(message, "Unsubscribed")
        print(f"Unsubscribed: {message.chat.id}")
    else:
        bot.reply_to(message, "Not subscribed")
        print(f"Not subscribed: {message.chat.id}")


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


if __name__ == "__main__":
    first_pass = True
    while True:
        sleep(1)
        try:
            print("(re)Starting bot...")
            if first_pass:
                broadcast_message("Hello! I'm up and running :)")
                first_pass = False
            bot.polling(non_stop=True)
        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            print(f"Error: {e}")
