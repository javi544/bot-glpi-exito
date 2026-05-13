import os
import re
import time
import logging
import pyperclip

from datetime import datetime
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

# Todas las regionales con su grupo de WhatsApp
GRUPOS = [
    {"nombre": "CALI",     "grupo_wa": "IT en sitio Cali"},
    {"nombre": "MEDELLIN", "grupo_wa": "IT en sitio Medellin Toshiba"},
    {"nombre": "COSTA",    "grupo_wa": "IT en sitio Costa"},
    {"nombre": "BOGOTA",   "grupo_wa": "IT en sitio Bogota Toshiba"},
]

CONFIG = {
    "perfil_whatsapp":   os.path.join(os.getcwd(), "perfil_monitor"),
    "registro_txt":      os.path.join(os.getcwd(), "registro_mensajes.txt"),
    "procesados_txt":    os.path.join(os.getcwd(), "mensajes_procesados.txt"),
    "intervalo_scan":    5,   # segundos entre escaneos
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Patrones de acción para productividad
ACCIONES = {
    "cerrado":               "✅ Cerrado",
    "cierre":                "✅ Cerrado",
    "cerrada":               "✅ Cerrado",
    "escalado a partes":     "📤 Escalado a Partes",
    "escalado a aprtes":     "📤 Escalado a Partes",
    "escalado partes":       "📤 Escalado a Partes",
    "escaldo a partes":      "📤 Escalado a Partes",
    "a partes":              "📤 Escalado a Partes",
    "escalado a cotizacion": "📤 Escalado a Cotización",
    "escalado a cotización": "📤 Escalado a Cotización",
    "escalado cotizacion":   "📤 Escalado a Cotización",
    "a cotizacion":          "📤 Escalado a Cotización",
    "a cotización":          "📤 Escalado a Cotización",
    "escalado a especialista": "📤 Escalado a Especialista",
    "escalado especialista":   "📤 Escalado a Especialista",
    "a especialista":          "📤 Escalado a Especialista",
    "escalado a otro grupo": "📤 Escalado a Otro Grupo",
    "otro grupo":            "📤 Escalado a Otro Grupo",
}

# Palabras que indican que es un mensaje de productividad
PALABRAS_PRODUCTIVIDAD = ["sumar", "productividad"]

# Textos que indican que el mensaje es del bot (no procesar)
TEXTOS_BOT = [
    "sumado a productividad",
    "bot glpi",
    "registrado",
    "✅ registrado",
    "cargas activas",
    "cierres hoy",
    "avance regional",
    "detalle por técnico",
    "top del día",
    "alertas glpi",
    "vencen en 24h",
    "sin actualizar",
]

# Set de mensajes ya procesados
mensajes_procesados = set()


# =========================
# PERSISTENCIA
# =========================
def cargar_procesados():
    if os.path.exists(CONFIG["procesados_txt"]):
        with open(CONFIG["procesados_txt"], "r", encoding="utf-8") as f:
            for linea in f:
                mensajes_procesados.add(linea.strip())
    logging.info(f"📂 {len(mensajes_procesados)} mensajes previos cargados")


def guardar_procesado(id_msg):
    mensajes_procesados.add(id_msg)
    with open(CONFIG["procesados_txt"], "a", encoding="utf-8") as f:
        f.write(id_msg + "\n")


def registrar_mensaje(regional, autor, texto, tipo="💬 Mensaje"):
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"{ahora} | {regional} | {autor} | {tipo} | {texto}\n"
    with open(CONFIG["registro_txt"], "a", encoding="utf-8") as f:
        f.write(linea)
    logging.info(f"📝 Registrado [{regional}] {autor}: {texto[:60]}...")


# =========================
# DRIVER
# =========================
def iniciar_driver():
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument(f"user-data-dir={CONFIG['perfil_whatsapp']}")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-extensions")
    options.add_experimental_option("detach", True)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


# =========================
# ABRIR GRUPO
# =========================
def abrir_grupo(driver, grupo_wa):
    driver.get("https://web.whatsapp.com")
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "pane-side")))
    time.sleep(2)

    lista = driver.find_element(By.ID, "pane-side")
    driver.execute_script("arguments[0].scrollTop = 0", lista)

    for _ in range(30):
        try:
            driver.find_element(By.XPATH, f'//span[@title="{grupo_wa}"]').click()
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//footer//div[@contenteditable="true"]'))
            )
            logging.info(f"✅ Grupo abierto: '{grupo_wa}'")
            return True
        except Exception:
            driver.execute_script("arguments[0].scrollTop += 300", lista)
            time.sleep(0.2)

    logging.error(f"❌ No se encontró grupo: '{grupo_wa}'")
    return False


# =========================
# LEER MENSAJES
# =========================
def leer_mensajes(driver):
    """Lee mensajes entrantes del chat actual."""
    mensajes = []
    try:
        filas = driver.find_elements(By.XPATH,
            "//div[contains(@class,'message-in')][@data-pre-plain-text]"
        )
        for fila in filas:
            try:
                pre = fila.get_attribute("data-pre-plain-text") or ""
                match_autor = re.search(r'\] (.+?):\s*$', pre)
                if not match_autor:
                    continue
                autor = match_autor.group(1).strip()

                texto_elems = fila.find_elements(By.XPATH,
                    ".//span[contains(@class,'selectable-text')]"
                )
                if not texto_elems:
                    continue
                texto = texto_elems[0].text.strip()

                if not texto or not autor:
                    continue

                # Ignorar mensajes del bot
                texto_lower = texto.lower()
                if any(t in texto_lower for t in TEXTOS_BOT):
                    continue

                id_unico = f"{autor}|||{texto}"
                if id_unico not in [m["id"] for m in mensajes]:
                    mensajes.append({
                        "texto": texto,
                        "autor": autor,
                        "id":    id_unico,
                    })
            except Exception:
                continue
    except Exception as e:
        logging.warning(f"⚠️  Error leyendo mensajes: {e}")
    return mensajes


