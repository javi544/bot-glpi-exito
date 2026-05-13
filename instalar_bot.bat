@echo off
title INSTALADOR BOT GLPI
color 0A
echo.
echo ================================================
echo    INSTALADOR BOT GLPI - IT en Sitio
echo    Grupo Exito
echo ================================================
echo.

:: Verificar que se ejecuta como administrador
net session >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ejecuta este archivo como Administrador
    echo Clic derecho ^> Ejecutar como administrador
    pause
    exit /b 1
)

:: ── PASO 1: Verificar Python ──
echo [1/5] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python no encontrado. Descargando instalador...
    echo.
    echo Abre este link en Chrome y descarga Python 3.11:
    echo https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo.
    echo IMPORTANTE: Durante la instalacion marca
    echo "Add Python to PATH"
    echo.
    start https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
    echo Presiona ENTER cuando Python este instalado...
    pause
    python --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python sigue sin estar instalado.
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('python --version') do echo    ✓ %%i instalado
echo.

:: ── PASO 2: Verificar Chrome ──
echo [2/5] Verificando Google Chrome...
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    echo    ✓ Chrome encontrado
) else if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    echo    ✓ Chrome encontrado
) else (
    echo Chrome no encontrado. Abriendo descarga...
    start https://www.google.com/chrome/
    echo Instala Chrome y presiona ENTER para continuar...
    pause
)
echo.

:: ── PASO 3: Crear carpeta del bot ──
echo [3/5] Creando carpeta C:\Bot_Incidentes...
if not exist "C:\Bot_Incidentes" (
    mkdir "C:\Bot_Incidentes"
    echo    ✓ Carpeta creada
) else (
    echo    ✓ Carpeta ya existe
)
echo.

:: ── PASO 4: Instalar librerias Python ──
echo [4/5] Instalando librerias Python...
echo    Instalando selenium...
pip install selenium --quiet
echo    Instalando webdriver-manager...
pip install webdriver-manager --quiet
echo    Instalando pandas...
pip install pandas --quiet
echo    Instalando pyperclip...
pip install pyperclip --quiet
echo    Instalando python-dotenv...
pip install python-dotenv --quiet
echo    Instalando openpyxl...
pip install openpyxl --quiet
echo    ✓ Todas las librerias instaladas
echo.

:: ── PASO 5: Crear archivo .env si no existe ──
echo [5/5] Configurando credenciales GLPI...
if not exist "C:\Bot_Incidentes\.env" (
    echo Ingresa tus credenciales de GLPI:
    echo.
    set /p GLPI_USER="   Usuario GLPI: "
    set /p GLPI_PASS="   Password GLPI: "
    echo GLPI_USER=%GLPI_USER%> "C:\Bot_Incidentes\.env"
    echo GLPI_PASS=%GLPI_PASS%>> "C:\Bot_Incidentes\.env"
    echo    ✓ Archivo .env creado
) else (
    echo    ✓ Archivo .env ya existe
)
echo.

:: ── PASO 6: Configurar perfil WhatsApp ──
echo ================================================
echo    CONFIGURACION DE WHATSAPP
echo ================================================
echo.
echo Ahora se abrira Chrome con el perfil del bot.
echo Debes escanear el codigo QR con tu celular.
echo.
echo Presiona ENTER para abrir WhatsApp...
pause

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\Bot_Incidentes\perfil_whatsapp" --new-window https://web.whatsapp.com
) else (
    start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\Bot_Incidentes\perfil_whatsapp" --new-window https://web.whatsapp.com
)

echo.
echo Cuando hayas escaneado el QR y veas tus chats,
echo cierra Chrome y presiona ENTER para continuar...
pause
echo.

:: ── PASO 7: Configurar perfil Monitor ──
echo Ahora configuramos el perfil del Bot Monitor.
echo Escanea el QR nuevamente con tu celular.
echo.
echo Presiona ENTER para abrir WhatsApp Monitor...
pause

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\Bot_Incidentes\perfil_monitor" --new-window https://web.whatsapp.com
) else (
    start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\Bot_Incidentes\perfil_monitor" --new-window https://web.whatsapp.com
)

echo.
echo Cuando hayas escaneado el QR y veas tus chats,
echo cierra Chrome y presiona ENTER para continuar...
pause
echo.

:: ── VERIFICACIÓN FINAL ──
echo ================================================
echo    VERIFICACION FINAL
echo ================================================
echo.
python -c "import selenium, pandas, pyperclip, dotenv; print('   Todas las librerias OK')"
if errorlevel 1 (
    echo ERROR: Algunas librerias no se instalaron correctamente
    pause
    exit /b 1
)

echo.
echo ================================================
echo    INSTALACION COMPLETADA EXITOSAMENTE
echo ================================================
echo.
echo Archivos necesarios en C:\Bot_Incidentes\:
echo   - bot_prueba.py      (bot principal)
echo   - bot_alertas.py     (bot de alertas)
echo   - bot_monitor.py     (bot monitor)
echo   - ejecutar_bot.bat   (lanzador principal)
echo   - .env               (ya configurado)
echo.
echo Para correr el bot: doble clic en ejecutar_bot.bat
echo.
pause