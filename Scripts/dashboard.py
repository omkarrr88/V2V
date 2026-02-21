"""
V2V Blind Spot Detection — Real-Time Dashboard
================================================
Premium Streamlit dashboard for monitoring the V2V BSD simulation.
Displays real-time CRI values, alert levels, vehicle maps, and risk analytics.

Usage:
    streamlit run dashboard.py
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
from pathlib import Path

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="V2V BSD Dashboard",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# CUSTOM CSS — Premium Dark Theme
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Root variables */
:root {
    --bg-primary: #0a0e17;
    --bg-card: #111827;
    --bg-card-hover: #1a2332;
    --accent-green: #10b981;
    --accent-yellow: #f59e0b;
    --accent-orange: #f97316;
    --accent-red: #ef4444;
    --accent-blue: #3b82f6;
    --accent-purple: #8b5cf6;
    --text-primary: #f1f5f9;
    --text-secondary: #94a3b8;
    --border: #1e293b;
}

/* Global */
.stApp {
    font-family: 'Inter', sans-serif !important;
}

/* Metric cards */
.metric-card {
    background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-card-hover) 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px 24px;
    text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0,0,0,0.3);
}
.metric-value {
    font-size: 2.2rem;
    font-weight: 800;
    line-height: 1.1;
    margin: 8px 0 4px;
}
.metric-label {
    font-size: 0.85rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 600;
}

/* Alert badges */
.alert-safe { color: var(--accent-green); }
.alert-caution { color: var(--accent-yellow); }
.alert-warning { color: var(--accent-orange); }
.alert-critical { color: var(--accent-red); animation: pulse 1.5s infinite; }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Section headers */
.section-header {
    font-size: 1.3rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 1.5rem 0 1rem;
    padding-bottom: 8px;
    border-bottom: 2px solid var(--accent-purple);
    display: inline-block;
}

/* Status indicator */
.status-dot {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    margin-right: 6px;
    animation: blink 2s infinite;
}
.status-dot.live { background: var(--accent-green); }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Vehicle detail table */
.threat-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px;
    margin: 8px 0;
}

/* Side CRI bars */
.cri-bar-container {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 6px 0;
}
.cri-bar-label {
    font-weight: 600;
    font-size: 0.9rem;
    min-width: 60px;
}
.cri-bar-bg {
    flex: 1;
    height: 24px;
    background: #1e293b;
    border-radius: 12px;
    overflow: hidden;
    position: relative;
}
.cri-bar-fill {
    height: 100%;
    border-radius: 12px;
    transition: width 0.5s ease;
}

/* Hide Streamlit's default elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
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
    """Load the latest live simulation data."""
    try:
        if os.path.exists(LIVE_FILE):
            with open(LIVE_FILE, 'r') as f:
                return json.load(f), None
    except Exception as e:
        return None, str(e)
    return None, "No live data file found"


@st.cache_data(ttl=5)
def load_metrics():
    """Load historical metrics CSV."""
    try:
        if os.path.exists(METRICS_FILE):
            df = pd.read_csv(METRICS_FILE)
            return df, None
    except Exception as e:
        return None, str(e)
    return None, "No metrics file found"


@st.cache_data(ttl=5)
def load_alerts():
    """Load alert history CSV."""
    try:
        if os.path.exists(ALERTS_FILE):
            df = pd.read_csv(ALERTS_FILE)
            return df, None
    except Exception as e:
        return None, str(e)
    return None, "No alerts file found"


def cri_color(cri: float) -> str:
    """Return color based on CRI value."""
    if cri >= 0.80: return "#ef4444"
    if cri >= 0.60: return "#f97316"
    if cri >= 0.30: return "#f59e0b"
    return "#10b981"


def alert_color(alert: str) -> str:
    """Return color for alert level."""
    colors = {
        'SAFE': '#10b981', 'CAUTION': '#f59e0b',
        'WARNING': '#f97316', 'CRITICAL': '#ef4444'
    }
    return colors.get(alert, '#64748b')


def alert_emoji(alert: str) -> str:
    emojis = {'SAFE': '🟢', 'CAUTION': '🟡', 'WARNING': '🟠', 'CRITICAL': '🔴'}
    return emojis.get(alert, '⚪')


# ============================================================
# AUTO-REFRESH
# ============================================================
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=2000, key="dashboard_refresh")
except ImportError:
    pass


# ============================================================
# HEADER
# ============================================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px;">
        <span style="font-size: 2.5rem;">🛡️</span>
        <div>
            <h1 style="margin: 0; font-size: 1.8rem; font-weight: 800; 
                background: linear-gradient(135deg, #8b5cf6 0%, #3b82f6 50%, #10b981 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                V2V Blind Spot Detection
            </h1>
            <p style="margin: 0; color: #94a3b8; font-size: 0.9rem;">
                Mathematical Model V2.4 • Real-Time SUMO Dashboard
            </p>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_h2:
    st.markdown("""
    <div style="text-align: right; padding-top: 8px;">
        <span class="status-dot live"></span>
        <span style="color: #10b981; font-weight: 600;">LIVE</span>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# LOAD DATA
