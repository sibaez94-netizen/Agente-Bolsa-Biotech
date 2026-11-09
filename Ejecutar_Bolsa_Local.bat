@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================================
echo   RADAR DE BOLSA BIOTECH, AGTECH (CRISPR/RNAi) Y DEFENSA (CORE-SATELLITE)
echo ============================================================================
echo.
python main.py
echo.
echo [OK] Abriendo el Panel Web Interactivo en tu navegador...
start "" "%~dp0docs\index.html"
pause
