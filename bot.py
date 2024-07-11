import os
import logging
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
    await update.message.reply_text('Placeholder text for help')

#TODO: Exeution of POTA script

if __name__ == '__main__':
    logger.info('Starting bot...')
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))

    # Polling
    logger.info('Polling...')
    app.run_polling(poll_interval=3)