# ============================================================
live_data, live_err = load_live_data()
metrics_df, metrics_err = load_metrics()
alerts_df, alerts_err = load_alerts()

if live_data is None and metrics_df is None:
    st.markdown("""
    <div style="text-align: center; padding: 80px 20px;">
        <span style="font-size: 4rem;">🚦</span>
        <h2 style="margin: 20px 0 10px; color: #f1f5f9;">Waiting for Simulation Data...</h2>
        <p style="color: #94a3b8; font-size: 1.1rem;">
            Start the simulation with: <code>python v2v_bsd_simulation.py</code>
        </p>
        <p style="color: #64748b; font-size: 0.9rem; margin-top: 10px;">
            The dashboard will auto-update when data arrives.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ============================================================
# TOP METRICS BAR
# ============================================================
vehicles = live_data.get('vehicles', {}) if live_data else {}
alert_counts = live_data.get('alert_counts', {}) if live_data else {}
current_step = live_data.get('step', 0) if live_data else 0
active_count = live_data.get('active_count', 0) if live_data else 0
has_ai = live_data.get('has_ai', False) if live_data else False

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Active Vehicles</div>
        <div class="metric-value" style="color: #3b82f6;">{active_count}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    safe = alert_counts.get('safe', 0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🟢 Safe</div>
        <div class="metric-value alert-safe">{safe}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    caution = alert_counts.get('caution', 0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🟡 Caution</div>
        <div class="metric-value alert-caution">{caution}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    warning = alert_counts.get('warning', 0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🟠 Warning</div>
        <div class="metric-value alert-warning">{warning}</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    critical = alert_counts.get('critical', 0)
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">🔴 Critical</div>
        <div class="metric-value alert-critical">{critical}</div>
    </div>
    """, unsafe_allow_html=True)

