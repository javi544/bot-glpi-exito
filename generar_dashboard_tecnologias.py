"""
Script que lee los CSV de alertas y genera el dashboard de tecnologías.
Se integra al bot_alertas.py para ejecutarse automáticamente.
"""
import os
import glob
import json
import shutil
import subprocess
import pandas as pd
from datetime import datetime, timedelta

# =========================
# CONFIG
# =========================
CARPETA_DATA    = os.path.join(os.path.dirname(__file__), "data")
REPO_DASHBOARD  = "C:/dashboard-tecnologias-exito"
ARCHIVO_SALIDA  = os.path.join(REPO_DASHBOARD, "index.html")

# Agrupación de tecnologías
def clasificar_tecnologia(categoria):
    if pd.isna(categoria):
        return "Otros"
    cat = str(categoria).lower()
    if "computador" in cat or "pc kiosko" in cat:
        return "💻 Computadores"
    elif "hand held" in cat or "handheld" in cat:
        return "📱 Terminal HandHeld"
    elif "balanza" in cat or "bioptico" in cat or "escanner balanza" in cat:
        return "⚖️ Balanzas"
    elif "puesto de pago" in cat or "pos autopago" in cat or "sco" in cat:
        return "🖥️ Puestos de Pago"
    elif "imp marcacion" in cat or "impresora" in cat or "imp laser" in cat:
        return "🖨️ Impresoras"
    elif "escaner de mano" in cat or "escáner" in cat:
        return "📷 Escáneres"
    elif "verificador" in cat:
        return "🏷️ Verificadores"
    elif "reloj" in cat or "biometrico" in cat:
        return "⏰ Control Biométrico"
    elif "aplicaciones" in cat or "sistema operativo" in cat or "windows" in cat:
        return "💾 Aplicaciones"
    else:
        return "📦 Otros"

REGIONALES = ["CALI", "MEDELLIN", "COSTA", "BOGOTA"]

def leer_todos_los_csv():
    """Lee todos los CSV del día actual de todas las regionales."""
    hoy = datetime.now().strftime("%Y%m%d")
    dfs = []

    for regional in REGIONALES:
        patron = os.path.join(CARPETA_DATA, f"alertas_{regional.lower()}_{hoy}.csv")
        archivos = glob.glob(patron)
        if not archivos:
            # Si no hay del día, tomar el más reciente
            patron_reciente = os.path.join(CARPETA_DATA, f"alertas_{regional.lower()}_*.csv")
            archivos = sorted(glob.glob(patron_reciente))

        if archivos:
            archivo = archivos[-1]
            try:
                df = pd.read_csv(archivo, encoding="utf-8-sig", on_bad_lines='skip')
                df['Regional'] = regional
                dfs.append(df)
                print(f"✅ {regional}: {len(df)} tickets")
            except Exception as e:
                print(f"⚠️  Error leyendo {regional}: {e}")

    if not dfs:
        return pd.DataFrame()

    df_total = pd.concat(dfs, ignore_index=True)
    df_total['Tecnologia'] = df_total['Categoría'].apply(clasificar_tecnologia)
    return df_total


