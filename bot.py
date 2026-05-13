import os
import time
import glob
import logging
import pyperclip
import pandas as pd

from collections import namedtuple
from datetime import date, datetime
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# =========================
# CONFIG
# =========================
ruta_env = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ruta_env)

REGIONALES = [
    {"nombre": "CALI",     "filtro": "CALI",     "grupo_wa": "IT en sitio Cali",             "meta_regional": 35},
    {"nombre": "MEDELLIN", "filtro": "MEDELLIN",  "grupo_wa": "IT en sitio Medellin Toshiba", "meta_regional": 62},
    {"nombre": "COSTA",    "filtro": "COSTA",     "grupo_wa": "IT en sitio Costa",            "meta_regional": 25},
    {"nombre": "BOGOTA",   "filtro": "BOGOTA",    "grupo_wa": "IT en sitio Bogota Toshiba",   "meta_regional": 62},
]

# Metas personalizadas por técnico (sobreescriben la meta general)
METAS_PERSONALIZADAS = {
    "JOSE DAVID RENDON PEREZ":            8,
    "BRAHIAN FLOREZ OSORNO":             10,
    "SEBASTIAN ENRIQUE MONTALVO BOLIVAR": 10,
}

CONFIG = {
    "url_login":            "https://mservicios.grupo-exito.com",
    "usuario":              os.getenv("GLPI_USER"),
    "password":             os.getenv("GLPI_PASS"),
    "meta_tecnico":         7,
    "perfil_whatsapp":      os.path.join(os.getcwd(), "perfil_whatsapp"),
    "carpeta_descargas":    os.path.join(os.path.expanduser("~"), "Downloads"),
    "savedsearch_cargas":   "1192",
    "savedsearch_cerrados": "1295",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
Tecnico = namedtuple("Tecnico", ["nombre", "asignados", "cerrados", "avance", "icono", "meta"])


# =========================
# CONSTRUIR URLs DE DESCARGA DIRECTA (display_type=-3 = CSV todas las páginas)
# =========================
def construir_url_csv_cargas(filtro):
    """URL directa de descarga CSV cargas — copiada del link 'Todas las páginas en CSV' de GLPI."""
    return (
        "https://mservicios.grupo-exito.com/front/report.dynamic.php"
        "?item_type=Ticket&sort%5B0%5D=19&order%5B0%5D=DESC&start=0"
        "&criteria%5B0%5D%5Blink%5D=AND&criteria%5B0%5D%5Bfield%5D=8"
        "&criteria%5B0%5D%5Bsearchtype%5D=contains&criteria%5B0%5D%5Bvalue%5D=TGCS"
        "&criteria%5B1%5D%5Blink%5D=AND%20NOT"
        "&criteria%5B1%5D%5Bcriteria%5D%5B0%5D%5Blink%5D=AND"
        "&criteria%5B1%5D%5Bcriteria%5D%5B0%5D%5Bfield%5D=8"
        "&criteria%5B1%5D%5Bcriteria%5D%5B0%5D%5Bsearchtype%5D=contains"
        "&criteria%5B1%5D%5Bcriteria%5D%5B0%5D%5Bvalue%5D=MESA"
        "&criteria%5B1%5D%5Bcriteria%5D%5B1%5D%5Blink%5D=OR"
        "&criteria%5B1%5D%5Bcriteria%5D%5B1%5D%5Bfield%5D=8"
        "&criteria%5B1%5D%5Bcriteria%5D%5B1%5D%5Bsearchtype%5D=contains"
        "&criteria%5B1%5D%5Bcriteria%5D%5B1%5D%5Bvalue%5D=ADMUSU"
        "&criteria%5B1%5D%5Bcriteria%5D%5B2%5D%5Blink%5D=OR"
        "&criteria%5B1%5D%5Bcriteria%5D%5B2%5D%5Bfield%5D=8"
        "&criteria%5B1%5D%5Bcriteria%5D%5B2%5D%5Bsearchtype%5D=contains"
        "&criteria%5B1%5D%5Bcriteria%5D%5B2%5D%5Bvalue%5D=SCCM"
        "&criteria%5B2%5D%5Blink%5D=AND%20NOT&criteria%5B2%5D%5Bfield%5D=12"
        "&criteria%5B2%5D%5Bsearchtype%5D=equals&criteria%5B2%5D%5Bvalue%5D=old"
        f"&criteria%5B3%5D%5Blink%5D=AND&criteria%5B3%5D%5Bfield%5D=83"
        f"&criteria%5B3%5D%5Bsearchtype%5D=contains&criteria%5B3%5D%5Bvalue%5D={filtro}"
        "&display_type=-3"
    )


def construir_url_csv_cerrados(filtro):
    """URL directa de descarga CSV cerrados hoy — copiada del link 'Todas las páginas en CSV' de GLPI."""
    return (
        "https://mservicios.grupo-exito.com/front/report.dynamic.php"
        "?item_type=Ticket&sort%5B0%5D=19&order%5B0%5D=DESC&start=0"
        "&criteria%5B0%5D%5Blink%5D=AND&criteria%5B0%5D%5Bfield%5D=8"
        "&criteria%5B0%5D%5Bsearchtype%5D=contains&criteria%5B0%5D%5Bvalue%5D=TGCS"
        "&criteria%5B1%5D%5Blink%5D=AND%20NOT"
        "&criteria%5B1%5D%5Bcriteria%5D%5B0%5D%5Blink%5D=AND"
        "&criteria%5B1%5D%5Bcriteria%5D%5B0%5D%5Bfield%5D=8"
        "&criteria%5B1%5D%5Bcriteria%5D%5B0%5D%5Bsearchtype%5D=contains"
        "&criteria%5B1%5D%5Bcriteria%5D%5B0%5D%5Bvalue%5D=MESA"
        "&criteria%5B1%5D%5Bcriteria%5D%5B1%5D%5Blink%5D=OR"
        "&criteria%5B1%5D%5Bcriteria%5D%5B1%5D%5Bfield%5D=8"
        "&criteria%5B1%5D%5Bcriteria%5D%5B1%5D%5Bsearchtype%5D=contains"
        "&criteria%5B1%5D%5Bcriteria%5D%5B1%5D%5Bvalue%5D=ADMUSU"
        "&criteria%5B1%5D%5Bcriteria%5D%5B2%5D%5Blink%5D=OR"
        "&criteria%5B1%5D%5Bcriteria%5D%5B2%5D%5Bfield%5D=8"
        "&criteria%5B1%5D%5Bcriteria%5D%5B2%5D%5Bsearchtype%5D=contains"
        "&criteria%5B1%5D%5Bcriteria%5D%5B2%5D%5Bvalue%5D=SCCM"
        "&criteria%5B2%5D%5Blink%5D=AND&criteria%5B2%5D%5Bfield%5D=17"
        "&criteria%5B2%5D%5Bsearchtype%5D=equals&criteria%5B2%5D%5Bvalue%5D=TODAY"
        f"&criteria%5B3%5D%5Blink%5D=AND&criteria%5B3%5D%5Bfield%5D=83"
        f"&criteria%5B3%5D%5Bsearchtype%5D=contains&criteria%5B3%5D%5Bvalue%5D={filtro}"
        "&display_type=-3"
    )


# =========================
# DRIVER
# =========================
def iniciar_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument(f"user-data-dir={CONFIG['perfil_whatsapp']}")
    prefs = {
        "download.default_directory": CONFIG["carpeta_descargas"],
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
    }
    options.add_experimental_option("prefs", prefs)
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


# =========================
# LOGIN GLPI
# =========================
def login(driver):
    logging.info("🔐 Entrando a GLPI...")
    driver.get(CONFIG["url_login"])
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    if "Authentication" not in driver.title:
        logging.info("✅ Sesión GLPI activa")
        return
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "login_name"))
    ).send_keys(CONFIG["usuario"])
    driver.find_element(By.ID, "login_password").send_keys(CONFIG["password"] + Keys.ENTER)
    WebDriverWait(driver, 20).until(lambda d: "Authentication" not in d.title)
    logging.info("✅ Login GLPI exitoso")


