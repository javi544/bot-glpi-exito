"""
╔══════════════════════════════════════════════════════════════╗
║   SISTEMA INTEGRAL DE IA — GRUPO ÉXITO                      ║
║   Entrenado con datos reales GLPI + Toshiba HR005           ║
║   49.904 tickets | Enero 2025 - Mayo 2026                   ║
╚══════════════════════════════════════════════════════════════╝

ARCHIVOS NECESARIOS (misma carpeta):
  - data__2_.xlsx              (o el nombre de tu export GLPI)
  - Toshiba_HR005_-_FECHA.xlsx

USO:
  pip install scikit-learn pandas numpy openpyxl
  python sistema_ia_exito.py
"""

import pandas as pd
import numpy as np
import glob, os, warnings
from datetime import datetime
warnings.filterwarnings("ignore")
try:
    import joblib
    JOBLIB_OK = True
except ImportError:
    JOBLIB_OK = False

# ════════════════════════════════════════════════════════════════
# CONFIGURACION
# ════════════════════════════════════════════════════════════════
# Rutas de archivos — ajusta si cambias de carpeta
CARPETA_BASE    = r"C:\Bot_Incidentes"                          # carpeta raiz del proyecto
CARPETA_GLPI    = os.path.join(CARPETA_BASE, "glpi")            # C:\Bot_Incidentes\glpi\
CARPETA_PARTES  = os.path.join(CARPETA_BASE, "partes")          # C:\Bot_Incidentes\partes\
CARPETA_ALERTAS = os.path.join(CARPETA_BASE, "data")            # misma carpeta que alimenta el bot de alertas
REGIONALES_ALERTAS = ["CALI", "MEDELLIN", "COSTA", "BOGOTA"]

# El script busca el Excel mas reciente en CARPETA_GLPI automaticamente
# Si quieres apuntar a un archivo fijo usa: ARCHIVO_GLPI = r"C:\...\archivo.xlsx"
ARCHIVO_GLPI   = None          # None = buscar automatico en CARPETA_GLPI
HOJA_GLPI      = "Export"      # nombre de la hoja en el Excel de GLPI
META_TICKETS_SEMANA = 15
STOCK_CRITICO       = 0
STOCK_BAJO          = 2

# Reentrenamiento del Modulo 1 (Gradient Boosting - tickets en riesgo)
FORZAR_REENTRENAMIENTO = False   # True = ignora el modelo guardado y reentrena siempre
DIAS_MAX_MODELO_M1     = 7       # reentrena automaticamente si el modelo guardado es mas viejo que esto

def archivo_mas_reciente(*patrones):
    """Devuelve la ruta del archivo mas reciente (por fecha de modificacion)
    entre los que matcheen alguno de los patrones glob dados. El orden por
    nombre de archivo no es confiable (ej. 'data.xlsx' vs 'data (2).xlsx')."""
    archivos = [a for patron in patrones for a in glob.glob(patron)]
    if not archivos:
        return None
    return max(archivos, key=os.path.getmtime)

def transformar_seguro(label_encoder, valores):
    """Aplica un LabelEncoder ya entrenado sobre valores nuevos, sin explotar
    si aparece una categoria que el encoder no vio en su momento (le asigna
    -1 en vez de lanzar ValueError)."""
    mapa = {clase: codigo for codigo, clase in enumerate(label_encoder.classes_)}
    return valores.astype(str).fillna("Sin dato").map(mapa).fillna(-1).astype(int)

def ids_backlog_alertas(carpeta):
    """IDs de tickets en el backlog actual que ya reporta el bot de alertas
    de WhatsApp (union del snapshot mas reciente por regional). El modelo
    se sigue entrenando con el historico completo de GLPI (necesita
    volumen para aprender bien), pero las predicciones que se exportan al
    dashboard se restringen a esta misma poblacion -- para ser consistente
    con lo que el equipo ya ve por WhatsApp, en vez de todo el universo de
    tickets activos de GLPI (que incluye grupos que el bot excluye
    explicitamente, como MESA/ADMUSU/SCCM)."""
    ids = set()
    for regional in REGIONALES_ALERTAS:
        archivos = glob.glob(os.path.join(carpeta, f"alertas_{regional.lower()}_*.csv"))
        if not archivos:
            continue
        archivo = max(archivos, key=os.path.getmtime)
        try:
            d = pd.read_csv(archivo, encoding="utf-8-sig")
            ids.update(d["ID"].astype(str).str.strip())
        except Exception as e:
            print(f"  AVISO: no se pudo leer {archivo} para el backlog de alertas: {e}")
    return ids

# Tecnicos a excluir del analisis de productividad
# (personal administrativo, coordinadores, o perfiles sin tickets de campo)
# Agrega o quita nombres segun tu operacion
TECNICOS_EXCLUIR = [
    "Alejandro Aristizabal Maldonado",
    "Alexander Cano Gutierrez",
    "Ana Maria Garcia Orrego",
    "Adriana Maria Correa Marin",
    "Arturo Rafael Cochero Lambis",
    "John Fredy Florez Franco",
    "Edwin Augusto Kammerer Orcasita",
    "Brian NIcolas Cardozo Cabrera",
    "Carlos David Casas Martinez",
    "Alexandra Quintanilla Ortiz",
    "Wilson Andres Viveros Melo",
    "Yuris Paola Alvarado Martinez",
    "Liliana Villa",
    "Sebastian Conde",
    "Pedro Pablo Portillo Mayoriano",
    "Harby Jhoan Gonzalez Jambo",
    "Jhonnier Andres Salcedo Correa",
    "LWY ALONSO MESA ARCILA",
]

