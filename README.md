# Vehicle-to-Vehicle Communication System for Blind Spots and Accident Prevention

*An AI-powered V2V simulator for preventing collisions in urban traffic - Final Year BE Project*


---

## Features
This V2V system is a complete simulation-based accident prevention tool with these key features:
- **Real-time V2V Communication** – Vehicles broadcast position, speed, and acceleration data
- **AI Collision Prediction** – Random Forest model detects risks with 92% accuracy
- **Traffic Simulation** – SUMO-based modeling of 1,440+ vehicles on Mumbai road networks
- **Scenario Generation** – 200+ customizable traffic scenarios with varying speeds and risks
- **Live Dashboard** – Streamlit interface showing vehicle trends, risk maps, and alerts
- **Data Logging** – CSV exports of 18,000+ telemetry records and collision predictions
- **Visual Alerts** – Color-coded warnings (red=danger, green=safe) in SUMO GUI

---

## Tech Stack
| Technology | Purpose |
|------------------|-----------------------------|
| SUMO + TraCI | Traffic simulation and control |
| Python | Core scripting and integration |
| scikit-learn | Random Forest ML model |
| pandas + NumPy | Data processing and analysis |
| Streamlit + Plotly | Real-time web dashboard |
| OpenStreetMap | Road network data |
| Git | Version control |

---

## Project Structure
```
v2v-project/
├── dashboard.py          # Streamlit dashboard for visualization
├── generate_scenarios.py # Creates 200 traffic scenarios
├── train_ai.py           # Trains Random Forest ML model
├── v2v_sim.py            # Main V2V simulation with SUMO integration
├── Maps/                 # OSM and SUMO network files
│   ├── atal.osm.xml
│   ├── atal.net.xml
│   └── atal.rou.xml
├── Outputs/              # Generated data and models
│   ├── collisions.csv
│   ├── live_metrics.csv
│   └── rf_model.pkl
├── Scenarios/            # Scenario data
│   └── scenarios.csv
└── README.md             # This file
```

---

## Key Features in Detail
### V2V Communication Simulator
- Simulates DSRC-like messaging between vehicles
- Processes 1,400+ vehicle pairs in real-time
- Logs predictions for 11,144 potential collisions

### AI Prediction Engine
- Trained on 10,000 synthetic scenarios
- Features: speed, distance, acceleration/deceleration
- 92% accuracy with physics-inspired labels
- Feature importance: Distance (45%), Speed A (21%)

### Interactive Dashboard
- Real-time metrics: Active vehicles, high-risk count, data points
- Vehicle trends: Speed and risk charts with Plotly
- Risk table: Top 20 high-risk vehicles with color gradients
- Auto-refresh every 3 seconds

---

## How to Run Locally
1. **Install SUMO**  
   Download from [Eclipse SUMO](https://www.eclipse.org/sumo/) and set `SUMO_HOME` environment variable.

2. **Clone the repository**  
   ```bash
   git clone https://github.com/omkar-kadam/v2v-accident-prevention.git
   cd v2v-accident-prevention
   ```

3. **Install Python dependencies**  
   ```bash
   pip install traci sumolib scikit-learn pandas numpy joblib streamlit plotly
   ```

4. **Generate Scenarios**  
   ```bash
   python generate_scenarios.py
   ```

5. **Train AI Model**  
   ```bash
   python train_ai.py
   ```

6. **Run Simulation**  
   ```bash
   python v2v_sim.py
   ```

7. **Launch Dashboard**  
   ```bash
   streamlit run dashboard.py
   ```
   Access at: http://localhost:8501

---

## Dataset Source
- Road networks from OpenStreetMap (Mumbai Atal area)
- 10,000 synthetic training samples generated in-script
- Real-time data from SUMO simulations

## Made with ❤️ by Omkar Kadam 

**Star this repo if you found it useful!**  
Feel free to fork, improve, and contribute.

---

**"Preventing accidents before they happen – The future of smart transportation."**