# =========================
# LIMPIAR DESCARGAS
# =========================
def limpiar_descargas():
    for f in glob.glob(os.path.join(CONFIG["carpeta_descargas"], "*.csv")):
        try:
            os.remove(f)
        except Exception:
            pass


# =========================
# ESPERAR DESCARGA CSV
# =========================
def esperar_descarga(timeout=60):
    carpeta = CONFIG["carpeta_descargas"]
    inicio = time.time()
    while time.time() - inicio < timeout:
        archivos = glob.glob(os.path.join(carpeta, "*.csv"))
        archivos = [a for a in archivos if not a.endswith(".crdownload")]
        if archivos:
            archivo = max(archivos, key=os.path.getmtime)
            time.sleep(0.5)
            logging.info(f"✅ Descarga detectada: {os.path.basename(archivo)}")
            return archivo
        time.sleep(0.5)
    raise TimeoutError(f"No se descargó ningún CSV en {timeout}s")


# =========================
# DESCARGAR CSV DIRECTO
# =========================
def descargar_csv(driver, url_csv, nombre):
    """
    Navega directamente a la URL de descarga CSV (report.dynamic.php con display_type=-3).
    No requiere interacción con menús — descarga automáticamente.
    """
    logging.info(f"📥 Descargando {nombre}...")
    limpiar_descargas()
    driver.get(url_csv)
    archivo = esperar_descarga(timeout=60)
    logging.info(f"✅ {nombre}: {os.path.basename(archivo)}")
    return archivo