ai_badge = '<span style="background: linear-gradient(135deg, #8b5cf6, #3b82f6); color: white; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">🤖 AI Active</span>' if has_ai else '<span style="background: #334155; color: #94a3b8; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">AI: Not Loaded</span>'
st.markdown(f"""
<div style="text-align: center; color: #64748b; font-size: 0.8rem; margin: 8px 0 16px;">
    Simulation Step: <strong>{current_step}</strong> • 
    Time: <strong>{current_step * 0.1:.1f}s</strong> •
    {ai_badge}
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ============================================================
# LIVE VEHICLE MAP
# ============================================================
st.markdown('<div class="section-header">📍 Live Vehicle Map</div>', unsafe_allow_html=True)

if vehicles:
    map_data = []
    for vid, vdata in vehicles.items():
        max_cri = max(vdata.get('cri_left', 0), vdata.get('cri_right', 0))
        max_alert = 'SAFE'
        for alert in ['alert_left', 'alert_right']:
            a = vdata.get(alert, 'SAFE')
            if ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL'].index(a) > \
               ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL'].index(max_alert):
                max_alert = a
        
        map_data.append({
            'vid': vid,
            'x': vdata['x'], 'y': vdata['y'],
            'speed': vdata.get('speed', 0),
            'cri_left': vdata.get('cri_left', 0),
            'cri_right': vdata.get('cri_right', 0),
            'max_cri': max_cri,
            'alert': max_alert,
            'color': alert_color(max_alert),
        })
    
    map_df = pd.DataFrame(map_data)
    
    fig_map = go.Figure()
    
    for alert_level in ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL']:
        subset = map_df[map_df['alert'] == alert_level]
        if subset.empty:
            continue
        fig_map.add_trace(go.Scatter(
            x=subset['x'], y=subset['y'],
            mode='markers',
            marker=dict(
                size=np.where(subset['alert'] == 'CRITICAL', 16,
                     np.where(subset['alert'] == 'WARNING', 14,
                     np.where(subset['alert'] == 'CAUTION', 12, 8))),
                color=alert_color(alert_level),
                line=dict(width=1, color='rgba(255,255,255,0.3)'),
                symbol='circle',
            ),
            name=f"{alert_emoji(alert_level)} {alert_level}",
            text=[f"ID: {r['vid']}<br>Speed: {r['speed']:.1f} m/s<br>"
                  f"CRI Left: {r['cri_left']:.3f}<br>CRI Right: {r['cri_right']:.3f}"
                  for _, r in subset.iterrows()],
            hoverinfo='text',
        ))
    
    fig_map.update_layout(
        plot_bgcolor='#0a0e17',
        paper_bgcolor='#0a0e17',
        font=dict(family='Inter', color='#f1f5f9'),
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02,
            xanchor='center', x=0.5,
            font=dict(size=12),
            bgcolor='rgba(17,24,39,0.8)',
        ),
        xaxis=dict(title='X (m)', gridcolor='#1e293b', zerolinecolor='#334155'),
        yaxis=dict(title='Y (m)', gridcolor='#1e293b', zerolinecolor='#334155',
                   scaleanchor='x'),
    )
    
    st.plotly_chart(fig_map, width='stretch')
else:
    st.info("No vehicles currently in simulation.")


# ============================================================
# SIDEBAR: VEHICLE INSPECTOR
# ============================================================
st.sidebar.markdown("""
<div style="text-align: center; padding: 10px 0;">
    <h2 style="margin: 0; font-size: 1.3rem; font-weight: 700;">🔍 Vehicle Inspector</h2>
</div>
""", unsafe_allow_html=True)

if vehicles:
    # Sort vehicles by max CRI (most dangerous first)
    sorted_vids = sorted(vehicles.keys(),
                         key=lambda v: max(vehicles[v].get('cri_left', 0),
                                          vehicles[v].get('cri_right', 0)),
                         reverse=True)

    selected_vid = st.sidebar.selectbox(
        "Select Vehicle",
        sorted_vids,
        format_func=lambda v: f"{v} — {alert_emoji(max(vehicles[v].get('alert_left','SAFE'), vehicles[v].get('alert_right','SAFE'), key=lambda a: ['SAFE','CAUTION','WARNING','CRITICAL'].index(a)))} CRI: {max(vehicles[v].get('cri_left',0), vehicles[v].get('cri_right',0)):.3f}"
    )

    if selected_vid and selected_vid in vehicles:
        vdata = vehicles[selected_vid]
        
        st.sidebar.markdown(f"### Vehicle `{selected_vid}`")
        st.sidebar.markdown(f"**Speed:** {vdata.get('speed', 0):.1f} m/s ({vdata.get('speed', 0) * 3.6:.1f} km/h)")
        st.sidebar.markdown(f"**Targets in range:** {vdata.get('num_targets', 0)}")
        
        # AI Model Prediction
        ai_alert = vdata.get('ai_alert', 'N/A')
        ai_conf = vdata.get('ai_confidence', 0.0)
        if ai_alert != 'N/A':
            ai_col = alert_color(ai_alert)
            ai_em = alert_emoji(ai_alert)
            st.sidebar.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e1b4b 0%, #1e293b 100%);
                        border: 1px solid #4338ca; border-radius: 12px; padding: 12px; margin: 8px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 700; color: #a78bfa;">🤖 AI Prediction</span>
                    <span style="color: {ai_col}; font-weight: 800; font-size: 1.1rem;">{ai_em} {ai_alert}</span>
                </div>
                <div style="margin-top: 6px;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #94a3b8;">
                        <span>Confidence</span>
                        <span>{ai_conf:.1%}</span>
                    </div>
                    <div style="background: #1e293b; height: 6px; border-radius: 3px; margin-top: 3px;">
                        <div style="background: linear-gradient(90deg, #8b5cf6, #3b82f6); height: 100%; width: {ai_conf*100:.0f}%; border-radius: 3px;"></div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Side-specific CRI display
        st.sidebar.markdown("#### Blind Spot Risk (Math Model)")
        
        for side in ['left', 'right']:
            cri_val = vdata.get(f'cri_{side}', 0)
            alert_val = vdata.get(f'alert_{side}', 'SAFE')
            color = alert_color(alert_val)
            emoji = alert_emoji(alert_val)
            
            st.sidebar.markdown(f"""
            <div style="margin: 8px 0;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-weight: 600;">{emoji} {side.upper()}</span>
                    <span style="color: {color}; font-weight: 700;">{cri_val:.4f}</span>
                </div>
                <div style="background: #1e293b; height: 10px; border-radius: 5px; margin-top: 4px;">
                    <div style="background: {color}; height: 100%; width: {min(cri_val * 100, 100):.1f}%; 
                         border-radius: 5px; transition: width 0.5s;"></div>
                </div>
                <div style="text-align: right; font-size: 0.75rem; color: #64748b;">{alert_val}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Top threats
        threats = vdata.get('top_threats', [])
        if threats:
            st.sidebar.markdown("#### Top Threats")
            for t in threats:
                side_emoji = "⬅️" if t['side'] == 'LEFT' else "➡️"
                st.sidebar.markdown(f"""
                <div class="threat-card">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-weight: 600;">{side_emoji} {t['vid']}</span>
                        <span style="color: {cri_color(t['cri'])}; font-weight: 700;">CRI: {t['cri']:.4f}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 4px;">
                        P={t['P']:.3f} | R_dec={t['R_decel']:.3f} | R_ttc={t['R_ttc']:.3f} | 
                        R_int={t['R_intent']:.3f} | Gap={t['d_gap']:.1f}m | PLR={t['plr']:.2f}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.sidebar.info("No threats detected")

# Model Parameters in sidebar  
st.sidebar.markdown("---")
st.sidebar.markdown("#### ⚙️ Model Parameters (V2.4)")
if live_data and 'params' in live_data:
    params = live_data['params']
    param_text = "\n".join([f"• **{k}** = {v}" for k, v in params.items()])
    st.sidebar.markdown(param_text)


# ============================================================
# V2V COMMUNICATION STATUS PANEL
# ============================================================
st.markdown("---")
st.markdown('<div class="section-header">📡 V2V Communication Status (DSRC/C-V2X)</div>', unsafe_allow_html=True)

v2v_col1, v2v_col2, v2v_col3, v2v_col4 = st.columns(4)

# Calculate communication stats from vehicle data
total_links = 0
total_targets = 0
max_plr = 0.0
vehicles_with_threats = 0

for vid, vdata in vehicles.items():
    n_targets = vdata.get('num_targets', 0)
    total_targets += n_targets
    if n_targets > 0:
        total_links += n_targets
    threats = vdata.get('top_threats', [])
    if threats:
        vehicles_with_threats += 1
        for t in threats:
            if t.get('plr', 0) > max_plr:
                max_plr = t['plr']

with v2v_col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">BSM Frequency</div>
        <div class="metric-value" style="color: #3b82f6;">10 Hz</div>
        <div style="font-size: 0.75rem; color: #64748b;">SAE J2735 DSRC</div>
    </div>
    """, unsafe_allow_html=True)

with v2v_col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Active V2V Links</div>
        <div class="metric-value" style="color: #8b5cf6;">{total_links}</div>
        <div style="font-size: 0.75rem; color: #64748b;">Within {int(live_data.get('params', {}).get('R_comm', 300) if live_data and 'params' in live_data else 300)}m range</div>
    </div>
    """, unsafe_allow_html=True)

with v2v_col3:
    plr_color = '#10b981' if max_plr < 0.1 else '#f59e0b' if max_plr < 0.3 else '#ef4444'
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Max Packet Loss</div>
        <div class="metric-value" style="color: {plr_color};">{max_plr:.0%}</div>
        <div style="font-size: 0.75rem; color: #64748b;">PLR window: 10 packets</div>
    </div>
    """, unsafe_allow_html=True)

