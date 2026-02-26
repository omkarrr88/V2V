"""
V2V Blind Spot Detection — Platinum Intelligence Dashboard (V3.2 Final)
========================================================================
The ultimate research & analysis suite.
- Tactical Map with Scanning Matrix
- Live Parameter Sandbox & Historical Replay
- AI Discrepancy & Performance Analytics
- Network Health & Packet Loss Monitoring
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import os
import time

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="V2V BSD Platinum Suite",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700;800&display=swap');

:root {
    --bg-dark: #05070d;
    --bg-panel: rgba(15, 20, 31, 0.75);
    --border-light: rgba(255, 255, 255, 0.1);
    --text-primary: #f8fafc;
    --text-muted: #94a3b8;
    --accent-primary: #6366f1;
}

.stApp {
    font-family: 'Outfit', sans-serif !important;
    background-color: var(--bg-dark);
    background-image: 
        radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.12) 0%, transparent 40%),
        radial-gradient(ellipse at bottom right, rgba(16, 185, 129, 0.08) 0%, transparent 40%);
    background-attachment: fixed;
    color: var(--text-primary);
}

/* Glass Cards */
.glass-card {
    background: var(--bg-panel);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border-light);
    border-radius: 18px;
    padding: 24px;
    text-align: center;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
}

.glow-safe { box-shadow: 0 0 15px rgba(16, 185, 129, 0.15); border-color: rgba(16, 185, 129, 0.2) !important; }
.glow-caution { box-shadow: 0 0 15px rgba(245, 158, 11, 0.15); border-color: rgba(245, 158, 11, 0.2) !important; }
.glow-warning { box-shadow: 0 0 20px rgba(249, 115, 22, 0.2); border-color: rgba(249, 115, 22, 0.3) !important; }
.glow-critical { box-shadow: 0 0 30px rgba(239, 68, 68, 0.3); border-color: rgba(239, 68, 68, 0.5) !important; animation: border-pulse 1.5s infinite; }

@keyframes border-pulse {
    0% { border-color: rgba(239, 68, 68, 0.5); }
    50% { border-color: rgba(239, 68, 68, 1); }
    100% { border-color: rgba(239, 68, 68, 0.5); }
}

/* Scanning Effect */
.scanning-bg {
    position: relative;
    overflow: hidden;
    border-radius: 18px;
    border: 1px solid var(--border-light);
    background: #0a0c10;
}
.scanning-bg::after {
    content: "";
    position: absolute;
    top: -100%; left: -100%; width: 300%; height: 300%;
    background: conic-gradient(from 0deg, transparent, rgba(99, 102, 241, 0.08), transparent 30%);
    animation: sweep 5s linear infinite;
    pointer-events: none;
    z-index: 1;
}
@keyframes sweep { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* Section Headers */
.section-head {
    font-size: 1.2rem;
    font-weight: 700;
    margin: 1.5rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 12px;
    color: var(--text-primary);
    border-left: 4px solid var(--accent-primary);
    padding-left: 12px;
}

.metric-label { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 4px; }
.metric-val { font-size: 2.2rem; font-weight: 800; font-family: 'JetBrains Mono', monospace; color: white; }

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {background: transparent !important;}
[data-testid="stMetricValue"] > div { font-family: 'JetBrains Mono', monospace !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATA HANDLING
# ============================================================
LIVE_FILE    = "../Outputs/bsd_live.json"
METRICS_FILE = "../Outputs/bsd_metrics.csv"

def alert_color(alert: str) -> str:
    C = {'SAFE': '#10b981', 'CAUTION': '#f59e0b', 'WARNING': '#f97316', 'CRITICAL': '#ef4444'}
    return C.get(str(alert).upper(), '#64748b')

def get_params_safe(raw_dict):
    """Normalize parameter keys to uppercase and provide defaults."""
    defaults = {"ALPHA": 0.15, "BETA": 0.80, "GAMMA": 0.05, "THETA_3": 0.005}
    if not isinstance(raw_dict, dict): return defaults
    norm = {str(k).upper(): v for k, v in raw_dict.items()}
    # Fill missing from defaults
    for k, v in defaults.items():
        if k not in norm: norm[k] = v
    return norm

def load_live_data():
    if not os.path.exists(LIVE_FILE): return None
    try:
        with open(LIVE_FILE, 'r') as f: 
            data = json.load(f)
            if data: st.session_state.last_good_data = data
            return data
    except: 
        return st.session_state.get('last_good_data')

@st.cache_data(ttl=2)
def load_alerts_history():
    if not os.path.exists("../Outputs/bsd_alerts.csv"): return pd.DataFrame()
    try:
        df = pd.read_csv("../Outputs/bsd_alerts.csv")
        return df.sort_values('step', ascending=False).head(50)
    except: return pd.DataFrame()

@st.cache_data(ttl=5)
def load_metrics_df():
    if not os.path.exists(METRICS_FILE): return None
    return pd.read_csv(METRICS_FILE)

# ============================================================
# STATE
# ============================================================
if "mode" not in st.session_state: st.session_state.mode = "LIVE Tracking"
if "sandbox" not in st.session_state: st.session_state.sandbox = False
if "sandbox_weights" not in st.session_state: st.session_state.sandbox_weights = {"ALPHA": 0.15, "BETA": 0.80, "GAMMA": 0.05}
if "frozen_data" not in st.session_state: st.session_state.frozen_data = None
if "cached_vids" not in st.session_state: st.session_state.cached_vids = []

# ============================================================
# UTILS
# ============================================================
def recalculate_cri_sandbox(tt_list, weights):
    re_cris = []
    # Ensure weights are normalized safely
    w_norm = get_params_safe(weights)
    for tt in tt_list:
        R_weighted = w_norm['ALPHA'] * tt.get('R_decel', 0.0) + \
                     w_norm['BETA'] * tt.get('R_ttc', 0.0) + \
                     w_norm['GAMMA'] * tt.get('R_intent', 0.0)
        plr_multiplier = 1.0 + 0.30 * tt.get('plr', 0.0)
        new_cri = np.clip(tt.get('P', 0.0) * R_weighted * plr_multiplier, 0.0, 1.0)
        new_tt = tt.copy(); new_tt['cri'] = new_cri; re_cris.append(new_tt)
    return re_cris

# ============================================================
# FRAGMENT: THE INTELLIGENCE ENGINE
# ============================================================
@st.fragment(run_every="2.5s" if st.session_state.mode == "LIVE Tracking" and not st.session_state.frozen_data else None)
def render_platinum_ui():
    # 1. LOAD DATA
    if st.session_state.mode == "LIVE Tracking":
        data = st.session_state.frozen_data if st.session_state.frozen_data else load_live_data()
        if not data: st.info("Initializing Uplink..."); return
        vehicles = data.get('vehicles', {})
        step = data.get('step', 0)
        orig_params = get_params_safe(data.get('params'))
    else:
        df = load_metrics_df()
        if df is None: st.error("No historical log found."); return
        max_step = int(df['step'].max())
        target_step = st.slider("Historical Time Scrubber", 0, max_step, 0)
        s_df = df[df['step'] == target_step]
        step = target_step
        orig_params = get_params_safe({}) # Uses defaults
        vehicles = {}
        for _, row in s_df.iterrows():
            tt_l = {'vid': 'L', 'cri': row['cri_left'], 'P': row['P_left'], 'R_decel': row['R_decel_left'], 'R_ttc': row['R_ttc_left'], 'R_intent': row['R_intent_left'], 'side': 'LEFT'}
            tt_r = {'vid': 'R', 'cri': row['cri_right'], 'P': row['P_right'], 'R_decel': row['R_decel_right'], 'R_ttc': row['R_ttc_right'], 'R_intent': row['R_intent_right'], 'side': 'RIGHT'}
            vehicles[row['ego_vid']] = {
                'x': row['x'], 'y': row['y'], 'speed': row['speed'], 'cri_left': row['cri_left'], 'cri_right': row['cri_right'],
                'alert_left': row['alert_left'], 'alert_right': row['alert_right'], 'ai_alert': row.get('ai_alert', 'N/A'),
                'top_threats': [t for t in [tt_l, tt_r] if t['cri'] > 0]
            }

    # 2. MUTATE (SANDBOX)
    if st.session_state.sandbox:
        for vid in vehicles:
            mut = recalculate_cri_sandbox(vehicles[vid].get('top_threats', []), st.session_state.sandbox_weights)
            vehicles[vid]['top_threats'] = mut
            vehicles[vid]['cri_left'] = max([t['cri'] for t in mut if t['side'] == 'LEFT'], default=0.0)
            vehicles[vid]['cri_right'] = max([t['cri'] for t in mut if t['side'] == 'RIGHT'], default=0.0)
            for s in ['left', 'right']:
                c = vehicles[vid][f'cri_{s}']
                vehicles[vid][f'alert_{s}'] = 'SAFE' if c < 0.3 else ('CAUTION' if c < 0.6 else ('WARNING' if c < 0.8 else 'CRITICAL'))

    # 3. METRICS PREP
    live_cumulative = data.get('alert_counts', {"safe":0, "caution":0, "warning":0, "critical":0})
    
    # Instantaneous counts for current scanning
    counts_now = {"SAFE":0, "CAUTION":0, "WARNING":0, "CRITICAL":0}
    ai_matches = 0
    total_ai = 0
    for v in vehicles.values():
        ma = max(str(v['alert_left']).upper(), str(v['alert_right']).upper(), key=lambda a: ['SAFE','CAUTION','WARNING','CRITICAL'].index(a))
        counts_now[ma] += 1
        if v.get('ai_alert') != 'N/A':
            total_ai += 1
            if v['ai_alert'] == ma: ai_matches += 1
    ai_acc = (ai_matches / total_ai * 100) if total_ai > 0 else 100.0
    
    # Cumulative AI Accuracy (Moving average in session state)
    if "avg_ai_acc" not in st.session_state: st.session_state.avg_ai_acc = 100.0
    st.session_state.avg_ai_acc = 0.95 * st.session_state.avg_ai_acc + 0.05 * ai_acc

    # 4. HEAD: TOP METRICS
    m1, m2, m3, m4, m5 = st.columns(5)
    # Use the true total count from the simulation engine
    total_nodes = data.get('active_count', len(vehicles))
    with m1: st.markdown(f'<div class="glass-card"><div class="metric-label">NETWORK NODES</div><div class="metric-val">{total_nodes}</div></div>', unsafe_allow_html=True)
    with m2: st.markdown(f'<div class="glass-card glow-caution"><div class="metric-label">MODEL SYNC</div><div class="metric-val" style="color:#6366f1;">{st.session_state.avg_ai_acc:.1f}%</div></div>', unsafe_allow_html=True)
    
    # Use Cumulative for the main big cards as requested
    with m3: st.markdown(f'<div class="glass-card glow-warning"><div class="metric-label">TOTAL WARNINGS</div><div class="metric-val" style="color:#f97316;">{live_cumulative.get("warning", 0)}</div></div>', unsafe_allow_html=True)
    with m4: st.markdown(f'<div class="glass-card glow-critical"><div class="metric-label">TOTAL CRITICALS</div><div class="metric-val" style="color:#ef4444;">{live_cumulative.get("critical", 0)}</div></div>', unsafe_allow_html=True)
    
    with m5: st.markdown(f'<div class="glass-card"><div class="metric-label">LATENCY</div><div class="metric-val" style="font-size:1.5rem; margin-top:10px;">{data.get("elapsed",0) if st.session_state.mode=="LIVE Tracking" else 0}s</div></div>', unsafe_allow_html=True)
    
    # Sub-metrics for Instantaneous
    st.markdown(f"""
    <div style="display:flex; justify-content:center; gap:20px; font-size:0.75rem; color:#94a3b8; margin: -10px 0 20px 0;">
        <span>Active Threats: <b style="color:#f97316;">{counts_now['WARNING']} Warning</b> | <b style="color:#ef4444;">{counts_now['CRITICAL']} Critical</b></span>
    </div>
    """, unsafe_allow_html=True)

    # 5. TABS FOR DEEP ANALYSIS
    tab_tactical, tab_analytics, tab_network = st.tabs(["🎯 TACTICAL MAP", "📊 PERFORMANCE LAB", "🌐 NETWORK LAYER"])

    # ------------------------------------------------------------
    # TAB 1: TACTICAL
    # ------------------------------------------------------------
    with tab_tactical:
        c_map, c_insp = st.columns([2, 1])
        with c_map:
            st.markdown(f'<div class="section-head">🗺️ LIVE SCANNING MATRIX (Step {step})</div>', unsafe_allow_html=True)
            if vehicles:
                map_pts = pd.DataFrame([{'vid':k, 'x':v['x'], 'y':v['y'], 'cri':max(v['cri_left'],v['cri_right'])} for k,v in vehicles.items()])
                
                # Base scatter for vehicles
                fig = px.scatter(map_pts, x='x', y='y', text='vid', color='cri', 
                                 color_continuous_scale=[[0, '#10b981'], [0.5, '#f59e0b'], [0.8, '#f97316'], [1, '#ef4444']],
                                 range_color=[0, 1])
                
                # ADD V2V COMMUNICATION LINKS
                links = data.get('comm_links', [])
                link_x, link_y = [], []
                for link in links:
                    e_vid, t_vid = link.get('ego'), link.get('target')
                    if e_vid in vehicles and t_vid in vehicles:
                        e, t = vehicles[e_vid], vehicles[t_vid]
                        link_x.extend([e['x'], t['x'], None])
                        link_y.extend([e['y'], t['y'], None])
                
                if link_x:
                    fig.add_trace(go.Scatter(
                        x=link_x, y=link_y,
                        mode='lines', line=dict(color='rgba(0, 255, 255, 0.4)', width=1, dash='dot'),
                        name='V2V Comm Link', hoverinfo='none', showlegend=True
                    ))

                fig.update_traces(marker=dict(size=20, line=dict(width=2, color='white')))
                fig.update_layout(plot_bgcolor='#0a0c10', paper_bgcolor='rgba(0,0,0,0)', height=600, 
                                  yaxis=dict(scaleanchor="x", gridcolor='rgba(255,255,255,0.05)'), 
                                  xaxis=dict(gridcolor='rgba(255,255,255,0.05)'), font=dict(color='white'))
                st.markdown('<div class="scanning-bg">', unsafe_allow_html=True)
                st.plotly_chart(fig, width='stretch', config={'displayModeBar': False})
                st.markdown('</div>', unsafe_allow_html=True)

        with c_insp:
            st.markdown('<div class="section-head">🔍 TARGET INSPECTOR</div>', unsafe_allow_html=True)
            vids = sorted(vehicles.keys(), key=lambda v: max(vehicles[v]['cri_left'], vehicles[v]['cri_right']), reverse=True)
            if vids:
                # Use session state to keep selection persistent across refreshes
                if "v_sel_tactical" not in st.session_state or st.session_state.v_sel_tactical not in vids:
                    st.session_state.v_sel_tactical = vids[0]
                
                sel_vid = st.selectbox("Lock Target ID", vids, key="v_sel_tactical")
                vd = vehicles[sel_vid]
                mc = max(vd['cri_left'], vd['cri_right'])
                ma = max(vd['alert_left'], vd['alert_right'], key=lambda a: ['SAFE','CAUTION','WARNING','CRITICAL'].index(a))
                
                st.markdown(f"""
                <div class="glass-card glow-{ma.lower()}" style="padding:20px; text-align:left; margin-bottom:20px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:1.5rem; font-weight:800;">{sel_vid}</span>
                        <span style="background:{alert_color(ma)}; color:white; padding:4px 12px; border-radius:30px; font-size:0.8rem;">{ma}</span>
                    </div>
                    <div style="margin-top:15px; font-size:0.9rem;">
                        <div style="display:flex; justify-content:space-between;"><span>Physics CRI:</span><strong>{mc:.3f}</strong></div>
                        <div style="display:flex; justify-content:space-between;"><span>AI Predict:</span><strong style="color:#6366f1;">{vd.get('ai_alert','N/A')}</strong></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                threats = vd.get('top_threats', [])
                if threats:
                    tt = threats[0]
                    # Radar (Radial Decomposition)
                    rf = go.Figure(go.Scatterpolar(
                        r=[tt['P'], tt['R_decel'], tt.get('R_ttc', 0.0), tt['R_intent'], tt['P']],
                        theta=['Prob', 'Brake', 'TTC', 'Intent', 'Prob'],
                        fill='toself', fillcolor='rgba(99, 102, 241, 0.4)', line=dict(color='#6366f1', width=2)
                    ))
                    rf.update_layout(polar=dict(radialaxis=dict(visible=False, range=[0, 1]), bgcolor='rgba(0,0,0,0)'),
                                     paper_bgcolor='rgba(0,0,0,0)', height=250, margin=dict(l=20,r=20,t=20,b=20))
                    st.plotly_chart(rf, width='stretch')
            else: st.info("No active targets.")

    # ------------------------------------------------------------
    # TAB 2: ANALYTICS
    # ------------------------------------------------------------
    with tab_analytics:
        col_acc, col_wf = st.columns([1, 2])
        with col_acc:
            st.markdown('<div class="section-head">🧠 AI vs PHYSICS SYNC</div>', unsafe_allow_html=True)
            # Gauges
            fig_acc = go.Figure(go.Indicator(
                mode = "gauge+number", value = ai_acc, title = {'text': "Model Agreement %", 'font':{'size':14}},
                gauge = {'axis': {'range': [0, 100], 'tickcolor': "white"},
                         'bar': {'color': "#6366f1"},
                         'steps': [{'range': [0, 70], 'color': "rgba(239, 68, 68, 0.2)"},
                                   {'range': [70, 90], 'color': "rgba(245, 158, 11, 0.2)"},
                                   {'range': [90, 100], 'color': "rgba(16, 185, 129, 0.2)"}]}
            ))
            fig_acc.update_layout(height=300, paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
            st.plotly_chart(fig_acc, width='stretch')
        
        with col_wf:
            st.markdown('<div class="section-head">🌊 RISK WATERFALL (Feature Attribution)</div>', unsafe_allow_html=True)
            if vids:
                # Analyze Subject
                sel_vid_wf = st.selectbox("Analyze Subject", vids, key="v_sel_wf")
                vd_wf = vehicles[sel_vid_wf]
                threats_wf = vd_wf.get('top_threats', [])
                if threats_wf:
                    tt = threats_wf[0]
                    # Normalize current active weights
                    cur_w = get_params_safe(st.session_state.sandbox_weights if st.session_state.sandbox else orig_params)
                    
                    y_vals = [
                        tt.get('P',0) * cur_w['ALPHA'] * tt.get('R_decel',0),
                        tt.get('P',0) * cur_w['BETA'] * tt.get('R_ttc',0),
                        tt.get('P',0) * cur_w['GAMMA'] * tt.get('R_intent',0)
                    ]
                    total = tt['cri']
                    
                    fig_wf = go.Figure(go.Waterfall(
                        name = "CRI Contribution", orientation = "v",
                        measure = ["relative", "relative", "relative", "total"],
                        x = ["Brake Risk", "TTC Risk", "Intent Risk", "Final CRI"],
                        y = [y_vals[0], y_vals[1], y_vals[2], total],
                        connector = {"line":{"color":"rgba(255,255,255,0.2)"}},
                        increasing = {"marker":{"color":"#ef4444"}},
                        totals = {"marker":{"color":"#6366f1"}}
                    ))
                    fig_wf.update_layout(height=350, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                         font=dict(color='white'), margin=dict(l=40,r=40,t=40,b=40))
                    st.plotly_chart(fig_wf, width='stretch')

    # ------------------------------------------------------------
    # TAB 3: NETWORK
    # ------------------------------------------------------------
    with tab_network:
        st.markdown('<div class="section-head">📡 V2V LAYER HEALTH (Gilbert-Elliott Channel)</div>', unsafe_allow_html=True)
        col_net1, col_net2 = st.columns(2)
        with col_net1:
            total_plr = []
            for v in vehicles.values():
                for t in v.get('top_threats', []):
                    if 'plr' in t: total_plr.append(t['plr'])
            avg_plr = np.mean(total_plr) if total_plr else 0.05
            
            st.metric("Avg Packet Loss Rate", f"{avg_plr*100:.1f}%", delta=f"{0.05-avg_plr:.2f}", delta_color="inverse")
            st.info("The Markov-Chain channel transitions between GOOD and BURSTY states based on vehicle proximity.")
            
            # Persistent Alert History 
            st.markdown('<div class="section-head">📜 PERSISTENT ALERT FEED</div>', unsafe_allow_html=True)
            history_df = load_alerts_history()
            if not history_df.empty:
                st.dataframe(history_df, width='stretch', hide_index=True)
            else:
                st.write("Monitoring for events...")
            fig_comm = go.Figure(go.Indicator(
                mode = "gauge+number", value = len(vehicles),
                title = {'text': "Network Participating Nodes", 'font':{'size':14}},
                gauge = {'bar': {'color': "#10b981"}}
            ))
            fig_comm.update_layout(height=250, paper_bgcolor='rgba(0,0,0,0)', font={'color': "white"})
            st.plotly_chart(fig_comm, width='stretch')

# ============================================================
# SIDEBAR RE-INTEGRATED
# ============================================================
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; margin-bottom: 30px;">
        <h2 style="margin:0; color:#6366f1; font-weight:800; font-size:1.8rem;">PLATINUM V3.2</h2>
        <div style="font-size:0.7rem; color:#94a3b8; letter-spacing:2px;">INTELLIGENCE ENGINE</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.session_state.mode = st.radio("SELECT MODE", ["LIVE Tracking", "Historical Replay"], help="Switch between real-time and post-sim analysis")
    
    st.markdown("---")
    st.markdown("### 🧪 PARAMETER SANDBOX")
    st.session_state.sandbox = st.toggle("Enable Mutation Mode", help="Interactively modify model weights")
    
    if st.session_state.sandbox:
        st.warning("MUTATION ACTIVE: Recalculating all risks.")
        st.session_state.sandbox_weights["ALPHA"] = st.slider("α (Brake)", 0.0, 1.0, st.session_state.sandbox_weights["ALPHA"])
        st.session_state.sandbox_weights["BETA"] = st.slider("β (TTC)", 0.0, 1.0, st.session_state.sandbox_weights["BETA"])
        st.session_state.sandbox_weights["GAMMA"] = st.slider("γ (Intent)", 0.0, 1.0, st.session_state.sandbox_weights["GAMMA"])
        tw = sum(st.session_state.sandbox_weights.values())
        if tw > 0:
            for k in st.session_state.sandbox_weights: st.session_state.sandbox_weights[k] /= tw
    
    st.markdown("---")
    if st.button("❄️ Capture Snapshot"):
        st.session_state.frozen_data = load_live_data()
        st.toast("Telemetry Frozen!")
    
    if st.session_state.frozen_data and st.button("🔥 Resume"):
        st.session_state.frozen_data = None
        st.rerun()

    st.markdown("---")
    st.markdown('<div style="font-size:0.8rem; color:#94a3b8;">Status: <span style="color:#10b981;">● Online</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.8rem; color:#94a3b8;">Hardware: GPU-ACCELERATED</div>', unsafe_allow_html=True)

# LAUNCH
render_platinum_ui()