BODEGA_REGIONAL = {
    "COBOG01": "Bogota",
    "COMED02": "Medellin",
    "CLSCL01": "Chile",
    "COCLO02": "Cali",
    "COBAQ02": "Costa",
}

MAPA_REGIONAL = {
    "Reg. Bogotá":     "Bogota",
    "Reg. Bogota":      "Bogota",
    "Regional Bogota":  "Bogota",
    "Reg. Cali":        "Cali",
    "Regional Cali":    "Cali",
    "Reg. Medellín":   "Medellin",
    "Reg. Medellin":    "Medellin",
    "Reg. Costa":       "Costa",
}

def seccion(titulo):
    print(f"\n{'='*65}")
    print(f"  {titulo}")
    print(f"{'='*65}")

print("=" * 65)
print("  SISTEMA INTEGRAL DE IA - GRUPO EXITO")
print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print("=" * 65)

# ════════════════════════════════════════════════════════════════
# MODULO A: CARGA GLPI
# ════════════════════════════════════════════════════════════════
seccion("MODULO A: CARGA DE DATOS GLPI")

# Crear carpetas si no existen
os.makedirs(CARPETA_GLPI,   exist_ok=True)
os.makedirs(CARPETA_PARTES, exist_ok=True)

# Buscar el Excel mas reciente en CARPETA_GLPI (por fecha real, no por nombre)
if ARCHIVO_GLPI is None:
    archivo_glpi = archivo_mas_reciente(
        os.path.join(CARPETA_GLPI, "*.xlsx"),
        os.path.join(CARPETA_GLPI, "*.xls"))
    if archivo_glpi is None:
        print(f"  ERROR: No se encontro ningun Excel en {CARPETA_GLPI}")
        print(f"  Coloca el export de GLPI en: {CARPETA_GLPI}")
        exit(1)
    ruta_glpi = archivo_glpi
else:
    ruta_glpi = ARCHIVO_GLPI
    archivo_glpi = ARCHIVO_GLPI

try:
    df = pd.read_excel(ruta_glpi, sheet_name=HOJA_GLPI)
    df.columns = [c.strip() for c in df.columns]
    print(f"  OK: {len(df):,} tickets cargados")
    print(f"  Archivo: {os.path.basename(ruta_glpi)}")
except FileNotFoundError:
    print(f"  ERROR: No se encontro '{ruta_glpi}'")
    print(f"  Coloca el export de GLPI en: {CARPETA_GLPI}")
    exit(1)

hoy = pd.Timestamp.today()

# Fechas -- algunos exports de GLPI vienen sin ciertas columnas de fecha
# (ej. un export configurado distinto no trae "Fecha Cierre"). Se crean
# vacias en vez de crashear todo el script por una columna faltante.
for _col_fecha in ["Fecha Apertura", "Fecha Cierre", "Fecha Icumplimiento"]:
    if _col_fecha not in df.columns:
        df[_col_fecha] = pd.NaT
        print(f"  AVISO: el export no trae la columna '{_col_fecha}', se deja vacia")
    df[_col_fecha] = pd.to_datetime(df[_col_fecha], errors="coerce")

df["dias_abierto"]  = (df["Fecha Cierre"].fillna(hoy) - df["Fecha Apertura"]).dt.days.clip(0)
df["mes_apertura"]  = df["Fecha Apertura"].dt.month
df["hora_apertura"] = df["Fecha Apertura"].dt.hour

# Regional normalizada
df["regional"] = df["Regional"].astype(str).str.strip()
for src, dst in MAPA_REGIONAL.items():
    df["regional"] = df["regional"].str.replace(src, dst, regex=False)

# Variables base
df["sla_excedido"]  = (df["Cumplimiento"].astype(str).str.strip().str.upper() == "NO").astype(int)
df["es_incidente"]  = (df["Tipo"].astype(str).str.strip() == "Incidente").astype(int)

# ── FEATURES NUEVAS PARA MODULO 1 ──────────────────────────────
# Ultima actividad conocida: max(Fecha Solucion, Fecha Icumplimiento)
df["Fecha Solucion"]  = pd.to_datetime(df["Fecha Solución"],        errors="coerce") if "Fecha Solución" in df.columns else pd.NaT
df["ultima_actividad"] = df[["Fecha Solucion","Fecha Icumplimiento"]].max(axis=1).fillna(df["Fecha Apertura"])
df["dias_sin_actividad"] = (hoy - df["ultima_actividad"]).dt.days.clip(0)

# Ventana SLA: dias entre apertura y fecha de incumplimiento (urgencia del ticket)
df["ventana_sla_dias"] = (df["Fecha Icumplimiento"] - df["Fecha Apertura"]).dt.days.fillna(0).clip(0)

# Prioridad codificada numericamente
MAPA_PRIORIDAD = {
    "Muy Urgente": 5, "Alta": 4, "Mediana": 3,
    "Baja": 2, "Muy Baja": 1
}
df["prioridad_num"] = df["Prioridad"].astype(str).str.strip().map(MAPA_PRIORIDAD).fillna(1).astype(int)

# Es ticket de alta prioridad (Alta o Muy Urgente)
df["es_alta_prioridad"] = (df["prioridad_num"] >= 4).astype(int)

# Tiene numero de dependencia asignada (proxy de si el ticket tiene ubicacion definida)
df["tiene_dependencia"] = df["# Dependencia"].notna().astype(int) if "# Dependencia" in df.columns else 0

