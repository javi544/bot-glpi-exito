@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo ================================================
echo   INSTALADOR DE TAREAS PROGRAMADAS
echo   Sistema de IA - Grupo Exito
echo ================================================
echo.

:: ── CONFIGURACION ────────────────────────────────
set CARPETA=C:\Bot_Incidentes
set PYTHON=C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python314\python.exe
set BAT_ALERTAS=%CARPETA%\ejecutar_alertas_partes.bat
set SCRIPT_IA=%CARPETA%\sistema_ia_exito.py
set LOG=%CARPETA%\log_tareas.txt

:: ── VERIFICACIONES PREVIAS ───────────────────────
echo [1/5] Verificando carpeta C:\Bot_Incidentes...
if not exist "%CARPETA%" (
    echo     CREANDO carpeta %CARPETA%
    mkdir "%CARPETA%"
) else (
    echo     OK - carpeta encontrada
)

echo.
echo [2/5] Verificando Python...
if not exist "%PYTHON%" (
    echo     AVISO: Python no encontrado en ruta por defecto.
    echo     Buscando python en PATH...
    where python >nul 2>&1
    if errorlevel 1 (
        echo     ERROR: Python no encontrado. Instala Python 3.x desde python.org
        pause
        exit /b 1
    ) else (
        set PYTHON=python
        echo     OK - Python encontrado en PATH
    )
) else (
    echo     OK - Python encontrado: %PYTHON%
)

echo.
echo [3/5] Verificando scripts necesarios...
if not exist "%BAT_ALERTAS%" (
    echo     AVISO: ejecutar_alertas_partes.bat no encontrado en %CARPETA%
    echo     Copialo antes de que corran las tareas programadas.
) else (
    echo     OK - ejecutar_alertas_partes.bat encontrado
)
if not exist "%SCRIPT_IA%" (
    echo     AVISO: sistema_ia_exito.py no encontrado en %CARPETA%
    echo     Copialo antes del proximo lunes a las 7:30am.
) else (
    echo     OK - sistema_ia_exito.py encontrado
)

echo.
echo [4/5] Eliminando tareas anteriores (si existen)...
schtasks /delete /tn "GLPI_IA_Manana"         /f >nul 2>&1
schtasks /delete /tn "GLPI_IA_Mediodia"       /f >nul 2>&1
schtasks /delete /tn "GLPI_IA_Cierre"         /f >nul 2>&1
schtasks /delete /tn "GLPI_IA_Reentrenamiento" /f >nul 2>&1
echo     OK - tareas anteriores eliminadas

echo.
echo [5/5] Creando tareas programadas...

:: ── TAREA 1: ALERTA MANANA 8:00 AM ──────────────
schtasks /create ^
  /tn "GLPI_IA_Manana" ^
  /tr "%BAT_ALERTAS%" ^
  /sc WEEKLY ^
  /d MON,TUE,WED,THU,FRI ^
  /st 08:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f ^
  /sd 01/01/2026 >nul 2>&1

if errorlevel 1 (
    echo     ERROR creando GLPI_IA_Manana
) else (
    echo     OK - GLPI_IA_Manana    [Lun-Vie 08:00]
)

:: ── TAREA 2: ALERTA MEDIODIA 12:00 PM ───────────
schtasks /create ^
  /tn "GLPI_IA_Mediodia" ^
  /tr "%BAT_ALERTAS%" ^
  /sc WEEKLY ^
  /d MON,TUE,WED,THU,FRI ^
  /st 12:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f ^
  /sd 01/01/2026 >nul 2>&1

if errorlevel 1 (
    echo     ERROR creando GLPI_IA_Mediodia
) else (
    echo     OK - GLPI_IA_Mediodia  [Lun-Vie 12:00]
)

:: ── TAREA 3: ALERTA CIERRE 5:00 PM ─────────────
schtasks /create ^
  /tn "GLPI_IA_Cierre" ^
  /tr "%BAT_ALERTAS%" ^
  /sc WEEKLY ^
  /d MON,TUE,WED,THU,FRI ^
  /st 17:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f ^
  /sd 01/01/2026 >nul 2>&1

if errorlevel 1 (
    echo     ERROR creando GLPI_IA_Cierre
) else (
    echo     OK - GLPI_IA_Cierre    [Lun-Vie 17:00]
)

:: ── TAREA 4: REENTRENAMIENTO LUNES 7:30 AM ──────
schtasks /create ^
  /tn "GLPI_IA_Reentrenamiento" ^
  /tr "\"%PYTHON%\" \"%SCRIPT_IA%\"" ^
  /sc WEEKLY ^
  /d MON ^
  /st 07:30 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f ^
  /sd 01/01/2026 >nul 2>&1

if errorlevel 1 (
    echo     ERROR creando GLPI_IA_Reentrenamiento
) else (
    echo     OK - GLPI_IA_Reentrenamiento [Lunes 07:30]
)

:: ── RESUMEN FINAL ─────────────────────────────────
echo.
echo ================================================
echo   TAREAS INSTALADAS CORRECTAMENTE
echo ================================================
echo.
echo   Tarea                     Horario
echo   ─────────────────────────────────────────────
echo   GLPI_IA_Reentrenamiento   Lunes 07:30 AM
echo   GLPI_IA_Manana            Lun-Vie 08:00 AM
echo   GLPI_IA_Mediodia          Lun-Vie 12:00 PM
echo   GLPI_IA_Cierre            Lun-Vie 05:00 PM
echo.
echo   Carpeta base: %CARPETA%
echo.
echo   VERIFICAR en: Inicio → Programador de tareas
echo   Buscar carpeta "Task Scheduler Library"
echo   y confirmar que las 4 tareas aparecen activas.
echo.

:: ── VERIFICACION FINAL ────────────────────────────
echo Verificando tareas creadas:
schtasks /query /fo TABLE /nh | findstr "GLPI_IA"
echo.

:: ── LOG ──────────────────────────────────────────
echo [%date% %time%] Tareas instaladas por %USERNAME% >> "%LOG%"

echo IMPORTANTE:
echo   1. Asegurate de que WhatsApp Desktop este ABIERTO
echo      en esta PC cuando corran las tareas.
echo   2. Cada lunes pon el nuevo export de GLPI en:
echo      %CARPETA%\glpi\
echo   3. Cada semana pon el nuevo HR005 en:
echo      %CARPETA%\partes\
echo.
pause
