import os
import data_centralisation as dc
import pandas as pd
from dotenv import load_dotenv
from logging_config import setup_logger
import telegram
import telegram.ext
import telegram.error
from time import sleep
import asyncio
import httpx
import requests
import aiofiles
import aiohttp
from aiohttp_sse_client import client as sse_client
import json

# Wait for OS to connect to internet
sleep(30)

logger = setup_logger()

logger.info('Loading environmental variables...')

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
	hour = ts[i+1:].split('.')[0].rstrip('Z')

	return (date, hour)

async def send_message_with_retry(app, chat_id, message_thread_id, text, parse_mode='HTML', max_retries=5):
	for attempt in range(max_retries):
		try:
			await app.bot.send_message(chat_id=chat_id, message_thread_id=message_thread_id, text=text, parse_mode=parse_mode)
			logger.info(f"Message sent successfully to chat_id={chat_id} on attempt {attempt + 1}.")
			return
		except (ConnectTimeout, ConnectError, NetworkError, TimedOut) as e:
			logger.warning(f"Network error on attempt {attempt + 1}/{max_retries}: {e}. Retrying...")
			await asyncio.sleep(2 ** attempt)
		except RetryAfter as e:
			retry_after = int(e.retry_after) if hasattr(e, 'retry_after') else 5
			logger.warning(f"Rate limited by Telegram. Retrying after {retry_after} seconds.")
			await asyncio.sleep(retry_after)
		except Exception as e:
			logger.error(f"Unexpected error on attempt {attempt + 1}/{max_retries}: {e}. Retrying...")
			await asyncio.sleep(2 ** attempt)
	logger.error(f"Failed to send message after {max_retries} attempts. Giving up.")


def most_recent(count=30):
	r = requests.get('https://api.pota.app/program/parks/RO')
	data = r.json()
	df = pd.DataFrame(data)

	# Get last 'count' parks
	latest_parks = df.tail(count).iloc[::-1]  # Reverse to show newest first

	message = f"<b><u>Latest {count} parks added:</u></b>\n\n"

	for index, park in latest_parks.iterrows():
		url = 'https://pota.app/#/park/' + park['reference']
		message += f"<a href='{url}'><b>[ {park['reference']} ]</b></a> - {park['name']}\n"
		message += f"   📍 {park['locationDesc']}\n\n"

	return message

# Commands