# Dia de la semana de apertura (0=lunes, 6=domingo)
df["dia_semana"] = df["Fecha Apertura"].dt.dayofweek.fillna(0).astype(int)
df["abierto_activo"]= df["Estado"].astype(str).isin(
    ["En curso (asignada)", "En curso (planificada)", "En espera"])
df["en_riesgo"]     = (
    (df["Dias Abiertos"].astype(str).str.strip() == "mas de 10") &
    df["abierto_activo"]
).astype(int) if "Dias Abiertos" in df.columns else (
    (df["Días Abiertos"].astype(str).str.strip() == "mas de 10") &
    df["abierto_activo"]
).astype(int)

# Productividad — semanas activas por tecnico (antiguedad real de CADA UNO,
# no el promedio de todo el historial del dataset). Con el calculo anterior,
# un tecnico nuevo con pocas semanas en el equipo salia con "baja
# productividad" solo por dividir su total entre ~78 semanas de historial
# que no le corresponden.
df["tecnico"] = df["Asignatario"].astype(str).str.strip()
tec_primera_fecha = df.groupby("tecnico")["Fecha Apertura"].min().rename("primera_fecha")
tec_vol = df.groupby("tecnico").size().reset_index(name="total_tec").merge(
    tec_primera_fecha, on="tecnico")
