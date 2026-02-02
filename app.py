import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# 1. Configuration Page & Thèmes
st.set_page_config(page_title="Dashboard Analytics V27", layout="wide")

# --- GESTION DES THÈMES ---
THEMES = {
    "Marine (Mer)": {
        "primary": "#0A2463",
        "card_bg": "#0A2463",
        "bar_vol": "#3E92CC",
        "palette": ['#0A2463', '#3E92CC', '#247BA0', '#DFF3E3', '#60A5FA', '#1E3A8A', '#93C5FD'],
        "bg_main": "#F0F4F8"
    },
    "Air (Ciel)": {
        "primary": "#0077B6",
        "card_bg": "#0077B6",
        "bar_vol": "#90E0EF",
        "palette": ['#0077B6', '#0096C7', '#48CAE4', '#90E0EF', '#ADE8F4', '#023E8A', '#CAF0F8'],
        "bg_main": "#F5FBFF"
    },
    "Terre (Sol)": {
        "primary": "#2D3E29",
        "card_bg": "#3A5A40",
        "bar_vol": "#A3B18A",
        "palette": ['#3A5A40', '#588157', '#A3B18A', '#DAD7CD', '#344E41', '#606C38', '#283618'],
        "bg_main": "#F7F8F6"
    }
}

# 2. Sidebar : Configuration
st.sidebar.title("⚙️ Configuration")
selected_theme_name = st.sidebar.selectbox("🎨 Thème Visuel", list(THEMES.keys()), index=0)
current_theme = THEMES[selected_theme_name]
uploaded_file = st.sidebar.file_uploader("Charger le fichier de données", type=["xlsx"])

# 3. Style CSS DYNAMIQUE
st.markdown(f"""
    <style>
    .main {{ background-color: {current_theme['bg_main']}; }}
    .stat-card {{
        background-color: {current_theme['card_bg']}; 
        color: white; padding: 20px; border-radius: 8px; text-align: center; 
        margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    .stat-card h3 {{ color: white !important; margin: 0; font-size: 28px; }}
    .stat-card small {{ text-transform: uppercase; letter-spacing: 1px; font-size: 12px; opacity: 0.9; }}
    .comparison-table {{ width: 100%; border-collapse: separate; border-spacing: 0 5px; font-size: 13px; }}
    .comparison-table th {{ background: #2C3E50; color: white; padding: 12px; text-align: center; }}
    .comparison-table tr {{ background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
    .comparison-table td {{ padding: 10px; text-align: right; vertical-align: middle; }}
    .data-bar {{ position: absolute; left: 0; top: 25%; height: 50%; opacity: 0.25; }}
    .cell-value {{ position: relative; z-index: 1; font-weight: bold; color: #444; }}
    .regie-name {{ text-align: left !important; font-weight: bold; color: {current_theme['primary']}; min-width: 200px; }}
    </style>
""", unsafe_allow_html=True)