with v2v_col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Active Threats</div>
        <div class="metric-value" style="color: {'#ef4444' if vehicles_with_threats > 0 else '#10b981'};">{vehicles_with_threats}</div>
        <div style="font-size: 0.75rem; color: #64748b;">Vehicles in blind spots</div>
    </div>
    """, unsafe_allow_html=True)

# V2V Communication Detail Table
if vehicles_with_threats > 0:
    st.markdown("""
    <div style="margin-top: 16px; padding: 16px; background: linear-gradient(135deg, #111827 0%, #1a2332 100%); 
                border: 1px solid #1e293b; border-radius: 12px;">
        <div style="font-weight: 700; color: #a78bfa; margin-bottom: 12px;">
            🔗 Active V2V Data Exchange (BSM Packets)
        </div>
    """, unsafe_allow_html=True)
    
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
                        padding: 8px 12px; margin: 4px 0; background: #0f172a; border-radius: 8px;
                        border-left: 3px solid {cri_color(cri_val)};">
                <div style="flex: 1;">
                    <span style="color: #f1f5f9; font-weight: 600;">{vid}</span>
                    <span style="color: #64748b;"> ↔ </span>
                    <span style="color: #f1f5f9; font-weight: 600;">{t['vid']}</span>
                </div>
                <div style="flex: 1; text-align: center;">
                    <span style="font-size: 0.75rem; color: #94a3b8;">P={t['P']:.3f}</span>
                    <span style="margin: 0 4px; color: #334155;">|</span>
                    <span style="font-size: 0.75rem; color: #94a3b8;">Gap={t['d_gap']:.1f}m</span>
                </div>
                <div style="flex: 0.6; text-align: center;">
                    <div style="background: #1e293b; height: 6px; border-radius: 3px; width: 60px; display: inline-block; vertical-align: middle;">
                        <div style="background: {plr_bar_color}; height: 100%; width: {max(5, (1-plr_val)*100):.0f}%; border-radius: 3px;"></div>
                    </div>
                    <span style="font-size: 0.7rem; color: {plr_bar_color}; margin-left: 4px;">{link_quality}</span>
                </div>
                <div style="flex: 0.4; text-align: right;">
                    <span style="color: {cri_color(cri_val)}; font-weight: 700; font-size: 0.85rem;">CRI {cri_val:.3f}</span>
                </div>
            </div>
            """
    
    st.markdown(comm_rows + "</div>", unsafe_allow_html=True)

