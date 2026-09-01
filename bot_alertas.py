import os
import re
import time
import glob
import logging
import subprocess
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
    "carpeta_data":         os.path.join(os.getcwd(), "data"),
    "dashboard_html":       os.path.join(os.getcwd(), "data", "dashboard_alertas.html"),
    "grupo_coordinacion":   "Coordinacion",
    "horas_vencimiento":    48,
    "dias_sin_actualizar":  5,
    "top_antiguos":         5,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

FIRMA = "\n━━━━━━━━━━━━━━━━━━━━\n_🤖 Bot desarrollado por el Ing. Javier Trujillo_"


# =========================
# URL DESCARGA CSV
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
def limpiar_cache_driver():
    import shutil
    cache = os.path.join(os.path.expanduser("~"), ".wdm")
    if os.path.exists(cache):
        shutil.rmtree(cache, ignore_errors=True)
        logging.info("🗑️  Caché ChromeDriver limpiado")


def matar_procesos_huerfanos():
    """Cierra chrome.exe/chromedriver.exe que hayan quedado colgados de una corrida
    anterior que crasheo antes de llegar a driver.quit(), para que no bloqueen el
    perfil de WhatsApp en la siguiente corrida."""
    for proceso in ("chromedriver.exe", "chrome.exe"):
        subprocess.run(
            ["taskkill", "/F", "/IM", proceso, "/T"],
            capture_output=True, text=True
        )
    time.sleep(1)


def iniciar_driver():
    limpiar_cache_driver()
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument(f"user-data-dir={CONFIG['perfil_whatsapp']}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-extensions")
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
    WebDriverWait(driver, 20).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    time.sleep(2)
    if "Authentication" not in driver.title and "login" not in driver.current_url.lower():
        logging.info("✅ Sesión GLPI activa")
        return
    logging.info("🔑 Iniciando sesión...")
    try:
        usuario  = CONFIG["usuario"]
        password = CONFIG["password"]
        campo_usuario = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "login_name"))
        )
        time.sleep(1)
        driver.execute_script("arguments[0].value = arguments[1];", campo_usuario, usuario)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", campo_usuario)
        campo_pass = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "login_password"))
        )
        driver.execute_script("arguments[0].value = arguments[1];", campo_pass, password)
        driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles: true}));", campo_pass)
        time.sleep(0.5)
        try:
            btn = driver.find_element(By.XPATH,
                "//button[@type='submit'] | //input[@type='submit'] | //button[contains(text(),'Iniciar')]"
            )
            driver.execute_script("arguments[0].click();", btn)
        except Exception:
            campo_pass.send_keys(Keys.ENTER)
        WebDriverWait(driver, 20).until(
            lambda d: "Authentication" not in d.title and "login" not in d.current_url.lower()
        )
        time.sleep(2)
        logging.info("✅ Login exitoso")
    except Exception as e:
        driver.save_screenshot("error_login_alertas.png")
        raise Exception(f"Error login: {e}")


# =========================
# DESCARGA CSV
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


def descargar_csv(driver, url, nombre):
    logging.info(f"📥 Descargando {nombre}...")
    limpiar_descargas()
    driver.get(url)
    if "Authentication" in driver.title or "login" in driver.current_url.lower():
        login(driver)
        limpiar_descargas()
        driver.get(url)
    archivo = esperar_descarga(timeout=60)
    logging.info(f"✅ {nombre}: {os.path.basename(archivo)}")
    return archivo


# =========================
# LEER Y PARSEAR CSV
# =========================
def leer_csv(archivo, regional):
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

    # Agregar columna regional
    df["Regional"] = regional

    # Parsear fecha vencimiento SLA
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

    for col in ['Fecha de apertura', 'Última modificación']:
        df[col] = pd.to_datetime(df[col], format="%Y-%m-%d %H:%M", errors='coerce')

    df['grupo_limpio'] = df['Asignado a - Grupo técnico'].apply(
        lambda x: str(x).replace("Grupos Activos > ", "").strip() if pd.notna(x) else "Sin grupo"
    )
    df['ID'] = df['ID'].apply(lambda x: str(x).replace(" ", "") if pd.notna(x) else "")

    return df