# =========================
# DETECTAR PRODUCTIVIDAD
# =========================
def detectar_productividad(texto):
    """
    Si el mensaje contiene palabras de productividad,
    retorna (numero_caso, accion). Si no, retorna (None, None).
    """
    texto_lower = texto.lower()

    if not any(k in texto_lower for k in PALABRAS_PRODUCTIVIDAD):
        return None, None

    match_caso = re.search(r'\b(\d{5,7})\b', texto_lower)
    if not match_caso:
        return None, None

    numero_caso = match_caso.group(1)

    for patron, label in ACCIONES.items():
        if patron in texto_lower:
            return numero_caso, label

    return numero_caso, ACCIONES["cerrado"]


# =========================
# RESPONDER EN WHATSAPP
# =========================
def responder(driver, msg_respuesta):
    try:
        caja = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//footer//div[@contenteditable="true"]'))
        )
        pyperclip.copy(msg_respuesta)
        caja.click()
        time.sleep(0.3)
        caja.send_keys(Keys.CONTROL, 'v')
        time.sleep(0.8)
        try:
            driver.find_element(By.XPATH,
                '//button[@aria-label="Enviar"] | //span[@data-icon="send"]/..'
            ).click()
        except Exception:
            caja.send_keys(Keys.ENTER)
        time.sleep(1)
        logging.info(f"💬 Respuesta enviada: {msg_respuesta[:60]}")
    except Exception as e:
        logging.error(f"❌ Error respondiendo: {e}")


# =========================
# LIMPIAR NOMBRE AUTOR
# =========================
def limpiar_nombre(autor):
    nombre = re.sub(r'^T\s*-\s*', '', autor).strip()
    nombre = re.sub(r'\s*-\s*(Cali|Medellin|Medellín|Costa|Bogota|Bogotá)$', '', nombre, flags=re.IGNORECASE).strip()
    return nombre


# =========================
# PROCESAR MENSAJES
# =========================
def procesar_mensajes(driver, mensajes, regional):
    vistos = set()
    for msg in mensajes:
        if msg["id"] in mensajes_procesados or msg["id"] in vistos:
            continue
        vistos.add(msg["id"])

        texto = msg["texto"]
        autor = msg["autor"]
        nombre = limpiar_nombre(autor)

        # Detectar si es mensaje de productividad
        caso, accion = detectar_productividad(texto)

        if caso and accion:
            # Mensaje de productividad — registrar y responder con detalle
            tipo = f"🏭 Productividad | Caso {caso} | {accion}"
            registrar_mensaje(regional, autor, texto, tipo)
            respuesta = f"✅ Caso {caso} sumado a productividad de {nombre}\n{accion}"
            responder(driver, respuesta)
        else:
            # Cualquier otro mensaje — registrar y responder "Registrado"
            registrar_mensaje(regional, autor, texto, "💬 Mensaje")
            responder(driver, f"✅ Registrado — {nombre}")

        guardar_procesado(msg["id"])


# =========================
# MONITOREAR UN GRUPO
# =========================
def monitorear_grupo(driver, grupo):
    """Escanea los mensajes del grupo actualmente abierto."""
    try:
        mensajes = leer_mensajes(driver)
        pendientes = [m for m in mensajes if m["id"] not in mensajes_procesados]
        if pendientes:
            procesar_mensajes(driver, pendientes, grupo["nombre"])
    except Exception as e:
        logging.warning(f"⚠️  Error escaneando {grupo['nombre']}: {e}")


# =========================
# MAIN
# =========================
def main():
    print("\n" + "="*55)
    print("👀 BOT MONITOR — TODAS LAS REGIONALES")
    print("="*55)
    print("Grupos monitoreados:")
    for g in GRUPOS:
        print(f"  • {g['nombre']}: {g['grupo_wa']}")
    print(f"\nRegistro: {CONFIG['registro_txt']}")
    print("Presiona Ctrl+C para detener")
    print("="*55 + "\n")

    cargar_procesados()

    driver = iniciar_driver()

    try:
        # Abrir WhatsApp y verificar que carga
        driver.get("https://web.whatsapp.com")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "pane-side")))
        logging.info("✅ WhatsApp cargado")
        time.sleep(2)

        # Índice del grupo actual
        idx_grupo = 0

        logging.info("🔄 Iniciando monitoreo rotativo de grupos...")

        while True:
            grupo = GRUPOS[idx_grupo]

            # Abrir el grupo
            if abrir_grupo(driver, grupo["grupo_wa"]):
                time.sleep(1)
                monitorear_grupo(driver, grupo)

            # Rotar al siguiente grupo
            idx_grupo = (idx_grupo + 1) % len(GRUPOS)

            # Pausa entre grupos
            time.sleep(CONFIG["intervalo_scan"])

    except KeyboardInterrupt:
        logging.info("\n⏹️  Monitor detenido por el usuario")
    except Exception as e:
        logging.error(f"💥 Error: {e}")
        raise
    finally:
        logging.info("🔒 Cerrando navegador...")
        driver.quit()


if __name__ == "__main__":
    main()