async def help_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
    if update.message.message_thread_id == TOPIC_ID:
        try:
            await update.message.reply_text(
                "<b><u>Here is a list of commands you can use:</u></b>\n\n"
                "-- /help - Provides a list of usable commands\n"
                "-- /get_bota [FILTER] - Provides a list of the future BOTA activations\n"
                "-- /get_pota [FILTER] - Provides a list of the most recent spotted POTA activators\n"
                "-- /get_sota [FILTER] - Provides a list of the most recent spotted SOTA activators\n"
				"-- /get_wwbota - Provides a list of the most recent spotted WWBOTA activators\n"
                "-- /callsign [CALLSIGN] - Provides information about the specified operator. Only works for Romanian operators!\n"
                "-- /latest - Provides the latest 30 parks added\n\n"
                "<b>/get_pota and /get_sota can be used with filters. If no filter is provided, it will default to Europe activators. Filters can be typed in lowercase or uppercase.</b>\n"
                "<b>Available filters:</b>\n"
                "-- EU - Europe\n"
                "-- RO - Romania\n"
                "-- US - United States\n"
                "-- JA - Japan",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.info("Failed to send message: " + str(e))

async def get_latest_park_command(update: telegram.Update, conext: telegram.ext.ContextTypes.DEFAULT_TYPE):
	try:
		await update.message.reply_text(most_recent(), parse_mode='HTML')
	except Exception as e:
			logger.info("Failed to send message: " + e)

async def get_BOTA_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
	if update.effective_chat.type == 'private' and str(update.message.from_user.id) not in USER_ID_LIST:
			try:
				await update.message.reply_text('Bot does not work in private chat.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

	if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
		ok, df = dc.centraliseBOTA('https://www.beachesontheair.com/activations/announcements')

		if ok == 0:
			try:
				await update.message.reply_text('An error occoured.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

		if df.empty:
			try:
				await update.message.reply_text('No activators found.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
		else:
			for index, row in df.iterrows():
				logger.info('Sending message...')
				activator = row['Activator']
				location = row['Activation'].split(' by')[0]
				date = row['UTC']

				urlActivator = 'https://www.qrz.com/db/' + activator

				try:
					await update.message.reply_text(f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> will be activating beach <b>[ {location} ]</b>\n\n"
													f"Date and time: <b>{date}</b>\n", parse_mode='HTML')
				except Exception as e:
					logger.info("Failed to send message: " + e)
				sleep(0.5)

	logger.info('All messages have been sent.')

async def get_POTA_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
	if update.effective_chat.type == 'private' and str(update.message.from_user.id) not in USER_ID_LIST:
			try:
				await update.message.reply_text('Bot does not work in private chat.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

	if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
		if context.args:
			filterPOTA = os.getenv(context.args[0].upper() + '_POTA')
			if not filterPOTA:
				try:
					await update.message.reply_text(f'Argument {context.args[0]} not recognised.')
				except Exception as e:
					logger.info("Failed to send message: " + e)
				return
			ok, df = dc.centralisePOTA(filterPOTA)
		else:
			ok, df = dc.centralisePOTA()

		if ok == 0:
			try:
				await update.message.reply_text('An error occoured.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

		if df.empty:
			try:
				await update.message.reply_text('No activators found.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
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
			try:
				await update.message.reply_text('Bot does not work in private chat.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

	if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
		if context.args:
			filterSOTA = os.getenv(context.args[0].upper() + '_SOTA')
			if not filterSOTA:
				try:
					await update.message.reply_text(f'Argument {context.args[0]} not recognised.')
				except Exception as e:
					logger.info("Failed to send message: " + e)
				return
			ok, df = dc.centraliseSOTA(filterSOTA)
		else:
			ok, df = dc.centraliseSOTA()

		if ok == 0:
			try:
				await update.message.reply_text('An error occoured.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

		if df.empty:
			try:
				await update.message.reply_text('No activators found.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
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

				try:
					await update.message.reply_text(f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> - <i>{actName}</i> is now activating summit <b>[ {summitCode} ]</b> - <i>{summitDetails}</i>\n\n"
													f"Posted at: <b>{timestamp[0]} - {timestamp[1]}</b>\n"
													f"Frequency: <b>{frequency}</b>\n"
													f"Mode: <b>{mode}</b>\n"
													f"Activator's comment: <b>{comment}</b>", parse_mode='HTML')
				except Exception as e:
					logger.info("Failed to send message: " + e)
				sleep(0.5)

		logger.info('All messages have been sent.')

async def get_WWBOTA_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
	if update.effective_chat.type == 'private' and str(update.message.from_user.id) not in USER_ID_LIST:
			try:
				await update.message.reply_text('Bot does not work in private chat.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

	if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
		ok, df = dc.centraliseWWBOTA()

		if ok == 0:
			try:
				await update.message.reply_text('An error occoured.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

		if df.empty:
			try:
				await update.message.reply_text('No activators found.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
		else:
			for index, row in df.iterrows():
				logger.info('Sending message...')
				timestamp = getTime(row['time'])
				activator = row['call']
				comment = row['comment']
				ref = row['reference']
				frequency = row['freq']
				mode = row['mode']
				urlActivator = 'https://www.qrz.com/db/' + row['call']

				try:
					await update.message.reply_text(f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating bunker <b>[ {ref} ]</b>\n\n"
													f"Posted at: <b>{timestamp[0]} - {timestamp[1]}</b>\n"
													f"Frequency: <b>{frequency}</b>\n"
													f"Mode: <b>{mode}</b>\n"
													f"Activator's comment: <b>{comment}</b>", parse_mode='HTML')
				except Exception as e:
					logger.info("Failed to send message: " + e)
				sleep(0.5)

		logger.info('All messages have been sent.')

async def callsign_info_command(update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE):
	global callbook
	if callbook is None:
		try:
			await update.message.reply_text("Callbook could not be loaded.")
		except Exception as e:
			logger.info("Failed to send message: " + e)
		return
	if update.effective_chat.type == 'private' and str(update.message.from_user.id) not in USER_ID_LIST:
			try:
				await update.message.reply_text('Bot does not work in private chat.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

	if update.message.message_thread_id == TOPIC_ID or str(update.message.from_user.id) in USER_ID_LIST:
		if not context.args:
			try:
				await update.message.reply_text('Please provide a callsign.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
			return

		if len(context.args) > 1:
			try:
				await update.message.reply_text('Too many arguments.')
			except Exception as e:
				logger.info("Failed to send message: " + e)
		else:
			callsign = context.args[0].strip().upper()
			index = callbook[callbook['INDICATIVUL'].str.strip().str.upper() == callsign].index
			if len(index) == 0:
				try:
					await update.message.reply_text('Callsign not found.')
				except Exception as e:
					logger.info("Failed to send message: " + e)
			else:
				row = callbook.loc[index[0]]
				name = row['TITULARUL']
				cls = row['CLASA']
				loc = row['LOCALITATEA']
				exp = row['DATA EXPIRARII']
				url = 'https://www.ancom.ro/radioamatori_2899'

				try:
					await update.message.reply_text(f"Showing information about operator: <b>{name} - [ {callsign} ]</b>\n"
													f"Class: <b>{cls}</b>\n"
													f"Location: <b>{loc}</b>\n"
													f"Expiration date: <b>{exp}</b>\n"
													f"Source: <a href='{url}'><b>ANCOM</b></a>", parse_mode='HTML')
				except Exception as e:
					logger.info("Failed to send message: " + e)

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

async def send_msg_WWBOTA(timestamp, activator, comment, ref, frequency, mode):
	urlActivator = 'https://www.qrz.com/db/' + activator

	message = (f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating bunker <b>[ {ref} ]</b>\n\n"
				f"Posted at: <b>{timestamp[0]} - {timestamp[1]}</b>\n"
				f"Frequency: <b>{frequency}</b>\n"
				f"Mode: <b>{mode}</b>\n"
				f"Activator's comment: <b>{comment}</b>")
	await send_message_with_retry(app, CHAT_ID, TOPIC_ID, message)
	await asyncio.sleep(0.5)

act_pota = {}
act_sota = {}
act_wwbota = {}

async def auto_spot(app):
	global act_pota
	global act_sota
	global act_wwbota
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
					act_pota[row['activator']] = (row['reference'], row['frequency'], row['comments'])
					await send_msg_POTA(row['activator'], row['frequency'], row['reference'], row['mode'], row['name'], row['locationDesc'], row['comments'])
					sent = True
					continue
				if act_pota[row['activator']][0] != row['reference']:
					act_pota[row['activator']] = (row['reference'], row['frequency'], row['comments'])
					await send_msg_POTA(row['activator'], row['frequency'], row['reference'], row['mode'], row['name'], row['locationDesc'], row['comments'])
					sent = True
					continue
				if abs(int(act_pota[row['activator']][1]) - int(row['frequency'])) >= 999:
					act_pota[row['activator']] = (row['reference'], row['frequency'], row['comments'])
					await send_msg_POTA(row['activator'], row['frequency'], row['reference'], row['mode'], row['name'], row['locationDesc'], row['comments'])
					sent = True
					continue
				if ('QRT' in row['comments'].upper() and 'QRT' not in act_pota[row['activator']][2].upper()) or \
				   ('QRV' in row['comments'].upper() and 'QRV' not in act_pota[row['activator']][2].upper()) or \
				   ('QSY' in row['comments'].upper() and 'QSY' not in act_pota[row['activator']][2].upper()):
					act_pota[row['activator']] = (row['reference'], row['frequency'], row['comments'])
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
					act_sota[row['activatorCallsign']] = (row['summitCode'], row['frequency'], row['comments'])
					await send_msg_SOTA(row['timeStamp'], row['activatorCallsign'], row['activatorName'], row['comments'], row['summitCode'], row['summitDetails'], row['frequency'], row['mode'])
					sent = True
					continue
				if act_sota[row['activatorCallsign']][0] != row['summitCode']:
					act_sota[row['activatorCallsign']] = (row['summitCode'], row['frequency'], row['comments'])
					await send_msg_SOTA(row['timeStamp'], row['activatorCallsign'], row['activatorName'], row['comments'], row['summitCode'], row['summitDetails'], row['frequency'], row['mode'])
					sent = True
					continue
				if abs(int(act_sota[row['activatorCallsign']][1]) - int(row['frequency'])) >= 999:
					act_sota[row['activatorCallsign']] = (row['summitCode'], row['frequency'], row['comments'])
					await send_msg_SOTA(row['timeStamp'], row['activatorCallsign'], row['activatorName'], row['comments'], row['summitCode'], row['summitDetails'], row['frequency'], row['mode'])
					sent = True
					continue
				if ('QRT' in row['comments'].upper() and 'QRT' not in act_sota[row['activatorCallsign']][2].upper()) or \
				   ('QRV' in row['comments'].upper() and 'QRV' not in act_sota[row['activatorCallsign']][2].upper()) or \
				   ('QSY' in row['comments'].upper() and 'QSY' not in act_sota[row['activatorCallsign']][2].upper()):
					act_sota[row['activatorCallsign']] = (row['summitCode'], row['frequency'], row['comments'])
					await send_msg_SOTA(row['timeStamp'], row['activatorCallsign'], row['activatorName'], row['comments'], row['summitCode'], row['summitDetails'], row['frequency'], row['mode'])
					sent = True
			if sent:
				logger.info("Auto spot messages sent successfully.")
	except Exception as e:
		logger.error(f"Auto spot error: {e}")

	# WWBOTA auto-spotting is now handled by SSE listener (wwbota_sse_listener)

async def wwbota_sse_listener(app):
	"""Listen to WWBOTA SSE stream for real-time spots."""
	global act_wwbota
	flt = os.getenv('AUTO_SPOT')
	if not flt:
		logger.info("AUTO_SPOT not set, WWBOTA SSE listener disabled.")
		return
	flt = flt.split()

	url = "https://api.wwbota.net/spots/"
	headers = {"Accept": "text/event-stream"}

	while True:
		try:
			logger.info("Connecting to WWBOTA SSE stream...")
			async with aiohttp.ClientSession() as session:
				async with sse_client.EventSource(url, session=session, headers=headers) as event_source:
					logger.info("Connected to WWBOTA SSE stream.")
					async for event in event_source:
						if event.data:
							try:
								spot = json.loads(event.data)
								call = spot.get('call', '')

								# Check if callsign is in AUTO_SPOT filter
								if not any(activator in call for activator in flt):
									continue

								# Extract data
								ref = spot.get('references', [{}])[0].get('reference', '') if spot.get('references') else ''
								freq = spot.get('freq', 0)
								mode = spot.get('mode', '')
								spot_type = spot.get('type', '').upper()
								comment = spot.get('comment', '')
								time_str = spot.get('time', '')

								# Parse timestamp
								if time_str and 'T' in time_str:
									timestamp = (time_str.split("T")[0], time_str.split("T")[1].split(".")[0])
								else:
									timestamp = ("", "")

								# Check if we should send notification
								should_send = False

								if call not in act_wwbota:
									act_wwbota[call] = (ref, freq, spot_type)
									should_send = True
								elif act_wwbota[call][0] != ref:
									act_wwbota[call] = (ref, freq, spot_type)
									should_send = True
								elif abs(int(act_wwbota[call][1]) - int(freq)) >= 999:
									act_wwbota[call] = (ref, freq, spot_type)
									should_send = True
								elif ('QRT' in spot_type and 'QRT' not in act_wwbota[call][2]) or \
									 ('QRV' in spot_type and 'QRV' not in act_wwbota[call][2]) or \
									 ('QSY' in spot_type and 'QSY' not in act_wwbota[call][2]):
									act_wwbota[call] = (ref, freq, spot_type)
									should_send = True

								if should_send:
									await send_msg_WWBOTA(timestamp, call, comment if comment else spot_type, ref, freq, mode)
									logger.info(f"WWBOTA SSE: Sent spot for {call}")

							except json.JSONDecodeError as e:
								logger.debug(f"SSE non-JSON data: {event.data[:100]}")
							except Exception as e:
								logger.error(f"WWBOTA SSE processing error: {e}")

		except asyncio.CancelledError:
			logger.info("WWBOTA SSE listener cancelled.")
			break
		except Exception as e:
			logger.error(f"WWBOTA SSE connection error: {e}")
			logger.info("Reconnecting to WWBOTA SSE in 10 seconds...")
			await asyncio.sleep(10)

async def scheduler(app):
	while True:
		await auto_spot(app)
		await asyncio.sleep(5)

if __name__ == '__main__':
	logger.info('Starting bot...')
	app = telegram.ext.Application.builder().token(TOKEN).build()

	# Commands
	app.add_handler(telegram.ext.CommandHandler('help', help_command))
	app.add_handler(telegram.ext.CommandHandler('latest', get_latest_park_command))
	app.add_handler(telegram.ext.CommandHandler('get_BOTA', get_BOTA_command))
	app.add_handler(telegram.ext.CommandHandler('get_POTA', get_POTA_command))
	app.add_handler(telegram.ext.CommandHandler('get_SOTA', get_SOTA_command))
	app.add_handler(telegram.ext.CommandHandler('get_WWBOTA', get_WWBOTA_command))
	app.add_handler(telegram.ext.CommandHandler('callsign', callsign_info_command))

	# Automatic spotting
	loop = asyncio.get_event_loop()
	loop.create_task(scheduler(app))
	loop.create_task(wwbota_sse_listener(app))

	# Polling
	logger.info('Polling...')
	app.run_polling(poll_interval=3)
