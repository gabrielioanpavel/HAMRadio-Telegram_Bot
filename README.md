# HAMRadio-Telegram_Bot

A Telegram bot that provides real-time information about BOTA, POTA, SOTA and WWBOTA activations.

I created this mainly for HAM Radio operators **YO3BEE** and **YO3DYL**, but decided to open-source it. Its main features are BOTA, POTA, SOTA and WWBOTA spotting via commands, as well as auto-spotting for specific callsigns.

## Features

* **BOTA, POTA, SOTA and WWBOTA Spotting**: Get the latest spots for Beaches, Parks, Summits and Bunkers activations.
* **Auto-Spotting**: Automatically track and announce spots for selected callsigns.
* **Custom Filters**: Filter spots by grid squares (POTA) or country prefixes (SOTA).
* **Dockerized**: Easy deployment using Docker and Docker Compose.

## Prerequisites

* **Docker** and **Docker Compose** installed on your machine.
* A **Telegram Bot Token** (obtained from [@BotFather](https://t.me/BotFather)).
* A **Telegram User ID** or **Chat ID** where the bot will operate.
* A **Telegram Topic ID**

## Installation and Setup

### On a server

1. **Clone the repository:**

    ```bash
    git clone [https://github.com/gabrielioanpavel/HAMRadio-Telegram_Bot.git](https://github.com/gabrielioanpavel/HAMRadio-Telegram_Bot.git)
    cd HAMRadio-Telegram_Bot
    ```

2. **Create a `.env` file:**
    Create a file named `.env` in the root directory and populate it with your configuration. You **must** include the following variables:

    ```env
    TOKEN="YOUR_BOT_TOKEN_HERE"
    BOT_USERNAME="@YOUR_BOT_USERNAME"
    CHAT_ID=YOUR_CHAT_ID
    TOPIC_ID=YOUR_TOPIC_ID
    
    # Auto-spotting configuration
    AUTO_SPOT="CALLSIGN1 CALLSIGN2 CALLSIGN3"
    
    # Default Filters
    FILTER_POTA="GRID1 GRID2 GRID3" 
    # Example: FILTER_POTA="KN24 KN25"
    
    FILTER_SOTA="COUNTRY_CALLSIGN1 COUNTRY_CALLSIGN2"
    # Example: FILTER_SOTA="YO YP YR" (Romania)
    ```

3. **Advanced Filtering (Optional):**
    You can create custom filters by adding variables like `SOMETHING_POTA` or `SOMETHING_SOTA` to your `.env` file. These can then be used as arguments in commands.

    *Example:*

    ```env
    EU_POTA="GRIDS_FOR_EUROPE"
    EU_SOTA="CALLSIGNS_FOR_EUROPE"
    ```

    *Usage:* `/get_pota EU` will use the `EU_POTA` filter.

4. **Build and Run with Docker:**

    ```bash
    sudo docker-compose build
    sudo docker-compose up -d
    ```

    Logs will be written to the `logs/` directory, timestamped by start date.

### Telegram Configuration

Use **@BotFather** to set the command list for your bot. Send `/setcommands` to BotFather and paste the following:

```text
help - Display available commands
get_bota - Get future BOTA activations
get_pota - Get latest POTA activations
get_sota - Get latest SOTA activations
get_wwbota - Get latest WWBOTA activations
callsign - Get details about an operator
latest - Get the latest added park
