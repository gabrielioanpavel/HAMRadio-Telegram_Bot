#!/bin/bash

PATH_TO_BOT=$(find / -type d -name 'HAMRadio-Telegram_Bot' 2> /dev/null -print >
PATH_TO_BOT+="/src/bot.py"

PATH_TO_SIGNAL_CHECKER=$(find / -type d -name 'HAMRadio-Telegram_Bot' 2> /dev/n>
PATH_TO_SIGNAL_CHECKER+="/src/check_for_signal.py"

python3 $PATH_TO_BOT &
python3 $PATH_TO_SIGNAL_CHECKER