# 4. Fonctions
def get_bucket(d):
    if d == 0: return "0 sec"
    if d <= 60: return f"{int(d)} sec"
    if d <= 300:
        s = int((d-61)//30)*30+61
        return f"{s}-{s+29} sec"
    return ">5 min"

def get_sort_val(b):
    if b == "0 sec": return -1
    if ">" in b: return 999999
    try: return int(b.split("-")[0].replace(" sec", ""))
    except: return 0

# 5. Logique Principale
if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, sheet_name="DATA")

        # MAPPING
        c_source_detail = 'Source'              
        c_regie_groupe  = 'Source recodifiée2'  
        c_campagne      = 'Campagne recodifiée' 
        c_variante      = 'Campagne - Variante' 
        c_duree   = 'Durée visite'  
        c_visites = 'Visites'       

        required_cols = [c_source_detail, c_regie_groupe, c_campagne, c_duree, c_visites, c_variante]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            st.error(f"❌ Colonnes introuvables : {missing}")
            st.stop()

        for col in [c_source_detail, c_regie_groupe, c_campagne, c_variante]:
            df[col] = df[col].astype(str).replace('nan', 'N/A')

        df['D_num'] = pd.to_numeric(df[c_duree], errors='coerce').fillna(0)
        df['V_num'] = pd.to_numeric(df[c_visites], errors='coerce').fillna(0).astype(int)

        df_work = pd.DataFrame({
            'Durée':    np.repeat(df['D_num'].values, df['V_num'].values),
            'Source':   np.repeat(df[c_source_detail].values, df['V_num'].values),
            'Regie':    np.repeat(df[c_regie_groupe].values, df['V_num'].values),
            'Campagne': np.repeat(df[c_campagne].values, df['V_num'].values),
            'Variante': np.repeat(df[c_variante].values, df['V_num'].values)
        }).reset_index(drop=True)

        # --- FILTRES ---
        st.sidebar.header("🎯 Filtres")
        sel_src = st.sidebar.multiselect("Sources", sorted(df_work['Source'].unique()))
        sel_cmp = st.sidebar.multiselect("Campagnes", sorted(df_work['Campagne'].unique()))
        
        # --- LOGIQUE FILTRE VARIANTES CORRIGÉE ---
        counts = df_work['Variante'].value_counts()
        exclude_low = st.sidebar.toggle("🚀 Top Variantes (>100 visites)", value=False)
        
        # Définition de la liste des variantes AUTORISÉES
        if exclude_low:
            allowed_variants = sorted([str(r) for r in counts.index if counts[r] >= 100])
        else:
            allowed_variants = sorted([str(r) for r in df_work['Variante'].unique()])
        
        # Le sélecteur ne montre que ce qui est autorisé
        sel_var = st.sidebar.multiselect("Variantes", allowed_variants)
        
        calc_mode = st.sidebar.selectbox("Calcul des Stats", ["Global (avec 0s)", "Engagement (sans 0s)"], index=1)

        # APPLICATION FILTRES
        filtered = df_work.copy()
        if sel_src: filtered = filtered[filtered['Source'].isin(sel_src)]
        if sel_cmp: filtered = filtered[filtered['Campagne'].isin(sel_cmp)]
        
        # 1. On filtre d'abord par la sélection manuelle si elle existe
        if sel_var: 
            filtered = filtered[filtered['Variante'].isin(sel_var)]
        
        # 2. SÉCURITÉ : Si le bouton >100 est ON, on re-filtre FORCÉMENT pour virer les petits
        # C'est ça qui manquait pour le graphique !
        if exclude_low:
            filtered = filtered[filtered['Variante'].isin(allowed_variants)]

        if not filtered.empty:
            # KPI
            d_all = filtered['Durée'].sort_values().values
            d_target = d_all if calc_mode == "Global (avec 0s)" else d_all[d_all > 0]
            n = len(filtered)
            
            rebond = (len(filtered[filtered['Durée'] == 0]) / n) * 100
            mean_v = np.mean(d_target) if len(d_target) > 0 else 0
            q1, med, q3 = (np.percentile(d_target, [25, 50, 75]) if len(d_target) > 0 else [0,0,0])

            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f'<div class="stat-card"><h3>{n:,}</h3><small>SESSIONS</small></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="stat-card"><h3>{rebond:.1f}%</h3><small>REBOND</small></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="stat-card"><h3>{int(med)}s</h3><small>MÉDIANE</small></div>', unsafe_allow_html=True)
            c4.markdown(f'<div class="stat-card"><h3>{int(mean_v)}s</h3><small>MOYENNE</small></div>', unsafe_allow_html=True)

            # --- GRAPHIQUE ---
            filtered['Bucket'] = filtered['Durée'].apply(get_bucket)
            buckets = sorted(filtered['Bucket'].unique(), key=get_sort_val)
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            variants_plot = sorted(filtered['Variante'].unique())
            
            theme_palette = current_theme['palette']
            
            for i, v in enumerate(variants_plot):
                v_data = filtered[filtered['Variante'] == v]
                b_counts = v_data['Bucket'].value_counts()
                col_code = theme_palette[i % len(theme_palette)]
                
                # Trace 0s (Gauche)
                fig.add_trace(go.Bar(
                    name=v, x=["0 sec"], y=[b_counts.get("0 sec", 0)],
                    marker_color=col_code, legendgroup=v, showlegend=False, opacity=0.6
                ), secondary_y=True)
                
                # Trace Engagement (Droite)
                other_b = [b for b in buckets if b != "0 sec"]
                fig.add_trace(go.Bar(
                    name=v, x=other_b, y=[b_counts.get(b, 0) for b in other_b],
                    marker_color=col_code, legendgroup=v, showlegend=True
                ), secondary_y=False)

            # Lignes Stats
            stats_config = [
                (q1, "Q1 (25%)", "#3498db", "dot"),
                (med, "MÉDIANE", "#e74c3c", "solid"),
                (q3, "Q3 (75%)", "#2ecc71", "dot"),
                (mean_v, "MOYENNE", "#f39c12", "dash")
            ]

            for val, label, color, dash in stats_config:
                b_pos = get_bucket(val)
                fig.add_vline(x=b_pos, line_width=3, line_dash=dash, line_color=color)
                fig.add_trace(go.Scatter(
                    x=[None], y=[None], mode='lines',
                    line=dict(color=color, width=3, dash=dash),
                    name=f"{label} : {int(val)}s", showlegend=True
                ), secondary_y=False)

            fig.update_layout(
                barmode='stack', height=650, title_text="Distribution des durées par Variante", xaxis_title="Durée",
                legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center", bgcolor="rgba(255,255,255,0.8)"),
                margin=dict(t=100)
            )
            
            # AXES INVERSÉS (Gauche = 0s / Droite = Engagé)
            fig.update_yaxes(title_text="Volume Rebond (0s)", secondary_y=True, side="left", showgrid=False)
            fig.update_yaxes(title_text="Sessions Engagées", secondary_y=False, side="right", showgrid=True)

            st.plotly_chart(fig, use_container_width=True)

            # --- TABLEAU ---
            max_v = filtered['Variante'].value_counts().max()
            comp_rows = []
            
            for v in variants_plot:
                v_d = filtered[filtered['Variante'] == v]
                vol = len(v_d)
                
                if vol > 0:
                    c_0 = len(v_d[v_d['Durée'] == 0])
                    c_1_30 = len(v_d[(v_d['Durée'] > 0) & (v_d['Durée'] <= 30)])
                    c_30_180 = len(v_d[(v_d['Durée'] > 30) & (v_d['Durée'] <= 180)])
                    c_180_plus = len(v_d[v_d['Durée'] > 180])
                    
                    p0 = (c_0 / vol * 100)
                    p1 = (c_1_30 / vol * 100)
                    p2 = (c_30_180 / vol * 100)
                    p3 = (c_180_plus / vol * 100)
                    
                    bar_vol_color = current_theme['bar_vol']

                    comp_rows.append(f"""
                    <tr>
                        <td class='regie-name'>{v}</td>
                        <td><div class='data-bar' style='width:{vol/max_v*100}%; background:{bar_vol_color};'></div><span class='cell-value'>{vol:,}</span></td>
                        <td><div class='data-bar' style='width:{p0}%; background:#e74c3c;'></div><span class='cell-value'>{p0:.1f}%</span></td>
                        <td><div class='data-bar' style='width:{p1}%; background:#f1c40f;'></div><span class='cell-value'>{p1:.1f}%</span></td>
                        <td><div class='data-bar' style='width:{p2}%; background:#3498db;'></div><span class='cell-value'>{p2:.1f}%</span></td>
                        <td><div class='data-bar' style='width:{p3}%; background:#2ecc71;'></div><span class='cell-value'>{p3:.1f}%</span></td>
                    </tr>""")

            st.write(f"""
            <table class='comparison-table'>
                <thead>
                    <tr>
                        <th>Variante</th>
                        <th>Volume</th>
                        <th>Rebond (0s)</th>
                        <th>Court (1-30s)</th>
                        <th>Engagé (30s-3m)</th>
                        <th>Top (>3m)</th>
                    </tr>
                </thead>
                <tbody>{''.join(comp_rows)}</tbody>
            </table>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Une erreur s'est produite : {e}")
