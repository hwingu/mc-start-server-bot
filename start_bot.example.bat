@echo off
title Minecraft Discord Bot (Auto-Restart Enabled)
cd /D "C:\Path\To\Your\Bot\"

echo Starting Playit tunnel in a new window...
START "Playit Tunnel" playit

:start_loop
echo Activating virtual environment...
call .\venv\Scripts\activate.bat

echo Starting the bot (bot.py)...
python bot.py

echo Bot has stopped or crashed. Restarting in 5 seconds...
timeout /t 5 /nobreak
goto start_loop