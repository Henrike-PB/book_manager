@echo off
REM Build .exe com PyInstaller (onefile). Ajuste se logo.png não existir.
SET APP=book_dashboard.py
SET ICON=app_icon.ico
REM Se não tiver ícone, remova --icon argument
pyinstaller --onefile --windowed --add-data "logo.png;." %APP%
echo Build finalizado. Verifique a pasta dist\.
pause
