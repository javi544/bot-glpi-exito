import os
import re
import time
import glob
import logging
import pyperclip
import pandas as pd

from datetime import datetime, timedelta
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
    {"nombre": "CALI",     "filtro": "CALI",     "grupo_wa": "IT en sitio Cali"},
    {"nombre": "MEDELLIN", "filtro": "MEDELLIN",  "grupo_wa": "IT en sitio Medellin Toshiba"},
    {"nombre": "COSTA",    "filtro": "COSTA",     "grupo_wa": "IT en sitio Costa"},
    {"nombre": "BOGOTA",   "filtro": "BOGOTA",    "grupo_wa": "IT en sitio Bogota Toshiba"},
]

CONFIG = {
    "url_login":            "https://mservicios.grupo-exito.com",
    "usuario":              os.getenv("GLPI_USER"),
    "password":             os.getenv("GLPI_PASS"),
    "perfil_whatsapp":      os.path.join(os.getcwd(), "perfil_whatsapp"),
    "carpeta_descargas":    os.path.join(os.path.expanduser("~"), "Downloads"),
    "savedsearch_cargas":   "1192",
    "dias_sin_actualizar":  5,      # días sin modificación para alertar
    "horas_vencimiento":    24,     # horas hacia adelante para alertar vencimiento
    "top_antiguos":         5,      # top N tickets más antiguos por grupo
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")


# =========================
# URL DESCARGA CSV CARGAS
# =========================
def construir_url_csv_cargas(filtro):
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
# LOGIN
# =========================
def login(driver):
    logging.info("🔐 Entrando a GLPI...")
    driver.get(CONFIG["url_login"])
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    if "Authentication" not in driver.title:
        logging.info("✅ Sesión activa")
        return
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "login_name"))
    ).send_keys(CONFIG["usuario"])
    driver.find_element(By.ID, "login_password").send_keys(CONFIG["password"] + Keys.ENTER)
    WebDriverWait(driver, 20).until(lambda d: "Authentication" not in d.title)
    logging.info("✅ Login exitoso")


# =========================
# LIMPIAR Y ESPERAR DESCARGA
# =========================
def limpiar_descargas():
    for f in glob.glob(os.path.join(CONFIG["carpeta_descargas"], "*.csv")):
        try:
            os.remove(f)
        except Exception:
            pass

def esperar_descarga(timeout=60):
    carpeta = CONFIG["carpeta_descargas"]
    inicio = time.time()
    while time.time() - inicio < timeout:
        archivos = glob.glob(os.path.join(carpeta, "*.csv"))
        archivos = [a for a in archivos if not a.endswith(".crdownload")]
        if archivos:
            archivo = max(archivos, key=os.path.getmtime)
            time.sleep(0.5)
            return archivo
        time.sleep(0.5)
    raise TimeoutError("No se descargó ningún CSV")


# =========================
# DESCARGAR CSV
# =========================
def descargar_csv(driver, url, nombre):
    logging.info(f"📥 Descargando {nombre}...")
    limpiar_descargas()
    driver.get(url)
    archivo = esperar_descarga(timeout=60)
    logging.info(f"✅ {nombre}: {os.path.basename(archivo)}")
    return archivo


# =========================
# LEER Y PARSEAR CSV
# =========================
def leer_csv(archivo):
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

    os.remove(archivo)

    # Parsear fecha de vencimiento SLA desde "Tiempo en resolver + Progreso"
    # Formato: "2026-04-23 14:30 \n\n 85%"
    def extraer_fecha_vencimiento(valor):
        if pd.isna(valor):
            return None
        match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', str(valor))
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")
            except Exception:
                return None
        return None

    def extraer_porcentaje(valor):
        if pd.isna(valor):
            return None
        match = re.search(r'(\d+)%', str(valor))
        return int(match.group(1)) if match else None

    df['fecha_vencimiento'] = df['Tiempo en resolver + Progreso'].apply(extraer_fecha_vencimiento)
    df['porcentaje_sla']    = df['Tiempo en resolver + Progreso'].apply(extraer_porcentaje)

    # Parsear fechas
    for col in ['Fecha de apertura', 'Última modificación']:
        df[col] = pd.to_datetime(df[col], format="%Y-%m-%d %H:%M", errors='coerce')

    # Limpiar nombre de grupo técnico
    df['grupo_limpio'] = df['Asignado a - Grupo técnico'].apply(
        lambda x: str(x).replace("Grupos Activos > ", "").strip() if pd.notna(x) else "Sin grupo"
    )

    # Limpiar ID
    df['ID'] = df['ID'].apply(lambda x: str(x).replace(" ", "") if pd.notna(x) else "")

    return df