# =========================
# GUARDAR CSV PARA DASHBOARD
# =========================
def guardar_csv_data(df, regional):
    os.makedirs(CONFIG["carpeta_data"], exist_ok=True)
    hoy = datetime.now().strftime("%Y%m%d")
    ruta = os.path.join(CONFIG["carpeta_data"], f"alertas_{regional.lower()}_{hoy}.csv")
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    logging.info(f"💾 Datos guardados: {os.path.basename(ruta)}")
    return ruta


# =========================
# ANALIZAR ALERTAS
# =========================
def analizar_alertas(df):
    ahora = datetime.now()
    limite_vencimiento   = ahora + timedelta(hours=CONFIG["horas_vencimiento"])
    limite_sin_actualizar = ahora - timedelta(days=CONFIG["dias_sin_actualizar"])

    vencen_pronto = df[
        (df['fecha_vencimiento'].notna()) &
        (df['fecha_vencimiento'] >= ahora) &
        (df['fecha_vencimiento'] <= limite_vencimiento)
    ].copy().sort_values('fecha_vencimiento')

    sin_actualizar = df[
        (df['Última modificación'].notna()) &
        (df['Última modificación'] <= limite_sin_actualizar)
    ].copy()
    sin_actualizar['dias_sin_update'] = (ahora - sin_actualizar['Última modificación']).dt.days
    sin_actualizar = sin_actualizar.sort_values('dias_sin_update', ascending=False)

    df['dias_abierto'] = (ahora - df['Fecha de apertura']).dt.days
    mas_antiguos = df[df['dias_abierto'].notna()].copy().sort_values('dias_abierto', ascending=False)

    return vencen_pronto, sin_actualizar, mas_antiguos


# =========================
# GENERAR MENSAJE WHATSAPP
# =========================
def generar_mensaje(regional, vencen, sin_update, antiguos):
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    msg  = f"⚠️ *ALERTAS GLPI - {regional}*\n"
    msg += f"📅 {ahora}\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n\n"

    # Vencimientos 48h
    msg += f"🚨 *VENCEN EN {CONFIG['horas_vencimiento']}H* ({len(vencen)})\n"
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

    # Sin actualizar
    msg += f"⏰ *SIN ACTUALIZAR +{CONFIG['dias_sin_actualizar']} DÍAS* ({len(sin_update)})\n"
    if sin_update.empty:
        msg += "✅ Todos los tickets actualizados\n"
    else:
        for _, row in sin_update.head(10).iterrows():
            dias    = int(row['dias_sin_update'])
            grupo   = row['grupo_limpio']
            tecnico = str(row.get('Asignado a - Técnico', 'Sin asignar')).strip()
            msg += f"• #{row['ID']} → {dias}d sin mover | {grupo} | {tecnico}\n"

    msg += "\n━━━━━━━━━━━━━━━━━━━━\n"

    # Más antiguos
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

    msg += FIRMA
    return msg