def preparar_datos(df):
    """Prepara los datos para el dashboard."""
    ahora = datetime.now()

    # 1. Backlog por tecnología
    backlog_tec = df.groupby('Tecnologia').size().reset_index(name='total')
    backlog_tec = backlog_tec.sort_values('total', ascending=False)

    # 2. Backlog por tecnología y regional
    backlog_tec_reg = df.groupby(['Tecnologia', 'Regional']).size().reset_index(name='total')

    # 3. Técnicos — avance diario por regional
    col_tecnico = None
    for col in df.columns:
        if 'TÉCNICO' in col.upper() and 'GRUPO' not in col.upper():
            col_tecnico = col
            break
    if col_tecnico is None:
        col_tecnico = 'Asignado a - Técnico'

    tecnicos_regional = df.groupby(['Regional', col_tecnico]).size().reset_index(name='tickets')
    tecnicos_regional = tecnicos_regional.rename(columns={col_tecnico: 'Tecnico'})
    tecnicos_regional = tecnicos_regional[tecnicos_regional['Tecnico'].notna()]
    tecnicos_regional = tecnicos_regional[tecnicos_regional['Tecnico'].str.strip() != '']

    # 4. Comparativa por regional
    comp_regional = df.groupby('Regional').agg(
        total=('ID', 'count'),
        con_tecnico=(col_tecnico, lambda x: x.notna().sum())
    ).reset_index()

    # 5. Tendencia semanal — leer CSVs de la semana
    semana_data = []
    for i in range(7):
        fecha = (ahora - timedelta(days=i)).strftime("%Y%m%d")
        total_dia = 0
        for regional in REGIONALES:
            patron = os.path.join(CARPETA_DATA, f"alertas_{regional.lower()}_{fecha}.csv")
            archivos = glob.glob(patron)
            if archivos:
                try:
                    df_dia = pd.read_csv(archivos[0], encoding="utf-8-sig", on_bad_lines='skip')
                    total_dia += len(df_dia)
                except Exception:
                    pass
        if total_dia > 0:
            semana_data.append({
                "fecha": (ahora - timedelta(days=i)).strftime("%d/%m"),
                "total": total_dia
            })
    semana_data.reverse()

    # 6. Antigüedad por rangos — parseo robusto de fecha
    df['_fecha_ap'] = pd.to_datetime(df['Fecha de apertura'],
        format='%Y-%m-%d %H:%M:%S', errors='coerce')
    # Fallback formato sin segundos
    mask = df['_fecha_ap'].isna()
    if mask.any():
        df.loc[mask, '_fecha_ap'] = pd.to_datetime(
            df.loc[mask, 'Fecha de apertura'], errors='coerce')
    df['dias_abierto'] = (pd.Timestamp(ahora) - df['_fecha_ap']).dt.days.astype('Int64')

    def rango_antiguedad(dias):
        if pd.isna(dias): return None
        dias = int(dias)
        if dias < 2: return None
        elif 2 <= dias <= 5: return "2-5 dias"
        elif 6 <= dias <= 10: return "5-10 dias"
        else: return "+10 dias"

    df['rango'] = df['dias_abierto'].apply(rango_antiguedad)
    df_ant = df[df['rango'].notna()].copy()

    # Antigüedad por tecnología y rango
    ant_tec = df_ant.groupby(['Tecnologia', 'rango']).size().reset_index(name='total')

    # Antigüedad por regional y rango
    ant_reg = df_ant.groupby(['Regional', 'rango']).size().reset_index(name='total')

    # Detalle tickets antiguos
    cols_detalle = ['ID', 'Título', col_tecnico, 'Regional', 'Tecnologia', 'dias_abierto', 'rango', 'Estados']
    cols_detalle = [c for c in cols_detalle if c in df_ant.columns]
    detalle_ant = df_ant[cols_detalle].copy()
    detalle_ant['ID'] = detalle_ant['ID'].astype(str).str.strip()
    if col_tecnico in detalle_ant.columns:
        detalle_ant = detalle_ant.rename(columns={col_tecnico: 'Tecnico'})
    detalle_ant = detalle_ant.fillna('Sin asignar')
    # NO ordenar antes de tomar muestra — tomar todos y ordenar después
    detalle_ant = detalle_ant.sort_values('dias_abierto', ascending=False)

    # DIAGNÓSTICO
    print("=== DIAGNÓSTICO ANTIGÜEDAD ===")
    print("dias_abierto sample:", df['dias_abierto'].dropna().head(10).tolist())
    print("rango counts:", df['rango'].value_counts().to_dict())
    print("==============================")

    return {
        "backlog_tec":     backlog_tec.to_dict('records'),
        "backlog_tec_reg": backlog_tec_reg.to_dict('records'),
        "tecnicos":        tecnicos_regional.to_dict('records'),
        "comp_regional":   comp_regional.to_dict('records'),
        "semana":          semana_data,
        "ant_tec":         ant_tec.to_dict('records'),
        "ant_reg":         ant_reg.to_dict('records'),
        "detalle_ant":     detalle_ant.to_dict('records'),
        "total_tickets":   len(df),
        "regionales":      REGIONALES,
        "tecnologias":     sorted(df['Tecnologia'].unique().tolist()),
        "fecha":           ahora.strftime("%d/%m/%Y %H:%M"),
    }


