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

# Function that takes the fetched data and stores it into a Pandas DataFrame, keeping only YO activators
def centralise():
    logger.info('Fetching data from [https://api.pota.app/spot/activator]...')
    url = 'https://api.pota.app/spot/activator'
    data = fetchData(url)
    df = pd.DataFrame
    if data:
        logger.info('Fetching successful.')

        # Construction of DataFrame
        df = pd.DataFrame(data)
        df.drop(['spotId', 'spotTime', 'source', 'spotter', 'parkName', 'invalid', 'grid6', 'count', 'expire'], axis=1, inplace=True)

        # This is a filter so that only European activators are kept in the DataFrame
        grids = os.getenv('GRIDS_EU').split()
        mask = df['grid4'].apply(lambda x: any(x.startswith(grid) for grid in grids))
        df = df[mask].reset_index(drop=True)

        df.drop_duplicates(inplace=True)
        logger.info('Operation complete.')
        return (1, df)
    else:
        logger.error('Failed to fetch data.')
        return (0, df)
