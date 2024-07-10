import pandas as pd
import requests
import logging
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] at %(asctime)s - %(message)s')

def sessionRetries(retries=3, backoff_factor=0.5, status_forcelist=(500, 502, 504)):
    session = requests.Session()
    retry = Retry(total=retries, read=retries, connect=retries, backoff_factor=backoff_factor, status_forcelist=status_forcelist)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# The API gives a list of dictionaries
def fetchData(url):
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

logger.info('Fetching data from [https://api.pota.app/spot/]...')
url = 'https://api.pota.app/spot/'
data = fetchData(url)
if data:
    logger.info('Fetching successful.')
    df = pd.DataFrame(data)
    df.drop(['spotId', 'spotTime', 'mode', 'spotter', 'comments'], axis=1, inplace=True)
else:
    logging.error('Failed to fetch data.')
logging.info('Operation complete.')