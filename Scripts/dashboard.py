"""
V2V Blind Spot Detection — Premium Dashboard
================================================================
Advanced Streamlit dashboard for monitoring the V2V BSD simulation.
Features real-time CRI values, alert levels, vehicle maps, radar analytics, and AI validation.
"""

import streamlit as st  # type: ignore
import pandas as pd  # type: ignore
import numpy as np  # type: ignore
import plotly.express as px  # type: ignore
import plotly.graph_objects as go  # type: ignore
from plotly.subplots import make_subplots  # type: ignore
import json
import os
import time

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="V2V BSD Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS — Premium Glassmorphism Theme
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;700;800&display=swap');

:root {
    --bg-dark: #05070d;
    --bg-panel: rgba(15, 20, 31, 0.7);
    --border-light: rgba(255, 255, 255, 0.08);
    --text-primary: #f8fafc;
    --text-muted: #94a3b8;
}

.stApp {
    font-family: 'Outfit', sans-serif !important;
    background-color: var(--bg-dark);
    background-image: 
        radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
        radial-gradient(ellipse at bottom right, rgba(16, 185, 129, 0.05) 0%, transparent 40%);
    background-attachment: fixed;
    color: var(--text-primary);
}

.glass-card {
    background: var(--bg-panel);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--border-light);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
}

.glass-card:hover {
    transform: translateY(-4px);
    border-color: rgba(255, 255, 255, 0.2);
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.4);
    background: rgba(20, 27, 41, 0.85);
}

.metric-label {
    font-size: 0.8rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
    margin-bottom: 8px;
}

