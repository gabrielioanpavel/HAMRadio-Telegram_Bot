#!/bin/bash

PATH_TO_BOT=$(find / -type d -name 'Bot_POTA-Telegram' 2> /dev/null -print -quit)
PATH_TO_BOT+="/src/bot.py"
python3 $PATH_TO_BOT
