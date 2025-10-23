# ============================================================
# V2V Real-Time Dashboard - Streamlit Application
# ============================================================
# FIXED: Missing import for st_autorefresh
# ============================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

# Try to import streamlit autorefresh, if not available use fallback
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ============================================================
# PATH CONFIGURATION
# ============================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "Outputs"
METRICS_FILE = OUTPUT_DIR / "live_metrics.csv"

# ============================================================
# PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="V2V Accident Prevention",
    page_icon="🚗",
    layout="wide"
)

st.title("🚗 V2V Accident Prevention Dashboard")
st.markdown("**Real-time monitoring of vehicle collision risks using AI-powered V2V communication**")

# ============================================================
# AUTO-REFRESH (if available)
# ============================================================
if HAS_AUTOREFRESH:
    st_autorefresh(interval=3000, key="dashboard_refresh")
else:
    st.info("💡 Tip: Install streamlit-autorefresh for auto-refresh: `pip install streamlit-autorefresh`")
    st.write("You can manually refresh the page (F5) to see updates")

# ============================================================
# LOAD LIVE METRICS
# ============================================================
def load_live_metrics():
    """Load the latest vehicle metrics from simulation"""
    try:
        if not METRICS_FILE.exists():
            return None, f"File not found"
        
        df = pd.read_csv(str(METRICS_FILE))
        return df, None
        
    except Exception as e:
        return None, f"Error: {str(e)}"

# Load data
df, error = load_live_metrics()

if error:
    st.error(f"⚠️ {error}")
    st.stop()

if df is None or df.empty:
    st.warning("⚠️ Waiting for data...")
    st.stop()

# ============================================================
# FAST COLLISION RISK CALCULATION (Vectorized)
# ============================================================
def compute_risk_vectorized(df_latest):
    """
    Fast collision risk calculation using vectorized operations
    """
    risk_scores = np.zeros(len(df_latest))
    nearest_dist = np.full(len(df_latest), np.inf)
    
    x = df_latest['x'].values
    y = df_latest['y'].values
    accel = df_latest['accel'].values
    
    # Component 1: Sudden braking detection
    braking_mask = accel < -2.0
    risk_scores[braking_mask] = np.minimum(1.0, np.abs(accel[braking_mask]) / 5.0) * 0.6
    
    # Component 2: Distance to nearest vehicle
    for i in range(len(df_latest)):
        dx = x - x[i]
        dy = y - y[i]
        distances = np.sqrt(dx**2 + dy**2)
        distances[i] = np.inf
        
        min_dist = np.nanmin(distances)
        if min_dist < 50:
            proximity_risk = (1 - min_dist / 50)
            risk_scores[i] += proximity_risk * 0.4
        
        nearest_dist[i] = min_dist
    
    risk_scores = np.minimum(risk_scores, 1.0)
    
    return risk_scores, nearest_dist

# ============================================================
# PROCESS DATA (FAST)
# ============================================================
latest_df = df.sort_values(by='ts').groupby('id').tail(1).reset_index(drop=True).copy()

risk_scores, nearest_distances = compute_risk_vectorized(latest_df)

latest_df['collision_risk'] = risk_scores
latest_df['nearest_dist'] = nearest_distances

high_risk_df = latest_df[latest_df['collision_risk'] > 0.5].copy()

# ============================================================
# METRICS
# ============================================================
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🚗 Active Vehicles", len(latest_df))
with col2:
    st.metric("⚠️ High Risk", len(high_risk_df), f"{len(high_risk_df)/len(latest_df)*100:.1f}%" if len(latest_df) > 0 else "0%")
with col3:
    st.metric("📊 Total Data Points", f"{len(df):,}")
with col4:
    st.metric("🕐 Step", int(df['ts'].max()))

st.markdown("---")

# ============================================================
# ALERTS
# ============================================================
if not high_risk_df.empty:
    st.error(f"🚨 COLLISION RISK ALERT: {len(high_risk_df)} vehicle(s) in danger!")
    alert_df = high_risk_df[['id', 'speed', 'accel', 'collision_risk', 'nearest_dist']].copy()
    alert_df['speed'] = alert_df['speed'].round(2)
    alert_df['accel'] = alert_df['accel'].round(2)
    alert_df['collision_risk'] = alert_df['collision_risk'].round(3)
    alert_df['nearest_dist'] = alert_df['nearest_dist'].round(2)
    alert_df.columns = ['ID', 'Speed (m/s)', 'Accel (m/s²)', 'Risk', 'Distance (m)']
    st.dataframe(alert_df.style.background_gradient(cmap='Reds', subset=['Risk']), use_container_width=True, hide_index=True)