.metric-val {
    font-size: 2.8rem;
    font-weight: 800;
    line-height: 1;
    font-family: 'JetBrains Mono', monospace;
    background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.val-safe { background: linear-gradient(135deg, #34d399, #10b981) !important; -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important; }
.val-caution { background: linear-gradient(135deg, #fbbf24, #f59e0b) !important; -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important; }
.val-warning { background: linear-gradient(135deg, #fb923c, #f97316) !important; -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important; }
.val-critical { background: linear-gradient(135deg, #f87171, #ef4444) !important; -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important; filter: drop-shadow(0 0 8px rgba(239, 68, 68, 0.5)); animation: pulse 1.5s infinite;}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.7; }
    100% { opacity: 1; }
}

.section-head {
    font-size: 1.4rem;
    font-weight: 700;
    margin: 1.5rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 10px;
    border-bottom: 1px solid var(--border-light);
    padding-bottom: 0.5rem;
}

.status-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.2);
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    color: #34d399;
}
.status-indicator .dot {
    width: 8px;
    height: 8px;
    background: #10b981;
    border-radius: 50%;
    animation: blink 2s infinite;
}
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Sidebar overrides */
[data-testid="stSidebar"] {
    background-color: rgba(9, 11, 17, 0.95) !important;
    border-right: 1px solid var(--border-light);
}

.sidebar-panel {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
/* Header visible so sidebar can be toggled */
header {background: transparent !important;}
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATA LOADING
# ============================================================
LIVE_FILE    = "../Outputs/bsd_live.json"
METRICS_FILE = "../Outputs/bsd_metrics.csv"
ALERTS_FILE  = "../Outputs/bsd_alerts.csv"

@st.cache_data(ttl=2)
def load_live_data():
    try:
        if os.path.exists(LIVE_FILE):
            with open(LIVE_FILE, 'r') as f:
                return json.load(f), None
    except Exception as e:
        return None, str(e)
    return None, "File not found"

@st.cache_data(ttl=5)
def load_metrics():
    try:
        if os.path.exists(METRICS_FILE):
            return pd.read_csv(METRICS_FILE), None
    except Exception as e:
        return None, str(e)
    return None, "File not found"

@st.cache_data(ttl=5)
def load_alerts():
    try:
        if os.path.exists(ALERTS_FILE):
            return pd.read_csv(ALERTS_FILE), None
    except Exception as e:
        return None, str(e)
    return None, "File not found"

def cri_color(cri: float) -> str:
    if cri >= 0.80: return "#ef4444"
    if cri >= 0.60: return "#f97316"
    if cri >= 0.30: return "#f59e0b"
    return "#10b981"

def alert_color(alert: str) -> str:
    C = {'SAFE': '#10b981', 'CAUTION': '#f59e0b', 'WARNING': '#f97316', 'CRITICAL': '#ef4444'}
    return C.get(alert, '#64748b')

def alert_emoji(alert: str) -> str:
    E = {'SAFE': '🟢', 'CAUTION': '🟡', 'WARNING': '🟠', 'CRITICAL': '🔴'}
    return E.get(alert, '⚪')

# ============================================================
# OMNIPRESENT SIDEBAR (VEHICLE INSPECTOR)
# ============================================================
st.sidebar.markdown("""
<div style="text-align: center; margin-bottom: 20px;">
    <h2 style="margin: 0; font-size: 1.5rem; color: #f8fafc; font-weight: 800;">🔍 INSPECTOR</h2>
    <div style="font-size: 0.8rem; color: #6366f1;">Subject Telemetry Focus</div>
</div>
""", unsafe_allow_html=True)

is_live = st.sidebar.toggle("🟢 Live Telemetry Sync", value=True)
st.sidebar.markdown("---")

# ============================================================
# AUTO-REFRESH
# ============================================================
if is_live:
    try:
        from streamlit_autorefresh import st_autorefresh # type: ignore
        st_autorefresh(interval=3000, key="dash_autorefresh")
    except Exception:
        now = time.time()
        if 'last_rerun_ts' not in st.session_state:
            st.session_state.last_rerun_ts = now
        if now - st.session_state.last_rerun_ts >= 3.0:
            st.session_state.last_rerun_ts = now
            st.rerun()

# ============================================================
# HEADER
# ============================================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 24px;">
        <div style="font-size: 3rem; filter: drop-shadow(0 0 10px rgba(99,102,241,0.5));">🛡️</div>
        <div>
            <h1 style="margin: 0; font-size: 2.2rem; font-weight: 800;
                background: linear-gradient(135deg, #a855f7 0%, #6366f1 50%, #10b981 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                V2V BSD Intelligence Core
            </h1>
            <h3 style="margin: 4px 0 0; color: #f8fafc; font-size: 1.2rem; font-weight: 600;">🚗 V2V Blind Spot Detection</h3>
            <p style="margin: 0; color: #94a3b8; font-size: 1rem; font-weight: 500;">
                Mathematical Model V3.0 + AI Hybrid Engine
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_h2:
    st.markdown("""
    <div style="text-align: right; padding-top: 15px;">
        <div class="status-indicator">
            <div class="dot"></div>
            LIVE STREAM
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# LOAD DATA & PREPARE
# ============================================================
live_data, _ = load_live_data()
metrics_df, _ = load_metrics()
alerts_df, _ = load_alerts()

if live_data is None:
    st.markdown("""
    <div style="text-align: center; padding: 100px 20px;">
        <span style="font-size: 5rem;">📡</span>
        <h2 style="color: #f8fafc; margin-top: 20px;">Awaiting Telemetry Data...</h2>
        <p style="color: #94a3b8;">Start the simulation engine: <code>python v2v_bsd_simulation.py --steps 3600</code></p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

vehicles = live_data.get('vehicles', {})
alert_counts = live_data.get('alert_counts', {})
current_step = live_data.get('step', 0)
active_count = live_data.get('active_count', 0)
has_ai = live_data.get('has_ai', False)

# ============================================================
# METRICS STRIP
# ============================================================
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(f"""<div class="glass-card"><div class="metric-label">Active Tracked</div>
    <div class="metric-val" style="color:#6366f1;">{active_count}</div></div>""", unsafe_allow_html=True)
with m2:
    st.markdown(f"""<div class="glass-card"><div class="metric-label">🟢 Safe Zones</div>
    <div class="metric-val val-safe">{alert_counts.get('safe', 0)}</div></div>""", unsafe_allow_html=True)
with m3:
    st.markdown(f"""<div class="glass-card"><div class="metric-label">🟡 Caution</div>
    <div class="metric-val val-caution">{alert_counts.get('caution', 0)}</div></div>""", unsafe_allow_html=True)
with m4:
    st.markdown(f"""<div class="glass-card"><div class="metric-label">🟠 Warnings</div>
    <div class="metric-val val-warning">{alert_counts.get('warning', 0)}</div></div>""", unsafe_allow_html=True)
with m5:
    st.markdown(f"""<div class="glass-card"><div class="metric-label">🔴 Critical Alerts</div>
    <div class="metric-val val-critical">{alert_counts.get('critical', 0)}</div></div>""", unsafe_allow_html=True)

st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); padding: 8px 16px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05); margin-bottom: 24px;">
    <div style="color: #94a3b8; font-size: 0.9rem;">
        Simulation Time: <strong style="color: #f8fafc;">{current_step * 0.1:.1f}s</strong> (Step {current_step})
    </div>
    <div>
        {'<span style="background: linear-gradient(135deg, #6366f1, #a855f7); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; box-shadow: 0 0 10px rgba(99,102,241,0.4);">🤖 AI Core Enabled</span>' if has_ai else '<span style="background: #334155; color: #94a3b8; padding: 4px 12px; border-radius: 20px; font-size: 0.8rem;">AI Offline</span>'}
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# MAIN TABS ARCHITECTURE
# ============================================================
tab_overview, tab_analytics, tab_system, tab_v2v = st.tabs(["🌐 Tactical Map", "📈 Analytics & AI Insights", "⚙️ Network & Parameters", "📡 V2V Matrix"])

# ------------------------------------------------------------
# TAB 1: OVERVIEW & MAP
# ------------------------------------------------------------
with tab_overview:
    if not vehicles:
        st.info("No vehicles currently active in simulation.")
    else:
        # Prepare Map Data
        map_data = []
        links_x = []
        links_y = []
        links_c = []
        
        for vid, vdata in vehicles.items():
            max_alert = 'SAFE'
            for a in [vdata.get('alert_left', 'SAFE'), vdata.get('alert_right', 'SAFE')]:
                if ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL'].index(a) > ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL'].index(max_alert):
                    max_alert = a
            
            map_data.append({
                'vid': vid,
                'x': vdata['x'], 'y': vdata['y'],
                'speed': vdata.get('speed', 0),
                'max_cri': max(vdata.get('cri_left', 0), vdata.get('cri_right', 0)),
                'alert': max_alert
            })
            
            # Draw lines to active threats
            threats = vdata.get('top_threats', [])
            for t in threats:
                if t['vid'] in vehicles:
                    tv = vehicles[t['vid']]
                    links_x.extend([vdata['x'], tv['x'], None])
                    links_y.extend([vdata['y'], tv['y'], None])
                    links_c.extend([t['cri'], t['cri'], None])

        map_df = pd.DataFrame(map_data)
        fig_map = go.Figure()
        
        # Threat Links
        if links_x:
            fig_map.add_trace(go.Scatter(
                x=links_x, y=links_y,
                mode='lines',
                line={'width': 1.5, 'color': 'rgba(239, 68, 68, 0.4)', 'dash': 'dot'},
                hoverinfo='none',
                name='Active Threats'
            ))

        # Vehicle Markers
        for alrt in ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL']:
            sub = map_df[map_df['alert'] == alrt]
            if sub.empty: continue # type: ignore
            fig_map.add_trace(go.Scatter(
                x=sub['x'], y=sub['y'],
                mode='markers+text',
                marker={
                    'size': np.where(sub['alert'] == 'CRITICAL', 20, np.where(sub['alert'] == 'WARNING', 16, 12)),
                    'color': alert_color(alrt),
                    'line': {'width': 2, 'color': '#ffffff' if alrt == 'CRITICAL' else 'rgba(255,255,255,0.4)'},
                    'symbol': 'triangle-up' # Give cars directionality later if desired
                },
                text=sub['vid'],
                textposition="bottom center",
                textfont={'color': '#94a3b8', 'size': 10},
                name=f"{alert_emoji(alrt)} {alrt}",
                hovertemplate="<b>%{text}</b><br>Speed: %{customdata[0]:.1f} m/s<br>Max CRI: %{customdata[1]:.3f}<extra></extra>",
                customdata=sub[['speed', 'max_cri']]
            ))
            
        fig_map.update_layout(
            plot_bgcolor='rgba(15, 20, 31, 0.6)',
            paper_bgcolor='rgba(0,0,0,0)',
            font={'family': 'Outfit', 'color': '#f8fafc'},
            height=650,
            margin={'l': 10, 'r': 10, 't': 40, 'b': 10},
            legend={'orientation': 'h', 'y': 1.05, 'x': 0.5, 'xanchor': 'center', 'bgcolor': 'rgba(0,0,0,0)'},
            xaxis={'title': '', 'gridcolor': 'rgba(255,255,255,0.05)', 'zerolinecolor': 'rgba(255,255,255,0.1)'},
            yaxis={'title': '', 'gridcolor': 'rgba(255,255,255,0.05)', 'zerolinecolor': 'rgba(255,255,255,0.1)', 'scaleanchor': 'x'},
        )
        
        st.markdown('<div class="section-head">🗺️ Tactical Coordinate Map</div>', unsafe_allow_html=True)
        st.plotly_chart(fig_map, width='stretch')


# ------------------------------------------------------------
# TAB 2: ANALYTICS & AI INSIGHTS
# ------------------------------------------------------------
with tab_analytics:
    ac1, ac2 = st.columns(2)
    with ac1:
        st.markdown('<div class="section-head">📊 CRI Distribution (Fleet-wide)</div>', unsafe_allow_html=True)
        if vehicles:
            cl = [v.get('cri_left', 0) for v in vehicles.values()]
            cr = [v.get('cri_right', 0) for v in vehicles.values()]
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(x=cl, name='Left Blind Spot', marker_color='#a855f7', opacity=0.75, nbinsx=25))
            fig_dist.add_trace(go.Histogram(x=cr, name='Right Blind Spot', marker_color='#3b82f6', opacity=0.75, nbinsx=25))
            for thresh, name, c in [(0.3, 'CAUTION', '#f59e0b'), (0.6, 'WARN', '#f97316'), (0.8, 'CRIT', '#ef4444')]:
                fig_dist.add_vline(x=thresh, line_dash="dash", line_color=c, annotation_text=name, annotation_position="top")
            fig_dist.update_layout(barmode='overlay', plot_bgcolor='rgba(0,0,0,0.2)', paper_bgcolor='rgba(0,0,0,0)',
                                   font={'family': 'Outfit', 'color': '#f8fafc'}, height=350, margin={'l': 20, 'r': 10, 't': 30, 'b': 20},
                                   xaxis={'title': 'Collision Risk Index (CRI)', 'gridcolor': 'rgba(255,255,255,0.05)', 'range': [0, 1]},
                                   yaxis={'title': 'Vehicle Frequency', 'gridcolor': 'rgba(255,255,255,0.05)'},
                                   legend={'orientation': 'h', 'y': 1.15, 'x': 0.5, 'xanchor': 'center'})
            st.plotly_chart(fig_dist, width='stretch')

    with ac2:
        st.markdown('<div class="section-head">⚡ Speed vs Physics Risk Profile</div>', unsafe_allow_html=True)
        if vehicles:
            s_data = pd.DataFrame([{'v': k, 'spd': v['speed']*3.6, 'cri': max(v.get('cri_left',0), v.get('cri_right',0)), 'alrt': max(v.get('alert_left','SAFE'), v.get('alert_right','SAFE'), key=lambda a: ['SAFE','CAUTION','WARNING','CRITICAL'].index(a))} for k, v in vehicles.items()])
            fig_sc = go.Figure()
            for alrt in ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL']:
                sub = s_data[s_data['alrt'] == alrt]
                if sub.empty: continue # type: ignore
                fig_sc.add_trace(go.Scatter(x=sub['spd'], y=sub['cri'], mode='markers',
                                            marker={'size': 12, 'color': alert_color(alrt), 'opacity': 0.8, 'line': {'width': 1, 'color': '#fff'}},
                                            name=f"{alert_emoji(alrt)} {alrt}", text=sub['v'], hovertemplate="<b>%{text}</b><br>%{x:.1f} km/h<br>CRI: %{y:.3f}"))
            fig_sc.update_layout(plot_bgcolor='rgba(0,0,0,0.2)', paper_bgcolor='rgba(0,0,0,0)', font={'family': 'Outfit', 'color': '#f8fafc'},
                                 height=350, margin={'l': 20, 'r': 10, 't': 30, 'b': 20}, xaxis={'title': 'Speed (km/h)', 'gridcolor': 'rgba(255,255,255,0.05)'},
                                 yaxis={'title': 'Max CRI', 'range': [0, 1], 'gridcolor': 'rgba(255,255,255,0.05)'},
                                 legend={'orientation': 'h', 'y': 1.15, 'x': 0.5, 'xanchor': 'center'})
            st.plotly_chart(fig_sc, width='stretch')

    if metrics_df is not None and not metrics_df.empty:
        st.markdown('<div class="section-head">📈 Historical CRI & Threat Escalation</div>', unsafe_allow_html=True)
        top_v = metrics_df.groupby('ego_vid')[['cri_left', 'cri_right']].max().max(axis=1).nlargest(10).index.tolist()
        if top_v:
            t_vid = st.selectbox("Select Target Vehicle Trajectory", top_v)
            t_data = metrics_df[metrics_df['ego_vid'] == t_vid]
            
            fig_tr = make_subplots(rows=2, cols=1, row_heights=[0.7, 0.3], shared_xaxes=True, vertical_spacing=0.08)
            fig_tr.add_trace(go.Scatter(x=t_data['step']*0.1, y=t_data['cri_left'], name='CRI Left', line={'color': '#a855f7', 'width': 2}, fill='tozeroy', fillcolor='rgba(168, 85, 247, 0.1)'), row=1, col=1)
            fig_tr.add_trace(go.Scatter(x=t_data['step']*0.1, y=t_data['cri_right'], name='CRI Right', line={'color': '#3b82f6', 'width': 2}, fill='tozeroy', fillcolor='rgba(59, 130, 246, 0.1)'), row=1, col=1)
            for t, c in [(0.3, '#f59e0b'), (0.6, '#f97316'), (0.8, '#ef4444')]:
                fig_tr.add_hline(y=t, line_dash="dot", line_color=c, opacity=0.5, row=1, col=1)
            fig_tr.add_trace(go.Scatter(x=t_data['step']*0.1, y=t_data['speed']*3.6, name='Speed (km/h)', line={'color': '#10b981', 'width': 2}), row=2, col=1)
            fig_tr.update_layout(plot_bgcolor='rgba(0,0,0,0.2)', paper_bgcolor='rgba(0,0,0,0)', font={'family': 'Outfit', 'color': '#f8fafc'},
                                 height=450, margin={'l': 20, 'r': 20, 't': 20, 'b': 20}, hovermode='x unified')
            fig_tr.update_xaxes(gridcolor='rgba(255,255,255,0.05)', title='Simulation Time (s)', row=2, col=1)
            fig_tr.update_yaxes(gridcolor='rgba(255,255,255,0.05)', title='Risk Index', range=[0, 1.05], row=1, col=1)
            fig_tr.update_yaxes(gridcolor='rgba(255,255,255,0.05)', title='km/h', row=2, col=1)
            st.plotly_chart(fig_tr, width='stretch')


# ------------------------------------------------------------
# TAB 3: SYSTEM LOGS & PARAMETERS
# ------------------------------------------------------------
with tab_system:
    sc1, sc2 = st.columns([2, 1])
    with sc1:
        st.markdown('<div class="section-head">🚨 Complete Alert Sub-system History</div>', unsafe_allow_html=True)
        if alerts_df is not None and not alerts_df.empty:
            d_df = alerts_df.tail(100).sort_values('step', ascending=False).copy()
            st.dataframe(d_df.style.background_gradient(cmap='RdYlGn_r', subset=['cri_left', 'cri_right', 'top_cri'], vmin=0, vmax=1),
                         width='stretch', hide_index=True, height=450)
        else:
            st.info("No recorded critical events in memory.")

    with sc2:
        st.markdown('<div class="section-head">📡 Mesh Topology Metrics</div>', unsafe_allow_html=True)
        t_l = sum(v.get('num_targets', 0) for v in vehicles.values())
        m_plr = max([t.get('plr', 0) for v in vehicles.values() for t in v.get('top_threats', [])], default=0)
        q_col = '#10b981' if m_plr < 0.1 else '#f59e0b' if m_plr < 0.3 else '#ef4444'
        
        st.markdown(f"""
        <div class="sidebar-panel" style="text-align: center;">
            <div style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 5px;">ACTIVE P2P LINKS (DSRC)</div>
            <div style="font-size: 2.5rem; font-weight: 800; font-family: 'JetBrains Mono'; color: #8b5cf6;">{t_l}</div>
            <div style="color: #64748b; font-size: 0.75rem;">10Hz Broadcasting active</div>
        </div>
        <div class="sidebar-panel" style="text-align: center;">
            <div style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 5px;">MAX NETWORK PACKET LOSS</div>
            <div style="font-size: 2.5rem; font-weight: 800; font-family: 'JetBrains Mono'; color: {q_col};">{m_plr:.0%}</div>
            <div style="color: #64748b; font-size: 0.75rem;">Quality state: {'Stable' if m_plr < 0.1 else 'Degraded' if m_plr < 0.3 else 'Critical'}</div>
        </div>
        """, unsafe_allow_html=True)

        if live_data and 'params' in live_data:
            st.markdown('<div class="section-head">⚙️ Math Core Constants (v2.4)</div>', unsafe_allow_html=True)
            p = live_data['params']
            p_html = "".join([f"<div style='display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.05);'><span>{k}</span><strong style='color:#a855f7;'>{v}</strong></div>" for k, v in p.items()])
            st.markdown(f"<div class='sidebar-panel' style='font-family: inherit; font-size: 0.85rem;'>{p_html}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------
# TAB 4: V2V COMMUNICATIONS
# ------------------------------------------------------------
with tab_v2v:
    st.markdown('<div class="section-head">🔗 Direct Vehicle-To-Vehicle Mesh Links (BSM)</div>', unsafe_allow_html=True)
    if not vehicles:
        st.info("No vehicles currently active in simulation.")
    else:
        comm_rows = ""
        for vid, vdata in vehicles.items():
            threats = vdata.get('top_threats', [])
            if not threats:
                continue
            for t in threats:
                plr_val = t.get('plr', 0)
                plr_bar_color = '#10b981' if plr_val < 0.1 else '#f59e0b' if plr_val < 0.3 else '#ef4444'
                link_quality = 'Excellent' if plr_val < 0.05 else 'Good' if plr_val < 0.15 else 'Degraded' if plr_val < 0.3 else 'Poor'
                cri_val = t.get('cri', 0)
                
                comm_rows += f"""
                <div style="display: flex; justify-content: space-between; align-items: center; 
                            padding: 16px; margin: 12px 0; background: rgba(15, 20, 31, 0.7); 
                            border-radius: 12px; border: 1px solid rgba(255,255,255,0.08);
                            border-left: 4px solid {cri_color(cri_val)};">
                    <div style="flex: 1;">
                        <span style="color: #f8fafc; font-weight: 700; font-family: 'JetBrains Mono'; font-size: 1.1rem;">{vid}</span>
                        <span style="color: #64748b; margin: 0 12px; font-size: 1.2rem;"> ↔ </span>
                        <span style="color: #f8fafc; font-weight: 700; font-family: 'JetBrains Mono'; font-size: 1.1rem;">{t['vid']}</span>
                    </div>
                    <div style="flex: 1.5; text-align: center;">
                        <span style="font-size: 0.9rem; color: #94a3b8;">Target Prob = <strong style="color: #f8fafc;">{t['P']:.3f}</strong></span>
                        <span style="margin: 0 12px; color: #334155;">|</span>
                        <span style="font-size: 0.9rem; color: #94a3b8;">Bumper Gap = <strong style="color: #f8fafc;">{t['d_gap']:.1f}m</strong></span>
                    </div>
                    <div style="flex: 1; text-align: center;">
                        <span style="font-size: 0.8rem; color: #94a3b8; display: block; margin-bottom: 4px;">Link Quality: <strong style="color: {plr_bar_color}">{link_quality}</strong></span>
                        <div style="background: rgba(0,0,0,0.5); height: 8px; border-radius: 4px; width: 100px; display: inline-block;">
                            <div style="background: {plr_bar_color}; height: 100%; width: {max(5, (1-plr_val)*100):.0f}%; border-radius: 4px;"></div>
                        </div>
                    </div>
                    <div style="flex: 0.5; text-align: right;">
                        <div style="color: {cri_color(cri_val)}; font-weight: 800; font-size: 1.3rem; font-family: 'JetBrains Mono';">CRI: {cri_val:.3f}</div>
                    </div>
                </div>
                """
        if comm_rows:
            st.markdown(comm_rows, unsafe_allow_html=True)
        else:
            st.success("✅ No imminent threat communications found. Network is relatively quiet.")


# ============================================================

if vehicles:
    s_vids = sorted(vehicles.keys(), key=lambda v: max(vehicles[v].get('cri_left',0), vehicles[v].get('cri_right',0)), reverse=True)
    sel_vid = st.sidebar.selectbox("TARGET LOCK", s_vids, format_func=lambda v: f"{v} • {alert_emoji(max(vehicles[v].get('alert_left','SAFE'), vehicles[v].get('alert_right','SAFE'), key=lambda a: ['SAFE','CAUTION','WARNING','CRITICAL'].index(a)))}")

    if sel_vid and sel_vid in vehicles:
        vd = vehicles[sel_vid]
        st.sidebar.markdown(f"""
        <div class="sidebar-panel">
            <h3 style="margin:0 0 10px; color:#f8fafc; font-size:1.2rem;">UNIT {sel_vid}</h3>
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span style="color:#94a3b8;">Velocity</span>
                <strong style="font-family:'JetBrains Mono';">{vd.get('speed',0)*3.6:.1f} km/h</strong>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <span style="color:#94a3b8;">Local Threats</span>
                <strong style="color:#ef4444;">{vd.get('num_targets',0)}</strong>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if has_ai:
            ai_a = vd.get('ai_alert', 'N/A')
            ai_c = vd.get('ai_confidence', 0.0)
            if ai_a != 'N/A':
                st.sidebar.markdown(f"""
                <div class="sidebar-panel" style="background: rgba(99, 102, 241, 0.05); border-color: rgba(99, 102, 241, 0.3);">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span style="font-weight:700; color:#a855f7;">🤖 AI ENGINE</span>
                        <strong style="color:{alert_color(ai_a)};">{alert_emoji(ai_a)} {ai_a}</strong>
                    </div>
                    <div>
                        <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94a3b8; margin-bottom:4px;">
                            <span>Model Confidence</span><span>{ai_c:.1%}</span>
                        </div>
                        <div style="height:6px; background:rgba(0,0,0,0.5); border-radius:3px; overflow:hidden;">
                            <div style="height:100%; width:{ai_c*100}%; background:linear-gradient(90deg, #6366f1, #a855f7);"></div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        # Radar for top threat
        threats = vd.get('top_threats', [])
        if threats:
            st.sidebar.markdown("<div style='font-size:0.9rem; font-weight:700; color:#f8fafc; margin-top:15px; margin-bottom:10px;'>📡 PHYSICS THREAT PROFILE</div>", unsafe_allow_html=True)
            tt = threats[0]
            
            rf = go.Figure(go.Scatterpolar(
                r=[tt['P'], tt['R_decel'], tt.get('R_ttc_lon', 0.0), tt.get('R_ttc_lat', 0.0), tt['R_intent'], tt['P']],
                theta=['Probability', 'Brake Risk', 'TTC Lon', 'TTC Lat', 'Intent Risk', 'Probability'],
                fill='toself',
                fillcolor=f"{alert_color(cri_color(tt['cri']))}",
                opacity=0.6,
                line={'color': alert_color(cri_color(tt['cri'])), 'width': 2}
            ))
            rf.update_layout(
                polar={
                    'radialaxis': {'visible': False, 'range': [0, 1]},
                    'angularaxis': {'color': '#f8fafc', 'gridcolor': 'rgba(255,255,255,0.1)'},
                    'bgcolor': 'rgba(0,0,0,0)'
                },
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=220,
                margin={'l': 30, 'r': 30, 't': 20, 'b': 20},
                font={'family': 'Outfit'}
            )
            st.sidebar.plotly_chart(rf, width='stretch')
            
            # Threat metrics summary
            st.sidebar.markdown(f"""
            <div class="threat-details">
                <div style="color:{alert_color(cri_color(tt['cri']))}; font-weight:800; font-size:1.1rem; text-align:center; margin-bottom:10px;">
                    CRI = {tt['cri']:.3f}
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.8rem;"><span>Gap:</span><strong>{tt['d_gap']:.1f}m</strong></div>
                <div style="display:flex; justify-content:space-between; font-size:0.8rem;"><span>Side:</span><strong>{tt['side']}</strong></div>
                <div style="display:flex; justify-content:space-between; font-size:0.8rem;"><span>Network PLR:</span><strong style="color:{'#ef4444' if tt['plr']>0.3 else '#10b981'};">{tt['plr']:.0%}</strong></div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.sidebar.success("✅ No imminent threats detected.")
else:
    st.sidebar.info("Awaiting Vehicle States.")