# =========================
# ANALIZAR ALERTAS
# =========================
def analizar_alertas(df, nombre_regional):
    ahora = datetime.now()
    limite_vencimiento = ahora + timedelta(hours=CONFIG["horas_vencimiento"])
    limite_sin_actualizar = ahora - timedelta(days=CONFIG["dias_sin_actualizar"])

    # ── ALERTA 1: Vencen en próximas 24 horas ──
    vencen_pronto = df[
        (df['fecha_vencimiento'].notna()) &
        (df['fecha_vencimiento'] >= ahora) &
        (df['fecha_vencimiento'] <= limite_vencimiento)
    ].copy()
    vencen_pronto = vencen_pronto.sort_values('fecha_vencimiento')

    # ── ALERTA 2: Sin actualizar hace más de 5 días ──
    sin_actualizar = df[
        (df['Última modificación'].notna()) &
        (df['Última modificación'] <= limite_sin_actualizar)
    ].copy()
    sin_actualizar['dias_sin_update'] = (ahora - sin_actualizar['Última modificación']).dt.days
    sin_actualizar = sin_actualizar.sort_values('dias_sin_update', ascending=False)

    # ── ALERTA 3: Más antiguos por grupo ──
    df['dias_abierto'] = (ahora - df['Fecha de apertura']).dt.days
    mas_antiguos = df[df['dias_abierto'].notna()].copy()
    mas_antiguos = mas_antiguos.sort_values('dias_abierto', ascending=False)

    logging.info(f"  📊 {nombre_regional}: {len(vencen_pronto)} vencen pronto | {len(sin_actualizar)} sin actualizar | {len(df)} total")

    return vencen_pronto, sin_actualizar, mas_antiguos


# =========================
# GENERAR MENSAJE DE ALERTAS
# =========================
def generar_mensaje_alertas(regional, vencen, sin_update, antiguos):
    ahora = datetime.now()
    hoy   = ahora.strftime("%d/%m/%Y %H:%M")

    msg  = f"⚠️ *ALERTAS GLPI - {regional}*\n"
    msg += f"📅 {hoy}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # ALERTA 1: Vencimientos
    msg += f"🚨 *VENCEN EN 24H* ({len(vencen)})\n"
    if vencen.empty:
        msg += "✅ Sin tickets próximos a vencer\n"
    else:
        for _, row in vencen.head(10).iterrows():
            tecnico = str(row.get('Asignado a - Técnico', 'Sin asignar')).strip()
            fecha   = row['fecha_vencimiento'].strftime("%d/%m %H:%M")
            pct     = row['porcentaje_sla']
            pct_str = f" {pct}%" if pct else ""
            msg += f"• #{row['ID']} → {fecha}{pct_str} | {tecnico}\n"

    msg += "\n━━━━━━━━━━━━━━━━━━━━\n"

    # ALERTA 2: Sin actualizar
    msg += f"⏰ *SIN ACTUALIZAR +{CONFIG['dias_sin_actualizar']} DÍAS* ({len(sin_update)})\n"
    if sin_update.empty:
        msg += "✅ Todos los tickets actualizados\n"
    else:
        for _, row in sin_update.head(10).iterrows():
            dias   = int(row['dias_sin_update'])
            grupo  = row['grupo_limpio']
            tecnico = str(row.get('Asignado a - Técnico', 'Sin asignar')).strip()
            msg += f"• #{row['ID']} → {dias}d sin mover | {grupo} | {tecnico}\n"

    msg += "\n━━━━━━━━━━━━━━━━━━━━\n"

    # ALERTA 3: Más antiguos por grupo
    msg += f"📅 *TOP {CONFIG['top_antiguos']} MÁS ANTIGUOS POR GRUPO*\n"
    grupos = antiguos['grupo_limpio'].unique()
    for grupo in sorted(grupos):
        tickets_grupo = antiguos[antiguos['grupo_limpio'] == grupo].head(CONFIG['top_antiguos'])
        if tickets_grupo.empty:
            continue
        msg += f"\n_{grupo}_\n"
        for _, row in tickets_grupo.iterrows():
            dias    = int(row['dias_abierto']) if pd.notna(row['dias_abierto']) else 0
            tecnico = str(row.get('Asignado a - Técnico', 'Sin asignar')).strip()
            msg += f"• #{row['ID']} → {dias}d | {tecnico}\n"

    return msg