# =========================
# ENVIAR WHATSAPP
# =========================
def enviar_whatsapp(driver, grupo, msg):
    logging.info(f"📲 Enviando a '{grupo}'...")

    # Recargar WhatsApp para asegurar estado limpio
    driver.get("https://web.whatsapp.com")
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "pane-side")))
    time.sleep(3)

    encontrado = False

    # Intento 1: scroll en lista de chats
    lista = driver.find_element(By.ID, "pane-side")
    driver.execute_script("arguments[0].scrollTop = 0", lista)
    time.sleep(0.5)
    for _ in range(50):
        try:
            driver.find_element(By.XPATH, f'//span[@title="{grupo}"]').click()
            encontrado = True
            logging.info(f"  ✅ Grupo encontrado por scroll")
            break
        except Exception:
            driver.execute_script("arguments[0].scrollTop += 150", lista)
            time.sleep(0.1)

    # Intento 2: buscar usando el input de búsqueda directo
    if not encontrado:
        try:
            logging.info("  🔍 Buscando via input de búsqueda...")
            # Clic en el panel lateral para activarlo
            driver.find_element(By.ID, "pane-side").click()
            time.sleep(0.5)
            # Enviar teclas directamente al body para abrir búsqueda
            body = driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.CONTROL, "f")
            time.sleep(1.5)

            # Buscar la caja de búsqueda activa
            caja_busq = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH,
                    '//div[@contenteditable="true"][contains(@class,"copyable-text")][@data-tab="3"] | '
                    '//div[@role="textbox"][@data-tab="3"] | '
                    '//div[@contenteditable="true"][@aria-label="Cuadro de texto de búsqueda"] | '
                    '//div[@contenteditable="true"][@aria-placeholder]'
                ))
            )
            caja_busq.click()
            time.sleep(0.3)
            pyperclip.copy(grupo)
            caja_busq.send_keys(Keys.CONTROL, "v")
            time.sleep(2)

            primeras = grupo[:5]
            resultado = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.XPATH,
                    f'//span[@title="{grupo}"] | //span[contains(@title,"{primeras}")]'
                ))
            )
            resultado.click()
            encontrado = True
            logging.info(f"  ✅ Grupo encontrado por búsqueda")
        except Exception as e:
            logging.warning(f"  ⚠️  Búsqueda fallida: {e}")

    if not encontrado:
        raise Exception(f"Grupo '{grupo}' no encontrado")

    # Enviar mensaje
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
            if not (caja.get_attribute("innerText") or "").strip():
                enviado = True
                break
        except Exception:
            enviado = True
            break

    try:
        driver.save_screenshot(f"confirmacion_{grupo[:10].replace(' ','_')}.png")
    except Exception:
        pass

    if enviado:
        logging.info(f"✅ Enviado a '{grupo}'")
    else:
        logging.warning(f"⚠️  No se confirmó envío a '{grupo}'")

