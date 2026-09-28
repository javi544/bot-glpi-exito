"""
Script standalone para mandar UN mensaje de WhatsApp a un grupo, reusando
la sesion ya autenticada del bot de alertas (perfil_whatsapp). Pensado
para dispararse desde el dashboard (boton "Alertar a Coordinacion"),
no como parte del ciclo completo de bot_alertas.py -- no toca GLPI ni
descarga nada, solo abre WhatsApp Web y manda el mensaje.

USO:
  python enviar_alerta_whatsapp.py <grupo> <ruta_archivo_mensaje>

El mensaje se pasa por archivo (no por argumento de linea de comandos)
para evitar problemas de escapado con acentos, emojis y saltos de linea.
"""
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bot_alertas as bot  # reusa iniciar_driver, enviar_whatsapp, etc.


def main():
    if len(sys.argv) != 3:
        print("USO: python enviar_alerta_whatsapp.py <grupo> <ruta_archivo_mensaje>")
        sys.exit(2)

    grupo = sys.argv[1]
    ruta_msg = sys.argv[2]

    with open(ruta_msg, encoding="utf-8") as f:
        mensaje = f.read()

    if not mensaje.strip():
        print("ERROR: el mensaje esta vacio")
        sys.exit(1)

    bot.matar_procesos_huerfanos()
    driver = None
    try:
        driver = bot.iniciar_driver()
        bot.enviar_whatsapp(driver, grupo, mensaje)
        print(f"OK: mensaje enviado a '{grupo}'")
    except Exception as e:
        print(f"ERROR enviando a '{grupo}': {e}")
        sys.exit(1)
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    main()