else:
    st.success("✅ ALL CLEAR - No high-risk vehicles")

st.markdown("---")

# ============================================================
# MAP
# ============================================================
st.subheader("📍 Live Vehicle Positions")

fig_map = go.Figure()

fig_map.add_trace(go.Scatter(
    x=latest_df['x'],
    y=latest_df['y'],
    mode='markers+text',
    marker=dict(
        size=12,
        color=latest_df['collision_risk'],
        colorscale='RdYlGn_r',
        cmin=0,
        cmax=1,
        colorbar=dict(title="Risk"),
        line=dict(width=1.5, color='black'),
    ),
    text=[f"{int(row['id'])}" for _, row in latest_df.iterrows()],
    textposition="top center",
    textfont=dict(size=8, color='black'),
    customdata=latest_df[['speed', 'collision_risk']].values,
    hovertemplate="<b>%{text}</b><br>Pos: (%{x:.0f}, %{y:.0f})<br>Speed: %{customdata[0]:.1f}m/s<br>Risk: %{customdata[1]:.2f}",
))

fig_map.update_layout(
    title="Vehicle Positions",
    xaxis_title="X (m)",
    yaxis_title="Y (m)",
    height=600,
    plot_bgcolor='#f0f0f0',
)

st.plotly_chart(fig_map, use_container_width=True)

# ============================================================
# TABLE
# ============================================================
st.subheader("📋 Top 20 Vehicles by Risk")

display_df = latest_df[['id', 'speed', 'accel', 'x', 'y', 'ts', 'collision_risk']].copy()
display_df = display_df.round(2)
display_df = display_df.sort_values(by='collision_risk', ascending=False).head(20)
display_df.columns = ['ID', 'Speed', 'Accel', 'X', 'Y', 'Step', 'Risk']

st.dataframe(display_df.style.background_gradient(cmap='RdYlGn_r', subset=['Risk']), use_container_width=True, hide_index=True)

# ============================================================
# VEHICLE TRENDS
# ============================================================
st.markdown("---")
st.subheader("🚦 Vehicle Trends")

if len(df['id'].unique()) > 0:
    vehicle_ids = sorted(df['id'].unique().tolist())[:50]
    selected_vehicle = st.selectbox("Select Vehicle:", vehicle_ids)
    
    vehicle_data = df[df['id'] == selected_vehicle].sort_values(by='ts').copy()
    
    if len(vehicle_data) > 0:
        vehicle_data['speed_prev'] = vehicle_data['speed'].shift(1)
        vehicle_data['collision_risk'] = np.where(
            vehicle_data['accel'] < -2.0,
            np.minimum(1.0, np.abs(vehicle_data['accel']) / 5.0),
            0.0
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_speed = go.Figure()
            fig_speed.add_trace(go.Scatter(x=vehicle_data['ts'], y=vehicle_data['speed'], mode='lines+markers', line=dict(color='blue', width=2)))
            fig_speed.update_layout(title=f"Speed - Vehicle {selected_vehicle}", xaxis_title="Step", yaxis_title="Speed (m/s)", height=400)
            st.plotly_chart(fig_speed, use_container_width=True)
        
        with col2:
            fig_risk = go.Figure()
            fig_risk.add_trace(go.Scatter(x=vehicle_data['ts'], y=vehicle_data['collision_risk'], mode='lines+markers', line=dict(color='red', width=2), fill='tozeroy'))
            fig_risk.add_hline(y=0.5, line_dash="dash", line_color="orange")
            fig_risk.update_layout(title=f"Risk - Vehicle {selected_vehicle}", xaxis_title="Step", yaxis_title="Risk", yaxis=dict(range=[0,1]), height=400)
            st.plotly_chart(fig_risk, use_container_width=True)

st.markdown("---")
st.caption("🔄 Dashboard running | Refresh page (F5) to see updates")