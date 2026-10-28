@echo off
cd /d "%~dp0"
echo Startar MZ Scouting for dator och mobil... Stang det har fonstret for att avsluta appen.
py -m mzanalys webb --mobil
if errorlevel 1 python -m mzanalys webb --mobil
pause