# ============================================================
# ALERT TIMELINE & ANALYTICS
# ============================================================
st.markdown("---")

col_left, col_right = st.columns(2)

# ── CRI Distribution ──
with col_left:
    st.markdown('<div class="section-header">📊 CRI Distribution</div>', unsafe_allow_html=True)
    
    if vehicles:
        cri_values_left = [v.get('cri_left', 0) for v in vehicles.values()]
        cri_values_right = [v.get('cri_right', 0) for v in vehicles.values()]
        
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Histogram(
            x=cri_values_left, name='CRI Left',
            marker_color='#8b5cf6', opacity=0.7,
            nbinsx=30,
        ))
        fig_dist.add_trace(go.Histogram(
            x=cri_values_right, name='CRI Right',
            marker_color='#3b82f6', opacity=0.7,
            nbinsx=30,
        ))
        
        # Threshold lines
        for thresh, name, color in [(0.3, 'CAUTION', '#f59e0b'), 
                                     (0.6, 'WARNING', '#f97316'),
                                     (0.8, 'CRITICAL', '#ef4444')]:
            fig_dist.add_vline(x=thresh, line_dash="dash", line_color=color,
                              annotation_text=name, annotation_position="top")
        
        fig_dist.update_layout(
            barmode='overlay',
            plot_bgcolor='#0a0e17', paper_bgcolor='#0a0e17',
            font=dict(family='Inter', color='#f1f5f9', size=11),
            height=350,
            margin=dict(l=20, r=20, t=30, b=30),
            xaxis=dict(title='CRI Value', range=[0, 1], gridcolor='#1e293b'),
            yaxis=dict(title='Count', gridcolor='#1e293b'),
            legend=dict(orientation='h', y=1.1, x=0.5, xanchor='center'),
        )
        st.plotly_chart(fig_dist, width='stretch')

