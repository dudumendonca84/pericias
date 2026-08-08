@echo off
REM Acrescenta ao acervo as pericias novas. Correr depois de entregar uma peca.
cd /d "%~dp0"
python atualizar.py
echo.
pause