# =========================
# GENERAR DASHBOARD HTML
# =========================
def generar_dashboard(todos_los_datos):
    """Genera dashboard HTML interactivo con todos los datos de las regionales."""
    os.makedirs(CONFIG["carpeta_data"], exist_ok=True)
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    hoy   = datetime.now().strftime("%Y%m%d")

    # Consolidar todos los DataFrames
    df_total = pd.concat(todos_los_datos, ignore_index=True) if todos_los_datos else pd.DataFrame()

    # Preparar datos para el dashboard
    def safe_str(val):
        return str(val) if pd.notna(val) else ""

    rows_vencen = []
    rows_sin_update = []
    rows_antiguos = []

    if not df_total.empty:
        ahora_dt = datetime.now()
        limite_venc = ahora_dt + timedelta(hours=CONFIG["horas_vencimiento"])
        limite_upd  = ahora_dt - timedelta(days=CONFIG["dias_sin_actualizar"])

        # Vencimientos
        vencen = df_total[
            (df_total['fecha_vencimiento'].notna()) &
            (df_total['fecha_vencimiento'] >= ahora_dt) &
            (df_total['fecha_vencimiento'] <= limite_venc)
        ].copy()
        for _, r in vencen.iterrows():
            rows_vencen.append({
                "regional": safe_str(r.get("Regional", "")),
                "id": safe_str(r.get("ID", "")),
                "titulo": safe_str(r.get("Título", ""))[:60],
                "tecnico": safe_str(r.get("Asignado a - Técnico", "Sin asignar")),
                "grupo": safe_str(r.get("grupo_limpio", "")),
                "vence": r['fecha_vencimiento'].strftime("%d/%m/%Y %H:%M") if pd.notna(r.get('fecha_vencimiento')) else "",
                "sla": f"{r['porcentaje_sla']}%" if pd.notna(r.get('porcentaje_sla')) else "",
            })

        # Sin actualizar
        sin_upd = df_total[
            (df_total['Última modificación'].notna()) &
            (df_total['Última modificación'] <= limite_upd)
        ].copy()
        sin_upd['dias'] = (ahora_dt - sin_upd['Última modificación']).dt.days
        for _, r in sin_upd.sort_values('dias', ascending=False).iterrows():
            rows_sin_update.append({
                "regional": safe_str(r.get("Regional", "")),
                "id": safe_str(r.get("ID", "")),
                "titulo": safe_str(r.get("Título", ""))[:60],
                "tecnico": safe_str(r.get("Asignado a - Técnico", "Sin asignar")),
                "grupo": safe_str(r.get("grupo_limpio", "")),
                "dias": int(r['dias']),
                "ultima_mod": r['Última modificación'].strftime("%d/%m/%Y") if pd.notna(r.get('Última modificación')) else "",
            })

        # Más antiguos
        df_total['dias_abierto'] = (ahora_dt - df_total['Fecha de apertura']).dt.days
        ant = df_total[df_total['dias_abierto'].notna()].sort_values('dias_abierto', ascending=False)
        for _, r in ant.head(50).iterrows():
            rows_antiguos.append({
                "regional": safe_str(r.get("Regional", "")),
                "id": safe_str(r.get("ID", "")),
                "titulo": safe_str(r.get("Título", ""))[:60],
                "tecnico": safe_str(r.get("Asignado a - Técnico", "Sin asignar")),
                "grupo": safe_str(r.get("grupo_limpio", "")),
                "dias": int(r['dias_abierto']),
                "apertura": r['Fecha de apertura'].strftime("%d/%m/%Y") if pd.notna(r.get('Fecha de apertura')) else "",
            })

    import json
    data_vencen     = json.dumps(rows_vencen,     ensure_ascii=False)
    data_sin_update = json.dumps(rows_sin_update,  ensure_ascii=False)
    data_antiguos   = json.dumps(rows_antiguos,    ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Alertas GLPI</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; color: #222; }}
  header {{ background: linear-gradient(135deg, #1F3864, #2E75B6); color: white; padding: 20px 32px; display: flex; justify-content: space-between; align-items: center; }}
  header h1 {{ font-size: 22px; }}
  header span {{ font-size: 13px; opacity: 0.85; }}
  .tabs {{ display: flex; background: #1F3864; padding: 0 32px; }}
  .tab {{ padding: 12px 24px; color: rgba(255,255,255,0.7); cursor: pointer; font-size: 14px; border-bottom: 3px solid transparent; transition: all 0.2s; }}
  .tab.active {{ color: white; border-bottom-color: #FFD700; }}
  .tab:hover {{ color: white; }}
  .filters {{ background: white; padding: 14px 32px; display: flex; gap: 12px; flex-wrap: wrap; border-bottom: 1px solid #e0e0e0; }}
  .filters select, .filters input {{ padding: 7px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 13px; }}
  .filters button {{ padding: 7px 18px; background: #2E75B6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; }}
  .filters button:hover {{ background: #1F3864; }}
  .content {{ padding: 24px 32px; }}
  .panel {{ display: none; }}
  .panel.active {{ display: block; }}
  .stats {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat-card {{ background: white; border-radius: 10px; padding: 16px 24px; flex: 1; min-width: 150px; box-shadow: 0 2px 8px rgba(0,0,0,0.07); border-left: 4px solid #2E75B6; }}
  .stat-card.red {{ border-left-color: #e53935; }}
  .stat-card.yellow {{ border-left-color: #f9a825; }}
  .stat-card.green {{ border-left-color: #43a047; }}
  .stat-card h3 {{ font-size: 28px; font-weight: 700; }}
  .stat-card p {{ font-size: 12px; color: #666; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.07); font-size: 13px; }}
  th {{ background: #1F3864; color: white; padding: 12px 14px; text-align: left; font-weight: 600; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #f0f0f0; }}
  tr:hover td {{ background: #f5f8ff; }}
  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }}
  .badge-red {{ background: #fde8e8; color: #c62828; }}
  .badge-yellow {{ background: #fff8e1; color: #f57f17; }}
  .badge-blue {{ background: #e3f0fb; color: #1565c0; }}
  .badge-green {{ background: #e8f5e9; color: #2e7d32; }}
  .no-data {{ text-align: center; padding: 48px; color: #999; font-size: 15px; }}
  footer {{ text-align: center; padding: 20px; color: #888; font-size: 12px; }}
</style>
</head>
<body>

<header>
  <div>
    <h1>🤖 Dashboard Alertas GLPI</h1>
    <div>IT en Sitio — Grupo Éxito</div>
  </div>
  <span>Actualizado: {ahora}</span>
</header>

<div class="tabs">
  <div class="tab active" onclick="showTab('vencen')">🚨 Vencen en {CONFIG['horas_vencimiento']}h</div>
  <div class="tab" onclick="showTab('sin_update')">⏰ Sin actualizar +{CONFIG['dias_sin_actualizar']}d</div>
  <div class="tab" onclick="showTab('antiguos')">📅 Más antiguos</div>
</div>

<div class="filters">
  <select id="filtro-regional" onchange="aplicarFiltros()">
    <option value="">Todas las regionales</option>
    <option>CALI</option><option>MEDELLIN</option><option>COSTA</option><option>BOGOTA</option>
  </select>
  <input id="filtro-texto" type="text" placeholder="Buscar técnico, grupo o ID..." oninput="aplicarFiltros()" style="width:260px">
  <button onclick="limpiarFiltros()">✕ Limpiar</button>
  <button onclick="exportarCSV()">⬇️ Exportar CSV</button>
</div>

<div class="content">

  <!-- PANEL VENCEN -->
  <div class="panel active" id="panel-vencen">
    <div class="stats">
      <div class="stat-card red"><h3 id="cnt-vencen">0</h3><p>Vencen en {CONFIG['horas_vencimiento']}h</p></div>
      <div class="stat-card red"><h3 id="cnt-vencen-cali">0</h3><p>Cali</p></div>
      <div class="stat-card red"><h3 id="cnt-vencen-med">0</h3><p>Medellín</p></div>
      <div class="stat-card red"><h3 id="cnt-vencen-cos">0</h3><p>Costa</p></div>
      <div class="stat-card red"><h3 id="cnt-vencen-bog">0</h3><p>Bogotá</p></div>
    </div>
    <table id="tabla-vencen">
      <thead><tr><th>Regional</th><th>ID</th><th>Título</th><th>Técnico</th><th>Grupo</th><th>Vence</th><th>SLA %</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <!-- PANEL SIN ACTUALIZAR -->
  <div class="panel" id="panel-sin_update">
    <div class="stats">
      <div class="stat-card yellow"><h3 id="cnt-sinupd">0</h3><p>Sin actualizar +{CONFIG['dias_sin_actualizar']}d</p></div>
      <div class="stat-card yellow"><h3 id="cnt-sinupd-cali">0</h3><p>Cali</p></div>
      <div class="stat-card yellow"><h3 id="cnt-sinupd-med">0</h3><p>Medellín</p></div>
      <div class="stat-card yellow"><h3 id="cnt-sinupd-cos">0</h3><p>Costa</p></div>
      <div class="stat-card yellow"><h3 id="cnt-sinupd-bog">0</h3><p>Bogotá</p></div>
    </div>
    <table id="tabla-sin_update">
      <thead><tr><th>Regional</th><th>ID</th><th>Título</th><th>Técnico</th><th>Grupo</th><th>Días sin mover</th><th>Última mod.</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

  <!-- PANEL ANTIGUOS -->
  <div class="panel" id="panel-antiguos">
    <div class="stats">
      <div class="stat-card blue"><h3 id="cnt-ant">0</h3><p>Tickets más antiguos</p></div>
      <div class="stat-card blue"><h3 id="cnt-ant-cali">0</h3><p>Cali</p></div>
      <div class="stat-card blue"><h3 id="cnt-ant-med">0</h3><p>Medellín</p></div>
      <div class="stat-card blue"><h3 id="cnt-ant-cos">0</h3><p>Costa</p></div>
      <div class="stat-card blue"><h3 id="cnt-ant-bog">0</h3><p>Bogotá</p></div>
    </div>
    <table id="tabla-antiguos">
      <thead><tr><th>Regional</th><th>ID</th><th>Título</th><th>Técnico</th><th>Grupo</th><th>Días abierto</th><th>Apertura</th></tr></thead>
      <tbody></tbody>
    </table>
  </div>

</div>

<footer>🤖 Bot desarrollado por el Ing. Javier Trujillo &nbsp;|&nbsp; Generado: {ahora}</footer>

<script>
const DATA = {{
  vencen:     {data_vencen},
  sin_update: {data_sin_update},
  antiguos:   {data_antiguos}
}};

let tabActual = 'vencen';

function showTab(tab) {{
  tabActual = tab;
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + tab).classList.add('active');
  event.target.classList.add('active');
  aplicarFiltros();
}}

function aplicarFiltros() {{
  const regional = document.getElementById('filtro-regional').value.toUpperCase();
  const texto    = document.getElementById('filtro-texto').value.toLowerCase();
  renderTabla(tabActual, regional, texto);
}}

function limpiarFiltros() {{
  document.getElementById('filtro-regional').value = '';
  document.getElementById('filtro-texto').value = '';
  aplicarFiltros();
}}

function filtrar(rows, regional, texto) {{
  return rows.filter(r => {{
    const matchReg = !regional || r.regional.toUpperCase() === regional;
    const matchTxt = !texto || JSON.stringify(r).toLowerCase().includes(texto);
    return matchReg && matchTxt;
  }});
}}

function badgeRegional(r) {{
  const colores = {{CALI:'blue', MEDELLIN:'green', COSTA:'yellow', BOGOTA:'red'}};
  const c = colores[r.toUpperCase()] || 'blue';
  return `<span class="badge badge-${{c}}">${{r}}</span>`;
}}

function renderTabla(tipo, regional, texto) {{
  const rows = filtrar(DATA[tipo], regional, texto);
  const tbody = document.querySelector('#tabla-' + tipo + ' tbody');
  tbody.innerHTML = '';

  if (rows.length === 0) {{
    const cols = tipo === 'vencen' ? 7 : 7;
    tbody.innerHTML = `<tr><td colspan="${{cols}}" class="no-data">✅ Sin registros con los filtros actuales</td></tr>`;
    return;
  }}

  rows.forEach(r => {{
    let fila = '<tr>';
    fila += `<td>${{badgeRegional(r.regional)}}</td>`;
    fila += `<td><b>#${{r.id}}</b></td>`;
    fila += `<td>${{r.titulo}}</td>`;
    fila += `<td>${{r.tecnico}}</td>`;
    fila += `<td>${{r.grupo}}</td>`;
    if (tipo === 'vencen') {{
      const slaNum = parseInt(r.sla) || 0;
      const slaColor = slaNum >= 90 ? 'red' : slaNum >= 70 ? 'yellow' : 'green';
      fila += `<td>⏰ ${{r.vence}}</td>`;
      fila += `<td><span class="badge badge-${{slaColor}}">${{r.sla}}</span></td>`;
    }} else if (tipo === 'sin_update') {{
      const diasColor = r.dias >= 10 ? 'red' : r.dias >= 7 ? 'yellow' : 'blue';
      fila += `<td><span class="badge badge-${{diasColor}}">${{r.dias}} días</span></td>`;
      fila += `<td>${{r.ultima_mod}}</td>`;
    }} else {{
      const diasColor = r.dias >= 30 ? 'red' : r.dias >= 15 ? 'yellow' : 'blue';
      fila += `<td><span class="badge badge-${{diasColor}}">${{r.dias}} días</span></td>`;
      fila += `<td>${{r.apertura}}</td>`;
    }}
    fila += '</tr>';
    tbody.innerHTML += fila;
  }});

  // Actualizar contadores
  actualizarContadores(tipo);
}}

function actualizarContadores(tipo) {{
  const prefijos = {{vencen:'cnt-vencen', sin_update:'cnt-sinupd', antiguos:'cnt-ant'}};
  const pref = prefijos[tipo];
  const todos = DATA[tipo];
  document.getElementById(pref).textContent = todos.length;
  ['CALI','MEDELLIN','COSTA','BOGOTA'].forEach((reg, i) => {{
    const sufijos = ['cali','med','cos','bog'];
    const id = pref + '-' + sufijos[i];
    const elem = document.getElementById(id);
    if (elem) elem.textContent = todos.filter(r => r.regional.toUpperCase() === reg).length;
  }});
}}

function exportarCSV() {{
  const rows = filtrar(DATA[tabActual],
    document.getElementById('filtro-regional').value.toUpperCase(),
    document.getElementById('filtro-texto').value.toLowerCase()
  );
  if (!rows.length) return alert('Sin datos para exportar');
  const keys = Object.keys(rows[0]);
  const csv  = [keys.join(','), ...rows.map(r => keys.map(k => `"${{r[k]}}"`).join(','))].join('\\n');
  const blob = new Blob([csv], {{type:'text/csv;charset=utf-8;'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `alertas_${{tabActual}}_${{new Date().toISOString().slice(0,10)}}.csv`;
  a.click();
}}

// Cargar datos iniciales
renderTabla('vencen', '', '');
actualizarContadores('vencen');
actualizarContadores('sin_update');
actualizarContadores('antiguos');
</script>
</body>
</html>"""

    with open(CONFIG["dashboard_html"], "w", encoding="utf-8") as f:
        f.write(html)
    logging.info(f"📊 Dashboard generado: {CONFIG['dashboard_html']}")


# =========================
# PUBLICAR DASHBOARD EN GITHUB
# =========================
def publicar_dashboard():
    """Copia el dashboard al repositorio BOT-ALERTAS y hace push a GitHub Pages."""
    import shutil
    import subprocess

    repo_dir     = "C:/BOT-ALERTAS"
    origen       = CONFIG["dashboard_html"]
    destino      = os.path.join(repo_dir, "index.html")

    try:
        if not os.path.exists(repo_dir):
            logging.warning("⚠️  Carpeta C:/BOT-ALERTAS no encontrada — omitiendo publicacion")
            return

        # Copiar dashboard al repositorio
        shutil.copy2(origen, destino)
        logging.info(f"📋 Dashboard copiado a {destino}")

        # Git add, commit y push
        subprocess.run(["git", "-C", repo_dir, "add", "index.html"], check=True)
        subprocess.run(["git", "-C", repo_dir, "commit", "-m",
            f"Dashboard actualizado {datetime.now().strftime('%d/%m/%Y %H:%M')}"],
            check=True)
        subprocess.run(["git", "-C", repo_dir, "push"], check=True)
        logging.info("✅ Dashboard publicado en GitHub Pages")
        logging.info("🌐 URL: https://javi544.github.io/BOT-ALERTAS/")

    except subprocess.CalledProcessError as e:
        logging.warning(f"⚠️  Error publicando dashboard: {e}")
    except Exception as e:
        logging.warning(f"⚠️  Error copiando dashboard: {e}")


# =========================
# MAIN
# =========================
def main():
    if not CONFIG["usuario"] or not CONFIG["password"]:
        raise ValueError("❌ Credenciales no definidas en .env")

    os.makedirs(CONFIG["carpeta_data"], exist_ok=True)

    print("\n" + "="*55)
    print("⚠️  BOT ALERTAS GLPI")
    print("="*55)
    print(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"🔔 Vencen en {CONFIG['horas_vencimiento']}h | Sin actualizar >{CONFIG['dias_sin_actualizar']}d | Top {CONFIG['top_antiguos']} antiguos")
    print(f"📊 Dashboard: {CONFIG['dashboard_html']}")
    print("="*55 + "\n")

    matar_procesos_huerfanos()

    driver = None
    todos_los_datos = []

    try:
        driver = iniciar_driver()
        login(driver)

        for r in REGIONALES:
            logging.info(f"\n{'='*50}\n🌎 {r['nombre']}\n{'='*50}")
            try:
                url_csv  = construir_url_csv_cargas(r['filtro'])
                archivo  = descargar_csv(driver, url_csv, f"CARGAS {r['nombre']}")
                df       = leer_csv(archivo, r['nombre'])

                # Guardar CSV para dashboard
                guardar_csv_data(df, r['nombre'])
                todos_los_datos.append(df)

                # Analizar y enviar al grupo regional
                vencen, sin_update, antiguos = analizar_alertas(df)
                msg = generar_mensaje(r['nombre'], vencen, sin_update, antiguos)
                print(f"\n===== ALERTAS {r['nombre']} =====\n{msg}\n")
                enviar_whatsapp(driver, r['grupo_wa'], msg)

            except Exception as e:
                logging.error(f"❌ Error en {r['nombre']}: {e}")
                continue

        # Generar dashboard consolidado de alertas
        generar_dashboard(todos_los_datos)

        # Publicar dashboard alertas en GitHub Pages
        publicar_dashboard()

        # Generar y publicar dashboard de tecnologías
        try:
            from generar_dashboard_tecnologias import main as generar_tec
            logging.info("📊 Generando dashboard de tecnologías...")
            generar_tec()
            logging.info("✅ Dashboard tecnologías publicado")
        except Exception as e:
            logging.warning(f"⚠️  Error generando dashboard tecnologías: {e}")

        # Enviar resumen consolidado a Coordinación
        logging.info(f"\n📲 Enviando resumen a '{CONFIG['grupo_coordinacion']}'...")
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
        total_vencen = sum(
            len(analizar_alertas(df)[0]) for df in todos_los_datos
        )
        total_sinupd = sum(
            len(analizar_alertas(df)[1]) for df in todos_los_datos
        )
        msg_coord  = f"⚠️ *RESUMEN ALERTAS GLPI*\n"
        msg_coord += f"📅 {ahora}\n"
        msg_coord += "━━━━━━━━━━━━━━━━━━━━\n"
        msg_coord += f"🚨 Vencen en {CONFIG['horas_vencimiento']}h: *{total_vencen} tickets*\n"
        msg_coord += f"⏰ Sin actualizar +{CONFIG['dias_sin_actualizar']}d: *{total_sinupd} tickets*\n"
        msg_coord += "━━━━━━━━━━━━━━━━━━━━\n"
        for r in REGIONALES:
            try:
                df_r = next(d for d in todos_los_datos if d['Regional'].iloc[0] == r['nombre'])
                v, s, _ = analizar_alertas(df_r)
                msg_coord += f"🌎 {r['nombre']}: {len(v)} vencen | {len(s)} sin actualizar\n"
            except Exception:
                msg_coord += f"🌎 {r['nombre']}: sin datos\n"
        msg_coord += FIRMA
        enviar_whatsapp(driver, CONFIG['grupo_coordinacion'], msg_coord)

        logging.info("✅ Proceso completado")

    except Exception as e:
        logging.error(f"💥 Error: {e}")
        raise
    finally:
        logging.info("🔒 Cerrando navegador...")
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
