import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import shutil
import os
import datetime
import io
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.colors as mcolors
import matplotlib.cm as cm

# --- Page Configuration ---
st.set_page_config(
    page_title="Dashboard - Sistemad BDIV",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS ---
st.markdown("""
    <style>
    .main { background-color: #0E1117; color: #FAFAFA; }
    .stMetric { background-color: #262730; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .stMetric label { color: #A0AEC0 !important; font-size: 14px !important; }
    div[data-testid="stMetricValue"] > div { color: #FAFAFA !important; font-weight: bold; }
    h1, h2, h3 { color: #E2E8F0; font-family: 'Inter', sans-serif; }
    </style>
""", unsafe_allow_html=True)

SHEET_ID = '1_orYCWD4Z81gaOxhJZh4AF9iICAcpiDIM4NlJwDLxu8'
@st.cache_data(ttl=10)
def load_data():
    try:
        url_sol = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Solicitudes'
        url_hist = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Historial_Estados'
        
        df_sol = pd.read_csv(url_sol)
        df_hist = pd.read_csv(url_hist)
        
        # Eliminar filas completamente vacías
        df_sol = df_sol.dropna(how='all')
        df_hist = df_hist.dropna(how='all')
        
        # Asegurar que los IDs sean enteros o válidos
        if 'id_solicitud' in df_sol.columns:
            df_sol['id_solicitud'] = pd.to_numeric(df_sol['id_solicitud'], errors='coerce')
        if 'id_solicitud' in df_hist.columns:
            df_hist['id_solicitud'] = pd.to_numeric(df_hist['id_solicitud'], errors='coerce')
            
    except Exception as e:
        st.error(f"Error leyendo Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame()
            
    return df_sol, df_hist
df_sol, df_hist = load_data()
if not df_sol.empty and not df_hist.empty:
    # --- PROCESAMIENTO GENERAL ---
    hist_cierres = df_hist[df_hist['estado_destino_id'] == 'Cerrada'].copy()
    cierres_reales = hist_cierres.groupby('id_solicitud')['fecha_cambio'].max().reset_index()
    cierres_reales.rename(columns={'fecha_cambio': 'Fecha_Cierre_Real'}, inplace=True)
    df_sol = pd.merge(df_sol, cierres_reales, on='id_solicitud', how='left')
    
    df_sol['fecha_compromiso'] = pd.to_datetime(df_sol['fecha_compromiso'], errors='coerce', dayfirst=True)
    df_sol['Fecha_Cierre_Real'] = pd.to_datetime(df_sol['Fecha_Cierre_Real'], errors='coerce', dayfirst=True)
    df_sol['fecha_solicitud'] = pd.to_datetime(df_sol['fecha_solicitud'], errors='coerce', dayfirst=True)
    df_sol['fecha_cierre'] = pd.to_datetime(df_sol['fecha_cierre'], errors='coerce', dayfirst=True)
    
    def get_cumplimiento(row):
        if pd.isnull(row['fecha_compromiso']): return "Sin Compromiso"
        if row['estado_actual'] != 'Cerrada':
            return "En Plazo" if datetime.datetime.now() <= row['fecha_compromiso'] else "Atrasado (Abierto)"
        else:
            # Si está cerrada, evaluar contra la fecha de cierre real (o fecha_cierre)
            fecha_cierre_final = row['Fecha_Cierre_Real'] if pd.notnull(row['Fecha_Cierre_Real']) else row['fecha_cierre']
            if pd.isnull(fecha_cierre_final):
                return "Cerrada (Sin Fecha)"
            return "Cumple" if fecha_cierre_final <= row['fecha_compromiso'] else "No Cumple"
            
    df_sol['Estado_Cumplimiento'] = df_sol.apply(get_cumplimiento, axis=1)

    # --- NAVEGACIÓN SIDEBAR ---
    st.sidebar.title("Navegación")
    st.sidebar.markdown("Selecciona la vista del Dashboard:")
    pagina = st.sidebar.radio(
        "Páginas:",
        ["Dashboard: Qualisys", "Dashboard: Intranet", "Gantt: Historial Estados"],
        index=1
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Exportar Reporte")

    if st.sidebar.button("⚙️ Generar Imagen .PNG"):
        with st.spinner("Dibujando reporte idéntico al dashboard..."):
            
            # Crear figura gigante y ancha
            fig = plt.figure(figsize=(20, 32))
            fig.patch.set_facecolor('white')
            
            # Grilla maestra: 10 filas, 2 columnas (simulando la estructura de tu web)
            gs = fig.add_gridspec(10, 2, height_ratios=[0.5, 1.5, 4, 4, 0.5, 0.5, 1.5, 4, 4, 0.5], hspace=0.6, wspace=0.2)
            
            def dibujar_sistema(sys_name, ax_title, ax_kpi, ax_hbar, ax_combo, ax_vbar):
                dfs = df_sol[df_sol['sistema_id'] == sys_name]
                
                # --- 0. TÍTULO ---
                ax_title.axis('off')
                ax_title.text(0, 0.5, f"🚀 Requerimientos Sistemas BDIV - {sys_name}", 
                              ha='left', va='center', fontsize=30, fontweight='bold', color='#1f2937')
                
                # --- 1. TARJETAS DE KPIs (Estilo Streamlit) ---
                ax_kpi.axis('off')
                ax_kpi.text(0, 1.05, "Resumen de Solicitudes", transform=ax_kpi.transAxes, fontsize=18, fontweight='bold', color='#4b5563')
                
                ing = len(dfs)
                pend = len(dfs[dfs['estado_actual'].isin(['Registrada', 'Priorizada'])])
                des = len(dfs[dfs['estado_actual'] == 'En desarrollo'])
                pru = len(dfs[dfs['estado_actual'] == 'En pruebas'])
                val = len(dfs[dfs['estado_actual'] == 'Esperando validación'])
                prd = len(dfs[dfs['estado_actual'] == 'Lista para producción'])
                imp = len(dfs[dfs['estado_actual'] == 'Cerrada'])
                
                labels = ["Ingresados", "Pendientes", "En Desarrollo", "En Pruebas", "Espera Val.", "Listo PRD", "Implementados"]
                values = [ing, pend, des, pru, val, prd, imp]
                num_cards = len(labels)
                
                for i in range(num_cards):
                    x = i / num_cards + 0.003
                    w = (1 / num_cards) - 0.01
                    # Dibujar el fondo negro redondeado de la tarjeta
                    rect = patches.FancyBboxPatch((x, 0.05), w, 0.9, transform=ax_kpi.transAxes, boxstyle="round,pad=0.01,rounding_size=0.04", facecolor='#1f2937', edgecolor='none')
                    ax_kpi.add_patch(rect)
                    # Textos dentro de la tarjeta
                    ax_kpi.text(x + 0.01, 0.7, labels[i], transform=ax_kpi.transAxes, color='#9ca3af', fontsize=12, va='center')
                    ax_kpi.text(x + 0.01, 0.35, str(values[i]), transform=ax_kpi.transAxes, color='white', fontsize=32, fontweight='bold', va='center')

                # --- 2. GRÁFICO: Recuento por Estado ---
                ax_hbar.set_title("Recuento por Estado Actual", loc='left', fontsize=12, fontweight='bold', color='#4b5563', pad=15)
                est_counts = dfs['estado_actual'].value_counts().sort_values(ascending=True)
                if not est_counts.empty:
                    bars = ax_hbar.barh(est_counts.index, est_counts.values, color='#0f4a8e')
                    for bar in bars:
                        val_bar = int(bar.get_width())
                        if val_bar > 0:
                            ax_hbar.text(val_bar - (val_bar*0.02), bar.get_y() + bar.get_height()/2, str(val_bar), ha='right', va='center', color='white', fontweight='bold', fontsize=10)
                ax_hbar.spines['top'].set_visible(False)
                ax_hbar.spines['right'].set_visible(False)
                ax_hbar.tick_params(axis='y', colors='#4b5563')
                
                # --- 3. GRÁFICO: Ingresados vs Implementados ---
                ax_combo.set_title("Ingresados vs. Implementados por Mes", loc='left', fontsize=12, fontweight='bold', color='#4b5563', pad=15)
                df_i = dfs.dropna(subset=['fecha_solicitud']).copy()
                df_i['Mes'] = df_i['fecha_solicitud'].dt.to_period('M').astype(str)
                ingresos = df_i.groupby('Mes').size().reset_index(name='Ingresados')
                
                df_c = dfs.dropna(subset=['fecha_cierre']).copy()
                df_c['Mes'] = df_c['fecha_cierre'].dt.to_period('M').astype(str)
                implementados = df_c.groupby('Mes').size().reset_index(name='Implementados')
                
                meses_df = pd.merge(ingresos, implementados, on='Mes', how='outer').fillna(0).sort_values('Mes')
                if not meses_df.empty:
                    x_pos = range(len(meses_df))
                    ax_combo.bar(x_pos, meses_df['Ingresados'], color='#3182ce', label='Ingresados')
                    ax_combo.plot(x_pos, meses_df['Implementados'], color='#38a169', marker='o', linewidth=2, label='Implementados')
                    ax_combo.set_xticks(x_pos)
                    ax_combo.set_xticklabels(meses_df['Mes'], rotation=45, ha='right', color='#4b5563')
                    ax_combo.legend(frameon=False, loc='upper right', labelcolor='#4b5563')
                ax_combo.spines['top'].set_visible(False)
                ax_combo.spines['right'].set_visible(False)

                # --- 4. GRÁFICO: Tiempos de Resolución ---
                ax_vbar.set_title("⏱ Tiempos de Resolución", loc='left', fontsize=18, fontweight='bold', color='#4b5563', pad=25)
                ax_vbar.text(0, 1.05, "Promedio de Días que pasa una solicitud en cada estado", transform=ax_vbar.transAxes, fontsize=11, color='#6b7280')
                
                dft = dfs.copy()
                fecha_limite = pd.to_datetime((datetime.datetime.now() - datetime.timedelta(days=90)).date())
                dft['fecha_solicitud_dt'] = pd.to_datetime(dft['fecha_solicitud'], errors='coerce', dayfirst=True)
                dft = dft[dft['fecha_solicitud_dt'] >= fecha_limite]
                
                dfh = df_hist.copy()
                dfh['fecha_cambio'] = pd.to_datetime(dfh['fecha_cambio'], errors='coerce', dayfirst=True)
                
                estado_durations = []
                for sol_id in dft['id_solicitud'].unique():
                    hist_sol = dfh[dfh['id_solicitud'] == sol_id].sort_values('fecha_cambio')
                    if hist_sol.empty: continue
                    sol_info = dft[dft['id_solicitud'] == sol_id].iloc[0]
                    last_date = sol_info['fecha_solicitud_dt']
                    for index, row in hist_sol.iterrows():
                        estado = row['estado_origen_id']
                        fecha_fin = row['fecha_cambio']
                        if pd.notnull(last_date) and pd.notnull(fecha_fin):
                            if fecha_fin < last_date: fecha_fin = last_date + datetime.timedelta(days=1)
                            dias = (fecha_fin - last_date).days
                            if estado != 'Pausada': estado_durations.append({'Estado': estado, 'Dias': dias})
                        last_date = fecha_fin
                    estado_actual = sol_info['estado_actual']
                    if estado_actual not in ['Cerrada', 'Anulada', 'Cancelada', 'Pausada']:
                        fecha_fin_actual = datetime.datetime.now()
                        if pd.notnull(last_date):
                            if fecha_fin_actual < last_date: fecha_fin_actual = last_date + datetime.timedelta(days=1)
                            dias = (fecha_fin_actual - last_date).days
                            estado_durations.append({'Estado': estado_actual, 'Dias': dias})
                
                if estado_durations:
                    df_dur = pd.DataFrame(estado_durations)
                    df_avg_dur = df_dur.groupby('Estado')['Dias'].mean().reset_index().sort_values('Dias', ascending=False)
                    df_avg_dur['Dias'] = df_avg_dur['Dias'].round(1)
                    
                    cmap = plt.get_cmap('Purples')
                    if df_avg_dur['Dias'].max() > 0:
                        norm = mcolors.Normalize(vmin=0, vmax=df_avg_dur['Dias'].max())
                        colors = [cmap(norm(v)*0.5 + 0.5) for v in df_avg_dur['Dias']]
                    else:
                        colors = [cmap(0.5)] * len(df_avg_dur)
                        
                    bars = ax_vbar.bar(df_avg_dur['Estado'], df_avg_dur['Dias'], color=colors)
                    for bar in bars:
                        yval = bar.get_height()
                        ax_vbar.text(bar.get_x() + bar.get_width()/2, yval + (yval*0.02), str(yval), ha='center', va='bottom', color='#4b5563', fontweight='bold', fontsize=11)
                    
                    ax_vbar.spines['top'].set_visible(False)
                    ax_vbar.spines['right'].set_visible(False)
                    ax_vbar.set_ylabel("Días", color='#6b7280')
                    ax_vbar.tick_params(axis='x', colors='#6b7280', labelsize=11)
                    ax_vbar.tick_params(axis='y', colors='#6b7280')
                else:
                    ax_vbar.text(0.5, 0.5, "Sin datos recientes", ha='center', va='center')
                    ax_vbar.axis('off')

            # --- ASIGNAR BLOQUES AL LIENZO ---
            # Intranet
            ax_t_int = fig.add_subplot(gs[0, :]) # Título arriba
            ax_k_int = fig.add_subplot(gs[1, :]) # KPIs abajo de título
            ax_h_int = fig.add_subplot(gs[2, 0]) # Barras horizontales (Izquierda)
            ax_c_int = fig.add_subplot(gs[2, 1]) # Combo Lineas (Derecha)
            ax_v_int = fig.add_subplot(gs[3, :]) # Barras verticales abajo ocupando todo
            dibujar_sistema("Intranet", ax_t_int, ax_k_int, ax_h_int, ax_c_int, ax_v_int)
            
            # Qualisys
            ax_t_qua = fig.add_subplot(gs[5, :])
            ax_k_qua = fig.add_subplot(gs[6, :])
            ax_h_qua = fig.add_subplot(gs[7, 0])
            ax_c_qua = fig.add_subplot(gs[7, 1])
            ax_v_qua = fig.add_subplot(gs[8, :])
            dibujar_sistema("Qualisys", ax_t_qua, ax_k_qua, ax_h_qua, ax_c_qua, ax_v_qua)
            
            # --- CONVERTIR A IMAGEN ---
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
            img_bytes = buf.getvalue()
            plt.close(fig)
            
            st.sidebar.success("¡Imagen Maestra Generada!")
            st.sidebar.download_button(
                label="⬇️ Descargar Reporte (.PNG)",
                data=img_bytes,
                file_name=f"Reporte_Sistemas_{datetime.datetime.now().strftime('%d_%m_%Y')}.png",
                mime="image/png"
            )
    
    # --- RENDERIZADO DE PÁGINAS ---
    if pagina.startswith("Dashboard"):
        st.title(f"🚀 Requerimientos Sistemas BDIV - {pagina.split(': ')[1]}")
        
        # Filtrar datos por sistema
        df_view = df_sol.copy()
        if "Qualisys" in pagina:
            df_view = df_view[df_view['sistema_id'] == 'Qualisys']
        elif "Intranet" in pagina:
            df_view = df_view[df_view['sistema_id'] == 'Intranet']
            
        if df_view.empty:
            st.warning("No hay datos para este sistema.")
        else:
            # --- KPIs ---
            st.markdown("### Resumen de Solicitudes")
            # Cambiamos a 7 columnas para hacer espacio al nuevo estado
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            
            ingresados = len(df_view)
            pendientes = len(df_view[df_view['estado_actual'].isin(['Registrada', 'Priorizada'])])
            en_desarrollo = len(df_view[df_view['estado_actual'] == 'En desarrollo'])
            en_pruebas = len(df_view[df_view['estado_actual'] == 'En pruebas'])
            esperando_val = len(df_view[df_view['estado_actual'] == 'Esperando validación'])
            listo_prd = len(df_view[df_view['estado_actual'] == 'Lista para producción'])
            implementados = len(df_view[df_view['estado_actual'] == 'Cerrada'])
            
            col1.metric("Ingresados", ingresados)
            col2.metric("Pendientes", pendientes)
            col3.metric("En Desarrollo", en_desarrollo)
            col4.metric("En Pruebas", en_pruebas)
            col5.metric("Espera Val.", esperando_val)
            col6.metric("Listo PRD", listo_prd)
            col7.metric("Implementados", implementados)
            
            st.markdown("---")
            
            # --- GRÁFICOS GENERALES ---
            row1_c1, row1_c2 = st.columns(2)
            with row1_c1:
                estados_counts = df_view['estado_actual'].value_counts().reset_index()
                estados_counts.columns = ['Estado', 'Cantidad']
                fig_estados = px.bar(
                    estados_counts, y='Estado', x='Cantidad', orientation='h', 
                    title='Recuento por Estado Actual', text='Cantidad', color='Cantidad', color_continuous_scale='Blues'
                )
                fig_estados.update_layout(yaxis={'categoryorder':'total ascending'}, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white', margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig_estados, use_container_width=True)
                
            with row1_c2:
                # Arreglo lógico para el gráfico de Ingresados vs Implementados
                df_ing = df_view.dropna(subset=['fecha_solicitud']).copy()
                df_ing['Mes'] = df_ing['fecha_solicitud'].dt.to_period('M').astype(str)
                ingresos = df_ing.groupby('Mes').size().reset_index(name='Ingresados')
                
                df_cierre = df_view.dropna(subset=['fecha_cierre']).copy()
                df_cierre['Mes'] = df_cierre['fecha_cierre'].dt.to_period('M').astype(str)
                implementados_df = df_cierre.groupby('Mes').size().reset_index(name='Implementados')
                
                meses_df = pd.merge(ingresos, implementados_df, on='Mes', how='outer').fillna(0).sort_values('Mes')
                
                fig_meses = go.Figure()
                fig_meses.add_trace(go.Bar(x=meses_df['Mes'], y=meses_df['Ingresados'], name='Ingresados', marker_color='#3182ce'))
                fig_meses.add_trace(go.Scatter(x=meses_df['Mes'], y=meses_df['Implementados'], name='Implementados', mode='lines+markers', line=dict(color='#38a169', width=3)))
                fig_meses.update_layout(title='Ingresados vs. Implementados por Mes', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white', margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig_meses, use_container_width=True)
                
            st.markdown("---")
            
            # --- PROMEDIO DE DÍAS POR ESTADO ---
            st.markdown("### ⏱️ Tiempos de Resolución")
            
            # Usar columnas para poner los filtros lado a lado
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                prioridad_grafico = st.selectbox(
                    "Filtrar gráfico por Prioridad:", 
                    ["Todas", "Crítico", "Alta", "Media", "Baja"],
                    key="filtro_prioridad_tiempos"
                )
                
            with col_f2:
                # Fecha por defecto: últimos 3 meses (90 días atrás)
                default_date = (datetime.datetime.now() - datetime.timedelta(days=90)).date()
                mes_desde = st.date_input(
                    "Ingresadas desde:", 
                    value=default_date,
                    key="filtro_fecha_tiempos"
                )
            
            # Crear copia de datos
            df_tiempos = df_view.copy()
            
            # Convertir fechas para el cálculo
            df_tiempos['fecha_solicitud_dt'] = pd.to_datetime(df_tiempos['fecha_solicitud'], errors='coerce', dayfirst=True)
            df_hist['fecha_cambio'] = pd.to_datetime(df_hist['fecha_cambio'], errors='coerce', dayfirst=True)
            
            # Aplicar filtro de fecha (desde el mes/día seleccionado en adelante)
            if pd.notnull(mes_desde):
                mes_desde_dt = pd.to_datetime(mes_desde)
                df_tiempos = df_tiempos[df_tiempos['fecha_solicitud_dt'] >= mes_desde_dt]
            
            # Aplicar filtro de prioridad
            if prioridad_grafico != "Todas":
                df_tiempos = df_tiempos[df_tiempos['prioridad'] == prioridad_grafico]
            
            estado_durations = []
            
            for sol_id in df_tiempos['id_solicitud'].unique():
                hist_sol = df_hist[df_hist['id_solicitud'] == sol_id].sort_values('fecha_cambio')
                if hist_sol.empty: continue
                
                sol_info = df_tiempos[df_tiempos['id_solicitud'] == sol_id].iloc[0]
                last_date = sol_info['fecha_solicitud_dt']
                
                for index, row in hist_sol.iterrows():
                    estado = row['estado_origen_id']
                    fecha_fin = row['fecha_cambio']
                    if pd.notnull(last_date) and pd.notnull(fecha_fin):
                        if fecha_fin < last_date: # Corregir desfases de fechas
                            fecha_fin = last_date + datetime.timedelta(days=1)
                        dias = (fecha_fin - last_date).days
                        
                        # EXCLUIR PAUSADA del historial
                        if estado != 'Pausada': 
                            estado_durations.append({'Estado': estado, 'Dias': dias})
                            
                    last_date = fecha_fin
                    
                # Sumar el tiempo que lleva en el estado actual (si no está cerrada ni pausada)
                estado_actual = sol_info['estado_actual']
                if estado_actual not in ['Cerrada', 'Anulada', 'Cancelada', 'Pausada']:
                    fecha_fin_actual = datetime.datetime.now()
                    if pd.notnull(last_date):
                        if fecha_fin_actual < last_date:
                            fecha_fin_actual = last_date + datetime.timedelta(days=1)
                        dias = (fecha_fin_actual - last_date).days
                        estado_durations.append({'Estado': estado_actual, 'Dias': dias})
            
            if estado_durations:
                df_dur = pd.DataFrame(estado_durations)
                df_avg_dur = df_dur.groupby('Estado')['Dias'].mean().reset_index()
                df_avg_dur['Dias'] = df_avg_dur['Dias'].round(1) # Redondear a 1 decimal
                
                fig_avg = px.bar(
                    df_avg_dur, x='Estado', y='Dias',
                    title='Promedio de Días que pasa una solicitud en cada estado', 
                    text='Dias', color='Dias', color_continuous_scale='Purp'
                )
                fig_avg.update_layout(xaxis={'categoryorder':'total descending'}, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white', margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig_avg, use_container_width=True)
            else:
                st.info("No hay suficientes datos de historial para calcular los promedios con los filtros seleccionados.")
                
            st.markdown("---")
            
            # --- TABLA: ALTA PRIORIDAD ---
            st.markdown("### 🚨 Solicitudes Críticas o de Alta Prioridad Pendientes")
            df_prioridad = df_view[
                (df_view['prioridad'].isin(['Crítico', 'Alta'])) & (df_view['estado_actual'] != 'Cerrada')
            ][['id_solicitud', 'titulo_solicitud', 'estado_actual', 'prioridad', 'fecha_compromiso', 'Estado_Cumplimiento']]
            
            def style_table(row):
                bg_prioridad = "background-color: #e53e3e; color: white" if row['prioridad'] == 'Crítico' else "background-color: #dd6b20; color: white"
                val_cump = row['Estado_Cumplimiento']
                color_cump = "color: #fc8181" if "Atrasado" in val_cump or "No Cumple" in val_cump else "color: #68d391" if val_cump == "Cumple" else "color: #f6e05e" if val_cump == "En Plazo" else ""
                return [bg_prioridad if col == 'prioridad' else color_cump if col == 'Estado_Cumplimiento' else '' for col in row.index]

            if not df_prioridad.empty:
                st.dataframe(df_prioridad.style.apply(style_table, axis=1), use_container_width=True, hide_index=True)
            else:
                st.success("No hay solicitudes de alta prioridad pendientes.")

    elif pagina == "Gantt: Historial Estados":
        st.title("⏱️ Diagrama de Gantt - Historial de Estados")
        st.markdown("Visualización de la duración de cada solicitud en sus distintas etapas.")
        
        # Construir datos para Gantt
        gantt_data = []
        # Asegurar fechas en datetime
        df_hist['fecha_cambio'] = pd.to_datetime(df_hist['fecha_cambio'], errors='coerce', dayfirst=True)
        df_sol['fecha_solicitud'] = pd.to_datetime(df_sol['fecha_solicitud'], errors='coerce', dayfirst=True)
        
        # --- FILTROS ---
        # Dividimos en 3 columnas
        col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
        
        with col_f1:
            sis_filter = st.selectbox("Filtrar por Sistema", ["Qualisys", "Intranet"])
            
        with col_f2:
            # Obtener lista de áreas disponibles para el sistema seleccionado
            areas_disponibles = ['Todas'] + sorted(df_sol[df_sol['sistema_id'] == sis_filter]['area_solicitante_id'].dropna().astype(str).unique())
            area_filter = st.selectbox("Filtrar por Área", areas_disponibles)
        
        # Parámetros para el slider de fechas
        min_d = df_sol['fecha_solicitud'].min()
        max_d = datetime.datetime.now()
        
        if pd.isnull(min_d): min_d = datetime.datetime(2026, 1, 1)
        if pd.isnull(max_d): max_d = datetime.datetime(2026, 12, 31)
        
        default_start = (max_d - datetime.timedelta(days=30)).date()
        if default_start < min_d.date(): default_start = min_d.date()
        
        with col_f3:
            date_filter = st.slider(
                "Filtrar por Fecha",
                min_value=min_d.date(),
                max_value=max_d.date(),
                value=(default_start, max_d.date()),
                format="DD/MM/YYYY"
            )
            
        start_date_filter = pd.to_datetime(date_filter[0])
        end_date_filter = pd.to_datetime(date_filter[1])
        
        # Filtro maestro de solicitudes
        filtro_base = (df_sol['sistema_id'] == sis_filter) & (df_sol['estado_actual'] != 'Anulada') & (df_sol['estado_actual'] != 'Cancelada')
        
        # Si eligió un área específica, la agregamos al filtro
        if area_filter != 'Todas':
            filtro_base = filtro_base & (df_sol['area_solicitante_id'] == area_filter)
            
        # Lista limpia y ORDENADA de solicitudes
        solicitudes_list = sorted(df_sol[filtro_base]['id_solicitud'].unique())
            
        for sol_id in solicitudes_list:
            hist_sol = df_hist[df_hist['id_solicitud'] == sol_id].sort_values('fecha_cambio')
            if hist_sol.empty: continue
            
            sol_info = df_sol[df_sol['id_solicitud'] == sol_id].iloc[0]
            titulo = f"#{sol_id} - {str(sol_info['titulo_solicitud'])[:30]}..."
            last_date = sol_info['fecha_solicitud']
            
            for index, row in hist_sol.iterrows():
                estado = row['estado_origen_id']
                fecha_fin = row['fecha_cambio']
                if pd.notnull(last_date) and pd.notnull(fecha_fin):
                    # Corregir error humano de fechas invertidas en el Excel
                    if fecha_fin < last_date:
                        fecha_fin = last_date + datetime.timedelta(days=1)
                        
                    # Solo agregar si se intercepta con el rango seleccionado
                    if last_date <= end_date_filter and fecha_fin >= start_date_filter:
                        gantt_data.append(dict(Task=titulo, Start=last_date, Finish=fecha_fin, Estado=estado))
                last_date = fecha_fin
                
            # Estado Actual
            estado_actual = sol_info['estado_actual']
            if estado_actual != 'Cerrada':
                fecha_fin_actual = datetime.datetime.now()
                if pd.notnull(last_date):
                    if fecha_fin_actual < last_date:
                        fecha_fin_actual = last_date + datetime.timedelta(days=1)
                    if last_date <= end_date_filter and fecha_fin_actual >= start_date_filter:
                        gantt_data.append(dict(Task=titulo, Start=last_date, Finish=fecha_fin_actual, Estado=estado_actual))

        df_gantt = pd.DataFrame(gantt_data)
        
        if not df_gantt.empty:
                        # Definimos un mapa fijo de colores para cada estado
            mapa_colores = {
                'Registrada': '#FFF59D',             # Amarillo claro
                'Priorizada': '#FBC846',             # Amarillo oscuro
                'En desarrollo': '#A5D6A7',          # Verde suave
                'En pruebas': '#BE9CFF',             # Morado
                'Esperando validación': '#EF9A9A',   # Rojo suave
                'Lista para producción': '#DA4747',  # Rojo oscuro
                'Pausada': '#90CAF9',                # Azul
                'Cerrada': '#4CAF50',                # (Mantuve el verde tradicional para Cerrada)
                'Anulada': '#E0E0E0',                # Gris (Por si acaso, aunque ya está filtrada)
                'Cancelada': '#E0E0E0'               # Gris (Equivalente)
            }

            fig_gantt = px.timeline(
                df_gantt, x_start="Start", x_end="Finish", y="Task", color="Estado",
                title="Ciclo de Vida de las Solicitudes",
                color_discrete_map=mapa_colores
            )

            fig_gantt = px.timeline(
                df_gantt, x_start="Start", x_end="Finish", y="Task", color="Estado",
                title="Ciclo de Vida de las Solicitudes",
                color_discrete_map=mapa_colores
            )
            fig_gantt.update_yaxes(autorange="reversed")
            fig_gantt.update_xaxes(range=[start_date_filter, end_date_filter])
            fig_gantt.update_layout(height=800, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white')
            st.plotly_chart(fig_gantt, use_container_width=True)
            
            st.markdown("### Datos Base del Gantt")
            st.dataframe(df_gantt)
        else:
            st.warning("No hay suficientes datos de historial en este rango de fechas para generar el Gantt.")
else:
    st.warning("No hay datos disponibles en el archivo Excel o están vacíos.")
