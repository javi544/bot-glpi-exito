@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo ================================================
echo   PILOTO DIARIO - SISTEMA IA GRUPO EXITO
echo   %date% %time%
echo ================================================
echo.

set CARPETA=C:\Bot_Incidentes
set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe
set LOG_PILOTO=%CARPETA%\log_piloto.txt
set LOG_DIARIO=%CARPETA%\reporte_%date:~6,4%%date:~3,2%%date:~0,2%.txt

:: Verificar que python esté disponible
where python >nul 2>&1
if errorlevel 1 (
    if not exist "%PYTHON%" (
        echo ERROR: Python no encontrado
        pause & exit /b 1
    )
) else (
    set PYTHON=python
)

echo Corriendo sistema de IA con datos actuales...
echo Resultado guardado en: %LOG_DIARIO%
echo.

:: Correr el modelo y guardar output
"%PYTHON%" "%CARPETA%\sistema_ia_exito.py" > "%LOG_DIARIO%" 2>&1

if errorlevel 1 (
    echo ERROR al correr el modelo. Revisa %LOG_DIARIO%
    echo [%date% %time%] ERROR en ejecucion >> "%LOG_PILOTO%"
) else (
    echo OK - Modelo corrido exitosamente
    echo [%date% %time%] Ejecucion exitosa >> "%LOG_PILOTO%"
)

echo.
echo ── RESUMEN RAPIDO ──────────────────────────────
findstr /i "En riesgo:\|AUC-ROC\|Stock critico\|CAIDA BRUSCA\|CRITICO\|Tecnico" "%LOG_DIARIO%" | head -20
echo.
echo Reporte completo: %LOG_DIARIO%
echo.

:: Abrir el reporte en el bloc de notas para revision manual
echo Abriendo reporte para validacion manual...
notepad "%LOG_DIARIO%"

echo.
echo ── CHECKLIST DE VALIDACION DIARIA ─────────────
echo.
echo Verifica manualmente en GLPI:
echo   [ ] Los TOP 5 tickets marcados como urgentes
echo       estan realmente sin atencion?
echo   [ ] Las alertas de FRUs criticas coinciden
echo       con lo que sabes de bodega?
echo   [ ] Las alertas de productividad son correctas
echo       o hay tecnicos marcados por error?
echo.
echo Si hay falsos positivos excesivos ajusta en
echo sistema_ia_exito.py:
echo   DIAS_RIESGO = 7         (sube si hay mucho ruido)
echo   META_TICKETS_SEMANA = 15 (baja si la meta es menor)
echo.
echo [%date% %time%] Piloto diario completado >> "%LOG_PILOTO%"
pause
