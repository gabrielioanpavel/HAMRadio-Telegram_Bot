import pandas as pd
import requests
import logging
import json
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

logger = logging.getLogger('BotLogger')
load_dotenv()

# Function for retrying to connect to the API in the case of failure
def sessionRetries(retries=3, backoff_factor=1, status_forcelist=(500, 502, 504)) -> requests.sessions.Session:
    session = requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor, status_forcelist=status_forcelist)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Function to fetch the data given by the API
def fetchData(url: str) -> dict:
    session = sessionRetries()
    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.ConnectionError as e:
        logging.error(f'Connection error: {e}')
        return None
    except requests.exceptions.HTTPError as e:
        logging.error(f'HTTPS error: {e}')
        return None
    except requests.exceptions.Timeout as e:
        logging.error(f'Timeout error: {e}')
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f'Request exception: {e}')
        return None

# Function that takes the fetched data and stores it into a Pandas DataFrame for POTA activations
def centralisePOTA(filterPOTA=os.getenv('FILTER_POTA')):
    logger.info('Fetching data from [https://api.pota.app/spot/activator]...')
    url = 'https://api.pota.app/spot/activator'
    data = fetchData(url)
    df = pd.DataFrame
    if data:
        logger.info('Fetching successful, building DataFrame...')

        # Construction of DataFrame
        df = pd.DataFrame(data)
        df.drop(['spotId', 'spotTime', 'source', 'spotter', 'parkName', 'invalid', 'grid6', 'count', 'expire'], axis=1, inplace=True)

        # This is a filter for removing certain lines form the DataFrame
        if filterPOTA:
            filterPOTA = filterPOTA.split()
            mask = df['grid4'].apply(lambda x: any(x.startswith(grid) for grid in filterPOTA))
            df = df[mask].reset_index(drop=True)

        df.drop_duplicates(inplace=True)
        logger.info('Operation complete.')
        return (1, df)
    else:
        logger.error('Failed to fetch data.')
        return (0, df)

# Function that takes the fetched data and stores it into a Pandas DataFrame for SOTA activations
def centraliseSOTA(filterSOTA=os.getenv('FILTER_SOTA')):
    logger.info('Fetching data from [https://api2.sota.org.uk/api/spots/-24/all]...')
    url = 'https://api2.sota.org.uk/api/spots/-24/all'
    data = fetchData(url)
    df = pd.DataFrame
    if data:
        logger.info('Fetching successful, building DataFrame')

        # Construction of DataFrame
        df = pd.DataFrame(data)
        df.drop(['id', 'userID', 'callsign', 'highlightColor'], axis=1, inplace=True)

        # This is a filter for removing certain lines form the DataFrame
        if filterSOTA:
            filterSOTA = filterSOTA.split()
            mask = df['associationCode'].apply(lambda x: any(x.startswith(grid) for grid in filterSOTA))
            df = df[mask].reset_index(drop=True)

        df.drop_duplicates(inplace=True)
        logger.info('Operation complete.')
        return (1, df)
    else:
        return (0, df)