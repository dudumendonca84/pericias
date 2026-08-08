@echo off
REM Gera "Procurar Pericias.exe" -- um executavel autonomo, sem Python.
REM Correr na maquina de quem desenvolve, nao na do perito.
cd /d "%~dp0"

echo A instalar o empacotador...
python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org pyinstaller
if errorlevel 1 goto erro

echo.
echo A construir...
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name "Procurar Pericias" ^
  --distpath "entrega" ^
  --workpath "build" ^
  --specpath "build" ^
  procurar_pericias.pyw
if errorlevel 1 goto erro

echo.
echo A copiar o acervo...
if exist acervo_pericias.sqlite (
  copy /y acervo_pericias.sqlite "entrega\" >nul
  echo   acervo copiado
) else (
  echo   AVISO: acervo_pericias.sqlite nao existe. Constroi o indice primeiro.
)

echo.
echo ============================================================
echo  Pronto. A pasta "entrega" tem tudo o que e preciso:
echo    Procurar Pericias.exe
echo    acervo_pericias.sqlite
echo.
echo  Copia essa pasta para a maquina do perito. Nao precisa
echo  de Python nem de mais nada instalado.
echo ============================================================
goto fim

:erro
echo.
echo FALHOU. Ve a mensagem acima.

:fim
echo.
pause