# ── Speed vs CRI ──
with col_right:
    st.markdown('<div class="section-header">⚡ Speed vs Max CRI</div>', unsafe_allow_html=True)
    
    if vehicles:
        scatter_data = pd.DataFrame([
            {
                'vid': vid,
                'speed': v.get('speed', 0),
                'max_cri': max(v.get('cri_left', 0), v.get('cri_right', 0)),
                'alert': max(v.get('alert_left', 'SAFE'), v.get('alert_right', 'SAFE'),
                           key=lambda a: ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL'].index(a)),
            }
            for vid, v in vehicles.items()
        ])
        
        fig_scatter = go.Figure()
        for alert_level in ['SAFE', 'CAUTION', 'WARNING', 'CRITICAL']:
            subset = scatter_data[scatter_data['alert'] == alert_level]
            if subset.empty:
                continue
            fig_scatter.add_trace(go.Scatter(
                x=subset['speed'] * 3.6,  # m/s to km/h
                y=subset['max_cri'],
                mode='markers',
                marker=dict(size=8, color=alert_color(alert_level), opacity=0.8),
                name=f"{alert_emoji(alert_level)} {alert_level}",
                text=subset['vid'],
                hovertemplate='%{text}<br>Speed: %{x:.1f} km/h<br>CRI: %{y:.4f}',
            ))
        
        fig_scatter.update_layout(
            plot_bgcolor='#0a0e17', paper_bgcolor='#0a0e17',
            font=dict(family='Inter', color='#f1f5f9', size=11),
            height=350,
            margin=dict(l=20, r=20, t=30, b=30),
            xaxis=dict(title='Speed (km/h)', gridcolor='#1e293b'),
            yaxis=dict(title='Max CRI', range=[0, 1], gridcolor='#1e293b'),
            legend=dict(orientation='h', y=1.1, x=0.5, xanchor='center'),
        )
        st.plotly_chart(fig_scatter, width='stretch')


# ============================================================
# HISTORICAL TRENDS
# ============================================================
st.markdown("---")
st.markdown('<div class="section-header">📈 Historical CRI Trends</div>', unsafe_allow_html=True)

if metrics_df is not None and not metrics_df.empty:
    # Pick top vehicles by max CRI
    latest = metrics_df.groupby('ego_vid').agg({
        'cri_left': 'max', 'cri_right': 'max'
    }).reset_index()
    latest['max_cri'] = latest[['cri_left', 'cri_right']].max(axis=1)
    top_vehicles = latest.nlargest(10, 'max_cri')['ego_vid'].tolist()
    
    if top_vehicles:
        selected_trend_vid = st.selectbox(
            "Select vehicle for trend analysis",
            top_vehicles,
            key="trend_vid"
        )
        
        trend_data = metrics_df[metrics_df['ego_vid'] == selected_trend_vid].copy()
        
        if not trend_data.empty:
            fig_trend = make_subplots(
                rows=2, cols=1,
                row_heights=[0.6, 0.4],
                shared_xaxes=True,
                vertical_spacing=0.08,
                subplot_titles=['CRI Over Time', 'Speed & Acceleration'],
            )
            
            # CRI trends
            fig_trend.add_trace(go.Scatter(
                x=trend_data['step'] * 0.1,
                y=trend_data['cri_left'],
                mode='lines',
                name='CRI Left',
                line=dict(color='#8b5cf6', width=2),
                fill='tozeroy',
                fillcolor='rgba(139, 92, 246, 0.1)',
            ), row=1, col=1)
            
            fig_trend.add_trace(go.Scatter(
                x=trend_data['step'] * 0.1,
                y=trend_data['cri_right'],
                mode='lines',
                name='CRI Right',
                line=dict(color='#3b82f6', width=2),
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.1)',
            ), row=1, col=1)
            
            # Threshold lines
            for thresh, color in [(0.3, '#f59e0b'), (0.6, '#f97316'), (0.8, '#ef4444')]:
                fig_trend.add_hline(y=thresh, line_dash="dot", line_color=color,
                                    line_width=1, row=1, col=1)
            
            # Speed
            fig_trend.add_trace(go.Scatter(
                x=trend_data['step'] * 0.1,
                y=trend_data['speed'] * 3.6,
                mode='lines',
                name='Speed (km/h)',
                line=dict(color='#10b981', width=1.5),
            ), row=2, col=1)
            
            fig_trend.update_layout(
                plot_bgcolor='#0a0e17', paper_bgcolor='#0a0e17',
                font=dict(family='Inter', color='#f1f5f9', size=11),
                height=500,
                margin=dict(l=20, r=20, t=40, b=20),
                legend=dict(orientation='h', y=1.08, x=0.5, xanchor='center'),
            )
            fig_trend.update_xaxes(gridcolor='#1e293b', title_text='Time (s)', row=2, col=1)
            fig_trend.update_yaxes(gridcolor='#1e293b', range=[0, 1], title_text='CRI', row=1, col=1)
            fig_trend.update_yaxes(gridcolor='#1e293b', title_text='km/h', row=2, col=1)
            
            st.plotly_chart(fig_trend, width='stretch')