def generar_html(datos):
    """Genera el dashboard HTML interactivo."""
    data_json = json.dumps(datos, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Tecnologías — Grupo Éxito</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Segoe UI',sans-serif; background:#f0f2f5; color:#222; }}
header {{ background:linear-gradient(135deg,#1F3864,#2E75B6); color:white; padding:20px 32px; display:flex; justify-content:space-between; align-items:center; }}
header h1 {{ font-size:22px; }}
header span {{ font-size:13px; opacity:.85; }}
.tabs {{ display:flex; background:#1F3864; padding:0 32px; overflow-x:auto; }}
.tab {{ padding:12px 22px; color:rgba(255,255,255,.7); cursor:pointer; font-size:14px; border-bottom:3px solid transparent; white-space:nowrap; transition:all .2s; }}
.tab.active {{ color:white; border-bottom-color:#FFD700; }}
.tab:hover {{ color:white; }}
.filters {{ background:white; padding:12px 32px; display:flex; gap:12px; flex-wrap:wrap; border-bottom:1px solid #e0e0e0; align-items:center; }}
.filters select {{ padding:7px 12px; border:1px solid #ddd; border-radius:6px; font-size:13px; }}
.filters label {{ font-size:13px; color:#555; }}
.content {{ padding:24px 32px; }}
.panel {{ display:none; }}
.panel.active {{ display:block; }}
.stats {{ display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap; }}
.stat {{ background:white; border-radius:10px; padding:16px 24px; flex:1; min-width:140px; box-shadow:0 2px 8px rgba(0,0,0,.07); border-left:4px solid #2E75B6; }}
.stat.green {{ border-left-color:#43a047; }}
.stat.orange {{ border-left-color:#fb8c00; }}
.stat.red {{ border-left-color:#e53935; }}
.stat.purple {{ border-left-color:#8e24aa; }}
.stat h3 {{ font-size:28px; font-weight:700; }}
.stat p {{ font-size:12px; color:#666; margin-top:4px; }}
.grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px; }}
.grid-3 {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px; margin-bottom:20px; }}
.card {{ background:white; border-radius:10px; padding:20px; box-shadow:0 2px 8px rgba(0,0,0,.07); }}
.card h3 {{ font-size:15px; font-weight:600; color:#1F3864; margin-bottom:16px; border-bottom:2px solid #e8f0fe; padding-bottom:8px; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#1F3864; color:white; padding:10px 12px; text-align:left; font-weight:600; }}
td {{ padding:9px 12px; border-bottom:1px solid #f0f0f0; }}
tr:hover td {{ background:#f5f8ff; }}
.badge {{ display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; }}
.badge-blue {{ background:#e3f0fb; color:#1565c0; }}
.badge-green {{ background:#e8f5e9; color:#2e7d32; }}
.badge-orange {{ background:#fff3e0; color:#e65100; }}
.badge-red {{ background:#fde8e8; color:#c62828; }}
.badge-purple {{ background:#f3e5f5; color:#6a1b9a; }}
.bar-container {{ margin:6px 0; }}
.bar-label {{ display:flex; justify-content:space-between; font-size:12px; margin-bottom:3px; }}
.bar-bg {{ background:#f0f0f0; border-radius:4px; height:12px; overflow:hidden; }}
.bar-fill {{ height:100%; border-radius:4px; transition:width .5s; }}
.no-data {{ text-align:center; padding:40px; color:#999; }}
@media(max-width:768px) {{ .grid-2,.grid-3 {{ grid-template-columns:1fr; }} .content {{ padding:16px; }} }}
footer {{ text-align:center; padding:20px; color:#888; font-size:12px; border-top:1px solid #e0e0e0; margin-top:20px; }}
</style>
</head>
<body>

<header>
  <div>
    <h1>📊 Dashboard Tecnologías — IT en Sitio</h1>
    <div>Grupo Éxito — Toshiba GCS Colombia</div>
  </div>
  <span>🕐 Actualizado: {datos['fecha']}</span>
</header>

<div class="tabs">
  <div class="tab active" onclick="showTab('backlog',this)">📦 Backlog por Tecnología</div>
  <div class="tab" onclick="showTab('regional',this)">🌎 Comparativa Regional</div>
  <div class="tab" onclick="showTab('tecnicos',this)">👤 Avance Técnicos</div>
  <div class="tab" onclick="showTab('semana',this)">📅 Tendencia Semanal</div>
  <div class="tab" onclick="showTab('antiguedad',this)">⏳ Antigüedad</div>
</div>

<div class="filters">
  <label>Regional:</label>
  <select id="filtro-regional" onchange="aplicarFiltros()">
    <option value="">Todas</option>
    {''.join(f'<option>{r}</option>' for r in REGIONALES)}
  </select>
  <label>Tecnología:</label>
  <select id="filtro-tec" onchange="aplicarFiltros()">
    <option value="">Todas</option>
  </select>
</div>

<div class="content">

  <!-- PANEL BACKLOG -->
  <div class="panel active" id="panel-backlog">
    <div class="stats">
      <div class="stat"><h3 id="stat-total">0</h3><p>Total tickets backlog</p></div>
      <div class="stat green"><h3 id="stat-tecs">0</h3><p>Tecnologías distintas</p></div>
      <div class="stat orange"><h3 id="stat-mayor">-</h3><p>Mayor backlog</p></div>
      <div class="stat purple"><h3 id="stat-regiones">4</h3><p>Regionales</p></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <h3>📦 Backlog por Tecnología</h3>
        <canvas id="chart-backlog-tec" height="280"></canvas>
      </div>
      <div class="card">
        <h3>🌎 Distribución por Regional y Tecnología</h3>
        <canvas id="chart-tec-reg" height="280"></canvas>
      </div>
    </div>
    <div class="card">
      <h3>📋 Detalle Backlog por Tecnología</h3>
      <table>
        <thead><tr><th>Tecnología</th><th>Tickets</th><th>% del total</th><th>Distribución</th></tr></thead>
        <tbody id="tabla-backlog"></tbody>
      </table>
    </div>
  </div>

  <!-- PANEL REGIONAL -->
  <div class="panel" id="panel-regional">
    <div class="grid-2">
      <div class="card">
        <h3>🌎 Tickets por Regional</h3>
        <canvas id="chart-regional" height="280"></canvas>
      </div>
      <div class="card">
        <h3>📊 % Asignación por Regional</h3>
        <canvas id="chart-asignacion" height="280"></canvas>
      </div>
    </div>
    <div class="card">
      <h3>📋 Comparativa de Regionales</h3>
      <table>
        <thead><tr><th>Regional</th><th>Total Tickets</th><th>Con Técnico</th><th>Sin Técnico</th><th>% Asignación</th></tr></thead>
        <tbody id="tabla-regional"></tbody>
      </table>
    </div>
    <br>
    <div class="card">
      <h3>🔧 Backlog por Tecnología y Regional</h3>
      <table>
        <thead><tr><th>Tecnología</th><th>CALI</th><th>MEDELLIN</th><th>COSTA</th><th>BOGOTA</th><th>Total</th></tr></thead>
        <tbody id="tabla-tec-reg"></tbody>
      </table>
    </div>
  </div>

  <!-- PANEL TÉCNICOS -->
  <div class="panel" id="panel-tecnicos">
    <div class="card">
      <h3>👤 Avance de Técnicos por Regional</h3>
      <table>
        <thead><tr><th>Regional</th><th>Técnico</th><th>Tickets asignados</th><th>Carga relativa</th></tr></thead>
        <tbody id="tabla-tecnicos"></tbody>
      </table>
    </div>
  </div>

  <!-- PANEL ANTIGÜEDAD -->
  <div class="panel" id="panel-antiguedad">
    <div class="stats">
      <div class="stat yellow" style="border-left-color:#f9a825"><h3 id="stat-ant-2-5">0</h3><p>🟡 2 a 5 días</p></div>
      <div class="stat orange" style="border-left-color:#fb8c00"><h3 id="stat-ant-5-10">0</h3><p>🟠 5 a 10 días</p></div>
      <div class="stat red"><h3 id="stat-ant-10">0</h3><p>🔴 Más de 10 días</p></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <h3>⏳ Antigüedad por Tecnología</h3>
        <canvas id="chart-ant-tec" height="280"></canvas>
      </div>
      <div class="card">
        <h3>🌎 Antigüedad por Regional</h3>
        <canvas id="chart-ant-reg" height="280"></canvas>
      </div>
    </div>
    <div class="card">
      <h3>📋 Detalle Tickets Antiguos</h3>
      <table>
        <thead><tr><th>ID</th><th>Título</th><th>Técnico</th><th>Regional</th><th>Tecnología</th><th>Días</th><th>Rango</th></tr></thead>
        <tbody id="tabla-antiguedad"></tbody>
      </table>
    </div>
  </div>

  <!-- PANEL SEMANA -->
  <div class="panel" id="panel-semana">
    <div class="card">
      <h3>📅 Tendencia de Backlog — Últimos 7 días</h3>
      <canvas id="chart-semana" height="120"></canvas>
    </div>
    <br>
    <div class="card">
      <h3>📋 Detalle por Día</h3>
      <table>
        <thead><tr><th>Fecha</th><th>Total Backlog</th><th>Variación</th></tr></thead>
        <tbody id="tabla-semana"></tbody>
      </table>
    </div>
  </div>

</div>

<footer>🤖 Bot desarrollado por el Ing. Javier Trujillo &nbsp;|&nbsp; IT en Sitio — Grupo Éxito &nbsp;|&nbsp; Actualizado: {datos['fecha']}</footer>

<script>
const DATA = {data_json};

const COLORES = [
  '#2E75B6','#43a047','#fb8c00','#e53935','#8e24aa',
  '#00897b','#f4511e','#1e88e5','#6d4c41','#546e7a'
];

let tabActual = 'backlog';
let charts = {{}};

// Poblar filtro tecnologías
DATA.tecnologias.forEach(t => {{
  const opt = document.createElement('option');
  opt.value = t; opt.text = t;
  document.getElementById('filtro-tec').appendChild(opt);
}});

function showTab(tab, el) {{
  tabActual = tab;
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + tab).classList.add('active');
  el.classList.add('active');
  renderTab(tab);
}}

function aplicarFiltros() {{ renderTab(tabActual); }}

function getFiltros() {{
  return {{
    regional: document.getElementById('filtro-regional').value,
    tec: document.getElementById('filtro-tec').value
  }};
}}

function filtrarDatos(rows, key_regional='Regional', key_tec='Tecnologia') {{
  const f = getFiltros();
  return rows.filter(r => {{
    const matchReg = !f.regional || r[key_regional] === f.regional;
    const matchTec = !f.tec || r[key_tec] === f.tec;
    return matchReg && matchTec;
  }});
}}

function destroyChart(id) {{
  if (charts[id]) {{ charts[id].destroy(); delete charts[id]; }}
}}

function renderTab(tab) {{
  if (tab === 'backlog') renderBacklog();
  else if (tab === 'regional') renderRegional();
  else if (tab === 'tecnicos') renderTecnicos();
  else if (tab === 'semana') renderSemana();
  else if (tab === 'antiguedad') renderAntiguedad();
}}

// ── BACKLOG ──
function renderBacklog() {{
  const f = getFiltros();
  let rows = DATA.backlog_tec;
  let rowsReg = DATA.backlog_tec_reg;

  if (f.regional) {{
    rowsReg = rowsReg.filter(r => r.Regional === f.regional);
    // Recalcular totales por tec
    const map = {{}};
    rowsReg.forEach(r => {{ map[r.Tecnologia] = (map[r.Tecnologia]||0) + r.total; }});
    rows = Object.entries(map).map(([t,v]) => ({{Tecnologia:t, total:v}}))
                  .sort((a,b) => b.total - a.total);
  }}
  if (f.tec) {{ rows = rows.filter(r => r.Tecnologia === f.tec); }}

  const total = rows.reduce((s,r) => s+r.total, 0);
  document.getElementById('stat-total').textContent = total;
  document.getElementById('stat-tecs').textContent = rows.length;
  document.getElementById('stat-mayor').textContent = rows[0]?.Tecnologia?.replace(/^[^ ]+ /,'') || '-';

  // Gráfico dona
  destroyChart('backlog-tec');
  charts['backlog-tec'] = new Chart(document.getElementById('chart-backlog-tec'), {{
    type: 'doughnut',
    data: {{
      labels: rows.map(r => r.Tecnologia),
      datasets: [{{ data: rows.map(r => r.total), backgroundColor: COLORES }}]
    }},
    options: {{ plugins: {{ legend: {{ position:'right', labels:{{font:{{size:11}}}} }} }}, cutout:'60%' }}
  }});

  // Gráfico barras por regional
  const regionales = ['CALI','MEDELLIN','COSTA','BOGOTA'];
  const tecnologias = rows.map(r => r.Tecnologia);
  let rowsRegFilt = f.tec ? DATA.backlog_tec_reg.filter(r => r.Tecnologia === f.tec) : DATA.backlog_tec_reg;
  if (f.regional) rowsRegFilt = rowsRegFilt.filter(r => r.Regional === f.regional);

  const datasets = regionales.map((reg, i) => ({{
    label: reg,
    data: tecnologias.map(t => {{
      const found = rowsRegFilt.find(r => r.Tecnologia===t && r.Regional===reg);
      return found ? found.total : 0;
    }}),
    backgroundColor: COLORES[i]
  }}));

  destroyChart('tec-reg');
  charts['tec-reg'] = new Chart(document.getElementById('chart-tec-reg'), {{
    type: 'bar',
    data: {{ labels: tecnologias.map(t => t.replace(/^[^ ]+ /,'')), datasets }},
    options: {{ plugins:{{legend:{{position:'top'}}}}, scales:{{x:{{stacked:true}},y:{{stacked:true}}}} }}
  }});

  // Tabla
  const tbody = document.getElementById('tabla-backlog');
  tbody.innerHTML = '';
  rows.forEach(r => {{
    const pct = total > 0 ? ((r.total/total)*100).toFixed(1) : 0;
    const color = COLORES[rows.indexOf(r) % COLORES.length];
    tbody.innerHTML += `<tr>
      <td>${{r.Tecnologia}}</td>
      <td><b>${{r.total}}</b></td>
      <td>${{pct}}%</td>
      <td>
        <div class="bar-bg"><div class="bar-fill" style="width:${{pct}}%;background:${{color}}"></div></div>
      </td>
    </tr>`;
  }});
}}

// ── REGIONAL ──
function renderRegional() {{
  const f = getFiltros();
  let comp = DATA.comp_regional;
  if (f.regional) comp = comp.filter(r => r.Regional === f.regional);

  destroyChart('regional');
  charts['regional'] = new Chart(document.getElementById('chart-regional'), {{
    type: 'bar',
    data: {{
      labels: comp.map(r => r.Regional),
      datasets: [{{
        label: 'Total tickets', data: comp.map(r => r.total),
        backgroundColor: COLORES
      }}]
    }},
    options: {{ plugins:{{legend:{{display:false}}}} }}
  }});

  destroyChart('asignacion');
  charts['asignacion'] = new Chart(document.getElementById('chart-asignacion'), {{
    type: 'bar',
    data: {{
      labels: comp.map(r => r.Regional),
      datasets: [
        {{ label: 'Con técnico', data: comp.map(r => r.con_tecnico), backgroundColor:'#43a047' }},
        {{ label: 'Sin técnico', data: comp.map(r => r.total - r.con_tecnico), backgroundColor:'#e53935' }}
      ]
    }},
    options: {{ scales:{{x:{{stacked:true}},y:{{stacked:true}}}} }}
  }});

  const tbody = document.getElementById('tabla-regional');
  tbody.innerHTML = '';
  comp.forEach(r => {{
    const sin = r.total - r.con_tecnico;
    const pct = r.total > 0 ? ((r.con_tecnico/r.total)*100).toFixed(1) : 0;
    const badge = pct >= 80 ? 'green' : pct >= 50 ? 'orange' : 'red';
    tbody.innerHTML += `<tr>
      <td><b>${{r.Regional}}</b></td>
      <td>${{r.total}}</td>
      <td>${{r.con_tecnico}}</td>
      <td>${{sin}}</td>
      <td><span class="badge badge-${{badge}}">${{pct}}%</span></td>
    </tr>`;
  }});

  // Tabla cruzada tec x regional
  let tecReg = DATA.backlog_tec_reg;
  if (f.tec) tecReg = tecReg.filter(r => r.Tecnologia === f.tec);
  const tecs = [...new Set(tecReg.map(r => r.Tecnologia))].sort();
  const tbody2 = document.getElementById('tabla-tec-reg');
  tbody2.innerHTML = '';
  tecs.forEach(t => {{
    const get = reg => tecReg.find(r=>r.Tecnologia===t&&r.Regional===reg)?.total || 0;
    const total = ['CALI','MEDELLIN','COSTA','BOGOTA'].reduce((s,reg)=>s+get(reg),0);
    tbody2.innerHTML += `<tr>
      <td>${{t}}</td>
      <td>${{get('CALI')}}</td><td>${{get('MEDELLIN')}}</td>
      <td>${{get('COSTA')}}</td><td>${{get('BOGOTA')}}</td>
      <td><b>${{total}}</b></td>
    </tr>`;
  }});
}}

// ── TÉCNICOS ──
function renderTecnicos() {{
  const f = getFiltros();
  let rows = DATA.tecnicos;
  if (f.regional) rows = rows.filter(r => r.Regional === f.regional);

  // Max por regional para barra relativa
  const maxPorReg = {{}};
  rows.forEach(r => {{ maxPorReg[r.Regional] = Math.max(maxPorReg[r.Regional]||0, r.tickets); }});

  const tbody = document.getElementById('tabla-tecnicos');
  tbody.innerHTML = '';

  const ordenado = [...rows].sort((a,b) => b.tickets - a.tickets);
  ordenado.forEach(r => {{
    const pct = maxPorReg[r.Regional] > 0 ? ((r.tickets/maxPorReg[r.Regional])*100).toFixed(0) : 0;
    const color = pct >= 80 ? '#e53935' : pct >= 50 ? '#fb8c00' : '#43a047';
    const badge = r.Regional;
    tbody.innerHTML += `<tr>
      <td><span class="badge badge-blue">${{r.Regional}}</span></td>
      <td>${{r.Tecnico}}</td>
      <td><b>${{r.tickets}}</b></td>
      <td style="width:200px">
        <div class="bar-label"><span>${{pct}}% de la carga máx.</span></div>
        <div class="bar-bg"><div class="bar-fill" style="width:${{pct}}%;background:${{color}}"></div></div>
      </td>
    </tr>`;
  }});
}}

// ── SEMANA ──
function renderSemana() {{
  const rows = DATA.semana;
  destroyChart('semana');
  charts['semana'] = new Chart(document.getElementById('chart-semana'), {{
    type: 'line',
    data: {{
      labels: rows.map(r => r.fecha),
      datasets: [{{
        label: 'Backlog total',
        data: rows.map(r => r.total),
        borderColor: '#2E75B6',
        backgroundColor: 'rgba(46,117,182,0.1)',
        tension: 0.4,
        fill: true,
        pointRadius: 5,
        pointBackgroundColor: '#2E75B6'
      }}]
    }},
    options: {{ plugins:{{legend:{{display:false}}}}, scales:{{y:{{beginAtZero:false}}}} }}
  }});

  const tbody = document.getElementById('tabla-semana');
  tbody.innerHTML = '';
  rows.forEach((r, i) => {{
    const prev = i > 0 ? rows[i-1].total : null;
    const diff = prev !== null ? r.total - prev : null;
    const varStr = diff === null ? '-' :
      diff > 0 ? `<span style="color:#e53935">▲ ${{diff}}</span>` :
      diff < 0 ? `<span style="color:#43a047">▼ ${{Math.abs(diff)}}</span>` :
      `<span style="color:#888">— 0</span>`;
    tbody.innerHTML += `<tr><td>${{r.fecha}}</td><td><b>${{r.total}}</b></td><td>${{varStr}}</td></tr>`;
  }});
}}

// ── ANTIGÜEDAD ──
function renderAntiguedad() {{
  const f = getFiltros();

  let antTec = DATA.ant_tec;
  let antReg = DATA.ant_reg;
  let detalle = DATA.detalle_ant;

  // Guardar detalle completo para contadores antes de filtrar
  let detalle_completo = [...detalle];
  if (f.regional) detalle_completo = detalle_completo.filter(r => r.Regional === f.regional);
  if (f.tec) detalle_completo = detalle_completo.filter(r => r.Tecnologia === f.tec);

  if (f.regional) {{
    antTec = []; // recalcular desde detalle
    detalle = detalle.filter(r => r.Regional === f.regional);
    // reagrupar
    const map = {{}};
    detalle.forEach(r => {{
      const k = r.Tecnologia + '|' + r.rango;
      map[k] = (map[k]||0) + 1;
    }});
    Object.entries(map).forEach(([k,v]) => {{
      const [t,rg] = k.split('|');
      antTec.push({{Tecnologia:t, rango:rg, total:v}});
    }});
    antReg = antReg.filter(r => r.Regional === f.regional);
  }}
  if (f.tec) {{
    antReg = [];
    detalle = detalle.filter(r => r.Tecnologia === f.tec);
    const map = {{}};
    detalle.forEach(r => {{
      const k = r.Regional + '|' + r.rango;
      map[k] = (map[k]||0) + 1;
    }});
    Object.entries(map).forEach(([k,v]) => {{
      const [rg, ra] = k.split('|');
      antReg.push({{Regional:rg, rango:ra, total:v}});
    }});
    antTec = antTec.filter(r => r.Tecnologia === f.tec);
  }}

  // Contadores — usar todos los datos filtrados por regional y tec
  const rangos = ['2-5 dias','5-10 dias','+10 dias'];
  const cnt = {{'2-5 dias':0,'5-10 dias':0,'+10 dias':0}};
  detalle_completo.forEach(r => {{ if(cnt[r.rango] !== undefined) cnt[r.rango]++; }});
  document.getElementById('stat-ant-2-5').textContent  = cnt['2-5 dias'];
  document.getElementById('stat-ant-5-10').textContent = cnt['5-10 dias'];
  document.getElementById('stat-ant-10').textContent   = cnt['+10 dias'];

  // Chart por tecnología
  const tecs = [...new Set(antTec.map(r=>r.Tecnologia))].sort();
  destroyChart('ant-tec');
  charts['ant-tec'] = new Chart(document.getElementById('chart-ant-tec'), {{
    type: 'bar',
    data: {{
      labels: tecs.map(t => t.replace(/^[^ ]+ /,'')),
      datasets: rangos.map((rg,i) => ({{
        label: rg,
        data: tecs.map(t => antTec.find(r=>r.Tecnologia===t&&r.rango===rg)?.total||0),
        backgroundColor: ['#f9a825','#fb8c00','#e53935'][i]
      }}))
    }},
    options: {{ scales:{{x:{{stacked:true}},y:{{stacked:true}}}} }}
  }});

  // Chart por regional
  const regs = [...new Set(antReg.map(r=>r.Regional))].sort();
  destroyChart('ant-reg');
  charts['ant-reg'] = new Chart(document.getElementById('chart-ant-reg'), {{
    type: 'bar',
    data: {{
      labels: regs,
      datasets: rangos.map((rg,i) => ({{
        label: rg,
        data: regs.map(r => antReg.find(x=>x.Regional===r&&x.rango===rg)?.total||0),
        backgroundColor: ['#f9a825','#fb8c00','#e53935'][i]
      }}))
    }},
    options: {{ scales:{{x:{{stacked:true}},y:{{stacked:true}}}} }}
  }});

  // Tabla detalle
  const tbody = document.getElementById('tabla-antiguedad');
  tbody.innerHTML = '';
  detalle.sort((a,b) => b.dias_abierto - a.dias_abierto).forEach(r => {{
    const color = r.rango === '+10 dias' ? 'red' : r.rango === '5-10 dias' ? 'orange' : 'yellow';
    tbody.innerHTML += `<tr>
      <td><b>#${{r.ID}}</b></td>
      <td>${{(r.Título||'').substring(0,50)}}</td>
      <td>${{r.Tecnico||'Sin asignar'}}</td>
      <td><span class="badge badge-blue">${{r.Regional}}</span></td>
      <td>${{r.Tecnologia}}</td>
      <td><b>${{r.dias_abierto}}</b></td>
      <td><span class="badge badge-${{color}}">${{r.rango}}</span></td>
    </tr>`;
  }});
}}

// Render inicial
renderBacklog();
</script>
</body>
</html>"""

    return html


def publicar_dashboard(html):
    """Guarda y publica el dashboard en GitHub Pages."""
    os.makedirs(os.path.dirname(ARCHIVO_SALIDA), exist_ok=True)

    with open(ARCHIVO_SALIDA, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Dashboard guardado: {ARCHIVO_SALIDA}")

    try:
        subprocess.run(["git", "-C", REPO_DASHBOARD, "add", "index.html"], check=True)
        subprocess.run(["git", "-C", REPO_DASHBOARD, "commit", "-m",
            f"Dashboard actualizado {datetime.now().strftime('%d/%m/%Y %H:%M')}"], check=True)
        subprocess.run(["git", "-C", REPO_DASHBOARD, "push"], check=True)
        print("✅ Dashboard publicado en GitHub Pages")
        print("🌐 URL: https://javi544.github.io/dashboard-tecnologias-exito/")
    except Exception as e:
        print(f"⚠️  Error publicando: {e}")


def main():
    print("\n" + "="*55)
    print("📊 GENERANDO DASHBOARD TECNOLOGÍAS")
    print("="*55)

    df = leer_todos_los_csv()

    if df.empty:
        print("⚠️  No se encontraron datos CSV")
        return

    print(f"\nTotal tickets: {len(df)}")
    datos = preparar_datos(df)
    html  = generar_html(datos)
    publicar_dashboard(html)


if __name__ == "__main__":
    main()