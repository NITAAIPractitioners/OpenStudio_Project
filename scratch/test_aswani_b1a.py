import sys
from pathlib import Path

# Add the aswani_model directory to sys.path so we can import the modified script
sys.path.append(r"C:\Users\me.com\Documents\engery\OpenStudio_Project\aswani_model")

import run_track_b_experiments as rbe

def test_b1a():
    params_a = {
        "stage": "TEST_B1a",
        "eq_density": 20.0,
        "eq_sch_type": "Scaled",
        "oa_rate": 0.010,
        "infiltration": 0.5,
        "use_baseline": True
    }
    
    print(">>> STARTING ASWANI B1a TEST RUN...")
    run_id = rbe.run_simulation(params_a)
    if run_id:
        print(f">>> SUCCESS: Simulation completed in {run_id}")
        metrics = rbe.get_metrics(run_id)
        if metrics:
            print(f">>> SUCCESS: Metrics retrieved: {metrics}")
        else:
            print(">>> ERROR: Failed to retrieve metrics.")
    else:
        print(">>> ERROR: Simulation failed.")

if __name__ == "__main__":
    test_b1a()
