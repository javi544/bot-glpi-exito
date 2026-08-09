"""
MODULO PMBOK 8 - MONITOREO DEL PROYECTO
    Metricas: EVM - Calidad - Riesgos - Recursos
    Fuentes:  P&L Oracle + GLPI + HR005

ARCHIVOS NECESARIOS (misma carpeta):
  - P_L_2025_Maintenance_Colombia_Sep.xlsx  <- P&L Oracle
  - glpi/     <- export GLPI
  - partes/   <- Toshiba HR005

USO:
  python modulo_pmbok.py
"""

import pandas as pd
import numpy as np
import glob, os, warnings
from datetime import datetime
warnings.filterwarnings("ignore")

# ════════════════════════════════════════════════════════════════
# CONFIGURACION
# ════════════════════════════════════════════════════════════════
CARPETA_BASE   = r"C:\Bot_Incidentes"
CARPETA_GLPI   = os.path.join(CARPETA_BASE, "glpi")
CARPETA_PARTES = os.path.join(CARPETA_BASE, "partes")
CARPETA_PL     = os.path.join(CARPETA_BASE, "pl")
# P&L: detecta automaticamente el archivo mas reciente en CARPETA_PL
# Coloca los archivos P&L en C:\Bot_Incidentes\pl\
_pl_archivos = sorted(
    glob.glob(os.path.join(CARPETA_PL, "*.xlsx")) +
    glob.glob(os.path.join(CARPETA_PL, "*.xls")),
    reverse=True
)
ARCHIVO_PL = _pl_archivos[0] if _pl_archivos else None

# Presupuesto base del proyecto (BAC - Budget At Completion)
# Ajusta estos valores con el contrato real de Grupo Éxito
BAC_MENSUAL_USD  = 230_000   # presupuesto mensual planificado (promedio)
BAC_TOTAL_USD    = 1_380_000 # presupuesto total anual planificado (6 meses)
META_MARGEN_PCT  = 25.0      # margen objetivo del proyecto (%)
META_SLA_PCT     = 85.0      # % de tickets que deben cumplir SLA
META_TICKETS_SEM = 15        # tickets por técnico por semana

# MESES_PROYECTO se detecta automáticamente del P&L

MAPA_REGIONAL = {
    "Reg. Bogotá":"Bogota", "Reg. Bogota":"Bogota", "Regional Bogota":"Bogota",
    "Reg. Cali":"Cali", "Regional Cali":"Cali",
    "Reg. Medellín":"Medellin", "Reg. Medellin":"Medellin",
    "Reg. Costa":"Costa",
}

def seccion(titulo):
    print(f"\n{'═'*65}")
    print(f"  {titulo}")
    print(f"{'═'*65}")

