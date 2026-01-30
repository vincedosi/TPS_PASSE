import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import json
from datetime import datetime

# Configuration de la page Streamlit
st.set_page_config(page_title="Marine Nationale - Dashboard Temps Passé", layout="wide")

# --- STYLE CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .main { background-color: #F6FBF8; }
    .stSelectbox, .stMultiSelect { font-family: 'Century Gothic', sans-serif; }
    .stat-card {
        background-color: #1C7C54;
        color: white;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        margin-bottom: 10px;
    }
    /* Style pour le tableau comparatif */
    .comparison-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .comparison-table th { background: #0E1512; color: white; padding: 10px; }
    .comparison-table td { border: 1px solid #eee; padding: 8px; position: relative; text-align: right; }
    .data-bar {
        position: absolute; left: 0; top: 20%; height: 60%;
        z-index: 0; opacity: 0.4; border-radius: 0 2px 2px 0;
    }
    .cell-value { position: relative; z-index: 1; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- LOGIQUE DE CALCUL ---
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

# --- INTERFACE STREAMLIT ---
st.title("📊 Marine Nationale - Dashboard Temps Passé")

uploaded_file = st.sidebar.file_uploader("📂 Charger le fichier Excel Marine", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name="DATA")
    
    # Nettoyage et Reconstruction (Logique Expert)
    try:
        df['D'] = pd.to_numeric(df['Durée'], errors='coerce').fillna(0)
        df['V'] = pd.to_numeric(df['Source recodifiée'], errors='coerce').fillna(0).astype(int)
        
        df_work = pd.DataFrame({
            'Durée': np.repeat(df['D'], df['V']),
            'Source': np.repeat(df['Source recodifiée2'], df['V']),
            'Regie': np.repeat(df['Visites'], df['V']),
            'Campagne': np.repeat(df['Campagne recodifiée'], df['V'])
        }).reset_index(drop=True)

        # Filtres Sidebar
        st.sidebar.header("🎯 Filtres")
        
        # Filtre Automatique Top 100
        exclude_low_visites = st.sidebar.checkbox("🚀 Top Régies (>100 visites)", value=False)
        
        # Sélecteurs Multiples
        all_sources = sorted(df_work['Source'].unique().tolist())
        sel_sources = st.sidebar.multiselect("Source", all_sources)
        
        all_campagnes = sorted(df_work['Campagne'].unique().tolist())
        sel_campagnes = st.sidebar.multiselect("Campagne", all_campagnes)
        
        regie_counts = df_work['Regie'].value_counts()
        if exclude_low_visites:
            available_regies = sorted([r for r in regie_counts.index if regie_counts[r] >= 100])
        else:
            available_regies = sorted(df_work['Regie'].unique().tolist())
            
        sel_regies = st.sidebar.multiselect("Régie", available_regies)

        calc_mode = st.sidebar.selectbox("Mode de calcul Stats", ["Inclure 0s", "Engagement (>0s)"], index=1)

        # Application des filtres
        filtered = df_work.copy()
        if sel_sources: filtered = filtered[filtered['Source'].isin(sel_sources)]
        if sel_campagnes: filtered = filtered[filtered['Campagne'].isin(sel_campagnes)]
        if sel_regies: filtered = filtered[filtered['Regie'].isin(sel_regies)]
        elif exclude_low_visites: filtered = filtered[filtered['Regie'].isin(available_regies)]

        if not filtered.empty:
            # Stats
            d_stats = filtered['Durée'].sort_values().values
            if calc_mode == "Engagement (>0s)":
                d_stats = d_stats[d_stats > 0]
            
            n = len(filtered)
            n_stats = len(d_stats)
            mean_val = np.mean(d_stats) if n_stats > 0 else 0
            q1 = np.percentile(d_stats, 25) if n_stats > 0 else 0
            med = np.percentile(d_stats, 50) if n_stats > 0 else 0
            q3 = np.percentile(d_stats, 75) if n_stats > 0 else 0
            rebond = (len(filtered[filtered['Durée'] == 0]) / n) * 100

            # Affichage KPI
            col1, col2, col3 = st.columns(3)
            col1.markdown(f'<div class="stat-card"><h2>{n:,}</h2><p>SESSIONS TOTALES</p></div>', unsafe_allow_html=True)
            col2.markdown(f'<div class="stat-card"><h2>{rebond:.1f}%</h2><p>TAUX DE REBOND</p></div>', unsafe_allow_html=True)
            col3.markdown(f'<div class="stat-card"><h2>{int(med)}s</h2><p>MÉDIANE</p></div>', unsafe_allow_html=True)

            # --- GRAPHIQUE PLOTLY ---
            filtered['Bucket'] = filtered['Durée'].apply(get_bucket)
            buckets_order = sorted(filtered['Bucket'].unique(), key=get_sort_val)
            
            fig = go.Figure()
            for r in sorted(filtered['Regie'].unique()):
                r_data = filtered[filtered['Regie'] == r]
                counts = r_data['Bucket'].value_counts()
                fig.add_trace(go.Bar(name=r, x=buckets_order, y=[counts.get(b, 0) for b in buckets_order]))

            # VLines Stats
            colors_dict = {"q1": "#3498db", "med": "#e74c3c", "q3": "#2ecc71", "mean": "#f39c12"}
            
            for val, name, col, dash in [(q1, 'Q1', 'q1', 'dot'), (med, 'MED', 'med', 'solid'), (q3, 'Q3', 'q3', 'dot'), (mean_val, 'MOY', 'mean', 'dash')]:
                b_pos = get_bucket(val)
                fig.add_vline(x=b_pos, line_width=2, line_dash=dash, line_color=colors_dict[col])
                fig.add_annotation(x=b_pos, y=1, yref="paper", text=name, showarrow=False, font=dict(color=colors_dict[col], size=12), bgcolor="white")

            fig.update_layout(barmode='stack', xaxis_title="Paliers de durée", yaxis_title="Sessions", height=600, legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig, use_container_width=True)

            # --- TABLEAUX ---
            t1, t2 = st.columns([1, 2])
            
            with t1:
                st.subheader("📍 Statistiques")
                st.table(pd.DataFrame({
                    "Indicateur": ["Moyenne", "Médiane (Q2)", "Quartile 1", "Quartile 3"],
                    "Valeur": [f"{int(mean_val)}s", f"{int(med)}s", f"{int(q1)}s", f"{int(q3)}s"]
                }))

            with t2:
                st.subheader("🏆 Performance Régies")
                # Construction du tableau comparatif avec barres HTML
                comp_data = []
                max_vol = filtered['Regie'].value_counts().max()
                
                for r in sorted(filtered['Regie'].unique()):
                    r_d = filtered[filtered['Regie'] == r]
                    tot = len(r_d)
                    p_reb = (len(r_d[r_d['Durée'] == 0]) / tot * 100)
                    p_rap = (len(r_d[(r_d['Durée'] > 0) & (r_d['Durée'] <= 30)]) / tot * 100)
                    p_eng = (len(r_d[(r_d['Durée'] > 30) & (r_d['Durée'] <= 180)]) / tot * 100)
                    p_top = (len(r_d[r_d['Durée'] > 180]) / tot * 100)
                    
                    def make_bar(perc, color):
                        return f'<div class="data-bar" style="width:{perc}%; background:{color};"></div><span class="cell-value">{perc:.1f}%</span>'
                    
                    comp_data.append({
                        "Régie": r,
                        "Volume": f'<div class="data-bar" style="width:{(tot/max_vol*100)}%; background:#3498db;"></div><span class="cell-value">{tot:,}</span>',
                        "Rebond": make_bar(p_reb, "#e74c3c"),
                        "Rapide": make_bar(p_rap, "#f39c12"),
                        "Engagé": make_bar(p_eng, "#3498db"),
                        "Top": make_bar(p_top, "#2ecc71")
                    })
                
                st.write(pd.DataFrame(comp_data).to_html(escape=False, index=False, classes="comparison-table"), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Erreur lors de l'analyse : {e}")
else:
    st.info("👋 Veuillez charger votre fichier Excel dans la barre latérale pour commencer.")
