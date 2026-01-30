import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

# Configuration de la page
st.set_page_config(page_title="Marine Nationale - Dashboard Temps Passé", layout="wide")

# --- STYLE CSS ---
st.markdown("""
    <style>
    .main { background-color: #F6FBF8; }
    .stat-card {
        background-color: #1C7C54; color: white; padding: 20px;
        border-radius: 10px; text-align: center; margin-bottom: 10px;
    }
    .comparison-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .comparison-table th { background: #0E1512; color: white; padding: 10px; }
    .comparison-table td { border: 1px solid #eee; padding: 8px; position: relative; text-align: right; }
    .data-bar { position: absolute; left: 0; top: 20%; height: 60%; z-index: 0; opacity: 0.4; border-radius: 0 2px 2px 0; }
    .cell-value { position: relative; z-index: 1; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- FONCTIONS DE TRI ET PALIERS ---
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

# --- INTERFACE ---
st.title("📊 Marine Nationale - Dashboard Temps Passé")

uploaded_file = st.sidebar.file_uploader("📂 Charger le fichier Excel Marine", type=["xlsx"])

if uploaded_file:
    try:
        # Lecture de l'Excel
        df = pd.read_excel(uploaded_file, sheet_name="DATA")
        
        # --- NETTOYAGE CRITIQUE (Correction de l'erreur float/str) ---
        # 1. Conversion forcée des colonnes de texte pour éviter le bug de tri
        for col in ['Source recodifiée2', 'Visites', 'Campagne recodifiée']:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', 'N/A')

        # 2. Conversion numérique des durées et volumes
        df['D_num'] = pd.to_numeric(df['Durée'], errors='coerce').fillna(0)
        df['V_num'] = pd.to_numeric(df['Source recodifiée'], errors='coerce').fillna(0).astype(int)
        
        # 3. Reconstruction de l'échantillon
        df_work = pd.DataFrame({
            'Durée': np.repeat(df['D_num'].values, df['V_num'].values),
            'Source': np.repeat(df['Source recodifiée2'].values, df['V_num'].values),
            'Regie': np.repeat(df['Visites'].values, df['V_num'].values),
            'Campagne': np.repeat(df['Campagne recodifiée'].values, df['V_num'].values)
        }).reset_index(drop=True)

        # --- FILTRES ---
        st.sidebar.header("🎯 Filtres")
        
        # Correction : On s'assure que les listes ne contiennent que des strings pour le tri
        all_sources = sorted([str(x) for x in df_work['Source'].unique()])
        sel_sources = st.sidebar.multiselect("Source", all_sources)
        
        all_campagnes = sorted([str(x) for x in df_work['Campagne'].unique()])
        sel_campagnes = st.sidebar.multiselect("Campagne", all_campagnes)
        
        exclude_low = st.sidebar.checkbox("🚀 Top Régies (>100 visites)", value=False)
        reg_counts = df_work['Regie'].value_counts()
        if exclude_low:
            available_regies = sorted([str(r) for r in reg_counts.index if reg_counts[r] >= 100])
        else:
            available_regies = sorted([str(x) for x in df_work['Regie'].unique()])
            
        sel_regies = st.sidebar.multiselect("Régie", available_regies)
        calc_mode = st.sidebar.selectbox("Mode de calcul Stats", ["Inclure 0s", "Engagement (>0s)"], index=1)

        # Filtrage effectif
        filtered = df_work.copy()
        if sel_sources: filtered = filtered[filtered['Source'].isin(sel_sources)]
        if sel_campagnes: filtered = filtered[filtered['Campagne'].isin(sel_campagnes)]
        if sel_regies: filtered = filtered[filtered['Regie'].isin(sel_regies)]
        elif exclude_low: filtered = filtered[filtered['Regie'].isin(available_regies)]

        if not filtered.empty:
            # Calcul des statistiques
            d_stats = filtered['Durée'].sort_values().values
            if calc_mode == "Engagement (>0s)":
                d_stats = d_stats[d_stats > 0]
            
            n = len(filtered)
            mean_val = np.mean(d_stats) if len(d_stats) > 0 else 0
            q1, med, q3 = (np.percentile(d_stats, [25, 50, 75]) if len(d_stats) > 0 else [0,0,0])
            rebond = (len(filtered[filtered['Durée'] == 0]) / n) * 100

            # KPI
            col1, col2, col3 = st.columns(3)
            col1.markdown(f'<div class="stat-card"><h2>{n:,}</h2><p>SESSIONS</p></div>', unsafe_allow_html=True)
            col2.markdown(f'<div class="stat-card"><h2>{rebond:.1f}%</h2><p>REBOND</p></div>', unsafe_allow_html=True)
            col3.markdown(f'<div class="stat-card"><h2>{int(med)}s</h2><p>MÉDIANE</p></div>', unsafe_allow_html=True)

            # --- GRAPH ---
            filtered['Bucket'] = filtered['Durée'].apply(get_bucket)
            buckets_order = sorted(filtered['Bucket'].unique(), key=get_sort_val)
            
            fig = go.Figure()
            for r in sorted(filtered['Regie'].unique()):
                r_data = filtered[filtered['Regie'] == r]
                counts = r_data['Bucket'].value_counts()
                fig.add_trace(go.Bar(name=str(r), x=buckets_order, y=[counts.get(b, 0) for b in buckets_order]))

            # Lignes Stats
            for val, name, col, dash in [(q1,'Q1','#3498db','dot'), (med,'MED','#e74c3c','solid'), (q3,'Q3','#2ecc71','dot'), (mean_val,'MOY','#f39c12','dash')]:
                b_pos = get_bucket(val)
                fig.add_vline(x=b_pos, line_width=2, line_dash=dash, line_color=col)
                fig.add_annotation(x=b_pos, y=1, yref="paper", text=name, showarrow=False, font=dict(color=col), bgcolor="white")

            fig.update_layout(barmode='stack', height=550, legend=dict(orientation="h", y=-0.2), margin=dict(t=80))
            st.plotly_chart(fig, use_container_width=True)

            # --- TABLES ---
            t1, t2 = st.columns([1, 2])
            with t1:
                st.table(pd.DataFrame({"Stats": ["Moyenne", "Médiane", "Q1", "Q3"], "Valeur": [f"{int(mean_val)}s", f"{int(med)}s", f"{int(q1)}s", f"{int(q3)}s"]}))
            with t2:
                # Tableau avec barres de données CSS
                max_v = filtered['Regie'].value_counts().max()
                rows = []
                for r in sorted(filtered['Regie'].unique()):
                    r_d = filtered[filtered['Regie'] == r]
                    tot = len(r_d)
                    p_reb = (len(r_d[r_d['Durée'] == 0]) / tot * 100)
                    p_top = (len(r_d[r_d['Durée'] > 180]) / tot * 100)
                    
                    rows.append(f"""<tr>
                        <td class="regie-name">{r}</td>
                        <td><div class="data-bar" style="width:{tot/max_v*100}%; background:#3498db;"></div><span class="cell-value">{tot:,}</span></td>
                        <td><div class="data-bar" style="width:{p_reb}%; background:#e74c3c;"></div><span class="cell-value">{p_reb:.1f}%</span></td>
                        <td><div class="data-bar" style="width:{p_top}%; background:#2ecc71;"></div><span class="cell-value">{p_top:.1f}%</span></td>
                    </tr>""")
                
                html_table = f'<table class="comparison-table"><thead><tr><th>Régie</th><th>Volume</th><th>Rebond</th><th>Top (+3m)</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
                st.write(html_table, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Erreur lors de l'analyse : {e}")
