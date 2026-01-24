import asyncio
import json
import os
from time import sleep

import aiohttp
import pandas as pd
import requests
import telegram
import telegram.ext
from aiohttp_sse_client import client as sse_client
from httpx import ConnectError, ConnectTimeout
from telegram.error import NetworkError, RetryAfter, TimedOut

import data_centralisation as dc
from logging_config import setup_logger

# Wait for OS to connect to internet
sleep(30)

logger = setup_logger()

logger.info("Loading environmental variables...")

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Token not provided")

_bot_username = os.getenv("BOT_USERNAME")
if not _bot_username:
    raise ValueError("Bot username not provided")
BOT_USERNAME = str(_bot_username)

_chat_id = os.getenv("CHAT_ID")
if not _chat_id:
    raise ValueError("Chat ID not provided")
CHAT_ID = int(_chat_id)

_topic_id = os.getenv("TOPIC_ID")
if not _topic_id:
    raise ValueError("Topic ID not provided")
TOPIC_ID = int(_topic_id)

USER_ID_LIST = os.getenv("USER_ID_LIST")
if not USER_ID_LIST:
    logger.warning("USER_ID_LIST not provided. Private chats may fail.")
    USER_ID_LIST = ""

logger.info("Environmental variables loaded successfully.")

# path_to_dir = os.path.dirname(os.path.abspath(__file__))

# Load callbook
logger.info("Loading callbook...")
path_to_callbook = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../res/callbook.csv"
)
path_to_callbook = os.path.normpath(path_to_callbook)
try:
    callbook = pd.read_csv(path_to_callbook)
except FileNotFoundError:
    logger.error("Could not find the file 'callbook.csv'")
except pd.errors.EmptyDataError:
    logger.error("The file is empty.")
except pd.errors.ParserError:
    logger.error("Error: There was an issue parsing the CSV file.")
except UnicodeDecodeError:
    logger.error(
        "Error: Could not decode the file. Try specifying a different encoding."
    )
except Exception as e:
    logger.error(f"An unexpected error occurred: {e}")
else:
    logger.info("Callbook successfully loaded.")
    callbook.drop(
        columns=["SUFIXUL", "E-MAIL", "DATA LIMITA A REZERVARII"], inplace=True
    )

# Load POTA database
logger.info("Loading POTA database...")
path_to_database = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "../res/database.csv"
)
path_to_database = os.path.normpath(path_to_database)
try:
    potadb = pd.read_csv(path_to_database)
except FileNotFoundError:
    logger.error("Could not find the file 'database.csv'")
except pd.errors.EmptyDataError:
    logger.error("The file is empty.")
except pd.errors.ParserError:
    logger.error("Error: There was an issue parsing the CSV file.")
except UnicodeDecodeError:
    logger.error(
        "Error: Could not decode the file. Try specifying a different encoding."
    )
except Exception as e:
    logger.error(f"An unexpected error occurred: {e}")
else:
    logger.info("Database successfully loaded.")

# Utils


def getTime(ts):
    try:
        if "T" in ts:
            i = ts.index("T")
            date = ts[:i]
            hour = ts[i + 1 :].split(".")[0].rstrip("Z")
            return (date, hour)
        elif " " in ts:
            i = ts.index(" ")
            date = ts[:i]
            hour = ts[i + 1 :].split(".")[0]
            return (date, hour)
    except Exception:
        pass
    return (str(ts), "??")