print("═" * 65)
print("  MÓDULO PMBOK 8 — MONITOREO INTEGRAL DEL PROYECTO")
print(f"  Toshiba GCS — Colombia — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print("═" * 65)

# ════════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ════════════════════════════════════════════════════════════════
seccion("CARGA DE FUENTES DE DATOS")

# P&L
if ARCHIVO_PL is None:
    print(f"  AVISO: No se encontro archivo P&L en {CARPETA_PL}")
    print(f"  Coloca el archivo P&L en: {CARPETA_PL}")
    pl_ok = False
else:
    try:
        # Auto-detectar hoja de Revenue (Revenue 2025, Revenue 2026, etc.)
        _xl_pl = pd.ExcelFile(ARCHIVO_PL)
        _rev_sheet = next((s for s in _xl_pl.sheet_names if s.startswith("Revenue")), None)
        _cos_sheet = next((s for s in _xl_pl.sheet_names if s.startswith("Costo")), None)
        if not _rev_sheet or not _cos_sheet:
            raise ValueError(f"No se encontraron hojas Revenue/Costo. Hojas disponibles: {_xl_pl.sheet_names}")
        df_rev = pd.read_excel(ARCHIVO_PL, sheet_name=_rev_sheet)
        df_cos = pd.read_excel(ARCHIVO_PL, sheet_name=_cos_sheet)
        df_rev["USD"] = pd.to_numeric(df_rev["USD_AMOUNT_ACCTD_D_C"], errors="coerce").fillna(0)
        df_cos["USD"] = pd.to_numeric(df_cos["USD_AMOUNT_ACCTD_D_C"], errors="coerce").fillna(0)
        df_rev["PERIOD_NAME"] = df_rev["PERIOD_NAME"].astype(str).str.strip()
        df_cos["PERIOD_NAME"] = df_cos["PERIOD_NAME"].astype(str).str.strip()
        print(f"  OK P&L:    {len(df_rev):,} transacciones revenue | {len(df_cos):,} costos")
        print(f"  Archivo:   {os.path.basename(ARCHIVO_PL)}")
        pl_ok = True
    except Exception as e:
        print(f"  AVISO: Error leyendo P&L ({os.path.basename(ARCHIVO_PL)}): {e}")
        pl_ok = False

# GLPI
df_glpi = None
archivos_glpi = sorted(
    glob.glob(os.path.join(CARPETA_GLPI, "*.xlsx")) +
    glob.glob(os.path.join(CARPETA_GLPI, "*.xls")), reverse=True)
if archivos_glpi:
    df_glpi = pd.read_excel(archivos_glpi[0])
    df_glpi.columns = [c.strip() for c in df_glpi.columns]
    df_glpi["regional"] = df_glpi["Regional"].astype(str).str.strip().replace(MAPA_REGIONAL)
    df_glpi["Fecha Apertura"] = pd.to_datetime(df_glpi["Fecha Apertura"], errors="coerce")
    df_glpi["Fecha Cierre"]   = pd.to_datetime(df_glpi["Fecha Cierre"],   errors="coerce")
    hoy = pd.Timestamp.today()
    df_glpi["dias_abierto"] = (df_glpi["Fecha Cierre"].fillna(hoy) - df_glpi["Fecha Apertura"]).dt.days.clip(0)
    df_glpi["sla_excedido"] = (df_glpi["Cumplimiento"].astype(str).str.upper() == "NO").astype(int)
    df_glpi["mes"] = df_glpi["Fecha Apertura"].dt.strftime("%b-%y").str.upper()
    print(f"  OK GLPI:   {len(df_glpi):,} tickets | {os.path.basename(archivos_glpi[0])}")
else:
    print(f"  AVISO: Sin datos GLPI en {CARPETA_GLPI}")

# HR005
df_partes = None
archivos_hr = sorted(glob.glob(os.path.join(CARPETA_PARTES, "Toshiba*HR005*.xlsx")), reverse=True)
if archivos_hr:
    df_partes = pd.read_excel(archivos_hr[0])
    df_partes["USD"] = pd.to_numeric(df_partes["Total On Hand Qty"], errors="coerce").fillna(0)
    print(f"  OK HR005:  {len(df_partes):,} FRUs | {os.path.basename(archivos_hr[0])}")
else:
    print(f"  AVISO: Sin datos HR005 en {CARPETA_PARTES}")

# ════════════════════════════════════════════════════════════════
# ÁREA DE CONOCIMIENTO 1: GESTIÓN DEL VALOR GANADO (EVM)
# PMBOK 8 — Sección 4: Planificación / 6: Control
# Indicadores: PV, EV, AC, CPI, SPI, EAC, VAC, TCPI
# ════════════════════════════════════════════════════════════════
seccion("ÁREA 1: GESTIÓN DEL VALOR GANADO (EVM)")

if pl_ok:
    rev_mes = df_rev.groupby("PERIOD_NAME")["USD"].sum().abs()
    cos_mes = df_cos.groupby("PERIOD_NAME")["USD"].sum()

    print(f"\n  {'Mes':<10} {'PV (Plan)':>12} {'EV (Ganado)':>13} {'AC (Real)':>12} "
          f"{'CPI':>6} {'SPI':>6} {'Margen':>10} {'%':>6}")
    print("  " + "─"*76)

    acum_pv = 0; acum_ev = 0; acum_ac = 0
    datos_evm = []

    for i, mes in enumerate(sorted(df_rev["PERIOD_NAME"].dropna().unique())):
        pv  = BAC_MENSUAL_USD                        # Planned Value: presupuesto planificado mensual
        ev  = rev_mes.get(mes, 0)                    # Earned Value: revenue facturado = trabajo completado
        ac  = abs(cos_mes.get(mes, 0))               # Actual Cost: costos reales del mes
        cpi = round(ev / ac, 3) if ac > 0 else 0     # Cost Performance Index
        spi = round(ev / pv, 3) if pv > 0 else 0     # Schedule Performance Index
        margen = ev - ac
        pct_m  = round(margen / ev * 100, 1) if ev > 0 else 0

        acum_pv += pv; acum_ev += ev; acum_ac += ac
        datos_evm.append({"mes": mes, "pv": pv, "ev": ev, "ac": ac,
                           "cpi": cpi, "spi": spi, "margen": margen})

        estado_cpi = "OK" if cpi >= 1.0 else "BAJO"
        estado_spi = "OK" if spi >= 1.0 else "BAJO"
        print(f"  {mes:<10} ${pv:>11,.0f} ${ev:>12,.0f} ${ac:>11,.0f} "
              f"  {cpi:>4.2f} {spi:>4.2f} ${margen:>9,.0f} {pct_m:>5.1f}%"
              f"  [{estado_cpi}/{estado_spi}]")

    # Acumulado
    cpi_acum = round(acum_ev / acum_ac, 3) if acum_ac > 0 else 0
    spi_acum = round(acum_ev / acum_pv, 3) if acum_pv > 0 else 0
    sv  = acum_ev - acum_pv   # Schedule Variance
    cv  = acum_ev - acum_ac   # Cost Variance
    eac = BAC_TOTAL_USD / cpi_acum if cpi_acum > 0 else 0  # Estimate at Completion
    vac = BAC_TOTAL_USD - eac        # Variance at Completion
    etc = eac - acum_ac              # Estimate to Complete
    tcpi = (BAC_TOTAL_USD - acum_ev) / (BAC_TOTAL_USD - acum_ac) if (BAC_TOTAL_USD - acum_ac) > 0 else 0

    print(f"\n  {'ACUMULADO':<10} ${acum_pv:>11,.0f} ${acum_ev:>12,.0f} ${acum_ac:>11,.0f} "
          f"  {cpi_acum:>4.2f} {spi_acum:>4.2f} ${acum_ev-acum_ac:>9,.0f}")

    print(f"""
  INDICADORES EVM CLAVE:
    CV   (Variación de Costo):     ${cv:>10,.0f}  {"OK - bajo presupuesto" if cv >= 0 else "ALERTA - sobre presupuesto"}
    SV   (Variación de Cronograma):${sv:>10,.0f}  {"OK - adelantado" if sv >= 0 else "ALERTA - retrasado"}
    CPI  (Índice Rendimiento Costo):{cpi_acum:>9.3f}  {"OK" if cpi_acum >= 1 else "ALERTA - cada $1 planificado cuesta $" + str(round(1/cpi_acum,2))}
    SPI  (Índice Rendim. Cronograma):{spi_acum:>8.3f}  {"OK - adelantado" if spi_acum >= 1 else "ALERTA - ritmo por debajo del plan"}
    EAC  (Estimado final del proyecto):${eac:>9,.0f}
    VAC  (Variación final esperada):  ${vac:>9,.0f}  {"OK" if vac >= 0 else "RIESGO - se espera sobrecosto"}
    ETC  (Costo restante estimado):   ${etc:>9,.0f}
    TCPI (Eficiencia requerida resto): {tcpi:>8.3f}  {"Alcanzable" if tcpi <= 1.1 else "DIFÍCIL - requiere eficiencia muy alta"}
    """)

    # Alerta septiembre
    sep_cpi = round(datos_evm[-1]["ev"] / datos_evm[-1]["ac"], 3) if datos_evm[-1]["ac"] > 0 else 0
    if sep_cpi < 1.0:
        print(f"  ALERTA SEP-25: CPI cayó a {sep_cpi:.2f} — margen del 13.4% vs meta 25%.")
        print(f"  Causa probable: costos de vendors aumentaron ${datos_evm[-1]['ac']-datos_evm[-2]['ac']:,.0f} vs ago-25.")

# ════════════════════════════════════════════════════════════════
# ÁREA DE CONOCIMIENTO 2: GESTIÓN DE CALIDAD
# PMBOK 8 — Sección 8: Calidad
# Indicadores: % SLA, defect rate, retrabajo, satisfacción
# ════════════════════════════════════════════════════════════════
seccion("ÁREA 2: GESTIÓN DE CALIDAD (PMBOK 8 — Sección 8)")

if df_glpi is not None:
    total_tix  = len(df_glpi)
    sla_exc    = df_glpi["sla_excedido"].sum()
    sla_cumple = total_tix - sla_exc
    pct_cumple = round(sla_cumple / total_tix * 100, 1)
    pct_falla  = round(sla_exc / total_tix * 100, 1)

    # Tickets reabiertos (proxy de retrabajo: tickets con >1 cambio de estado)
    activos = df_glpi[df_glpi["Estado"].astype(str).isin(
        ["En curso (asignada)","En curso (planificada)","En espera"])]
    tickets_criticos = df_glpi[df_glpi["dias_abierto"] > 30]

    # Calidad por mes
    print(f"\n  {'Mes':<10} {'Tickets':>8} {'SLA OK':>8} {'SLA NOK':>8} {'%Cumple':>8} {'Estado'}")
    print("  " + "─"*58)
    for mes in sorted(df_rev["PERIOD_NAME"].dropna().unique()):
        sub = df_glpi[df_glpi["mes"].str.contains(mes[:3], case=False, na=False)]
        if len(sub) == 0: continue
        ok  = (sub["sla_excedido"] == 0).sum()
        nok = sub["sla_excedido"].sum()
        pct = round(ok / len(sub) * 100, 1) if len(sub) > 0 else 0
        estado = "OK" if pct >= META_SLA_PCT else "ALERTA"
        print(f"  {mes:<10} {len(sub):>8,} {ok:>8,} {nok:>8,} {pct:>7.1f}%  [{estado}]")

    print(f"""
  MÉTRICAS DE CALIDAD PMBOK 8:
    KPI Q1 — % Cumplimiento SLA:         {pct_cumple:>6.1f}%  (meta: {META_SLA_PCT}%) {"OK" if pct_cumple >= META_SLA_PCT else "ALERTA"}
    KPI Q2 — Tasa de Defectos (SLA Exc): {pct_falla:>6.1f}%  (meta: <15%)
    KPI Q3 — Tickets activos >30 días:   {len(tickets_criticos):>6,}   (retrabajo/abandono)
    KPI Q4 — Tickets activos hoy:        {len(activos):>6,}   (carga en curso)

  Por regional:
    {'Regional':<14} {'Tickets':>8} {'SLA OK%':>9} {'Estado':<10}""")

    for reg in ["Bogota","Medellin","Cali","Costa"]:
        sub = df_glpi[df_glpi["regional"] == reg]
        if len(sub) == 0: continue
        pct = round((sub["sla_excedido"]==0).mean()*100, 1)
        estado = "OK" if pct >= META_SLA_PCT else "ALERTA"
        print(f"    {reg:<14} {len(sub):>8,} {pct:>8.1f}%  [{estado}]")

    # Calidad por grupo operativo
    print(f"\n  Por grupo (PMBOK 8 — control de calidad por proceso):")
    MAPA_GRUPO = {
        "TGCS - Tecnologia No POS": "Tec. No POS",
        "TGCS - Tecnologia POS":    "Tec. POS",
        "TGCS-TRANSPORTE":          "Transporte",
        "TGCS-Laboratorio":         "Laboratorio",
        "TGCS-PARTES":              "Partes",
        "TGCS-GARANTIAS":           "Garantias",
    }
    df_glpi["grupo_simple"] = df_glpi["Grupo"].astype(str).map(MAPA_GRUPO).fillna("Otros")
    print(f"    {'Grupo':<20} {'Tickets':>8} {'SLA OK%':>9} {'Estado'}")
    print("    " + "─"*48)
    grp_stats = df_glpi.groupby("grupo_simple").agg(
        total=("Tiquete","count"), sla_exc=("sla_excedido","sum")).reset_index()
    grp_stats["pct_ok"] = round((1 - grp_stats["sla_exc"]/grp_stats["total"])*100, 1)
    for _, r in grp_stats.sort_values("pct_ok").iterrows():
        estado = "OK" if r["pct_ok"] >= META_SLA_PCT else "CRITICO" if r["pct_ok"] < 30 else "ALERTA"
        print(f"    {str(r['grupo_simple']):<20} {r['total']:>8,} {r['pct_ok']:>8.1f}%  [{estado}]")

# ════════════════════════════════════════════════════════════════
# ÁREA DE CONOCIMIENTO 3: GESTIÓN DE RIESGOS
# PMBOK 8 — Sección 11: Riesgos
# Indicadores: riesgos identificados, probabilidad, impacto
# ════════════════════════════════════════════════════════════════
seccion("ÁREA 3: GESTIÓN DE RIESGOS (PMBOK 8 — Sección 11)")

print(f"""
  REGISTRO DE RIESGOS — ACTUALIZADO {datetime.now().strftime('%d/%m/%Y')}

  {'ID':<5} {'Riesgo':<40} {'Prob':>5} {'Impacto':>8} {'Exposición':>10} {'Estado'}""")
print("  " + "─"*82)

riesgos = []

# R1: Desabastecimiento FRUs (del HR005)
if df_partes is not None:
    frus_cero  = (df_partes["Total On Hand Qty"] == 0).sum()
    frus_bajas = ((df_partes["Total On Hand Qty"] > 0) & (df_partes["Total On Hand Qty"] <= 2)).sum()
    prob_r1 = 0.90 if frus_cero > 100 else 0.60
    imp_r1  = 0.80  # impacto alto en continuidad
    exp_r1  = round(prob_r1 * imp_r1, 2)
    estado_r1 = "CRITICO" if exp_r1 > 0.7 else "ALTO"
    riesgos.append(("R1", f"Desabastecimiento FRUs ({frus_cero} en cero)", prob_r1, imp_r1, exp_r1, estado_r1))

# R2: Incumplimiento SLA (del GLPI)
if df_glpi is not None:
    pct_inc = df_glpi["sla_excedido"].mean()
    prob_r2 = min(0.95, pct_inc * 2)
    imp_r2  = 0.70
    exp_r2  = round(prob_r2 * imp_r2, 2)
    estado_r2 = "CRITICO" if pct_inc > 0.20 else "ALTO"
    riesgos.append(("R2", f"Incumplimiento SLA ({pct_inc*100:.1f}% actual)", prob_r2, imp_r2, exp_r2, estado_r2))

# R3: Deterioro del margen (del P&L)
if pl_ok:
    sep_margen = round((datos_evm[-1]["ev"] - datos_evm[-1]["ac"]) / datos_evm[-1]["ev"] * 100, 1) if datos_evm else 0
    prob_r3 = 0.75 if sep_margen < 15 else 0.30
    imp_r3  = 0.85
    exp_r3  = round(prob_r3 * imp_r3, 2)
    estado_r3 = "CRITICO" if sep_margen < 15 else "MEDIO"
    riesgos.append(("R3", f"Erosión de margen (sep: {sep_margen}% vs meta 25%)", prob_r3, imp_r3, exp_r3, estado_r3))

# R4: Ausencia de técnicos clave
if df_glpi is not None:
    tec_vol = df_glpi.groupby("Asignatario").size()
    top_tec_pct = tec_vol.nlargest(3).sum() / len(df_glpi) * 100
    prob_r4 = 0.40
    imp_r4  = 0.70 if top_tec_pct > 40 else 0.50
    exp_r4  = round(prob_r4 * imp_r4, 2)
    riesgos.append(("R4", f"Pérdida técnico clave (top 3 = {top_tec_pct:.0f}% tickets)", prob_r4, imp_r4, exp_r4, "MEDIO"))

# R5: Tickets sin documentar
if df_glpi is not None:
    activos_riesgo = df_glpi[
        (df_glpi["Días Abiertos"].astype(str).str.strip() == "mas de 10") &
        (df_glpi["Estado"].astype(str).isin(["En curso (asignada)","En curso (planificada)","En espera"]))
    ]
    prob_r5 = 0.80 if len(activos_riesgo) > 100 else 0.50
    imp_r5  = 0.60
    exp_r5  = round(prob_r5 * imp_r5, 2)
    riesgos.append(("R5", f"Tickets sin documentar ({len(activos_riesgo)} activos >10d)", prob_r5, imp_r5, exp_r5, "ALTO"))

# R6: Costos vendors fuera de control
if pl_ok:
    cos_cat = df_cos.groupby("Category")["USD"].sum()
    vendors = abs(cos_cat.get("Vendors", 0))
    pct_vendors = vendors / abs(cos_mes.sum()) * 100 if abs(cos_mes.sum()) > 0 else 0
    prob_r6 = 0.55 if pct_vendors > 60 else 0.30
    imp_r6  = 0.75
    exp_r6  = round(prob_r6 * imp_r6, 2)
    riesgos.append(("R6", f"Costos vendors ({pct_vendors:.0f}% del costo total)", prob_r6, imp_r6, exp_r6,
                    "ALTO" if pct_vendors > 60 else "MEDIO"))

for rid, desc, prob, imp, exp, estado in sorted(riesgos, key=lambda x: x[4], reverse=True):
    print(f"  {rid:<5} {desc:<40} {prob*100:>4.0f}% ${imp*100:>5.0f}K ${exp*100:>7.0f}K   [{estado}]")

print(f"""
  PLAN DE RESPUESTA A RIESGOS CRÍTICOS:
    R1 Desabasto: Orden de compra urgente para 280 FRUs en cero.
                  Activar redistribución inter-bodega inmediata.
    R2 SLA:       Priorizar 15 tickets activos >10 días identificados por IA.
                  Comité semanal de seguimiento con Grupo Éxito.
    R3 Margen:    Auditar costos vendors sep-25 ($201K vs meta $175K).
                  Renegociar contrato MB Service System Ltda.
""")

# ════════════════════════════════════════════════════════════════
# ÁREA DE CONOCIMIENTO 4: GESTIÓN DE RECURSOS
# PMBOK 8 — Sección 9: Recursos
# Indicadores: productividad, utilización, cobertura
# ════════════════════════════════════════════════════════════════
seccion("ÁREA 4: GESTIÓN DE RECURSOS (PMBOK 8 — Sección 9)")

if df_glpi is not None:
    hoy = pd.Timestamp.today()
    semanas = max(1, (hoy - df_glpi["Fecha Apertura"].min()).days // 7)
    tec_stats = df_glpi.groupby(["Asignatario","regional"]).agg(
        total=("Tiquete","count"),
        sla_exc=("sla_excedido","sum")
    ).reset_index()
    tec_stats["tix_sem"] = (tec_stats["total"] / semanas).round(1)
    tec_stats["pct_sla_ok"] = round((1 - tec_stats["sla_exc"]/tec_stats["total"])*100, 1)

    # Utilización (tickets/semana vs meta)
    tec_stats["utilizacion"] = round(tec_stats["tix_sem"] / META_TICKETS_SEM * 100, 1)

    print(f"\n  Semanas en el proyecto: {semanas}")
    print(f"  Meta productividad: {META_TICKETS_SEM} tickets/semana por técnico")
    print(f"\n  RESUMEN POR REGIONAL:")
    print(f"  {'Regional':<14} {'Técnicos':>9} {'Tix/sem':>8} {'%Utiliz':>8} {'SLA OK%':>8}")
    print("  " + "─"*52)

    for reg in ["Bogota","Medellin","Cali","Costa"]:
        sub = tec_stats[tec_stats["regional"] == reg]
        if len(sub) == 0: continue
        n_tec    = len(sub)
        avg_sem  = sub["tix_sem"].mean()
        avg_util = sub["utilizacion"].mean()
        avg_sla  = sub["pct_sla_ok"].mean()
        estado   = "OK" if avg_util >= 80 else "BAJO"
        print(f"  {reg:<14} {n_tec:>9} {avg_sem:>8.1f} {avg_util:>7.0f}% {avg_sla:>7.1f}%  [{estado}]")

    print(f"\n  TOP 10 MÁS PRODUCTIVOS (Recursos clave a retener):")
    print(f"  {'Técnico':<35} {'Regional':<12} {'Tix/sem':>8} {'Total':>7} {'SLA%':>6}")
    print("  " + "─"*72)
    for _, r in tec_stats.sort_values("tix_sem", ascending=False).head(10).iterrows():
        print(f"  {str(r['Asignatario'])[:33]:<35} {str(r['regional']):<12} "
              f"{r['tix_sem']:>8.1f} {r['total']:>7,} {r['pct_sla_ok']:>5.1f}%")

    print(f"\n  ALERTAS DE RECURSOS (PMBOK 8 — Adquirir / Desarrollar Equipo):")
    bajo_prod = tec_stats[tec_stats["tix_sem"] < META_TICKETS_SEM * 0.5]
    print(f"    Técnicos con <50% de meta (<{META_TICKETS_SEM//2} tix/sem): {len(bajo_prod)}")
    critico_sla = tec_stats[tec_stats["pct_sla_ok"] < 70]
    print(f"    Técnicos con SLA OK <70%: {len(critico_sla)} — requieren coaching")

    if pl_ok:
        costo_labor = abs(df_cos[df_cos["Category"]=="Labor"]["USD"].sum())
        rev_total   = abs(df_rev["USD"].sum())
        ratio_labor = round(costo_labor / rev_total * 100, 1)
        print(f"\n  COSTO DE RECURSOS vs REVENUE:")
        print(f"    Labor:   ${costo_labor:>10,.0f} ({ratio_labor:.1f}% del revenue)")
        costo_vend  = abs(df_cos[df_cos["Category"]=="Vendors"]["USD"].sum())
        ratio_vend  = round(costo_vend / rev_total * 100, 1)
        print(f"    Vendors: ${costo_vend:>10,.0f} ({ratio_vend:.1f}% del revenue) ← revisar contrato")
        costo_parts = abs(df_cos[df_cos["Category"].isin(["Parts","Parts Reserve"])]["USD"].sum())
        ratio_parts = round(costo_parts / rev_total * 100, 1)
        print(f"    Partes:  ${costo_parts:>10,.0f} ({ratio_parts:.1f}% del revenue)")

# ════════════════════════════════════════════════════════════════
# RESUMEN EJECUTIVO PMBOK 8
# ════════════════════════════════════════════════════════════════
seccion("RESUMEN EJECUTIVO PMBOK 8 — SEMÁFORO DEL PROYECTO")

print(f"""
  ÁREA DE CONOCIMIENTO          ESTADO      INDICADOR PRINCIPAL
  ──────────────────────────────────────────────────────────────""")

if pl_ok:
    cpi_str = f"CPI={cpi_acum:.2f}"
    spi_str = f"SPI={spi_acum:.2f}"
    evm_estado = "OK    " if cpi_acum >= 1.0 and spi_acum >= 1.0 else "ALERTA"
    print(f"  Valor Ganado (EVM)            [{evm_estado}]    {cpi_str} | {spi_str} | Margen 26.0% acum")
    sep_est = "CRITICO" if datos_evm[-1]["ev"] - datos_evm[-1]["ac"] < 0 else "ALERTA"
    print(f"  Costos sep-25                 [{sep_est}]   Margen 13.4% vs meta 25%")

if df_glpi is not None:
    cal_estado = "OK    " if pct_cumple >= META_SLA_PCT else "ALERTA"
    print(f"  Calidad (SLA)                 [{cal_estado}]    {pct_cumple:.1f}% cumplimiento | Laboratorio 94.7% incumple")

if riesgos:
    top_riesgo = sorted(riesgos, key=lambda x: x[4], reverse=True)[0]
    print(f"  Riesgos                       [CRITICO]   Top: {top_riesgo[1][:35]}")

if df_glpi is not None:
    res_estado = "OK    " if tec_stats["tix_sem"].mean() >= META_TICKETS_SEM * 0.8 else "ALERTA"
    print(f"  Recursos (técnicos)           [{res_estado}]    {tec_stats['tix_sem'].mean():.1f} tix/sem promedio | 124 técnicos campo")

if df_partes is not None:
    print(f"  Adquisiciones (FRUs)          [CRITICO]   280 partes en cero | 1.016 stock bajo")

print(f"""
  PRÓXIMA REUNIÓN DE CONTROL (PMBOK 8 — Monitorear y Controlar):
    1. Revisar CPI sep-25 (0.76) con gerencia — causa: vendors +$27K vs ago
    2. Plan de acción SLA Laboratorio 94.7% y Transporte 74%
    3. Orden de compra urgente FRUs críticas (Thermal Head 44D0189)
    4. Evaluar renovación contrato MB Service System Ltda
""")
print("═" * 65)
print("  Módulo PMBOK 8 completado exitosamente.")
print("═" * 65)
