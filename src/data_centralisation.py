import pandas as pd
import requests
import logging
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time

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
    logger.info('Fetching data from [https://api2.sota.org.uk/api/spots/-1/all]...')
    url = 'https://api2.sota.org.uk/api/spots/-1/all'
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

def centraliseBOTA(url):
    try:
        # Setup Chrome Driver
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        # Get the page
        driver.get(url)
        time.sleep(5)
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        # Fetch the table
        forthcoming_div = soup.find('div', {'class': 'view-header'}).find('h2', string="Forthcoming")
        if forthcoming_div:
            next_div = forthcoming_div.find_parent('div').find_next_sibling('div')
            table = next_div.find('table')
            if table:
                headers = []
                data = []
                header_row = table.find('thead')
                if header_row:
                    headers = [th.text.strip() for th in header_row.find_all('th')]
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    row_data = [cell.text.strip() for cell in cells]
                    if row_data:
                        data.append(row_data)
                if data:
                    df = pd.DataFrame(data, columns=headers if headers else None)
                    df = df.iloc[:, :-1]
                    return (1, df)
                else:
                    df = pd.DataFrame
                    logger.info("No data found in table.")
                    return (0, df)
            else:
                logger.error("Could not find table.")
        else:
            logger.error("Could not find 'Forthcoming' section.")
    except NoSuchElementException as e:
        logger.error(f"Unable to find the table or element on the page. Details: {e}")
    except TimeoutException as e:
        logger.error(f"The page took too long to load. Details: {e}")
    except WebDriverException as e:
        logger.error(f"Issue with WebDriver. Details: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred. Details: {e}")
    finally:
        driver.quit()
