@echo off
cd /d "%~dp0"
echo Startar MZ Scouting... Stang det har fonstret for att avsluta appen.
py -m mzanalys webb
if errorlevel 1 python -m mzanalys webb
pause
