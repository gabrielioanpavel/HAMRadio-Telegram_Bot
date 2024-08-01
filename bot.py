import os
import logging
import data_centralisation as dc
import pandas
from dotenv import load_dotenv
from logging_config import setup_logger
import telegram
import telegram.ext
from time import sleep
import asyncio

logger = setup_logger()

logger.info('Loading environmental variables...')
load_dotenv()

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Token not provided")

BOT_USERNAME = str(os.getenv('BOT_USERNAME'))
if not BOT_USERNAME:
    raise ValueError("Bot username not provided")

CHAT_ID = int(os.getenv('CHAT_ID'))

TOPIC_ID = int(os.getenv('TOPIC_ID'))
if not TOPIC_ID:
    raise ValueError("Topic ID not provided")

logger.info('Environmental variables loaded successfully.')

def getTime(ts):
    i = ts.index('T')
    date = ts[:i]
    hour = ts[i+1:]
    return (date, hour)

# Commands

async def start_command(update: telegram.Update, conext: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message.message_thread_id == TOPIC_ID:
        await update.message.reply_text('Hello! This is a bot that provides information related to POTA activations.')

async def help_command(update: telegram.Update, conext: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message.message_thread_id == TOPIC_ID:
        await update.message.reply_text("<b><u>Here is a list of commands you can use:</u></b>\n\n"
                                        "-- /start - Starts the bot\n"
                                        "-- /help - Provides a list of usable commands\n"
                                        "-- /get_pota - Provides a list of the most recent spotted POTA activators\n"
                                        "-- /get_sota - Provides a list of the most recent spotted SOTA activators\n\n"
                                        "<b>/get_pota and /get_sota can be used with filters. If no filter is provided, it will default to Europe activators. Filters can be typed in lowercase or uppercase.</b>\n"
                                        "<b>Available filters:</b>\n"
                                        "-- EU - Europe\n"
                                        "-- RO - Romania",
                                        parse_mode='HTML')

async def get_POTA_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
            await update.message.reply_text('Bot does not work in private chat.')
            return
    
    if update.message.message_thread_id == TOPIC_ID:
        if context.args:
            filterPOTA = os.getenv(context.args[0].upper() + '_POTA')
            if not filterPOTA:
                await update.message.reply_text(f'Argument {context.args[0]} not recognised.')
                return
            ok, df = dc.centralisePOTA(filterPOTA)
        else:
            ok, df = dc.centralisePOTA()

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

                urlPark = 'https://pota.app/#/park/'+ reference
                urlActivator = 'https://www.qrz.com/db/' + activator

                await update.message.reply_text(f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating park <a href='{urlPark}'><b>[ {reference} ]</b></a> - <i>{name}</i>\n\n"
                                                f"Frequency: <b>{frequency}</b>\n"
                                                f"Mode: <b>{mode}</b>\n"
                                                f"Region: <b>{locationDesc}</b>\n"
                                                f"Info: <b>{comment}</b>", parse_mode='HTML')
                sleep(0.5)

    logger.info('All messages have been sent.')

async def get_SOTA_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private':
            await update.message.reply_text('Bot does not work in private chat.')
            return
    
    if update.message.message_thread_id == TOPIC_ID:
        if context.args:
            filterSOTA = os.getenv(context.args[0].upper() + '_SOTA')
            if not filterSOTA:
                await update.message.reply_text(f'Argument {context.args[0]} not recognised.')
                return
            ok, df = dc.centraliseSOTA(filterSOTA)
        else:
            ok, df = dc.centraliseSOTA()

        if ok == 0:
            await update.message.reply_text('An error occoured.')
            return
        
        if df.empty:
            await update.message.reply_text('No activators found.')
        else:
            for index, row in df.iterrows():
                logger.info('Sending message...')
                timestamp = getTime(row['timeStamp'])
                activator = row['activatorCallsign']
                actName = row['activatorName']
                comment = row['comments']
                summitCode = row['summitCode']
                summitDetails = row['summitDetails']
                frequency = row['frequency']
                mode = row['mode']
                urlActivator = 'https://www.qrz.com/db/' + row['activatorCallsign']
                await update.message.reply_text(f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> - <i>{actName}</i> is now activating summit <b>[ {summitCode} ]</b> - <i>{summitDetails}</i>\n\n"
                                                f"Posted at: <b>{timestamp[0]} - {timestamp[1]}</b>\n"
                                                f"Frequency: <b>{frequency}</b>\n"
                                                f"Mode: <b>{mode}</b>\n"
                                                f"Activator's comment: <b>{comment}</b>", parse_mode='HTML')
                sleep(0.5)

        logger.info('All messages have been sent.')

async def auto_spot(app):
    _, df = dc.centralisePOTA()
    flt = os.getenv('AUTO_SPOT')
    if flt:
        flt = flt.split()
        mask = df['activator'].apply(lambda x: any(x.startswith(act) for act in flt))
        df = df[mask].reset_index(drop=True)
        for index, row in df.iterrows():
            activator = row['activator']
            frequency = row['frequency']
            reference = row['reference']
            mode = row['mode']
            name = row['name']
            locationDesc = row['locationDesc']
            comment = row['comments']

            urlPark = 'https://pota.app/#/park/'+ reference
            urlActivator = 'https://www.qrz.com/db/' + activator

            message = (f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating park <a href='{urlPark}'><b>[ {reference} ]</b></a> - <i>{name}</i>\n\n"
                       f"Frequency: <b>{frequency}</b>\n"
                       f"Mode: <b>{mode}</b>\n"
                       f"Region: <b>{locationDesc}</b>\n"
                       f"Info: <b>{comment}</b>")
            await app.bot.send_message(chat_id=CHAT_ID, text=message, message_thread_id=TOPIC_ID, parse_mode='HTML')

async def scheduler(app):
    while True:
        await auto_spot(app)
        await asyncio.sleep(300)

if __name__ == '__main__':
    logger.info('Starting bot...')
    app = telegram.ext.Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(telegram.ext.CommandHandler('start', start_command))
    app.add_handler(telegram.ext.CommandHandler('help', help_command))
    app.add_handler(telegram.ext.CommandHandler('get_POTA', get_POTA_command))
    app.add_handler(telegram.ext.CommandHandler('get_SOTA', get_SOTA_command))

    # Automatic spotting
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler(app))

    # Polling
    logger.info('Polling...')
    app.run_polling(poll_interval=3)