# =========================
# LEER CSV
# =========================
def leer_csv(archivo, nombre):
    logging.info(f"📂 Leyendo {nombre}...")
    df = None
    for encoding in ["utf-8-sig", "utf-8", "latin-1"]:
        try:
            tmp = pd.read_csv(archivo, sep=";", encoding=encoding, on_bad_lines='skip')
            if len(tmp.columns) > 1:
                df = tmp
                break
        except Exception:
            continue

    if df is None or df.empty:
        raise ValueError(f"No se pudo leer {archivo}")

    logging.info(f"  Filas: {len(df)}")

    col_tecnico = None
    for col in df.columns:
        col_up = str(col).upper()
        if ("TÉCNICO" in col_up or "TECNICO" in col_up) and "GRUPO" not in col_up:
            col_tecnico = col
            break

    if col_tecnico is None:
        raise ValueError(f"Columna técnico no encontrada. Columnas: {list(df.columns)}")

    total_tickets = len(df)
    data = {}
    for v in df[col_tecnico].dropna():
        t = str(v).strip().upper()
        if t and t not in ("NAN", ""):
            data[t] = data.get(t, 0) + 1

    sin_tecnico = total_tickets - sum(data.values())
    logging.info(f"✅ {nombre}: {len(data)} técnicos | {sum(data.values())} asignados | {sin_tecnico} sin técnico | {total_tickets} total")

    data["__total__"] = total_tickets
    os.remove(archivo)
    return data


# =========================
# PROCESAR
# =========================
def procesar(asignados, cerrados):
    meta_base = CONFIG["meta_tecnico"]
    resultado = []
    tecnicos = (set(asignados) | set(cerrados)) - {"__total__"}
    for nombre in tecnicos:
        a = asignados.get(nombre, 0)
        c = cerrados.get(nombre, 0)
        # Usar meta personalizada si existe, si no la meta general
        meta = METAS_PERSONALIZADAS.get(nombre, meta_base)
        avance = min((c / meta) * 100, 100) if meta else 0
        icono = "🟢" if c >= meta else "🟡" if c >= meta * 0.5 else "🔴"
        resultado.append(Tecnico(nombre, a, c, avance, icono, meta))
    resultado.sort(key=lambda x: x.avance, reverse=True)
    return resultado


