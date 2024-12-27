import os
import data_centralisation as dc
import pandas as pd
from dotenv import load_dotenv
from logging_config import setup_logger
import telegram
import telegram.ext
from time import sleep
import asyncio
import httpx
import requests

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
if not CHAT_ID:
    raise ValueError("Chat ID not provided")

TOPIC_ID = int(os.getenv('TOPIC_ID'))
if not TOPIC_ID:
    raise ValueError("Topic ID not provided")

USER_ID_LIST = (os.getenv('USER_ID_LIST'))

logger.info('Environmental variables loaded successfully.')

# path_to_dir = os.path.dirname(os.path.abspath(__file__))

# Load callbook
logger.info('Loading callbook...')
path_to_callbook = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../res/callbook.csv')
path_to_callbook = os.path.normpath(path_to_callbook)
try:
    callbook = pd.read_csv(path_to_callbook)
except FileNotFoundError:
    logger.error(f'Could not find the file \'callbook.csv\'')
except pd.errors.EmptyDataError:
    logger.error("The file is empty.")
except pd.errors.ParserError:
    logger.error("Error: There was an issue parsing the CSV file.")
except UnicodeDecodeError:
    logger.error("Error: Could not decode the file. Try specifying a different encoding.")
except Exception as e:
    logger.error(f"An unexpected error occurred: {e}")
else:
    logger.info('Callbook successfully loaded.')
    callbook.drop(columns=['SUFIXUL', 'E-MAIL', 'DATA LIMITA A REZERVARII'], axis=1)

# Utils

def getTime(ts):
    i = ts.index('T')
    date = ts[:i]
    hour = ts[i+1:]
    return (date, hour)

async def send_message_with_retry(app, chat_id, message_thread_id, text, parse_mode='HTML', max_retries=3):
    for attempt in range(max_retries):
        try:
            await app.bot.send_message(chat_id=chat_id, message_thread_id=message_thread_id, text=text, parse_mode=parse_mode)
            return
        except httpx.ConnectTimeout as e:
            logger.error(f"Connection timeout on attempt {attempt + 1}/{max_retries}: {e}")
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}/{max_retries}: {e}")
            break
    logger.error(f"Failed to send message after {max_retries} attempts.")

def most_recent():
	r = requests.get('https://api.pota.app/program/parks/RO')
	data = r.json()
	df = pd.DataFrame(data)
	nums = []
	for index, row in df.iterrows():
		num = row['reference']
		num = num[3:]
		num = int(num)
		nums.append(num)

	park = df.iloc[-1]
	url = 'https://pota.app/#/park/' + park['reference']
    
	message = f"<b><u>Latest park:</u></b>\nReference: <a href='{url}'>[ {park['reference']} ]</a>\nName: {park['name']}\nCoordinates: {park['latitude']} {park['longitude']}\nLocationDesc: {park['locationDesc']}"
    
	return message

# Commands

