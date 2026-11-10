@echo off
chcp 65001 > nul
title Radar Inteligente de Bolsa: Biotech, IVD, AgTech y Defensa
echo ============================================================================
echo   INICIANDO AGENTE DE BOLSA CORE-SATELLITE (CON MEMORIA Y MODO MENTOR)
echo ============================================================================
cd /d "%~dp0"
python main.py
echo.
echo Abriendo Panel Web Interactivo...
start "" "docs\index.html"
pause
