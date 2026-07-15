import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import shutil
import os
import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Dashboard CdG - Sistema Comercial",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
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
    
    df_sol['fecha_compromiso'] = pd.to_datetime(df_sol['fecha_compromiso'], errors='coerce')
    df_sol['Fecha_Cierre_Real'] = pd.to_datetime(df_sol['Fecha_Cierre_Real'], errors='coerce')
    df_sol['fecha_solicitud'] = pd.to_datetime(df_sol['fecha_solicitud'], errors='coerce')
    df_sol['fecha_cierre'] = pd.to_datetime(df_sol['fecha_cierre'], errors='coerce')
    
    def get_cumplimiento(row):
        if pd.isnull(row['fecha_compromiso']): return "Sin Compromiso"
        if pd.isnull(row['Fecha_Cierre_Real']):
            return "En Plazo" if datetime.datetime.now() <= row['fecha_compromiso'] else "Atrasado (Abierto)"
        else:
            return "Cumple" if row['Fecha_Cierre_Real'] <= row['fecha_compromiso'] else "No Cumple"
            
    df_sol['Estado_Cumplimiento'] = df_sol.apply(get_cumplimiento, axis=1)
    # --- NAVEGACIÓN SIDEBAR ---
    st.sidebar.title("Navegación")
    st.sidebar.markdown("Selecciona la vista del Dashboard:")
    pagina = st.sidebar.radio(
        "Páginas:",
        ["Dashboard: Qualisys", "Dashboard: Intranet", "Gantt: Historial Estados"]
    )
    
    # --- RENDERIZADO DE PÁGINAS ---
    if pagina.startswith("Dashboard"):
        st.title(f"🚀 Requerimientos CdG - {pagina.split(': ')[1]}")
        
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
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            
            ingresados = len(df_view)
            pendientes = len(df_view[df_view['estado_actual'].isin(['Registrada', 'Priorizada'])])
            en_desarrollo = len(df_view[df_view['estado_actual'] == 'En desarrollo'])
            en_pruebas = len(df_view[df_view['estado_actual'] == 'En pruebas'])
            listo_prd = len(df_view[df_view['estado_actual'] == 'Lista para producción'])
            implementados = len(df_view[df_view['estado_actual'] == 'Cerrada'])
            
            col1.metric("Ingresados", ingresados)
            col2.metric("Pendientes", pendientes)
            col3.metric("En Desarrollo", en_desarrollo)
            col4.metric("En Pruebas", en_pruebas)
            col5.metric("Listo PRD", listo_prd)
            col6.metric("Implementados", implementados)
            
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
        df_hist['fecha_cambio'] = pd.to_datetime(df_hist['fecha_cambio'])
        df_sol['fecha_solicitud'] = pd.to_datetime(df_sol['fecha_solicitud'])
        
        # --- FILTROS ---
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            sis_filter = st.selectbox("Filtrar por Sistema", ["Qualisys", "Intranet"])
        
        # Slider de fechas
        min_d = df_sol['fecha_solicitud'].min()
        max_d = datetime.datetime.now()
        
        if pd.isnull(min_d): min_d = datetime.datetime(2026, 1, 1)
        if pd.isnull(max_d): max_d = datetime.datetime(2026, 12, 31)
        
        default_start = (max_d - datetime.timedelta(days=30)).date()
        if default_start < min_d.date(): default_start = min_d.date()
        
        with col_f2:
            date_filter = st.slider(
                "Filtrar por Fecha",
                min_value=min_d.date(),
                max_value=max_d.date(),
                value=(default_start, max_d.date()),
                format="DD/MM/YYYY"
            )
            
        start_date_filter = pd.to_datetime(date_filter[0])
        end_date_filter = pd.to_datetime(date_filter[1])
        
        solicitudes_list = df_sol[df_sol['sistema_id'] == sis_filter]['id_solicitud'].unique()
            
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
            fig_gantt = px.timeline(
                df_gantt, x_start="Start", x_end="Finish", y="Task", color="Estado",
                title="Ciclo de Vida de las Solicitudes",
                color_discrete_sequence=px.colors.qualitative.Pastel
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