tec_vol["semanas_activo"] = ((hoy - tec_vol["primera_fecha"]).dt.days // 7).clip(lower=1)
tec_vol["tickets_semana"] = (tec_vol["total_tec"] / tec_vol["semanas_activo"]).round(2)
df = df.merge(tec_vol[["tecnico","total_tec","tickets_semana"]], on="tecnico", how="left")
df["baja_productividad"] = (df["tickets_semana"] < META_TICKETS_SEMANA).astype(int)

# Excluir tecnicos administrativos o sin tickets de campo
df["es_tecnico_campo"] = ~df["tecnico"].isin(TECNICOS_EXCLUIR)
print(f"  Tecnicos de campo:  {df[df['es_tecnico_campo']]['tecnico'].nunique()} (excluidos {len(TECNICOS_EXCLUIR)} perfiles administrativos)")

semanas_historial = max(1, (hoy - df["Fecha Apertura"].min()).days // 7)
print(f"  Rango:              {df['Fecha Apertura'].min().date()} a {df['Fecha Apertura'].max().date()}")
print(f"  Semanas historial:  {semanas_historial}")
print(f"  Tecnicos unicos:    {df['tecnico'].nunique()}")
print(f"  En riesgo:          {df['en_riesgo'].sum():>6} ({df['en_riesgo'].mean()*100:.1f}%)")
print(f"  SLA excedido:       {df['sla_excedido'].sum():>6} ({df['sla_excedido'].mean()*100:.1f}%)")
print(f"  Baja productividad: {df['baja_productividad'].sum():>6} ({df['baja_productividad'].mean()*100:.1f}%)")

print(f"\n  {'Regional':<14} {'Tickets':>8} {'SLA Exc':>8} {'%':>6}")
print("  " + "-"*40)
for reg in ["Bogota","Medellin","Cali","Costa"]:
    sub = df[df["regional"] == reg]
    if len(sub) == 0: continue
    print(f"  {reg:<14} {len(sub):>8,} {sub['sla_excedido'].sum():>8,} {sub['sla_excedido'].mean()*100:>5.1f}%")

# ════════════════════════════════════════════════════════════════
# MODULO B: PARTES HR005
# ════════════════════════════════════════════════════════════════
seccion("MODULO B: INVENTARIO DE PARTES (HR005)")

df_partes = None
archivos_hr = sorted(glob.glob(os.path.join(CARPETA_PARTES, "Toshiba*HR005*.xlsx")), reverse=True)
if archivos_hr:
    df_partes = pd.read_excel(archivos_hr[0])
    df_partes["regional"] = df_partes["Warehouse Code"].map(BODEGA_REGIONAL).fillna("Otra")
    df_partes["alerta"]   = "OK"
    df_partes.loc[df_partes["Total On Hand Qty"] <= STOCK_BAJO,    "alerta"] = "BAJO"
    df_partes.loc[df_partes["Total On Hand Qty"] == STOCK_CRITICO, "alerta"] = "CRITICO"
    print(f"  OK: {len(df_partes):,} partes | {os.path.basename(archivos_hr[0])}")
    print(f"  Stock critico (=0):  {(df_partes['alerta']=='CRITICO').sum()}")
    print(f"  Stock bajo (1-{STOCK_BAJO}):   {(df_partes['alerta']=='BAJO').sum()}")
else:
    print("  AVISO: No se encontro HR005 - modulo 2 desactivado.")

# ════════════════════════════════════════════════════════════════
# PREPROCESAMIENTO
# ════════════════════════════════════════════════════════════════
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

encoders_actuales = {}
for col_orig, col_enc, clave in [("regional","regional_enc","regional"), ("CI","ci_enc","ci"),
                                  ("tecnico","tecnico_enc","tecnico"), ("Grupo","grupo_enc","grupo")]:
    le = LabelEncoder()
    df[col_enc] = le.fit_transform(df[col_orig].astype(str).fillna("Sin dato"))
    encoders_actuales[clave] = le

# Crear df_campo DESPUES de los encodings para heredar todas las columnas
df_campo = df[df["es_tecnico_campo"]].copy()

def entrenar(X, y, modelo, lbl_pos, lbl_neg):
    if y.nunique() < 2:
        print(f"  AVISO: solo una clase presente - ajusta umbrales.")
        return None
    if y.sum() < 10:
        print(f"  AVISO: muy pocos positivos ({y.sum()}) - exporta mas historial.")
        return None
    X_tr, X_te, y_tr, y_te = train_test_split(
        X.fillna(0), y, test_size=0.25, random_state=42, stratify=y)
    modelo.fit(X_tr, y_tr)
    y_pred = modelo.predict(X_te)
    auc    = roc_auc_score(y_te, modelo.predict_proba(X_te)[:,1])
    print(f"\n  AUC-ROC: {auc:.4f}")
    print(classification_report(y_te, y_pred, target_names=[lbl_neg, lbl_pos], digits=3))
    return modelo

# ════════════════════════════════════════════════════════════════
# MODULO 1: TICKETS EN RIESGO — Gradient Boosting
# ════════════════════════════════════════════════════════════════
seccion("MODULO 1: PREDICCION DE TICKETS EN RIESGO (Gradient Boosting)")
from sklearn.ensemble import GradientBoostingClassifier

FEAT1 = [
    "dias_abierto",         # dias desde apertura
    "dias_sin_actividad",   # dias desde ultima accion en el ticket (NUEVO)
    "ventana_sla_dias",     # urgencia del SLA asignado (NUEVO)
    "prioridad_num",        # prioridad numerica 1-5 (NUEVO)
    "es_alta_prioridad",    # flag Alta/Muy Urgente (NUEVO)
    "tiene_dependencia",    # tiene ubicacion definida (NUEVO)
    "dia_semana",           # dia de semana de apertura (NUEVO)
    "sla_excedido",
    "es_incidente",
    "mes_apertura",
    "hora_apertura",
    "regional_enc",
    "ci_enc",
    "grupo_enc",
    "tecnico_enc",
]

CARPETA_MODELOS = os.path.join(CARPETA_BASE, "modelos")
os.makedirs(CARPETA_MODELOS, exist_ok=True)
RUTA_M1 = os.path.join(CARPETA_MODELOS, "m1_tickets_riesgo.joblib")

_guardar = GUARDAR_MODELOS if 'GUARDAR_MODELOS' in dir() else True
_jlib    = JOBLIB_OK if 'JOBLIB_OK' in dir() else False
_modelo_viejo = os.path.exists(RUTA_M1) and (
    (datetime.now().timestamp() - os.path.getmtime(RUTA_M1)) > DIAS_MAX_MODELO_M1 * 86400
)

# X1: features de M1 a usar para predecir. Por defecto las de este mismo run
# (regional_enc/ci_enc/etc recien calculadas). Si se carga el modelo cacheado,
# se reemplazan por versiones codificadas con LOS MISMOS encoders con que se
# entreno ese modelo — evita que "regional=Bogota" cambie de numero de un
# run a otro y el modelo interprete mal los datos (train/serve skew).
X1 = df[FEAT1].copy()

m1 = None
m1_cargado = False
_usar_cache = _jlib and os.path.exists(RUTA_M1) and not FORZAR_REENTRENAMIENTO and not _modelo_viejo

if _usar_cache:
    try:
        bundle = joblib.load(RUTA_M1)
        m1 = bundle["modelo"]
        enc_m1 = bundle["encoders"]
        X1["regional_enc"] = transformar_seguro(enc_m1["regional"], df["regional"])
        X1["ci_enc"]       = transformar_seguro(enc_m1["ci"], df["CI"])
        X1["tecnico_enc"]  = transformar_seguro(enc_m1["tecnico"], df["tecnico"])
        X1["grupo_enc"]    = transformar_seguro(enc_m1["grupo"], df["Grupo"])
        m1_cargado = True
        print(f"  Modelo M1 cargado desde disco (sin re-entrenar, encoders originales)")
    except Exception as e:
        print(f"  AVISO: modelo M1 guardado no es compatible ({e}), reentrenando...")
        m1_cargado = False

if not m1_cargado:
    m1 = entrenar(
        X1, df["en_riesgo"],
        GradientBoostingClassifier(n_estimators=200, learning_rate=0.1,
                                   max_depth=4, subsample=0.8, random_state=42),
        "En Riesgo", "OK"
    )
    if m1 and _jlib and _guardar:
        joblib.dump({"modelo": m1, "encoders": encoders_actuales}, RUTA_M1)
        print(f"  Modelo M1 guardado en disco (con encoders)")

if m1:
    if hasattr(m1, 'feature_importances_'):
        imp1 = pd.Series(m1.feature_importances_, index=FEAT1).sort_values(ascending=False)
        print("  Importancia de variables:")
        for feat, imp in imp1.items():
            barra = "I" * int(imp * 40)
            print(f"    {feat:<22} {barra} {imp:.3f}")

    df["prob_riesgo"] = m1.predict_proba(X1[FEAT1].fillna(0))[:,1]
    activos = df[df["abierto_activo"]]
    if len(activos) > 0:
        print(f"\n  TOP 15 TICKETS ACTIVOS MAS URGENTES:")
        print(f"  {'Ticket':<10} {'Regional':<12} {'CI':<22} {'Dias':>5} {'SLA':>4} {'Prob':>6}")
        print("  " + "-"*62)
        for _, r in activos.nlargest(15, "prob_riesgo").iterrows():
            sla = "NO" if r["sla_excedido"] else "SI"
            print(f"  #{str(r['Tiquete']):<9} {str(r['regional']):<12} "
                  f"{str(r['CI'])[:20]:<22} {r['dias_abierto']:>5} "
                  f"{sla:>4} {r['prob_riesgo']:>6.0%}")

# ════════════════════════════════════════════════════════════════
# MODULO 2: DESABASTECIMIENTO — Random Forest (HR005)
# ════════════════════════════════════════════════════════════════
seccion("MODULO 2: PREDICCION DE DESABASTECIMIENTO (Random Forest)")
from sklearn.ensemble import RandomForestClassifier

if df_partes is not None:
    le_bod = LabelEncoder()
    df_partes["bodega_enc"]   = le_bod.fit_transform(df_partes["Warehouse Code"].astype(str))
    df_partes["necesita_repo"]= (df_partes["Total On Hand Qty"] <= STOCK_BAJO).astype(int)

    FEAT2 = ["Total On Hand Qty","Total ATP Qty","Total Allocated Qty",
             "Total Open PO Qty","bodega_enc"]
    m2 = entrenar(
        df_partes[FEAT2], df_partes["necesita_repo"],
        RandomForestClassifier(n_estimators=150, class_weight="balanced",
                               max_depth=6, random_state=42, n_jobs=-1),
        "Necesita Repo", "OK"
    )
    if m2:
        imp2 = pd.Series(m2.feature_importances_, index=FEAT2).sort_values(ascending=False)
        print("  Importancia de variables:")
        for feat, imp in imp2.items():
            barra = "I" * int(imp * 40)
            print(f"    {feat:<30} {barra} {imp:.3f}")

    print(f"\n  ESTADO DE STOCK POR BODEGA:")
    print(f"  {'Regional':<12} {'Bodega':<10} {'Total':>6} {'Cero':>6} {'Bajo':>6} {'Con PO':>7}")
    print("  " + "-"*50)
    for bodega, reg in BODEGA_REGIONAL.items():
        sub = df_partes[df_partes["Warehouse Code"] == bodega]
        if len(sub) == 0: continue
        ceros = (sub["Total On Hand Qty"] == 0).sum()
        bajos = ((sub["Total On Hand Qty"] > 0) & (sub["Total On Hand Qty"] <= STOCK_BAJO)).sum()
        con_po= ((sub["Total On Hand Qty"] == 0) & (sub["Total Open PO Qty"] > 0)).sum()
        alerta = "CRITICO" if ceros > 20 else "BAJO" if ceros > 0 else "OK"
        print(f"  [{alerta:<7}] {reg:<10} {bodega:<10} {len(sub):>6} {ceros:>6} {bajos:>6} {con_po:>7}")
else:
    print("  Sin datos HR005. Agrega el archivo y vuelve a correr.")
    m2 = None

# ════════════════════════════════════════════════════════════════
# MODULO 3: BAJA PRODUCTIVIDAD — SVM RBF
# ════════════════════════════════════════════════════════════════
seccion("MODULO 3: DETECCION DE BAJA PRODUCTIVIDAD (SVM RBF)")
from sklearn.svm import SVC
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEAT3 = ["tickets_semana","sla_excedido","es_incidente",
         "regional_enc","ci_enc","grupo_enc"]

m3 = entrenar(
    df_campo[FEAT3], df_campo["baja_productividad"],
    Pipeline([
        ("sc",  StandardScaler()),
        ("svm", SVC(kernel="rbf", C=1.5, gamma="scale",
                    probability=True, class_weight="balanced", random_state=42))
    ]),
    "Baja Productividad", "Productivo"
)

if m3:
    df_campo["prob_baja_prod"] = m3.predict_proba(df_campo[FEAT3].fillna(0))[:,1]
    tec_stats = df_campo.groupby("tecnico").agg(
        regional   =("regional",        "first"),
        tix_sem    =("tickets_semana",  "mean"),
        sla_exc    =("sla_excedido",    "sum"),
        total_tix  =("Tiquete",         "count"),
        prob_media =("prob_baja_prod",  "mean"),
    ).sort_values("prob_media", ascending=False)

    print(f"\n  TECNICOS DE CAMPO CON MAYOR RIESGO (excluye perfiles administrativos):")
    print(f"  {'Tecnico':<35} {'Regional':<12} {'Tix/sem':>8} {'SLA Exc':>8} {'Riesgo':>7}")
    print("  " + "-"*74)
    for tec, r in tec_stats.head(15).iterrows():
        nivel = "ALTO " if r["prob_media"] > 0.7 else "MEDIO" if r["prob_media"] > 0.4 else "OK   "
        print(f"  [{nivel}] {str(tec)[:33]:<35} {str(r['regional']):<12} "
              f"{r['tix_sem']:>8.1f} {r['sla_exc']:>8} {r['prob_media']:>7.0%}")

    # Ranking completo: top productivos también
    print(f"\n  TOP 10 TECNICOS MAS PRODUCTIVOS:")
    print(f"  {'Tecnico':<35} {'Regional':<12} {'Tix/sem':>8} {'Total':>7} {'Riesgo':>7}")
    print("  " + "-"*74)
    for tec, r in tec_stats.sort_values("tix_sem", ascending=False).head(10).iterrows():
        print(f"  [OK   ] {str(tec)[:33]:<35} {str(r['regional']):<12} "
              f"{r['tix_sem']:>8.1f} {r['total_tix']:>7} {r['prob_media']:>7.0%}")

# ════════════════════════════════════════════════════════════════
# MODULO 4: STOPPERS NLP — TF-IDF + K-Means sobre Asuntos reales
# ════════════════════════════════════════════════════════════════
seccion("MODULO 4: STOPPERS RECURRENTES - NLP (TF-IDF + K-Means)")
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD

corpus = df["Asunto"].astype(str).fillna("sin descripcion").tolist()
print(f"  Corpus: {len(corpus):,} asuntos reales de tickets GLPI")

vectorizer = TfidfVectorizer(max_features=300, ngram_range=(1,2),
                             min_df=5, max_df=0.85, strip_accents="unicode")
X4  = vectorizer.fit_transform(corpus)
svd = TruncatedSVD(n_components=15, random_state=42)
X4r = svd.fit_transform(X4)

N_CLUSTERS = 6
kmeans    = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=15)
etiquetas = kmeans.fit_predict(X4r)
df["cluster_stopper"] = etiquetas

feature_names = vectorizer.get_feature_names_out()
print(f"\n  {'Cluster':>8} {'Casos':>8} {'%':>6}  Top terminos clave")
print("  " + "-"*72)
conteo = pd.Series(etiquetas).value_counts().sort_index()
for cid in range(N_CLUSTERS):
    cnt  = conteo.get(cid, 0)
    pct  = cnt / len(etiquetas) * 100
    centro_tfidf = svd.inverse_transform(kmeans.cluster_centers_[[cid]])[0]
    top_idx   = centro_tfidf.argsort()[::-1][:5]
    top_terms = " | ".join(feature_names[top_idx])
    print(f"  {cid:>8} {cnt:>8,} {pct:>5.1f}%  {top_terms}")

print(f"\n  Stoppers por regional:")
pivot = pd.crosstab(df["regional"], df["cluster_stopper"],
                    margins=True, margins_name="Total")
print(pivot.to_string())


# Guardar modelos m2 y m3 si existen
if _jlib and _guardar:
    try:
        if m2 is not None:
            joblib.dump(m2, os.path.join(CARPETA_MODELOS, "m2_desabastecimiento.joblib"))
        if m3 is not None:
            joblib.dump(m3, os.path.join(CARPETA_MODELOS, "m3_productividad.joblib"))
        print(f"\n  Modelos M2/M3 guardados en disco")
    except Exception as e_save:
        print(f"  Aviso al guardar modelos: {e_save}")

# ════════════════════════════════════════════════════════════════
# ANALISIS COMPLEMENTARIO 1: SLA POR GRUPO OPERATIVO
# ════════════════════════════════════════════════════════════════
seccion("ANALISIS DE GRUPOS OPERATIVOS — SLA POR GRUPO")

MAPA_GRUPO = {
    "TGCS - Tecnologia No POS":      "Tecnologia No POS",
    "TGCS - Tecnologia POS":         "Tecnologia POS",
    "TGCS-TRANSPORTE":               "Transporte",
    "TGCS-Laboratorio":              "Laboratorio",
    "TGCS-PARTES":                   "Partes",
    "TGCS-GARANTIAS":                "Garantias",
    "TGCS - ClicCafe":               "ClicCafe",
    "TGCS - Call dispacher  no pos": "Call Dispatcher No POS",
    "TGCS- Call dispacher pos":      "Call Dispatcher POS",
    "TGCS - BogOficinas  80 Sitio":  "Bog Oficinas",
    "TGCS-COTIZACIONES":             "Cotizaciones",
}
df["grupo_simple"] = df["Grupo"].astype(str).map(MAPA_GRUPO).fillna(df["Grupo"])

sla_grupo = df.groupby("grupo_simple").agg(
    tickets=("Tiquete","count"),
    sla_exc=("sla_excedido","sum")
).assign(pct_inc=lambda x: (x["sla_exc"]/x["tickets"]*100).round(1)).sort_values("pct_inc",ascending=False)

print(f"\n  {'Grupo':<30} {'Tickets':>8} {'SLA Exc':>8} {'% Incumpl':>10}  Estado")
print("  " + "-"*70)
for grupo, r in sla_grupo.iterrows():
    if r["pct_inc"] >= 70:  estado = "CRITICO"
    elif r["pct_inc"] >= 30: estado = "ALTO   "
    elif r["pct_inc"] >= 15: estado = "MEDIO  "
    else:                    estado = "OK     "
    print(f"  {str(grupo):<30} {r['tickets']:>8,} {r['sla_exc']:>8,} {r['pct_inc']:>9.1f}%  [{estado}]")

# ════════════════════════════════════════════════════════════════
# ANALISIS COMPLEMENTARIO 2: FRUs CRITICAS EN DESABASTECIMIENTO
# ════════════════════════════════════════════════════════════════
seccion("FRUs CRITICAS EN DESABASTECIMIENTO (Stock = 0)")

if df_partes is not None:
    BODEGA_NOMBRE = {
        "COBOG01": "Bogota",
        "COMED02": "Medellin",
        "COCLO02": "Cali",
        "COBAQ02": "Costa",
        "CLSCL01": "Chile",
    }
    frus_cero = df_partes[df_partes["Total On Hand Qty"] == 0].copy()
    frus_cero["regional"] = frus_cero["Warehouse Code"].map(BODEGA_NOMBRE).fillna("Otra")
    frus_cero = frus_cero.sort_values("Total Open PO Qty", ascending=False)

    print(f"\n  Total FRUs con stock = 0: {len(frus_cero)}")
    print("\n  TOP 20 FRUs CRITICAS (ordenadas por PO abierta):")
    print(f"  {'Regional':<10} {'Bodega':<10} {'Part Number':<14} {'Descripcion':<40} {'PO':>6}")
    print("  " + "-"*84)
    for _, r in frus_cero.head(20).iterrows():
        desc = str(r["Part Description"])[:38]
        print(f"  {r['regional']:<10} {r['Warehouse Code']:<10} {r['Part Number']:<14} {desc:<40} {int(r['Total Open PO Qty']):>6}")

    print("\n  RESUMEN POR BODEGA:")
    print(f"  {'Regional':<12} {'Bodega':<10} {'FRUs Cero':>10} {'Stock Bajo':>11} {'Con PO':>7}")
    print("  " + "-"*54)
    for bodega, reg in {"COBOG01":"Bogota","COMED02":"Medellin","COCLO02":"Cali","COBAQ02":"Costa","CLSCL01":"Chile"}.items():
        sub = df_partes[df_partes["Warehouse Code"] == bodega]
        if len(sub) == 0: continue
        ceros  = (sub["Total On Hand Qty"] == 0).sum()
        bajos  = ((sub["Total On Hand Qty"] > 0) & (sub["Total On Hand Qty"] <= STOCK_BAJO)).sum()
        con_po = ((sub["Total On Hand Qty"] == 0) & (sub["Total Open PO Qty"] > 0)).sum()
        alerta = "CRITICO" if ceros > 20 else "BAJO" if ceros > 0 else "OK"
        print(f"  [{alerta:<7}] {reg:<10} {bodega:<10} {ceros:>10} {bajos:>11} {con_po:>7}")
else:
    print("  Sin datos HR005 disponibles.")

# ════════════════════════════════════════════════════════════════
# ANALISIS COMPLEMENTARIO 3: PRODUCTIVIDAD MENSUAL POR TECNICO
# ════════════════════════════════════════════════════════════════
seccion("PRODUCTIVIDAD MENSUAL POR TECNICO Y REGIONAL")

df["mes"] = df["Fecha Apertura"].dt.to_period("M")
meses_disponibles = sorted(df["mes"].dropna().unique())
ultimos6 = meses_disponibles[-6:]
print(f"  Periodos analizados: {[str(m) for m in ultimos6]}")

# Solo tecnicos de campo
df_campo_mes = df_campo.copy()
df_campo_mes["mes"] = df["mes"]

prod_mensual = df_campo_mes.groupby(["tecnico","regional","mes"]).size().unstack(fill_value=0)
prod_mensual.columns = [str(c) for c in prod_mensual.columns]
cols6 = [str(m) for m in ultimos6 if str(m) in prod_mensual.columns]
prod6 = prod_mensual[cols6].copy()
prod6["Total"] = prod6.sum(axis=1)
prod6 = prod6[prod6["Total"] > 0].sort_values("Total", ascending=False)

# Encabezados amigables
meses_labels = {str(m): m.strftime("%b-%y").capitalize() for m in ultimos6}
cols_mostrar = cols6 + ["Total"]

print("\n  TOP 25 TECNICOS — TICKETS POR MES:")
header = f"  {'Tecnico':<35} {'Regional':<12}"
for c in cols6:
    header += f" {meses_labels.get(c,c):>7}"
header += f" {'Total':>7}"
print(header)
print("  " + "-"*(35+12+len(cols6)*8+8+4))

for (tec, reg), row in prod6.head(25).iterrows():
    linea = f"  {str(tec)[:33]:<35} {str(reg):<12}"
    for c in cols6:
        val = int(row[c])
        linea += f" {val:>7}"
    linea += f" {int(row['Total']):>7}"
    print(linea)

# Detectar caídas bruscas (último mes vs penúltimo)
_caidas_export = []
if len(cols6) >= 2:
    ultimo   = cols6[-1]
    penultimo= cols6[-2]
    prod6["caida"] = prod6[penultimo] - prod6[ultimo]
    prod6["pct_caida"] = (prod6["caida"] / prod6[penultimo].replace(0,1) * 100).round(1)
    caidas = prod6[
        (prod6["caida"] > 30) & (prod6[penultimo] > 30)
    ].sort_values("caida", ascending=False)

    if len(caidas) > 0:
        print("\n  ALERTAS DE CAIDA BRUSCA DE PRODUCTIVIDAD:")
        print(f"  {'Tecnico':<35} {'Regional':<12} {meses_labels.get(penultimo,'Pen.'):>8} {meses_labels.get(ultimo,'Ult.'):>8} {'Caida':>7} {'%Caida':>8}")
        print("  " + "-"*82)
        for (tec, reg), row in caidas.head(10).iterrows():
            print(f"  {str(tec)[:33]:<35} {str(reg):<12} "
                  f"{int(row[penultimo]):>8} {int(row[ultimo]):>8} "
                  f"{int(row['caida']):>7} {row['pct_caida']:>7.1f}%  ⚠")
            _caidas_export.append({
                "tecnico": str(tec),
                "regional": str(reg),
                "mes_anterior": meses_labels.get(penultimo, penultimo),
                "mes_actual": meses_labels.get(ultimo, ultimo),
                "tickets_anterior": int(row[penultimo]),
                "tickets_actual": int(row[ultimo]),
                "caida": int(row["caida"]),
                "pct_caida": float(row["pct_caida"]),
            })

# ════════════════════════════════════════════════════════════════
# EQUIDAD Y ETICA
# ════════════════════════════════════════════════════════════════
seccion("ANALISIS DE EQUIDAD POR REGIONAL")

print(f"\n  {'Regional':<14} {'Tickets':>8} {'SLA Exc':>8} {'%SLA':>6} {'Riesgo':>7} {'%Riesgo':>8}")
print("  " + "-"*56)
for reg in ["Bogota","Medellin","Cali","Costa"]:
    sub = df[df["regional"] == reg]
    if len(sub) == 0: continue
    print(f"  {reg:<14} {len(sub):>8,} {sub['sla_excedido'].sum():>8,} "
          f"{sub['sla_excedido'].mean()*100:>5.1f}% "
          f"{sub['en_riesgo'].sum():>7} {sub['en_riesgo'].mean()*100:>7.1f}%")

print("""
  Principios aplicados:
  - class_weight='balanced' en Random Forest y SVM
  - Metricas auditadas por regional (sin penalizar carga historica)
  - NLP sobre asuntos reales, sin vincular stoppers a tecnicos
  - Modelos como señal de alerta, no criterio disciplinario
""")

# ════════════════════════════════════════════════════════════════
# RESUMEN FINAL
# ════════════════════════════════════════════════════════════════

# Exportar predicciones para el dashboard
try:
    import json as _json
    _predicciones = {
        "generado_en": datetime.now().isoformat(),
        "archivo_glpi": os.path.basename(archivo_glpi) if archivo_glpi else "",
        "resumen": {
            "total_tickets": int(len(df)),
            "tickets_en_riesgo": int(df["en_riesgo"].sum()),
            "frus_criticas": int((df_partes["Total On Hand Qty"]==0).sum()) if df_partes is not None else 0,
            "pct_sla": round((1 - df["sla_excedido"].mean()) * 100, 1),
            "alertas_productividad": len(_caidas_export),
        },
        "tickets_riesgo": [],
        "frus_riesgo": [],
        "caidas_productividad": _caidas_export,
    }
    if "prob_riesgo" in df.columns:
        _activos_mask = df["Estado"].astype(str).isin(["En curso (asignada)","En curso (planificada)","En espera"])
        # Restringir a la MISMA poblacion de tickets que ya reporta el bot
        # de alertas (backlog actual por regional), no todo el universo de
        # activos de GLPI -- si no hay CSV de alertas disponibles, se sigue
        # de largo sin filtrar en vez de dejar la lista vacia.
        _ids_alertas = ids_backlog_alertas(CARPETA_ALERTAS)
        if _ids_alertas:
            _en_backlog = df["Tiquete"].astype(str).str.strip().isin(_ids_alertas)
            print(f"  Backlog de alertas: {len(_ids_alertas)} tickets | de los activos de GLPI, {int((_activos_mask & _en_backlog).sum())} coinciden")
        else:
            print("  AVISO: sin CSV de alertas disponibles, prediciones sin restringir al backlog de alertas")
            _en_backlog = pd.Series(True, index=df.index)
        top = df[_activos_mask & _en_backlog].sort_values("prob_riesgo", ascending=False).head(20)
        for _, r in top.iterrows():
            _predicciones["tickets_riesgo"].append({
                "id": str(r.get("Tiquete","")),
                "regional": str(r.get("regional","")),
                "ci": str(r.get("CI",""))[:40],
                "dias": int(r.get("dias_abierto",0)),
                "sla_excedido": int(r.get("sla_excedido",0)),
                "prob": round(float(r.get("prob_riesgo",0))*100, 4),
            })
    if df_partes is not None:
        top_frus = df_partes[df_partes["Total On Hand Qty"]==0].sort_values("Total Open PO Qty", ascending=False).head(15)
        for _, r in top_frus.iterrows():
            _predicciones["frus_riesgo"].append({
                "Warehouse Code": str(r.get("Warehouse Code","")),
                "Part Number": str(r.get("Part Number","")),
                "Part Description": str(r.get("Part Description",""))[:45],
                "Total On Hand Qty": int(r.get("Total On Hand Qty",0)),
                "Total Open PO Qty": int(r.get("Total Open PO Qty",0)),
            })
    _ruta = os.path.join(CARPETA_BASE, "predicciones.json")
    with open(_ruta, "w", encoding="utf-8") as _fj:
        _json.dump(_predicciones, _fj, ensure_ascii=False, indent=2)
    print(f"  OK Predicciones guardadas: {_ruta}")
except Exception as _e:
    print(f"  AVISO exportacion: {_e}")

seccion("RESUMEN EJECUTIVO")
n_partes = len(df_partes) if df_partes is not None else 0
print(f"  Dataset GLPI:  {len(df):,} tickets reales (ene 2025 - may 2026)")
print(f"  Dataset HR005: {n_partes:,} partes de inventario")
print()
print("  Modulo 1 - Tickets en Riesgo    -> Gradient Boosting  -> datos GLPI")
print("  Modulo 2 - Desabastecimiento    -> Random Forest       -> datos HR005")
print("  Modulo 3 - Productividad/SLA    -> SVM kernel RBF      -> datos GLPI")
print("  Modulo 4 - Stoppers NLP         -> TF-IDF + K-Means    -> Asuntos GLPI")
print()
print(r"  Estructura de carpetas:")
print(r"    C:\Bot_Incidentes\ ")
print(r"    |-- sistema_ia_exito.py          <- este script")
print(r"    |-- bot_alertas_partes.py        <- bot de alertas WhatsApp")
print(r"    |-- glpi\                        <- exporta el Excel de GLPI aqui")
print(r"    |   \-- data (2).xlsx            <- el script toma el mas reciente")
print(r"    \-- partes\                      <- copia el HR005 aqui cada semana")
print(r"        \-- Toshiba_HR005_-_FECHA.xlsx")
print()
print(r"  Para actualizar el modelo cada semana:")
print(r"    1. Exporta el Excel de GLPI -> copialo en: C:\Bot_Incidentes\glpi\ ")
print(r"    2. Copia el nuevo HR005 en:               C:\Bot_Incidentes\partes\ ")
print(r"    3. Corre: python sistema_ia_exito.py  (toma el archivo mas reciente)")
print(r"    4. El bot_alertas_partes.py envia resultados a WhatsApp")
print("=" * 65)
print("  Sistema entrenado con datos reales exitosamente.")
print("=" * 65)