else:
    st.info("📊 Run the simulation to generate historical data.")


# ============================================================
# ALERT LOG TABLE
# ============================================================
st.markdown("---")
st.markdown('<div class="section-header">🚨 Alert Log</div>', unsafe_allow_html=True)

if alerts_df is not None and not alerts_df.empty:
    recent_alerts = alerts_df.tail(50).sort_values('step', ascending=False)
    
    # Color code the dataframe
    display_df = recent_alerts[['step', 'ego_vid', 'cri_left', 'cri_right', 
                                 'alert_left', 'alert_right', 'top_threat', 'top_cri']].copy()
    display_df.columns = ['Step', 'Vehicle', 'CRI Left', 'CRI Right', 
                           'Alert Left', 'Alert Right', 'Top Threat', 'Max CRI']
    
    st.dataframe(
        display_df.style.background_gradient(
            cmap='RdYlGn_r', subset=['CRI Left', 'CRI Right', 'Max CRI'],
            vmin=0, vmax=1
        ),
        width='stretch', 
        hide_index=True,
        height=400,
    )
else:
    st.info("No alerts recorded yet.")


# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 20px 0; color: #475569;">
    <p style="margin: 0; font-size: 0.85rem;">
        🛡️ V2V Blind Spot Detection System • Mathematical Model V2.4 • 
        SUMO Simulation • Research Project
    </p>
    <p style="margin: 4px 0 0; font-size: 0.75rem; color: #334155;">
        Parameters: α=0.35 β=0.45 γ=0.20 ε=0.30 | Thresholds: θ₁=0.30 θ₂=0.60 θ₃=0.80 | σ_GPS=1.5m
    </p>
</div>
""", unsafe_allow_html=True)