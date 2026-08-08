@echo off
REM Atalho para abrir a janela de pesquisa sem passar pelo terminal.
REM Copiar para o Ambiente de Trabalho (botao direito > Enviar para).
cd /d "%~dp0"
start "" pythonw "procurar_pericias.pyw"
