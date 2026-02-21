"""
V2V BSD Project — Run Everything
=================================
1. Run the SUMO simulation with V2.4 BSD engine
2. Launch the real-time dashboard

Usage:
    python run.py              — Run simulation with GUI
    python run.py --no-gui     — Run headless
    python run.py --dashboard  — Launch dashboard only
"""

import subprocess
import sys
import os
import time


def main():
    dashboard_only = "--dashboard" in sys.argv
    
    if dashboard_only:
        print("🖥️  Launching dashboard...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard.py", 
                       "--server.port", "8501"], cwd=os.path.dirname(__file__) or ".")
        return

    # Run simulation
    sim_args = [sys.executable, "v2v_bsd_simulation.py"]
    if "--no-gui" in sys.argv:
        sim_args.append("--no-gui")
    
    steps = "3600"
    for i, arg in enumerate(sys.argv):
        if arg == "--steps" and i + 1 < len(sys.argv):
            steps = sys.argv[i + 1]
    sim_args.extend(["--steps", steps])

    print("=" * 70)
    print("🚀 V2V Blind Spot Detection System")
    print("   Mathematical Model V2.4")
    print("=" * 70)
    print()
    print("1️⃣  Starting SUMO simulation...")
    print("2️⃣  Open another terminal and run:")
    print("    cd Scripts && streamlit run dashboard.py")
    print()
    
    subprocess.run(sim_args, cwd=os.path.dirname(__file__) or ".")


if __name__ == "__main__":
    main()