# =========================
# ENVIAR WHATSAPP
# =========================
def enviar_whatsapp(driver, grupo, msg):
    logging.info(f"📲 Enviando alertas a '{grupo}'...")

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

    enviado = False
    for intento in range(1, 4):
        pyperclip.copy(msg)
        caja.click()
        time.sleep(0.5)
        caja.send_keys(Keys.CONTROL, 'a')
        time.sleep(0.2)
        caja.send_keys(Keys.CONTROL, 'v')
        time.sleep(1.5)

        texto_caja = caja.get_attribute("innerText") or ""
        if not texto_caja.strip():
            logging.warning(f"  ⚠️  Caja vacía intento {intento}")
            time.sleep(1)
            continue

        try:
            driver.find_element(By.XPATH,
                '//button[@aria-label="Enviar"] | //span[@data-icon="send"]/..'
            ).click()
        except Exception:
            caja.send_keys(Keys.ENTER)

        time.sleep(2)
        try:
            texto_despues = caja.get_attribute("innerText") or ""
            if not texto_despues.strip():
                enviado = True
                break
        except Exception:
            enviado = True
            break

    try:
        driver.save_screenshot(f"alerta_{grupo[:10].replace(' ','_')}.png")
    except Exception:
        pass

    if enviado:
        logging.info(f"✅ Alertas enviadas a '{grupo}'")
    else:
        logging.warning(f"⚠️  No se confirmó envío a '{grupo}' — continuando")


# =========================
# MAIN
# =========================
def main():
    if not CONFIG["usuario"] or not CONFIG["password"]:
        raise ValueError("❌ Credenciales no definidas en .env")

    print("\n" + "="*55)
    print("⚠️  BOT ALERTAS GLPI - TODAS LAS REGIONALES")
    print("="*55)
    print(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"🔔 Alertas: vencen en {CONFIG['horas_vencimiento']}h | sin actualizar >{CONFIG['dias_sin_actualizar']} días | top {CONFIG['top_antiguos']} antiguos")
    print("="*55 + "\n")

    driver = iniciar_driver()
    try:
        login(driver)

        for r in REGIONALES:
            logging.info(f"\n{'='*50}\n🌎 {r['nombre']}\n{'='*50}")

            # Descargar CSV de cargas
            url_csv = construir_url_csv_cargas(r['filtro'])
            archivo = descargar_csv(driver, url_csv, f"CARGAS {r['nombre']}")

            # Leer y analizar
            df = leer_csv(archivo)
            vencen, sin_update, antiguos = analizar_alertas(df, r['nombre'])

            # Generar y mostrar mensaje
            msg = generar_mensaje_alertas(r['nombre'], vencen, sin_update, antiguos)
            print(f"\n===== ALERTAS {r['nombre']} =====\n{msg}")

            # Enviar a WhatsApp
            enviar_whatsapp(driver, r['grupo_wa'], msg)

        logging.info("\n✅ Alertas enviadas a todas las regionales")

    except Exception as e:
        logging.error(f"💥 Error: {e}")
        raise
    finally:
        logging.info("🔒 Cerrando navegador...")
        driver.quit()


if __name__ == "__main__":
    main()
