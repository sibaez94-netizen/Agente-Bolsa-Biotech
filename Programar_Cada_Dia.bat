@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Programando el Agente de Bolsa cada dia a las 08:30 (solo actualizacion local, sin duplicar el correo de GitHub Actions)...
schtasks /Create /F /SC DAILY /ST 08:30 /TN "Agente Bolsa Local" /TR "cmd /c cd /d \"%~dp0\" && set NO_ENVIAR_EMAIL=1 && python main.py"
echo.
echo Hecho. Para quitar la tarea:  schtasks /Delete /TN "Agente Bolsa Local" /F
echo (Si quieres que envie correo desde tu PC, quita "set NO_ENVIAR_EMAIL=1 && " de este archivo.)
pause