# =========================
# MENSAJE
# =========================
def generar_mensaje(regional, meta_regional, asignados, cerrados, data, modo):
    hoy           = date.today().strftime("%d/%m/%Y")
    meta_t        = CONFIG["meta_tecnico"]
    total_cargas  = asignados.get("__total__", sum(v for k,v in asignados.items() if k != "__total__"))
    total_cierres = cerrados.get("__total__", sum(v for k,v in cerrados.items() if k != "__total__"))

    msg  = f"🤖 *BOT GLPI - {regional}*\n"
    msg += f"📅 {hoy}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += "📋 *Resumen Regional*\n"
    msg += f"📥 Cargas activas: *{total_cargas}*\n"
    msg += f"🎯 Meta del día:   *{meta_regional} cierres*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"

    if modo == "manana":
        msg += "👤 *Cargas por Técnico*\n\n"
        for t in sorted(data, key=lambda x: x.asignados, reverse=True):
            msg += f"📌 {t.nombre}: {t.asignados} tickets\n"
    else:
        avance  = min((total_cierres / meta_regional) * 100, 100) if meta_regional else 0
        icono_r = "🟢" if avance >= 100 else "🟡" if avance >= 50 else "🔴"
        msg += f"✅ Cierres hoy:    *{total_cierres}/{meta_regional}*\n"
        msg += f"{icono_r} Avance regional: *{avance:.0f}%*\n"
        msg += "━━━━━━━━━━━━━━━━━━━━\n"
        msg += f"👤 *Detalle por Técnico* (meta: {meta_t})\n\n"
        for t in data:
            cumple = "✅ Cumple" if t.cerrados >= t.meta else "❌ No cumple"
            msg += f"{t.icono} {t.nombre}: {t.avance:.0f}% ({t.cerrados}/{t.meta}) {cumple}\n"
        top = max(data, key=lambda t: t.cerrados) if data else None
        if top and top.cerrados > 0:
            msg += f"\n🏆 *Top del día:* {top.nombre} ({top.cerrados} cierres)\n"

    return msg


# =========================
# ENVIAR WHATSAPP
# =========================
def enviar_whatsapp(driver, grupo, msg):
    logging.info(f"📲 Enviando a '{grupo}'...")

    driver.get("https://web.whatsapp.com")
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "pane-side")))

    lista = driver.find_element(By.ID, "pane-side")
    driver.execute_script("arguments[0].scrollTop = 0", lista)
    time.sleep(0.5)

    encontrado = False
    for _ in range(30):
        try:
            driver.find_element(By.XPATH, f'//span[@title="{grupo}"]').click()
            encontrado = True
            break
        except Exception:
            driver.execute_script("arguments[0].scrollTop += 300", lista)
            time.sleep(0.2)

    if not encontrado:
        palabras = " ".join(grupo.split()[:3])
        driver.execute_script("arguments[0].scrollTop = 0", lista)
        for _ in range(30):
            try:
                driver.find_element(By.XPATH, f'//span[contains(@title,"{palabras}")]').click()
                encontrado = True
                break
            except Exception:
                driver.execute_script("arguments[0].scrollTop += 300", lista)
                time.sleep(0.2)

    if not encontrado:
        raise Exception(f"Grupo '{grupo}' no encontrado")

    caja = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, '//footer//div[@contenteditable="true"]'))
    )

    huella = msg.strip().split("\n")[0].replace("*", "").strip()
    enviado = False

    for intento in range(1, 4):
        logging.info(f"  📤 Intento {intento}...")
        pyperclip.copy(msg)
        caja.click()
        time.sleep(0.5)
        caja.send_keys(Keys.CONTROL, 'a')
        time.sleep(0.2)
        caja.send_keys(Keys.CONTROL, 'v')
        time.sleep(1.5)

        texto_caja = caja.get_attribute("innerText") or ""
        if not texto_caja.strip():
            logging.warning(f"  ⚠️  Caja vacía en intento {intento}")
            time.sleep(1)
            continue

        try:
            driver.find_element(By.XPATH,
                '//button[@aria-label="Enviar"] | //span[@data-icon="send"]/..'
            ).click()
        except Exception:
            caja.send_keys(Keys.ENTER)

        # Esperar 2 segundos y verificar que la caja quedó vacía (señal de envío exitoso)
        time.sleep(2)
        try:
            texto_despues = caja.get_attribute("innerText") or ""
            if not texto_despues.strip():
                logging.info(f"  ✅ Caja vacía — mensaje enviado (intento {intento})")
                enviado = True
                break
            else:
                logging.warning(f"  ⚠️  Caja aún tiene texto (intento {intento})")
                time.sleep(1)
        except Exception:
            # Si la caja no existe, probablemente se envió y el foco cambió
            enviado = True
            break

    try:
        driver.save_screenshot(f"confirmacion_{grupo[:10].replace(' ','_')}.png")
    except Exception:
        pass  # screenshot opcional, no bloquear el proceso

    if enviado:
        logging.info(f"✅ Mensaje enviado a '{grupo}'")
    else:
        logging.warning(f"⚠️  No se confirmó envío a '{grupo}' — continuando de todas formas")


