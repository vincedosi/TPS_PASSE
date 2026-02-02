import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. Configuration Page
st.set_page_config(page_title="Marine Nationale - Dashboard V18", layout="wide")

# 2. Style CSS
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
        
        # --- 🔧 MAPPING DES COLONNES (A VERIFIER ICI) ---
        # Si vous avez renommé vos colonnes, assurez-vous que les noms ci-dessous correspondent EXACTEMENT à votre Excel
        col_source = 'Source'       # Nom de la colonne Source (vu dans l'image)
        col_campagne = 'Campagne'   # Nom de la colonne Campagne
        col_duree = 'Durée'         # Nom de la colonne Durée (Attention aux accents !)
        
        # ATTENTION : Dans votre ancien code, les noms étaient inversés par rapport à la logique habituelle.
        # J'ai supposé que "Visites" contient le NOM de la Régie et une autre colonne contient le NOMBRE.
        # Si vous avez nettoyé l'Excel, ajustez ces deux lignes :
        col_regie_nom = 'Visites'           # La colonne qui contient le NOM de la régie (ex: Google, Meta)
        col_volume_nb = 'Source recodifiée' # La colonne qui contient le NOMBRE de visites (chiffre entier)
        
        # Petit fix automatique si vous avez renommé "Source recodifiée" en "Nombre de visites" ou juste "Visites"
        # Décommentez la ligne ci-dessous si votre colonne de chiffres s'appelle 'V_num' ou 'NB_Visites'
        # col_volume_nb = 'NB_Visites' 
        # -----------------------------------------------

        # Vérification préventive pour éviter le crash brutal
        missing_cols = [c for c in [col_source, col_campagne, col_duree, col_regie_nom, col_volume_nb] if c not in df.columns]
        if missing_cols:
            st.error(f"⚠️ Colonnes manquantes dans l'Excel : {missing_cols}")
            st.info("Vérifiez les noms dans la section 'MAPPING DES COLONNES' du code.")
            st.stop()

        # Nettoyage des types
        for col in [col_source, col_regie_nom, col_campagne]:
            df[col] = df[col].astype(str).replace('nan', 'N/A')

        df['D_num'] = pd.to_numeric(df[col_duree], errors='coerce').fillna(0)
        df['V_num'] = pd.to_numeric(df[col_volume_nb], errors='coerce').fillna(0).astype(int)

        # Création du dataset éclaté (row repetition based on visits count)
        df_work = pd.DataFrame({
            'Durée': np.repeat(df['D_num'].values, df['V_num'].values),
            'Source': np.repeat(df[col_source].values, df['V_num'].values),
            'Regie': np.repeat(df[col_regie_nom].values, df['V_num'].values),
            'Campagne': np.repeat(df[col_campagne].values, df['V_num'].values)
        }).reset_index(drop=True)

        # Filtres Sidebar
        st.sidebar.header("🎯 Filtres")
        sel_src = st.sidebar.multiselect("Sources", sorted(df_work['Source'].unique()))
        sel_cmp = st.sidebar.multiselect("Campagnes", sorted(df_work['Campagne'].unique()))
        
        counts = df_work['Regie'].value_counts()
        exclude_low = st.sidebar.toggle("🚀 Top Régies (>100 visites)", value=False)
        reg_list = sorted([str(r) for r in df_work['Regie'].unique()])
        if exclude_low:
            reg_list = sorted([str(r) for r in counts.index if counts[r] >= 100])
        
        sel_reg = st.sidebar.multiselect("Régies", reg_list)
        calc_mode = st.sidebar.selectbox("Calcul des Stats", ["Global (avec 0s)", "Engagement (sans 0s)"], index=1)

        # Application filtres
        filtered = df_work.copy()
        if sel_src: filtered = filtered[filtered['Source'].isin(sel_src)]
        if sel_cmp: filtered = filtered[filtered['Campagne'].isin(sel_cmp)]
        if sel_reg: filtered = filtered[filtered['Regie'].isin(sel_reg)]
        elif exclude_low: filtered = filtered[filtered['Regie'].isin(reg_list)]

        if not filtered.empty:
            # Stats
            d_all = filtered['Durée'].sort_values().values
            d_target = d_all if calc_mode == "Global (avec 0s)" else d_all[d_all > 0]
            n = len(filtered)
            rebond = (len(filtered[filtered['Durée'] == 0]) / n) * 100
            mean_v = np.mean(d_target) if len(d_target) > 0 else 0
            q1, med, q3 = (np.percentile(d_target, [25, 50, 75]) if len(d_target) > 0 else [0,0,0])

            # KPI
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(f'<div class="stat-card"><h3>{n:,}</h3><small>SESSIONS</small></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="stat-card"><h3>{rebond:.1f}%</h3><small>REBOND</small></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="stat-card"><h3>{int(med)}s</h3><small>MÉDIANE</small></div>', unsafe_allow_html=True)
            c4.markdown(f'<div class="stat-card"><h3>{int(mean_v)}s</h3><small>MOYENNE</small></div>', unsafe_allow_html=True)

            # --- GRAPHIQUE DOUBLE AXE Y AVEC COULEURS FIXES ---
            filtered['Bucket'] = filtered['Durée'].apply(get_bucket)
            buckets = sorted(filtered['Bucket'].unique(), key=get_sort_val)
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            regies_plot = sorted(filtered['Regie'].unique())
            
            # Palette de couleurs fixe pour garantir la correspondance
            color_palette = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
            regie_colors = {r: color_palette[i % len(color_palette)] for i, r in enumerate(regies_plot)}

            for r in regies_plot:
                r_data = filtered[filtered['Regie'] == r]
                b_counts = r_data['Bucket'].value_counts()
                
                # Trace pour les 0s (Axe Secondaire)
                fig.add_trace(go.Bar(
                    name=f"{r} (0s)", x=["0 sec"], y=[b_counts.get("0 sec", 0)],
                    marker_color=regie_colors[r], legendgroup=r, showlegend=False
                ), secondary_y=True)
                
                # Trace pour Engagé (Axe Principal)
                other_b = [b for b in buckets if b != "0 sec"]
                fig.add_trace(go.Bar(
                    name=r, x=other_b, y=[b_counts.get(b, 0) for b in other_b],
                    marker_color=regie_colors[r], legendgroup=r, showlegend=True
                ), secondary_y=False)

            # Lignes de stats
            stats_colors = {"q1": "#3498db", "med": "#e74c3c", "q3": "#2ecc71", "moy": "#f39c12"}
            for val, name, col, dash in [(q1,'Q1','q1','dot'), (med,'MED','med','solid'), (q3,'Q3','q3','dot'), (mean_v,'MOY','moy','dash')]:
                b_pos = get_bucket(val)
                fig.add_vline(x=b_pos, line_width=2, line_dash=dash, line_color=stats_colors[col])

            fig.update_layout(barmode='stack', height=600, title_text="Distribution avec Couleurs Verrouillées", xaxis_title="Durée", legend=dict(orientation="h", y=-0.2))
            fig.update_yaxes(title_text="Sessions Engagées", secondary_y=False)
            fig.update_yaxes(title_text="Volume Rebond (0s)", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)

            # --- TABLEAU COMPARATIF ---
            max_v = filtered['Regie'].value_counts().max()
            comp_rows = []
            for r in regies_plot:
                r_d = filtered[filtered['Regie'] == r]
                vol = len(r_d)
                p_reb = (len(r_d[r_d['Durée'] == 0]) / vol * 100)
                p_top = (len(r_d[r_d['Durée'] > 180]) / vol * 100)
                comp_rows.append(f"<tr><td class='regie-name'>{r}</td><td><div class='data-bar' style='width:{vol/max_v*100}%; background:#3498db;'></div><span class='cell-value'>{vol:,}</span></td><td><div class='data-bar' style='width:{p_reb}%; background:#e74c3c;'></div><span class='cell-value'>{p_reb:.1f}%</span></td><td><div class='data-bar' style='width:{p_top}%; background:#2ecc71;'></div><span class='cell-value'>{p_top:.1f}%</span></td></tr>")

            st.write(f"<table class='comparison-table'><thead><tr><th>Régie</th><th>Volume</th><th>Rebond</th><th>Top (+3m)</th></tr></thead><tbody>{''.join(comp_rows)}</tbody></table>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Une erreur s'est produite : {e}")
