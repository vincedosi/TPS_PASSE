import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. Configuration Page
st.set_page_config(page_title="Marine Nationale - Dashboard V16", layout="wide")

# 2. Style CSS (Barres de données & Cards)
st.markdown("""
    <style>
    .main { background-color: #F6FBF8; }
    .stat-card {
        background-color: #1C7C54; color: white; padding: 15px;
        border-radius: 10px; text-align: center; margin-bottom: 10px;
    }
    .comparison-table { width: 100%; border-collapse: collapse; font-size: 13px; }
    .comparison-table th { background: #0E1512; color: white; padding: 10px; text-align: center; }
    .comparison-table td { border: 1px solid #eee; padding: 8px; position: relative; text-align: right; height: 30px; }
    .data-bar { position: absolute; left: 0; top: 20%; height: 60%; z-index: 0; opacity: 0.3; border-radius: 0 2px 2px 0; }
    .cell-value { position: relative; z-index: 1; font-weight: bold; }
    .regie-name { text-align: left !important; background: #f9f9f9; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# 3. Fonctions utilitaires
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

# 4. Sidebar & Chargement
st.sidebar.title("⚓ Configuration")
uploaded_file = st.sidebar.file_uploader("Charger l'Excel Marine", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, sheet_name="DATA")
        
        # Nettoyage des types (Blindage contre l'erreur float/str)
        for col in ['Source recodifiée2', 'Visites', 'Campagne recodifiée']:
            if col in df.columns:
                df[col] = df[col].astype(str).replace('nan', 'N/A')

        df['D_num'] = pd.to_numeric(df['Durée'], errors='coerce').fillna(0)
        df['V_num'] = pd.to_numeric(df['Source recodifiée'], errors='coerce').fillna(0).astype(int)

        # Création du dataset de travail
        df_work = pd.DataFrame({
            'Durée': np.repeat(df['D_num'].values, df['V_num'].values),
            'Source': np.repeat(df['Source recodifiée2'].values, df['V_num'].values),
            'Regie': np.repeat(df['Visites'].values, df['V_num'].values),
            'Campagne': np.repeat(df['Campagne recodifiée'].values, df['V_num'].values)
        }).reset_index(drop=True)

        # Filtres interactifs
        st.sidebar.header("🎯 Filtres")
        
        # Filtre Volume > 100
        exclude_low = st.sidebar.toggle("🚀 Top Régies (>100 visites)", value=False)
        
        counts = df_work['Regie'].value_counts()
        reg_list = sorted([str(r) for r in df_work['Regie'].unique()])
        if exclude_low:
            reg_list = sorted([str(r) for r in counts.index if counts[r] >= 100])

        sel_src = st.sidebar.multiselect("Sources", sorted(df_work['Source'].unique()))
        sel_cmp = st.sidebar.multiselect("Campagnes", sorted(df_work['Campagne'].unique()))
        sel_reg = st.sidebar.multiselect("Régies", reg_list)
        
        calc_mode = st.sidebar.selectbox("Calcul des Stats", ["Global (avec 0s)", "Engagement (sans 0s)"], index=1)

        # Application filtres
        filtered = df_work.copy()
        if sel_src: filtered = filtered[filtered['Source'].isin(sel_src)]
        if sel_cmp: filtered = filtered[filtered['Campagne'].isin(sel_cmp)]
        if sel_reg: filtered = filtered[filtered['Regie'].isin(sel_reg)]
        elif exclude_low: filtered = filtered[filtered['Regie'].isin(reg_list)]

        if not filtered.empty:
            # Calcul Stats
            d_all = filtered['Durée'].sort_values().values
            d_eng = d_all[d_all > 0]
            d_target = d_all if calc_mode == "Global (avec 0s)" else d_eng
            
            n = len(filtered)
            rebond = (len(filtered[filtered['Durée'] == 0]) / n) * 100
            mean_v = np.mean(d_target) if len(d_target) > 0 else 0
            q1, med, q3 = (np.percentile(d_target, [25, 50, 75]) if len(d_target) > 0 else [0,0,0])

            # Affichage KPI
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f'<div class="stat-card"><h3>{n:,}</h3><small>SESSIONS</small></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="stat-card"><h3>{rebond:.1f}%</h3><small>REBOND</small></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="stat-card"><h3>{int(med)}s</h3><small>MÉDIANE</small></div>', unsafe_allow_html=True)
            c4.markdown(f'<div class="stat-card"><h3>{int(mean_v)}s</h3><small>MOYENNE</small></div>', unsafe_allow_html=True)

            # --- GRAPHIQUE DOUBLE AXE Y ---
            filtered['Bucket'] = filtered['Durée'].apply(get_bucket)
            buckets = sorted(filtered['Bucket'].unique(), key=get_sort_val)
            
            # On utilise make_subplots pour avoir l'axe Y secondaire
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            regies_in_plot = sorted(filtered['Regie'].unique())
            
            for r in regies_in_plot:
                r_data = filtered[filtered['Regie'] == r]
                b_counts = r_data['Bucket'].value_counts()
                
                # Trace pour les 0s (Axe Y Droit)
                fig.add_trace(go.Bar(
                    name=f"{r} (0s)", 
                    x=["0 sec"], 
                    y=[b_counts.get("0 sec", 0)],
                    marker_color=None, # Plotly gère les couleurs automatiquement
                    legendgroup=r,
                    showlegend=False
                ), secondary_y=True)
                
                # Trace pour le reste (Axe Y Gauche)
                other_buckets = [b for b in buckets if b != "0 sec"]
                fig.add_trace(go.Bar(
                    name=r, 
                    x=other_buckets, 
                    y=[b_counts.get(b, 0) for b in other_buckets],
                    legendgroup=r,
                    showlegend=True
                ), secondary_y=False)

            # Lignes de stats
            colors = {"q1": "#3498db", "med": "#e74c3c", "q3": "#2ecc71", "moy": "#f39c12"}
            for val, name, col, dash in [(q1,'Q1','q1','dot'), (med,'MED','med','solid'), (q3,'Q3','q3','dot'), (mean_v,'MOY','moy','dash')]:
                b_pos = get_bucket(val)
                fig.add_vline(x=b_pos, line_width=2, line_dash=dash, line_color=colors[col])

            fig.update_layout(
                barmode='stack', 
                height=600, 
                title_text="Distribution Temps Passé (0s sur Axe Y Droit)",
                xaxis_title="Paliers de durée",
                legend=dict(orientation="h", y=-0.2)
            )
            fig.update_yaxes(title_text="Sessions Engagées", secondary_y=False)
            fig.update_yaxes(title_text="Sessions Rebond (0s)", secondary_y=True)
            
            st.plotly_chart(fig, use_container_width=True)

            # --- TABLEAU COMPARATIF ---
            st.subheader("🏆 Performance des Régies")
            max_v = filtered['Regie'].value_counts().max()
            
            comp_rows = []
            for r in regies_in_plot:
                r_d = filtered[filtered['Regie'] == r]
                vol = len(r_d)
                p_reb = (len(r_d[r_d['Durée'] == 0]) / vol * 100)
                p_rap = (len(r_d[(r_d['Durée'] > 0) & (r_d['Durée'] <= 30)]) / vol * 100)
                p_eng = (len(r_d[(r_d['Durée'] > 30) & (r_d['Durée'] <= 180)]) / vol * 100)
                p_top = (len(r_d[r_d['Durée'] > 180]) / vol * 100)
                
                def bar(p, c): return f'<div class="data-bar" style="width:{p}%; background:{c};"></div><span class="cell-value">{p:.1f}%</span>'
                
                comp_rows.append(f"""<tr>
                    <td class="regie-name">{r}</td>
                    <td><div class="data-bar" style="width:{vol/max_v*100}%; background:#3498db;"></div><span class="cell-value">{vol:,}</span></td>
                    <td>{bar(p_reb, "#e74c3c")}</td>
                    <td>{bar(p_rap, "#f39c12")}</td>
                    <td>{bar(p_eng, "#3498db")}</td>
                    <td>{bar(p_top, "#2ecc71")}</td>
                </tr>""")

            table_html = f"""<table class="comparison-table">
                <thead><tr><th>Régie</th><th>Volume</th><th>Rebond</th><th>Rapide</th><th>Engagé</th><th>Top</th></tr></thead>
                <tbody>{"".join(comp_rows)}</tbody></table>"""
            st.write(table_html, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Erreur lors de l'analyse : {e}")
