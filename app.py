import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# 1. Configuration Page
st.set_page_config(page_title="Marine Nationale - Dashboard V20", layout="wide")

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

        # --- 🔧 MAPPING DES COLONNES ---
        c_source_detail = 'Source'              
        c_regie_groupe  = 'Source recodifiée2'  
        c_campagne      = 'Campagne recodifiée' 
        
        # C'est cette colonne qui devient la STAR du dashboard
        c_variante      = 'Campagne - Variante' 

        c_duree   = 'Durée visite'  
        c_visites = 'Visites'       

        # Vérification
        required_cols = [c_source_detail, c_regie_groupe, c_campagne, c_duree, c_visites, c_variante]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            st.error(f"❌ Colonnes introuvables : {missing}")
            st.stop()

        # Nettoyage
        for col in [c_source_detail, c_regie_groupe, c_campagne, c_variante]:
            df[col] = df[col].astype(str).replace('nan', 'N/A')

        df['D_num'] = pd.to_numeric(df[c_duree], errors='coerce').fillna(0)
        df['V_num'] = pd.to_numeric(df[c_visites], errors='coerce').fillna(0).astype(int)

        # Création du dataset
        df_work = pd.DataFrame({
            'Durée':    np.repeat(df['D_num'].values, df['V_num'].values),
            'Source':   np.repeat(df[c_source_detail].values, df['V_num'].values),
            'Regie':    np.repeat(df[c_regie_groupe].values, df['V_num'].values),
            'Campagne': np.repeat(df[c_campagne].values, df['V_num'].values),
            'Variante': np.repeat(df[c_variante].values, df['V_num'].values) # Nouvelle colonne clé
        }).reset_index(drop=True)

        # --- FILTRES SIDEBAR MODIFIÉS ---
        st.sidebar.header("🎯 Filtres")
        sel_src = st.sidebar.multiselect("Sources", sorted(df_work['Source'].unique()))
        sel_cmp = st.sidebar.multiselect("Campagnes", sorted(df_work['Campagne'].unique()))
        
        # --- NOUVELLE LOGIQUE TOP > 100 SUR VARIANTE ---
        # On compte le nombre de lignes par Variante (puisque le dataset est déjà éclaté par visite, count = sum des visites)
        counts = df_work['Variante'].value_counts()
        
        exclude_low = st.sidebar.toggle("🚀 Top Variantes (>100 visites)", value=False)
        
        # Liste de base
        all_variants = sorted([str(r) for r in df_work['Variante'].unique()])
        
        # Si le bouton est actif, on ne garde que celles > 100
        var_list = all_variants
        if exclude_low:
            var_list = sorted([str(r) for r in counts.index if counts[r] >= 100])
        
        # Le selectbox affiche maintenant les VARIANTES
        sel_var = st.sidebar.multiselect("Variantes (ex-Régies)", var_list)
        
        calc_mode = st.sidebar.selectbox("Calcul des Stats", ["Global (avec 0s)", "Engagement (sans 0s)"], index=1)

        # Application filtres
        filtered = df_work.copy()
        if sel_src: filtered = filtered[filtered['Source'].isin(sel_src)]
        if sel_cmp: filtered = filtered[filtered['Campagne'].isin(sel_cmp)]
        
        # Filtre sur VARIANTE
        if sel_var: 
            filtered = filtered[filtered['Variante'].isin(sel_var)]
        elif exclude_low: 
            filtered = filtered[filtered['Variante'].isin(var_list)]

        if not filtered.empty:
            # Stats KPI
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

            # --- GRAPHIQUE EMPILÉ PAR VARIANTE ---
            filtered['Bucket'] = filtered['Durée'].apply(get_bucket)
            buckets = sorted(filtered['Bucket'].unique(), key=get_sort_val)
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # On utilise les variantes filtrées pour l'affichage
            variants_plot = sorted(filtered['Variante'].unique())
            
            # Palette large
            colors = px.colors.qualitative.Dark24 + px.colors.qualitative.Alphabet
            
            for i, v in enumerate(variants_plot):
                v_data = filtered[filtered['Variante'] == v]
                b_counts = v_data['Bucket'].value_counts()
                col_code = colors[i % len(colors)]
                
                # Trace pour les 0s (Rebond)
                fig.add_trace(go.Bar(
                    name=f"{v} (0s)", x=["0 sec"], y=[b_counts.get("0 sec", 0)],
                    marker_color=col_code, legendgroup=v, showlegend=False, opacity=0.6
                ), secondary_y=True)
                
                # Trace pour l'Engagement
                other_b = [b for b in buckets if b != "0 sec"]
                fig.add_trace(go.Bar(
                    name=v, x=other_b, y=[b_counts.get(b, 0) for b in other_b],
                    marker_color=col_code, legendgroup=v, showlegend=True
                ), secondary_y=False)

            # Lignes verticales stats
            stats_colors = {"q1": "#3498db", "med": "#e74c3c", "q3": "#2ecc71", "moy": "#f39c12"}
            for val, name, col, dash in [(q1,'Q1','q1','dot'), (med,'MED','med','solid'), (q3,'Q3','q3','dot'), (mean_v,'MOY','moy','dash')]:
                b_pos = get_bucket(val)
                fig.add_vline(x=b_pos, line_width=2, line_dash=dash, line_color=stats_colors[col])

            fig.update_layout(barmode='stack', height=600, title_text="Distribution par Variante", xaxis_title="Durée", legend=dict(orientation="h", y=-0.3))
            fig.update_yaxes(title_text="Sessions Engagées", secondary_y=False)
            fig.update_yaxes(title_text="Volume Rebond (0s)", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True)

            # --- TABLEAU MODIFIÉ : AFFICHAGE PAR VARIANTE ---
            # On boucle sur les variantes au lieu des régies
            max_v = filtered['Variante'].value_counts().max()
            comp_rows = []
            
            for v in variants_plot:
                v_d = filtered[filtered['Variante'] == v]
                vol = len(v_d)
                p_reb = (len(v_d[v_d['Durée'] == 0]) / vol * 100) if vol > 0 else 0
                p_top = (len(v_d[v_d['Durée'] > 180]) / vol * 100) if vol > 0 else 0
                
                # Le nom affiché dans la première colonne est v (la Variante)
                comp_rows.append(f"<tr><td class='regie-name'>{v}</td><td><div class='data-bar' style='width:{vol/max_v*100}%; background:#3498db;'></div><span class='cell-value'>{vol:,}</span></td><td><div class='data-bar' style='width:{p_reb}%; background:#e74c3c;'></div><span class='cell-value'>{p_reb:.1f}%</span></td><td><div class='data-bar' style='width:{p_top}%; background:#2ecc71;'></div><span class='cell-value'>{p_top:.1f}%</span></td></tr>")

            st.write(f"<table class='comparison-table'><thead><tr><th>Variante</th><th>Volume</th><th>Rebond</th><th>Top (+3m)</th></tr></thead><tbody>{''.join(comp_rows)}</tbody></table>", unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Une erreur s'est produite : {e}")