async def help_command(update: telegram.Update, conext: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message.message_thread_id == TOPIC_ID:
        await update.message.reply_text("<b><u>Here is a list of commands you can use:</u></b>\n\n"
                                        "-- /help - Provides a list of usable commands\n"
                                        "-- /get_bota [FILTER]- Provides a list of the future BOTA activations\n"
                                        "-- /get_pota [FILTER]- Provides a list of the most recent spotted POTA activators\n"
                                        "-- /get_sota [FILTER]- Provides a list of the most recent spotted SOTA activators\n"
                                        "-- /callsign [CALLSIGN] - Provides information about the specified operator. Only works for Romanian operators!\n\n"
                                        "<b>/get_pota and /get_sota can be used with filters. If no filter is provided, it will default to Europe activators. Filters can be typed in lowercase or uppercase.</b>\n"
                                        "<b>Available filters:</b>\n"
                                        "-- EU - Europe\n"
                                        "-- RO - Romania\n"
                                        "-- US - United States\n"
                                        "-- JA - Japan",
                                        parse_mode='HTML')

async def get_latest_park_command(update: telegram.Update, conext: telegram.ext.ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(most_recent(), parse_mode='HTML')

async def get_BOTA_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private' and str(update.message.from_user.id) not in USER_ID_LIST:
            await update.message.reply_text('Bot does not work in private chat.')
            return
    
    if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
        ok, df = dc.centraliseBOTA('https://www.beachesontheair.com/activations/announcements')

        if ok == 0:
            await update.message.reply_text('An error occoured.')
            return
        
        if df.empty:
            await update.message.reply_text('No activators found.')
        else:
            for index, row in df.iterrows():
                logger.info('Sending message...')
                activator = row['Activator']
                location = row['Activation'].split(' by')[0]
                date = row['UTC']

                urlActivator = 'https://www.qrz.com/db/' + activator

                await update.message.reply_text(f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> will be activating beach <b>[ {location} ]</b>\n\n"
                                                f"Date and time: <b>{date}</b>\n", parse_mode='HTML')
                sleep(0.5)

    logger.info('All messages have been sent.')

async def get_POTA_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private' and str(update.message.from_user.id) not in USER_ID_LIST:
            await update.message.reply_text('Bot does not work in private chat.')
            return
    
    if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
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

                urlPark = 'https://pota.app/#/park/' + reference
                urlActivator = 'https://www.qrz.com/db/' + activator

                await update.message.reply_text(f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating park <a href='{urlPark}'><b>[ {reference} ]</b></a> - <i>{name}</i>\n\n"
                                                f"Frequency: <b>{frequency}</b>\n"
                                                f"Mode: <b>{mode}</b>\n"
                                                f"Region: <b>{locationDesc}</b>\n"
                                                f"Info: <b>{comment}</b>", parse_mode='HTML')
                sleep(0.5)

    logger.info('All messages have been sent.')

async def get_SOTA_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == 'private' and str(update.message.from_user.id) not in USER_ID_LIST:
            await update.message.reply_text('Bot does not work in private chat.')
            return
    
    if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
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

async def callsign_info_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    global callbook
    if callbook is None:
        await update.message.reply_text("Callbook could not be loaded.")
        return
    if update.effective_chat.type == 'private' and str(update.message.from_user.id) not in USER_ID_LIST:
            await update.message.reply_text('Bot does not work in private chat.')
            return
    
    if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
        if not context.args:
            await update.message.reply_text('Please provide a callsign.')
            return
        
        if len(context.args) > 1:
            await update.message.reply_text('Too many arguments.')
        else:
            callsign = context.args[0].strip().upper()
            index = callbook[callbook['INDICATIVUL'].str.strip().str.upper() == callsign].index
            if len(index) == 0:
                await update.message.reply_text('Callsign not found.')
            else:
                row = callbook.loc[index[0]]
                name = row['TITULARUL']
                cls = row['CLASA']
                loc = row['LOCALITATEA']
                exp = row['DATA EXPIRARII']
                url = 'https://www.ancom.ro/radioamatori_2899'
                await update.message.reply_text(f"Showing information about operator: <b>{name} - [ {callsign} ]</b>\n"
                                                f"Class: <b>{cls}</b>\n"
                                                f"Location: <b>{loc}</b>\n"
                                                f"Expiration date: <b>{exp}</b>\n"
                                                f"Source: <a href='{url}'><b>ANCOM</b></a>", parse_mode='HTML')

# Automatic Spotting

async def send_msg_POTA(activator, frequency, reference, mode, name, locationDesc, comment):
    urlPark = 'https://pota.app/#/park/'+ reference
    urlActivator = 'https://www.qrz.com/db/' + activator

    message = (f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating park <a href='{urlPark}'><b>[ {reference} ]</b></a> - <i>{name}</i>\n\n"
               f"Frequency: <b>{frequency}</b>\n"
               f"Mode: <b>{mode}</b>\n"
               f"Region: <b>{locationDesc}</b>\n"
               f"Info: <b>{comment}</b>")
    await send_message_with_retry(app, CHAT_ID, TOPIC_ID, message)
    await asyncio.sleep(0.5)

async def send_msg_SOTA(timeStamp, activatorCallsign, activatorName, comments, summitCode, summitDetails, frequency, mode):
    urlActivator = 'https://www.qrz.com/db/' + activatorCallsign

    message = (f"<a href='{urlActivator}'><b>[ {activatorCallsign} ]</b></a> - <i>{activatorName}</i> is now activating summit <b>[ {summitCode} ]</b> - <i>{summitDetails}</i>\n\n"
               f"Posted at: <b>{timeStamp[0]} - {timeStamp[1]}</b>\n"
               f"Frequency: <b>{frequency}</b>\n"
               f"Mode: <b>{mode}</b>\n"
               f"Activator's comment: <b>{comments}</b>")
    await send_message_with_retry(app, CHAT_ID, TOPIC_ID, message)
    await asyncio.sleep(0.5)

act_pota = {}
act_sota = {}
async def auto_spot(app):
    global act_pota
    global act_sota
    sent = False
    try:
        _, df = dc.centralisePOTA()
        flt = os.getenv('AUTO_SPOT')
        if flt:
            flt = flt.split()
            mask = df['activator'].apply(lambda x: any(activator in x for activator in flt))
            df = df[mask].reset_index(drop=True)

            for index, row in df.iterrows():
                if row['activator'] not in act_pota:
                    act_pota[row['activator']] = (row['reference'], row['frequency'])
                    await send_msg_POTA(row['activator'], row['frequency'], row['reference'], row['mode'], row['name'], row['locationDesc'], row['comments'])
                    sent = True
                    continue
                if act_pota[row['activator']][0] != row['reference']:
                    act_pota[row['activator']] = (row['reference'], row['frequency'])
                    await send_msg_POTA(row['activator'], row['frequency'], row['reference'], row['mode'], row['name'], row['locationDesc'], row['comments'])
                    sent = True
                    continue
                if abs(int(act_pota[row['activator']][1]) - int(row['frequency'])) >= 999:
                    act_pota[row['activator']] = (row['reference'], row['frequency'])
                    await send_msg_POTA(row['activator'], row['frequency'], row['reference'], row['mode'], row['name'], row['locationDesc'], row['comments'])
                    sent = True                
            if sent:
                logger.info("Auto spot messages sent successfully.")
    except Exception as e:
        logger.error(f"Auto spot error: {e}")
    
    sent = False
    try:
        _, df = dc.centraliseSOTA()
        flt = os.getenv('AUTO_SPOT')
        if flt:
            flt = flt.split()
            mask = df['activatorCallsign'].apply(lambda x: any(activator in x for activator in flt))
            df = df[mask].reset_index(drop=True)

            for index, row in df.iterrows():
                if row['activatorCallsign'] not in act_sota:
                    act_sota[row['activatorCallsign']] = (row['summitCode'], row['frequency'])
                    await send_msg_SOTA(row['timeStamp'], row['activatorCallsign'], row['activatorName'], row['comments'], row['summitCode'], row['summitDetails'], row['frequency'], row['mode'])
                    sent = True
                    continue
                if act_sota[row['activatorCallsign']][0] != row['summitCode']:
                    act_sota[row['activatorCallsign']] = (row['summitCode'], row['frequency'])
                    await send_msg_SOTA(row['timeStamp'], row['activatorCallsign'], row['activatorName'], row['comments'], row['summitCode'], row['summitDetails'], row['frequency'], row['mode'])
                    sent = True
                    continue
                if abs(int(act_pota[row['activatorCallsign']][1]) - int(row['frequency'])) >= 999:
                    act_sota[row['activatorCallsign']] = (row['summitCode'], row['frequency'])
                    await send_msg_SOTA(row['timeStamp'], row['activatorCallsign'], row['activatorName'], row['comments'], row['summitCode'], row['summitDetails'], row['frequency'], row['mode'])
                    sent = True
            if sent:
                logger.info("Auto spot messages sent successfully.")
    except Exception as e:
        logger.error(f"Auto spot error: {e}")

async def scheduler(app):
    while True:
        await auto_spot(app)
        await asyncio.sleep(60)

if __name__ == '__main__':
    logger.info('Starting bot...')
    app = telegram.ext.Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(telegram.ext.CommandHandler('help', help_command))
    app.add_handler(telegram.ext.CommandHandler('latest', get_latest_park_command))
    app.add_handler(telegram.ext.CommandHandler('get_BOTA', get_BOTA_command))
    app.add_handler(telegram.ext.CommandHandler('get_POTA', get_POTA_command))
    app.add_handler(telegram.ext.CommandHandler('get_SOTA', get_SOTA_command))
    app.add_handler(telegram.ext.CommandHandler('callsign', callsign_info_command))

    # Automatic spotting
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler(app))

    # Polling
    logger.info('Polling...')
    app.run_polling(poll_interval=3)
