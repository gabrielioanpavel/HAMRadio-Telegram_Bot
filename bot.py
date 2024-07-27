import os
import logging
import data_centralisation as dc
import pandas
from dotenv import load_dotenv
from logging_config import setup_logger
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from time import sleep

logger = setup_logger()

logger.info('Loading environmental variables...')
load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Token not provided")

BOT_USERNAME = str(os.getenv('BOT_USERNAME'))
if not BOT_USERNAME:
    raise ValueError("Bot username not provided")

TOPIC_ID = int(os.getenv('TOPIC_ID'))
if not TOPIC_ID:
    raise ValueError("Topic ID not provided")

logger.info('Environmental variables loaded successfully.')

def get_urls(ref: str, act: str):
    urlPark = 'https://pota.app/#/park/' + ref

    try:
        i = act.index('/')
    except ValueError:
        pass
    else:
        act = act[:i]
    urlActivator = 'https://www.qrz.com/db/' + act

    return urlPark, urlActivator

# Commands

async def start_command(update: Update, conext: ContextTypes.DEFAULT_TYPE):
    if update.message.message_thread_id == TOPIC_ID:
        await update.message.reply_text('Hello! This is a bot that provides information related to POTA activations.')

async def help_command(update: Update, conext: ContextTypes.DEFAULT_TYPE):
    if update.message.message_thread_id == TOPIC_ID:
        await update.message.reply_text("<b><u>Here is a list of commands you can use:</u></b>\n\n"
                                        "-- /start - Starts the bot\n"
                                        "-- /help - Provides a list of usable commands\n"
                                        "-- /get_activators - Provides a list of the most recent spotted activators",
                                        parse_mode='HTML')

async def get_activators_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.message_thread_id == TOPIC_ID:
        if update.effective_chat.type == 'private':
            await update.message.reply_text('Bot does not work in private chat.')
            return
        ok, df = dc.centralise()
        if ok == 0:
            await update.message.reply_text('An error occoured.')
            return
        if df.empty:
            await update.message.reply_text('No activators found.')
        else:
            for index, row in df.iterrows():
                logger.info('Sending message...')
                activator = row['activator']
                frequency = row['frequency']
                reference = row['reference']
                mode = row['mode']
                name = row['name']
                locationDesc = row['locationDesc']
                comment = row['comments']
                urlPark, urlActivator = get_urls(row['reference'], row['activator'])
                await update.message.reply_text(f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating park <a href='{urlPark}'><b>[ {reference} ]</b></a> - <i>{name}</i>\n\n"
                                                f"Frequency: <b>{frequency}</b>\n"
                                                f"Mode: <b>{mode}</b>\n"
                                                f"Region: <b>{locationDesc}</b>\n"
                                                f"Info: <b>{comment}</b>", parse_mode='HTML')
                sleep(0.5)
    logger.info('All messages have been sent.')

if __name__ == '__main__':
    logger.info('Starting bot...')
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('get_activators', get_activators_command))

    # Polling
    logger.info('Polling...')
    app.run_polling(poll_interval=3)