# =========================
# MAIN
# =========================
def main():
    if not CONFIG["usuario"] or not CONFIG["password"]:
        raise ValueError("❌ Credenciales no definidas en .env")

    hora_actual = datetime.now().hour + datetime.now().minute / 60
    modo = "manana" if 7.0 <= hora_actual < 9.0 else "seguimiento"

    print("\n" + "="*55)
    print("🤖 BOT GLPI - TODAS LAS REGIONALES")
    print("="*55)
    print(f"{'☀️  Modo: MAÑANA' if modo == 'manana' else '📊 Modo: SEGUIMIENTO'} ({datetime.now().strftime('%H:%M')})")
    print(f"Regionales: {', '.join(r['nombre'] for r in REGIONALES)}")
    print("="*55 + "\n")

    driver = iniciar_driver()
    try:
        login(driver)

        errores = []

        for r in REGIONALES:
            logging.info(f"\n{'='*50}\n🌎 {r['nombre']} (meta: {r['meta_regional']})\n{'='*50}")

            try:
                # Descargar y leer CARGAS
                archivo_cargas = descargar_csv(driver, construir_url_csv_cargas(r['filtro']), f"CARGAS {r['nombre']}")
                asignados = leer_csv(archivo_cargas, f"CARGAS {r['nombre']}")

                # Descargar y leer CERRADOS (con manejo de regional sin cierres)
                cerrados = {}
                if modo == "seguimiento":
                    try:
                        archivo_cerrados = descargar_csv(driver, construir_url_csv_cerrados(r['filtro']), f"CERRADOS {r['nombre']}")
                        cerrados = leer_csv(archivo_cerrados, f"CERRADOS {r['nombre']}")
                    except Exception as e_cerrados:
                        logging.warning(f"⚠️  {r['nombre']}: sin datos de cerrados — se envía con cierres en 0 | {e_cerrados}")
                        cerrados = {}

                data = procesar(asignados, cerrados)
                msg  = generar_mensaje(r['nombre'], r['meta_regional'], asignados, cerrados, data, modo)

                print(f"\n===== {r['nombre']} =====\n{msg}")
                enviar_whatsapp(driver, r['grupo_wa'], msg)

            except Exception as e_regional:
                logging.error(f"❌ Error en regional {r['nombre']}: {e_regional}")
                errores.append(r['nombre'])
                logging.info(f"⏭️  Continuando con la siguiente regional...")
                continue

        if errores:
            logging.warning(f"\n⚠️  Regionales con error: {', '.join(errores)}")
        logging.info("\n✅ Proceso completado para todas las regionales")

    except Exception as e:
        logging.error(f"💥 Error: {e}")
        raise
    finally:
        logging.info("🔒 Cerrando navegador...")
        driver.quit()


if __name__ == "__main__":
    main()
