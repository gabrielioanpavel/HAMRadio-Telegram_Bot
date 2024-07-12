import os
import logging
import data_centralisation as dc
import pandas
from dotenv import load_dotenv
from logging_config import setup_logger
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logger = setup_logger()
load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Token not provided")
BOT_USERNAME = '@infoPOTA_bot'

# Commands

async def start_command(update: Update, conext: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hello! This is a bot that provides information related to POTA activations.')

async def help_command(update: Update, conext: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("<b><u>Here is a list of commands you can use:</u></b>\n\n"
                                    "-- /start - Starts the bot\n"
                                    "-- /help - Provides a list of usable commands\n"
                                    "-- /get_activators - Provides a list of the most recent spotted activators",
                                    parse_mode='HTML')

async def get_activators_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok, df = dc.centralise()
    if ok == 0:
        await update.message.reply_text('An error occoured.')
        return
    if df.empty:
        await update.message.reply_text('No activators found.')
    else:
        for index, row in df.iterrows():
            activator = row['activator']
            frequency = row['frequency']
            reference = row['reference']
            mode = row['mode']
            name = row['name']
            locationDesc = row['locationDesc']
            await update.message.reply_text(f"<b>[ {activator} ]</b> is now activating park <b>[ {reference} ]</b> - <i>{name}</i>\n\n"
                                            f"Frequency: <b>{frequency}</b>\n"
                                            f"Mode: <b>{mode}</b>\n"
                                            f"Region: <b>{locationDesc}</b>", parse_mode='HTML')
            #TODO: Add hyperlinks for {activator} and {reference}

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