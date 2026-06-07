@echo off
title BOT ALERTAS GLPI
color 0C
cd /d C:\Bot_Incidentes
echo ================================================
echo    BOT ALERTAS GLPI - VENCIMIENTOS Y ANTIGUOS
echo ================================================
echo.
python bot_alertas.py
echo.
if errorlevel 1 (
    echo ERROR: El bot terminó con errores
) else (
    echo Alertas enviadas correctamente
)
echo.
pause