async def send_message_with_retry(
    app, chat_id, message_thread_id, text, parse_mode="HTML", max_retries=5
):
    for attempt in range(max_retries):
        try:
            await app.bot.send_message(
                chat_id=chat_id,
                message_thread_id=message_thread_id,
                text=text,
                parse_mode=parse_mode,
            )
            logger.info(
                f"Message sent successfully to chat_id={chat_id} on attempt {attempt + 1}."
            )
            return
        except (ConnectTimeout, ConnectError, NetworkError, TimedOut) as e:
            logger.warning(
                f"Network error on attempt {attempt + 1}/{max_retries}: {e}. Retrying..."
            )
            await asyncio.sleep(2**attempt)
        except RetryAfter as e:
            seconds = (
                e.retry_after
                if isinstance(e.retry_after, (int, float))
                else e.retry_after.total_seconds()
            )
            retry_after = int(seconds)
            logger.warning(f"Rate limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
        except Exception as e:
            logger.error(
                f"Unexpected error on attempt {attempt + 1}/{max_retries}: {e}. Retrying..."
            )
            await asyncio.sleep(2**attempt)
    logger.error(f"Failed to send message after {max_retries} attempts. Giving up.")


def most_recent(count=30):
    r = requests.get("https://api.pota.app/program/parks/RO")
    data = r.json()
    df = pd.DataFrame(data)

    # Get last 'count' parks
    latest_parks = df.tail(count).iloc[::-1]  # Reverse to show newest first

    message = f"<b><u>Latest {count} parks added:</u></b>\n\n"

    for index, park in latest_parks.iterrows():
        url = "https://pota.app/#/park/" + park["reference"]
        message += (
            f"<a href='{url}'><b>[ {park['reference']} ]</b></a> - {park['name']}\n"
        )
        message += f"   📍 {park['locationDesc']}\n\n"

    return message


# Commands


async def help_command(
    update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    if update.message.message_thread_id == TOPIC_ID:
        try:
            await update.message.reply_text(
                "<b><u>Here is a list of commands you can use:</u></b>\n\n"
                "-- /help - Provides a list of usable commands\n"
                "-- /get_bota [FILTER] - Provides a list of the future BOTA activations\n"
                "-- /get_llota [FILTER] - Provides a list of the future LLOTA activations\n"
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
                parse_mode="HTML",
            )
        except Exception as e:
            logger.info("Failed to send message: " + str(e))


async def get_latest_park_command(
    update: telegram.Update, conext: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    if not update.message:
        return

    try:
        await update.message.reply_text(most_recent(), parse_mode="HTML")
    except Exception as e:
        logger.info("Failed to send message: " + e)


async def get_BOTA_command(
    update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    if (
        update.effective_chat.type == "private"
        and str(update.message.from_user.id) not in USER_ID_LIST
    ):
        try:
            await update.message.reply_text("Bot does not work in private chat.")
        except Exception as e:
            logger.info("Failed to send message: " + e)
        return

    if (
        update.message.message_thread_id == TOPIC_ID
        or str(update.message.from_user.id) in USER_ID_LIST
    ):
        ok, df = dc.centraliseBOTA(
            "https://www.beachesontheair.com/activations/announcements"
        )

        if ok == 0:
            try:
                await update.message.reply_text("An error occoured.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
            return

        if df.empty:
            try:
                await update.message.reply_text("No activators found.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
        else:
            for index, row in df.iterrows():
                logger.info("Sending message...")
                activator = row["Activator"]
                location = row["Activation"].split(" by")[0]
                date = row["UTC"]

                urlActivator = "https://www.qrz.com/db/" + activator

                try:
                    await update.message.reply_text(
                        f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> will be activating beach <b>[ {location} ]</b>\n\n"
                        f"Date and time: <b>{date}</b>\n",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.info("Failed to send message: " + e)
                sleep(0.5)

    logger.info("All messages have been sent.")


async def get_POTA_command(
    update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    if (
        update.effective_chat.type == "private"
        and str(update.message.from_user.id) not in USER_ID_LIST
    ):
        try:
            await update.message.reply_text("Bot does not work in private chat.")
        except Exception as e:
            logger.info("Failed to send message: " + e)
        return

    if (
        update.message.message_thread_id == TOPIC_ID
        or str(update.message.from_user.id) in USER_ID_LIST
    ):
        if context.args:
            filterPOTA = os.getenv(context.args[0].upper() + "_POTA")
            if not filterPOTA:
                try:
                    await update.message.reply_text(
                        f"Argument {context.args[0]} not recognised."
                    )
                except Exception as e:
                    logger.info("Failed to send message: " + e)
                return
            ok, df = dc.centralisePOTA(filterPOTA)
        else:
            ok, df = dc.centralisePOTA()

        if ok == 0:
            try:
                await update.message.reply_text("An error occoured.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
            return

        if df.empty:
            try:
                await update.message.reply_text("No activators found.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
        else:
            for index, row in df.iterrows():
                logger.info("Sending message...")
                activator = row["activator"]
                frequency = row["frequency"]
                reference = row["reference"]
                mode = row["mode"]
                name = row["name"]
                locationDesc = row["locationDesc"]
                comment = row["comments"]

                urlPark = "https://pota.app/#/park/" + reference
                urlActivator = "https://www.qrz.com/db/" + activator

                await update.message.reply_text(
                    f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating park <a href='{urlPark}'><b>[ {reference} ]</b></a> - <i>{name}</i>\n\n"
                    f"Frequency: <b>{frequency}</b>\n"
                    f"Mode: <b>{mode}</b>\n"
                    f"Region: <b>{locationDesc}</b>\n"
                    f"Info: <b>{comment}</b>",
                    parse_mode="HTML",
                )
                sleep(0.5)

    logger.info("All messages have been sent.")


async def get_SOTA_command(
    update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    if (
        update.effective_chat.type == "private"
        and str(update.message.from_user.id) not in USER_ID_LIST
    ):
        try:
            await update.message.reply_text("Bot does not work in private chat.")
        except Exception as e:
            logger.info("Failed to send message: " + e)
        return

    if (
        update.message.message_thread_id == TOPIC_ID
        or str(update.message.from_user.id) in USER_ID_LIST
    ):
        if context.args:
            filterSOTA = os.getenv(context.args[0].upper() + "_SOTA")
            if not filterSOTA:
                try:
                    await update.message.reply_text(
                        f"Argument {context.args[0]} not recognised."
                    )
                except Exception as e:
                    logger.info("Failed to send message: " + e)
                return
            ok, df = dc.centraliseSOTA(filterSOTA)
        else:
            ok, df = dc.centraliseSOTA()

        if ok == 0:
            try:
                await update.message.reply_text("An error occoured.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
            return

        if df.empty:
            try:
                await update.message.reply_text("No activators found.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
        else:
            for index, row in df.iterrows():
                logger.info("Sending message...")
                timestamp = getTime(row["timeStamp"])
                activator = row["activatorCallsign"]
                actName = row["activatorName"]
                comment = row["comments"]
                summitCode = row["summitCode"]
                summitDetails = row["summitDetails"]
                frequency = row["frequency"]
                mode = row["mode"]
                urlActivator = "https://www.qrz.com/db/" + row["activatorCallsign"]

                try:
                    await update.message.reply_text(
                        f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> - <i>{actName}</i> is now activating summit <b>[ {summitCode} ]</b> - <i>{summitDetails}</i>\n\n"
                        f"Posted at: <b>{timestamp[0]} - {timestamp[1]}</b>\n"
                        f"Frequency: <b>{frequency}</b>\n"
                        f"Mode: <b>{mode}</b>\n"
                        f"Activator's comment: <b>{comment}</b>",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.info("Failed to send message: " + e)
                sleep(0.5)

        logger.info("All messages have been sent.")


async def get_WWBOTA_command(
    update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    if (
        update.effective_chat.type == "private"
        and str(update.message.from_user.id) not in USER_ID_LIST
    ):
        try:
            await update.message.reply_text("Bot does not work in private chat.")
        except Exception as e:
            logger.info("Failed to send message: " + e)
        return

    if (
        update.message.message_thread_id == TOPIC_ID
        or str(update.message.from_user.id) in USER_ID_LIST
    ):
        ok, df = dc.centraliseWWBOTA()

        if ok == 0:
            try:
                await update.message.reply_text("An error occoured.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
            return

        if df.empty:
            try:
                await update.message.reply_text("No activators found.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
        else:
            for index, row in df.iterrows():
                logger.info("Sending message...")
                timestamp = getTime(row["time"])
                activator = row["call"]
                comment = row["comment"]
                ref = row["reference"]
                frequency = row["freq"]
                mode = row["mode"]
                urlActivator = "https://www.qrz.com/db/" + row["call"]

                try:
                    await update.message.reply_text(
                        f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating bunker <b>[ {ref} ]</b>\n\n"
                        f"Posted at: <b>{timestamp[0]} - {timestamp[1]}</b>\n"
                        f"Frequency: <b>{frequency}</b>\n"
                        f"Mode: <b>{mode}</b>\n"
                        f"Activator's comment: <b>{comment}</b>",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.info("Failed to send message: " + e)
                sleep(0.5)

        logger.info("All messages have been sent.")


async def get_LLOTA_command(
    update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    # 1. Access Check
    if (
        update.effective_chat.type == "private"
        and str(update.message.from_user.id) not in USER_ID_LIST
    ):
        try:
            await update.message.reply_text("Bot does not work in private chat.")
        except Exception as e:
            logger.info(f"Failed to send message: {e}")
        return

    # 2. Topic/User Check
    if (
        update.message.message_thread_id == TOPIC_ID
        or str(update.message.from_user.id) in USER_ID_LIST
    ):
        url = "https://llota.app/api/spots"
        ok, df = dc.centraliseLLOTA(url)

        if ok == 0:
            try:
                await update.message.reply_text("An error occurred.")
            except Exception as e:
                logger.info(f"Failed to send message: {e}")
            return

        # 3. Apply Filter if arguments exist
        if context.args and not df.empty:
            search_term = context.args[0].upper()
            # Filter by Callsign OR Country (e.g. "RO" matches YO calls or Romania)
            mask = df.apply(
                lambda x: search_term in str(x["callsign"]).upper()
                or search_term in str(x["country_name"]).upper(),
                axis=1,
            )
            df = df[mask].reset_index(drop=True)

        if df.empty:
            try:
                msg = (
                    f"No activators found matching '{context.args[0]}'."
                    if context.args
                    else "No activators found."
                )
                await update.message.reply_text(msg)
            except Exception as e:
                logger.info(f"Failed to send message: {e}")
        else:
            for index, row in df.iterrows():
                logger.info("Sending message...")

                raw_ts = str(row["timestamp"])
                if " " in raw_ts and "T" not in raw_ts:
                    raw_ts = raw_ts.replace(" ", "T")

                timestamp = (
                    getTime(raw_ts) if raw_ts and raw_ts != "None" else ("??", "??")
                )

                activator = row["callsign"]
                frequency = row["frequency"]
                mode = row["mode"]
                reference = row["reference"]
                refName = row["reference_name"]
                country = row["country_name"]
                comment = row["comment"]

                urlActivator = "https://www.qrz.com/db/" + activator

                try:
                    await update.message.reply_text(
                        f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating "
                        f"<b>[ {reference} ]</b> - <i>{refName}</i> ({country})\n\n"
                        f"Posted at: <b>{timestamp[0]} - {timestamp[1]}</b>\n"
                        f"Frequency: <b>{frequency}</b>\n"
                        f"Mode: <b>{mode}</b>\n"
                        f"Info: <b>{comment}</b>",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.info(f"Failed to send message: {e}")
                sleep(0.5)

    logger.info("All messages have been sent.")


async def callsign_info_command(
    update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    global callbook
    if callbook is None:
        try:
            await update.message.reply_text("Callbook could not be loaded.")
        except Exception as e:
            logger.info("Failed to send message: " + e)
        return
    if (
        update.effective_chat.type == "private"
        and str(update.message.from_user.id) not in USER_ID_LIST
    ):
        try:
            await update.message.reply_text("Bot does not work in private chat.")
        except Exception as e:
            logger.info("Failed to send message: " + e)
        return

    if (
        update.message.message_thread_id == TOPIC_ID
        or str(update.message.from_user.id) in USER_ID_LIST
    ):
        if not context.args:
            try:
                await update.message.reply_text("Please provide a callsign.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
            return

        if len(context.args) > 1:
            try:
                await update.message.reply_text("Too many arguments.")
            except Exception as e:
                logger.info("Failed to send message: " + e)
        else:
            callsign = context.args[0].strip().upper()
            index = callbook[
                callbook["INDICATIVUL"].str.strip().str.upper() == callsign
            ].index
            if len(index) == 0:
                try:
                    await update.message.reply_text("Callsign not found.")
                except Exception as e:
                    logger.info("Failed to send message: " + e)
            else:
                row = callbook.loc[index[0]]
                name = row["TITULARUL"]
                cls = row["CLASA"]
                loc = row["LOCALITATEA"]
                exp = row["DATA EXPIRARII"]
                url = "https://www.ancom.ro/radioamatori_2899"

                try:
                    await update.message.reply_text(
                        f"Showing information about operator: <b>{name} - [ {callsign} ]</b>\n"
                        f"Class: <b>{cls}</b>\n"
                        f"Location: <b>{loc}</b>\n"
                        f"Expiration date: <b>{exp}</b>\n"
                        f"Source: <a href='{url}'><b>ANCOM</b></a>",
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.info("Failed to send message: " + e)


async def potadate_command(
    update: telegram.Update, context: telegram.ext.ContextTypes.DEFAULT_TYPE
):
    if not context.args:
        try:
            await update.message.reply_text("Please provide a reference.")
        except Exception as e:
            logger.info("Failed to send message: " + e)
        return

    if len(context.args) > 1:
        try:
            await update.message.reply_text("Too many arguments.")
        except Exception as e:
            logger.info("Failed to send message: " + e)
    else:
        ref = context.args[0].strip().upper()

        if ref not in potadb["reference"].values:
            await update.message.reply_text("Park reference not found.")
        else:
            await update.message.reply_text(
                f"Park <b>{ref}</b> was added on <b>{potadb.loc[potadb['reference'] == ref, 'date'].iloc[0]}</b>.",
                parse_mode="HTML",
            )


# Automatic Spotting


async def send_msg_POTA(
    activator, frequency, reference, mode, name, locationDesc, comment
):
    urlPark = "https://pota.app/#/park/" + reference
    urlActivator = "https://www.qrz.com/db/" + activator

    message = (
        f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating park <a href='{urlPark}'><b>[ {reference} ]</b></a> - <i>{name}</i>\n\n"
        f"Frequency: <b>{frequency}</b>\n"
        f"Mode: <b>{mode}</b>\n"
        f"Region: <b>{locationDesc}</b>\n"
        f"Info: <b>{comment}</b>"
    )
    await send_message_with_retry(app, CHAT_ID, TOPIC_ID, message)
    await asyncio.sleep(0.5)


async def send_msg_SOTA(
    timeStamp,
    activatorCallsign,
    activatorName,
    comments,
    summitCode,
    summitDetails,
    frequency,
    mode,
):
    urlActivator = "https://www.qrz.com/db/" + activatorCallsign

    message = (
        f"<a href='{urlActivator}'><b>[ {activatorCallsign} ]</b></a> - <i>{activatorName}</i> is now activating summit <b>[ {summitCode} ]</b> - <i>{summitDetails}</i>\n\n"
        f"Posted at: <b>{timeStamp[0]} - {timeStamp[1]}</b>\n"
        f"Frequency: <b>{frequency}</b>\n"
        f"Mode: <b>{mode}</b>\n"
        f"Activator's comment: <b>{comments}</b>"
    )
    await send_message_with_retry(app, CHAT_ID, TOPIC_ID, message)
    await asyncio.sleep(0.5)


async def send_msg_WWBOTA(timestamp, activator, comment, ref, frequency, mode):
    urlActivator = "https://www.qrz.com/db/" + activator

    message = (
        f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating bunker <b>[ {ref} ]</b>\n\n"
        f"Posted at: <b>{timestamp[0]} - {timestamp[1]}</b>\n"
        f"Frequency: <b>{frequency}</b>\n"
        f"Mode: <b>{mode}</b>\n"
        f"Activator's comment: <b>{comment}</b>"
    )
    await send_message_with_retry(app, CHAT_ID, TOPIC_ID, message)
    await asyncio.sleep(0.5)


async def send_msg_LLOTA(
    timestamp, activator, frequency, mode, reference, refName, country, comment
):
    if timestamp:
        raw_ts = str(timestamp).replace(" ", "T")
        ts = getTime(raw_ts)
    else:
        ts = ("??", "??")

    urlActivator = "https://www.qrz.com/db/" + activator

    message = (
        f"<a href='{urlActivator}'><b>[ {activator} ]</b></a> is now activating "
        f"<b>[ {reference} ]</b> - <i>{refName}</i> ({country})\n\n"
        f"Posted at: <b>{ts[0]} - {ts[1]}</b>\n"
        f"Frequency: <b>{frequency}</b>\n"
        f"Mode: <b>{mode}</b>\n"
        f"Info: <b>{comment}</b>"
    )
    await send_message_with_retry(app, CHAT_ID, TOPIC_ID, message)
    await asyncio.sleep(0.5)


act_pota = {}
act_sota = {}
act_wwbota = {}
act_llota = {}


async def auto_spot(app):
    global act_pota
    global act_sota
    global act_wwbota
    sent = False

    try:
        _, df = dc.centralisePOTA()
        flt = os.getenv("AUTO_SPOT")
        if flt:
            flt = flt.split()
            mask = df["activator"].apply(
                lambda x: any(activator in x for activator in flt)
            )
            df = df[mask].reset_index(drop=True)

            for index, row in df.iterrows():
                if row["activator"] not in act_pota:
                    act_pota[row["activator"]] = (
                        row["reference"],
                        row["frequency"],
                        row["comments"],
                    )
                    await send_msg_POTA(
                        row["activator"],
                        row["frequency"],
                        row["reference"],
                        row["mode"],
                        row["name"],
                        row["locationDesc"],
                        row["comments"],
                    )
                    sent = True
                    continue
                if act_pota[row["activator"]][0] != row["reference"]:
                    act_pota[row["activator"]] = (
                        row["reference"],
                        row["frequency"],
                        row["comments"],
                    )
                    await send_msg_POTA(
                        row["activator"],
                        row["frequency"],
                        row["reference"],
                        row["mode"],
                        row["name"],
                        row["locationDesc"],
                        row["comments"],
                    )
                    sent = True
                    continue
                if (
                    abs(int(act_pota[row["activator"]][1]) - int(row["frequency"]))
                    >= 999
                ):
                    act_pota[row["activator"]] = (
                        row["reference"],
                        row["frequency"],
                        row["comments"],
                    )
                    await send_msg_POTA(
                        row["activator"],
                        row["frequency"],
                        row["reference"],
                        row["mode"],
                        row["name"],
                        row["locationDesc"],
                        row["comments"],
                    )
                    sent = True
                    continue
                if (
                    (
                        "QRT" in row["comments"].upper()
                        and "QRT" not in act_pota[row["activator"]][2].upper()
                    )
                    or (
                        "QRV" in row["comments"].upper()
                        and "QRV" not in act_pota[row["activator"]][2].upper()
                    )
                    or (
                        "QSY" in row["comments"].upper()
                        and "QSY" not in act_pota[row["activator"]][2].upper()
                    )
                ):
                    act_pota[row["activator"]] = (
                        row["reference"],
                        row["frequency"],
                        row["comments"],
                    )
                    await send_msg_POTA(
                        row["activator"],
                        row["frequency"],
                        row["reference"],
                        row["mode"],
                        row["name"],
                        row["locationDesc"],
                        row["comments"],
                    )
                    sent = True
            if sent:
                logger.info("Auto spot messages sent successfully.")
    except Exception as e:
        logger.error(f"Auto spot error: {e}")

    sent = False

    try:
        _, df = dc.centraliseSOTA()
        flt = os.getenv("AUTO_SPOT")
        if flt:
            flt = flt.split()
            mask = df["activatorCallsign"].apply(
                lambda x: any(activator in x for activator in flt)
            )
            df = df[mask].reset_index(drop=True)

            for index, row in df.iterrows():
                if row["activatorCallsign"] not in act_sota:
                    act_sota[row["activatorCallsign"]] = (
                        row["summitCode"],
                        row["frequency"],
                        row["comments"],
                    )
                    await send_msg_SOTA(
                        row["timeStamp"],
                        row["activatorCallsign"],
                        row["activatorName"],
                        row["comments"],
                        row["summitCode"],
                        row["summitDetails"],
                        row["frequency"],
                        row["mode"],
                    )
                    sent = True
                    continue
                if act_sota[row["activatorCallsign"]][0] != row["summitCode"]:
                    act_sota[row["activatorCallsign"]] = (
                        row["summitCode"],
                        row["frequency"],
                        row["comments"],
                    )
                    await send_msg_SOTA(
                        row["timeStamp"],
                        row["activatorCallsign"],
                        row["activatorName"],
                        row["comments"],
                        row["summitCode"],
                        row["summitDetails"],
                        row["frequency"],
                        row["mode"],
                    )
                    sent = True
                    continue
                if (
                    abs(
                        int(act_sota[row["activatorCallsign"]][1])
                        - int(row["frequency"])
                    )
                    >= 999
                ):
                    act_sota[row["activatorCallsign"]] = (
                        row["summitCode"],
                        row["frequency"],
                        row["comments"],
                    )
                    await send_msg_SOTA(
                        row["timeStamp"],
                        row["activatorCallsign"],
                        row["activatorName"],
                        row["comments"],
                        row["summitCode"],
                        row["summitDetails"],
                        row["frequency"],
                        row["mode"],
                    )
                    sent = True
                    continue
                if (
                    (
                        "QRT" in row["comments"].upper()
                        and "QRT" not in act_sota[row["activatorCallsign"]][2].upper()
                    )
                    or (
                        "QRV" in row["comments"].upper()
                        and "QRV" not in act_sota[row["activatorCallsign"]][2].upper()
                    )
                    or (
                        "QSY" in row["comments"].upper()
                        and "QSY" not in act_sota[row["activatorCallsign"]][2].upper()
                    )
                ):
                    act_sota[row["activatorCallsign"]] = (
                        row["summitCode"],
                        row["frequency"],
                        row["comments"],
                    )
                    await send_msg_SOTA(
                        row["timeStamp"],
                        row["activatorCallsign"],
                        row["activatorName"],
                        row["comments"],
                        row["summitCode"],
                        row["summitDetails"],
                        row["frequency"],
                        row["mode"],
                    )
                    sent = True
            if sent:
                logger.info("Auto spot messages sent successfully.")
    except Exception as e:
        logger.error(f"Auto spot error: {e}")

    try:
        url = "https://llota.app/api/spots"
        _, df = dc.centraliseLLOTA(url)
        flt = os.getenv("AUTO_SPOT")

        if flt and not df.empty:
            flt = flt.split()
            # 1. Filter by callsign first
            mask = df["callsign"].apply(
                lambda x: any(activator in x for activator in flt)
            )
            df = df[mask].reset_index(drop=True)

            if not df.empty and "timestamp" in df.columns:
                df = df.sort_values("timestamp", ascending=True)
                df = df.drop_duplicates(subset=["callsign"], keep="last")

            for index, row in df.iterrows():
                callsign = row["callsign"]

                try:
                    raw_freq = float(row["frequency"])
                    if raw_freq > 200:
                        current_freq = f"{raw_freq / 1000:.3f}"
                    else:
                        current_freq = str(row["frequency"])
                except ValueError:
                    current_freq = str(row["frequency"])

                # Check for new spot
                if callsign not in act_llota:
                    act_llota[callsign] = (
                        row["reference"],
                        current_freq,
                        row["comment"] if row["comment"] else "",
                    )
                    await send_msg_LLOTA(
                        row["timestamp"],
                        callsign,
                        current_freq,
                        row["mode"],
                        row["reference"],
                        row["reference_name"],
                        row["country_name"],
                        row["comment"],
                    )
                    sent = True
                    continue

                # Check for reference change
                if act_llota[callsign][0] != row["reference"]:
                    act_llota[callsign] = (
                        row["reference"],
                        current_freq,
                        row["comment"] if row["comment"] else "",
                    )
                    await send_msg_LLOTA(
                        row["timestamp"],
                        callsign,
                        current_freq,
                        row["mode"],
                        row["reference"],
                        row["reference_name"],
                        row["country_name"],
                        row["comment"],
                    )
                    sent = True
                    continue

                # Check for frequency change (MHz)
                try:
                    old_freq_float = float(act_llota[callsign][1])
                    new_freq_float = float(current_freq)

                    if abs(old_freq_float - new_freq_float) >= 0.001:
                        act_llota[callsign] = (
                            row["reference"],
                            current_freq,
                            row["comment"] if row["comment"] else "",
                        )
                        await send_msg_LLOTA(
                            row["timestamp"],
                            callsign,
                            current_freq,
                            row["mode"],
                            row["reference"],
                            row["reference_name"],
                            row["country_name"],
                            row["comment"],
                        )
                        sent = True
                        continue
                except ValueError:
                    # Fallback if frequency isn't a valid float
                    pass

                # Check for Q-codes in comments
                current_comment = row["comment"] if row["comment"] else ""
                old_comment = act_llota[callsign][2]

                if (
                    (
                        "QRT" in current_comment.upper()
                        and "QRT" not in old_comment.upper()
                    )
                    or (
                        "QRV" in current_comment.upper()
                        and "QRV" not in old_comment.upper()
                    )
                    or (
                        "QSY" in current_comment.upper()
                        and "QSY" not in old_comment.upper()
                    )
                ):
                    act_llota[callsign] = (
                        row["reference"],
                        current_freq,
                        current_comment,
                    )
                    await send_msg_LLOTA(
                        row["timestamp"],
                        callsign,
                        current_freq,
                        row["mode"],
                        row["reference"],
                        row["reference_name"],
                        row["country_name"],
                        row["comment"],
                    )
                    sent = True

            if sent:
                logger.info("LLOTA Auto spot messages sent successfully.")
    except Exception as e:
        logger.error(f"LLOTA Auto spot error: {e}")

    # WWBOTA auto-spotting is now handled by SSE listener (wwbota_sse_listener)


async def wwbota_sse_listener(app):
    """Listen to WWBOTA SSE stream for real-time spots."""
    global act_wwbota
    flt = os.getenv("AUTO_SPOT")
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
                async with sse_client.EventSource(
                    url, session=session, headers=headers
                ) as event_source:
                    logger.info("Connected to WWBOTA SSE stream.")
                    async for event in event_source:
                        if event.data:
                            try:
                                spot = json.loads(event.data)
                                call = spot.get("call", "")

                                # Check if callsign is in AUTO_SPOT filter
                                if not any(activator in call for activator in flt):
                                    continue

                                # Extract data
                                ref = (
                                    spot.get("references", [{}])[0].get("reference", "")
                                    if spot.get("references")
                                    else ""
                                )
                                freq = spot.get("freq", 0)
                                mode = spot.get("mode", "")
                                spot_type = spot.get("type", "").upper()
                                comment = spot.get("comment", "")
                                time_str = spot.get("time", "")

                                # Parse timestamp
                                if time_str and "T" in time_str:
                                    timestamp = (
                                        time_str.split("T")[0],
                                        time_str.split("T")[1].split(".")[0],
                                    )
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
                                elif (
                                    (
                                        "QRT" in spot_type
                                        and "QRT" not in act_wwbota[call][2]
                                    )
                                    or (
                                        "QRV" in spot_type
                                        and "QRV" not in act_wwbota[call][2]
                                    )
                                    or (
                                        "QSY" in spot_type
                                        and "QSY" not in act_wwbota[call][2]
                                    )
                                ):
                                    act_wwbota[call] = (ref, freq, spot_type)
                                    should_send = True

                                if should_send:
                                    await send_msg_WWBOTA(
                                        timestamp,
                                        call,
                                        comment if comment else spot_type,
                                        ref,
                                        freq,
                                        mode,
                                    )
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


if __name__ == "__main__":
    logger.info("Starting bot...")
    app = telegram.ext.Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(telegram.ext.CommandHandler("help", help_command))
    app.add_handler(telegram.ext.CommandHandler("latest", get_latest_park_command))
    app.add_handler(telegram.ext.CommandHandler("get_BOTA", get_BOTA_command))
    app.add_handler(telegram.ext.CommandHandler("get_LLOTA", get_LLOTA_command))
    app.add_handler(telegram.ext.CommandHandler("get_POTA", get_POTA_command))
    app.add_handler(telegram.ext.CommandHandler("get_SOTA", get_SOTA_command))
    app.add_handler(telegram.ext.CommandHandler("get_WWBOTA", get_WWBOTA_command))
    app.add_handler(telegram.ext.CommandHandler("callsign", callsign_info_command))
    app.add_handler(telegram.ext.CommandHandler("potadate", potadate_command))

    # Automatic spotting
    loop = asyncio.get_event_loop()
    loop.create_task(scheduler(app))
    loop.create_task(wwbota_sse_listener(app))

    # Polling
    logger.info("Polling...")
    app.run_polling(poll_interval=3)
