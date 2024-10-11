# Telegram Bot for POTA and SOTA information

I created this mainly for HAM Radio operators YO3BEE and YO3DYL, but decided to create a repo for it. Its main features are
BOTA, POTA and SOTA spotting in the form of commands and auto-spotting for selected callsigns.

## Getting Started

### Dependencies

* Python 3
* pip
* All used Python modules are in requirements.txt

### Installing

* Make sure you have Python3 and pip installed
* Clone the repository
* Install the requirements:

```bash
pip install -r requirements.txt
```

* Give execute permissions to the shell scripts:

```bash
chmod +x *.sh
```

* Install the Chrome Driver so the BOTA function will work:

```bash
./chromedriver_installation.sh
```

### Setup

* Create a `.env` file. You must include the following lines for the bot to work:

```bash
TOKEN="YOUR_BOTS_TOKEN"
BOT_USERNAME="@YOUR_BOTS_USERNAME"
CHAT_ID=YOUR_CHATS_ID
TOPIC_ID=YOUR_TOPICS_ID
```

* Add the filters to `.env`. Note that filters for **POTA** must contain **grids**, while filters for **SOTA**
must contain **callsigns** that represent a country (ex.: Romania - YO YP YR). For the auto-spot feature use
specific **callsigns**. Reference:

```bash
AUTO_SPOT="CALLSIGN1 CALLSIGN2 CALLSIGN3"
FILTER_POTA="GRID1 GRID2 GRID3"
FILTER_SOTA="COUNTRY_CALLSIGN1 COUNTRY_CALLSIGN2"
```

> Note that the bot is made to work in a specific topic only.

* You may add additional filters for either POTA or SOTA in a similar manner as above. `FILTER_POTA` and `FILTER_SOTA`
are the default ones. The additional filters will be applied when sent as an argument of a command. Reference:

```bash
EU_POTA="GRIDS_CONTAINING_EUROPE"
EU_SOTA="CALLSIGNS_OF_EUROPEAN_COUNTRIES"
```

> To create a filter, simply add `SOMETHING_POTA` or `SOMETHING_SOTA` to `.env`. The argument passed through the message
should coincide with **SOMETHING** (i.e. `/get_pota EU` for the above European filter).

* Create a bot using BotFather on Telegram.
* Set the following commands with `/set_commands` :

```telegram
/info
/get_bota
/get_pota
/get_sota
```

## Running the bot

Run the following command in the terminal to start the bot:

```bash
./start_bot.sh
```

You will receive informational logs in the console and error logs in the `log.txt` file.

### Usage

* Use the `/help` command to display the available commands.
* Use `/get_bota` to get a list of future BOTA activations.
* Use `/get_pota` to get the latest information on POTA activations.
* Use `/get_sota` to get the latest information on SOTA activations.
* You may provide an argument to the `/get_pota` or `/get_sota` commands to represent a certain filter that was created in `.env`.

## Contributing

Pull requests are welcome. For major changes or bugs please open an issue first.

## License

This project is licensed under the [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.en.html) License - see the LICENSE file for details
